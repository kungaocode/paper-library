from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import numpy as np

from .chunking import stable_id
from .normalizing import clamp_float, pick, string_list
from .schemas import (
    Direction,
    ExperimentPlan,
    FollowupItem,
    Idea,
    IdeaCritique,
    SearchHit,
    utc_now,
)


# Generated content is indexed under its own chunk kinds so a corpus rebuild
# never wipes it and an ideation rerun never leaves stale ideas behind.
KIND_IDEA = "idea.claim"
KIND_DIRECTION = "idea.direction"

FOLLOWUP_KINDS = frozenset({"paper_to_read", "dataset", "tool", "experiment", "question"})


class SynthesisError(RuntimeError):
    pass


@dataclass
class EvidencePack:
    query: str
    hits: list[SearchHit] = field(default_factory=list)
    paper_ids: list[str] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)
    text: str = ""


DEFAULT_MAX_CHUNKS_PER_PAPER = 2

# Rejection reasons that mean "the model output was unusable", as opposed to
# "the idea was fine but its citations did not hold up". The pipeline treats
# structural failures as final and still runs dedupe on everything else.
REASON_NOT_JSON = "想法不是 JSON 对象"
REASON_NO_TITLE = "模型未给出想法标题"
STRUCTURAL_REASONS = frozenset({REASON_NOT_JSON, REASON_NO_TITLE})


def diversify_by_paper(
    hits: Sequence[SearchHit],
    *,
    limit: int,
    max_per_paper: int = DEFAULT_MAX_CHUNKS_PER_PAPER,
) -> list[SearchHit]:
    """Trim ranked hits so no single paper can monopolise an evidence pack.

    A focused query retrieves many chunks from the same paper, and ideas must
    cite at least two papers to pass validation. Retrieving a wider pool and
    capping the per-paper share keeps the pack both relevant and cross-paper.
    Rank order is preserved; deferred hits fill any slots the cap left empty.
    """
    if limit <= 0:
        return []
    cap = max(1, max_per_paper)
    selected: list[SearchHit] = []
    deferred: list[SearchHit] = []
    counts: dict[str, int] = {}
    for hit in hits:
        if len(selected) >= limit:
            break
        # Category-level and generated chunks carry no paper_id. Group them by
        # category, then by content family ("idea", "direction"), so neither can
        # crowd out the paper evidence a cross-paper citation needs.
        bucket = (
            hit.paper_id or hit.category_id or hit.kind.split(".", 1)[0] or hit.chunk_id
        )
        used = counts.get(bucket, 0)
        if used < cap:
            counts[bucket] = used + 1
            selected.append(hit)
        else:
            deferred.append(hit)
    for hit in deferred:
        if len(selected) >= limit:
            break
        selected.append(hit)
    return selected


def build_evidence_pack(
    query: str,
    hits: Sequence[SearchHit],
    *,
    max_chars_per_hit: int = 420,
    max_total_chars: int = 14000,
) -> EvidencePack:
    """Render retrieved chunks into the citation-bearing block sent to the model.

    paper_id / chunk_id are printed verbatim: the citation validator downstream
    only accepts ids that appear here, which is what keeps ideas traceable.
    """
    lines: list[str] = []
    paper_ids: list[str] = []
    chunk_ids: list[str] = []
    used = 0
    for index, hit in enumerate(hits, start=1):
        page = f" | 页码={hit.page_number}" if hit.page_number else ""
        header = (
            f"[{index}] paper_id={hit.paper_id or '(分类级)'} | chunk_id={hit.chunk_id} | "
            f"分类={hit.category_id or '-'} | 类型={hit.kind or '-'}{page} | "
            f"相关度={hit.score:.3f}"
        )
        body = hit.text.strip().replace("\n", " ")
        if len(body) > max_chars_per_hit:
            body = body[: max_chars_per_hit - 1] + "…"
        block = f"{header}\n    {body}"
        if used + len(block) > max_total_chars:
            break
        used += len(block)
        lines.append(block)
        if hit.paper_id and hit.paper_id not in paper_ids:
            paper_ids.append(hit.paper_id)
        chunk_ids.append(hit.chunk_id)

    return EvidencePack(
        query=query,
        hits=list(hits[: len(lines)]),
        paper_ids=paper_ids,
        chunk_ids=chunk_ids,
        text="\n".join(lines),
    )


