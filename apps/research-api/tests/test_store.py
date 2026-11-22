"""Own-database persistence: round-trips, index isolation, migration."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from app.chunking import build_category_chunks, build_paper_chunks
from app.config import ResearchSettings
from app.corpus import PaperLibraryReader
from app.schemas import (
    DeepAnalysisRecord,
    Direction,
    ExperimentPlan,
    FollowupItem,
    Idea,
    IdeationRun,
    ResearchJob,
    utc_now,
)
from app.store import ResearchStore, StoreError


def _cards(settings: ResearchSettings):
    return PaperLibraryReader(settings).load_cards()


def _idea(idea_id: str = "idea-aaaaaaaaaaaa", **overrides) -> Idea:
    payload = {
        "id": idea_id,
        "title": "跨论文整合的想法",
        "hypothesis": "假设可证伪",
        "source_paper_ids": ["paper-aaa111000000", "paper-bbb222000000"],
        "category_ids": ["cat-01", "cat-04"],
        "confidence": 0.7,
        "generation": 1,
        "batch_id": "batch-test",
        "created_at": utc_now(),
    }
    payload.update(overrides)
    return Idea(**payload)


def test_schema_is_created_and_migration_is_additive(tmp_path: Path) -> None:
    db_path = tmp_path / "research.sqlite3"
    # Simulate a database created before summary_json existed.
    legacy = sqlite3.connect(db_path)
    legacy.execute(
        "CREATE TABLE corpus_papers (paper_id TEXT PRIMARY KEY, title TEXT NOT NULL, "
        "synced_at TEXT NOT NULL)"
    )
    legacy.execute(
        "INSERT INTO corpus_papers VALUES ('paper-old', 'Old', '2026-01-01T00:00:00+00:00')"
    )
    legacy.commit()
    legacy.close()

    store = ResearchStore(db_path)
    columns = {
        row[1]
        for row in sqlite3.connect(db_path).execute("PRAGMA table_info(corpus_papers)")
    }
    assert "summary_json" in columns
    # The pre-existing row survives the migration.
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT summary_json FROM corpus_papers WHERE paper_id='paper-old'"
        ).fetchone()
    assert row[0] == "{}"
    assert store.count_papers() == 1  # the pre-existing row is still readable


def test_missing_fts5_raises_store_error(monkeypatch, tmp_path: Path) -> None:
    import app.store as store_module

    monkeypatch.setattr(store_module, "_fts_available", lambda connection: False)
    with pytest.raises(StoreError):
        ResearchStore(tmp_path / "nofts.sqlite3")


def test_upsert_paper_lifecycle(store: ResearchStore, settings: ResearchSettings) -> None:
    cards = _cards(settings)
    first = next(card for card in cards if card.paper_id == "paper-aaa111000000")

    assert store.upsert_paper(first, pdf_exists=True) == "created"
    assert store.upsert_paper(first, pdf_exists=True) == "unchanged"

    changed = first.model_copy(update={"novelty_zh": "更新后的创新点", "fingerprint": "new"})
    assert store.upsert_paper(changed, pdf_exists=False) == "updated"

    stored = store.get_paper("paper-aaa111000000")
    assert stored is not None
    assert stored.novelty_zh == "更新后的创新点"
    assert store.get_paper("paper-nope") is None


def test_upsert_keeps_deep_analysis_status(store: ResearchStore, settings) -> None:
    card = _cards(settings)[0]
    store.upsert_paper(card, pdf_exists=True)
    store.set_deep_analysis_status(card.paper_id, "failed")

    store.upsert_paper(card.model_copy(update={"fingerprint": "changed"}), pdf_exists=True)

    assert store.get_paper(card.paper_id).deep_analysis_status == "failed"


def test_paper_round_trip_keeps_shallow_extraction(
    store: ResearchStore, settings: ResearchSettings
) -> None:
    """The library's existing extraction must survive the copy into our DB."""
    for card in _cards(settings):
        store.upsert_paper(card, pdf_exists=True)

    stored = store.get_paper("paper-aaa111000000")
    assert stored.problem == "全量对齐训练代价高且损害通用能力。"
    assert stored.method
    assert stored.findings == ["越狱成功率下降 41%", "通用基准损失小于 2%"]
    assert stored.limitations == ["依赖标注器质量"]
    assert stored.innovations[0].claim == "把安全性建模为稀疏 token 属性"
    assert stored.innovations[0].evidence_pages == [3]
    assert stored.innovations[0].evidence_quotes
    assert stored.needs_deep_analysis is False
    assert stored.thesis_zh
    assert stored.authors == ["Wei Chen", "Lin Zhao"]

    # Chunks built from the stored card carry the innovations, no model needed.
    kinds = {row["kind"] for _, row in build_paper_chunks(stored)}
    assert {"paper.thesis", "paper.novelty", "paper.innovation", "paper.finding"} <= kinds


