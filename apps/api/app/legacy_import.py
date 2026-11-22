from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import unquote

from pypdf import PdfReader

from .pdf_utils import format_file_size, sha256_file
from .schemas import PaperRecord, PaperSummary, utc_now
from .store import LibraryStore


SECTION_RE = re.compile(r"^##\s+(\d{1,2})\.\s+")
ENTRY_RE = re.compile(r"^###\s+(.+?)\s*$")
PDF_RE = re.compile(r"\*\*PDF\*\*：\[[^\]]*\]\(<([^>]+)>\)")
ZH_THESIS_RE = re.compile(r"-\s*\*\*核心论点（中）\*\*：(.+)")
ZH_NOVELTY_RE = re.compile(r"-\s*\*\*创新点（中）\*\*：(.+)")
EN_THESIS_RE = re.compile(r"-\s*\*\*Core thesis \(EN\)\*\*:\s*(.+)")
EN_NOVELTY_RE = re.compile(r"-\s*\*\*Novelty \(EN\)\*\*:\s*(.+)")
OPEN_BRACKETS = {"（": "）", "(": ")"}
CLOSE_BRACKETS = {value: key for key, value in OPEN_BRACKETS.items()}
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


@dataclass
class LegacyEntry:
    category_index: int
    heading: str
    pdf_path: Path
    pdf_raw: str = ""
    thesis_zh: str = ""
    novelty_zh: str = ""
    thesis_en: str = ""
    novelty_en: str = ""


def parse_knowledge_base(path: Path) -> list[LegacyEntry]:
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    entries: list[LegacyEntry] = []
    current: LegacyEntry | None = None
    want_pdf = False
    category_index = 0

    def flush() -> None:
        nonlocal current
        if current is not None and current.pdf_raw:
            entries.append(current)
        current = None

    for raw_line in text.splitlines():
        line = raw_line.strip()

        section = SECTION_RE.match(line)
        if section:
            flush()
            category_index = int(section.group(1))
            continue
        if line.startswith("## "):
            flush()
            continue

        heading = ENTRY_RE.match(line)
        if heading:
            flush()
            current = LegacyEntry(
                category_index=category_index,
                heading=heading.group(1).strip(),
                pdf_path=Path(),
            )
            want_pdf = True
            continue

        if current is None:
            continue

        if want_pdf and not current.pdf_raw:
            if not line:
                continue
            pdf_match = PDF_RE.search(line)
            if pdf_match:
                # Markdown link targets percent-encode characters like apostrophes.
                current.pdf_raw = unquote(pdf_match.group(1).strip())
                current.pdf_path = Path(current.pdf_raw).expanduser()
                want_pdf = False
                continue
            # The heading has no PDF line; stop waiting and keep scanning fields.
            want_pdf = False

        if not current.thesis_zh:
            match = ZH_THESIS_RE.match(line)
            if match:
                current.thesis_zh = single_line(match.group(1))
                continue
        if not current.novelty_zh:
            match = ZH_NOVELTY_RE.match(line)
            if match:
                current.novelty_zh = single_line(match.group(1))
                continue
        if not current.thesis_en:
            match = EN_THESIS_RE.match(line)
            if match:
                current.thesis_en = single_line(match.group(1))
                continue
        if not current.novelty_en:
            match = EN_NOVELTY_RE.match(line)
            if match:
                current.novelty_en = single_line(match.group(1))
                continue

    flush()

    return entries


def split_title_and_metadata(heading: str) -> tuple[str, str]:
    text = heading.strip()
    if not text or text[-1] not in CLOSE_BRACKETS:
        return text, ""

    depth = 0
    start = -1
    for index in range(len(text) - 1, -1, -1):
        char = text[index]
        if char in CLOSE_BRACKETS:
            depth += 1
        elif char in OPEN_BRACKETS:
            depth -= 1
            if depth == 0:
                start = index
                break
    if start <= 0:
        return text, ""

    metadata = text[start + 1 : -1].strip()
    title = text[:start].strip(" \u3000")
    if not metadata or not title:
        return text, ""
    return title, metadata