# ---------------- prompts ----------------

IDEATION_SYSTEM_PROMPT = (
    "你是科研创新整合助手。你只能使用用户给出的证据卡片，禁止编造论文、数据集、"
    "实验结果或数字。每条想法必须能追溯到卡片里的具体论文。输出必须是 JSON。"
)


def render_ideation_prompt(
    *,
    query: str,
    pack: EvidencePack,
    corpus_size: tuple[int, int],
    idea_count: int,
    generation: int,
) -> str:
    papers, chunks = corpus_size
    return f"""【本轮聚焦问题】{query}
【演化轮次】第 {generation} 代
【语料规模】{papers} 篇论文 / {chunks} 个证据切片
【证据卡片】
{pack.text or '(无命中，请说明证据不足)'}

请跨论文整合创新点，提出 {idea_count} 个可以尝试的新研究想法。要求：
1. 每个想法必须由至少 2 张来自不同论文的证据卡片支撑，并说明它们之间的缺口如何被补上；
2. 假设要可证伪，方法要能在单机或小集群上先做小规模验证；
3. source_paper_ids 必须逐字复制证据卡片中的 paper_id，evidence_refs 必须逐字复制 chunk_id；
4. 不要重复卡片里已有工作的结论，要提出新的组合或新的测量方式。

只返回一个 JSON 对象：
{{
  "ideas": [
    {{
      "title": "想法标题",
      "hypothesis": "可证伪的假设",
      "motivation": "为什么现在值得做（引用卡片中的缺口）",
      "method_sketch": "分步骤的方法草案",
      "expected_contribution": "预期贡献",
      "novelty_claim": "与已有工作的差别",
      "risks": ["主要风险"],
      "required_resources": ["需要的数据/算力/工具"],
      "source_paper_ids": ["paper-xxxxxxxx"],
      "evidence_refs": ["chunk id"],
      "confidence": 0.0
    }}
  ]
}}"""


CRITIQUE_SYSTEM_PROMPT = (
    "你是严格的科研评审。你要判断一个研究想法是否值得投入，必须指出证据不足或"
    "无法证伪的地方。评分只能依据用户给出的想法内容与证据卡片。输出必须是 JSON。"
)


def render_critique_prompt(*, idea: Idea, pack: EvidencePack) -> str:
    payload = {
        "title": idea.title,
        "hypothesis": idea.hypothesis,
        "motivation": idea.motivation,
        "method_sketch": idea.method_sketch,
        "novelty_claim": idea.novelty_claim,
        "risks": idea.risks,
        "source_paper_ids": idea.source_paper_ids,
    }
    return f"""【待评审想法】
{json.dumps(payload, ensure_ascii=False, indent=2)}

【该想法引用的证据卡片】
{pack.text or '(无)'}

请给出评审结论。只返回一个 JSON 对象：
{{
  "novelty": 0.0,
  "feasibility": 0.0,
  "evidence_support": 0.0,
  "risk": 0.0,
  "verdict": "一句话结论",
  "unsupported_claims": ["证据不足的具体论断"],
  "suggested_fix": "如何修正才能成立"
}}"""


DIRECTION_SYSTEM_PROMPT = (
    "你是研究方向规划者。你要把若干研究想法聚合成可长期推进的方向，并明确指出"
    "研究空白与演化关系。只能使用给出的想法与论文，不得编造。输出必须是 JSON。"
)


