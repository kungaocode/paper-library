"""Stages E/F/G contracts: evidence rendering, citation gate, normalization.

The prompt literals asserted here are the same ones the offline mock provider
parses, so a wording change that would silently break the loop fails fast.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.chunking import stable_id
from app.schemas import Direction, Idea, SearchHit
from app.synthesis import (
    CRITIQUE_SYSTEM_PROMPT,
    DEFAULT_MAX_CHUNKS_PER_PAPER,
    DIRECTION_SYSTEM_PROMPT,
    EXPERIMENT_SYSTEM_PROMPT,
    IDEATION_SYSTEM_PROMPT,
    KIND_DIRECTION,
    KIND_IDEA,
    apply_critique,
    build_evidence_pack,
    build_generated_chunks,
    diversify_by_paper,
    find_duplicate,
    idea_signature,
    normalize_critique,
    normalize_direction,
    normalize_experiment,
    normalize_idea,
    render_critique_prompt,
    render_direction_prompt,
    render_experiment_prompt,
    render_ideation_prompt,
)
from conftest import PAPERS

PAPER_A = PAPERS[0]["id"]
PAPER_B = PAPERS[1]["id"]
KNOWN_PAPERS = {PAPER_A, PAPER_B}
CATEGORIES = {PAPER_A: "cat-01", PAPER_B: "cat-04"}
KNOWN_CHUNKS = {"chunk-aaa111", "chunk-bbb222"}
KNOWN_IDEAS = {"idea-0123456789ab", "idea-fedcba987654"}


def _hit(
    chunk_id: str,
    *,
    paper_id: str = PAPER_A,
    text: str = "创新点证据文本",
    score: float = 0.5,
    kind: str = "paper.innovation",
    category_id: str = "cat-01",
    page_number: int | None = 3,
) -> SearchHit:
    return SearchHit(
        chunk_id=chunk_id,
        paper_id=paper_id,
        paper_title=PAPERS[0]["title_zh"],
        category_id=category_id,
        kind=kind,
        text=text,
        score=score,
        page_number=page_number,
    )


def _idea(**overrides: object) -> Idea:
    payload: dict[str, object] = {
        "id": "idea-0123456789ab",
        "title": "把安全token约束迁移到工具调用链",
        "hypothesis": "决策点约束可降低注入成功率",
        "motivation": "两篇论文指向同一干预层",
        "method_sketch": "标注决策 token 后加锚定正则",
        "novelty_claim": "把训练期约束扩展到运行时",
        "risks": ["决策 token 界定不稳定"],
        "source_paper_ids": [PAPER_A, PAPER_B],
        "evidence_refs": ["chunk-aaa111"],
        "category_ids": ["cat-01", "cat-04"],
        "confidence": 0.6,
        "generation": 1,
        "batch_id": "batch-test",
    }
    payload.update(overrides)
    return Idea(**payload)


def _direction(**overrides: object) -> Direction:
    payload: dict[str, object] = {
        "id": "dir-0123456789ab",
        "name": "决策点安全约束",
        "question": "能否统一微调期与运行时的安全约束？",
        "gap_analysis": "缺少跨层对齐的公开工作",
        "member_idea_ids": ["idea-0123456789ab"],
        "source_paper_ids": [PAPER_A, PAPER_B],
        "roadmap": ["复现基线", "构造标注流程"],
        "priority": 0.8,
        "generation": 2,
    }
    payload.update(overrides)
    return Direction(**payload)


# ---------------- evidence pack ----------------


def test_evidence_pack_prints_ids_verbatim_for_citation() -> None:
    hits = [
        _hit("chunk-aaa111", score=0.85),
        _hit("chunk-bbb222", paper_id=PAPER_B, category_id="cat-04", page_number=None),
        _hit("chunk-cat001", paper_id="", kind="category.positioning", category_id="cat-01"),
    ]

    pack = build_evidence_pack("查询", hits)

    assert f"paper_id={PAPER_A}" in pack.text
    assert f"paper_id={PAPER_B}" in pack.text
    assert "paper_id=(分类级)" in pack.text
    assert "chunk_id=chunk-aaa111" in pack.text
    assert "页码=3" in pack.text
    assert "相关度=0.850" in pack.text
    assert "类型=category.positioning" in pack.text
    # Category-level chunks are citable as evidence but are not papers.
    assert pack.paper_ids == [PAPER_A, PAPER_B]
    assert pack.chunk_ids == ["chunk-aaa111", "chunk-bbb222", "chunk-cat001"]
    assert len(pack.hits) == 3
    assert pack.query == "查询"


def test_evidence_pack_truncates_each_hit() -> None:
    pack = build_evidence_pack(
        "查询", [_hit("chunk-aaa111", text="证" * 600)], max_chars_per_hit=100
    )

    body = pack.text.splitlines()[-1].strip()
    assert len(body) == 100
    assert body.endswith("…")


def test_evidence_pack_flattens_newlines() -> None:
    pack = build_evidence_pack("查询", [_hit("chunk-aaa111", text="第一行\n第二行")])

    assert "第一行 第二行" in pack.text


def test_evidence_pack_stops_at_the_total_budget() -> None:
    hits = [_hit(f"chunk-{index:03d}", text="证" * 200) for index in range(5)]

    pack = build_evidence_pack("查询", hits, max_total_chars=400)

    assert 0 < len(pack.hits) < len(hits)
    assert len(pack.chunk_ids) == len(pack.hits)
    assert pack.text.count("[") == len(pack.hits)


def test_evidence_pack_without_hits_is_empty_but_valid() -> None:
    pack = build_evidence_pack("查询", [])

    assert pack.text == ""
    assert pack.hits == [] and pack.paper_ids == [] and pack.chunk_ids == []


# ---------------- evidence diversification ----------------


def test_diversify_caps_a_dominant_paper_and_keeps_rank_order() -> None:
    pool = [
        _hit("chunk-a1", paper_id=PAPER_A, score=0.95),
        _hit("chunk-a2", paper_id=PAPER_A, score=0.90),
        _hit("chunk-a3", paper_id=PAPER_A, score=0.85),
        _hit("chunk-b1", paper_id=PAPER_B, category_id="cat-04", score=0.80),
        _hit("chunk-a4", paper_id=PAPER_A, score=0.75),
        _hit("chunk-b2", paper_id=PAPER_B, category_id="cat-04", score=0.70),
    ]

    kept = diversify_by_paper(pool, limit=4)

    assert [hit.chunk_id for hit in kept] == ["chunk-a1", "chunk-a2", "chunk-b1", "chunk-b2"]
    # The whole point of the cap: the pack must be able to cite two papers.
    assert build_evidence_pack("查询", kept).paper_ids == [PAPER_A, PAPER_B]


def test_diversify_backfills_when_the_pool_covers_one_paper() -> None:
    pool = [
        _hit(f"chunk-a{index}", paper_id=PAPER_A, score=0.9 - index * 0.01) for index in range(4)
    ]

    kept = diversify_by_paper(pool, limit=4)

    assert len(kept) == 4
    assert {hit.paper_id for hit in kept} == {PAPER_A}


def test_diversify_caps_category_level_chunks_as_one_bucket() -> None:
    pool = [
        _hit("chunk-cat01", paper_id="", kind="category.positioning", category_id="cat-01", score=0.9),
        _hit("chunk-cat02", paper_id="", kind="category.positioning", category_id="cat-01", score=0.8),
        _hit("chunk-cat03", paper_id="", kind="category.positioning", category_id="cat-01", score=0.7),
        _hit("chunk-a1", paper_id=PAPER_A, score=0.6),
    ]

    kept = diversify_by_paper(pool, limit=3)

    assert [hit.chunk_id for hit in kept] == ["chunk-cat01", "chunk-cat02", "chunk-a1"]


def test_diversify_treats_each_category_as_its_own_bucket() -> None:
    pool = [
        _hit("chunk-cat01", paper_id="", kind="category.positioning", category_id="cat-01", score=0.9),
        _hit("chunk-cat02", paper_id="", kind="category.positioning", category_id="cat-02", score=0.8),
        _hit("chunk-cat03", paper_id="", kind="category.positioning", category_id="cat-03", score=0.7),
        _hit("chunk-a1", paper_id=PAPER_A, score=0.6),
    ]

    kept = diversify_by_paper(pool, limit=4)

    assert [hit.chunk_id for hit in kept] == [
        "chunk-cat01",
        "chunk-cat02",
        "chunk-cat03",
        "chunk-a1",
    ]


def test_diversify_honours_an_explicit_cap() -> None:
    pool = [
        _hit(f"chunk-a{index}", paper_id=PAPER_A, score=0.9 - index * 0.01) for index in range(3)
    ]

    assert len(diversify_by_paper(pool, limit=3, max_per_paper=1)) == 3
    assert len(diversify_by_paper(pool, limit=2, max_per_paper=1)) == 2


def test_diversify_uses_the_module_default_cap() -> None:
    pool = [
        _hit(f"chunk-a{index}", paper_id=PAPER_A) for index in range(3)
    ] + [_hit("chunk-b1", paper_id=PAPER_B, category_id="cat-04")]

    kept = diversify_by_paper(pool, limit=3)

    assert sum(hit.paper_id == PAPER_A for hit in kept) == DEFAULT_MAX_CHUNKS_PER_PAPER


def test_diversify_edge_arguments_are_harmless() -> None:
    pool = [_hit("chunk-a1", paper_id=PAPER_A), _hit("chunk-b1", paper_id=PAPER_B)]

    assert diversify_by_paper(pool, limit=0) == []
    assert diversify_by_paper([], limit=5) == []
    # A non-positive cap must not silently drop all evidence.
    assert len(diversify_by_paper(pool, limit=5, max_per_paper=0)) == 2


# ---------------- idea normalization / citation gate ----------------


def test_idea_with_two_corpus_citations_is_accepted() -> None:
    raw = {
        "title": "新想法",
        "hypothesis": "假设",
        "motivation": "动机",
        "method_sketch": "方法",
        "expected_contribution": "贡献",
        "novelty_claim": "新颖性",
        "risks": ["风险一"],
        "required_resources": ["单卡"],
        "source_paper_ids": [PAPER_A, PAPER_B],
        "evidence_refs": ["chunk-aaa111", "chunk-not-in-pack"],
        "confidence": 0.7,
    }

    idea, reason = normalize_idea(
        raw,
        batch_id="batch-test",
        generation=1,
        known_paper_ids=KNOWN_PAPERS,
        known_chunk_ids=KNOWN_CHUNKS,
        category_by_paper=CATEGORIES,
    )

    assert reason == ""
    assert idea.title == "新想法"
    assert idea.source_paper_ids == [PAPER_A, PAPER_B]
    assert idea.category_ids == ["cat-01", "cat-04"]
    # Only chunk ids that were really in the prompt survive.
    assert idea.evidence_refs == ["chunk-aaa111"]
    assert idea.confidence == 0.7
    assert idea.generation == 1 and idea.batch_id == "batch-test"
    assert idea.created_at


def test_idea_ids_are_stable_for_a_batch_and_title() -> None:
    kwargs = {
        "batch_id": "batch-test",
        "generation": 1,
        "known_paper_ids": KNOWN_PAPERS,
        "known_chunk_ids": KNOWN_CHUNKS,
        "category_by_paper": CATEGORIES,
    }
    raw = {"title": "同一个标题", "source_paper_ids": [PAPER_A, PAPER_B]}

    first, _ = normalize_idea(raw, **kwargs)
    second, _ = normalize_idea(dict(raw), **kwargs)
    other, _ = normalize_idea({**raw, "title": "另一个标题"}, **kwargs)
    other_batch, _ = normalize_idea(dict(raw), **{**kwargs, "batch_id": "batch-other"})

    assert first.id == second.id == f"idea-{stable_id('batch-test', '同一个标题')[:12]}"
    assert first.id != other.id
    assert first.id != other_batch.id


def test_idea_without_corpus_citations_is_rejected() -> None:
    raw = {
        "title": "编造引用的想法",
        "source_paper_ids": ["paper-deadbeef99", "arxiv:2401.00001"],
    }

    idea, reason = normalize_idea(
        raw,
        batch_id="batch-test",
        generation=1,
        known_paper_ids=KNOWN_PAPERS,
        known_chunk_ids=KNOWN_CHUNKS,
        category_by_paper=CATEGORIES,
    )

    assert reason.startswith("引用校验失败")
    assert "paper-deadbeef99" in reason
    assert idea.source_paper_ids == []
    assert idea.title == "编造引用的想法"


def test_idea_without_any_citation_field_is_rejected() -> None:
    _, reason = normalize_idea(
        {"title": "无引用"},
        batch_id="b",
        generation=1,
        known_paper_ids=KNOWN_PAPERS,
        known_chunk_ids=KNOWN_CHUNKS,
        category_by_paper=CATEGORIES,
    )

    assert reason == "引用校验失败：没有指向语料内真实论文的 source_paper_ids"


def test_single_paper_idea_is_rejected_as_not_cross_paper() -> None:
    _, reason = normalize_idea(
        {"title": "只引一篇", "source_paper_ids": [PAPER_A]},
        batch_id="b",
        generation=1,
        known_paper_ids=KNOWN_PAPERS,
        known_chunk_ids=KNOWN_CHUNKS,
        category_by_paper=CATEGORIES,
    )

    assert reason.startswith("证据不足：只引用了 1 篇论文")


def test_unknown_citations_are_dropped_but_recorded_as_a_risk() -> None:
    idea, reason = normalize_idea(
        {
            "title": "混合引用",
            "source_paper_ids": [PAPER_A, PAPER_B, "paper-deadbeef99"],
            "risks": ["原有风险"],
        },
        batch_id="b",
        generation=1,
        known_paper_ids=KNOWN_PAPERS,
        known_chunk_ids=KNOWN_CHUNKS,
        category_by_paper=CATEGORIES,
    )

    assert reason == ""
    assert idea.source_paper_ids == [PAPER_A, PAPER_B]
    assert idea.risks[0] == "原有风险"
    assert "已丢弃" in idea.risks[-1] and "paper-deadbeef99" in idea.risks[-1]


def test_idea_aliases_and_limits_are_normalized() -> None:
    raw = {
        "name": "  别名标题  ",
        "hypothesis": "h" * 5000,
        "method": "方法别名",
        "novelty": "新颖性别名",
        "resources": "单卡即可",
        "citations": [PAPER_A, PAPER_B],
        "evidence": ["chunk-aaa111"],
        "confidence": 4,
        "risks": [f"风险{index}" for index in range(30)],
    }

    idea, reason = normalize_idea(
        raw,
        batch_id="b",
        generation=1,
        known_paper_ids=KNOWN_PAPERS,
        known_chunk_ids=KNOWN_CHUNKS,
        category_by_paper=CATEGORIES,
    )

    assert reason == ""
    assert idea.title == "别名标题"
    assert len(idea.hypothesis) == 2000
    assert idea.method_sketch == "方法别名"
    assert idea.novelty_claim == "新颖性别名"
    assert idea.required_resources == ["单卡即可"]
    assert idea.confidence == 1.0
    assert len(idea.risks) == 8


@pytest.mark.parametrize("raw", ["只是一段话", 42, None, ["列表"]])
def test_non_object_ideas_are_rejected(raw: object) -> None:
    idea, reason = normalize_idea(
        raw,
        batch_id="b",
        generation=1,
        known_paper_ids=KNOWN_PAPERS,
        known_chunk_ids=KNOWN_CHUNKS,
        category_by_paper=CATEGORIES,
    )

    assert reason == "想法不是 JSON 对象"
    assert idea.id.startswith("idea-")
    assert idea.rejected_reason == ""


def test_idea_without_a_title_is_rejected() -> None:
    idea, reason = normalize_idea(
        {"title": "   ", "source_paper_ids": [PAPER_A, PAPER_B]},
        batch_id="b",
        generation=1,
        known_paper_ids=KNOWN_PAPERS,
        known_chunk_ids=KNOWN_CHUNKS,
        category_by_paper=CATEGORIES,
    )

    assert reason == "模型未给出想法标题"
    assert idea.title == "(无效想法)"


# ---------------- critique ----------------


def test_critique_score_is_a_weighted_mix() -> None:
    critique = normalize_critique(
        {
            "novelty": 1.0,
            "feasibility": 0.5,
            "evidence_support": 1.0,
            "risk": 0.0,
            "verdict": "值得做",
            "unsupported_claims": ["缺少基线"],
            "suggested_fix": "先做小规模验证",
        }
    )

    assert critique.score == round(0.3 * 1.0 + 0.25 * 0.5 + 0.3 * 1.0 + 0.15 * 1.0, 4)
    assert critique.verdict == "值得做"
    assert critique.unsupported_claims == ["缺少基线"]


def test_critique_clamps_out_of_range_scores_and_uses_defaults() -> None:
    critique = normalize_critique({"novelty": 7, "feasibility": -2, "risk": "high"})

    assert critique.novelty == 1.0
    assert critique.feasibility == 0.0
    assert critique.risk == 0.5
    assert critique.evidence_support == 0.5


def test_unparsable_critique_is_marked_instead_of_crashing() -> None:
    critique = normalize_critique("模型跑偏了")

    assert critique.verdict == "评审结果不可解析"
    assert critique.score == 0.0


def test_apply_critique_lets_the_reviewer_outweigh_self_confidence() -> None:
    idea = _idea(confidence=1.0)
    critique = normalize_critique(
        {"novelty": 0.0, "feasibility": 0.0, "evidence_support": 0.0, "risk": 1.0}
    )

    reviewed = apply_critique(idea, critique)

    assert critique.score == 0.0
    assert reviewed.confidence == round(0.4 * 1.0 + 0.6 * 0.0, 3)
    assert reviewed.critique["verdict"] == critique.verdict
    assert reviewed.critique["score"] == 0.0


# ---------------- dedupe ----------------


def test_idea_signature_covers_the_claim_bearing_fields() -> None:
    idea = _idea()
    signature = idea_signature(idea)

    assert idea.title in signature
    assert idea.hypothesis in signature
    assert idea.method_sketch in signature
    assert idea.novelty_claim in signature
    # Motivation is context, not part of the dedupe fingerprint.
    assert idea.motivation not in signature
    bare = _idea(hypothesis="", method_sketch="", novelty_claim="")
    assert idea_signature(bare) == bare.title


def test_find_duplicate_flags_near_identical_ideas() -> None:
    # cos((1,0,0), (0.9,0.1,0)) = 0.9939, so it only clears a stricter bar.
    vector = np.array([1.0, 0.0, 0.0])
    orthogonal = [("idea-a", np.array([0.0, 1.0, 0.0])), ("idea-b", np.array([0.0, 0.0, 1.0]))]
    near_identical = [("idea-c", np.array([0.9, 0.1, 0.0]))]

    assert find_duplicate(vector, orthogonal, 0.5) == ""
    assert find_duplicate(vector, near_identical, 0.92) == "idea-c"
    assert find_duplicate(vector, near_identical, 0.999) == ""
    assert find_duplicate(vector, [], 0.5) == ""
    assert find_duplicate(vector, [("idea-a", vector.copy())], 0.92) == "idea-a"


def test_find_duplicate_ignores_zero_vectors() -> None:
    zero = np.zeros(3)

    assert find_duplicate(zero, [("idea-a", np.ones(3))], 0.1) == ""
    assert find_duplicate(np.ones(3), [("idea-a", zero)], 0.1) == ""


# ---------------- direction normalization ----------------


def test_direction_keeps_only_real_members_and_papers() -> None:
    raw = {
        "name": "新方向",
        "question": "问题",
        "rationale": "理由",
        "gap_analysis": "空白",
        "roadmap": ["阶段一"],
        "success_metrics": ["指标"],
        "open_risks": ["风险"],
        "member_idea_ids": ["idea-0123456789ab", "idea-phantom00"],
        "source_paper_ids": [PAPER_A, "paper-phantom00"],
        "priority": 0.9,
    }

    direction, reason = normalize_direction(
        raw,
        batch_id="batch-test",
        generation=2,
        known_idea_ids=KNOWN_IDEAS,
        known_paper_ids=KNOWN_PAPERS,
    )

    assert reason == ""
    assert direction.member_idea_ids == ["idea-0123456789ab"]
    assert direction.source_paper_ids == [PAPER_A]
    assert direction.priority == 0.9
    assert direction.status == "proposed"
    assert direction.generation == 2
    assert direction.id == f"dir-{stable_id('batch-test', '新方向')[:12]}"


def test_direction_without_real_members_is_rejected() -> None:
    direction, reason = normalize_direction(
        {"name": "空方向", "member_idea_ids": ["idea-phantom00"]},
        batch_id="b",
        generation=1,
        known_idea_ids=KNOWN_IDEAS,
        known_paper_ids=KNOWN_PAPERS,
    )

    assert reason.startswith("成员校验失败")
    assert direction.member_idea_ids == []


def test_direction_lineage_needs_a_real_parent() -> None:
    kwargs = {
        "batch_id": "b",
        "generation": 2,
        "known_idea_ids": KNOWN_IDEAS,
        "known_paper_ids": KNOWN_PAPERS,
    }
    raw = {"name": "延续方向", "member_idea_ids": ["idea-0123456789ab"]}

    known, _ = normalize_direction(
        {**raw, "parent_direction_id": "dir-0123456789ab"},
        known_direction_ids={"dir-0123456789ab"},
        **kwargs,
    )
    phantom, _ = normalize_direction(
        {**raw, "parent_direction_id": "dir-phantom0000"},
        known_direction_ids={"dir-0123456789ab"},
        **kwargs,
    )
    unguarded, _ = normalize_direction({**raw, "parent_direction_id": "dir-x"}, **kwargs)

    assert known.parent_direction_id == "dir-0123456789ab"
    assert phantom.parent_direction_id == ""
    assert unguarded.parent_direction_id == ""


def test_direction_without_a_name_or_object_is_rejected() -> None:
    kwargs = {
        "batch_id": "b",
        "generation": 1,
        "known_idea_ids": KNOWN_IDEAS,
        "known_paper_ids": KNOWN_PAPERS,
    }

    _, unnamed = normalize_direction({"question": "没有问题名"}, **kwargs)
    _, not_object = normalize_direction("一段话", **kwargs)

    assert unnamed == "模型未给出方向名称"
    assert not_object == "方向不是 JSON 对象"


def test_direction_priority_is_clamped() -> None:
    direction, _ = normalize_direction(
        {"name": "方向", "member_idea_ids": ["idea-0123456789ab"], "priority": 12},
        batch_id="b",
        generation=1,
        known_idea_ids=KNOWN_IDEAS,
        known_paper_ids=KNOWN_PAPERS,
    )

    assert direction.priority == 1.0


# ---------------- experiment normalization ----------------


def test_experiment_plan_inherits_the_direction_and_keeps_the_protocol() -> None:
    direction = _direction()
    raw = {
        "objective": "验证假设",
        "hypothesis": "被检验的假设",
        "datasets": ["AgentHarm"],
        "baselines": ["无约束微调"],
        "metrics": ["ASR"],
        "protocol_steps": ["固定随机种子", "训练并评测"],
        "ablations": ["随机 token 对照"],
        "compute_estimate": "单卡两天",
        "falsification_criteria": "ASR 下降不足 10% 则否证",
        "timeline": ["第 1 周"],
        "risks": ["基准饱和"],
        "followups": [],
    }

    plan, followups, problem = normalize_experiment(raw, direction=direction, batch_id="batch-test")

    assert problem == ""
    assert followups == []
    assert plan.id == f"exp-{stable_id('batch-test', direction.id)[:12]}"
    assert plan.direction_id == direction.id
    assert plan.direction_name == direction.name
    assert plan.generation == direction.generation
    assert plan.status == "draft"
    assert plan.protocol_steps == ["固定随机种子", "训练并评测"]
    assert plan.falsification_criteria.startswith("ASR 下降不足")
    assert plan.datasets == ["AgentHarm"] and plan.baselines == ["无约束微调"]


def test_experiment_without_steps_is_flagged() -> None:
    plan, _, problem = normalize_experiment(
        {"objective": "只有目标"}, direction=_direction(), batch_id="b"
    )

    assert problem == "实验方案缺少可执行步骤"
    assert plan.protocol_steps == []


def test_non_object_experiment_is_flagged_but_still_tracked() -> None:
    direction = _direction()

    plan, followups, problem = normalize_experiment("跑偏了", direction=direction, batch_id="b")

    assert problem == "实验方案不是 JSON 对象"
    assert followups == []
    assert plan.direction_id == direction.id
    assert plan.id.startswith("exp-")


def test_followups_are_normalized_and_linked_to_the_experiment() -> None:
    direction = _direction()
    raw = {
        "protocol_steps": ["步骤"],
        "followups": [
            {"kind": "paper_to_read", "query": "decision token safety", "reason": "确认已有工作"},
            {"kind": "made_up_kind", "query": "dataset query", "reason": "理由"},
            "纯字符串待办",
            {"kind": "dataset"},
            {"kind": "tool", "query": "", "reason": ""},
            {"kind": "experiment", "reason": "只有理由也算", "suggested_action": "先跑消融"},
        ],
    }

    plan, followups, problem = normalize_experiment(raw, direction=direction, batch_id="batch-test")

    assert problem == ""
    assert [item.kind for item in followups] == [
        "paper_to_read",
        "question",
        "question",
        "experiment",
    ]
    assert followups[0].suggested_action.startswith("把该检索式交给阅读平台")
    assert followups[2].query == "纯字符串待办"
    assert followups[3].suggested_action == "先跑消融"
    for item in followups:
        assert item.id.startswith("fu-")
        assert item.direction_id == direction.id
        assert item.experiment_id == plan.id
        assert item.status == "open"
    assert len({item.id for item in followups}) == len(followups)


def test_followup_list_is_capped() -> None:
    raw = {
        "protocol_steps": ["步骤"],
        "followups": [
            {"kind": "question", "query": f"问题 {index}"} for index in range(60)
        ],
    }

    _, followups, _ = normalize_experiment(raw, direction=_direction(), batch_id="b")

    assert len(followups) == 20


# ---------------- indexing generated content ----------------


def test_generated_chunks_cover_accepted_ideas_and_directions() -> None:
    accepted = _idea()
    rejected = _idea(id="idea-fedcba987654", title="被拒想法", rejected_reason="引用校验失败")
    direction = _direction()

    chunks = build_generated_chunks([accepted, rejected], [direction])

    assert [data["kind"] for _, data in chunks] == [KIND_IDEA, KIND_DIRECTION]
    idea_id, idea_data = chunks[0]
    assert idea_id == stable_id("idea", accepted.id)
    assert idea_data["text"].startswith("【新想法】把安全token约束迁移到工具调用链：")
    assert idea_data["paper_id"] == ""
    assert idea_data["category_id"] == "cat-01"
    assert idea_data["page_number"] is None
    assert idea_data["metadata"]["idea_id"] == accepted.id
    assert idea_data["metadata"]["source_paper_ids"] == [PAPER_A, PAPER_B]
    assert idea_data["metadata"]["generation"] == 1

    direction_id, direction_data = chunks[1]
    assert direction_id == stable_id("direction", direction.id)
    assert direction_data["text"].startswith("【研究方向】决策点安全约束：")
    assert direction_data["kind"] == KIND_DIRECTION
    assert direction_data["metadata"]["direction_id"] == direction.id
    assert direction_data["metadata"]["priority"] == 0.8


def test_generated_idea_chunk_falls_back_to_motivation() -> None:
    chunks = build_generated_chunks([_idea(hypothesis="", motivation="动机文本")], [])

    assert chunks[0][1]["text"] == "【新想法】把安全token约束迁移到工具调用链：动机文本"


def test_generated_chunks_are_stable_across_rebuilds() -> None:
    ideas, directions = [_idea()], [_direction()]

    first = build_generated_chunks(ideas, directions)
    second = build_generated_chunks(ideas, directions)

    assert [chunk_id for chunk_id, _ in first] == [chunk_id for chunk_id, _ in second]


def test_no_generated_chunks_without_content() -> None:
    assert build_generated_chunks([], []) == []


# ---------------- prompt literals the loop depends on ----------------


def test_ideation_prompt_demands_verbatim_citations() -> None:
    pack = build_evidence_pack("查询", [_hit("chunk-aaa111")])

    prompt = render_ideation_prompt(
        query="跨论文的研究空白",
        pack=pack,
        corpus_size=(3, 25),
        idea_count=2,
        generation=4,
    )

    assert "【本轮聚焦问题】跨论文的研究空白" in prompt
    assert "第 4 代" in prompt
    assert "3 篇论文 / 25 个证据切片" in prompt
    assert pack.text in prompt
    assert "提出 2 个可以尝试的新研究想法" in prompt
    assert "source_paper_ids 必须逐字复制证据卡片中的 paper_id" in prompt
    assert "evidence_refs 必须逐字复制 chunk_id" in prompt
    assert "至少 2 张来自不同论文的证据卡片" in prompt
    for field in ("title", "hypothesis", "method_sketch", "novelty_claim", "confidence"):
        assert f'"{field}"' in prompt


def test_ideation_prompt_without_hits_says_evidence_is_missing() -> None:
    prompt = render_ideation_prompt(
        query="q", pack=build_evidence_pack("q", []), corpus_size=(0, 0), idea_count=1, generation=1
    )

    assert "(无命中，请说明证据不足)" in prompt


def test_critique_prompt_shows_the_idea_and_its_evidence() -> None:
    idea = _idea()
    pack = build_evidence_pack("查询", [_hit("chunk-aaa111")])

    prompt = render_critique_prompt(idea=idea, pack=pack)

    assert idea.title in prompt
    assert idea.hypothesis in prompt
    assert PAPER_A in prompt
    assert pack.text in prompt
    assert '"unsupported_claims"' in prompt
    assert "(无)" not in prompt


def test_direction_prompt_lists_member_ids_and_lineage() -> None:
    idea = _idea()
    parent = _direction()

    prompt = render_direction_prompt(
        ideas=[idea],
        titles={PAPER_A: "细粒度对齐", PAPER_B: "间接提示注入"},
        generation=3,
        parent=parent,
        feedback="请更聚焦智能体安全",
    )

    assert f"idea_id={idea.id}" in prompt
    assert f"{PAPER_A}(细粒度对齐)" in prompt
    assert "未知论文" not in prompt
    assert f"上一代方向ID：{parent.id}" in prompt
    assert f"上一代方向：{parent.name}" in prompt
    assert parent.question in prompt
    assert "用户反馈：请更聚焦智能体安全" in prompt
    assert "member_idea_ids 必须逐字使用上面出现的 idea_id" in prompt


def test_direction_prompt_without_parent_or_feedback_omits_those_blocks() -> None:
    prompt = render_direction_prompt(
        ideas=[], titles={}, generation=1, parent=None
    )

    assert "上一代方向ID" not in prompt
    assert "用户反馈" not in prompt
    assert "(无)" in prompt


def test_experiment_prompt_scopes_ideas_to_the_direction() -> None:
    direction = _direction()
    member = _idea()
    outsider = _idea(id="idea-fedcba987654", title="别的方向的想法")

    prompt = render_experiment_prompt(
        direction=direction,
        ideas=[member, outsider],
        titles={PAPER_A: "细粒度对齐", PAPER_B: "间接提示注入"},
    )

    assert f"研究方向：{direction.name}" in prompt
    assert f"方向ID：{direction.id}" in prompt
    assert member.title in prompt
    assert "别的方向的想法" not in prompt
    assert f"- {PAPER_A}：细粒度对齐" in prompt
    assert '"followups"' in prompt
    assert '"falsification_criteria"' in prompt


def test_system_prompts_forbid_invention() -> None:
    assert "禁止编造论文" in IDEATION_SYSTEM_PROMPT
    assert "证据不足" in CRITIQUE_SYSTEM_PROMPT
    assert "不得编造" in DIRECTION_SYSTEM_PROMPT
    assert "不得编造已有结果" in EXPERIMENT_SYSTEM_PROMPT
    for prompt in (
        IDEATION_SYSTEM_PROMPT,
        CRITIQUE_SYSTEM_PROMPT,
        DIRECTION_SYSTEM_PROMPT,
        EXPERIMENT_SYSTEM_PROMPT,
    ):
        assert "JSON" in prompt
