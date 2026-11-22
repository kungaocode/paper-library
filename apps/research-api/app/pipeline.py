from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable
from uuid import uuid4

import numpy as np

from . import analysis, synthesis
from .chunking import build_category_chunks, build_paper_chunks
from .config import ANALYSIS_PROMPT_VERSION, ResearchSettings
from .corpus import (
    PaperLibraryReader,
    load_category_positioning,
    pdf_is_readable,
    resolve_pdf_path,
)
from .embeddings import HashingEmbedder
from .provider import ProviderError, ResearchProvider, build_provider
from .retrieval import RetrievalBackend, RetrievalError, build_backend
from .schemas import (
    CorpusSyncResult,
    DeepAnalysisRecord,
    Direction,
    EvidenceCard,
    ExperimentPlan,
    FollowupItem,
    Idea,
    IdeationRun,
    IndexStats,
    PlatformStatus,
    ResearchJob,
    ResearchJobResult,
    SearchHit,
    utc_now,
)
from .store import ResearchStore


class PipelineError(RuntimeError):
    pass


# (stage, progress_percent, message)
ProgressFn = Callable[[str, int, str], None]


# Evidence packs are assembled from a wider retrieval pool than they hold, so a
# single dominant paper cannot starve the cross-paper citation check downstream.
EVIDENCE_POOL_FACTOR = 3
EVIDENCE_POOL_CAP = 40


@dataclass
class DeepAnalysisSummary:
    scanned: int = 0
    analyzed: int = 0
    cached: int = 0
    skipped_no_pdf: int = 0
    failed: int = 0
    model: str = ""
    prompt_version: str = ANALYSIS_PROMPT_VERSION
    errors: list[str] = field(default_factory=list)

    def as_detail(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "analyzed": self.analyzed,
            "cached": self.cached,
            "skipped_no_pdf": self.skipped_no_pdf,
            "failed": self.failed,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "errors": self.errors[:20],
            "message": (
                f"深度解析完成：新解析 {self.analyzed} 篇，复用 {self.cached} 篇，"
                f"失败 {self.failed} 篇，无 PDF {self.skipped_no_pdf} 篇"
            ),
        }


@dataclass
class IdeationRequest:
    """What one evolution round should do. Everything has a safe default."""

    queries: list[str] = field(default_factory=list)
    generation: int = 0
    max_queries: int = 3
    top_k: int = 0
    ideas_per_query: int = 2
    max_directions: int = 3
    max_experiments: int = 2
    user_feedback: str = ""
    parent_direction_id: str = ""
    # Caller-supplied id so the HTTP job record and the IdeationRun agree.
    batch_id: str = ""