def test_list_and_category_filters(store: ResearchStore, settings) -> None:
    for card in _cards(settings):
        store.upsert_paper(card, pdf_exists=True)

    assert store.count_papers() == 3
    assert len(store.list_papers()) == 3
    assert [c.paper_id for c in store.list_papers(category_id="cat-04")] == ["paper-bbb222000000"]
    assert len(store.list_papers(limit=2)) == 2

    counts = {row["category_id"]: row for row in store.category_counts()}
    assert counts["cat-01"]["papers"] == 1
    assert counts["cat-01"]["category_name"]

    titles = store.paper_titles(["paper-aaa111000000", "paper-aaa111000000", "", "paper-nope"])
    assert titles == {"paper-aaa111000000": "细粒度对齐使安全性成为稀疏token属性"}
    assert store.paper_titles([]) == {}


def test_chunk_replacement_is_scoped(store: ResearchStore, settings) -> None:
    cards = {card.paper_id: card for card in _cards(settings)}
    for card in cards.values():
        store.upsert_paper(card, pdf_exists=True)

    store.replace_paper_chunks(
        "paper-aaa111000000", build_paper_chunks(cards["paper-aaa111000000"])
    )
    store.replace_paper_chunks(
        "paper-bbb222000000", build_paper_chunks(cards["paper-bbb222000000"])
    )
    store.replace_chunks_by_kind(
        "category.positioning",
        build_category_chunks({"cat-01": "定位一", "cat-04": "定位四"}, {}),
    )

    before = store.chunk_count()
    kinds = store.chunk_kinds()
    assert kinds["category.positioning"] == 2
    assert store.distinct_chunk_categories() == 2

    # Rebuilding one paper must not touch the others or the corpus-level layer.
    store.replace_paper_chunks(
        "paper-aaa111000000", build_paper_chunks(cards["paper-aaa111000000"])
    )
    assert store.chunk_count() == before
    assert store.chunk_kinds()["category.positioning"] == 2

    store.replace_chunks_by_kind("category.positioning", [])
    assert store.chunk_count() == before - 2
    assert "category.positioning" not in store.chunk_kinds()

    store.clear_index()
    assert store.chunk_count() == 0
    assert store.load_vector_matrix() == ([], [])


def test_vectors_round_trip(store: ResearchStore, settings) -> None:
    cards = _cards(settings)
    store.upsert_paper(cards[0], pdf_exists=True)
    chunks = build_paper_chunks(cards[0])
    store.replace_paper_chunks(cards[0].paper_id, chunks)

    missing = store.chunks_without_vectors("hashing-v1-384")
    assert len(missing) == len(chunks)

    vector = np.arange(384, dtype=np.float32) / 384.0
    store.save_vectors(
        [(chunk_id, vector.tobytes(), "hashing-v1-384", 384) for chunk_id, _ in chunks]
    )
    assert store.chunks_without_vectors("hashing-v1-384") == []
    assert len(store.chunks_without_vectors("other-model")) == len(chunks)

    ids, matrix = store.load_vector_matrix()
    assert len(ids) == len(chunks)
    assert np.allclose(np.stack(matrix)[0], vector)

    store.replace_paper_chunks(cards[0].paper_id, [])
    # Chunk replacement cascades: a paper's vectors go away with its chunks.
    assert store.load_vector_matrix() == ([], [])
    assert store.delete_orphan_vectors() == 0

    # A vector whose chunk disappeared some other way (crash mid-rebuild) is
    # still caught by the orphan sweep.
    store.replace_paper_chunks(cards[0].paper_id, chunks)
    store.save_vectors(
        [(chunk_id, vector.tobytes(), "hashing-v1-384", 384) for chunk_id, _ in chunks]
    )
    assert len(store.chunks_without_vectors("hashing-v1-384")) == 0
    with sqlite3.connect(settings.database_path) as connection:
        connection.execute("DELETE FROM chunks")
    assert store.delete_orphan_vectors() == len(chunks)
    assert store.load_vector_matrix() == ([], [])


