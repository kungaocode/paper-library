"""Stage C: how an evidence card becomes retrievable chunks."""

from __future__ import annotations

from app.chunking import (
    KIND_CATEGORY,
    KIND_FINDING,
    KIND_INNOVATION,
    KIND_LIMITATION,
    KIND_METHOD,
    KIND_NOVELTY,
    KIND_PROBLEM,
    KIND_THESIS,
    build_category_chunks,
    build_paper_chunks,
    stable_id,
    tokenize,
)
from app.corpus import PaperLibraryReader
from app.schemas import EvidenceCard


def _card() -> EvidenceCard:
    return EvidenceCard(
        paper_id="paper-aaa111000000",
        title="Fine-Grained Alignment",
        title_zh="细粒度对齐",
        category_id="cat-01",
        category_name="微调安全：机理与测量",
        thesis_zh="安全能力集中在少量关键 token 上。",
        novelty_zh="提出 token 级安全置信度约束。",
        thesis_en="Safety concentrates on a few tokens.",
        problem="全量对齐代价高。",
        method="关键 token 锚定正则。",
        findings=["越狱成功率下降 41%", "通用基准损失小于 2%"],
        innovations=[
            {
                "claim": "把安全性建模为稀疏 token 属性",
                "evidence_pages": [3],
                "evidence_quotes": ["Safety concentrates on a few tokens."],
            }
        ],
        limitations=["依赖标注器质量"],
    )


def test_stable_id_is_deterministic_and_bounded() -> None:
    first = stable_id("paper-1", "kind", 0)
    assert first == stable_id("paper-1", "kind", 0)
    assert first != stable_id("paper-1", "kind", 1)
    assert len(first) == 20
    assert all(char in "0123456789abcdef" for char in first)


def test_paper_chunks_cover_every_field() -> None:
    chunks = build_paper_chunks(_card())
    kinds = [row["kind"] for _, row in chunks]

    assert kinds.count(KIND_THESIS) == 2  # 中文 + 英文论点
    assert KIND_NOVELTY in kinds
    assert KIND_PROBLEM in kinds
    assert KIND_METHOD in kinds
    assert kinds.count(KIND_FINDING) == 2
    assert kinds.count(KIND_INNOVATION) == 1
    assert kinds.count(KIND_LIMITATION) == 1

    ids = [chunk_id for chunk_id, _ in chunks]
    assert len(set(ids)) == len(ids), "同一篇论文的切片 id 必须唯一"

    for _chunk_id, row in chunks:
        assert row["paper_id"] == "paper-aaa111000000"
        assert row["category_id"] == "cat-01"
        assert row["text"].strip()
        assert row["metadata"]["label"] == "细粒度对齐"
        assert isinstance(row["ordinal"], int)


def test_innovation_chunk_keeps_page_and_quote() -> None:
    chunks = build_paper_chunks(_card())
    innovation = next(row for _, row in chunks if row["kind"] == KIND_INNOVATION)

    assert innovation["page_number"] == 3
    assert innovation["metadata"]["evidence_pages"] == [3]
    assert "把安全性建模为稀疏 token 属性" in innovation["text"]
    assert "Safety concentrates on a few tokens." in innovation["text"]
    assert "[PAGE 3]" in innovation["text"]


def test_deep_analysis_overrides_shallow_fields() -> None:
    card = _card()
    deep = {
        "problem": "深度解析后的问题描述",
        "method": "深度解析后的方法描述",
        "findings": ["深度发现"],
        "innovations": [
            {"claim": "深度创新点", "evidence_pages": [7], "evidence_quotes": ["deep quote"]}
        ],
        "limitations": ["深度局限"],
    }

    shallow = {row["text"] for _, row in build_paper_chunks(card)}
    enriched = {row["text"] for _, row in build_paper_chunks(card, deep=deep)}

    assert "全量对齐代价高。" in " ".join(shallow)
    joined = " ".join(enriched)
    assert "深度解析后的问题描述" in joined
    assert "深度创新点" in joined
    assert "[PAGE 7]" in joined
    assert "全量对齐代价高。" not in joined


def test_empty_card_produces_no_chunks() -> None:
    empty = EvidenceCard(paper_id="paper-empty", title="Empty", category_id="cat-01")
    assert build_paper_chunks(empty) == []


def test_blank_innovation_claims_are_dropped() -> None:
    payload = _card().model_dump()
    payload["innovations"] = [
        {"claim": "   ", "evidence_pages": [], "evidence_quotes": []},
        {"claim": "有效创新点", "evidence_pages": [2], "evidence_quotes": []},
    ]
    card = EvidenceCard(**payload)
    innovations = [row for _, row in build_paper_chunks(card) if row["kind"] == KIND_INNOVATION]
    assert len(innovations) == 1
    assert innovations[0]["text"].endswith("[PAGE 2]")


def test_category_chunks_are_corpus_level() -> None:
    chunks = build_category_chunks(
        {"cat-01": "训练期安全约束", "cat-04": "运行期安全"},
        {"cat-01": "微调安全", "cat-04": "智能体安全"},
    )

    assert len(chunks) == 2
    for _, row in chunks:
        assert row["kind"] == KIND_CATEGORY
        assert row["paper_id"] == ""
    assert "【主题定位】微调安全（cat-01）：训练期安全约束" in chunks[0][1]["text"]

    # Categories without a name fall back to the id; empty text is skipped.
    fallback = build_category_chunks({"cat-09": "定位", "cat-10": ""}, {})
    assert len(fallback) == 1
    assert "cat-09" in fallback[0][1]["text"]


def test_tokenize_handles_mixed_chinese_and_english() -> None:
    tokens = tokenize("Token 级安全约束 GCG")
    assert "token" in tokens
    assert "gcg" in tokens
    assert "安" in tokens and "全" in tokens
    assert "安全" in tokens  # CJK bigram
    assert tokenize("") == []


def test_chunks_are_rebuildable_from_the_real_reader(settings) -> None:
    """Same code path as the pipeline: read the library, then chunk it."""
    cards = PaperLibraryReader(settings).load_cards()
    total = 0
    for card in cards:
        chunks = build_paper_chunks(card)
        assert chunks
        total += len(chunks)
    assert total >= len(cards) * 5