class ResearchPipeline:
    """Orchestrates corpus -> index -> deep analysis -> ideas -> directions -> loop.

    The reading platform is only ever read (see corpus.PaperLibraryReader); every
    write here lands in storage/research/research.sqlite3.
    """

    def __init__(
        self,
        settings: ResearchSettings | None = None,
        store: ResearchStore | None = None,
        backend: RetrievalBackend | None = None,
        provider: ResearchProvider | None = None,
    ) -> None:
        self.settings = settings or ResearchSettings.from_env()
        self.settings.ensure_directories()
        self.store = store or ResearchStore(self.settings.database_path)
        if backend is None:
            backend, notice = build_backend(self.store, self.settings)
        else:
            notice = ""
        self.backend = backend
        self.backend_notice = notice
        self._provider = provider
        self._embedder = HashingEmbedder()
        # One heavy job at a time: keeps SQLite writes and model spend predictable.
        self._lock = asyncio.Lock()

    # ---------------- provider / backend helpers ----------------

    @property
    def provider(self) -> ResearchProvider:
        if self._provider is None:
            self._provider = build_provider(self.settings)
        return self._provider

    @property
    def provider_label(self) -> str:
        return self.settings.llm_provider

    @property
    def model_label(self) -> str:
        if self.settings.llm_model:
            return self.settings.llm_model
        return "mock-research" if self.settings.llm_provider.lower() == "mock" else ""

    def knowledge_vector_available(self) -> bool:
        root = self.settings.knowledge_vector_root
        if not root:
            return False
        base = Path(root).expanduser()
        return (base / "src" / "knowledge_vector").is_dir() or (
            base / "knowledge_vector"
        ).is_dir()

    # ---------------- stage B: corpus sync ----------------

    def sync_corpus(self, *, category_id: str = "") -> CorpusSyncResult:
        reader = PaperLibraryReader(self.settings)
        cards = reader.load_cards()

        result = CorpusSyncResult(scanned=len(cards))
        for card in cards:
            if category_id and card.category_id != category_id:
                continue
            try:
                pdf_exists = pdf_is_readable(card.pdf_path, self.settings.paper_root)
                action = self.store.upsert_paper(card, pdf_exists=pdf_exists)
                if action == "created":
                    result.created += 1
                elif action == "updated":
                    result.updated += 1
                else:
                    result.unchanged += 1
                if not pdf_exists:
                    result.missing_pdf += 1
                stored = self.store.get_paper(card.paper_id)
                if stored and stored.needs_deep_analysis:
                    result.needs_deep_analysis += 1
            except Exception as error:  # noqa: BLE001 - one bad row must not stop the sync
                result.errors.append(f"{card.paper_id}: {error}")

        result.total = self.store.count_papers()
        result.errors = result.errors[:20]
        self.store.set_meta("corpus_synced_at", utc_now())
        return result

    def corpus_overview(self) -> dict[str, Any]:
        papers = self.store.list_papers(limit=100000)
        ready = {
            record.paper_id
            for record in self.store.list_deep_analyses(
                status="ready", prompt_version=ANALYSIS_PROMPT_VERSION, limit=100000
            )
        }
        categories = self.store.category_counts()
        return {
            "papers": len(papers),
            "categories": categories,
            "deep_analysis_ready": len(ready),
            "needs_deep_analysis": len([p for p in papers if p.paper_id not in ready]),
            "synced_at": self.store.get_meta("corpus_synced_at"),
            "index_updated_at": self.store.get_meta("index_updated_at"),
            "index_stale": self.store.get_meta("index_stale") == "1",
            "reading_platform_database": str(self.settings.paper_database_path),
            "reading_platform_access": "read-only",
        }

    # ---------------- stage C: index ----------------

    def rebuild_index(self, *, category_id: str = "") -> IndexStats:
        cards = self.store.list_papers(category_id=category_id, limit=100000)
        if not cards:
            raise PipelineError(
                "语料库为空，无法建立索引。请先调用 POST /api/research/corpus/sync。"
            )

        deep = {
            record.paper_id: record
            for record in self.store.list_deep_analyses(
                status="ready", prompt_version=ANALYSIS_PROMPT_VERSION, limit=100000
            )
        }
        for card in cards:
            record = deep.get(card.paper_id)
            self.store.replace_paper_chunks(
                card.paper_id,
                build_paper_chunks(
                    card, deep=record.model_dump(mode="json") if record else None
                ),
            )

        positioning = load_category_positioning(self.settings.knowledge_base_path)
        names = {
            row["category_id"]: row["category_name"] for row in self.store.category_counts()
        }
        self.store.replace_chunks_by_kind(
            "category.positioning", build_category_chunks(positioning, names)
        )

        self._index_generated_content()
        embedded = self._embed_new_chunks()
        self.store.set_meta("index_updated_at", utc_now())
        self.store.set_meta("index_stale", "0")
        self.store.set_meta("index_embedded_last", str(embedded))
        return self.index_stats()

    def ensure_index(self) -> None:
        """Rebuild when the index is missing or was invalidated by new analyses."""
        stale = self.store.get_meta("index_stale") == "1"
        if stale or self.store.chunk_count() == 0:
            self.rebuild_index()

    def index_stats(self) -> IndexStats:
        try:
            return self.backend.stats()
        except RetrievalError as error:
            raise PipelineError(str(error)) from error

    def search(
        self, query: str, *, top_k: int = 0, mode: str = "hybrid"
    ) -> list[SearchHit]:
        if mode not in {"hybrid", "lexical", "vector"}:
            raise PipelineError(f"不支持的检索模式：{mode}")
        limit = top_k or self.settings.retrieval_top_k
        try:
            return self.backend.search(query, top_k=limit, mode=mode)
        except RetrievalError as error:
            raise PipelineError(str(error)) from error

    def _index_generated_content(self) -> None:
        ideas = self.store.list_ideas(limit=1000)
        directions = self.store.list_directions(limit=500)
        chunks = synthesis.build_generated_chunks(ideas, directions)
        by_kind: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for chunk_id, data in chunks:
            by_kind.setdefault(data["kind"], []).append((chunk_id, data))
        for kind in (synthesis.KIND_IDEA, synthesis.KIND_DIRECTION):
            self.store.replace_chunks_by_kind(kind, by_kind.get(kind, []))

    def _embed_new_chunks(self) -> int:
        embed = getattr(self.backend, "embed_missing_chunks", None)
        if callable(embed):
            return int(embed())
        return 0

    # ---------------- stage D: deep analysis ----------------

    def analysis_estimate(
        self, *, limit: int = 0, category_id: str = "", force: bool = False
    ) -> dict[str, Any]:
        papers = self.store.list_papers(category_id=category_id, limit=100000)
        ready = {
            record.paper_id
            for record in self.store.list_deep_analyses(
                status="ready", prompt_version=ANALYSIS_PROMPT_VERSION, limit=100000
            )
        }
        pending = [paper for paper in papers if paper.paper_id not in ready]
        # A forced run re-reads the whole scope, so its cost estimate must be
        # based on every paper in scope rather than the (possibly empty)
        # pending list -- otherwise the job announces "0 篇" and then bills 3.
        candidates = papers if force else pending
        selected = candidates[:limit] if limit > 0 else candidates
        missing_pdf = [
            paper.paper_id
            for paper in selected
            if resolve_pdf_path(paper.pdf_path, self.settings.paper_root) is None
        ]
        est_chars = sum(
            min(
                self.settings.analysis_max_chars,
                max(1, paper.page_count or 20) * 2600,
            )
            for paper in selected
        )
        return {
            "papers_total": len(papers),
            "already_ready": len(ready),
            "pending": len(pending),
            "selected": len(selected),
            "force": force,
            "missing_pdf": missing_pdf[:20],
            "missing_pdf_count": len(missing_pdf),
            "estimated_prompt_chars": est_chars,
            "estimated_model_calls": len(selected),
            "page_limit": self.settings.analysis_page_limit,
            "concurrency": self.settings.analysis_concurrency,
            "prompt_version": ANALYSIS_PROMPT_VERSION,
            "model": self.model_label,
        }

    async def run_deep_analysis(
        self,
        *,
        limit: int = 0,
        category_id: str = "",
        force: bool = False,
        progress: ProgressFn | None = None,
    ) -> DeepAnalysisSummary:
        report = _progress(progress)
        papers = self.store.list_papers(category_id=category_id, limit=100000)
        if not papers:
            raise PipelineError("语料库为空，请先执行语料同步。")

        provider = self.provider  # raises ProviderError early when unconfigured
        summary = DeepAnalysisSummary(scanned=len(papers), model=self.model_label)

        targets: list[EvidenceCard] = []
        for card in papers:
            existing = self.store.get_deep_analysis(card.paper_id, ANALYSIS_PROMPT_VERSION)
            if existing and existing.status == "ready" and not force:
                summary.cached += 1
                continue
            targets.append(card)
        if limit > 0:
            targets = targets[:limit]

        total = len(targets)
        report("analyzing", 5, f"待解析 {total} 篇（已复用 {summary.cached} 篇）")
        if not total:
            return summary

        semaphore = asyncio.Semaphore(self.settings.analysis_concurrency)
        done = 0

        async def handle(card: EvidenceCard) -> None:
            nonlocal done
            async with semaphore:
                outcome = await self._analyze_one(card, provider)
            status, error = outcome
            if status == "ready":
                summary.analyzed += 1
            elif status == "skipped":
                summary.skipped_no_pdf += 1
            else:
                summary.failed += 1
                if error:
                    summary.errors.append(f"{card.title_zh or card.title}: {error}")
            done += 1
            report(
                "analyzing",
                5 + int(90 * done / total),
                f"深度解析 {done}/{total}：{card.title_zh or card.title}",
            )

        await asyncio.gather(*(handle(card) for card in targets))
        summary.errors = summary.errors[:20]
        self.store.set_meta("index_stale", "1")
        report("analyzing", 100, summary.as_detail()["message"])
        return summary

    async def _analyze_one(
        self, card: EvidenceCard, provider: ResearchProvider
    ) -> tuple[str, str]:
        path = resolve_pdf_path(card.pdf_path, self.settings.paper_root)
        if path is None:
            self.store.set_deep_analysis_status(card.paper_id, "failed")
            self.store.save_deep_analysis(
                DeepAnalysisRecord(
                    id=f"deep-{card.paper_id}-{ANALYSIS_PROMPT_VERSION}",
                    paper_id=card.paper_id,
                    paper_title=card.title_zh or card.title,
                    prompt_version=ANALYSIS_PROMPT_VERSION,
                    status="failed",
                    model=self.model_label,
                    error="PDF 不可读或不在论文仓库内",
                    created_at=utc_now(),
                )
            )
            return "skipped", "PDF 不可读"

        self.store.set_deep_analysis_status(card.paper_id, "pending")
        try:
            extracted = await asyncio.to_thread(analysis.extract_paper, self.settings, card)
            system_prompt, user_prompt = analysis.build_analysis_prompt(
                self.settings, card, extracted
            )
            raw = await provider.generate_json(
                system_prompt=system_prompt, user_prompt=user_prompt, purpose="deep_analysis"
            )
            normalized = analysis.normalize_deep_analysis(
                raw, int(getattr(extracted, "page_count", 0) or 0)
            )
        except (ProviderError, analysis.AnalysisError) as error:
            return self._record_analysis_failure(card, str(error))
        except Exception as error:  # noqa: BLE001 - keep the batch alive
            return self._record_analysis_failure(
                card, f"{error.__class__.__name__}: {error}"
            )

        record = DeepAnalysisRecord(
            id=f"deep-{card.paper_id}-{ANALYSIS_PROMPT_VERSION}",
            paper_id=card.paper_id,
            paper_title=card.title_zh or card.title,
            prompt_version=ANALYSIS_PROMPT_VERSION,
            status="ready",
            problem=normalized["problem"],
            method=normalized["method"],
            findings=normalized["findings"],
            innovations=normalized["innovations"],
            limitations=normalized["limitations"],
            model=self.model_label,
            created_at=utc_now(),
        )
        self.store.save_deep_analysis(record)
        self.store.set_deep_analysis_status(card.paper_id, "ready")
        return "ready", ""

    def _record_analysis_failure(self, card: EvidenceCard, message: str) -> tuple[str, str]:
        self.store.save_deep_analysis(
            DeepAnalysisRecord(
                id=f"deep-{card.paper_id}-{ANALYSIS_PROMPT_VERSION}",
                paper_id=card.paper_id,
                paper_title=card.title_zh or card.title,
                prompt_version=ANALYSIS_PROMPT_VERSION,
                status="failed",
                model=self.model_label,
                error=message[:600],
                created_at=utc_now(),
            )
        )
        self.store.set_deep_analysis_status(card.paper_id, "failed")
        return "failed", message[:300]

    # ---------------- stages E/F/G: ideation ----------------

    async def run_ideation(
        self,
        request: IdeationRequest | None = None,
        *,
        progress: ProgressFn | None = None,
    ) -> IdeationRun:
        request = request or IdeationRequest()
        report = _progress(progress)

        if self.store.count_papers() == 0:
            raise PipelineError("语料库为空，请先执行 POST /api/research/corpus/sync。")
        report("indexing", 5, "检查向量索引")
        await asyncio.to_thread(self.ensure_index)

        provider = self.provider
        batch_id = request.batch_id or f"batch-{uuid4().hex[:10]}"
        generation = request.generation or (self.store.max_generation() + 1)
        run = IdeationRun(
            batch_id=batch_id,
            status="running",
            generation=generation,
            provider=self.provider_label,
            model=self.model_label,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.store.save_run(run)

        papers = self.store.list_papers(limit=100000)
        known_paper_ids = {card.paper_id for card in papers}
        category_by_paper = {
            card.paper_id: card.category_id for card in papers if card.category_id
        }
        titles = self.store.paper_titles(known_paper_ids)

        queries = [q.strip() for q in request.queries if q.strip()][: request.max_queries]
        if not queries:
            queries = self._default_queries(request.max_queries)

        accepted: list[Idea] = []
        existing_vectors = self._existing_idea_vectors()
        skipped_queries: list[str] = []

        span = max(1, len(queries))
        for index, query in enumerate(queries):
            base = 10 + int(45 * index / span)
            report("ideating", base, f"检索证据：{query}")
            limit = request.top_k or self.settings.retrieval_top_k
            pool = self.search(
                query,
                top_k=max(limit, min(limit * EVIDENCE_POOL_FACTOR, EVIDENCE_POOL_CAP)),
                mode="hybrid",
            )
            hits = synthesis.diversify_by_paper(pool, limit=limit)
            pack = synthesis.build_evidence_pack(query, hits)
            if not pack.hits:
                skipped_queries.append(query)
                continue

            report("ideating", base + 5, f"整合创新点：{query}")
            raw = await provider.generate_json(
                system_prompt=synthesis.IDEATION_SYSTEM_PROMPT,
                user_prompt=synthesis.render_ideation_prompt(
                    query=query,
                    pack=pack,
                    corpus_size=(self.store.count_papers(), self.store.chunk_count()),
                    idea_count=max(1, request.ideas_per_query),
                    generation=generation,
                ),
                purpose="ideation",
            )

            known_chunk_ids = set(pack.chunk_ids)
            for item in _as_list(raw.get("ideas"), raw):
                idea, reason = synthesis.normalize_idea(
                    item,
                    batch_id=batch_id,
                    generation=generation,
                    known_paper_ids=known_paper_ids,
                    known_chunk_ids=known_chunk_ids,
                    category_by_paper=category_by_paper,
                )
                # Dedupe outranks the citation gate: an idea this corpus already
                # produced is a repeat no matter how thin its citations are, and
                # "已探索过" is the verdict the next generation needs to see.
                # Unparseable output stays a structural failure.
                if reason not in synthesis.STRUCTURAL_REASONS:
                    vector = self._embedder.embed_query(synthesis.idea_signature(idea))
                    duplicate = synthesis.find_duplicate(
                        vector, existing_vectors, self.settings.dedupe_threshold
                    )
                    if duplicate:
                        reason = f"与已有想法重复，已合并到 {duplicate}"
                    elif not reason:
                        existing_vectors.append((idea.id, vector))
                if reason:
                    idea.rejected_reason = reason
                    run.ideas_rejected += 1
                    # Idea ids are derived from (batch, title), so the same idea
                    # can come back from another query. A later duplicate must
                    # not downgrade the row that already passed review, or its
                    # directions would point at a rejected idea.
                    if not any(kept.id == idea.id for kept in accepted):
                        self.store.save_idea(idea)
                    continue

                idea = await self._critique_idea(idea, pack, provider)
                run.ideas_accepted += 1
                self.store.save_idea(idea)
                accepted.append(idea)
            run.ideas_total = run.ideas_accepted + run.ideas_rejected
            run.updated_at = utc_now()
            self.store.save_run(run)

        if not accepted:
            run.status = "succeeded"
            run.message = (
                "本轮没有通过引用校验的想法，未生成方向。"
                + (f" 无命中的查询：{'；'.join(skipped_queries)}" if skipped_queries else "")
            )
            run.updated_at = utc_now()
            self.store.save_run(run)
            report("ideating", 100, run.message)
            return run

        directions = await self._build_directions(
            accepted=accepted,
            batch_id=batch_id,
            generation=generation,
            titles=titles,
            known_paper_ids=known_paper_ids,
            request=request,
            provider=provider,
            report=report,
            run=run,
        )
        await self._build_experiments(
            directions=directions,
            accepted=accepted,
            batch_id=batch_id,
            titles=titles,
            request=request,
            provider=provider,
            report=report,
            run=run,
        )

        await asyncio.to_thread(self._index_generated_content)
        self._embed_new_chunks()
        self.store.set_meta("index_stale", "1")
        self.store.set_meta("last_ideation_batch", batch_id)

        run.status = "succeeded"
        run.message = (
            f"第 {generation} 代演化完成：{run.ideas_accepted} 条想法、"
            f"{run.directions_total} 个方向、{run.experiments_total} 份实验方案、"
            f"{run.followups_total} 条待办"
        )
        run.updated_at = utc_now()
        self.store.save_run(run)
        report("succeeded", 100, run.message)
        return run

    async def _critique_idea(
        self, idea: Idea, pack: synthesis.EvidencePack, provider: ResearchProvider
    ) -> Idea:
        try:
            raw = await provider.generate_json(
                system_prompt=synthesis.CRITIQUE_SYSTEM_PROMPT,
                user_prompt=synthesis.render_critique_prompt(idea=idea, pack=pack),
                purpose="critique",
            )
        except ProviderError as error:
            idea.critique = {"error": str(error)[:300]}
            return idea
        return synthesis.apply_critique(idea, synthesis.normalize_critique(raw))

    async def _build_directions(
        self,
        *,
        accepted: list[Idea],
        batch_id: str,
        generation: int,
        titles: dict[str, str],
        known_paper_ids: set[str],
        request: IdeationRequest,
        provider: ResearchProvider,
        report: ProgressFn,
        run: IdeationRun,
    ) -> list[Direction]:
        report("clustering", 65, "聚合研究方向")
        parent = self._resolve_parent_direction(request, generation)
        known_direction_ids = {
            direction.id for direction in self.store.list_directions(limit=1000)
        }
        raw = await provider.generate_json(
            system_prompt=synthesis.DIRECTION_SYSTEM_PROMPT,
            user_prompt=synthesis.render_direction_prompt(
                ideas=accepted,
                titles=titles,
                generation=generation,
                parent=parent,
                feedback=request.user_feedback,
            ),
            purpose="direction",
        )

        directions: list[Direction] = []
        rejected: list[str] = []
        for item in _as_list(raw.get("directions"), raw):
            direction, reason = synthesis.normalize_direction(
                item,
                batch_id=batch_id,
                generation=generation,
                known_idea_ids={idea.id for idea in accepted},
                known_paper_ids=known_paper_ids,
                known_direction_ids=known_direction_ids,
            )
            if reason:
                rejected.append(reason)
                continue
            if not direction.source_paper_ids:
                direction.source_paper_ids = _merge_paper_ids(
                    idea.source_paper_ids
                    for idea in accepted
                    if idea.id in set(direction.member_idea_ids)
                )
            self.store.save_direction(direction)
            known_direction_ids.add(direction.id)
            directions.append(direction)
            if len(directions) >= max(1, request.max_directions):
                break

        run.directions_total = len(directions)
        if rejected:
            run.message = f"方向校验丢弃 {len(rejected)} 条：{rejected[0]}"
        run.updated_at = utc_now()
        self.store.save_run(run)
        return directions

    async def _build_experiments(
        self,
        *,
        directions: list[Direction],
        accepted: list[Idea],
        batch_id: str,
        titles: dict[str, str],
        request: IdeationRequest,
        provider: ResearchProvider,
        report: ProgressFn,
        run: IdeationRun,
    ) -> list[ExperimentPlan]:
        if not directions:
            return []
        ordered = sorted(directions, key=lambda item: item.priority, reverse=True)
        selected = ordered[: max(1, request.max_experiments)]
        plans: list[ExperimentPlan] = []
        for index, direction in enumerate(selected):
            report(
                "experiment",
                75 + int(20 * index / max(1, len(selected))),
                f"设计实验方案：{direction.name}",
            )
            raw = await provider.generate_json(
                system_prompt=synthesis.EXPERIMENT_SYSTEM_PROMPT,
                user_prompt=synthesis.render_experiment_prompt(
                    direction=direction, ideas=accepted, titles=titles
                ),
                purpose="experiment",
            )
            plan, followups, problem = synthesis.normalize_experiment(
                raw, direction=direction, batch_id=batch_id
            )
            self.store.save_experiment(plan)
            plans.append(plan)
            run.experiments_total += 1
            for item in followups:
                self.store.save_followup(item)
                run.followups_total += 1
            if problem:
                run.message = f"{run.message}；{problem}" if run.message else problem
            run.updated_at = utc_now()
            self.store.save_run(run)
        return plans

    def _resolve_parent_direction(
        self, request: IdeationRequest, generation: int
    ) -> Direction | None:
        if request.parent_direction_id:
            return self.store.get_direction(request.parent_direction_id)
        if generation <= 1:
            return None
        previous = self.store.list_directions(generation=generation - 1, limit=1)
        return previous[0] if previous else None

    def _existing_idea_vectors(self) -> list[tuple[str, np.ndarray]]:
        vectors: list[tuple[str, np.ndarray]] = []
        for idea in self.store.list_ideas(limit=1000):
            vectors.append(
                (idea.id, self._embedder.embed_query(synthesis.idea_signature(idea)))
            )
        return vectors

    def _default_queries(self, limit: int) -> list[str]:
        rows = sorted(
            self.store.category_counts(), key=lambda row: row["papers"], reverse=True
        )
        queries = [
            f"{row['category_name'] or row['category_id']} 的未解决问题与创新点"
            for row in rows[: max(0, limit - 1)]
        ]
        queries.append("跨论文的研究空白：哪些创新点可以组合成新的可验证方法")
        return queries[: max(1, limit)]

    # ---------------- status ----------------

    def status(self) -> PlatformStatus:
        reader = PaperLibraryReader(self.settings)
        return PlatformStatus(
            provider=self.provider_label,
            model=self.model_label,
            model_configured=self.settings.model_configured,
            retrieval_backend=getattr(self.backend, "name", "unknown"),
            knowledge_vector_available=self.knowledge_vector_available(),
            paper_database=str(self.settings.paper_database_path),
            paper_database_readable=reader.readable(),
            papers_indexed=self.store.count_papers(),
            chunks=self.store.chunk_count(),
            ideas=self.store.idea_count(),
            directions=self.store.direction_count(),
            experiments=self.store.experiment_count(),
            generations=self.store.max_generation(),
            reading_platform_writes=0,
        )

    # ---------------- job wrappers ----------------

    async def run_corpus_sync_job(self, job_id: str, *, category_id: str = "") -> None:
        async def runner(report: ProgressFn) -> tuple[str, dict[str, Any]]:
            report("syncing", 20, "只读扫描论文库")
            result = await asyncio.to_thread(self.sync_corpus, category_id=category_id)
            detail = result.model_dump(mode="json")
            detail["message"] = (
                f"语料同步完成：新增 {result.created}，更新 {result.updated}，"
                f"未变 {result.unchanged}，待深度解析 {result.needs_deep_analysis}"
            )
            report("syncing", 90, "刷新向量索引")
            stats = await asyncio.to_thread(self.rebuild_index)
            detail["index"] = stats.model_dump(mode="json")
            return "corpus_sync", detail

        await self._execute_job(job_id, runner)

    async def run_index_rebuild_job(self, job_id: str, *, category_id: str = "") -> None:
        async def runner(report: ProgressFn) -> tuple[str, dict[str, Any]]:
            report("indexing", 30, "重建切片与向量索引")
            stats = await asyncio.to_thread(self.rebuild_index, category_id=category_id)
            detail = stats.model_dump(mode="json")
            detail["message"] = f"索引重建完成：{stats.chunks} 个切片 / {stats.papers} 篇论文"
            return "index_rebuild", detail

        await self._execute_job(job_id, runner)

    async def run_deep_analysis_job(
        self, job_id: str, *, limit: int = 0, category_id: str = "", force: bool = False
    ) -> None:
        async def runner(report: ProgressFn) -> tuple[str, dict[str, Any]]:
            summary = await self.run_deep_analysis(
                limit=limit, category_id=category_id, force=force, progress=report
            )
            return "deep_analysis", summary.as_detail()

        await self._execute_job(job_id, runner)

    async def run_ideation_job(self, job_id: str, request: IdeationRequest) -> None:
        job = self.store.get_job(job_id)
        if job is None:
            return

        async def runner(report: ProgressFn) -> tuple[str, dict[str, Any]]:
            run = await self.run_ideation(request, progress=report)
            detail = run.model_dump(mode="json")
            detail["message"] = run.message
            return "ideation", detail

        await self._execute_job(job_id, runner)

    async def _execute_job(
        self,
        job_id: str,
        runner: Callable[[ProgressFn], Awaitable[tuple[str, dict[str, Any]]]],
    ) -> None:
        job = self.store.get_job(job_id)
        if job is None:
            return

        async with self._lock:
            def report(stage: str, progress: int, message: str) -> None:
                job.stage = stage
                job.progress = max(0, min(100, int(progress)))
                job.message = message
                job.updated_at = utc_now()
                self.store.save_job(job)

            job.status = "running"
            job.error = ""
            report(job.stage or "running", max(job.progress, 1), job.message or "任务开始")
            try:
                phase, detail = await runner(report)
                job.status = "succeeded"
                job.stage = "succeeded"
                job.progress = 100
                job.message = str(detail.get("message") or "完成")
                job.error = ""
                job.result = ResearchJobResult(phase=phase, detail=detail)
            except Exception as error:  # noqa: BLE001 - surfaced through the job record
                job.status = "failed"
                job.stage = "failed"
                job.message = "执行失败"
                job.error = str(error) or error.__class__.__name__
                if job.batch_id:
                    run = self.store.get_run(job.batch_id)
                    if run and run.status in {"queued", "running"}:
                        run.status = "failed"
                        run.message = job.error
                        run.updated_at = utc_now()
                        self.store.save_run(run)
            job.updated_at = utc_now()
            self.store.save_job(job)

    def create_job(
        self, job_type: str, *, message: str, batch_id: str = ""
    ) -> ResearchJob:
        timestamp = utc_now()
        job = ResearchJob(
            id=f"job-{uuid4().hex[:12]}",
            job_type=job_type,  # type: ignore[arg-type]
            status="queued",
            progress=0,
            stage="queued",
            message=message,
            batch_id=batch_id,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.store.save_job(job)
        return job


def _progress(progress: ProgressFn | None) -> ProgressFn:
    if progress is None:
        return lambda stage, percent, message: None
    return progress


def _as_list(value: Any, fallback: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if isinstance(fallback, dict) and any(
        key in fallback for key in ("title", "name", "hypothesis", "question", "objective")
    ):
        return [fallback]
    return []


def _merge_paper_ids(groups: Any) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for paper_id in group:
            if paper_id not in merged:
                merged.append(paper_id)
    return merged