def test_lexical_candidates(store: ResearchStore, settings) -> None:
    cards = {card.paper_id: card for card in _cards(settings)}
    for card in cards.values():
        store.upsert_paper(card, pdf_exists=True)
        store.replace_paper_chunks(card.paper_id, build_paper_chunks(card))

    hits = store.lexical_candidates("越狱成功率", 10)
    assert hits
    assert all(hit["lexical_score"] >= 0 for hit in hits)
    assert "paper-aaa111000000" in {hit["paper_id"] for hit in hits}

    # Short queries fall back to substring counting instead of FTS MATCH.
    assert store.lexical_candidates("安全", 10)
    assert store.lexical_candidates("", 10) == []
    assert store.lexical_candidates("zzzz-not-present", 10) == []
    # SQL metacharacters must not break the LIKE fallback.
    assert isinstance(store.lexical_candidates("100% _ \\", 10), list)


def test_deep_analysis_records(store: ResearchStore) -> None:
    record = DeepAnalysisRecord(
        id="deep-paper-aaa111000000-v1",
        paper_id="paper-aaa111000000",
        paper_title="细粒度对齐",
        prompt_version="v1",
        status="ready",
        problem="深度问题",
        method="深度方法",
        findings=["发现一"],
        innovations=[{"claim": "深度创新点", "evidence_pages": [2], "evidence_quotes": []}],
        limitations=["局限"],
        model="mock-research",
        created_at=utc_now(),
    )
    store.save_deep_analysis(record)

    loaded = store.get_deep_analysis("paper-aaa111000000", "v1")
    assert loaded.problem == "深度问题"
    assert loaded.innovations[0].claim == "深度创新点"
    assert loaded.innovations[0].evidence_pages == [2]
    assert store.get_deep_analysis("paper-aaa111000000", "v2") is None

    store.save_deep_analysis(
        DeepAnalysisRecord(
            id="deep-paper-bbb222000000-v1",
            paper_id="paper-bbb222000000",
            prompt_version="v1",
            status="failed",
            error="模型接口返回 500",
            created_at=utc_now(),
        )
    )
    assert store.deep_analysis_count("ready") == 1
    assert store.deep_analysis_count("failed") == 1
    assert len(store.list_deep_analyses(prompt_version="v1")) == 2
    assert len(store.list_deep_analyses(status="ready")) == 1
    assert len(store.list_deep_analyses(prompt_version="v9")) == 0


def test_ideas_and_directions(store: ResearchStore) -> None:
    accepted = _idea("idea-accepted01", confidence=0.8)
    rejected = _idea(
        "idea-rejected01", confidence=0.9, rejected_reason="引用校验失败"
    )
    store.save_idea(accepted)
    store.save_idea(rejected)

    assert store.idea_count() == 1
    assert store.idea_count(include_rejected=True) == 2
    listed = store.list_ideas(include_rejected=True)
    assert {idea.id for idea in listed} == {"idea-accepted01", "idea-rejected01"}
    assert store.list_ideas()[0].id == "idea-accepted01"
    assert store.list_ideas(batch_id="batch-test")[0].source_paper_ids == [
        "paper-aaa111000000",
        "paper-bbb222000000",
    ]
    assert store.list_ideas(batch_id="batch-nope") == []
    assert store.list_ideas(generation=2) == []
    assert store.list_ideas()[0].critique == {}

    store.save_idea(accepted.model_copy(update={"confidence": 0.35, "critique": {"score": 0.4}}))
    reloaded = store.list_ideas()[0]
    assert reloaded.confidence == 0.35
    assert reloaded.critique == {"score": 0.4}

    direction = Direction(
        id="dir-first0001",
        name="决策点安全约束",
        question="能否统一训练期与运行时约束？",
        member_idea_ids=["idea-accepted01"],
        source_paper_ids=["paper-aaa111000000"],
        roadmap=["第一步", "第二步"],
        priority=0.8,
        generation=1,
        batch_id="batch-test",
        created_at=utc_now(),
    )
    store.save_direction(direction)
    assert store.direction_count() == 1
    assert store.max_generation() == 1
    assert store.get_direction("dir-first0001").roadmap == ["第一步", "第二步"]
    assert store.get_direction("dir-nope") is None
    assert store.list_directions(generation=1)[0].name == "决策点安全约束"
    assert store.list_directions(generation=5) == []

    store.save_direction(direction.model_copy(update={"id": "dir-second01", "generation": 2}))
    assert store.max_generation() == 2
    assert store.list_directions()[0].generation == 2  # newest generation first


