from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from .config import ResearchSettings
from .schemas import EvidenceCard


class CorpusError(RuntimeError):
    pass


CATEGORY_POSITIONING_RE = re.compile(r"^\*\*主题定位\*\*：(.+)$")
SECTION_RE = re.compile(r"^##\s+(\d{1,2})\.\s+")


def _connect_readonly(uri: str) -> sqlite3.Connection:
    """Read-only connection: SQLite itself rejects any write attempt."""
    connection = sqlite3.connect(uri, uri=True, timeout=15)
    connection.row_factory = sqlite3.Row
    return connection


class PaperLibraryReader:
    """Reads the reading platform's library without ever writing to it."""

    def __init__(self, settings: ResearchSettings) -> None:
        self.settings = settings

    def database_exists(self) -> bool:
        return self.settings.paper_database_path.is_file()

    def readable(self) -> bool:
        if not self.database_exists():
            return False
        try:
            with _connect_readonly(self.settings.paper_database_uri) as connection:
                connection.execute("SELECT COUNT(*) FROM papers").fetchone()
            return True
        except sqlite3.Error:
            return False

    def paper_columns(self) -> set[str]:
        with _connect_readonly(self.settings.paper_database_uri) as connection:
            rows = connection.execute("PRAGMA table_info(papers)").fetchall()
        return {row["name"] for row in rows}

    def load_cards(self) -> list[EvidenceCard]:
        if not self.readable():
            raise CorpusError(
                f"无法只读打开论文库：{self.settings.paper_database_path}。"
                "请确认阅读平台已生成 storage/api/library.sqlite3。"
            )

        columns = self.paper_columns()
        select_columns = [
            name
            for name in (
                "id",
                "title",
                "title_zh",
                "authors_json",
                "venue",
                "year",
                "category_id",
                "abstract",
                "tags_json",
                "page_count",
                "sha256",
                "file_path",
                "summary_json",
            )
            if name in columns
        ]
        query = f"SELECT {', '.join(select_columns)} FROM papers ORDER BY id"

        with _connect_readonly(self.settings.paper_database_uri) as connection:
            rows = connection.execute(query).fetchall()

        categories = _load_categories(self.settings)
        cards: list[EvidenceCard] = []
        for row in rows:
            card = _build_card(row, columns, categories)
            if card:
                cards.append(card)
        return cards


def _load_categories(settings: ResearchSettings) -> dict[str, str]:
    """Reuse the reading platform's category table (pure data, no side effects)."""
    from .interop import InteropError, load_reading_platform_module

    try:
        module = load_reading_platform_module(
            settings.reading_platform_app, "categories"
        )
    except InteropError:
        return {}
    return {
        category.id: category.name_zh for category in getattr(module, "CATEGORIES", ())
    }


