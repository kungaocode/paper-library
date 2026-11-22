"""Stage B: read-only corpus ingestion.

The single most important property of this service is that the reading
platform's database is never written. These tests assert that from both sides:
the connection is opened read-only, and the file digest does not change.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from app import interop
from app.config import ResearchSettings
from app.corpus import (
    CorpusError,
    PaperLibraryReader,
    load_category_positioning,
    pdf_is_readable,
    resolve_pdf_path,
)

from conftest import PAPERS, make_settings


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_paper_database_is_opened_read_only(settings: ResearchSettings) -> None:
    assert settings.paper_database_uri.endswith("?mode=ro")
    connection = sqlite3.connect(settings.paper_database_uri, uri=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("INSERT INTO papers (id) VALUES ('paper-evil')")
    finally:
        connection.close()


def test_load_cards_reads_all_fields(settings: ResearchSettings) -> None:
    library = settings.paper_database_path
    before = _digest(library)

    cards = PaperLibraryReader(settings).load_cards()

    assert _digest(library) == before, "只读读取不应改动论文库文件"
    assert {card.paper_id for card in cards} == {paper["id"] for paper in PAPERS}

    by_id = {card.paper_id: card for card in cards}
    first = by_id["paper-aaa111000000"]
    assert first.title.startswith("Fine-Grained Alignment")
    assert first.authors == ["Wei Chen", "Lin Zhao"]
    assert first.venue == "NeurIPS"
    assert first.year == 2024
    assert first.category_id == "cat-01"
    # Category names come from the reading platform's own table (interop).
    assert first.category_name
    assert first.page_count == 12
    assert first.problem
    assert first.method
    assert first.findings
    assert first.innovations[0].claim
    assert first.innovations[0].evidence_pages == [3]
    assert first.limitations == ["依赖标注器质量"]
    # summary_json already carries innovations, so no backfill is required.
    assert first.needs_deep_analysis is False
    assert first.deep_analysis_status == "ready"


def test_missing_library_raises_corpus_error(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, tmp_path / "research")
    reader = PaperLibraryReader(settings)
    assert reader.database_exists() is False
    assert reader.readable() is False
    with pytest.raises(CorpusError):
        reader.load_cards()


def test_missing_columns_degrade_gracefully(tmp_path: Path) -> None:
    """An older reading-platform schema must not break ingestion."""
    db_path = tmp_path / "storage" / "api" / "library.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("CREATE TABLE papers (id TEXT PRIMARY KEY, title TEXT)")
        connection.execute("INSERT INTO papers VALUES ('paper-legacy01', 'Legacy Paper')")
        connection.commit()
    finally:
        connection.close()

    settings = make_settings(tmp_path, tmp_path / "research")
    cards = PaperLibraryReader(settings).load_cards()

    assert len(cards) == 1
    card = cards[0]
    assert card.paper_id == "paper-legacy01"
    assert card.title == "Legacy Paper"
    assert card.page_count == 0
    assert card.findings == []
    assert card.needs_deep_analysis is True


def test_rows_without_id_are_skipped(tmp_path: Path) -> None:
    db_path = tmp_path / "storage" / "api" / "library.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("CREATE TABLE papers (id TEXT, title TEXT)")
        connection.execute("INSERT INTO papers VALUES ('', 'no id')")
        connection.execute("INSERT INTO papers VALUES (NULL, 'null id')")
        connection.execute("INSERT INTO papers VALUES ('paper-ok0001', 'kept')")
        connection.commit()
    finally:
        connection.close()

    cards = PaperLibraryReader(make_settings(tmp_path, tmp_path / "research")).load_cards()
    assert [card.paper_id for card in cards] == ["paper-ok0001"]


def test_pdf_path_resolution_refuses_escape(settings: ResearchSettings) -> None:
    root = settings.paper_root
    assert resolve_pdf_path(f"papers/{PAPERS[0]['id']}.pdf", root) is not None
    assert pdf_is_readable(f"papers/{PAPERS[0]['id']}.pdf", root) is True

    for hostile in (
        "",
        "../outside.pdf",
        "papers/../../etc/passwd",
        "/etc/passwd",
        str(root.parent / "escape.pdf"),
        "papers/missing.pdf",
        "KNOWLEDGE_BASE.md",
    ):
        assert resolve_pdf_path(hostile, root) is None, hostile
        assert pdf_is_readable(hostile, root) is False, hostile


def test_category_positioning_is_parsed_from_knowledge_base(
    settings: ResearchSettings,
) -> None:
    positioning = load_category_positioning(settings.knowledge_base_path)
    assert set(positioning) == {"cat-01", "cat-02", "cat-04"}
    assert "训练期安全约束" in positioning["cat-01"]
    assert load_category_positioning(settings.paper_root / "nope.md") == {}


def test_interop_refuses_unsafe_reading_platform_modules(
    settings: ResearchSettings,
) -> None:
    api_root = settings.reading_platform_app
    assert settings.reading_platform_available() is True

    for name in ("config", "main", "pipeline", "store", "model_provider"):
        with pytest.raises(interop.InteropError):
            interop.load_reading_platform_module(api_root, name)

    categories = interop.load_reading_platform_module(api_root, "categories")
    assert any(item.id == "cat-01" for item in categories.CATEGORIES)
    # Repeated loads are cached and identical.
    assert interop.load_reading_platform_module(api_root, "categories") is categories


def test_interop_reports_missing_platform(tmp_path: Path) -> None:
    # `paper_atlas` may already be mounted by an earlier test in this process.
    interop.clear_cache()
    try:
        with pytest.raises(interop.InteropError):
            interop.load_reading_platform_module(tmp_path / "nope", "pdf_utils")
    finally:
        interop.clear_cache()


def test_interop_does_not_leak_reading_platform_env(settings: ResearchSettings) -> None:
    """Importing their modules must not run their config/.env loader."""
    import os

    before = dict(os.environ)
    PaperLibraryReader(settings).load_cards()
    assert dict(os.environ) == before
