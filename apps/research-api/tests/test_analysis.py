"""Stage D: prompt contract, PDF reuse, and deep-analysis normalization.

The PDF extractor is the reading platform's own module, loaded read-only
through the interop allowlist; these tests exercise the real code path.
"""

from __future__ import annotations

import dataclasses
import threading
from types import ModuleType

import pytest

from app import interop
from app.analysis import (
    DEEP_JSON_SHAPE,
    DEEP_SYSTEM_PROMPT,
    AnalysisError,
    build_analysis_prompt,
    extract_paper,
    load_pdf_utils,
    normalize_deep_analysis,
)
from app.config import ResearchSettings
from app.interop import InteropError, load_reading_platform_module
from app.schemas import EvidenceCard
from conftest import PAPERS

PAPER = PAPERS[0]


def _card(**overrides: object) -> EvidenceCard:
    payload = {
        "paper_id": PAPER["id"],
        "title": PAPER["title"],
        "title_zh": PAPER["title_zh"],
        "category_id": PAPER["category_id"],
        "category_name": "模型安全微调",
        "thesis_zh": PAPER["thesis_zh"],
        "novelty_zh": PAPER["novelty_zh"],
        "pdf_path": f"papers/{PAPER['id']}.pdf",
        "page_count": 3,
    }
    payload.update(overrides)
    return EvidenceCard(**payload)


# ---------------- prompt contract ----------------


def test_system_prompt_pins_evidence_to_pages() -> None:
    assert "[PAGE n]" in DEEP_SYSTEM_PROMPT
    assert "不要补全事实" in DEEP_SYSTEM_PROMPT
    assert "给定文本之外的论文" in DEEP_SYSTEM_PROMPT
    assert "JSON" in DEEP_SYSTEM_PROMPT


def test_json_shape_declares_every_field_the_pipeline_reads() -> None:
    for field in (
        "problem",
        "method",
        "findings",
        "innovations",
        "claim",
        "evidence_pages",
        "evidence_quotes",
        "limitations",
        "confidence",
        "needs_review",
    ):
        assert field in DEEP_JSON_SHAPE


def test_user_prompt_carries_the_paper_and_its_page_numbers(
    settings: ResearchSettings,
) -> None:
    extracted = extract_paper(settings, _card())

    system_prompt, user_prompt = build_analysis_prompt(settings, _card(), extracted)

    assert system_prompt == DEEP_SYSTEM_PROMPT
    assert f"论文标题：{PAPER['title_zh']}" in user_prompt
    assert f"原始标题：{PAPER['title']}" in user_prompt
    assert "分类：模型安全微调" in user_prompt
    assert "页数：3" in user_prompt
    assert "带页码的论文正文节选：" in user_prompt
    assert "[PAGE 1]" in user_prompt and "[PAGE 3]" in user_prompt
    assert "Evidence sentence for the innovation claim." in user_prompt
    # The existing Chinese thesis is passed as a hint, not as ground truth.
    assert PAPER["thesis_zh"] in user_prompt
    assert "仅作参考" in user_prompt
    assert DEEP_JSON_SHAPE in user_prompt


def test_prompt_uses_the_english_title_when_no_chinese_one_exists(
    settings: ResearchSettings,
) -> None:
    extracted = extract_paper(settings, _card())
    card = _card(title_zh="")

    _, user_prompt = build_analysis_prompt(settings, card, extracted)

    assert f"论文标题：{PAPER['title']}" in user_prompt


def test_page_limit_samples_head_and_tail_pages(settings: ResearchSettings) -> None:
    """Long papers are sampled, not truncated from the front only."""
    narrow = dataclasses.replace(settings, analysis_page_limit=2)
    card = _card()
    extracted = extract_paper(narrow, card)

    _, user_prompt = build_analysis_prompt(narrow, card, extracted)

    assert user_prompt.count("[PAGE ") == 2
    assert "[PAGE 1]" in user_prompt and "[PAGE 3]" in user_prompt
    assert "[PAGE 2]" not in user_prompt


def test_context_respects_the_character_budget(settings: ResearchSettings) -> None:
    small = dataclasses.replace(settings, analysis_max_chars=160)
    card = _card()

    extracted = extract_paper(small, card)
    _, user_prompt = build_analysis_prompt(small, card, extracted)

    body = user_prompt.split("带页码的论文正文节选：", 1)[1].split(DEEP_JSON_SHAPE, 1)[0]
    assert 0 < len(body.strip()) <= 170


# ---------------- PDF reuse (read-only interop) ----------------


def test_extract_paper_reads_the_repository_pdf(settings: ResearchSettings) -> None:
    extracted = extract_paper(settings, _card())

    assert extracted.page_count == 3
    assert len(extracted.page_texts) == 3
    assert PAPER["title"] in extracted.full_text
    assert extracted.sha256 and extracted.size_bytes > 0


def test_load_pdf_utils_reuses_the_reading_platform_module(
    settings: ResearchSettings,
) -> None:
    pdf_utils = load_pdf_utils(settings)

    assert callable(pdf_utils.extract_pdf)
    assert pdf_utils.__name__ == "paper_atlas.pdf_utils"


def test_extract_paper_rejects_a_missing_pdf(settings: ResearchSettings) -> None:
    card = _card(pdf_path="papers/does-not-exist.pdf")

    with pytest.raises(AnalysisError) as error:
        extract_paper(settings, card)

    assert "PDF 不可读" in str(error.value)