def _build_card(
    row: sqlite3.Row,
    columns: set[str],
    categories: dict[str, str],
) -> EvidenceCard | None:
    data: dict[str, Any] = dict(row)
    paper_id = str(data.get("id") or "").strip()
    if not paper_id:
        return None

    summary = _parse_json(data.get("summary_json") or "{}", {})
    authors = _parse_json(data.get("authors_json") or "[]", [])
    category_id = str(data.get("category_id") or "").strip()

    innovations = []
    for item in summary.get("innovations") or []:
        if isinstance(item, dict) and str(item.get("claim") or "").strip():
            innovations.append(
                {
                    "claim": str(item.get("claim")).strip(),
                    "evidence_pages": [
                        page
                        for page in (item.get("evidence_pages") or [])
                        if isinstance(page, int)
                    ],
                    "evidence_quotes": [
                        str(quote).strip()
                        for quote in (item.get("evidence_quotes") or [])
                        if str(quote).strip()
                    ],
                }
            )
        elif isinstance(item, str) and item.strip():
            innovations.append(
                {"claim": item.strip(), "evidence_pages": [], "evidence_quotes": []}
            )

    findings = _string_list(summary.get("findings"))
    limitations = _string_list(summary.get("limitations"))
    problem = str(summary.get("problem") or "").strip()
    method = str(summary.get("method") or "").strip()

    pdf_path = str(data.get("file_path") or "").strip()
    page_count = _as_int(data.get("page_count"))

    thesis_zh = str(summary.get("thesis_zh") or "").strip()
    novelty_zh = str(summary.get("novelty_zh") or "").strip()
    thesis_en = str(summary.get("thesis_en") or "").strip()
    novelty_en = str(summary.get("novelty_en") or "").strip()

    has_deep_fields = bool(innovations or findings or problem or method)
    fingerprint = _fingerprint(
        paper_id,
        thesis_zh,
        novelty_zh,
        thesis_en,
        novelty_en,
        problem,
        method,
        findings,
        innovations,
        limitations,
        category_id,
        pdf_path,
        page_count,
    )

    return EvidenceCard(
        paper_id=paper_id,
        title=str(data.get("title") or "Untitled").strip(),
        title_zh=str(data.get("title_zh") or "").strip(),
        authors=[str(author) for author in authors] if isinstance(authors, list) else [],
        venue=str(data.get("venue") or "").strip(),
        year=_as_int(data.get("year")),
        category_id=category_id,
        category_name=categories.get(category_id, ""),
        thesis_zh=thesis_zh,
        novelty_zh=novelty_zh,
        thesis_en=thesis_en,
        novelty_en=novelty_en,
        problem=problem,
        method=method,
        findings=findings,
        innovations=[_to_innovation_model(item) for item in innovations],
        limitations=limitations,
        pdf_path=pdf_path,
        page_count=page_count,
        sha256=str(data.get("sha256") or "").strip(),
        fingerprint=fingerprint,
        deep_analysis_status="missing" if not has_deep_fields else "ready",
        needs_deep_analysis=not has_deep_fields,
    )


def _to_innovation_model(item: dict[str, Any]) -> Any:
    from .schemas import Innovation

    return Innovation(
        claim=item["claim"],
        evidence_pages=item.get("evidence_pages", []),
        evidence_quotes=item.get("evidence_quotes", []),
    )


def _parse_json(raw: str, fallback: Any) -> Any:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return fallback
    return parsed if parsed is not None else fallback


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _fingerprint(*parts: Any) -> str:
    payload = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def resolve_pdf_path(path: str, paper_root: Path) -> Path | None:
    """Resolve a stored PDF path, refusing anything outside the paper repository."""
    if not path:
        return None
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = (paper_root / candidate).resolve()
    else:
        candidate = candidate.resolve()
    try:
        candidate.relative_to(paper_root.resolve())
    except ValueError:
        return None
    if candidate.is_file() and candidate.suffix.lower() == ".pdf":
        return candidate
    return None


def pdf_is_readable(path: str, paper_root: Path) -> bool:
    """True only when the PDF exists and stays inside the paper repository."""
    return resolve_pdf_path(path, paper_root) is not None


def load_category_positioning(knowledge_base_path: Path) -> dict[str, str]:
    """Extract the per-category '主题定位' paragraph from KNOWLEDGE_BASE.md.

    Returns {category_id: positioning}. Used to give the model corpus-level
    context that no single paper carries. Read-only.
    """
    if not knowledge_base_path.is_file():
        return {}
    try:
        text = knowledge_base_path.read_text(encoding="utf-8")
    except OSError:
        return {}

    positions: dict[str, str] = {}
    current_index = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        section = SECTION_RE.match(line)
        if section:
            current_index = int(section.group(1))
            continue
        if line.startswith("## "):
            current_index = 0
            continue
        match = CATEGORY_POSITIONING_RE.match(line)
        if match and 1 <= current_index <= 99 and current_index not in positions:
            positions[current_index] = re.sub(r"\s+", " ", match.group(1)).strip()
    return {f"cat-{index:02d}": text for index, text in positions.items()}
