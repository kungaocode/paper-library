"""HTTP surface tests: routes, status codes, job lifecycle, isolation.

The reading platform is live and must stay untouched, so every client here is
built from the conftest fixtures (throwaway paper repo, mock provider, temp
storage). `RESEARCH_*` env vars are redirected to a scratch dir *before*
`app.main` is imported, because that module builds a default app at import time
and would otherwise create `storage/research/` inside the real repository.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import replace
from pathlib import Path

_IMPORT_SCRATCH = Path(tempfile.mkdtemp(prefix="research-api-import-"))
os.environ["RESEARCH_PAPER_ROOT"] = str(_IMPORT_SCRATCH / "paper")
os.environ["RESEARCH_STORAGE_DIR"] = str(_IMPORT_SCRATCH / "storage")

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.analysis import AnalysisError
from app.config import ResearchSettings
from app.corpus import CorpusError
from app.interop import InteropError
from app.main import _translate_failure, create_app
from app.pipeline import PipelineError
from app.provider import ProviderError
from app.retrieval import RetrievalError
from app.schemas import IdeationRun, ResearchJob, utc_now
from app.store import ResearchStore, StoreError
from app.synthesis import SynthesisError


# ---------------- helpers ----------------


def _store(client: TestClient) -> ResearchStore:
    return client.app.state.store


def _seed_job(
    store: ResearchStore,
    job_id: str,
    *,
    status: str = "running",
    job_type: str = "ideation",
    batch_id: str = "",
) -> ResearchJob:
    job = ResearchJob(
        id=job_id,
        job_type=job_type,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        progress=40,
        stage="seeded",
        message="测试用占位任务",
        batch_id=batch_id,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    store.save_job(job)
    return job


def _launch(client: TestClient, url: str, **kwargs) -> tuple[dict, dict]:
    """Start a background job and return (accepted payload, finished job).

    TestClient runs background tasks as part of the response, so the job is
    already terminal by the time the second GET returns.
    """
    response = client.post(url, **kwargs)
    assert response.status_code == 202, response.text
    accepted = response.json()
    assert accepted["status"] == "queued"
    assert accepted["id"].startswith("job-")

    finished = client.get(f"/api/research/jobs/{accepted['id']}")
    assert finished.status_code == 200, finished.text
    return accepted, finished.json()


def _assert_succeeded(job: dict, phase: str) -> dict:
    assert job["status"] == "succeeded", job
    assert job["progress"] == 100 and job["stage"] == "succeeded"
    assert job["error"] == ""
    assert job["result"] is not None and job["result"]["phase"] == phase
    return job["result"]["detail"]


def _protected_digest(root: Path) -> dict[str, str]:
    """Hash everything the research service is only allowed to read."""
    targets = [
        root / "storage" / "api" / "library.sqlite3",
        root / "KNOWLEDGE_BASE.md",
        *sorted((root / "papers").glob("*.pdf")),
    ]
    return {
        str(path.relative_to(root)): hashlib.md5(path.read_bytes()).hexdigest()
        for path in targets
    }


@pytest.fixture()
def client(settings: ResearchSettings) -> TestClient:
    return TestClient(create_app(settings))


@pytest.fixture()
def synced_client(client: TestClient) -> TestClient:
    """Client with corpus + index ready (corpus sync also rebuilds the index)."""
    _launch(client, "/api/research/corpus/sync")
    return client


@pytest.fixture()
def unconfigured_client(settings: ResearchSettings, tmp_path: Path) -> TestClient:
    """A non-mock provider with empty credentials: model_configured is False."""
    offline = replace(
        settings,
        llm_provider="openai",
        llm_base_url="",
        llm_api_key="",
        llm_model="",
        storage_dir=tmp_path / "research-unconfigured",
    )
    assert offline.model_configured is False
    return TestClient(create_app(offline))


def _ideated(client: TestClient) -> dict:
    """Sync the corpus and run one ideation generation; return the run record."""
    _launch(client, "/api/research/corpus/sync")
    _, job = _launch(
        client,
        "/api/research/ideate",
        json={
            "queries": ["把训练期安全约束迁移到智能体运行时决策点"],
            "ideas_per_query": 2,
            "max_directions": 1,
            "max_experiments": 1,
        },
    )
    return _assert_succeeded(job, "ideation")


# ---------------- health & status ----------------


def test_health_reports_the_offline_stack(client: TestClient) -> None:
    payload = client.get("/health").json()

    assert payload["status"] == "ok"
    assert payload["service"] == "research-studio"
    assert payload["provider"] == "mock" and payload["model"] == "mock-research"
    assert payload["backend"] == "builtin-sqlite-hybrid"
    # No knowledge_vector configured yet: the built-in backend runs, no warning.
    assert payload["notice"] == ""


def test_status_declares_read_only_reading_platform_access(
    client: TestClient, settings: ResearchSettings, tmp_paper_root: Path
) -> None:
    response = client.get("/api/research/status")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["service"] == "research-studio"
    assert payload["model_configured"] is True
    assert payload["paper_database"] == str(settings.paper_database_path)
    assert payload["paper_database_readable"] is True
    assert payload["reading_platform_writes"] == 0
    assert payload["knowledge_vector_available"] is False
    assert payload["papers_indexed"] == 0 and payload["chunks"] == 0

    assert payload["config"]["reading_platform_access"] == "read-only"
    assert payload["config"]["paper_root"] == str(tmp_paper_root)
    assert payload["config"]["reading_platform_available"] is True
    # The research database must live outside the reading platform's tree.
    assert not Path(payload["config"]["database"]).is_relative_to(tmp_paper_root)

    assert payload["index"]["stale"] is False and payload["index"]["kinds"] == {}


# ---------------- corpus ----------------


def test_corpus_overview_is_empty_before_sync(client: TestClient) -> None:
    payload = client.get("/api/research/corpus").json()

    assert payload["papers"] == 0
    assert payload["categories"] == []
    assert payload["reading_platform_access"] == "read-only"
    assert payload["index_stale"] is False


def test_corpus_sync_runs_as_a_background_job(client: TestClient) -> None:
    accepted, job = _launch(client, "/api/research/corpus/sync")

    assert accepted["job_type"] == "corpus_sync"
    assert accepted["message"] == "语料同步任务已创建，等待处理"
    detail = _assert_succeeded(job, "corpus_sync")
    assert (detail["scanned"], detail["created"], detail["total"]) == (3, 3, 3)
    assert detail["missing_pdf"] == 0 and detail["errors"] == []
    # Sync also refreshes the index so search works right away.
    assert detail["index"]["papers"] == 3 and detail["index"]["chunks"] > 0
    assert job["message"].startswith("语料同步完成")


def test_corpus_papers_filter_by_category(synced_client: TestClient) -> None:
    everything = synced_client.get("/api/research/corpus/papers").json()
    assert everything["total"] == 3

    filtered = synced_client.get(
        "/api/research/corpus/papers", params={"category_id": "cat-01"}
    ).json()
    assert filtered["total"] == 1
    paper = filtered["items"][0]
    assert paper["paper_id"] == "paper-aaa111000000"
    assert paper["thesis_zh"] and paper["novelty_zh"]
    assert paper["innovations"][0]["claim"]
    assert paper["pdf_path"].startswith("papers/")


def test_corpus_papers_reject_invalid_limit(synced_client: TestClient) -> None:
    assert (
        synced_client.get("/api/research/corpus/papers", params={"limit": 0}).status_code
        == 422
    )
    assert (
        synced_client.get(
            "/api/research/corpus/papers", params={"limit": 1001}
        ).status_code
        == 422
    )


# ---------------- index & search ----------------


def test_index_rebuild_job_reports_chunk_stats(synced_client: TestClient) -> None:
    _, job = _launch(synced_client, "/api/research/index/rebuild")

    detail = _assert_succeeded(job, "index_rebuild")
    assert detail["papers"] == 3 and detail["chunks"] > 0
    assert detail["categories"] == 3
    assert detail["embedding_model"] == "hashing-v1-384"
    assert job["message"].startswith("索引重建完成")


def test_search_refuses_an_empty_index(client: TestClient) -> None:
    response = client.get("/api/research/search", params={"q": "安全"})

    assert response.status_code == 409
    assert "向量索引为空" in response.json()["detail"]


@pytest.mark.parametrize(
    "params",
    [
        {"q": ""},
        {"q": "长" * 501},
        {"q": "安全", "top_k": 51},
        {"q": "安全", "top_k": -1},
        {"q": "安全", "mode": "bogus"},
        {},
    ],
)
def test_search_validates_query_parameters(client: TestClient, params: dict) -> None:
    assert client.get("/api/research/search", params=params).status_code == 422


def test_search_returns_ranked_hybrid_hits(synced_client: TestClient) -> None:
    response = synced_client.get(
        "/api/research/search", params={"q": "安全 token 约束", "top_k": 5}
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["query"] == "安全 token 约束" and payload["mode"] == "hybrid"
    assert 1 <= payload["total"] <= 5 and payload["total"] == len(payload["items"])
    scores = [item["score"] for item in payload["items"]]
    assert scores == sorted(scores, reverse=True)
    top = payload["items"][0]
    assert top["chunk_id"] and top["text"] and top["kind"].startswith("paper.")
    assert top["paper_id"] == "paper-aaa111000000"
    assert top["lexical_score"] is not None and top["vector_score"] is not None


def test_search_supports_lexical_and_vector_modes(synced_client: TestClient) -> None:
    lexical = synced_client.get(
        "/api/research/search", params={"q": "注入", "mode": "lexical", "top_k": 3}
    ).json()
    assert lexical["mode"] == "lexical" and lexical["total"] >= 1
    assert all(item["vector_score"] is None for item in lexical["items"])
    assert any("注入" in item["text"] for item in lexical["items"])

    vector = synced_client.get(
        "/api/research/search", params={"q": "越狱迁移性", "mode": "vector", "top_k": 3}
    ).json()
    assert vector["mode"] == "vector" and vector["total"] >= 1
    assert all(item["score"] >= 0 for item in vector["items"])


# ---------------- deep analysis ----------------


def test_estimate_analysis_describes_pending_work(synced_client: TestClient) -> None:
    estimate = synced_client.get("/api/research/estimate-analysis").json()
    assert estimate["papers_total"] == 3 and estimate["pending"] == 3
    assert estimate["selected"] == 3 and estimate["estimated_model_calls"] == 3
    assert estimate["missing_pdf_count"] == 0
    assert estimate["prompt_version"] == "v1" and estimate["model"] == "mock-research"
    assert estimate["concurrency"] == 2

    limited = synced_client.get(
        "/api/research/estimate-analysis", params={"limit": 2}
    ).json()
    assert limited["selected"] == 2 and limited["pending"] == 3

    scoped = synced_client.get(
        "/api/research/estimate-analysis", params={"category_id": "cat-04"}
    ).json()
    assert scoped["papers_total"] == 1 and scoped["selected"] == 1


def test_analyze_requires_a_synced_corpus(client: TestClient) -> None:
    response = client.post("/api/research/analyze")

    assert response.status_code == 409
    assert response.json()["detail"] == "语料库为空，请先执行语料同步。"


def test_analyze_reports_503_when_the_model_is_not_configured(
    unconfigured_client: TestClient,
) -> None:
    response = unconfigured_client.post("/api/research/analyze")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "模型未配置" in detail and "RESEARCH_LLM_BASE_URL" in detail
    assert unconfigured_client.get("/api/research/status").json()["model_configured"] is False


def test_ideate_reports_503_when_the_model_is_not_configured(
    unconfigured_client: TestClient,
) -> None:
    response = unconfigured_client.post("/api/research/ideate", json={})

    assert response.status_code == 503
    assert "模型未配置" in response.json()["detail"]


def test_analyze_stores_ready_records(synced_client: TestClient) -> None:
    accepted, job = _launch(synced_client, "/api/research/analyze")
    assert accepted["job_type"] == "deep_analysis"
    assert "计划处理 3 篇论文" in accepted["message"]

    detail = _assert_succeeded(job, "deep_analysis")
    assert detail["analyzed"] == 3 and detail["failed"] == 0

    analyses = synced_client.get("/api/research/analyses").json()
    assert analyses["total"] == 3
    for record in analyses["items"]:
        assert record["status"] == "ready" and record["prompt_version"] == "v1"
        assert record["problem"] and record["method"] and record["findings"]
        assert record["innovations"][0]["evidence_quotes"]

    overview = synced_client.get("/api/research/corpus").json()
    assert overview["deep_analysis_ready"] == 3 and overview["needs_deep_analysis"] == 0
    # New analyses invalidate the index until it is rebuilt.
    assert overview["index_stale"] is True


def test_analyze_refuses_a_second_pass_until_forced(synced_client: TestClient) -> None:
    _launch(synced_client, "/api/research/analyze")

    repeat = synced_client.post("/api/research/analyze")
    assert repeat.status_code == 409
    assert "没有待解析的论文" in repeat.json()["detail"]
    assert "force=true" in repeat.json()["detail"]

    # The estimate route can preview a forced rerun: nothing is pending, yet one
    # paper would be re-read, so the announced cost must not collapse to 0.
    preview = synced_client.get(
        "/api/research/estimate-analysis", params={"force": True, "limit": 1}
    ).json()
    assert preview["force"] is True
    assert preview["already_ready"] == 3 and preview["pending"] == 0
    assert preview["selected"] == 1 and preview["estimated_model_calls"] == 1

    accepted, job = _launch(synced_client, "/api/research/analyze", json={"force": True, "limit": 1})
    assert "计划处理 1 篇论文" in accepted["message"]
    detail = _assert_succeeded(job, "deep_analysis")
    # force bypasses the cache, so nothing is counted as reused.
    assert detail["analyzed"] == 1 and detail["cached"] == 0

    estimate = synced_client.get("/api/research/estimate-analysis").json()
    assert estimate["already_ready"] == 3 and estimate["pending"] == 0
    assert estimate["force"] is False and estimate["selected"] == 0


def test_analyses_list_filters_by_status(synced_client: TestClient) -> None:
    _launch(synced_client, "/api/research/analyze")

    ready = synced_client.get("/api/research/analyses", params={"status": "ready"}).json()
    assert ready["total"] == 3
    failed = synced_client.get("/api/research/analyses", params={"status": "failed"}).json()
    assert failed["total"] == 0 and failed["items"] == []


# ---------------- ideation loop ----------------


def test_ideate_requires_a_synced_corpus(client: TestClient) -> None:
    response = client.post("/api/research/ideate", json={})

    assert response.status_code == 409
    assert response.json()["detail"] == "语料库为空，请先执行语料同步。"


def test_ideate_rejects_an_unknown_parent_direction(synced_client: TestClient) -> None:
    response = synced_client.post(
        "/api/research/ideate", json={"parent_direction_id": "dir-does-not-exist"}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "父研究方向不存在"


@pytest.mark.parametrize(
    "body",
    [
        {"ideas_per_query": 0},
        {"ideas_per_query": 7},
        {"max_queries": 0},
        {"max_queries": 9},
        {"generation": -1},
        {"top_k": 41},
        {"max_directions": 0},
        {"max_directions": 11},
        {"max_experiments": 7},
        {"user_feedback": "x" * 4001},
    ],
)
def test_ideate_validates_the_request_body(client: TestClient, body: dict) -> None:
    assert client.post("/api/research/ideate", json=body).status_code == 422


def test_ideation_produces_traceable_output(client: TestClient) -> None:
    run = _ideated(client)

    assert run["generation"] == 1 and run["provider"] == "mock"
    assert run["ideas_total"] == 2 and run["ideas_accepted"] == 2
    assert run["ideas_rejected"] == 0
    assert (run["directions_total"], run["experiments_total"]) == (1, 1)
    assert run["followups_total"] == 3
    assert run["message"] == "第 1 代演化完成：2 条想法、1 个方向、1 份实验方案、3 条待办"

    ideas = client.get("/api/research/ideas").json()
    assert ideas["total"] == 2
    for idea in ideas["items"]:
        assert idea["id"].startswith("idea-") and idea["rejected_reason"] == ""
        assert idea["batch_id"] == run["batch_id"]
        assert idea["hypothesis"] and idea["method_sketch"]
        # The citation gate: >= 2 real corpus papers and real chunk ids.
        assert len(idea["source_paper_ids"]) >= 2
        assert idea["evidence_refs"]
        assert idea["critique"]["verdict"] and 0 <= idea["critique"]["score"] <= 1

    assert run["batch_id"].startswith("batch-")
    listed = client.get(f"/api/research/runs/{run['batch_id']}").json()
    assert listed["status"] == "succeeded" and listed["ideas_accepted"] == 2


def test_direction_detail_bundles_the_closed_loop(client: TestClient) -> None:
    run = _ideated(client)

    directions = client.get("/api/research/directions").json()
    assert directions["total"] == 1
    direction_id = directions["items"][0]["id"]
    assert direction_id.startswith("dir-")

    response = client.get(f"/api/research/directions/{direction_id}")
    assert response.status_code == 200, response.text
    detail = response.json()

    assert detail["direction"]["id"] == direction_id
    assert detail["direction"]["roadmap"] and detail["direction"]["success_metrics"]
    member_ids = set(detail["direction"]["member_idea_ids"])
    accepted_ids = {
        idea["id"] for idea in client.get("/api/research/ideas").json()["items"]
    }
    assert member_ids and member_ids <= accepted_ids
    assert {idea["id"] for idea in detail["ideas"]} == member_ids
    assert len(detail["experiments"]) == run["experiments_total"]
    assert all(plan["direction_id"] == direction_id for plan in detail["experiments"])
    assert len(detail["followups"]) == run["followups_total"]
    assert all(item["direction_id"] == direction_id for item in detail["followups"])

    # Filtering by generation must keep the same view.
    scoped = client.get("/api/research/directions", params={"generation": 1}).json()
    assert scoped["total"] == 1
    empty = client.get("/api/research/directions", params={"generation": 2}).json()
    assert empty["total"] == 0


def test_experiment_detail_belongs_to_its_direction(client: TestClient) -> None:
    _ideated(client)

    plans = client.get("/api/research/experiments").json()
    assert plans["total"] == 1
    plan_id = plans["items"][0]["id"]

    response = client.get(f"/api/research/experiments/{plan_id}")
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["id"] == plan_id and plan["status"] == "draft"
    assert plan["datasets"] and plan["baselines"] and plan["metrics"]
    assert plan["protocol_steps"] and plan["ablations"] and plan["timeline"]
    assert plan["falsification_criteria"] and plan["compute_estimate"]
    assert plan["direction_name"] == plans["items"][0]["direction_name"]


def test_followups_support_status_transitions(client: TestClient) -> None:
    run = _ideated(client)

    followups = client.get("/api/research/followups").json()
    assert followups["total"] == run["followups_total"]
    kinds = {item["kind"] for item in followups["items"]}
    assert "paper_to_read" in kinds
    assert all(item["status"] == "open" and item["query"] for item in followups["items"])

    target = next(
        item for item in followups["items"] if item["kind"] == "paper_to_read"
    )
    # The reading-platform hand-off is the point of a paper_to_read followup.
    assert "阅读平台" in target["suggested_action"]

    updated = client.patch(
        f"/api/research/followups/{target['id']}/status", json={"status": "done"}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "done"

    done = client.get("/api/research/followups", params={"status": "done"}).json()
    assert done["total"] == 1 and done["items"][0]["id"] == target["id"]
    still_open = client.get("/api/research/followups", params={"status": "open"}).json()
    assert still_open["total"] == 2

    dismissed = client.patch(
        f"/api/research/followups/{target['id']}/status", json={"status": "dismissed"}
    )
    assert dismissed.status_code == 200 and dismissed.json()["status"] == "dismissed"


def test_second_generation_dedupes_instead_of_repeating(client: TestClient) -> None:
    _ideated(client)

    _, job = _launch(
        client,
        "/api/research/ideate",
        json={"queries": ["把训练期安全约束迁移到智能体运行时决策点"]},
    )
    second = _assert_succeeded(job, "ideation")

    assert second["generation"] == 2
    assert second["ideas_total"] == 2 and second["ideas_accepted"] == 0
    assert second["ideas_rejected"] == 2
    assert second["directions_total"] == 0 and second["experiments_total"] == 0
    assert second["message"] == "本轮没有通过引用校验的想法，未生成方向。"

    rejected = client.get(
        "/api/research/ideas", params={"generation": 2, "include_rejected": True}
    ).json()
    assert rejected["total"] == 2
    assert all("与已有想法重复" in item["rejected_reason"] for item in rejected["items"])
    # Accepted ideas from generation 1 are untouched.
    assert client.get("/api/research/ideas").json()["total"] == 2


def test_status_marks_the_index_stale_after_ideation(client: TestClient) -> None:
    _ideated(client)

    payload = client.get("/api/research/status").json()
    assert payload["ideas"] == 2 and payload["directions"] == 1
    assert payload["experiments"] == 1 and payload["generations"] == 1
    assert payload["index"]["stale"] is True
    assert payload["index"]["kinds"]["idea.claim"] == 2
    assert payload["index"]["kinds"]["idea.direction"] == 1

    # Rebuilding clears the flag and folds generated content back into search.
    _launch(client, "/api/research/index/rebuild")
    refreshed = client.get("/api/research/status").json()
    assert refreshed["index"]["stale"] is False
    assert refreshed["chunks"] > 0


def test_unknown_ids_return_404(client: TestClient) -> None:
    cases = [
        ("/api/research/directions/dir-nope", "研究方向不存在"),
        ("/api/research/experiments/exp-nope", "实验方案不存在"),
        ("/api/research/runs/batch-nope", "演化轮次不存在"),
        ("/api/research/jobs/job-nope", "任务不存在"),
    ]
    for url, detail in cases:
        response = client.get(url)
        assert response.status_code == 404, url
        assert response.json()["detail"] == detail

    patched = client.patch("/api/research/followups/fu-nope/status", json={"status": "done"})
    assert patched.status_code == 404
    assert patched.json()["detail"] == "待办事项不存在"

    invalid = client.patch("/api/research/followups/fu-nope/status", json={"status": "nope"})
    assert invalid.status_code == 422


# ---------------- jobs & concurrency ----------------


def test_jobs_list_and_detail(synced_client: TestClient) -> None:
    listing = synced_client.get("/api/research/jobs").json()
    assert listing["total"] == 1
    job = listing["items"][0]
    assert job["job_type"] == "corpus_sync" and job["status"] == "succeeded"

    fetched = synced_client.get(f"/api/research/jobs/{job['id']}").json()
    assert fetched["id"] == job["id"] and fetched["result"]["phase"] == "corpus_sync"


def test_busy_job_blocks_new_work(client: TestClient) -> None:
    """One heavy job at a time protects SQLite writes and model spend."""
    _seed_job(_store(client), "job-seeded", status="running")

    for url in (
        "/api/research/corpus/sync",
        "/api/research/index/rebuild",
        "/api/research/analyze",
        "/api/research/ideate",
    ):
        response = client.post(url, json={})
        assert response.status_code == 409, url
        detail = response.json()["detail"]
        assert "已有任务在执行" in detail and "job-seeded" in detail

    # Read-only routes stay available while a job is running.
    assert client.get("/api/research/status").status_code == 200
    assert client.get("/api/research/jobs").status_code == 200


def test_queued_job_also_blocks_new_work(client: TestClient) -> None:
    _seed_job(_store(client), "job-queued", status="queued", job_type="corpus_sync")

    response = client.post("/api/research/corpus/sync")
    assert response.status_code == 409
    assert "job-queued" in response.json()["detail"]


def test_startup_marks_interrupted_jobs_failed(settings: ResearchSettings) -> None:
    """A crash mid-job must not leave rows stuck in queued/running forever."""
    app = create_app(settings)
    store = app.state.store
    _seed_job(store, "job-was-running", status="running", batch_id="batch-interrupted")
    _seed_job(store, "job-was-queued", status="queued", job_type="corpus_sync")
    _seed_job(store, "job-already-done", status="succeeded", job_type="index_rebuild")
    store.save_run(
        IdeationRun(
            batch_id="batch-interrupted",
            status="running",
            generation=1,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )

    with TestClient(app) as client:
        jobs = {item["id"]: item for item in client.get("/api/research/jobs").json()["items"]}

    assert jobs["job-was-running"]["status"] == "failed"
    assert jobs["job-was-running"]["message"] == "服务重启，任务已中断"
    assert jobs["job-was-running"]["error"]
    assert jobs["job-was-queued"]["status"] == "failed"
    assert jobs["job-already-done"]["status"] == "succeeded"
    assert store.get_meta("interrupted_jobs") == "2"

    run = store.get_run("batch-interrupted")
    assert run is not None and run.status == "failed"
    assert run.message == "服务重启，本轮演化已中断"


# ---------------- error mapping & CORS ----------------


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (ProviderError("模型服务超时"), 503),
        (PipelineError("语料库为空"), 409),
        (SynthesisError("想法缺少引用"), 409),
        (AnalysisError("PDF 解析失败"), 409),
        (InteropError("拒绝加载阅读平台模块"), 409),
        (RetrievalError("索引缺失"), 500),
        (CorpusError("论文库不可读"), 500),
        (StoreError("数据库损坏"), 500),
    ],
)
def test_translate_failure_maps_domain_errors(error: Exception, status_code: int) -> None:
    translated = _translate_failure(error)

    assert isinstance(translated, HTTPException)
    assert translated.status_code == status_code
    assert translated.detail == str(error)


def test_translate_failure_handles_passthrough_and_unknown_errors() -> None:
    original = HTTPException(status_code=418, detail="保持原样")
    assert _translate_failure(original) is original

    blank = _translate_failure(StoreError("   "))
    assert blank.status_code == 500 and blank.detail == "StoreError"

    generic = _translate_failure(ValueError("boom"))
    assert generic.status_code == 500
    assert generic.detail == "服务内部错误：boom"


def test_cors_preflight_allows_the_research_web_only(client: TestClient) -> None:
    allowed = client.options(
        "/api/research/ideate",
        headers={
            "Origin": "http://localhost:3100",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3100"
    assert allowed.headers["access-control-allow-credentials"] == "true"

    blocked = client.options(
        "/api/research/ideate",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert blocked.status_code == 400
    assert "access-control-allow-origin" not in blocked.headers

    simple = client.get("/health", headers={"Origin": "http://example.com"})
    assert simple.status_code == 200
    assert "access-control-allow-origin" not in simple.headers


# ---------------- isolation ----------------


def test_full_loop_never_writes_the_reading_platform(
    client: TestClient, settings: ResearchSettings, tmp_paper_root: Path
) -> None:
    """Run every stage over HTTP, then prove the paper repo is byte-identical."""
    before = _protected_digest(tmp_paper_root)

    _launch(client, "/api/research/corpus/sync")
    _launch(client, "/api/research/analyze")
    _ideated(client)
    client.get("/api/research/search", params={"q": "安全 token"})
    client.get("/api/research/status")

    assert _protected_digest(tmp_paper_root) == before
    assert settings.database_path.exists()
    assert not (tmp_paper_root / "storage" / "research").exists()
    assert client.get("/api/research/status").json()["reading_platform_writes"] == 0
