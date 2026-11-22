from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from .config import ResearchSettings
from .embeddings import HashingEmbedder, stack_matrix
from .schemas import IndexStats, SearchHit
from .store import ResearchStore


class RetrievalError(RuntimeError):
    pass


class RetrievalBackend(Protocol):
    name: str

    def search(
        self, query: str, *, top_k: int = 8, mode: str = "hybrid"
    ) -> list[SearchHit]: ...

    def stats(self) -> IndexStats: ...


class SqliteHybridBackend:
    """Built-in backend: FTS5 trigram lexical scores fused with vector cosine."""

    name = "builtin-sqlite-hybrid"

    def __init__(
        self,
        store: ResearchStore,
        settings: ResearchSettings,
        embedder: HashingEmbedder | None = None,
    ) -> None:
        self.store = store
        self.settings = settings
        self.embedder = embedder or HashingEmbedder()
        self._matrix: np.ndarray | None = None
        self._ids: list[str] = []
        self._cache_version = -1

    # -------- indexing --------

    def embed_missing_chunks(self) -> int:
        """Compute and persist vectors for chunks that do not have one yet."""
        missing = self.store.chunks_without_vectors(self.embedder.name)
        if not missing:
            return 0
        vectors = self.embedder.embed_documents(
            [row["text"] for row in missing]
        )
        self.store.save_vectors(
            (
                (
                    row["chunk_id"],
                    np.ascontiguousarray(vector, dtype=np.float32).tobytes(),
                    self.embedder.name,
                    int(vector.shape[0]),
                )
                for row, vector in zip(missing, vectors)
            )
        )
        return len(missing)

    def _ensure_matrix(self) -> np.ndarray:
        if (
            self._matrix is not None
            and self._cache_version == self.store.vector_cache_version
        ):
            return self._matrix
        ids, vectors = self.store.load_vector_matrix()
        self._ids = ids
        self._matrix = stack_matrix(vectors)
        self._cache_version = self.store.vector_cache_version
        return self._matrix

    # -------- search --------

    def search(
        self, query: str, *, top_k: int = 8, mode: str = "hybrid"
    ) -> list[SearchHit]:
        query = (query or "").strip()
        if not query:
            return []
        top_k = max(1, min(top_k, 200))
        candidate_k = max(self.settings.retrieval_candidate_k, top_k * 3)

        lexical: list[dict[str, Any]] = []
        vector: list[dict[str, Any]] = []
        if mode in {"hybrid", "lexical"}:
            lexical = self.store.lexical_candidates(query, candidate_k)
        if mode in {"hybrid", "vector"}:
            vector = self._vector_candidates(query, candidate_k)

        if mode == "lexical":
            ranked = _score_single(lexical, "lexical_score")
        elif mode == "vector":
            ranked = _score_single(vector, "vector_score")
        else:
            ranked = _fuse(lexical, vector, self.settings.lexical_weight)

        top = ranked[:top_k]
        details = self.store.get_chunks([item["chunk_id"] for item in top])
        # Ranked rows only carry chunk_id plus scores; paper identity comes from
        # the chunk detail, so look the titles up from there.
        titles = self.store.paper_titles(
            details[item["chunk_id"]]["paper_id"]
            for item in top
            if item["chunk_id"] in details
        )

        hits: list[SearchHit] = []
        for item in top:
            detail = details.get(item["chunk_id"])
            if not detail:
                continue
            paper_id = detail["paper_id"]
            hits.append(
                SearchHit(
                    chunk_id=detail["chunk_id"],
                    paper_id=paper_id,
                    paper_title=titles.get(paper_id, ""),
                    category_id=detail["category_id"],
                    kind=detail["kind"],
                    text=detail["text"],
                    score=round(float(item["score"]), 5),
                    lexical_score=_round_or_none(item.get("lexical_score")),
                    vector_score=_round_or_none(item.get("vector_score")),
                    page_number=detail["page_number"],
                )
            )
        return hits

    def _vector_candidates(self, query: str, limit: int) -> list[dict[str, Any]]:
        matrix = self._ensure_matrix()
        if matrix.size == 0 or not self._ids:
            return []
        query_vector = self.embedder.embed_query(query)
        if query_vector.shape[0] != matrix.shape[1]:
            raise RetrievalError(
                f"向量维度不一致：查询 {query_vector.shape[0]} vs 索引 {matrix.shape[1]}。"
                "请重建索引（POST /api/research/index/rebuild）。"
            )
        scores = matrix @ query_vector
        count = min(int(limit), len(self._ids))
        top_indexes = np.argpartition(-scores, count - 1)[:count]
        top_indexes = top_indexes[np.argsort(-scores[top_indexes])]
        return [
            {
                "chunk_id": self._ids[index],
                "vector_score": float(scores[index]),
            }
            for index in top_indexes
        ]

    def stats(self) -> IndexStats:
        return IndexStats(
            backend=self.name,
            embedding_model=self.embedder.name,
            papers=self.store.count_papers(),
            chunks=self.store.chunk_count(),
            categories=self.store.distinct_chunk_categories(),
            updated_at=self.store.get_meta("index_updated_at"),
        )


def _round_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 5)
    except (TypeError, ValueError):
        return None


