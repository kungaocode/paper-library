"""End-to-end offline loop: corpus -> index -> deep analysis -> ideas -> directions.

Everything here runs against the deterministic mock provider, so the whole
research loop is verified without a model API and without the external vector
library. The numbers asserted are the loop's real output on the three-paper
synthetic corpus from conftest.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.config import ANALYSIS_PROMPT_VERSION, ResearchSettings
from app.pipeline import (
    EVIDENCE_POOL_CAP,
    EVIDENCE_POOL_FACTOR,
    IdeationRequest,
    PipelineError,
    ResearchPipeline,
)
from app.provider import ProviderError, ResearchProvider
from app.schemas import Direction, utc_now
from app.synthesis import build_evidence_pack, diversify_by_paper

GHOST_ID = "paper-ddd444000000"


class _FailingProvider(ResearchProvider):
    """Stands in for a strong model that is unreachable mid-run."""

    async def generate_json(
        self, *, system_prompt: str, user_prompt: str, purpose: str
    ) -> dict[str, Any]:
        raise ProviderError("模型不可用（测试注入）")


def _add_ghost_paper(pipeline: ResearchPipeline) -> None:
    """Register a corpus row whose PDF does not exist (a real-corpus case)."""
    template = pipeline.store.get_paper("paper-aaa111000000")
    ghost = template.model_copy(
        update={
            "paper_id": GHOST_ID,
            "title": "Ghost Paper",
            "title_zh": "幽灵论文",
            "category_id": "cat-09",
            "pdf_path": "papers/does-not-exist.pdf",
        }
    )
    pipeline.store.upsert_paper(ghost, pdf_exists=False)


# ---------------- stage guards ----------------


async def test_empty_corpus_blocks_every_stage(pipeline: ResearchPipeline) -> None:
    with pytest.raises(PipelineError):
        pipeline.rebuild_index()
    with pytest.raises(PipelineError) as analysis_error:
        await pipeline.run_deep_analysis()
    with pytest.raises(PipelineError) as ideation_error:
        await pipeline.run_ideation()

    assert "语料库为空" in str(analysis_error.value)
    assert "语料库为空" in str(ideation_error.value)


async def test_unknown_job_id_is_ignored(pipeline: ResearchPipeline) -> None:
    await pipeline.run_ideation_job("job-doesnotexist", IdeationRequest())
    await pipeline.run_corpus_sync_job("job-doesnotexist")

    assert pipeline.store.list_jobs(limit=10) == []


# ---------------- evidence diversification (citation gate) ----------------


def test_focused_query_evidence_spans_two_papers(
    synced_pipeline: ResearchPipeline,
) -> None:
    """Regression: a focused query used to return one paper's chunks only.

    Ideas must cite at least two papers, so a single-paper pack rejected every
    idea and the loop could never produce a direction.
    """
    query = "智能体工具调用的注入防护"
    limit = synced_pipeline.settings.retrieval_top_k

    naive = synced_pipeline.search(query, top_k=limit, mode="hybrid")
    pool = synced_pipeline.search(
        query,
        top_k=max(limit, min(limit * EVIDENCE_POOL_FACTOR, EVIDENCE_POOL_CAP)),
        mode="hybrid",
    )
    pack = build_evidence_pack(query, diversify_by_paper(pool, limit=limit))

    # The raw ranking really is dominated by one paper; the pack is not.
    assert {hit.paper_id for hit in naive if hit.paper_id} == {"paper-bbb222000000"}
    assert len(pack.hits) == limit
    assert len(pack.paper_ids) >= 2


async def test_single_focused_query_still_yields_accepted_ideas(
    synced_pipeline: ResearchPipeline,
) -> None:
    run = await synced_pipeline.run_ideation(
        IdeationRequest(queries=["智能体工具调用的注入防护"], ideas_per_query=2)
    )

    assert run.ideas_total == 2
    assert run.ideas_accepted == 2 and run.ideas_rejected == 0
    assert run.directions_total == 1


# ---------------- the loop itself ----------------


async def test_full_loop_produces_direction_experiment_and_followups(
    synced_pipeline: ResearchPipeline,
) -> None:
    await synced_pipeline.run_deep_analysis(limit=3)
    synced_pipeline.rebuild_index()

    run = await synced_pipeline.run_ideation()

    assert run.status == "succeeded"
    assert run.generation == 1
    assert run.ideas_total == 6
    assert run.ideas_accepted == 2 and run.ideas_rejected == 4
    assert run.ideas_total == run.ideas_accepted + run.ideas_rejected
    assert run.directions_total == 1
    assert run.experiments_total == 1
    assert run.followups_total == 3
    assert run.message == "第 1 代演化完成：2 条想法、1 个方向、1 份实验方案、3 条待办"
    assert synced_pipeline.store.get_meta("last_ideation_batch") == run.batch_id


async def test_accepted_ideas_pass_the_two_paper_citation_gate(
    synced_pipeline: ResearchPipeline,
) -> None:
    run = await synced_pipeline.run_ideation()

    kept = synced_pipeline.store.list_ideas(limit=50)
    assert len(kept) == run.ideas_accepted == 2
    for idea in kept:
        assert idea.rejected_reason == ""
        assert idea.generation == 1
        assert idea.batch_id == run.batch_id
        # The gate itself: cross-paper evidence, every citation inside the corpus.
        assert len(idea.source_paper_ids) >= 2
        assert set(idea.source_paper_ids) <= {
            card.paper_id for card in synced_pipeline.store.list_papers(limit=100)
        }
        assert idea.evidence_refs
        assert idea.critique, "accepted ideas carry the reviewer's scores"

    everything = synced_pipeline.store.list_ideas(limit=50, include_rejected=True)
    assert {idea.id for idea in kept} <= {idea.id for idea in everything}


async def test_direction_experiment_and_followups_are_linked(
    synced_pipeline: ResearchPipeline,
) -> None:
    run = await synced_pipeline.run_ideation()

    directions = synced_pipeline.store.list_directions(limit=10)
    assert len(directions) == run.directions_total == 1
    direction = directions[0]
    assert direction.generation == 1
    assert direction.batch_id == run.batch_id
    assert direction.status == "proposed"
    assert set(direction.member_idea_ids) == {
        idea.id for idea in synced_pipeline.store.list_ideas(limit=50)
    }
    assert direction.source_paper_ids and direction.roadmap and direction.open_risks

    experiments = synced_pipeline.store.list_experiments(limit=10)
    assert [plan.direction_id for plan in experiments] == [direction.id]
    assert experiments[0].objective and experiments[0].protocol_steps

    followups = synced_pipeline.store.list_followups(limit=10)
    assert len(followups) == run.followups_total == 3
    assert {item.direction_id for item in followups} == {direction.id}
    assert {item.experiment_id for item in followups} == {experiments[0].id}
    assert {item.kind for item in followups} == {"paper_to_read", "dataset", "tool"}
    assert all(item.status == "open" and item.reason for item in followups)

    stored_run = synced_pipeline.store.get_run(run.batch_id)
    assert stored_run is not None and stored_run.status == "succeeded"


async def test_generated_content_is_indexed_and_searchable(
    synced_pipeline: ResearchPipeline,
) -> None:
    await synced_pipeline.run_ideation()

    kinds = synced_pipeline.store.chunk_kinds()
    assert kinds["idea.claim"] == 2
    assert kinds["idea.direction"] == 1
    # New content invalidates the index so the next stage re-reads it.
    assert synced_pipeline.store.get_meta("index_stale") == "1"

    hits = synced_pipeline.search("mock 想法", top_k=5)
    assert any(hit.kind in {"idea.claim", "idea.direction"} for hit in hits)


async def test_rebuild_keeps_generated_content(
    synced_pipeline: ResearchPipeline,
) -> None:
    await synced_pipeline.run_ideation()

    stats = synced_pipeline.rebuild_index()

    assert synced_pipeline.store.get_meta("index_stale") == "0"
    assert stats.chunks == synced_pipeline.store.chunk_count()
    assert synced_pipeline.store.chunk_kinds()["idea.claim"] == 2


async def test_second_generation_dedupes_the_first(
    synced_pipeline: ResearchPipeline,
) -> None:
    first = await synced_pipeline.run_ideation()
    second = await synced_pipeline.run_ideation()

    assert first.ideas_accepted == 2
    assert second.generation == 2
    assert second.ideas_accepted == 0
    assert second.ideas_rejected == second.ideas_total == 6
    assert second.directions_total == 0
    assert second.message == "本轮没有通过引用校验的想法，未生成方向。"

    # The generation counter follows directions, so nothing was invented here.
    assert synced_pipeline.store.max_generation() == 1
    kept = synced_pipeline.store.list_ideas(limit=50)
    assert len(kept) == 2
    assert all(idea.generation == 1 and idea.rejected_reason == "" for idea in kept)
    rejected = [
        idea
        for idea in synced_pipeline.store.list_ideas(limit=50, include_rejected=True)
        if idea.rejected_reason
    ]
    assert rejected
    assert all("重复" in idea.rejected_reason for idea in rejected)

    directions = synced_pipeline.store.list_directions(limit=10)
    assert len(directions) == 1 and directions[0].generation == 1


async def test_explicit_generation_keeps_the_parent_link(
    synced_pipeline: ResearchPipeline,
) -> None:
    seed = Direction(
        id="dir-111111111111",
        name="上一代方向",
        generation=1,
        batch_id="batch-seed0000",
        created_at=utc_now(),
    )
    synced_pipeline.store.save_direction(seed)

    run = await synced_pipeline.run_ideation(
        IdeationRequest(generation=2, parent_direction_id=seed.id)
    )

    assert run.generation == 2 and run.ideas_accepted == 2
    children = [
        direction
        for direction in synced_pipeline.store.list_directions(limit=10)
        if direction.id != seed.id
    ]
    assert len(children) == 1
    assert children[0].parent_direction_id == seed.id
    assert children[0].generation == 2
    assert synced_pipeline.store.max_generation() == 2


def test_parent_direction_inference_rules(
    synced_pipeline: ResearchPipeline,
) -> None:
    """Generation N>1 continues the previous generation unless told otherwise."""
    seed = Direction(
        id="dir-222222222222",
        name="第一代方向",
        generation=1,
        batch_id="batch-seed0001",
        created_at=utc_now(),
    )
    synced_pipeline.store.save_direction(seed)

    inferred = synced_pipeline._resolve_parent_direction(IdeationRequest(generation=2), 2)
    assert inferred is not None and inferred.id == seed.id

    # An explicit parent wins, and a bogus one simply resolves to nothing.
    explicit = synced_pipeline._resolve_parent_direction(
        IdeationRequest(generation=2, parent_direction_id="dir-doesnotexist"), 2
    )
    assert explicit is None
    assert synced_pipeline._resolve_parent_direction(IdeationRequest(), 1) is None


async def test_unknown_parent_direction_degrades_to_no_parent(
    synced_pipeline: ResearchPipeline,
) -> None:
    run = await synced_pipeline.run_ideation(
        IdeationRequest(parent_direction_id="dir-doesnotexist")
    )

    assert run.ideas_accepted == 2
    assert all(
        direction.parent_direction_id == ""
        for direction in synced_pipeline.store.list_directions(limit=10)
    )


async def test_progress_events_are_monotonic_and_complete(
    synced_pipeline: ResearchPipeline,
) -> None:
    events: list[tuple[str, int, str]] = []

    await synced_pipeline.run_ideation(
        progress=lambda stage, percent, message: events.append((stage, percent, message))
    )

    stages = [stage for stage, _, _ in events]
    percents = [percent for _, percent, _ in events]
    assert stages[0] == "indexing" and stages[-1] == "succeeded"
    assert set(stages) == {"indexing", "ideating", "clustering", "experiment", "succeeded"}
    assert percents == sorted(percents)
    assert percents[-1] == 100
    assert all(message for _, _, message in events)


# ---------------- deep analysis stage ----------------


async def test_deep_analysis_caches_and_force_recomputes(
    synced_pipeline: ResearchPipeline,
) -> None:
    estimate = synced_pipeline.analysis_estimate(limit=3)
    assert estimate["papers_total"] == 3
    assert estimate["selected"] == 3 and estimate["estimated_model_calls"] == 3

    first = await synced_pipeline.run_deep_analysis(limit=3)
    assert (first.scanned, first.analyzed, first.failed) == (3, 3, 0)
    assert first.prompt_version == ANALYSIS_PROMPT_VERSION

    second = await synced_pipeline.run_deep_analysis(limit=3)
    assert (second.analyzed, second.cached) == (0, 3)

    forced = await synced_pipeline.run_deep_analysis(limit=1, force=True)
    assert (forced.analyzed, forced.cached) == (1, 0)

    after = synced_pipeline.analysis_estimate(limit=3)
    assert after["already_ready"] == 3
    assert after["pending"] == 0 and after["selected"] == 0

    # Regression: a forced run used to announce "0 篇" because the estimate only
    # counted pending papers, then billed for the papers it re-read anyway.
    forced_estimate = synced_pipeline.analysis_estimate(limit=1, force=True)
    assert forced_estimate["force"] is True
    assert forced_estimate["pending"] == 0 and forced_estimate["selected"] == 1
    assert forced_estimate["estimated_model_calls"] == 1


async def test_concurrent_pdf_extraction_does_not_fail_the_batch(
    synced_pipeline: ResearchPipeline,
) -> None:
    """Regression: concurrency=2 used to fail every paper but the first.

    The reading platform's pdf_utils module was handed out half-initialized to
    the other worker threads (see app/interop.py).
    """
    assert synced_pipeline.settings.analysis_concurrency == 2

    summary = await synced_pipeline.run_deep_analysis(limit=3)

    assert summary.failed == 0 and summary.errors == []
    assert summary.analyzed == 3
    records = synced_pipeline.store.list_deep_analyses(limit=10)
    assert len(records) == 3
    assert all(record.status == "ready" for record in records)
    assert all(record.innovations for record in records)


async def test_paper_without_a_readable_pdf_is_skipped(
    synced_pipeline: ResearchPipeline,
) -> None:
    _add_ghost_paper(synced_pipeline)

    summary = await synced_pipeline.run_deep_analysis()

    assert summary.scanned == 4
    assert summary.skipped_no_pdf == 1
    assert summary.analyzed == 3 and summary.failed == 0

    record = synced_pipeline.store.get_deep_analysis(GHOST_ID, ANALYSIS_PROMPT_VERSION)
    assert record is not None and record.status == "failed"
    assert "PDF 不可读" in record.error
    card = synced_pipeline.store.get_paper(GHOST_ID)
    assert card.deep_analysis_status == "failed"


# ---------------- isolation & status ----------------


async def test_status_reports_read_only_reading_platform_access(
    synced_pipeline: ResearchPipeline, settings: ResearchSettings
) -> None:
    await synced_pipeline.run_ideation()

    status = synced_pipeline.status()

    assert status.reading_platform_writes == 0
    assert status.paper_database == str(settings.paper_database_path)
    assert status.paper_database_readable is True
    assert status.provider == "mock" and status.model == "mock-research"
    assert status.model_configured is True
    assert status.papers_indexed == 3
    assert (status.ideas, status.directions, status.experiments) == (2, 1, 1)
    assert status.generations == 1
    # The research service keeps its own database; the reading platform's is untouched.
    assert status.paper_database.endswith("storage/api/library.sqlite3")
    assert settings.database_path.name == "research.sqlite3"


# ---------------- job wrappers ----------------


async def test_successful_job_carries_the_run_result(
    synced_pipeline: ResearchPipeline,
) -> None:
    job = synced_pipeline.create_job(
        "ideation", message="离线自测", batch_id="batch-job00001"
    )
    assert job.status == "queued"

    await synced_pipeline.run_ideation_job(
        job.id, IdeationRequest(batch_id="batch-job00001")
    )

    stored = synced_pipeline.store.get_job(job.id)
    assert stored.status == "succeeded" and stored.stage == "succeeded"
    assert stored.progress == 100 and stored.error == ""
    assert stored.result is not None and stored.result.phase == "ideation"
    assert stored.result.detail["ideas_accepted"] == 2
    assert stored.result.detail["directions_total"] == 1
    assert "第 1 代演化完成" in stored.message


async def test_failed_job_records_the_reason(
    pipeline: ResearchPipeline,
) -> None:
    job = pipeline.create_job("ideation", message="离线自测")

    await pipeline.run_ideation_job(job.id, IdeationRequest())

    stored = pipeline.store.get_job(job.id)
    assert stored.status == "failed" and stored.stage == "failed"
    assert "语料库为空" in stored.error
    assert stored.message == "执行失败"


async def test_failed_job_marks_its_run_failed(settings: ResearchSettings) -> None:
    """A run row left in `running` would look stuck in the UI forever."""
    pipeline = ResearchPipeline(settings=settings, provider=_FailingProvider())
    pipeline.sync_corpus()
    pipeline.rebuild_index()
    job = pipeline.create_job(
        "ideation", message="离线自测", batch_id="batch-willfail"
    )

    await pipeline.run_ideation_job(job.id, IdeationRequest(batch_id=job.batch_id))

    stored = pipeline.store.get_job(job.id)
    assert stored.status == "failed"
    assert "模型不可用" in stored.error

    run = pipeline.store.get_run(job.batch_id)
    assert run is not None
    assert run.status == "failed"
    assert "模型不可用" in run.message