def render_direction_prompt(
    *,
    ideas: Sequence[Idea],
    titles: dict[str, str],
    generation: int,
    parent: Direction | None,
    feedback: str = "",
) -> str:
    lines = []
    for idea in ideas:
        sources = "、".join(
            f"{pid}({titles.get(pid, '未知论文')})" for pid in idea.source_paper_ids[:4]
        )
        lines.append(
            f"- idea_id={idea.id} | 标题：{idea.title}\n"
            f"  假设：{idea.hypothesis}\n"
            f"  新颖度/可行性/证据支持：{_critique_scores(idea)}\n"
            f"  来源论文：{sources}"
        )
    parent_block = ""
    if parent:
        parent_block = (
            f"上一代方向ID：{parent.id}\n"
            f"上一代方向：{parent.name}\n"
            f"上一代研究问题：{parent.question}\n"
            f"上一代路线图：{'；'.join(parent.roadmap[:6])}\n"
        )
    feedback_block = f"用户反馈：{feedback}\n" if feedback else ""
    return f"""【演化轮次】第 {generation} 代
{parent_block}{feedback_block}
【本轮通过评审的想法】
{chr(10).join(lines) or '(无)'}

请把这些想法聚合成 1-3 个研究方向。要求：
1. 每个方向给出明确的研究问题、空白分析、可执行路线图与成功判据；
2. member_idea_ids 必须逐字使用上面出现的 idea_id；
3. source_paper_ids 必须来自这些想法引用的论文；
4. 若存在上一代方向，请说明本轮是延续、分裂还是淘汰它，并填写 parent_direction_id。

只返回一个 JSON 对象：
{{
  "directions": [
    {{
      "name": "方向名称",
      "question": "研究问题",
      "rationale": "为什么这些想法能聚成该方向",
      "gap_analysis": "研究空白",
      "roadmap": ["阶段目标"],
      "success_metrics": ["可量化成功判据"],
      "open_risks": ["未解决风险"],
      "member_idea_ids": ["idea-xxxxxxxx"],
      "source_paper_ids": ["paper-xxxxxxxx"],
      "priority": 0.0,
      "parent_direction_id": ""
    }}
  ]
}}"""


EXPERIMENT_SYSTEM_PROMPT = (
    "你是实验设计助手。你要把一个研究方向落成可执行、可证伪的实验方案，并列出"
    "为完成它还需要补充阅读的论文或数据。不得编造已有结果。输出必须是 JSON。"
)


def render_experiment_prompt(*, direction: Direction, ideas: Sequence[Idea], titles: dict[str, str]) -> str:
    idea_lines = "\n".join(
        f"- {idea.title}：{idea.hypothesis}" for idea in ideas if idea.id in set(direction.member_idea_ids)
    ) or "(无)"
    source_lines = "\n".join(
        f"- {pid}：{titles.get(pid, '未知论文')}" for pid in direction.source_paper_ids[:8]
    ) or "(无)"
    return f"""研究方向：{direction.name}
方向ID：{direction.id}
研究问题：{direction.question}
空白分析：{direction.gap_analysis}
路线图：{'；'.join(direction.roadmap[:8])}
成功判据：{'；'.join(direction.success_metrics[:6])}

【方向下的想法】
{idea_lines}

【相关论文】
{source_lines}

请设计一个可执行实验方案，并列出仍需补充的材料。只返回一个 JSON 对象：
{{
  "objective": "实验目标",
  "hypothesis": "被检验的假设",
  "datasets": ["数据集"],
  "baselines": ["对比基线"],
  "metrics": ["评测指标"],
  "protocol_steps": ["按顺序的实验步骤"],
  "ablations": ["消融设置"],
  "compute_estimate": "算力与时间估计",
  "falsification_criteria": "什么结果会否证该假设",
  "timeline": ["阶段时间安排"],
  "risks": ["执行风险"],
  "followups": [
    {{"kind": "paper_to_read", "query": "检索式", "reason": "为什么需要", "suggested_action": "建议动作"}}
  ]
}}"""


# ---------------- normalization / validation ----------------


def _critique_scores(idea: Idea) -> str:
    critique = idea.critique or {}
    return (
        f"{critique.get('novelty', '-')} / {critique.get('feasibility', '-')} / "
        f"{critique.get('evidence_support', '-')}"
    )


