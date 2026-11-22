from __future__ import annotations

import asyncio
import os
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from .categories import CATEGORIES, CATEGORY_BY_ID, CATEGORY_BY_NAME, CategoryDefinition
from .config import Settings
from .downloader import DownloadedPdf, download_pdf
from .knowledge_base import organize_pdf_and_append
from .model_provider import ModelProvider, ModelProviderError, build_provider
from .pdf_utils import ExtractedPdf, extract_pdf, format_file_size
from .schemas import (
    AnalysisResult,
    CategoryCandidate,
    ClassificationResult,
    Innovation,
    JobRecord,
    JobResult,
    PaperRecord,
    PaperSummary,
    utc_now,
)
from .store import LibraryStore


class PipelineError(RuntimeError):
    pass


TRANSLATION_CHUNK_CHARS = 5000
TRANSLATION_MAX_PAGES_PER_CHUNK = 1


class PaperImportPipeline:
    def __init__(self, settings: Settings, store: LibraryStore) -> None:
        self.settings = settings
        self.store = store
        self._lock = asyncio.Lock()
        self._translation_lock = asyncio.Lock()

    async def run_url_import(self, job_id: str) -> None:
        job = self.store.get_job(job_id)
        if not job:
            return
        if not job.source_url:
            self._fail(job, "任务缺少来源链接。")
            return

        async with self._lock:
            try:
                await self._run(job)
            except Exception as error:
                self._fail(job, str(error) or error.__class__.__name__)

    async def run_local_import(self, job_id: str, pdf_path: str) -> None:
        job = self.store.get_job(job_id)
        if not job:
            return

        path = Path(pdf_path)
        if not path.exists():
            self._fail(job, "上传的 PDF 文件不存在，请重新上传。")
            return

        downloaded = DownloadedPdf(
            path=path,
            original_url="",
            resolved_url="",
            filename=path.name,
        )
        async with self._lock:
            try:
                await self._process_downloaded(job, downloaded)
            except Exception as error:
                self._fail(job, str(error) or error.__class__.__name__)

    async def _run(self, job: JobRecord) -> None:
        self._update(
            job,
            progress=8,
            stage="downloading",
            message="正在解析链接并下载 PDF",
        )
        downloaded = await download_pdf(
            job.source_url, self.settings, self.settings.need_organization_dir
        )
        await self._process_downloaded(job, downloaded)

    async def run_translation(self, paper_id: str, job_id: str) -> None:
        job = self.store.get_job(job_id)
        if not job:
            return

        async with self._translation_lock:
            paper = self.store.get_paper(paper_id)
            if not paper:
                self._fail(job, "论文不存在，无法生成中文译文。")
                return

            existing_path = self._safe_translation_path(paper)
            if (
                paper.translation_status == "ready"
                and existing_path
                and existing_path.exists()
            ):
                job.paper_id = paper.id
                job.paper_title = paper.title
                job.status = "succeeded"
                job.progress = 100
                job.stage = "succeeded"
                job.message = "中文译文已存在"
                job.error = ""
                job.updated_at = utc_now()
                self.store.save_job(job)
                return

            try:
                await self._translate_paper(paper, job)
            except Exception as error:
                self._fail_translation(
                    job,
                    paper,
                    str(error) or error.__class__.__name__,
                )

    async def _translate_paper(self, paper: PaperRecord, job: JobRecord) -> None:
        source = self._validated_pdf_path(paper)
        extracted = await asyncio.to_thread(extract_pdf, source)
        chunks = build_translation_chunks(
            extracted.page_texts,
            max_chars=TRANSLATION_CHUNK_CHARS,
            max_pages=TRANSLATION_MAX_PAGES_PER_CHUNK,
        )
        if not chunks:
            raise PipelineError("PDF 中没有可翻译的正文文本。")

        provider = build_provider(self.settings)
        final_path = self._translation_output_path(paper)
        temporary_path = final_path.with_suffix(f"{final_path.suffix}.part")
        temporary_path.unlink(missing_ok=True)

        paper.translation_status = "running"
        paper.translation_path = ""
        paper.translation_url = ""
        paper.translation_error = ""
        paper.translation_model = self.settings.llm_model
        paper.translation_progress = 1
        paper.translation_page_count = extracted.page_count
        paper.translation_completed_pages = 0
        paper.translation_updated_at = utc_now()
        self.store.save_paper(paper)
        self._update(
            job,
            progress=1,
            stage="translating",
            message=f"正在翻译，共 {len(chunks)} 个分段",
        )

        try:
            with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(f"# {paper.title_zh or paper.title}\n\n")
                handle.write("> 中文译文由模型生成，公式、引用和术语请对照原始 PDF。\n")

                completed_pages = 0
                seen_pages: set[int] = set()
                for index, chunk in enumerate(chunks, start=1):
                    translated = await provider.generate_text(
                        system_prompt=(
                            "你是严谨的学术论文翻译。将论文正文忠实翻译成简体中文，"
                            "保留章节层级、公式、变量、引用编号、作者名和专有名词。"
                            "只输出译文，不解释、不总结、不添加原文没有的内容。"
                        ),
                        user_prompt=(
                            "请翻译下面的论文文本。保留 [PAGE n] 页码对应的内容顺序；"
                            "术语首次出现时可采用“中文（English）”格式。\n\n"
                            f"{chunk['text']}"
                        ),
                        purpose="translation",
                    )
                    if not translated.strip():
                        raise ModelProviderError("模型没有返回可用的中文译文。")

                    page_label = (
                        str(chunk["pages"][0])
                        if len(chunk["pages"]) == 1
                        else f"{chunk['pages'][0]}-{chunk['pages'][-1]}"
                    )
                    handle.write(
                        f"\n\n## 第 {page_label} 页\n\n{translated.strip()}\n"
                    )
                    handle.flush()
                    os.fsync(handle.fileno())

                    seen_pages.update(chunk["pages"])
                    completed_pages = len(seen_pages)
                    progress = min(96, 5 + round(91 * index / len(chunks)))
                    paper.translation_progress = progress
                    paper.translation_completed_pages = completed_pages
                    paper.translation_updated_at = utc_now()
                    self.store.save_paper(paper)
                    self._update(
                        job,
                        progress=progress,
                        stage="translating",
                        message=(
                            f"已完成 {completed_pages}/{extracted.page_count} 页"
                            f"（分段 {index}/{len(chunks)}）"
                        ),
                    )
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

        temporary_path.replace(final_path)
        paper.translation_status = "ready"
        paper.translation_path = str(final_path)
        paper.translation_url = f"/api/papers/{paper.id}/translation/file"
        paper.translation_error = ""
        paper.translation_progress = 100
        paper.translation_completed_pages = extracted.page_count
        paper.translation_updated_at = utc_now()
        self.store.save_paper(paper)

        job.paper_id = paper.id
        job.paper_title = paper.title
        job.result = JobResult(phase="completed", destination=str(final_path))
        job.status = "succeeded"
        job.progress = 100
        job.stage = "succeeded"
        job.message = f"中文译文已保存到 {final_path.parent.name}"
        job.error = ""
        job.updated_at = utc_now()
        self.store.save_job(job)

    def _validated_pdf_path(self, paper: PaperRecord) -> Path:
        if not paper.file_path:
            raise PipelineError("论文没有可读取的 PDF 文件。")
        path = Path(paper.file_path).resolve()
        try:
            path.relative_to(self.settings.paper_root.resolve())
        except ValueError as error:
            raise PipelineError("论文 PDF 路径不合法。") from error
        if not path.exists() or path.suffix.lower() != ".pdf":
            raise PipelineError("论文 PDF 文件不存在。")
        return path

    def _safe_translation_path(self, paper: PaperRecord) -> Path | None:
        if not paper.translation_path:
            return None
        path = Path(paper.translation_path).resolve()
        try:
            path.relative_to(self.settings.translation_dir.resolve())
        except ValueError:
            return None
        if path.suffix.lower() != ".md" or not path.is_file():
            return None
        return path

    def _translation_output_path(self, paper: PaperRecord) -> Path:
        title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", paper.title).strip()
        title = re.sub(r"\s+", " ", title).strip(" ._-")[:80] or "paper"
        paper_id = re.sub(r"[^A-Za-z0-9_-]", "", paper.id)[:40] or "paper"
        return self.settings.translation_dir / f"{title}-{paper_id}.md"

    def _fail_translation(
        self,
        job: JobRecord,
        paper: PaperRecord,
        message: str,
    ) -> None:
        paper.translation_status = "failed"
        paper.translation_path = ""
        paper.translation_url = ""
        paper.translation_error = message[:800]
        paper.translation_progress = 0
        paper.translation_completed_pages = 0
        paper.translation_updated_at = utc_now()
        self.store.save_paper(paper)
        self._fail(job, message)

    async def _process_downloaded(
        self, job: JobRecord, downloaded: DownloadedPdf
    ) -> None:
        job.paper_title = Path(downloaded.filename).stem
        self._update(
            job,
            progress=24,
            stage="downloaded",
            message=f"已放入 need_organization：{downloaded.filename}",
        )

        self._update(
            job,
            progress=34,
            stage="extracting",
            message="正在提取页级文本和元数据",
        )
        extracted = await asyncio.to_thread(extract_pdf, downloaded.path)

        duplicate = self.store.get_paper_by_sha256(extracted.sha256)
        if duplicate:
            archived_path = self._archive_duplicate(downloaded.path)
            job.paper_id = duplicate.id
            job.paper_title = duplicate.title
            self._update(
                job,
                progress=100,
                stage="succeeded",
                message=f"文件与已有论文重复，已归档到 {archived_path.parent.name}",
            )
            job.status = "succeeded"
            job.error = ""
            job.updated_at = utc_now()
            self.store.save_job(job)
            return

        provider = build_provider(self.settings)
        self._update(
            job,
            progress=48,
            stage="classifying",
            message="正在调用模型判断论文分类",
        )
        classification = await self.classify(
            provider=provider,
            extracted=extracted,
            source_url=downloaded.original_url,
        )
        category = CATEGORY_BY_ID[classification.primary_category_id]
        job.paper_title = classification.canonical_title or classification.title_zh
        job.result = JobResult(
            phase="classified",
            classification=classification,
            category_id=category.id,
            category_name=category.name_zh,
            destination=category.directory,
        )
        self._update(
            job,
            progress=64,
            stage="classifying",
            message=f"已分类到：{category.name_zh}（{classification.confidence:.0%}）",
        )

        self._update(
            job,
            progress=76,
            stage="analyzing",
            message="正在生成双语解读和创新点证据",
        )
        analysis = await self.analyze(
            provider=provider,
            extracted=extracted,
            classification=classification,
            category=category,
        )
        job.result = JobResult(
            phase="analyzed",
            classification=classification,
            analysis=analysis,
            category_id=category.id,
            category_name=category.name_zh,
            destination=category.directory,
        )

        self._update(
            job,
            progress=90,
            stage="organizing",
            message=f"正在写入 knowledgebase 和 {category.directory}",
        )
        destination = await asyncio.to_thread(
            organize_pdf_and_append,
            paper_root=self.settings.paper_root,
            source_pdf=downloaded.path,
            category=category,
            classification=classification,
            analysis=analysis,
        )

        paper = self._build_paper(
            downloaded=downloaded.original_url,
            destination=destination,
            extracted=extracted,
            classification=classification,
            analysis=analysis,
        )
        self.store.save_paper(paper)

        job.paper_id = paper.id
        job.paper_title = paper.title
        job.result = JobResult(
            phase="completed",
            classification=classification,
            analysis=analysis,
            category_id=category.id,
            category_name=category.name_zh,
            destination=str(destination),
        )
        self._update(
            job,
            progress=100,
            stage="succeeded",
            message="分类、分析、知识库写入和前端索引已完成",
        )
        job.status = "succeeded"
        job.error = ""
        job.updated_at = utc_now()
        self.store.save_job(job)

    async def classify(
        self,
        *,
        provider: ModelProvider,
        extracted: ExtractedPdf,
        source_url: str,
    ) -> ClassificationResult:
        category_lines = []
        for category in CATEGORIES:
            examples = "；".join(category.representative_titles)
            category_lines.append(
                f"- {category.id} | {category.directory} | {category.name_zh} | "
                f"{category.name_en} | {category.description} | 代表论文：{examples}"
            )

        context = extracted.context(
            max_chars=min(self.settings.max_text_chars, 32000),
            page_limit=min(8, extracted.page_count),
        )
        system_prompt = (
            "你是严谨的论文知识库整理员。只依据用户提供的论文文本和固定分类体系输出 JSON，"
            "不得猜测不存在的数据。标题、作者、年份、摘要和分类理由都必须有文本依据；"
            "无法确认时留空并降低置信度。"
        )
        user_prompt = f"""
请完成论文元数据规范化与单标签分类。

来源链接：
{source_url}

PDF 内嵌标题：{extracted.metadata_title or "未提供"}
PDF 内嵌作者：{extracted.metadata_author or "未提供"}
页数：{extracted.page_count}

固定分类体系：
{chr(10).join(category_lines)}

论文正文节选：
{context}

只返回一个 JSON 对象，字段如下：
{{
  "canonical_title": "论文规范标题",
  "title_zh": "中文标题，没有则为空",
  "authors": ["作者姓名"],
  "venue": "会议、期刊或 arXiv",
  "year": 2025,
  "abstract": "论文摘要的精简转述，不要编造",
  "language": "en 或 zh 或 mixed",
  "keywords": ["关键词"],
  "primary_category_id": "cat-01 到 cat-12",
  "primary_category_name": "分类中文名",
  "confidence": 0.0,
  "rationale": "分类依据",
  "candidate_categories": [
    {{"category_id": "cat-xx", "category_name": "名称", "confidence": 0.0, "rationale": "原因"}}
  ],
  "needs_review": false
}}
"""
        raw = await provider.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            purpose="classification",
        )
        return normalize_classification(raw)

    async def analyze(
        self,
        *,
        provider: ModelProvider,
        extracted: ExtractedPdf,
        classification: ClassificationResult,
        category: CategoryDefinition,
    ) -> AnalysisResult:
        context = extracted.context(
            max_chars=self.settings.max_text_chars,
            page_limit=min(self.settings.analysis_page_limit, extracted.page_count),
        )
        system_prompt = (
            "你是论文解读助手。输出必须是 JSON。所有结论只能来自给定论文文本；"
            "创新点必须附原文章节中的短引文和 PDF 页码。页码使用 [PAGE n] 标记中的整数。"
            "如果证据不足，应明确写限制而不是补全事实。"
        )
        user_prompt = f"""
论文标题：{classification.canonical_title}
分类：{category.name_zh} / {category.name_en}

带页码的论文正文节选：
{context}

只返回一个 JSON 对象：
{{
  "problem": "研究问题",
  "method": "核心方法",
  "findings": ["主要发现"],
  "innovations": [
    {{
      "claim": "创新点",
      "evidence_pages": [1, 4],
      "evidence_quotes": ["原文短引文"]
    }}
  ],
  "limitations": ["局限性"],
  "thesis_zh": "两到四句中文核心论点",
  "novelty_zh": "两到三句中文创新点，尽量保留论文中的关键数字",
  "thesis_en": "English core thesis",
  "novelty_en": "English novelty summary",
  "relation_to_library": "与当前知识库分类或代表论文的关系",
  "confidence": 0.0,
  "needs_review": false
}}
"""
        raw = await provider.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            purpose="analysis",
        )
        return normalize_analysis(raw, extracted.page_count)

    def _build_paper(
        self,
        *,
        downloaded: str,
        destination: Path,
        extracted: ExtractedPdf,
        classification: ClassificationResult,
        analysis: AnalysisResult,
    ) -> PaperRecord:
        paper_id = f"paper-{uuid.uuid4().hex[:12]}"
        status = (
            "needs_review"
            if classification.needs_review
            or analysis.needs_review
            or classification.confidence < 0.75
            else "ready"
        )
        summary = PaperSummary(
            problem=analysis.problem,
            method=analysis.method,
            findings=analysis.findings,
            innovations=analysis.innovations,
            limitations=analysis.limitations,
            thesis_zh=analysis.thesis_zh,
            novelty_zh=analysis.novelty_zh,
            thesis_en=analysis.thesis_en,
            novelty_en=analysis.novelty_en,
            relation_to_library=analysis.relation_to_library,
            evidence_pages=sorted(
                {
                    page
                    for innovation in analysis.innovations
                    for page in innovation.evidence_pages
                }
            ),
        )
        return PaperRecord(
            id=paper_id,
            title=classification.canonical_title,
            title_zh=classification.title_zh,
            authors=classification.authors,
            venue=classification.venue,
            year=classification.year,
            abstract=classification.abstract,
            category_id=classification.primary_category_id,
            status=status,
            reading_status="unread",
            source="model",
            confidence=round(
                min(classification.confidence, analysis.confidence), 3
            ),
            updated_at=date.today().isoformat(),
            file_size=format_file_size(extracted.size_bytes),
            page_count=extracted.page_count,
            tags=classification.keywords,
            candidate_categories=classification.candidate_categories,
            summary=summary,
            file_path=str(destination),
            file_url=f"/api/papers/{paper_id}/file",
            original_url=downloaded,
            sha256=extracted.sha256,
            created_at=utc_now(),
            ai_rationale=classification.rationale,
        )

    def _archive_duplicate(self, source: Path) -> Path:
        destination_dir = self.settings.archive_dir / "duplicates"
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / source.name
        index = 2
        while destination.exists():
            destination = destination_dir / f"{source.stem} ({index}){source.suffix}"
            index += 1
        source.replace(destination)
        return destination

    def _update(
        self,
        job: JobRecord,
        *,
        progress: int,
        stage: str,
        message: str,
    ) -> None:
        job.status = "running"
        job.progress = progress
        job.stage = stage
        job.message = message
        job.error = ""
        job.updated_at = utc_now()
        self.store.save_job(job)

    def _fail(self, job: JobRecord, message: str) -> None:
        job.status = "failed"
        job.stage = "failed"
        job.message = message
        job.error = message
        if job.result is None:
            job.result = JobResult()
        job.updated_at = utc_now()
        self.store.save_job(job)