def test_extract_paper_rejects_paths_outside_the_repository(
    settings: ResearchSettings,
) -> None:
    card = _card(pdf_path="../../storage/api/library.sqlite3")

    with pytest.raises(AnalysisError):
        extract_paper(settings, card)


def test_interop_refuses_modules_outside_the_allowlist(
    settings: ResearchSettings,
) -> None:
    """Their `config` would load apps/api/.env into this process."""
    with pytest.raises(InteropError) as error:
        load_reading_platform_module(settings.reading_platform_app, "config")

    assert "不在允许清单内" in str(error.value)


def test_interop_reports_a_missing_reading_platform(tmp_path) -> None:
    interop.clear_cache()
    try:
        with pytest.raises(InteropError) as error:
            load_reading_platform_module(tmp_path / "absent", "pdf_utils")
        assert "未找到阅读平台代码目录" in str(error.value)
    finally:
        interop.clear_cache()


def test_interop_load_survives_concurrent_worker_threads(
    settings: ResearchSettings,
) -> None:
    """Deep analysis extracts several PDFs at once, all needing this module.

    Regression: the cache used to be read straight from sys.modules, which holds
    a module *before* its body has run, so concurrent callers got a
    half-initialized module and failed with AttributeError.
    """
    api_root = settings.reading_platform_app
    workers = 8
    loaded: list[ModuleType] = []
    failures: list[BaseException] = []
    gate = threading.Barrier(workers)

    def worker() -> None:
        gate.wait()
        try:
            loaded.append(load_reading_platform_module(api_root, "pdf_utils"))
        except BaseException as error:  # noqa: BLE001 - asserted below
            failures.append(error)

    interop.clear_cache()
    threads = [threading.Thread(target=worker) for _ in range(workers)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
    finally:
        interop.clear_cache()

    assert failures == []
    assert len(loaded) == workers
    assert all(module is loaded[0] for module in loaded)
    assert callable(loaded[0].extract_pdf)


# ---------------- normalization ----------------


def test_normalize_keeps_only_pages_that_exist(page_count: int = 3) -> None:
    raw = {
        "problem": "  研究问题  ",
        "method": "方法",
        "findings": ["发现一", "发现一", "发现二"],
        "innovations": [
            {"claim": "创新点", "evidence_pages": [3, 1, 5, 0, -2, 1], "evidence_quotes": ["引文"]},
        ],
        "limitations": ["局限"],
        "confidence": 0.42,
        "needs_review": True,
    }

    normalized = normalize_deep_analysis(raw, page_count)

    innovation = normalized["innovations"][0]
    assert innovation.evidence_pages == [1, 3]
    assert innovation.evidence_quotes == ["引文"]
    assert normalized["problem"] == "研究问题"
    assert normalized["findings"] == ["发现一", "发现二"]
    assert normalized["confidence"] == 0.42
    assert normalized["needs_review"] is True


def test_normalize_drops_evidence_less_innovations() -> None:
    raw = {
        "innovations": [
            {"claim": "   ", "evidence_pages": [1]},
            {"evidence_pages": [1]},
            {"claim": "有效创新点", "evidence_pages": [2]},
            "字符串形式的创新点",
            42,
        ]
    }

    innovations = normalize_deep_analysis(raw, 3)["innovations"]

    assert [item.claim for item in innovations] == ["有效创新点", "字符串形式的创新点"]
    assert innovations[1].evidence_pages == []


def test_normalize_accepts_the_field_aliases_models_actually_use() -> None:
    raw = {
        "main_findings": "发现一行一\n发现行二",
        "innovations": [
            {
                "innovation": "别名创新点",
                "pages": [2],
                "quotes": ["quote"],
            }
        ],
        "confidence": "0.9",
    }

    normalized = normalize_deep_analysis(raw, 5)

    assert normalized["findings"] == ["发现一行一", "发现行二"]
    assert normalized["innovations"][0].claim == "别名创新点"
    assert normalized["innovations"][0].evidence_pages == [2]
    assert normalized["confidence"] == 0.9


@pytest.mark.parametrize(
    ("value", "expected"),
    [(5, 1.0), (-3, 0.0), ("nonsense", 0.7), (None, 0.7), (float("nan"), 0.7)],
)
def test_normalize_clamps_confidence(value: object, expected: float) -> None:
    assert normalize_deep_analysis({"confidence": value}, 3)["confidence"] == expected


def test_normalize_caps_list_sizes_and_text_lengths() -> None:
    raw = {
        "problem": "p" * 5000,
        "findings": [f"发现 {index}" for index in range(40)],
        "limitations": [f"局限 {index}" for index in range(40)],
        "innovations": [
            {
                "claim": "c" * 1200,
                "evidence_pages": list(range(1, 30)),
                "evidence_quotes": [f"引文{index}" + "q" * 900 for index in range(9)],
            }
            for _ in range(30)
        ],
    }

    normalized = normalize_deep_analysis(raw, 40)

    assert len(normalized["problem"]) == 2000
    assert len(normalized["findings"]) == 12
    assert len(normalized["limitations"]) == 10
    assert len(normalized["innovations"]) == 10
    innovation = normalized["innovations"][0]
    assert len(innovation.claim) == 600
    assert len(innovation.evidence_pages) == 8
    assert len(innovation.evidence_quotes) == 3
    assert all(len(quote) == 400 for quote in innovation.evidence_quotes)


def test_normalize_handles_an_empty_payload() -> None:
    normalized = normalize_deep_analysis({}, 0)

    assert normalized["problem"] == ""
    assert normalized["innovations"] == []
    assert normalized["confidence"] == 0.7
    assert normalized["needs_review"] is False
