from __future__ import annotations

from typing import Any

from .config import ResearchSettings
from .corpus import resolve_pdf_path
from .interop import InteropError, load_reading_platform_module
from .normalizing import clamp_float, pick, string_list
from .schemas import EvidenceCard, Innovation


class AnalysisError(RuntimeError):
    pass


DEEP_SYSTEM_PROMPT = (
    "你是论文深度解析助手。输出必须是 JSON。所有结论只能来自给定论文文本；"
    "每条创新点必须附原文章节中的短引文和 PDF 页码，页码使用 [PAGE n] 标记中的整数。"
    "证据不足时明确写进 limitations，不要补全事实，也不要引用给定文本之外的论文。"
)

DEEP_JSON_SHAPE = """只返回一个 JSON 对象：
{
  "problem": "研究问题",
  "method": "核心方法",
  "findings": ["主要发现"],
  "innovations": [
    {
      "claim": "创新点",
      "evidence_pages": [1, 4],
      "evidence_quotes": ["原文短引文"]
    }
  ],
  "limitations": ["局限性"],
  "confidence": 0.0,
  "needs_review": false
}"""


def load_pdf_utils(settings: ResearchSettings) -> Any:
    """Reuse the reading platform's PDF extractor (pure module, no side effects)."""
    try:
        return load_reading_platform_module(settings.reading_platform_app, "pdf_utils")
    except InteropError as error:
        raise AnalysisError(f"无法复用阅读平台的 PDF 解析模块：{error}") from error


def extract_paper(settings: ResearchSettings, card: EvidenceCard) -> Any:
    path = resolve_pdf_path(card.pdf_path, settings.paper_root)
    if path is None:
        raise AnalysisError(f"PDF 不可读或不在论文仓库内：{card.pdf_path or '(空)'}")
    pdf_utils = load_pdf_utils(settings)
    return pdf_utils.extract_pdf(path)


def build_analysis_prompt(
    settings: ResearchSettings, card: EvidenceCard, extracted: Any
) -> tuple[str, str]:
    page_count = int(getattr(extracted, "page_count", 0) or 0)
    context = extracted.context(
        max_chars=settings.analysis_max_chars,
        page_limit=min(settings.analysis_page_limit, page_count) if page_count else 1,
    )
    label = card.title_zh or card.title
    user_prompt = f"""论文标题：{label}
原始标题：{card.title}
分类：{card.category_name or card.category_id}
页数：{page_count}
已有中文论点（仅作参考，请依据正文重新提取）：{card.thesis_zh}
已有中文创新点（仅作参考，请依据正文重新提取）：{card.novelty_zh}

带页码的论文正文节选：
{context}

{DEEP_JSON_SHAPE}
"""
    return DEEP_SYSTEM_PROMPT, user_prompt


def normalize_deep_analysis(raw: dict[str, Any], page_count: int) -> dict[str, Any]:
    """Same contract as the reading platform's normalize_analysis, deep fields only."""
    innovations: list[Innovation] = []
    for item in raw.get("innovations") or []:
        if isinstance(item, str):
            claim = item.strip()
            if claim:
                innovations.append(
                    Innovation(claim=claim[:600], evidence_pages=[], evidence_quotes=[])
                )
            continue
        if not isinstance(item, dict):
            continue
        pages = [
            page
            for page in (pick(item, "evidence_pages", "pages", "evidencePages") or [])
            if isinstance(page, int) and 1 <= page <= max(page_count, 1)
        ]
        quotes = pick(item, "evidence_quotes", "quotes", "evidenceQuotes") or []
        claim = str(pick(item, "claim", "innovation") or "").strip()
        if not claim:
            continue
        innovations.append(
            Innovation(
                claim=claim[:600],
                evidence_pages=sorted(set(pages))[:8],
                evidence_quotes=[
                    text[:400] for text in string_list(quotes, limit=3, max_chars=400)
                ],
            )
        )

    return {
        "problem": str(pick(raw, "problem") or "").strip()[:2000],
        "method": str(pick(raw, "method") or "").strip()[:2000],
        "findings": string_list(pick(raw, "findings", "main_findings"), limit=12, max_chars=600),
        "innovations": innovations[:10],
        "limitations": string_list(raw.get("limitations"), limit=10, max_chars=600),
        "confidence": clamp_float(raw.get("confidence"), 0.7),
        "needs_review": bool(raw.get("needs_review")),
    }