def _normalize(values: list[dict[str, Any]], key: str) -> dict[str, float]:
    scores = [float(item[key]) for item in values if item.get(key) is not None]
    if not scores:
        return {}
    low, high = min(scores), max(scores)
    if high - low < 1e-9:
        return {item["chunk_id"]: 1.0 for item in values}
    return {
        item["chunk_id"]: (float(item[key]) - low) / (high - low)
        for item in values
        if item.get(key) is not None
    }


def _score_single(values: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    normalized = _normalize(values, key)
    out = []
    for item in values:
        entry = dict(item)
        entry["score"] = normalized.get(item["chunk_id"], 0.0)
        out.append(entry)
    return sorted(out, key=lambda row: row["score"], reverse=True)


def _fuse(
    lexical: list[dict[str, Any]],
    vector: list[dict[str, Any]],
    lexical_weight: float,
) -> list[dict[str, Any]]:
    lexical_scores = _normalize(lexical, "lexical_score")
    vector_scores = _normalize(vector, "vector_score")
    vector_weight = 1.0 - lexical_weight

    merged: dict[str, dict[str, Any]] = {}
    for item in lexical:
        merged.setdefault(item["chunk_id"], {})["lexical_score"] = item["lexical_score"]
    for item in vector:
        merged.setdefault(item["chunk_id"], {})["vector_score"] = item["vector_score"]

    fused: list[dict[str, Any]] = []
    for chunk_id, parts in merged.items():
        lexical_part = lexical_scores.get(chunk_id, 0.0)
        vector_part = vector_scores.get(chunk_id, 0.0)
        fused.append(
            {
                "chunk_id": chunk_id,
                "lexical_score": parts.get("lexical_score"),
                "vector_score": parts.get("vector_score"),
                "score": lexical_weight * lexical_part + vector_weight * vector_part,
            }
        )
    return sorted(fused, key=lambda row: row["score"], reverse=True)


class KnowledgeVectorBackend:
    """Adapter that delegates to the user's `knowledge_vector` project.

    Activation requires KNOWLEDGE_VECTOR_ROOT (project dir containing `src/`).
    When the project is unavailable the factory falls back to the builtin
    backend, so the research pipeline never hard-depends on it yet.
    """

    name = "knowledge_vector"

    def __init__(self, settings: ResearchSettings) -> None:
        self.settings = settings
        root = Path(settings.knowledge_vector_root).expanduser()
        if not root.is_dir():
            raise RetrievalError(f"KNOWLEDGE_VECTOR_ROOT 不存在：{root}")
        for candidate in (root / "src", root):
            entry = str(candidate)
            if entry not in sys.path:
                sys.path.append(entry)
        try:
            from knowledge_vector.config import (  # type: ignore[import-not-found]
                RetrievalConfig,
            )
            from knowledge_vector.retrieval import (  # type: ignore[import-not-found]
                SearchEngine,
            )
            from knowledge_vector.store import (  # type: ignore[import-not-found]
                SQLiteStore,
            )
        except Exception as error:
            raise RetrievalError(
                f"无法导入 knowledge_vector：{error}. 请确认该项目已安装或设置 "
                "KNOWLEDGE_VECTOR_ROOT 指向包含 src/ 的目录。"
            ) from error

        db_path = settings.knowledge_vector_db or str(
            root / ".knowledge-vector" / "index.sqlite3"
        )
        if not Path(db_path).is_file():
            raise RetrievalError(f"knowledge_vector 数据库不存在：{db_path}")

        self._store = SQLiteStore(Path(db_path))
        self._config = RetrievalConfig(top_k=settings.retrieval_top_k)
        self._engine = SearchEngine(self._store, None, self._config)
        self._SearchEngine = SearchEngine
        self._RetrievalConfig = RetrievalConfig

    def search(
        self, query: str, *, top_k: int = 8, mode: str = "hybrid"
    ) -> list[SearchHit]:
        query = (query or "").strip()
        if not query:
            return []
        try:
            results = self._engine.search(
                query, top_k=top_k, mode="lexical" if mode == "hybrid" else mode
            )
        except Exception as error:
            raise RetrievalError(f"knowledge_vector 检索失败：{error}") from error
        return [
            SearchHit(
                chunk_id=result.chunk_id,
                paper_id=str(result.metadata.get("paper_id", "")),
                paper_title=result.title,
                category_id=str(result.metadata.get("category_id", "")),
                kind=str(result.metadata.get("kind", "")),
                text=result.text,
                score=round(float(result.score), 5),
                lexical_score=_round_or_none(result.lexical_score),
                vector_score=_round_or_none(result.vector_score),
                page_number=result.page_number,
            )
            for result in results
        ]

    def stats(self) -> IndexStats:
        return IndexStats(
            backend=self.name,
            embedding_model="knowledge_vector",
            papers=0,
            chunks=0,
            categories=0,
            updated_at="",
        )


def build_backend(
    store: ResearchStore, settings: ResearchSettings
) -> tuple[RetrievalBackend, str]:
    """Returns (backend, notice). Falls back to builtin when the adapter fails."""
    if settings.retrieval_backend == "knowledge_vector":
        try:
            return KnowledgeVectorBackend(settings), ""
        except RetrievalError as error:
            return (
                SqliteHybridBackend(store, settings),
                f"knowledge_vector 后端不可用，已降级到内置后端：{error}",
            )
    return SqliteHybridBackend(store, settings), ""