def parse_authors(metadata: str) -> list[str]:
    if not metadata:
        return []
    first = re.split(r"[,，]", metadata, maxsplit=1)[0].strip()
    first = re.sub(r"\s+et al\.?$", "", first, flags=re.IGNORECASE).strip()
    return [first] if first else []


def parse_year(metadata: str) -> int:
    match = YEAR_RE.search(metadata)
    return int(match.group(0)) if match else 0


def parse_venue(metadata: str) -> str:
    if not metadata:
        return ""
    without_year = YEAR_RE.sub("", metadata)
    parts = [
        part.strip(" ,")
        for part in re.split(r"[,，]", without_year)
        if part.strip(" ,")
    ]
    if not parts:
        return ""
    for candidate in reversed(parts):
        cleaned = re.sub(
            r"^(et al\.?|and|\u7b49)\s+", "", candidate, flags=re.IGNORECASE
        ).strip(" ,")
        if cleaned and cleaned.lower() not in {"et al", "et al.", "and", "\u7b49"}:
            return cleaned
    return ""


def single_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def stable_paper_id(source_path: Path) -> str:
    digest = hashlib.sha1(str(source_path).encode("utf-8")).hexdigest()
    return f"paper-{digest[:12]}"


def build_paper(
    *,
    entry: LegacyEntry,
    paper_root: Path,
) -> PaperRecord | None:
    if entry.category_index < 1 or entry.category_index > 12:
        return None

    source_path = entry.pdf_path
    if not source_path.is_absolute():
        source_path = (paper_root / source_path).resolve()
    else:
        source_path = source_path.resolve()
    if not source_path.exists() or source_path.suffix.lower() != ".pdf":
        return None

    title, metadata = split_title_and_metadata(entry.heading)
    paper_id = stable_paper_id(source_path)
    digest = sha256_file(source_path)
    size_bytes = source_path.stat().st_size

    try:
        page_count = len(PdfReader(str(source_path)).pages)
    except Exception:
        page_count = 0

    summary = PaperSummary(
        problem="",
        method="",
        findings=[],
        innovations=[],
        limitations=[],
        thesis_zh=entry.thesis_zh,
        novelty_zh=entry.novelty_zh,
        thesis_en=entry.thesis_en,
        novelty_en=entry.novelty_en,
    )

    return PaperRecord(
        id=paper_id,
        title=title,
        title_zh="",
        authors=parse_authors(metadata),
        venue=parse_venue(metadata),
        year=parse_year(metadata),
        abstract="",
        category_id=f"cat-{entry.category_index:02d}",
        status="ready",
        reading_status="unread",
        source="migration",
        confidence=1.0,
        updated_at=date.today().isoformat(),
        file_size=format_file_size(size_bytes),
        page_count=page_count,
        tags=[],
        candidate_categories=[],
        summary=summary,
        file_path=str(source_path),
        file_url=f"/api/papers/{paper_id}/file",
        original_url="",
        sha256=digest,
        created_at=utc_now(),
        ai_rationale="来源：KNOWLEDGE_BASE.md 人工整理的核心论点与创新点。",
    )


def migrate_legacy_library(
    *,
    store: LibraryStore,
    paper_root: Path,
    knowledge_base_path: Path,
) -> dict[str, int]:
    entries = parse_knowledge_base(knowledge_base_path)
    stats = {"parsed": len(entries), "imported": 0, "skipped": 0, "missing": 0}

    for entry in entries:
        paper = build_paper(entry=entry, paper_root=paper_root)
        if paper is None:
            stats["missing"] += 1
            continue
        existing = store.get_paper_by_sha256(paper.sha256)
        if existing is not None:
            stats["skipped"] += 1
            continue
        store.save_paper(paper)
        stats["imported"] += 1

    return stats
