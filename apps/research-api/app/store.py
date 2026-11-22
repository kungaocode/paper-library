from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .schemas import (
    DeepAnalysisRecord,
    Direction,
    EvidenceCard,
    ExperimentPlan,
    FollowupItem,
    Idea,
    Innovation,
    IdeationRun,
    ResearchJob,
    ResearchJobResult,
    utc_now,
)


class StoreError(RuntimeError):
    """Raised when the research database cannot support an operation."""


class ResearchStore:
    """Own SQLite database. Never touches the reading platform's library."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.vector_cache_version = 0
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _bump_vector_cache(self) -> None:
        self.vector_cache_version += 1

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS corpus_papers (
                    paper_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    title_zh TEXT NOT NULL DEFAULT '',
                    authors_json TEXT NOT NULL DEFAULT '[]',
                    venue TEXT NOT NULL DEFAULT '',
                    year INTEGER NOT NULL DEFAULT 0,
                    category_id TEXT NOT NULL DEFAULT '',
                    category_name TEXT NOT NULL DEFAULT '',
                    thesis_zh TEXT NOT NULL DEFAULT '',
                    novelty_zh TEXT NOT NULL DEFAULT '',
                    thesis_en TEXT NOT NULL DEFAULT '',
                    novelty_en TEXT NOT NULL DEFAULT '',
                    summary_json TEXT NOT NULL DEFAULT '{}',
                    pdf_path TEXT NOT NULL DEFAULT '',
                    page_count INTEGER NOT NULL DEFAULT 0,
                    sha256 TEXT NOT NULL DEFAULT '',
                    fingerprint TEXT NOT NULL DEFAULT '',
                    deep_analysis_status TEXT NOT NULL DEFAULT 'missing',
                    pdf_exists INTEGER NOT NULL DEFAULT 0,
                    synced_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    paper_id TEXT NOT NULL DEFAULT '',
                    category_id TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL DEFAULT '',
                    ordinal INTEGER NOT NULL DEFAULT 0,
                    text TEXT NOT NULL,
                    page_number INTEGER,
                    embedding_model TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS chunks_paper_idx ON chunks(paper_id);
                CREATE INDEX IF NOT EXISTS chunks_kind_idx ON chunks(kind);

                CREATE TABLE IF NOT EXISTS chunk_vectors (
                    chunk_id TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    dim INTEGER NOT NULL,
                    vector BLOB NOT NULL
                );

                CREATE TABLE IF NOT EXISTS deep_analyses (
                    id TEXT PRIMARY KEY,
                    paper_id TEXT NOT NULL,
                    paper_title TEXT NOT NULL DEFAULT '',
                    prompt_version TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'ready',
                    problem TEXT NOT NULL DEFAULT '',
                    method TEXT NOT NULL DEFAULT '',
                    findings_json TEXT NOT NULL DEFAULT '[]',
                    innovations_json TEXT NOT NULL DEFAULT '[]',
                    limitations_json TEXT NOT NULL DEFAULT '[]',
                    model TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    UNIQUE(paper_id, prompt_version)
                );

                CREATE TABLE IF NOT EXISTS ideas (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    hypothesis TEXT NOT NULL DEFAULT '',
                    motivation TEXT NOT NULL DEFAULT '',
                    method_sketch TEXT NOT NULL DEFAULT '',
                    expected_contribution TEXT NOT NULL DEFAULT '',
                    novelty_claim TEXT NOT NULL DEFAULT '',
                    risks_json TEXT NOT NULL DEFAULT '[]',
                    required_resources_json TEXT NOT NULL DEFAULT '[]',
                    source_paper_ids_json TEXT NOT NULL DEFAULT '[]',
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    category_ids_json TEXT NOT NULL DEFAULT '[]',
                    confidence REAL NOT NULL DEFAULT 0,
                    generation INTEGER NOT NULL DEFAULT 1,
                    batch_id TEXT NOT NULL DEFAULT '',
                    rejected_reason TEXT NOT NULL DEFAULT '',
                    critique_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ideas_batch_idx ON ideas(batch_id);
                CREATE INDEX IF NOT EXISTS ideas_gen_idx ON ideas(generation);

                CREATE TABLE IF NOT EXISTS directions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    question TEXT NOT NULL DEFAULT '',
                    rationale TEXT NOT NULL DEFAULT '',
                    gap_analysis TEXT NOT NULL DEFAULT '',
                    member_idea_ids_json TEXT NOT NULL DEFAULT '[]',
                    source_paper_ids_json TEXT NOT NULL DEFAULT '[]',
                    roadmap_json TEXT NOT NULL DEFAULT '[]',
                    success_metrics_json TEXT NOT NULL DEFAULT '[]',
                    open_risks_json TEXT NOT NULL DEFAULT '[]',
                    priority REAL NOT NULL DEFAULT 0,
                    generation INTEGER NOT NULL DEFAULT 1,
                    parent_direction_id TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'proposed',
                    batch_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS experiment_plans (
                    id TEXT PRIMARY KEY,
                    direction_id TEXT NOT NULL DEFAULT '',
                    direction_name TEXT NOT NULL DEFAULT '',
                    objective TEXT NOT NULL DEFAULT '',
                    hypothesis TEXT NOT NULL DEFAULT '',
                    datasets_json TEXT NOT NULL DEFAULT '[]',
                    baselines_json TEXT NOT NULL DEFAULT '[]',
                    metrics_json TEXT NOT NULL DEFAULT '[]',
                    protocol_steps_json TEXT NOT NULL DEFAULT '[]',
                    ablations_json TEXT NOT NULL DEFAULT '[]',
                    compute_estimate TEXT NOT NULL DEFAULT '',
                    falsification_criteria TEXT NOT NULL DEFAULT '',
                    timeline_json TEXT NOT NULL DEFAULT '[]',
                    risks_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'draft',
                    result_summary TEXT NOT NULL DEFAULT '',
                    result_metrics_json TEXT NOT NULL DEFAULT '{}',
                    generation INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS followup_items (
                    id TEXT PRIMARY KEY,
                    direction_id TEXT NOT NULL DEFAULT '',
                    experiment_id TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL DEFAULT 'paper_to_read',
                    query TEXT NOT NULL DEFAULT '',
                    reason TEXT NOT NULL DEFAULT '',
                    suggested_action TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ideation_runs (
                    batch_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'queued',
                    generation INTEGER NOT NULL DEFAULT 1,
                    provider TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    ideas_total INTEGER NOT NULL DEFAULT 0,
                    ideas_accepted INTEGER NOT NULL DEFAULT 0,
                    ideas_rejected INTEGER NOT NULL DEFAULT 0,
                    directions_total INTEGER NOT NULL DEFAULT 0,
                    experiments_total INTEGER NOT NULL DEFAULT 0,
                    followups_total INTEGER NOT NULL DEFAULT 0,
                    message TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    progress INTEGER NOT NULL DEFAULT 0,
                    stage TEXT NOT NULL DEFAULT 'queued',
                    message TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    batch_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    result_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT ''
                );
                """
            )
            if not _fts_available(connection):
                raise StoreError(
                    "SQLite 不支持 FTS5，无法建立研究索引。请升级 SQLite 后重试。"
                )
            connection.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts "
                "USING fts5(chunk_id UNINDEXED, paper_id UNINDEXED, text, "
                "tokenize='trigram')"
            )
            self._migrate(connection)

    def _migrate(self, connection: sqlite3.Connection) -> None:
        """Additive-only migration for databases created by an earlier build.

        The shallow extraction the reading platform already produced (problem,
        method, findings, innovations, limitations) is part of the corpus row:
        the index must be useful before any model backfill runs.
        """
        existing = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(corpus_papers)").fetchall()
        }
        if "summary_json" not in existing:
            connection.execute(
                "ALTER TABLE corpus_papers "
                "ADD COLUMN summary_json TEXT NOT NULL DEFAULT '{}'"
            )

    # ---------------- meta ----------------

    def set_meta(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def get_meta(self, key: str, default: str = "") -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM meta WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else default

    # ---------------- corpus ----------------

    def upsert_paper(self, card: EvidenceCard, *, pdf_exists: bool) -> str:
        existing = self.get_paper(card.paper_id)
        if existing and existing.fingerprint == card.fingerprint:
            return "unchanged"
        created = existing is None
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO corpus_papers (
                    paper_id, title, title_zh, authors_json, venue, year,
                    category_id, category_name, thesis_zh, novelty_zh,
                    thesis_en, novelty_en, summary_json, pdf_path, page_count, sha256,
                    fingerprint, deep_analysis_status, pdf_exists, synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(paper_id) DO UPDATE SET
                    title = excluded.title,
                    title_zh = excluded.title_zh,
                    authors_json = excluded.authors_json,
                    venue = excluded.venue,
                    year = excluded.year,
                    category_id = excluded.category_id,
                    category_name = excluded.category_name,
                    thesis_zh = excluded.thesis_zh,
                    novelty_zh = excluded.novelty_zh,
                    thesis_en = excluded.thesis_en,
                    novelty_en = excluded.novelty_en,
                    summary_json = excluded.summary_json,
                    pdf_path = excluded.pdf_path,
                    page_count = excluded.page_count,
                    sha256 = excluded.sha256,
                    fingerprint = excluded.fingerprint,
                    pdf_exists = excluded.pdf_exists,
                    synced_at = excluded.synced_at
                """,
                (
                    card.paper_id,
                    card.title,
                    card.title_zh,
                    json.dumps(card.authors, ensure_ascii=False),
                    card.venue,
                    card.year,
                    card.category_id,
                    card.category_name,
                    card.thesis_zh,
                    card.novelty_zh,
                    card.thesis_en,
                    card.novelty_en,
                    json.dumps(_summary_payload(card), ensure_ascii=False),
                    card.pdf_path,
                    card.page_count,
                    card.sha256,
                    card.fingerprint,
                    card.deep_analysis_status,
                    int(pdf_exists),
                    utc_now(),
                ),
            )
        return "created" if created else "updated"

    def get_paper(self, paper_id: str) -> EvidenceCard | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM corpus_papers WHERE paper_id = ?", (paper_id,)
            ).fetchone()
        return _card_from_row(row) if row else None

    def list_papers(
        self, *, category_id: str = "", limit: int = 500
    ) -> list[EvidenceCard]:
        query = "SELECT * FROM corpus_papers"
        params: list[Any] = []
        if category_id:
            query += " WHERE category_id = ?"
            params.append(category_id)
        query += " ORDER BY category_id, title LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_card_from_row(row) for row in rows]

    def set_deep_analysis_status(self, paper_id: str, status: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE corpus_papers SET deep_analysis_status = ? WHERE paper_id = ?",
                (status, paper_id),
            )

    def count_papers(self) -> int:
        with self._connect() as connection:
            return int(
                connection.execute("SELECT COUNT(*) c FROM corpus_papers").fetchone()["c"]
            )

    def category_counts(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT category_id, category_name, COUNT(*) c FROM corpus_papers "
                "GROUP BY category_id, category_name ORDER BY category_id"
            ).fetchall()
        return [
            {
                "category_id": row["category_id"],
                "category_name": row["category_name"],
                "papers": int(row["c"]),
            }
            for row in rows
        ]

    # ---------------- chunks / index ----------------

    def replace_paper_chunks(
        self, paper_id: str, chunks: Iterable[tuple[str, Any]]
    ) -> None:
        """chunks: iterable of (chunk_id, row_dict). Row dict carries text etc."""
        rows = list(chunks)
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM chunks_fts WHERE paper_id = ?", (paper_id,)
            )
            # Vectors must go first: the subquery joins against chunks.
            connection.execute(
                "DELETE FROM chunk_vectors WHERE chunk_id IN "
                "(SELECT chunk_id FROM chunks WHERE paper_id = ?)",
                (paper_id,),
            )
            connection.execute("DELETE FROM chunks WHERE paper_id = ?", (paper_id,))
            _insert_chunk_rows(connection, rows)
        self._bump_vector_cache()

    def replace_chunks_by_kind(
        self, kind: str, chunks: Iterable[tuple[str, Any]]
    ) -> None:
        """Replace every chunk of one kind.

        Used for corpus-independent layers (category positioning, generated
        ideas/directions) that must not be wiped by a per-paper rebuild.
        """
        rows = list(chunks)
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM chunks_fts WHERE chunk_id IN "
                "(SELECT chunk_id FROM chunks WHERE kind = ?)",
                (kind,),
            )
            connection.execute(
                "DELETE FROM chunk_vectors WHERE chunk_id IN "
                "(SELECT chunk_id FROM chunks WHERE kind = ?)",
                (kind,),
            )
            connection.execute("DELETE FROM chunks WHERE kind = ?", (kind,))
            _insert_chunk_rows(connection, rows)
        self._bump_vector_cache()

    def save_vectors(
        self, vectors: Iterable[tuple[str, bytes, str, int]]
    ) -> None:
        """vectors: iterable of (chunk_id, blob, model, dim)."""
        with self._connect() as connection:
            connection.executemany(
                # Callers pass (chunk_id, blob, model, dim); keep the column
                # order aligned with that tuple so nothing is shifted.
                "INSERT OR REPLACE INTO chunk_vectors (chunk_id, vector, model, dim) "
                "VALUES (?, ?, ?, ?)",
                list(vectors),
            )
        self._bump_vector_cache()

    def delete_orphan_vectors(self) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM chunk_vectors WHERE chunk_id NOT IN "
                "(SELECT chunk_id FROM chunks)"
            )
            removed = cursor.rowcount or 0
        if removed:
            self._bump_vector_cache()
        return removed

    def load_vector_matrix(self) -> tuple[list[str], list[Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT v.chunk_id, v.vector, v.dim FROM chunk_vectors v "
                "JOIN chunks c ON c.chunk_id = v.chunk_id ORDER BY c.chunk_id"
            ).fetchall()
        ids: list[str] = []
        vectors: list[Any] = []
        for row in rows:
            ids.append(row["chunk_id"])
            vectors.append(_blob_to_array(row["vector"], int(row["dim"])))
        return ids, vectors

    def chunk_count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"])

    def chunk_kinds(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT kind, COUNT(*) c FROM chunks GROUP BY kind"
            ).fetchall()
        return {row["kind"]: int(row["c"]) for row in rows}

    def distinct_chunk_categories(self) -> int:
        with self._connect() as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(DISTINCT category_id) c FROM chunks "
                    "WHERE category_id <> ''"
                ).fetchone()["c"]
            )

    def chunks_without_vectors(self, model: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT c.chunk_id, c.text FROM chunks c "
                "LEFT JOIN chunk_vectors v ON v.chunk_id = c.chunk_id "
                "WHERE v.chunk_id IS NULL OR v.model <> ? ORDER BY c.chunk_id",
                (model,),
            ).fetchall()
        return [{"chunk_id": row["chunk_id"], "text": row["text"]} for row in rows]

    def paper_titles(self, paper_ids: Iterable[str]) -> dict[str, str]:
        wanted = [pid for pid in dict.fromkeys(paper_ids) if pid]
        if not wanted:
            return {}
        placeholders = ",".join("?" for _ in wanted)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT paper_id, title, title_zh FROM corpus_papers "
                f"WHERE paper_id IN ({placeholders})",
                wanted,
            ).fetchall()
        return {row["paper_id"]: row["title_zh"] or row["title"] for row in rows}

    def clear_index(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM chunks_fts")
            connection.execute("DELETE FROM chunks")
            connection.execute("DELETE FROM chunk_vectors")
        self._bump_vector_cache()

    def lexical_candidates(
        self, query: str, limit: int, *, escape_match: bool = True
    ) -> list[dict[str, Any]]:
        """FTS5 trigram search. Falls back to substring counting when MATCH is empty."""
        limit = max(1, limit)
        with self._connect() as connection:
            rows: list[sqlite3.Row] = []
            if escape_match:
                match = _fts_match_expression(query)
                if match:
                    try:
                        rows = connection.execute(
                            "SELECT chunk_id, paper_id, bm25(chunks_fts) rank "
                            "FROM chunks_fts WHERE chunks_fts MATCH ? "
                            "ORDER BY rank LIMIT ?",
                            (match, limit),
                        ).fetchall()
                    except sqlite3.OperationalError:
                        rows = []
            if not rows:
                needle = query.strip()
                if not needle:
                    return []
                rows = connection.execute(
                    "SELECT chunk_id, paper_id, "
                    "  (LENGTH(text) - LENGTH(REPLACE(LOWER(text), LOWER(?), ''))) hits "
                    "FROM chunks WHERE LOWER(text) LIKE ? ESCAPE '\\' "
                    "ORDER BY hits DESC LIMIT ?",
                    (needle, f"%{_like_escape(needle)}%", limit),
                ).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            keys = row.keys()
            if "rank" in keys:
                score = 1.0 / (1.0 + abs(float(row["rank"])))
            else:
                score = float(row["hits"] or 0)
            results.append(
                {
                    "chunk_id": row["chunk_id"],
                    "paper_id": row["paper_id"],
                    "lexical_score": score,
                }
            )
        return results

    def get_chunks(self, chunk_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        wanted = list(dict.fromkeys(chunk_ids))
        if not wanted:
            return {}
        placeholders = ",".join("?" for _ in wanted)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM chunks WHERE chunk_id IN ({placeholders})", wanted
            ).fetchall()
        return {
            row["chunk_id"]: {
                "chunk_id": row["chunk_id"],
                "paper_id": row["paper_id"],
                "category_id": row["category_id"],
                "kind": row["kind"],
                "text": row["text"],
                "page_number": row["page_number"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
            }
            for row in rows
        }

    # ---------------- deep analyses ----------------

    def save_deep_analysis(self, record: DeepAnalysisRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO deep_analyses (
                    id, paper_id, paper_title, prompt_version, status, problem,
                    method, findings_json, innovations_json, limitations_json,
                    model, error, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(paper_id, prompt_version) DO UPDATE SET
                    id = excluded.id,
                    paper_title = excluded.paper_title,
                    status = excluded.status,
                    problem = excluded.problem,
                    method = excluded.method,
                    findings_json = excluded.findings_json,
                    innovations_json = excluded.innovations_json,
                    limitations_json = excluded.limitations_json,
                    model = excluded.model,
                    error = excluded.error,
                    created_at = excluded.created_at
                """,
                (
                    record.id,
                    record.paper_id,
                    record.paper_title,
                    record.prompt_version,
                    record.status,
                    record.problem,
                    record.method,
                    json.dumps(record.findings, ensure_ascii=False),
                    json.dumps(
                        [item.model_dump(mode="json") for item in record.innovations],
                        ensure_ascii=False,
                    ),
                    json.dumps(record.limitations, ensure_ascii=False),
                    record.model,
                    record.error,
                    record.created_at or utc_now(),
                ),
            )

    def get_deep_analysis(
        self, paper_id: str, prompt_version: str
    ) -> DeepAnalysisRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM deep_analyses WHERE paper_id = ? AND prompt_version = ?",
                (paper_id, prompt_version),
            ).fetchone()
        return _deep_from_row(row) if row else None

    def list_deep_analyses(
        self, *, status: str = "", prompt_version: str = "", limit: int = 500
    ) -> list[DeepAnalysisRecord]:
        query = "SELECT * FROM deep_analyses"
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if prompt_version:
            clauses.append("prompt_version = ?")
            params.append(prompt_version)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_deep_from_row(row) for row in rows]

    def deep_analysis_count(self, status: str = "ready") -> int:
        with self._connect() as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) c FROM deep_analyses WHERE status = ?", (status,)
                ).fetchone()["c"]
            )

    # ---------------- ideas ----------------

    def save_idea(self, idea: Idea) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ideas (
                    id, title, hypothesis, motivation, method_sketch,
                    expected_contribution, novelty_claim, risks_json,
                    required_resources_json, source_paper_ids_json,
                    evidence_refs_json, category_ids_json, confidence,
                    generation, batch_id, rejected_reason, critique_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    hypothesis = excluded.hypothesis,
                    motivation = excluded.motivation,
                    method_sketch = excluded.method_sketch,
                    expected_contribution = excluded.expected_contribution,
                    novelty_claim = excluded.novelty_claim,
                    risks_json = excluded.risks_json,
                    required_resources_json = excluded.required_resources_json,
                    source_paper_ids_json = excluded.source_paper_ids_json,
                    evidence_refs_json = excluded.evidence_refs_json,
                    category_ids_json = excluded.category_ids_json,
                    confidence = excluded.confidence,
                    generation = excluded.generation,
                    batch_id = excluded.batch_id,
                    rejected_reason = excluded.rejected_reason,
                    critique_json = excluded.critique_json
                """,
                (
                    idea.id,
                    idea.title,
                    idea.hypothesis,
                    idea.motivation,
                    idea.method_sketch,
                    idea.expected_contribution,
                    idea.novelty_claim,
                    json.dumps(idea.risks, ensure_ascii=False),
                    json.dumps(idea.required_resources, ensure_ascii=False),
                    json.dumps(idea.source_paper_ids, ensure_ascii=False),
                    json.dumps(idea.evidence_refs, ensure_ascii=False),
                    json.dumps(idea.category_ids, ensure_ascii=False),
                    idea.confidence,
                    idea.generation,
                    idea.batch_id,
                    idea.rejected_reason,
                    json.dumps(idea.critique, ensure_ascii=False),
                    idea.created_at or utc_now(),
                ),
            )

    def list_ideas(
        self,
        *,
        batch_id: str = "",
        generation: int = 0,
        include_rejected: bool = False,
        limit: int = 200,
    ) -> list[Idea]:
        query = "SELECT * FROM ideas"
        clauses: list[str] = []
        params: list[Any] = []
        if batch_id:
            clauses.append("batch_id = ?")
            params.append(batch_id)
        if generation:
            clauses.append("generation = ?")
            params.append(generation)
        if not include_rejected:
            clauses.append("rejected_reason = ''")
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY confidence DESC, created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_idea_from_row(row) for row in rows]

    def idea_count(self, *, include_rejected: bool = False) -> int:
        query = "SELECT COUNT(*) c FROM ideas"
        params: tuple[Any, ...] = ()
        if not include_rejected:
            query += " WHERE rejected_reason = ''"
        with self._connect() as connection:
            return int(connection.execute(query, params).fetchone()["c"])

    # ---------------- directions ----------------

    def save_direction(self, direction: Direction) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO directions (
                    id, name, question, rationale, gap_analysis,
                    member_idea_ids_json, source_paper_ids_json, roadmap_json,
                    success_metrics_json, open_risks_json, priority, generation,
                    parent_direction_id, status, batch_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    question = excluded.question,
                    rationale = excluded.rationale,
                    gap_analysis = excluded.gap_analysis,
                    member_idea_ids_json = excluded.member_idea_ids_json,
                    source_paper_ids_json = excluded.source_paper_ids_json,
                    roadmap_json = excluded.roadmap_json,
                    success_metrics_json = excluded.success_metrics_json,
                    open_risks_json = excluded.open_risks_json,
                    priority = excluded.priority,
                    generation = excluded.generation,
                    parent_direction_id = excluded.parent_direction_id,
                    status = excluded.status,
                    batch_id = excluded.batch_id
                """,
                (
                    direction.id,
                    direction.name,
                    direction.question,
                    direction.rationale,
                    direction.gap_analysis,
                    json.dumps(direction.member_idea_ids, ensure_ascii=False),
                    json.dumps(direction.source_paper_ids, ensure_ascii=False),
                    json.dumps(direction.roadmap, ensure_ascii=False),
                    json.dumps(direction.success_metrics, ensure_ascii=False),
                    json.dumps(direction.open_risks, ensure_ascii=False),
                    direction.priority,
                    direction.generation,
                    direction.parent_direction_id,
                    direction.status,
                    direction.batch_id,
                    direction.created_at or utc_now(),
                ),
            )

    def list_directions(
        self, *, generation: int = 0, limit: int = 200
    ) -> list[Direction]:
        query = "SELECT * FROM directions"
        params: list[Any] = []
        if generation:
            query += " WHERE generation = ?"
            params.append(generation)
        query += " ORDER BY generation DESC, priority DESC, created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_direction_from_row(row) for row in rows]

    def get_direction(self, direction_id: str) -> Direction | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM directions WHERE id = ?", (direction_id,)
            ).fetchone()
        return _direction_from_row(row) if row else None

    def direction_count(self) -> int:
        with self._connect() as connection:
            return int(
                connection.execute("SELECT COUNT(*) c FROM directions").fetchone()["c"]
            )

    def max_generation(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(generation), 0) g FROM directions"
            ).fetchone()
        return int(row["g"] or 0)

    # ---------------- experiment plans ----------------

    def save_experiment(self, plan: ExperimentPlan) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO experiment_plans (
                    id, direction_id, direction_name, objective, hypothesis,
                    datasets_json, baselines_json, metrics_json,
                    protocol_steps_json, ablations_json, compute_estimate,
                    falsification_criteria, timeline_json, risks_json, status,
                    result_summary, result_metrics_json, generation, created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    direction_id = excluded.direction_id,
                    direction_name = excluded.direction_name,
                    objective = excluded.objective,
                    hypothesis = excluded.hypothesis,
                    datasets_json = excluded.datasets_json,
                    baselines_json = excluded.baselines_json,
                    metrics_json = excluded.metrics_json,
                    protocol_steps_json = excluded.protocol_steps_json,
                    ablations_json = excluded.ablations_json,
                    compute_estimate = excluded.compute_estimate,
                    falsification_criteria = excluded.falsification_criteria,
                    timeline_json = excluded.timeline_json,
                    risks_json = excluded.risks_json,
                    status = excluded.status,
                    result_summary = excluded.result_summary,
                    result_metrics_json = excluded.result_metrics_json,
                    generation = excluded.generation,
                    updated_at = excluded.updated_at
                """,
                (
                    plan.id,
                    plan.direction_id,
                    plan.direction_name,
                    plan.objective,
                    plan.hypothesis,
                    json.dumps(plan.datasets, ensure_ascii=False),
                    json.dumps(plan.baselines, ensure_ascii=False),
                    json.dumps(plan.metrics, ensure_ascii=False),
                    json.dumps(plan.protocol_steps, ensure_ascii=False),
                    json.dumps(plan.ablations, ensure_ascii=False),
                    plan.compute_estimate,
                    plan.falsification_criteria,
                    json.dumps(plan.timeline, ensure_ascii=False),
                    json.dumps(plan.risks, ensure_ascii=False),
                    plan.status,
                    plan.result_summary,
                    json.dumps(plan.result_metrics, ensure_ascii=False),
                    plan.generation,
                    plan.created_at or utc_now(),
                    plan.updated_at or utc_now(),
                ),
            )

    def list_experiments(self, *, limit: int = 200) -> list[ExperimentPlan]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM experiment_plans ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_experiment_from_row(row) for row in rows]

    def get_experiment(self, experiment_id: str) -> ExperimentPlan | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM experiment_plans WHERE id = ?", (experiment_id,)
            ).fetchone()
        return _experiment_from_row(row) if row else None

    def experiment_count(self) -> int:
        with self._connect() as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) c FROM experiment_plans"
                ).fetchone()["c"]
            )

    # ---------------- followups ----------------

    def save_followup(self, item: FollowupItem) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO followup_items (
                    id, direction_id, experiment_id, kind, query, reason,
                    suggested_action, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    direction_id = excluded.direction_id,
                    experiment_id = excluded.experiment_id,
                    kind = excluded.kind,
                    query = excluded.query,
                    reason = excluded.reason,
                    suggested_action = excluded.suggested_action,
                    status = excluded.status
                """,
                (
                    item.id,
                    item.direction_id,
                    item.experiment_id,
                    item.kind,
                    item.query,
                    item.reason,
                    item.suggested_action,
                    item.status,
                    item.created_at or utc_now(),
                ),
            )

    def list_followups(
        self, *, status: str = "", limit: int = 300
    ) -> list[FollowupItem]:
        query = "SELECT * FROM followup_items"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_followup_from_row(row) for row in rows]

    def update_followup_status(self, followup_id: str, status: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE followup_items SET status = ? WHERE id = ?",
                (status, followup_id),
            )
            return bool(cursor.rowcount)

    def followup_count(self) -> int:
        with self._connect() as connection:
            return int(
                connection.execute("SELECT COUNT(*) c FROM followup_items").fetchone()["c"]
            )

    # ---------------- ideation runs ----------------

    def save_run(self, run: IdeationRun) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ideation_runs (
                    batch_id, status, generation, provider, model, ideas_total,
                    ideas_accepted, ideas_rejected, directions_total,
                    experiments_total, followups_total, message, created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(batch_id) DO UPDATE SET
                    status = excluded.status,
                    generation = excluded.generation,
                    provider = excluded.provider,
                    model = excluded.model,
                    ideas_total = excluded.ideas_total,
                    ideas_accepted = excluded.ideas_accepted,
                    ideas_rejected = excluded.ideas_rejected,
                    directions_total = excluded.directions_total,
                    experiments_total = excluded.experiments_total,
                    followups_total = excluded.followups_total,
                    message = excluded.message,
                    updated_at = excluded.updated_at
                """,
                (
                    run.batch_id,
                    run.status,
                    run.generation,
                    run.provider,
                    run.model,
                    run.ideas_total,
                    run.ideas_accepted,
                    run.ideas_rejected,
                    run.directions_total,
                    run.experiments_total,
                    run.followups_total,
                    run.message,
                    run.created_at or utc_now(),
                    run.updated_at or utc_now(),
                ),
            )

    def get_run(self, batch_id: str) -> IdeationRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ideation_runs WHERE batch_id = ?", (batch_id,)
            ).fetchone()
        return IdeationRun(**dict(row)) if row else None

    def list_runs(self, limit: int = 50) -> list[IdeationRun]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM ideation_runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [IdeationRun(**dict(row)) for row in rows]

    # ---------------- jobs ----------------

    def save_job(self, job: ResearchJob) -> None:
        timestamp = job.updated_at or utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id, job_type, status, progress, stage, message, error,
                    batch_id, created_at, updated_at, result_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    job_type = excluded.job_type,
                    status = excluded.status,
                    progress = excluded.progress,
                    stage = excluded.stage,
                    message = excluded.message,
                    error = excluded.error,
                    batch_id = excluded.batch_id,
                    updated_at = excluded.updated_at,
                    result_json = excluded.result_json
                """,
                (
                    job.id,
                    job.job_type,
                    job.status,
                    job.progress,
                    job.stage,
                    job.message,
                    job.error,
                    job.batch_id,
                    job.created_at or timestamp,
                    timestamp,
                    (job.result or ResearchJobResult()).model_dump_json(),
                ),
            )

    def get_job(self, job_id: str) -> ResearchJob | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return _job_from_row(row) if row else None

    def list_jobs(self, limit: int = 50) -> list[ResearchJob]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_job_from_row(row) for row in rows]

    def mark_interrupted_jobs(self) -> int:
        interrupted = [
            job for job in self.list_jobs() if job.status in {"queued", "running"}
        ]
        for job in interrupted:
            job.status = "failed"
            job.stage = "failed"
            job.message = "服务重启，任务已中断"
            job.error = "服务重启后未继续执行，可重新触发。"
            job.updated_at = utc_now()
            self.save_job(job)
            if job.batch_id:
                run = self.get_run(job.batch_id)
                if run and run.status in {"queued", "running"}:
                    run.status = "failed"
                    run.message = "服务重启，本轮演化已中断"
                    run.updated_at = utc_now()
                    self.save_run(run)
        return len(interrupted)


