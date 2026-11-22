from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4
from typing import Any, Awaitable, Callable, Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .analysis import AnalysisError
from .config import ResearchSettings
from .corpus import CorpusError
from .interop import InteropError
from .pipeline import IdeationRequest, PipelineError, ResearchPipeline
from .provider import ProviderError
from .retrieval import RetrievalError
from .schemas import JobType, RetrievalMode
from .store import StoreError
from .synthesis import SynthesisError


ACTIVE_JOB_STATUSES = frozenset({"queued", "running"})


class CorpusSyncRequest(BaseModel):
    category_id: str = ""


class IndexRebuildRequest(BaseModel):
    category_id: str = ""


class DeepAnalysisRequest(BaseModel):
    limit: int = Field(default=0, ge=0, le=500)
    category_id: str = ""
    force: bool = False


class IdeationRequestBody(BaseModel):
    queries: list[str] = Field(default_factory=list)
    generation: int = Field(default=0, ge=0)
    max_queries: int = Field(default=3, ge=1, le=8)
    top_k: int = Field(default=0, ge=0, le=40)
    ideas_per_query: int = Field(default=2, ge=1, le=6)
    max_directions: int = Field(default=3, ge=1, le=10)
    max_experiments: int = Field(default=2, ge=0, le=6)
    user_feedback: str = Field(default="", max_length=4000)
    parent_direction_id: str = ""


class FollowupStatusUpdate(BaseModel):
    status: Literal["open", "done", "dismissed"]


def _failure_detail(error: Exception) -> str:
    message = str(error).strip()
    return message or error.__class__.__name__


def _translate_failure(error: Exception) -> HTTPException:
    """Map pipeline-level errors onto HTTP codes with Chinese messages."""
    if isinstance(error, HTTPException):
        return error
    if isinstance(error, ProviderError):
        return HTTPException(status_code=503, detail=_failure_detail(error))
    if isinstance(error, (PipelineError, SynthesisError, AnalysisError, InteropError)):
        return HTTPException(status_code=409, detail=_failure_detail(error))
    if isinstance(error, (RetrievalError, CorpusError, StoreError)):
        return HTTPException(status_code=500, detail=_failure_detail(error))
    return HTTPException(status_code=500, detail=f"服务内部错误：{_failure_detail(error)}")


