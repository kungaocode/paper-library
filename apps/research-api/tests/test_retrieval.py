"""Stage C retrieval: hybrid fusion, mode fallbacks, backend selection."""

from __future__ import annotations

import dataclasses

import pytest

from app.config import ResearchSettings
from app.embeddings import HashingEmbedder
from app.pipeline import PipelineError, ResearchPipeline
from app.provider import MockResearchProvider
from app.retrieval import (
    KnowledgeVectorBackend,
    RetrievalError,
    SqliteHybridBackend,
    build_backend,
)
from app.store import ResearchStore

QUERY = "越狱成功率 与 安全 token 约束"


def _store(settings: ResearchSettings) -> ResearchStore:
    settings.ensure_directories()
    return ResearchStore(settings.database_path)


def _indexed(settings: ResearchSettings) -> ResearchPipeline:
    pipeline = ResearchPipeline(settings=settings, provider=MockResearchProvider())
    pipeline.sync_corpus()
    pipeline.rebuild_index()
    return pipeline


def test_all_three_modes_return_ranked_hits(settings: ResearchSettings) -> None:
    pipeline = _indexed(settings)

    for mode in ("hybrid", "lexical", "vector"):
        hits = pipeline.search(QUERY, mode=mode)
        assert hits, f"{mode} 模式应返回命中"
        scores = [hit.score for hit in hits]
        assert scores == sorted(scores, reverse=True), f"{mode} 结果应按分数降序"
        assert all(hit.chunk_id and hit.text for hit in hits)
        assert len(hits) <= settings.retrieval_top_k


def test_hybrid_carries_both_sub_scores(settings: ResearchSettings) -> None:
    pipeline = _indexed(settings)

    hits = pipeline.search(QUERY, mode="hybrid")
    fused = [hit for hit in hits if hit.lexical_score is not None and hit.vector_score is not None]
    assert fused, "hybrid 至少应有一条同时具备词法与向量分数的结果"
    # Category-level chunks have no owning paper; the title lookup must not crash.
    assert any(hit.paper_id == "" for hit in hits) or all(hit.paper_id for hit in hits)
    for hit in hits:
        if hit.paper_id:
            assert hit.paper_title


def test_lexical_weight_shifts_ranking(settings: ResearchSettings) -> None:
    lexical_first = ResearchPipeline(settings=settings, provider=MockResearchProvider())
    lexical_first.sync_corpus()
    lexical_first.rebuild_index()
    lexical_top = [hit.chunk_id for hit in lexical_first.search(QUERY, mode="lexical", top_k=3)]
    vector_top = [hit.chunk_id for hit in lexical_first.search(QUERY, mode="vector", top_k=3)]

    assert lexical_top and vector_top
    # The two signals disagree somewhere, which is the point of fusing them.
    assert lexical_top != vector_top

    hybrid_top = [hit.chunk_id for hit in lexical_first.search(QUERY, mode="hybrid", top_k=3)]
    assert hybrid_top != lexical_top or hybrid_top != vector_top


def test_empty_and_unknown_queries_are_safe(settings: ResearchSettings) -> None:
    pipeline = _indexed(settings)

    assert pipeline.search("   ") == []
    # Lexical search has no match at all, so it returns nothing.
    assert pipeline.search("zzzz-不存在的词-zzzz", mode="lexical") == []
    # Vector search is dense: it always yields nearest neighbours, but an
    # unrelated query must score clearly below a real one.
    unrelated = pipeline.search("zzzz-不存在的词-zzzz", mode="vector")
    related = pipeline.search(QUERY, mode="vector")
    assert unrelated
    assert max(hit.vector_score or 0 for hit in unrelated) < max(
        hit.vector_score or 0 for hit in related
    )


def test_invalid_mode_raises_pipeline_error(settings: ResearchSettings) -> None:
    pipeline = _indexed(settings)

    with pytest.raises(PipelineError) as error:
        pipeline.search(QUERY, mode="semantic")
    assert "不支持的检索模式" in str(error.value)


def test_top_k_is_respected(settings: ResearchSettings) -> None:
    pipeline = _indexed(settings)

    assert len(pipeline.search(QUERY, top_k=2)) <= 2
    assert len(pipeline.search(QUERY, top_k=200)) <= 200