def normalize_idea(
    raw: Any,
    *,
    batch_id: str,
    generation: int,
    known_paper_ids: set[str],
    known_chunk_ids: set[str],
    category_by_paper: dict[str, str],
) -> tuple[Idea, str]:
    """Turn a model idea into an Idea plus a rejection reason ('' when accepted).

    Citation validation is the hard gate: an idea that points at papers outside
    the corpus is kept for auditability but never enters the direction stage.
    """
    if not isinstance(raw, dict):
        return _empty_idea(batch_id, generation, str(raw)[:80]), REASON_NOT_JSON

    title = str(pick(raw, "title", "name", "idea") or "").strip()
    if not title:
        return _empty_idea(batch_id, generation, ""), REASON_NO_TITLE

    raw_ids = string_list(
        pick(raw, "source_paper_ids", "source_papers", "paper_ids", "citations"), limit=12
    )
    accepted_ids = [pid for pid in raw_ids if pid in known_paper_ids]
    unknown_ids = [pid for pid in raw_ids if pid not in known_paper_ids]
    refs = [
        ref
        for ref in string_list(pick(raw, "evidence_refs", "evidence", "chunk_ids"), limit=12)
        if ref in known_chunk_ids
    ]

    idea_id = f"idea-{stable_id(batch_id, title)[:12]}"
    idea = Idea(
        id=idea_id,
        title=title[:300],
        hypothesis=str(pick(raw, "hypothesis") or "").strip()[:2000],
        motivation=str(pick(raw, "motivation") or "").strip()[:2000],
        method_sketch=str(pick(raw, "method_sketch", "method") or "").strip()[:3000],
        expected_contribution=str(pick(raw, "expected_contribution") or "").strip()[:1200],
        novelty_claim=str(pick(raw, "novelty_claim", "novelty") or "").strip()[:1200],
        risks=string_list(raw.get("risks"), limit=8, max_chars=400),
        required_resources=string_list(
            pick(raw, "required_resources", "resources"), limit=8, max_chars=300
        ),
        source_paper_ids=accepted_ids,
        evidence_refs=refs,
        category_ids=sorted(
            {category_by_paper[pid] for pid in accepted_ids if category_by_paper.get(pid)}
        ),
        confidence=clamp_float(pick(raw, "confidence", "score"), 0.5),
        generation=generation,
        batch_id=batch_id,
        created_at=utc_now(),
    )

    if not accepted_ids:
        detail = f"（模型给出的 id：{', '.join(unknown_ids[:5])}）" if unknown_ids else ""
        return idea, f"引用校验失败：没有指向语料内真实论文的 source_paper_ids{detail}"
    if len(accepted_ids) < 2:
        return idea, "证据不足：只引用了 1 篇论文，跨论文整合不成立"
    if unknown_ids:
        idea.rejected_reason = ""
        idea.risks.append(f"模型引用了语料外的论文 id，已丢弃：{', '.join(unknown_ids[:5])}")
    return idea, ""


def _empty_idea(batch_id: str, generation: int, title: str) -> Idea:
    return Idea(
        id=f"idea-{stable_id(batch_id, title or 'empty', 'rejected')[:12]}",
        title=title or "(无效想法)",
        generation=generation,
        batch_id=batch_id,
        created_at=utc_now(),
    )


def normalize_critique(raw: Any) -> IdeaCritique:
    if not isinstance(raw, dict):
        return IdeaCritique(verdict="评审结果不可解析")
    critique = IdeaCritique(
        novelty=clamp_float(pick(raw, "novelty", "novelty_score"), 0.5),
        feasibility=clamp_float(pick(raw, "feasibility", "feasibility_score"), 0.5),
        evidence_support=clamp_float(
            pick(raw, "evidence_support", "evidence", "support"), 0.5
        ),
        risk=clamp_float(raw.get("risk"), 0.5),
        verdict=str(pick(raw, "verdict", "summary") or "").strip()[:800],
        unsupported_claims=string_list(
            pick(raw, "unsupported_claims", "unsupported"), limit=8, max_chars=400
        ),
        suggested_fix=str(pick(raw, "suggested_fix", "fix") or "").strip()[:1200],
    )
    critique.score = round(
        0.3 * critique.novelty
        + 0.25 * critique.feasibility
        + 0.3 * critique.evidence_support
        + 0.15 * (1.0 - critique.risk),
        4,
    )
    return critique


