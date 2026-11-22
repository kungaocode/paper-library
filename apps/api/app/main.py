from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from .auth import (
    SESSION_COOKIE_NAME,
    create_session_token,
    verify_credentials,
    verify_session_token,
)
from .categories import CATEGORIES
from .config import Settings
from .downloader import DownloadError, safe_filename
from .legacy_import import migrate_legacy_library
from .model_provider import build_provider
from .pipeline import PaperImportPipeline
from .schemas import (
    AuthStatus,
    ImportUrlRequest,
    JobRecord,
    LoginRequest,
    ModelConnectionTest,
    ModelStatus,
    PaperRecord,
    utc_now,
)
from .store import LibraryStore


def translation_file_path(settings: Settings, paper: PaperRecord) -> Path | None:
    if not paper.translation_path:
        return None
    path = Path(paper.translation_path).resolve()
    try:
        path.relative_to(settings.translation_dir.resolve())
    except ValueError as error:
        raise HTTPException(status_code=403, detail="译文路径不合法") from error
    if not path.is_file() or path.suffix.lower() != ".md":
        return None
    return path


def translation_payload(
    settings: Settings,
    paper: PaperRecord,
    *,
    include_text: bool = True,
) -> dict[str, object]:
    status = paper.translation_status
    error = paper.translation_error
    path: Path | None = None
    try:
        path = translation_file_path(settings, paper)
    except HTTPException as exception:
        status = "failed"
        error = str(exception.detail)

    if status == "ready" and path is None:
        status = "failed"
        error = "译文文件不存在，请重新翻译。"

    text = None
    if include_text and status == "ready" and path is not None:
        text = path.read_text(encoding="utf-8")

    return {
        "paper_id": paper.id,
        "status": status,
        "progress": paper.translation_progress,
        "page_count": paper.translation_page_count or paper.page_count,
        "completed_pages": paper.translation_completed_pages,
        "text": text,
        "error": error,
        "model": paper.translation_model or settings.llm_model,
        "updated_at": paper.translation_updated_at,
        "download_url": (
            f"/api/papers/{paper.id}/translation/file"
            if status == "ready" and path is not None
            else ""
        ),
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings.from_env()
    app_settings.ensure_directories()
    store = LibraryStore(app_settings.database_path)
    pipeline = PaperImportPipeline(app_settings, store)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        store.mark_interrupted_jobs()
        if not store.list_papers(limit=1):
            migrate_legacy_library(
                store=store,
                paper_root=app_settings.paper_root,
                knowledge_base_path=app_settings.knowledge_base_path,
            )
        yield

    app = FastAPI(
        title="Paper Atlas API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.store = store
    app.state.pipeline = pipeline

    @app.middleware("http")
    async def require_authentication(request: Request, call_next):
        path = request.url.path
        is_public_auth_route = path.startswith("/api/auth/")
        is_protected_api = path.startswith("/api/") and not is_public_auth_route
        if (
            app_settings.auth_enabled
            and is_protected_api
            and request.method != "OPTIONS"
            and not verify_session_token(
                app_settings,
                request.cookies.get(SESSION_COOKIE_NAME),
            )
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "请先登录"},
                headers={"WWW-Authenticate": "Cookie"},
            )
        return await call_next(request)

    # Add CORS last so it wraps authentication errors as well as normal responses.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/auth/status", response_model=AuthStatus)
    async def auth_status(request: Request) -> AuthStatus:
        authenticated = not app_settings.auth_enabled or verify_session_token(
            app_settings,
            request.cookies.get(SESSION_COOKIE_NAME),
        )
        return AuthStatus(
            auth_enabled=app_settings.auth_enabled,
            authenticated=authenticated,
            username=app_settings.auth_username if authenticated else "",
        )

    @app.post("/api/auth/login", response_model=AuthStatus)
    async def login(payload: LoginRequest) -> Response:
        if app_settings.auth_enabled and not verify_credentials(
            app_settings,
            payload.username,
            payload.password,
        ):
            raise HTTPException(status_code=401, detail="账号或密码不正确")

        token = (
            create_session_token(app_settings, app_settings.auth_username)
            if app_settings.auth_enabled
            else "preview"
        )
        response = JSONResponse(
            AuthStatus(
                auth_enabled=app_settings.auth_enabled,
                authenticated=True,
                username=(
                    app_settings.auth_username
                    if app_settings.auth_enabled
                    else payload.username
                ),
            ).model_dump()
        )
        response.set_cookie(
            SESSION_COOKIE_NAME,
            token,
            max_age=app_settings.auth_session_ttl_hours * 3600,
            httponly=True,
            secure=app_settings.auth_cookie_secure,
            samesite="lax",
            path="/",
        )
        return response

    @app.post("/api/auth/logout", status_code=204)
    async def logout() -> Response:
        response = Response(status_code=204)
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")
        return response

    @app.get("/api/settings/models", response_model=ModelStatus)
    async def model_status() -> ModelStatus:
        return ModelStatus(
            provider=app_settings.llm_provider,
            model=app_settings.llm_model,
            base_url=app_settings.llm_base_url,
            configured=app_settings.model_configured,
        )

    @app.post("/api/settings/models/test", response_model=ModelConnectionTest)
    async def test_model_connection() -> ModelConnectionTest:
        started_at = perf_counter()
        try:
            provider = build_provider(app_settings)
            message = await provider.test_connection()
            ok = True
        except Exception as error:
            message = str(error) or error.__class__.__name__
            ok = False

        return ModelConnectionTest(
            ok=ok,
            message=message[:800],
            latency_ms=max(0, round((perf_counter() - started_at) * 1000)),
            provider=app_settings.llm_provider,
            model=app_settings.llm_model,
        )

    @app.get("/api/categories")
    async def list_categories() -> list[dict[str, object]]:
        return [
            {
                "id": category.id,
                "directory": category.directory,
                "nameZh": category.name_zh,
                "nameEn": category.name_en,
                "description": category.description,
            }
            for category in CATEGORIES
        ]

    @app.get("/api/papers")
    async def list_papers(
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ) -> list[dict[str, object]]:
        return [
            paper.model_dump(mode="json")
            for paper in store.list_papers(limit=limit, offset=offset)
        ]

    @app.get("/api/papers/{paper_id}")
    async def get_paper(paper_id: str) -> dict[str, object]:
        paper = store.get_paper(paper_id)
        if not paper:
            raise HTTPException(status_code=404, detail="论文不存在")
        return paper.model_dump(mode="json")

    @app.get("/api/papers/{paper_id}/file")
    async def get_paper_file(paper_id: str) -> FileResponse:
        paper = store.get_paper(paper_id)
        if not paper or not paper.file_path:
            raise HTTPException(status_code=404, detail="PDF 文件不存在")
        path = Path(paper.file_path).resolve()
        try:
            path.relative_to(app_settings.paper_root.resolve())
        except ValueError as error:
            raise HTTPException(status_code=403, detail="PDF 路径不合法") from error
        if not path.exists() or path.suffix.lower() != ".pdf":
            raise HTTPException(status_code=404, detail="PDF 文件不存在")
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=path.name,
            content_disposition_type="inline",
        )

    @app.get("/api/papers/{paper_id}/translation")
    async def get_translation(paper_id: str) -> dict[str, object]:
        paper = store.get_paper(paper_id)
        if not paper:
            raise HTTPException(status_code=404, detail="论文不存在")
        return translation_payload(app_settings, paper)

    @app.get("/api/papers/{paper_id}/translation/file")
    async def get_translation_file(paper_id: str) -> FileResponse:
        paper = store.get_paper(paper_id)
        if not paper:
            raise HTTPException(status_code=404, detail="论文不存在")
        path = translation_file_path(app_settings, paper)
        if path is None or paper.translation_status != "ready":
            raise HTTPException(status_code=404, detail="中文译文不存在")
        return FileResponse(
            path,
            media_type="text/markdown; charset=utf-8",
            filename=path.name,
            content_disposition_type="attachment",
        )

    @app.post("/api/papers/{paper_id}/translation", status_code=202)
    async def start_translation(
        paper_id: str,
        background_tasks: BackgroundTasks,
    ) -> dict[str, object]:
        paper = store.get_paper(paper_id)
        if not paper:
            raise HTTPException(status_code=404, detail="论文不存在")
        if not paper.file_path:
            raise HTTPException(status_code=409, detail="论文没有可翻译的 PDF 文件")
        if not app_settings.model_configured:
            raise HTTPException(status_code=503, detail="模型未配置，无法生成中文译文")

        current = translation_payload(
            app_settings,
            paper,
            include_text=False,
        )
        if current["status"] in {"queued", "running", "ready"}:
            return current

        timestamp = utc_now()
        job = JobRecord(
            id=f"job-{uuid.uuid4().hex[:12]}",
            paper_id=paper.id,
            paper_title=paper.title,
            job_type="translate",
            status="queued",
            progress=0,
            message="翻译任务已创建，等待处理",
            stage="queued",
            source_url=paper.original_url,
            updated_at=timestamp,
            created_at=timestamp,
        )
        store.save_job(job)

        paper.translation_status = "queued"
        paper.translation_error = ""
        paper.translation_progress = 0
        paper.translation_completed_pages = 0
        paper.translation_model = app_settings.llm_model
        paper.translation_updated_at = timestamp
        store.save_paper(paper)
        background_tasks.add_task(pipeline.run_translation, paper.id, job.id)
        return translation_payload(app_settings, paper, include_text=False)

    @app.get("/api/jobs")
    async def list_jobs(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, object]]:
        return [job.model_dump(mode="json") for job in store.list_jobs(limit=limit)]

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: str) -> dict[str, object]:
        job = store.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="任务不存在")
        return job.model_dump(mode="json")

    @app.post("/api/imports/url", status_code=202)
    async def import_url(
        request: ImportUrlRequest,
        background_tasks: BackgroundTasks,
    ) -> dict[str, object]:
        if not app_settings.model_configured:
            raise HTTPException(
                status_code=503,
                detail=(
                    "模型未配置。请设置 LLM_BASE_URL、LLM_MODEL（或 LLM_MODEL_ID）"
                    "和 LLM_API_KEY，或使用 LLM_PROVIDER=mock 做离线测试。"
                ),
            )
        timestamp = utc_now()
        job = JobRecord(
            id=f"job-{uuid.uuid4().hex[:12]}",
            paper_title="等待解析链接",
            job_type="import",
            status="queued",
            progress=0,
            message="任务已创建，等待处理",
            stage="queued",
            source_url=request.url,
            updated_at=timestamp,
            created_at=timestamp,
        )
        store.save_job(job)
        background_tasks.add_task(pipeline.run_url_import, job.id)
        return job.model_dump(mode="json")

    @app.post("/api/imports/file", status_code=202)
    async def import_file(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
    ) -> dict[str, object]:
        if not app_settings.model_configured:
            raise HTTPException(
                status_code=503,
                detail=(
                    "模型未配置。请设置 LLM_BASE_URL、LLM_MODEL（或 LLM_MODEL_ID）"
                    "和 LLM_API_KEY，或使用 LLM_PROVIDER=mock 做离线测试。"
                ),
            )

        original_name = file.filename or "paper.pdf"
        if not original_name.lower().endswith(".pdf"):
            raise HTTPException(status_code=415, detail="只支持 PDF 文件。")

        filename = safe_filename(original_name)
        destination = (
            app_settings.need_organization_dir
            / f"{filename[:-4]}-{uuid.uuid4().hex[:8]}.pdf"
        )
        max_bytes = app_settings.max_download_mb * 1024 * 1024
        downloaded_bytes = 0
        first_chunk = True

        try:
            with destination.open("wb") as handle:
                while chunk := await file.read(1024 * 1024):
                    if first_chunk:
                        first_chunk = False
                        if not chunk.lstrip().startswith(b"%PDF-"):
                            raise HTTPException(
                                status_code=400, detail="文件不是有效的 PDF。"
                            )
                    downloaded_bytes += len(chunk)
                    if downloaded_bytes > max_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail=f"文件超过 {app_settings.max_download_mb} MB 的上传限制。",
                        )
                    handle.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            await file.close()

        timestamp = utc_now()
        job = JobRecord(
            id=f"job-{uuid.uuid4().hex[:12]}",
            paper_title=Path(original_name).stem,
            job_type="import",
            status="queued",
            progress=0,
            message="PDF 已放入 need_organization，等待处理",
            stage="queued",
            source_url=f"upload://{filename}",
            updated_at=timestamp,
            created_at=timestamp,
        )
        store.save_job(job)
        background_tasks.add_task(pipeline.run_local_import, job.id, str(destination))
        return job.model_dump(mode="json")

    @app.post("/api/jobs/{job_id}/retry", status_code=202)
    async def retry_job(
        job_id: str,
        background_tasks: BackgroundTasks,
    ) -> dict[str, object]:
        job = store.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="任务不存在")
        if (
            job.status != "failed"
            or not job.source_url
            or not job.source_url.startswith(("http://", "https://"))
        ):
            raise HTTPException(status_code=409, detail="只有失败且保留来源链接的任务可以重试")
        job.status = "queued"
        job.stage = "queued"
        job.progress = 0
        job.message = "任务已重新入队"
        job.error = ""
        job.updated_at = utc_now()
        store.save_job(job)
        background_tasks.add_task(pipeline.run_url_import, job.id)
        return job.model_dump(mode="json")

    return app


app = create_app()