def test_embed_missing_chunks_is_idempotent(settings: ResearchSettings) -> None:
    pipeline = _indexed(settings)
    backend = pipeline.backend
    assert isinstance(backend, SqliteHybridBackend)

    # Everything was embedded during rebuild, so there is nothing left to do.
    assert backend.embed_missing_chunks() == 0

    stored = pipeline.store
    chunks = stored.chunks_without_vectors(backend.embedder.name)
    assert chunks == []

    # A brand-new chunk gets picked up on the next pass, and only once.
    stored.replace_chunks_by_kind(
        "test.extra",
        [
            (
                "chunk-extra-1",
                {
                    "paper_id": "",
                    "category_id": "",
                    "kind": "test.extra",
                    "ordinal": 0,
                    "text": "额外切片：用于验证增量向量化",
                    "page_number": None,
                    "metadata": {},
                },
            )
        ],
    )
    assert backend.embed_missing_chunks() == 1
    assert backend.embed_missing_chunks() == 0


def test_dimension_mismatch_reports_a_readable_error(
    settings: ResearchSettings,
) -> None:
    pipeline = _indexed(settings)
    mismatched = SqliteHybridBackend(
        pipeline.store, settings, embedder=HashingEmbedder(dim=16)
    )

    with pytest.raises(RetrievalError) as error:
        mismatched.search(QUERY, mode="vector")
    assert "向量维度不一致" in str(error.value)
    assert "重建索引" in str(error.value)


def test_stats_describe_the_index(settings: ResearchSettings) -> None:
    pipeline = _indexed(settings)
    stats = pipeline.index_stats()

    assert stats.backend == "builtin-sqlite-hybrid"
    assert stats.embedding_model == "hashing-v1-384"
    assert stats.papers == 3
    assert stats.chunks > 0
    assert stats.chunks == pipeline.store.chunk_count()
    assert stats.categories >= 1
    assert stats.updated_at


def test_rebuild_on_empty_corpus_raises(settings: ResearchSettings) -> None:
    pipeline = ResearchPipeline(settings=settings, provider=MockResearchProvider())

    with pytest.raises(PipelineError) as error:
        pipeline.rebuild_index()
    assert "语料库为空" in str(error.value)


def test_knowledge_vector_backend_falls_back_with_notice(
    settings: ResearchSettings, tmp_path
) -> None:
    """The user's vector library is not wired yet: degrade, do not crash."""
    missing = dataclasses.replace(
        settings,
        retrieval_backend="knowledge_vector",
        knowledge_vector_root=str(tmp_path / "not-here"),
    )
    backend, notice = build_backend(_store(settings), missing)

    assert isinstance(backend, SqliteHybridBackend)
    assert "已降级到内置后端" in notice
    assert "KNOWLEDGE_VECTOR_ROOT 不存在" in notice


def test_knowledge_vector_backend_rejects_unusable_root(
    settings: ResearchSettings, tmp_path
) -> None:
    broken = dataclasses.replace(
        settings,
        retrieval_backend="knowledge_vector",
        knowledge_vector_root=str(tmp_path),
    )

    with pytest.raises(RetrievalError) as error:
        KnowledgeVectorBackend(broken)
    assert "knowledge_vector" in str(error.value)


def test_knowledge_vector_available_flag(settings: ResearchSettings, tmp_path) -> None:
    pipeline = ResearchPipeline(settings=settings, provider=MockResearchProvider())
    assert pipeline.knowledge_vector_available() is False

    project = tmp_path / "vector_library"
    (project / "src" / "knowledge_vector").mkdir(parents=True)
    wired = dataclasses.replace(
        settings, knowledge_vector_root=str(project), retrieval_backend="knowledge_vector"
    )
    wired_pipeline = ResearchPipeline(settings=wired, provider=MockResearchProvider())

    assert wired_pipeline.knowledge_vector_available() is True
    # Still no real library importable, so the backend degraded.
    assert isinstance(wired_pipeline.backend, SqliteHybridBackend)
    assert wired_pipeline.backend_notice


def test_default_backend_is_builtin(settings: ResearchSettings) -> None:
    backend, notice = build_backend(_store(settings), settings)

    assert isinstance(backend, SqliteHybridBackend)
    assert notice == ""