def apply_critique(idea: Idea, critique: IdeaCritique) -> Idea:
    idea.critique = critique.model_dump(mode="json")
    # The reviewer's score outweighs the generator's self-confidence: the point
    # of the second pass is to stop the model from grading its own homework.
    idea.confidence = round(
        clamp_float(0.4 * idea.confidence + 0.6 * critique.score, 0.5), 3
    )
    return idea


def idea_signature(idea: Idea) -> str:
    return " ".join(
        part
        for part in (idea.title, idea.hypothesis, idea.method_sketch, idea.novelty_claim)
        if part
    )


def find_duplicate(
    vector: np.ndarray,
    existing: Iterable[tuple[str, np.ndarray]],
    threshold: float,
) -> str:
    """Return the id of an already-known idea that is too similar, else ''."""
    norm = float(np.linalg.norm(vector))
    if norm == 0:
        return ""
    for idea_id, other in existing:
        other_norm = float(np.linalg.norm(other))
        if other_norm == 0:
            continue
        similarity = float(np.dot(vector, other) / (norm * other_norm))
        if similarity >= threshold:
            return idea_id
    return ""


def normalize_direction(
    raw: Any,
    *,
    batch_id: str,
    generation: int,
    known_idea_ids: set[str],
    known_paper_ids: set[str],
    known_direction_ids: set[str] | None = None,
) -> tuple[Direction, str]:
    if not isinstance(raw, dict):
        return (
            Direction(
                id=f"dir-{stable_id(batch_id, 'invalid')[:12]}",
                name="(无效方向)",
                generation=generation,
                batch_id=batch_id,
                created_at=utc_now(),
            ),
            "方向不是 JSON 对象",
        )

    name = str(pick(raw, "name", "title") or "").strip()
    if not name:
        return (
            Direction(
                id=f"dir-{stable_id(batch_id, 'unnamed')[:12]}",
                name="(未命名方向)",
                generation=generation,
                batch_id=batch_id,
                created_at=utc_now(),
            ),
            "模型未给出方向名称",
        )

    members = [
        idea_id
        for idea_id in string_list(pick(raw, "member_idea_ids", "idea_ids", "members"), limit=30)
        if idea_id in known_idea_ids
    ]
    parent = str(pick(raw, "parent_direction_id", "parent") or "").strip()
    # A lineage link is only kept when it points at a direction we really have;
    # otherwise the evolution tree would grow phantom ancestors.
    if parent and parent not in (known_direction_ids or set()):
        parent = ""
    direction = Direction(
        id=f"dir-{stable_id(batch_id, name)[:12]}",
        name=name[:200],
        question=str(pick(raw, "question", "research_question") or "").strip()[:1200],
        rationale=str(pick(raw, "rationale") or "").strip()[:2000],
        gap_analysis=str(pick(raw, "gap_analysis", "gap") or "").strip()[:2000],
        member_idea_ids=members,
        source_paper_ids=[
            pid
            for pid in string_list(pick(raw, "source_paper_ids", "papers"), limit=20)
            if pid in known_paper_ids
        ],
        roadmap=string_list(raw.get("roadmap"), limit=12, max_chars=500),
        success_metrics=string_list(
            pick(raw, "success_metrics", "metrics"), limit=10, max_chars=400
        ),
        open_risks=string_list(pick(raw, "open_risks", "risks"), limit=10, max_chars=400),
        priority=clamp_float(raw.get("priority"), 0.5),
        generation=generation,
        parent_direction_id=parent,
        status="proposed",
        batch_id=batch_id,
        created_at=utc_now(),
    )
    if not members:
        return direction, "成员校验失败：member_idea_ids 没有指向本轮任何真实想法"
    return direction, ""


