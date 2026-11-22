from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

from .schemas import EvidenceCard


# Chunk kinds are stable identifiers used by the UI and by evidence citations.
KIND_THESIS = "paper.thesis"
KIND_NOVELTY = "paper.novelty"
KIND_PROBLEM = "paper.problem"
KIND_METHOD = "paper.method"
KIND_FINDING = "paper.finding"
KIND_INNOVATION = "paper.innovation"
KIND_LIMITATION = "paper.limitation"
KIND_CATEGORY = "category.positioning"


def stable_id(*parts: Any) -> str:
    payload = "|".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def build_paper_chunks(
    card: EvidenceCard,
    *,
    deep: dict[str, Any] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Split one evidence card into retrievable units.

    `deep` optionally overrides problem/method/findings/innovations/limitations
    with the back-filled deep-analysis result.
    """
    problem = card.problem
    method = card.method
    findings = list(card.findings)
    innovations = [item.model_dump() for item in card.innovations]
    limitations = list(card.limitations)

    if deep:
        problem = deep.get("problem") or problem
        method = deep.get("method") or method
        findings = deep.get("findings") or findings
        innovations = deep.get("innovations") or innovations
        limitations = deep.get("limitations") or limitations

    label = card.title_zh or card.title
    pieces: list[tuple[str, str, int | None, dict[str, Any]]] = []

    thesis = card.thesis_zh or card.thesis_en
    if thesis:
        pieces.append(
            (KIND_THESIS, f"【核心论点】{label}：{thesis}", None, {})
        )
    novelty = card.novelty_zh or card.novelty_en
    if novelty:
        pieces.append(
            (KIND_NOVELTY, f"【创新点】{label}：{novelty}", None, {})
        )
    if card.thesis_en and card.thesis_zh:
        pieces.append(
            (KIND_THESIS, f"[Thesis EN] {card.title}: {card.thesis_en}", None, {"lang": "en"})
        )
    if problem:
        pieces.append((KIND_PROBLEM, f"【研究问题】{label}：{problem}", None, {}))
    if method:
        pieces.append((KIND_METHOD, f"【核心方法】{label}：{method}", None, {}))

    for index, finding in enumerate(findings):
        if finding:
            pieces.append(
                (KIND_FINDING, f"【主要发现】{label}：{finding}", None, {"index": index})
            )

    for index, item in enumerate(innovations):
        claim = str(item.get("claim") or "").strip() if isinstance(item, dict) else str(item)
        if not claim:
            continue
        pages = [
            page
            for page in (item.get("evidence_pages") or [] if isinstance(item, dict) else [])
            if isinstance(page, int)
        ]
        quotes = [
            str(quote).strip()
            for quote in (item.get("evidence_quotes") or [] if isinstance(item, dict) else [])
            if str(quote).strip()
        ]
        page = pages[0] if pages else None
        suffix = ""
        if quotes:
            suffix = f"（原文：{quotes[0][:200]}）"
        if pages:
            suffix += f" [PAGE {pages[0]}]"
        pieces.append(
            (
                KIND_INNOVATION,
                f"【创新点 {index + 1}】{label}：{claim}{suffix}",
                page,
                {"index": index, "evidence_pages": pages},
            )
        )

    for index, limitation in enumerate(limitations):
        if limitation:
            pieces.append(
                (
                    KIND_LIMITATION,
                    f"【局限】{label}：{limitation}",
                    None,
                    {"index": index},
                )
            )

    chunks: list[tuple[str, dict[str, Any]]] = []
    for ordinal, (kind, text, page, extra) in enumerate(pieces):
        metadata = {"label": label, **extra}
        chunk_id = stable_id(card.paper_id, kind, ordinal, text[:80])
        chunks.append(
            (
                chunk_id,
                {
                    "paper_id": card.paper_id,
                    "category_id": card.category_id,
                    "kind": kind,
                    "ordinal": ordinal,
                    "text": text,
                    "page_number": page,
                    "metadata": metadata,
                },
            )
        )
    return chunks


def build_category_chunks(
    positioning: dict[str, str], category_names: dict[str, str]
) -> list[tuple[str, dict[str, Any]]]:
    chunks: list[tuple[str, dict[str, Any]]] = []
    for category_id, text in sorted(positioning.items()):
        if not text:
            continue
        name = category_names.get(category_id, category_id)
        payload = f"【主题定位】{name}（{category_id}）：{text}"
        chunks.append(
            (
                stable_id("category", category_id, payload[:80]),
                {
                    "paper_id": "",
                    "category_id": category_id,
                    "kind": KIND_CATEGORY,
                    "ordinal": 0,
                    "text": payload,
                    "page_number": None,
                    "metadata": {"label": name},
                },
            )
        )
    return chunks


TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    """Mixed CN/EN tokenizer: latin words, CJK unigrams and CJK bigrams.

    Bigrams matter because Chinese carries most of its meaning in two-character
    compounds, and trigram FTS5 alone misses the semantic side.
    """
    if not text:
        return []
    lowered = text.lower()
    tokens: list[str] = TOKEN_RE.findall(lowered)
    chars = [char for char in lowered if CJK_RE.match(char)]
    tokens.extend(chars)
    tokens.extend(a + b for a, b in zip(chars, chars[1:]))
    return tokens