def normalize_classification(raw: dict[str, Any]) -> ClassificationResult:
    category_id = str(
        raw.get("primary_category_id")
        or raw.get("primary_category")
        or raw.get("category_id")
        or ""
    ).strip()
    category_name = str(
        raw.get("primary_category_name") or raw.get("category_name") or ""
    ).strip()
    category = resolve_category(category_id, category_name)
    if not category:
        raise PipelineError("模型返回了无法识别的分类，任务已停止，PDF 保留在 need_organization。")

    authors = raw.get("authors") or []
    if isinstance(authors, str):
        authors = [part.strip() for part in re.split(r"[,，;；]", authors) if part.strip()]
    authors = [
        str(author.get("name", "") if isinstance(author, dict) else author).strip()
        for author in authors
        if str(author.get("name", "") if isinstance(author, dict) else author).strip()
    ]

    candidates: list[CategoryCandidate] = []
    for item in raw.get("candidate_categories") or []:
        if not isinstance(item, dict):
            continue
        candidate = resolve_category(
            str(item.get("category_id") or item.get("category") or ""),
            str(item.get("category_name") or item.get("name") or ""),
        )
        if not candidate:
            continue
        candidates.append(
            CategoryCandidate(
                category_id=candidate.id,
                category_name=candidate.name_zh,
                confidence=clamp_float(item.get("confidence"), 0.0),
                rationale=str(item.get("rationale") or ""),
            )
        )

    confidence = clamp_float(raw.get("confidence"), 0.0)
    return ClassificationResult(
        canonical_title=str(
            raw.get("canonical_title") or raw.get("title") or "Untitled paper"
        ).strip(),
        title_zh=str(raw.get("title_zh") or "").strip(),
        authors=authors,
        venue=str(raw.get("venue") or "").strip(),
        year=parse_int(raw.get("year")),
        abstract=str(raw.get("abstract") or "").strip(),
        language=str(raw.get("language") or "en").strip(),
        keywords=[
            str(item).strip()
            for item in (raw.get("keywords") or [])
            if str(item).strip()
        ][:12],
        primary_category_id=category.id,
        primary_category_name=category.name_zh,
        confidence=confidence,
        rationale=str(raw.get("rationale") or "").strip(),
        candidate_categories=candidates,
        needs_review=bool(raw.get("needs_review")) or confidence < 0.75,
    )