def _insert_chunk_rows(
    connection: sqlite3.Connection, rows: list[tuple[str, Any]]
) -> None:
    for chunk_id, data in rows:
        connection.execute(
            """
            INSERT OR REPLACE INTO chunks (
                chunk_id, paper_id, category_id, kind, ordinal, text,
                page_number, embedding_model, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                data["paper_id"],
                data.get("category_id", ""),
                data.get("kind", ""),
                int(data.get("ordinal", 0)),
                data["text"],
                data.get("page_number"),
                data.get("embedding_model", ""),
                json.dumps(data.get("metadata", {}), ensure_ascii=False),
            ),
        )
        connection.execute(
            "INSERT OR REPLACE INTO chunks_fts (chunk_id, paper_id, text) "
            "VALUES (?, ?, ?)",
            (chunk_id, data["paper_id"], data["text"]),
        )


def _fts_available(connection: sqlite3.Connection) -> bool:
    try:
        connection.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS _fts_probe USING fts5(x)"
        )
        connection.execute("DROP TABLE IF EXISTS _fts_probe")
        return True
    except sqlite3.OperationalError:
        return False


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _fts_match_expression(query: str) -> str:
    """Build a safe FTS5 MATCH expression from free text."""
    tokens = [token for token in query.replace('"', " ").split() if token.strip()]
    if not tokens:
        compact = query.strip()
        return f'"{compact}"' if len(compact) >= 3 else ""
    quoted = [f'"{token}"' for token in tokens if len(token) >= 3]
    if not quoted:
        return ""
    return " OR ".join(quoted)


def _blob_to_array(blob: bytes, dim: int) -> Any:
    import numpy as np

    return np.frombuffer(blob, dtype=np.float32, count=dim)


def _card_from_row(row: sqlite3.Row) -> EvidenceCard:
    data = dict(row)
    data.pop("pdf_exists", None)
    data.pop("synced_at", None)
    data["authors"] = json.loads(data.pop("authors_json") or "[]")
    summary = _parse_summary(data.pop("summary_json", "") or "")
    data["problem"] = str(summary.get("problem") or "").strip()
    data["method"] = str(summary.get("method") or "").strip()
    data["findings"] = _string_list(summary.get("findings"))
    data["limitations"] = _string_list(summary.get("limitations"))
    data["innovations"] = _innovations_from_payload(summary.get("innovations"))
    # Mirrors corpus._build_card: "ready" here means the reading platform
    # already extracted something usable, not that the model backfill ran.
    data["needs_deep_analysis"] = not (
        data["problem"] or data["method"] or data["findings"] or data["innovations"]
    )
    return EvidenceCard(**data)


def _summary_payload(card: EvidenceCard) -> dict[str, Any]:
    """Shallow extraction copied from the reading platform (read-only source)."""
    return {
        "problem": card.problem,
        "method": card.method,
        "findings": list(card.findings),
        "innovations": [item.model_dump(mode="json") for item in card.innovations],
        "limitations": list(card.limitations),
    }


def _parse_summary(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _innovations_from_payload(value: Any) -> list[Innovation]:
    if not isinstance(value, list):
        return []
    innovations: list[Innovation] = []
    for item in value:
        if isinstance(item, str):
            claim = item.strip()
            if claim:
                innovations.append(Innovation(claim=claim[:600]))
            continue
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim") or "").strip()
        if not claim:
            continue
        innovations.append(
            Innovation(
                claim=claim[:600],
                evidence_pages=[
                    page
                    for page in (item.get("evidence_pages") or [])
                    if isinstance(page, int)
                ][:8],
                evidence_quotes=_string_list(item.get("evidence_quotes"))[:3],
            )
        )
    return innovations[:10]


def _deep_from_row(row: sqlite3.Row) -> DeepAnalysisRecord:
    data = dict(row)
    data["findings"] = json.loads(data.pop("findings_json") or "[]")
    data["innovations"] = json.loads(data.pop("innovations_json") or "[]")
    data["limitations"] = json.loads(data.pop("limitations_json") or "[]")
    return DeepAnalysisRecord(**data)


def _idea_from_row(row: sqlite3.Row) -> Idea:
    data = dict(row)
    data["risks"] = json.loads(data.pop("risks_json") or "[]")
    data["required_resources"] = json.loads(data.pop("required_resources_json") or "[]")
    data["source_paper_ids"] = json.loads(data.pop("source_paper_ids_json") or "[]")
    data["evidence_refs"] = json.loads(data.pop("evidence_refs_json") or "[]")
    data["category_ids"] = json.loads(data.pop("category_ids_json") or "[]")
    try:
        data["critique"] = json.loads(data.pop("critique_json") or "{}")
    except json.JSONDecodeError:
        data["critique"] = {}
    return Idea(**data)


def _direction_from_row(row: sqlite3.Row) -> Direction:
    data = dict(row)
    data["member_idea_ids"] = json.loads(data.pop("member_idea_ids_json") or "[]")
    data["source_paper_ids"] = json.loads(data.pop("source_paper_ids_json") or "[]")
    data["roadmap"] = json.loads(data.pop("roadmap_json") or "[]")
    data["success_metrics"] = json.loads(data.pop("success_metrics_json") or "[]")
    data["open_risks"] = json.loads(data.pop("open_risks_json") or "[]")
    return Direction(**data)


def _experiment_from_row(row: sqlite3.Row) -> ExperimentPlan:
    data = dict(row)
    data["datasets"] = json.loads(data.pop("datasets_json") or "[]")
    data["baselines"] = json.loads(data.pop("baselines_json") or "[]")
    data["metrics"] = json.loads(data.pop("metrics_json") or "[]")
    data["protocol_steps"] = json.loads(data.pop("protocol_steps_json") or "[]")
    data["ablations"] = json.loads(data.pop("ablations_json") or "[]")
    data["timeline"] = json.loads(data.pop("timeline_json") or "[]")
    data["risks"] = json.loads(data.pop("risks_json") or "[]")
    data["result_metrics"] = json.loads(data.pop("result_metrics_json") or "{}")
    return ExperimentPlan(**data)


def _followup_from_row(row: sqlite3.Row) -> FollowupItem:
    return FollowupItem(**dict(row))


def _job_from_row(row: sqlite3.Row) -> ResearchJob:
    data = dict(row)
    raw = data.pop("result_json", "") or ""
    result: ResearchJobResult | None = None
    if raw.strip() not in {"", "{}"}:
        try:
            result = ResearchJobResult.model_validate_json(raw)
        except Exception:
            result = None
    return ResearchJob(**data, result=result)
