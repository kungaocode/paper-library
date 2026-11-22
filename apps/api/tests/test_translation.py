from __future__ import annotations

import asyncio
import shutil
from datetime import date
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.config import Settings
from app.main import create_app
from app.model_provider import (
    ModelProvider,
    ModelProviderError,
    OpenAICompatibleProvider,
)
from app.pipeline import (
    TRANSLATION_CHUNK_CHARS,
    TRANSLATION_MAX_PAGES_PER_CHUNK,
    build_translation_chunks,
)
from app.schemas import PaperRecord, PaperSummary, utc_now
from app.store import LibraryStore


ROOT = Path(__file__).resolve().parents[3]
PDFS = sorted((ROOT / "completed").rglob("*.pdf"), key=lambda path: path.stat().st_size)
SAMPLE_PDF = PDFS[0] if PDFS else None


def build_settings(tmp_path: Path) -> Settings:
    return Settings(
        paper_root=tmp_path,
        storage_dir=tmp_path / "storage" / "api",
        llm_provider="mock",
        llm_base_url="",
        llm_api_key="",
        llm_model="mock",
        llm_timeout_seconds=10,
        llm_max_output_tokens=2000,
        llm_json_mode=True,
        allow_private_urls=False,
        max_download_mb=20,
        max_text_chars=30000,
        analysis_page_limit=8,
    )


def test_translation_chunks_keep_requests_small_and_page_scoped() -> None:
    pages = [
        "A" * 4800,
        "B" * (TRANSLATION_CHUNK_CHARS + 100),
    ]

    chunks = build_translation_chunks(
        pages,
        max_chars=TRANSLATION_CHUNK_CHARS,
        max_pages=TRANSLATION_MAX_PAGES_PER_CHUNK,
    )

    assert [chunk["pages"][0] for chunk in chunks] == [1, 2, 2]
    assert all(len(set(chunk["pages"])) == 1 for chunk in chunks)
    assert max(len(chunk["text"]) for chunk in chunks) <= TRANSLATION_CHUNK_CHARS + 16


def test_model_timeout_message_includes_limit_and_reason(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = build_settings(tmp_path)
    provider = OpenAICompatibleProvider(settings)

    async def fake_post(*_: object, **__: object) -> httpx.Response:
        raise httpx.ReadTimeout("upstream stalled")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with pytest.raises(ModelProviderError) as captured:
        asyncio.run(
            provider.generate_text(
                system_prompt="translate",
                user_prompt="text",
                purpose="translation",
            )
        )

    message = str(captured.value)
    assert "10 秒" in message
    assert "upstream stalled" in message


def prepare_paper(
    settings: Settings,
    *,
    translation_path: str = "",
    translation_status: str = "not_started",
) -> tuple[LibraryStore, PaperRecord]:
    if SAMPLE_PDF is None:
        raise RuntimeError("No PDF fixture is available under completed/.")

    settings.ensure_directories()
    pdf_dir = settings.completed_dir / "01_test"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / "translation-test.pdf"
    shutil.copy2(SAMPLE_PDF, pdf_path)
    page_count = len(PdfReader(str(pdf_path)).pages)

    paper = PaperRecord(
        id="paper-translation-test",
        title="Translation Test Paper",
        authors=["Paper Atlas"],
        venue="Local test",
        year=2026,
        abstract="",
        category_id="cat-05",
        status="ready",
        reading_status="unread",
        source="manual",
        confidence=1.0,
        updated_at=date.today().isoformat(),
        page_count=page_count,
        summary=PaperSummary(problem="", method=""),
        file_path=str(pdf_path),
        file_url="/api/papers/paper-translation-test/file",
        created_at=utc_now(),
        translation_path=translation_path,
        translation_status=translation_status,
    )
    store = LibraryStore(settings.database_path)
    store.save_paper(paper)
    return store, paper


def test_translation_endpoint_writes_displayable_downloadable_markdown(
    tmp_path: Path,
) -> None:
    if SAMPLE_PDF is None:
        import pytest

        pytest.skip("No PDF fixture is available under completed/.")

    settings = build_settings(tmp_path)
    store, paper = prepare_paper(settings)
    app = create_app(settings)

    with TestClient(app) as client:
        start_response = client.post(f"/api/papers/{paper.id}/translation")
        assert start_response.status_code == 202
        assert start_response.json()["status"] in {"queued", "running", "ready"}

        translation_response = client.get(
            f"/api/papers/{paper.id}/translation"
        )
        assert translation_response.status_code == 200
        payload = translation_response.json()
        assert payload["status"] == "ready"
        assert payload["model"] == "mock"
        assert payload["progress"] == 100
        assert payload["completed_pages"] == paper.page_count
        assert "离线中文译文" in payload["text"]
        assert payload["download_url"] == (
            f"/api/papers/{paper.id}/translation/file"
        )

        translation_files = list(settings.translation_dir.glob("*.md"))
        assert len(translation_files) == 1
        assert not list(settings.translation_dir.glob("*.part"))
        assert "Translation Test Paper" in translation_files[0].read_text(
            encoding="utf-8"
        )

        file_response = client.get(
            f"/api/papers/{paper.id}/translation/file"
        )
        assert file_response.status_code == 200
        assert "text/markdown" in file_response.headers["content-type"]
        assert "attachment" in file_response.headers["content-disposition"]
        assert "离线中文译文" in file_response.content.decode("utf-8")

    stored = store.get_paper(paper.id)
    assert stored is not None
    assert stored.translation_status == "ready"
    assert stored.translation_path == str(translation_files[0])


def test_translation_failure_is_persisted_without_partial_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    if SAMPLE_PDF is None:
        import pytest

        pytest.skip("No PDF fixture is available under completed/.")

    class FailingProvider(ModelProvider):
        async def generate_json(self, **_: object) -> dict[str, object]:
            raise ModelProviderError("unexpected JSON request")

        async def generate_text(self, **_: object) -> str:
            raise ModelProviderError("translation provider failed")

        async def test_connection(self) -> str:
            return "failed"

    settings = build_settings(tmp_path)
    store, paper = prepare_paper(settings)
    monkeypatch.setattr(
        "app.pipeline.build_provider",
        lambda _: FailingProvider(),
    )
    app = create_app(settings)

    with TestClient(app) as client:
        assert client.post(f"/api/papers/{paper.id}/translation").status_code == 202
        payload = client.get(f"/api/papers/{paper.id}/translation").json()
        assert payload["status"] == "failed"
        assert "translation provider failed" in payload["error"]
        assert payload["text"] is None

    stored = store.get_paper(paper.id)
    assert stored is not None
    assert stored.translation_status == "failed"
    assert stored.translation_path == ""
    assert not list(settings.translation_dir.glob("*.md"))
    assert not list(settings.translation_dir.glob("*.part"))


def test_translation_path_outside_translate_directory_is_rejected(
    tmp_path: Path,
) -> None:
    if SAMPLE_PDF is None:
        import pytest

        pytest.skip("No PDF fixture is available under completed/.")

    settings = build_settings(tmp_path)
    outside_file = tmp_path / "outside.md"
    outside_file.write_text("not allowed", encoding="utf-8")
    store, paper = prepare_paper(
        settings,
        translation_path=str(outside_file),
        translation_status="ready",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get(f"/api/papers/{paper.id}/translation")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "failed"
        assert payload["text"] is None
        assert "译文路径不合法" in payload["error"]
        assert client.get(
            f"/api/papers/{paper.id}/translation/file"
        ).status_code == 403

    stored = store.get_paper(paper.id)
    assert stored is not None
    assert stored.translation_status == "ready"