def normalize_analysis(raw: dict[str, Any], page_count: int) -> AnalysisResult:
    innovations: list[Innovation] = []
    for item in raw.get("innovations") or []:
        if isinstance(item, str):
            innovations.append(Innovation(claim=item, evidence_pages=[], evidence_quotes=[]))
            continue
        if not isinstance(item, dict):
            continue
        pages = [
            page
            for page in (
                item.get("evidence_pages")
                or item.get("pages")
                or item.get("evidencePages")
                or []
            )
            if isinstance(page, int) and 1 <= page <= page_count
        ]
        quotes = item.get("evidence_quotes") or item.get("quotes") or item.get("evidenceQuotes") or []
        if isinstance(quotes, str):
            quotes = [quotes]
        innovations.append(
            Innovation(
                claim=str(item.get("claim") or item.get("innovation") or "").strip(),
                evidence_pages=pages,
                evidence_quotes=[str(quote).strip() for quote in quotes if str(quote).strip()],
            )
        )

    return AnalysisResult(
        problem=str(raw.get("problem") or "").strip(),
        method=str(raw.get("method") or "").strip(),
        findings=string_list(raw.get("findings") or raw.get("main_findings")),
        innovations=[item for item in innovations if item.claim],
        limitations=string_list(raw.get("limitations")),
        thesis_zh=str(raw.get("thesis_zh") or raw.get("core_thesis_zh") or "").strip(),
        novelty_zh=str(raw.get("novelty_zh") or "").strip(),
        thesis_en=str(raw.get("thesis_en") or raw.get("core_thesis_en") or "").strip(),
        novelty_en=str(raw.get("novelty_en") or "").strip(),
        relation_to_library=str(raw.get("relation_to_library") or "").strip(),
        confidence=clamp_float(raw.get("confidence"), 0.7),
        needs_review=bool(raw.get("needs_review")),
    )