def normalize_experiment(
    raw: Any,
    *,
    direction: Direction,
    batch_id: str,
) -> tuple[ExperimentPlan, list[FollowupItem], str]:
    if not isinstance(raw, dict):
        return (
            ExperimentPlan(
                id=f"exp-{stable_id(batch_id, direction.id, 'invalid')[:12]}",
                direction_id=direction.id,
                direction_name=direction.name,
                generation=direction.generation,
                created_at=utc_now(),
                updated_at=utc_now(),
            ),
            [],
            "实验方案不是 JSON 对象",
        )

    experiment_id = f"exp-{stable_id(batch_id, direction.id)[:12]}"
    plan = ExperimentPlan(
        id=experiment_id,
        direction_id=direction.id,
        direction_name=direction.name,
        objective=str(pick(raw, "objective", "goal") or "").strip()[:1200],
        hypothesis=str(pick(raw, "hypothesis") or "").strip()[:1500],
        datasets=string_list(raw.get("datasets"), limit=12, max_chars=200),
        baselines=string_list(raw.get("baselines"), limit=12, max_chars=200),
        metrics=string_list(pick(raw, "metrics", "evaluation_metrics"), limit=12, max_chars=200),
        protocol_steps=string_list(
            pick(raw, "protocol_steps", "steps", "protocol"), limit=20, max_chars=600
        ),
        ablations=string_list(raw.get("ablations"), limit=12, max_chars=300),
        compute_estimate=str(pick(raw, "compute_estimate", "compute") or "").strip()[:400],
        falsification_criteria=str(
            pick(raw, "falsification_criteria", "falsification") or ""
        ).strip()[:800],
        timeline=string_list(raw.get("timeline"), limit=12, max_chars=300),
        risks=string_list(raw.get("risks"), limit=10, max_chars=300),
        status="draft",
        generation=direction.generation,
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    followups: list[FollowupItem] = []
    for index, item in enumerate(raw.get("followups") or []):
        if not isinstance(item, dict):
            text = str(item).strip()
            item = {"kind": "question", "query": text} if text else {}
        kind = str(item.get("kind") or "question").strip()
        if kind not in FOLLOWUP_KINDS:
            kind = "question"
        query = str(pick(item, "query", "search_query", "title") or "").strip()[:400]
        reason = str(item.get("reason") or "").strip()[:600]
        if not query and not reason:
            continue
        action = str(item.get("suggested_action") or "").strip()[:600]
        if kind == "paper_to_read" and not action:
            action = "把该检索式交给阅读平台的 URL/检索导入，人工确认后入库"
        followups.append(
            FollowupItem(
                id=f"fu-{stable_id(batch_id, direction.id, kind, query or reason, index)[:12]}",
                direction_id=direction.id,
                experiment_id=experiment_id,
                kind=kind,  # type: ignore[arg-type]
                query=query,
                reason=reason,
                suggested_action=action,
                status="open",
                created_at=utc_now(),
            )
        )

    problem = ""
    if not plan.protocol_steps:
        problem = "实验方案缺少可执行步骤"
    return plan, followups[:20], problem


# ---------------- indexing generated content ----------------


def build_generated_chunks(
    ideas: Iterable[Idea], directions: Iterable[Direction]
) -> list[tuple[str, dict[str, Any]]]:
    """Make ideas/directions searchable alongside the corpus (closed loop)."""
    chunks: list[tuple[str, dict[str, Any]]] = []
    for idea in ideas:
        if idea.rejected_reason:
            continue
        text = f"【新想法】{idea.title}：{idea.hypothesis or idea.motivation}".strip()
        chunks.append(
            (
                stable_id("idea", idea.id),
                {
                    "paper_id": "",
                    "category_id": idea.category_ids[0] if idea.category_ids else "",
                    "kind": KIND_IDEA,
                    "ordinal": 0,
                    "text": text,
                    "page_number": None,
                    "metadata": {
                        "label": idea.title,
                        "idea_id": idea.id,
                        "generation": idea.generation,
                        "source_paper_ids": idea.source_paper_ids,
                        "confidence": idea.confidence,
                    },
                },
            )
        )
    for direction in directions:
        text = f"【研究方向】{direction.name}：{direction.question}".strip()
        chunks.append(
            (
                stable_id("direction", direction.id),
                {
                    "paper_id": "",
                    "category_id": "",
                    "kind": KIND_DIRECTION,
                    "ordinal": 0,
                    "text": text,
                    "page_number": None,
                    "metadata": {
                        "label": direction.name,
                        "direction_id": direction.id,
                        "generation": direction.generation,
                        "priority": direction.priority,
                    },
                },
            )
        )
    return chunks