def create_app(settings: ResearchSettings | None = None) -> FastAPI:
    app_settings = settings or ResearchSettings.from_env()
    app_settings.ensure_directories()
    pipeline = ResearchPipeline(app_settings)
    store = pipeline.store

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # A crash mid-job would otherwise leave rows stuck in "running" forever.
        interrupted = await asyncio.to_thread(store.mark_interrupted_jobs)
        if interrupted:
            await asyncio.to_thread(store.set_meta, "interrupted_jobs", str(interrupted))
        yield

    app = FastAPI(
        title="Research Studio API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.store = store
    app.state.pipeline = pipeline
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_settings.cors_origins),
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):3\d{3}",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def require_idle() -> None:
        """One heavy job at a time: protects SQLite writes and model spend."""
        busy = [job for job in store.list_jobs(limit=20) if job.status in ACTIVE_JOB_STATUSES]
        if busy:
            current = busy[0]
            raise HTTPException(
                status_code=409,
                detail=(
                    f"已有任务在执行（{current.id} / {current.job_type} / {current.stage}），"
                    "请等待其结束或查看 /api/research/jobs。"
                ),
            )

    def require_model() -> None:
        if not app_settings.model_configured:
            raise HTTPException(
                status_code=503,
                detail=(
                    "模型未配置。请填写 RESEARCH_LLM_BASE_URL、RESEARCH_LLM_MODEL、"
                    "RESEARCH_LLM_API_KEY，或使用 RESEARCH_LLM_PROVIDER=mock 做离线跑通。"
                ),
            )

    def launch(
        background_tasks: BackgroundTasks,
        job_type: JobType,
        message: str,
        runner: Callable[[str], Awaitable[None]],
        *,
        batch_id: str = "",
    ) -> dict[str, Any]:
        job = pipeline.create_job(job_type, message=message, batch_id=batch_id)
        background_tasks.add_task(runner, job.id)
        return job.model_dump(mode="json")

    # ---------------- health & status ----------------

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "research-studio",
            "provider": pipeline.provider_label,
            "model": pipeline.model_label,
            "backend": getattr(pipeline.backend, "name", "unknown"),
            "notice": pipeline.backend_notice,
        }

    @app.get("/api/research/status")
    async def status() -> dict[str, Any]:
        try:
            payload = pipeline.status().model_dump(mode="json")
        except (CorpusError, StoreError) as error:
            raise _translate_failure(error) from error
        payload["backend_notice"] = pipeline.backend_notice
        payload["config"] = {
            "paper_root": str(app_settings.paper_root),
            "storage_dir": str(app_settings.storage_dir),
            "database": str(app_settings.database_path),
            "reading_platform_available": app_settings.reading_platform_available(),
            "reading_platform_access": "read-only",
        }
        payload["index"] = {
            "stats": store.get_meta("index_updated_at"),
            "stale": store.get_meta("index_stale") == "1",
            "kinds": store.chunk_kinds(),
        }
        return payload

    # ---------------- corpus (stage B) ----------------

    @app.get("/api/research/corpus")
    async def corpus_overview() -> dict[str, Any]:
        try:
            return pipeline.corpus_overview()
        except (CorpusError, StoreError, PipelineError) as error:
            raise _translate_failure(error) from error

    @app.get("/api/research/corpus/papers")
    async def corpus_papers(
        category_id: str = "",
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> dict[str, Any]:
        try:
            papers = store.list_papers(category_id=category_id, limit=limit)
        except StoreError as error:
            raise _translate_failure(error) from error
        return {
            "total": len(papers),
            "items": [paper.model_dump(mode="json") for paper in papers],
        }

    @app.post("/api/research/corpus/sync", status_code=202)
    async def corpus_sync(
        background_tasks: BackgroundTasks,
        payload: CorpusSyncRequest | None = None,
    ) -> dict[str, Any]:
        require_idle()
        body = payload or CorpusSyncRequest()

        async def runner(job_id: str) -> None:
            await pipeline.run_corpus_sync_job(job_id, category_id=body.category_id)

        return launch(
            background_tasks,
            "corpus_sync",
            "语料同步任务已创建，等待处理",
            runner,
        )

    # ---------------- index (stage C) ----------------

    @app.post("/api/research/index/rebuild", status_code=202)
    async def index_rebuild(
        background_tasks: BackgroundTasks,
        payload: IndexRebuildRequest | None = None,
    ) -> dict[str, Any]:
        require_idle()
        body = payload or IndexRebuildRequest()

        async def runner(job_id: str) -> None:
            await pipeline.run_index_rebuild_job(job_id, category_id=body.category_id)

        return launch(
            background_tasks,
            "index_rebuild",
            "索引重建任务已创建，等待处理",
            runner,
        )

    @app.get("/api/research/search")
    async def search(
        q: str = Query(min_length=1, max_length=500),
        top_k: int = Query(default=0, ge=0, le=50),
        mode: RetrievalMode = "hybrid",
    ) -> dict[str, Any]:
        if store.chunk_count() == 0:
            raise HTTPException(
                status_code=409,
                detail="向量索引为空，请先执行 POST /api/research/corpus/sync。",
            )
        try:
            hits = pipeline.search(q, top_k=top_k, mode=mode)
        except (PipelineError, RetrievalError) as error:
            raise _translate_failure(error) from error
        return {
            "query": q,
            "mode": mode,
            "total": len(hits),
            "items": [hit.model_dump(mode="json") for hit in hits],
        }

    # ---------------- deep analysis (stage D) ----------------

    @app.get("/api/research/estimate-analysis")
    async def estimate_analysis(
        limit: int = Query(default=0, ge=0, le=500),
        category_id: str = "",
        force: bool = False,
    ) -> dict[str, Any]:
        try:
            return pipeline.analysis_estimate(
                limit=limit, category_id=category_id, force=force
            )
        except (PipelineError, StoreError) as error:
            raise _translate_failure(error) from error

    @app.get("/api/research/analyses")
    async def list_analyses(
        status_filter: str = Query(default="", alias="status"),
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict[str, Any]:
        try:
            records = store.list_deep_analyses(status=status_filter, limit=limit)
        except StoreError as error:
            raise _translate_failure(error) from error
        return {
            "total": len(records),
            "items": [record.model_dump(mode="json") for record in records],
        }

    @app.post("/api/research/analyze", status_code=202)
    async def start_analysis(
        background_tasks: BackgroundTasks,
        payload: DeepAnalysisRequest | None = None,
    ) -> dict[str, Any]:
        require_idle()
        require_model()
        body = payload or DeepAnalysisRequest()
        try:
            estimate = pipeline.analysis_estimate(
                limit=body.limit, category_id=body.category_id, force=body.force
            )
        except (PipelineError, StoreError) as error:
            raise _translate_failure(error) from error
        if estimate["papers_total"] == 0:
            raise HTTPException(status_code=409, detail="语料库为空，请先执行语料同步。")
        if not body.force and estimate["selected"] == 0:
            raise HTTPException(
                status_code=409,
                detail="没有待解析的论文（当前提示词版本已全部完成），如需重跑请使用 force=true。",
            )

        async def runner(job_id: str) -> None:
            await pipeline.run_deep_analysis_job(
                job_id,
                limit=body.limit,
                category_id=body.category_id,
                force=body.force,
            )

        return launch(
            background_tasks,
            "deep_analysis",
            f"深度解析任务已创建，计划处理 {estimate['selected']} 篇论文",
            runner,
        )

    # ---------------- ideation loop (stages E/F/G) ----------------

    @app.post("/api/research/ideate", status_code=202)
    async def start_ideation(
        background_tasks: BackgroundTasks,
        payload: IdeationRequestBody | None = None,
    ) -> dict[str, Any]:
        require_idle()
        require_model()
        body = payload or IdeationRequestBody()
        if store.count_papers() == 0:
            raise HTTPException(status_code=409, detail="语料库为空，请先执行语料同步。")
        if body.parent_direction_id and not store.get_direction(body.parent_direction_id):
            raise HTTPException(status_code=404, detail="父研究方向不存在")

        request = IdeationRequest(
            queries=[item.strip() for item in body.queries if item.strip()],
            generation=body.generation,
            max_queries=body.max_queries,
            top_k=body.top_k,
            ideas_per_query=body.ideas_per_query,
            max_directions=body.max_directions,
            max_experiments=body.max_experiments,
            user_feedback=body.user_feedback.strip(),
            parent_direction_id=body.parent_direction_id,
            batch_id=f"batch-{uuid4().hex[:10]}",
        )

        async def runner(job_id: str) -> None:
            await pipeline.run_ideation_job(job_id, request)

        return launch(
            background_tasks,
            "ideation",
            "创新点生成任务已创建，等待处理",
            runner,
            batch_id=request.batch_id,
        )

    @app.get("/api/research/ideas")
    async def list_ideas(
        batch_id: str = "",
        generation: int = Query(default=0, ge=0),
        include_rejected: bool = False,
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> dict[str, Any]:
        try:
            ideas = store.list_ideas(
                batch_id=batch_id,
                generation=generation,
                include_rejected=include_rejected,
                limit=limit,
            )
        except StoreError as error:
            raise _translate_failure(error) from error
        return {
            "total": len(ideas),
            "items": [idea.model_dump(mode="json") for idea in ideas],
        }

    @app.get("/api/research/directions")
    async def list_directions(
        generation: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, Any]:
        try:
            directions = store.list_directions(generation=generation, limit=limit)
        except StoreError as error:
            raise _translate_failure(error) from error
        return {
            "total": len(directions),
            "items": [item.model_dump(mode="json") for item in directions],
        }

    @app.get("/api/research/directions/{direction_id}")
    async def get_direction(direction_id: str) -> dict[str, Any]:
        try:
            direction = store.get_direction(direction_id)
            if direction is None:
                raise HTTPException(status_code=404, detail="研究方向不存在")
            members = store.list_ideas(batch_id="", generation=0, include_rejected=False, limit=1000)
            wanted = set(direction.member_idea_ids)
            experiments = [
                plan
                for plan in store.list_experiments(limit=500)
                if plan.direction_id == direction_id
            ]
        except StoreError as error:
            raise _translate_failure(error) from error
        return {
            "direction": direction.model_dump(mode="json"),
            "ideas": [
                idea.model_dump(mode="json") for idea in members if idea.id in wanted
            ],
            "experiments": [plan.model_dump(mode="json") for plan in experiments],
            "followups": [
                item.model_dump(mode="json")
                for item in store.list_followups(limit=500)
                if item.direction_id == direction_id
            ],
        }

    @app.get("/api/research/experiments")
    async def list_experiments(
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, Any]:
        try:
            plans = store.list_experiments(limit=limit)
        except StoreError as error:
            raise _translate_failure(error) from error
        return {
            "total": len(plans),
            "items": [plan.model_dump(mode="json") for plan in plans],
        }

    @app.get("/api/research/experiments/{experiment_id}")
    async def get_experiment(experiment_id: str) -> dict[str, Any]:
        try:
            plan = store.get_experiment(experiment_id)
        except StoreError as error:
            raise _translate_failure(error) from error
        if plan is None:
            raise HTTPException(status_code=404, detail="实验方案不存在")
        return plan.model_dump(mode="json")

    @app.get("/api/research/followups")
    async def list_followups(
        status_filter: str = Query(default="", alias="status"),
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> dict[str, Any]:
        try:
            items = store.list_followups(status=status_filter, limit=limit)
        except StoreError as error:
            raise _translate_failure(error) from error
        return {
            "total": len(items),
            "items": [item.model_dump(mode="json") for item in items],
        }

    @app.patch("/api/research/followups/{followup_id}/status")
    async def update_followup(
        followup_id: str, payload: FollowupStatusUpdate
    ) -> dict[str, Any]:
        try:
            updated = store.update_followup_status(followup_id, payload.status)
        except StoreError as error:
            raise _translate_failure(error) from error
        if not updated:
            raise HTTPException(status_code=404, detail="待办事项不存在")
        current = next(
            (item for item in store.list_followups(limit=1000) if item.id == followup_id),
            None,
        )
        if current is None:
            raise HTTPException(status_code=404, detail="待办事项不存在")
        return current.model_dump(mode="json")

    @app.get("/api/research/runs")
    async def list_runs(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
        try:
            runs = store.list_runs(limit=limit)
        except StoreError as error:
            raise _translate_failure(error) from error
        return {
            "total": len(runs),
            "items": [run.model_dump(mode="json") for run in runs],
        }

    @app.get("/api/research/runs/{batch_id}")
    async def get_run(batch_id: str) -> dict[str, Any]:
        try:
            run = store.get_run(batch_id)
        except StoreError as error:
            raise _translate_failure(error) from error
        if run is None:
            raise HTTPException(status_code=404, detail="演化轮次不存在")
        return run.model_dump(mode="json")

    # ---------------- jobs ----------------

    @app.get("/api/research/jobs")
    async def list_jobs(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
        jobs = store.list_jobs(limit=limit)
        return {
            "total": len(jobs),
            "items": [job.model_dump(mode="json") for job in jobs],
        }

    @app.get("/api/research/jobs/{job_id}")
    async def get_job(job_id: str) -> dict[str, Any]:
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        return job.model_dump(mode="json")

    return app


app = create_app()


__all__ = ["app", "create_app"]