def resolve_category(category_id: str, category_name: str) -> CategoryDefinition | None:
    normalized_id = category_id.strip()
    if normalized_id in CATEGORY_BY_ID:
        return CATEGORY_BY_ID[normalized_id]
    normalized_name = category_name.strip()
    if normalized_name in CATEGORY_BY_NAME:
        return CATEGORY_BY_NAME[normalized_name]
    for category in CATEGORIES:
        if normalized_name in {category.name_en, category.directory}:
            return category
        if normalized_id in {category.name_zh, category.name_en, category.directory}:
            return category
        if normalized_id and normalized_id in category.directory:
            return category
    return None


def clamp_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, parsed))


def parse_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        if isinstance(value, str):
            match = re.search(r"\b(19|20)\d{2}\b", value)
            if match:
                return int(match.group(0))
        return 0


def string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def build_translation_chunks(
    page_texts: list[str],
    *,
    max_chars: int,
    max_pages: int,
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    current_pages: list[int] = []
    current_parts: list[str] = []
    current_length = 0

    def flush() -> None:
        nonlocal current_pages, current_parts, current_length
        if not current_parts:
            return
        chunks.append(
            {
                "pages": list(dict.fromkeys(current_pages)),
                "text": "\n\n".join(current_parts),
            }
        )
        current_pages = []
        current_parts = []
        current_length = 0

    for page_number, page_text in enumerate(page_texts, start=1):
        for segment in split_translation_text(page_text, max_chars):
            segment_length = len(segment)
            exceeds_length = current_parts and current_length + segment_length > max_chars
            exceeds_pages = (
                current_pages and page_number not in current_pages
                and len(set(current_pages)) >= max_pages
            )
            if exceeds_length or exceeds_pages:
                flush()
            current_pages.append(page_number)
            current_parts.append(f"[PAGE {page_number}]\n{segment}")
            current_length += segment_length

    flush()
    return chunks


def split_translation_text(text: str, max_chars: int) -> list[str]:
    remaining = text.strip()
    if not remaining:
        return []
    if len(remaining) <= max_chars:
        return [remaining]

    segments: list[str] = []
    while len(remaining) > max_chars:
        window = remaining[:max_chars]
        cut = window.rfind("\n\n")
        minimum_cut = max_chars // 2
        if cut < minimum_cut:
            cut = window.rfind("\n")
        if cut < minimum_cut:
            cut = window.rfind(". ")
            if cut >= 0:
                cut += 1
        if cut < minimum_cut:
            cut = max_chars

        segment = remaining[:cut].strip()
        if segment:
            segments.append(segment)
        remaining = remaining[cut:].lstrip()

    if remaining:
        segments.append(remaining)
    return segments
