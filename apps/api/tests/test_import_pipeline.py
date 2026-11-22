from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

from app.config import Settings
from app.legacy_import import migrate_legacy_library
from app.main import create_app
from app.pipeline import PaperImportPipeline
from app.schemas import JobRecord, utc_now
from app.store import LibraryStore


ROOT = Path(__file__).resolve().parents[3]
SAMPLE_PDF = next(iter(sorted((ROOT / "completed").rglob("*.pdf"))), None)


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


def prepare_library(tmp_path: Path) -> tuple[Settings, Path]:
    if SAMPLE_PDF is None:
        pytest.skip("No PDF fixture is available under completed/.")
    settings = build_settings(tmp_path)
    settings.ensure_directories()
    shutil.copy2(ROOT / "KNOWLEDGE_BASE.md", settings.knowledge_base_path)
    staged_pdf = settings.need_organization_dir / "pipeline-test.pdf"
    shutil.copy2(SAMPLE_PDF, staged_pdf)
    return settings, staged_pdf


def write_derivative_pdf(source: Path, destination: Path) -> None:
    """Append a blank page so the upload has a distinct SHA-256 from the sample."""
    writer = PdfWriter()
    for page in PdfReader(str(source)).pages:
        writer.add_page(page)
    writer.add_blank_page(
        width=float(writer.pages[0].mediabox.width),
        height=float(writer.pages[0].mediabox.height),
    )
    with destination.open("wb") as handle:
        writer.write(handle)


def test_mock_pipeline_writes_knowledge_base_and_store(tmp_path: Path) -> None:
    settings, staged_pdf = prepare_library(tmp_path)
    store = LibraryStore(settings.database_path)
    pipeline = PaperImportPipeline(settings, store)
    timestamp = utc_now()
    job = JobRecord(
        id="job-pipeline-test",
        paper_title="Pending import",
        status="queued",
        progress=0,
        message="queued",
        stage="queued",
        updated_at=timestamp,
        created_at=timestamp,
    )
    store.save_job(job)

    asyncio.run(pipeline.run_local_import(job.id, str(staged_pdf)))

    stored_job = store.get_job(job.id)
    assert stored_job is not None
    assert stored_job.status == "succeeded"
    assert not staged_pdf.exists()

    completed_pdfs = list((settings.paper_root / "completed").rglob("*.pdf"))
    assert len(completed_pdfs) == 1

    knowledge_base = settings.knowledge_base_path.read_text(encoding="utf-8")
    assert "Imported Paper: Safety Evaluation Pipeline" in knowledge_base
    assert "核心论点（中）" in knowledge_base
    assert "Novelty (EN)" in knowledge_base

    papers = store.list_papers()
    assert len(papers) == 1
    assert papers[0].category_id == "cat-05"
    assert papers[0].file_url == f"/api/papers/{papers[0].id}/file"


def test_mock_pipeline_persists_phase_progress(tmp_path: Path) -> None:
    settings, staged_pdf = prepare_library(tmp_path)
    store = LibraryStore(settings.database_path)
    pipeline = PaperImportPipeline(settings, store)
    timestamp = utc_now()
    job = JobRecord(
        id="job-phase-test",
        paper_title="Pending import",
        status="queued",
        progress=0,
        message="queued",
        stage="queued",
        updated_at=timestamp,
        created_at=timestamp,
    )
    store.save_job(job)

    asyncio.run(pipeline.run_local_import(job.id, str(staged_pdf)))

    stored_job = store.get_job(job.id)
    assert stored_job is not None
    assert stored_job.status == "succeeded"
    assert stored_job.result is not None
    # Final successful task must report the terminal phase, not an intermediate one.
    assert stored_job.result.phase == "completed"
    assert stored_job.result.classification is not None
    assert stored_job.result.analysis is not None
    assert stored_job.result.category_id == "cat-05"
    assert stored_job.result.destination


def test_knowledge_base_migration_is_idempotent(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    settings.ensure_directories()
    shutil.copy2(ROOT / "KNOWLEDGE_BASE.md", settings.knowledge_base_path)
    store = LibraryStore(settings.database_path)

    first = migrate_legacy_library(
        store=store,
        paper_root=ROOT,
        knowledge_base_path=settings.knowledge_base_path,
    )
    assert first["parsed"] == 67
    assert first["imported"] == 67
    assert first["missing"] == 0
    assert len(store.list_papers(limit=500)) == 67

    second = migrate_legacy_library(
        store=store,
        paper_root=ROOT,
        knowledge_base_path=settings.knowledge_base_path,
    )
    assert second["imported"] == 0
    assert second["skipped"] == first["imported"]
    assert len(store.list_papers(limit=500)) == 67


def test_upload_endpoint_runs_background_pipeline(tmp_path: Path) -> None:
    settings, _ = prepare_library(tmp_path)
    app = create_app(settings)
    upload_pdf = tmp_path / "upload-test.pdf"
    write_derivative_pdf(SAMPLE_PDF, upload_pdf)

    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        model_status = client.get("/api/settings/models").json()
        assert model_status["configured"] is True
        assert model_status["provider"] == "mock"
        model_test = client.post("/api/settings/models/test")
        assert model_test.status_code == 200
        assert model_test.json()["ok"] is True
        assert model_test.json()["provider"] == "mock"

        with upload_pdf.open("rb") as handle:
            response = client.post(
                "/api/imports/file",
                files={"file": ("upload-test.pdf", handle, "application/pdf")},
            )
        assert response.status_code == 202
        job_id = response.json()["id"]
        job = client.get(f"/api/jobs/{job_id}").json()
        assert job["status"] == "succeeded"
        assert job["result"]["phase"] == "completed"
        uploaded_paper_id = job["paper_id"]
        assert uploaded_paper_id

        papers = client.get("/api/papers").json()
        # Lifespan migrates the 67 legacy entries from KNOWLEDGE_BASE.md, so the
        # uploaded paper is located by id instead of assuming an empty library.
        paper = next(item for item in papers if item["id"] == uploaded_paper_id)
        assert paper["title"] == "Imported Paper: Safety Evaluation Pipeline"
        assert paper["candidate_categories"]

        file_response = client.get(f"/api/papers/{paper['id']}/file")
        assert file_response.status_code == 200
        assert file_response.headers["content-type"] == "application/pdf"
        assert file_response.content.startswith(b"%PDF-")