def test_experiments_and_followups(store: ResearchStore) -> None:
    plan = ExperimentPlan(
        id="exp-first0001",
        direction_id="dir-first0001",
        direction_name="决策点安全约束",
        objective="验证假设",
        datasets=["AgentHarm"],
        baselines=["无约束微调"],
        metrics=["ASR"],
        protocol_steps=["步骤一"],
        result_metrics={"asr": 0.12},
        generation=1,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    store.save_experiment(plan)
    assert store.experiment_count() == 1
    loaded = store.get_experiment("exp-first0001")
    assert loaded.datasets == ["AgentHarm"]
    assert loaded.result_metrics == {"asr": 0.12}
    assert loaded.status == "draft"
    assert store.get_experiment("exp-nope") is None
    assert store.list_experiments()[0].id == "exp-first0001"

    store.save_experiment(plan.model_copy(update={"status": "done", "result_summary": "完成"}))
    assert store.experiment_count() == 1
    assert store.get_experiment("exp-first0001").status == "done"

    followup = FollowupItem(
        id="fu-first00001",
        direction_id="dir-first0001",
        experiment_id="exp-first0001",
        kind="paper_to_read",
        query="agent decision token safety",
        reason="需要确认已有工作",
        suggested_action="交给阅读平台导入",
        created_at=utc_now(),
    )
    store.save_followup(followup)
    assert store.followup_count() == 1
    assert store.list_followups(status="open")[0].query == followup.query
    assert store.list_followups(status="done") == []

    assert store.update_followup_status("fu-first00001", "done") is True
    assert store.list_followups(status="done")[0].id == "fu-first00001"
    assert store.update_followup_status("fu-nope", "done") is False


def test_runs_and_jobs(store: ResearchStore) -> None:
    run = IdeationRun(
        batch_id="batch-run01",
        status="running",
        generation=1,
        provider="mock",
        model="mock-research",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    store.save_run(run)
    store.save_run(run.model_copy(update={"ideas_accepted": 2}))
    finished = run.model_copy(
        update={"batch_id": "batch-done01", "status": "succeeded"}
    )
    store.save_run(finished)
    assert len(store.list_runs()) == 2
    assert store.get_run("batch-run01").ideas_accepted == 2
    assert store.get_run("batch-nope") is None

    job = ResearchJob(
        id="job-running01",
        job_type="ideation",
        status="running",
        progress=40,
        stage="ideating",
        message="生成中",
        batch_id="batch-run01",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    store.save_job(job)
    store.save_job(
        ResearchJob(
            id="job-queued001",
            job_type="corpus_sync",
            status="queued",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )
    assert store.get_job("job-running01").progress == 40
    assert store.get_job("job-nope") is None
    assert len(store.list_jobs()) == 2

    # A restart must not leave jobs stuck in running/queued forever.
    assert store.mark_interrupted_jobs() == 2
    assert all(item.status == "failed" for item in store.list_jobs())
    assert store.get_run("batch-run01").status == "failed"
    # An already finished run is left alone.
    assert store.get_run("batch-done01").status == "succeeded"
    assert store.mark_interrupted_jobs() == 0


def test_meta(store: ResearchStore) -> None:
    assert store.get_meta("missing") == ""
    assert store.get_meta("missing", "fallback") == "fallback"
    store.set_meta("index_stale", "1")
    assert store.get_meta("index_stale") == "1"
    store.set_meta("index_stale", "0")
    assert store.get_meta("index_stale") == "0"
