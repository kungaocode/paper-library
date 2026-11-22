from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .schemas import JobRecord, JobResult, PaperRecord, utc_now


class LibraryStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS papers (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    title_zh TEXT NOT NULL DEFAULT '',
                    authors_json TEXT NOT NULL DEFAULT '[]',
                    venue TEXT NOT NULL DEFAULT '',
                    year INTEGER NOT NULL DEFAULT 0,
                    abstract TEXT NOT NULL DEFAULT '',
                    category_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reading_status TEXT NOT NULL DEFAULT 'unread',
                    source TEXT NOT NULL DEFAULT 'model',
                    confidence REAL NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    file_size TEXT NOT NULL DEFAULT '',
                    page_count INTEGER NOT NULL DEFAULT 0,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    candidates_json TEXT NOT NULL DEFAULT '[]',
                    summary_json TEXT NOT NULL,
                    file_path TEXT NOT NULL DEFAULT '',
                    file_url TEXT NOT NULL DEFAULT '',
                    original_url TEXT NOT NULL DEFAULT '',
                    sha256 TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    ai_rationale TEXT NOT NULL DEFAULT '',
                    translation_status TEXT NOT NULL DEFAULT 'not_started',
                    translation_path TEXT NOT NULL DEFAULT '',
                    translation_url TEXT NOT NULL DEFAULT '',
                    translation_error TEXT NOT NULL DEFAULT '',
                    translation_updated_at TEXT NOT NULL DEFAULT '',
                    translation_model TEXT NOT NULL DEFAULT '',
                    translation_progress INTEGER NOT NULL DEFAULT 0,
                    translation_page_count INTEGER NOT NULL DEFAULT 0,
                    translation_completed_pages INTEGER NOT NULL DEFAULT 0
                );

                CREATE UNIQUE INDEX IF NOT EXISTS papers_sha256_unique
                ON papers(sha256)
                WHERE sha256 <> '';

                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    paper_id TEXT NOT NULL DEFAULT '',
                    paper_title TEXT NOT NULL,
                    job_type TEXT NOT NULL DEFAULT 'import',
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    message TEXT NOT NULL DEFAULT '',
                    stage TEXT NOT NULL DEFAULT 'queued',
                    updated_at TEXT NOT NULL,
                    source_url TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    result_json TEXT NOT NULL DEFAULT '{}'
                );
                """
            )
            paper_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(papers)").fetchall()
            }
            if "candidates_json" not in paper_columns:
                connection.execute(
                    "ALTER TABLE papers ADD COLUMN candidates_json TEXT NOT NULL DEFAULT '[]'"
                )
            paper_migrations = {
                "translation_status": (
                    "ALTER TABLE papers ADD COLUMN translation_status "
                    "TEXT NOT NULL DEFAULT 'not_started'"
                ),
                "translation_path": (
                    "ALTER TABLE papers ADD COLUMN translation_path "
                    "TEXT NOT NULL DEFAULT ''"
                ),
                "translation_url": (
                    "ALTER TABLE papers ADD COLUMN translation_url "
                    "TEXT NOT NULL DEFAULT ''"
                ),
                "translation_error": (
                    "ALTER TABLE papers ADD COLUMN translation_error "
                    "TEXT NOT NULL DEFAULT ''"
                ),
                "translation_updated_at": (
                    "ALTER TABLE papers ADD COLUMN translation_updated_at "
                    "TEXT NOT NULL DEFAULT ''"
                ),
                "translation_model": (
                    "ALTER TABLE papers ADD COLUMN translation_model "
                    "TEXT NOT NULL DEFAULT ''"
                ),
                "translation_progress": (
                    "ALTER TABLE papers ADD COLUMN translation_progress "
                    "INTEGER NOT NULL DEFAULT 0"
                ),
                "translation_page_count": (
                    "ALTER TABLE papers ADD COLUMN translation_page_count "
                    "INTEGER NOT NULL DEFAULT 0"
                ),
                "translation_completed_pages": (
                    "ALTER TABLE papers ADD COLUMN translation_completed_pages "
                    "INTEGER NOT NULL DEFAULT 0"
                ),
            }
            for column, statement in paper_migrations.items():
                if column not in paper_columns:
                    connection.execute(statement)
            job_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
            }
            if "result_json" not in job_columns:
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN result_json TEXT NOT NULL DEFAULT '{}'"
                )

    def save_job(self, job: JobRecord) -> None:
        timestamp = job.updated_at or utc_now()
        created_at = job.created_at or timestamp
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id, paper_id, paper_title, job_type, status, progress, message,
                    stage, updated_at, source_url, error, created_at, result_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    paper_id = excluded.paper_id,
                    paper_title = excluded.paper_title,
                    job_type = excluded.job_type,
                    status = excluded.status,
                    progress = excluded.progress,
                    message = excluded.message,
                    stage = excluded.stage,
                    updated_at = excluded.updated_at,
                    source_url = excluded.source_url,
                    error = excluded.error,
                    result_json = excluded.result_json
                """,
                (
                    job.id,
                    job.paper_id,
                    job.paper_title,
                    job.job_type,
                    job.status,
                    job.progress,
                    job.message,
                    job.stage,
                    timestamp,
                    job.source_url,
                    job.error,
                    created_at,
                    (job.result or JobResult()).model_dump_json(),
                ),
            )

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._job_from_row(row) if row else None

    def list_jobs(self, limit: int = 50) -> list[JobRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._job_from_row(row) for row in rows]

    def mark_interrupted_jobs(self) -> int:
        interrupted = [
            job for job in self.list_jobs() if job.status in {"queued", "running"}
        ]
        for job in interrupted:
            job.status = "failed"
            job.stage = "failed"
            job.message = "服务重启，任务已中断"
            job.error = "服务重启后未继续执行，可点击重试。"
            job.updated_at = utc_now()
            self.save_job(job)
            if job.job_type == "translate" and job.paper_id:
                paper = self.get_paper(job.paper_id)
                if paper and paper.translation_status in {"queued", "running"}:
                    paper.translation_status = "failed"
                    paper.translation_error = "服务重启后翻译已中断，可重新翻译。"
                    paper.translation_updated_at = utc_now()
                    self.save_paper(paper)
        return len(interrupted)

    def save_paper(self, paper: PaperRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO papers (
                    id, title, title_zh, authors_json, venue, year, abstract,
                    category_id, status, reading_status, source, confidence,
                    updated_at, file_size, page_count, tags_json, candidates_json,
                    summary_json, file_path, file_url, original_url, sha256,
                    created_at, ai_rationale, translation_status, translation_path,
                    translation_url, translation_error, translation_updated_at,
                    translation_model, translation_progress, translation_page_count,
                    translation_completed_pages
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    title_zh = excluded.title_zh,
                    authors_json = excluded.authors_json,
                    venue = excluded.venue,
                    year = excluded.year,
                    abstract = excluded.abstract,
                    category_id = excluded.category_id,
                    status = excluded.status,
                    reading_status = excluded.reading_status,
                    source = excluded.source,
                    confidence = excluded.confidence,
                    updated_at = excluded.updated_at,
                    file_size = excluded.file_size,
                    page_count = excluded.page_count,
                    tags_json = excluded.tags_json,
                    candidates_json = excluded.candidates_json,
                    summary_json = excluded.summary_json,
                    file_path = excluded.file_path,
                    file_url = excluded.file_url,
                    original_url = excluded.original_url,
                    sha256 = excluded.sha256,
                    ai_rationale = excluded.ai_rationale,
                    translation_status = excluded.translation_status,
                    translation_path = excluded.translation_path,
                    translation_url = excluded.translation_url,
                    translation_error = excluded.translation_error,
                    translation_updated_at = excluded.translation_updated_at,
                    translation_model = excluded.translation_model,
                    translation_progress = excluded.translation_progress,
                    translation_page_count = excluded.translation_page_count,
                    translation_completed_pages = excluded.translation_completed_pages
                """,
                (
                    paper.id,
                    paper.title,
                    paper.title_zh,
                    json.dumps(paper.authors, ensure_ascii=False),
                    paper.venue,
                    paper.year,
                    paper.abstract,
                    paper.category_id,
                    paper.status,
                    paper.reading_status,
                    paper.source,
                    paper.confidence,
                    paper.updated_at,
                    paper.file_size,
                    paper.page_count,
                    json.dumps(paper.tags, ensure_ascii=False),
                    json.dumps(
                        [
                            candidate.model_dump(mode="json")
                            for candidate in paper.candidate_categories
                        ],
                        ensure_ascii=False,
                    ),
                    paper.summary.model_dump_json(),
                    paper.file_path,
                    paper.file_url,
                    paper.original_url,
                    paper.sha256,
                    paper.created_at or paper.updated_at,
                    paper.ai_rationale,
                    paper.translation_status,
                    paper.translation_path,
                    paper.translation_url,
                    paper.translation_error,
                    paper.translation_updated_at,
                    paper.translation_model,
                    paper.translation_progress,
                    paper.translation_page_count,
                    paper.translation_completed_pages,
                ),
            )

    def get_paper(self, paper_id: str) -> PaperRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM papers WHERE id = ?", (paper_id,)
            ).fetchone()
        return self._paper_from_row(row) if row else None

    def get_paper_by_sha256(self, sha256: str) -> PaperRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM papers WHERE sha256 = ?", (sha256,)
            ).fetchone()
        return self._paper_from_row(row) if row else None

    def list_papers(self, limit: int = 200, offset: int = 0) -> list[PaperRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM papers
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [self._paper_from_row(row) for row in rows]

    @staticmethod
    def _job_from_row(row: sqlite3.Row) -> JobRecord:
        data: dict[str, Any] = dict(row)
        raw_result = data.pop("result_json", "") or ""
        result: JobResult | None = None
        if raw_result and raw_result.strip() not in {"", "{}"}:
            try:
                result = JobResult.model_validate_json(raw_result)
            except Exception:
                result = None
        return JobRecord(**data, result=result)

    @staticmethod
    def _paper_from_row(row: sqlite3.Row) -> PaperRecord:
        data: dict[str, Any] = dict(row)
        data["authors"] = json.loads(data.pop("authors_json") or "[]")
        data["tags"] = json.loads(data.pop("tags_json") or "[]")
        data["candidate_categories"] = json.loads(
            data.pop("candidates_json") or "[]"
        )
        data["summary"] = json.loads(data.pop("summary_json") or "{}")
        return PaperRecord(**data)
