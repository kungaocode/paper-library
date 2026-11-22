from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ImportUrlRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)

    @field_validator("url")
    @classmethod
    def strip_url(cls, value: str) -> str:
        return value.strip()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=500)


class AuthStatus(BaseModel):
    auth_enabled: bool
    authenticated: bool
    username: str = ""


class CategoryCandidate(BaseModel):
    category_id: str
    category_name: str
    confidence: float = Field(ge=0, le=1)
    rationale: str = ""


class ClassificationResult(BaseModel):
    canonical_title: str
    title_zh: str = ""
    authors: list[str] = Field(default_factory=list)
    venue: str = ""
    year: int = 0
    abstract: str = ""
    language: str = "en"
    keywords: list[str] = Field(default_factory=list)
    primary_category_id: str
    primary_category_name: str
    confidence: float = Field(ge=0, le=1)
    rationale: str = ""
    candidate_categories: list[CategoryCandidate] = Field(default_factory=list)
    needs_review: bool = False


class Innovation(BaseModel):
    claim: str
    evidence_pages: list[int] = Field(default_factory=list)
    evidence_quotes: list[str] = Field(default_factory=list)


class PaperSummary(BaseModel):
    problem: str
    method: str
    findings: list[str] = Field(default_factory=list)
    innovations: list[Innovation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    thesis_zh: str = ""
    novelty_zh: str = ""
    thesis_en: str = ""
    novelty_en: str = ""
    relation_to_library: str = ""
    evidence_pages: list[int] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    problem: str
    method: str
    findings: list[str] = Field(default_factory=list)
    innovations: list[Innovation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    thesis_zh: str
    novelty_zh: str
    thesis_en: str
    novelty_en: str
    relation_to_library: str = ""
    confidence: float = Field(default=0.8, ge=0, le=1)
    needs_review: bool = False


class PaperRecord(BaseModel):
    id: str
    title: str
    title_zh: str = ""
    authors: list[str] = Field(default_factory=list)
    venue: str = ""
    year: int = 0
    abstract: str = ""
    category_id: str
    status: str = "ready"
    reading_status: str = "unread"
    source: str = "model"
    confidence: float = 0.0
    updated_at: str
    file_size: str = ""
    page_count: int = 0
    tags: list[str] = Field(default_factory=list)
    candidate_categories: list[CategoryCandidate] = Field(default_factory=list)
    summary: PaperSummary
    file_path: str = ""
    file_url: str = ""
    original_url: str = ""
    sha256: str = ""
    created_at: str = ""
    ai_rationale: str = ""
    translation_status: Literal[
        "not_started", "queued", "running", "ready", "failed"
    ] = "not_started"
    translation_path: str = ""
    translation_url: str = ""
    translation_error: str = ""
    translation_updated_at: str = ""
    translation_model: str = ""
    translation_progress: int = Field(default=0, ge=0, le=100)
    translation_page_count: int = 0
    translation_completed_pages: int = 0


class JobResult(BaseModel):
    phase: str = ""
    classification: ClassificationResult | None = None
    analysis: AnalysisResult | None = None
    category_id: str = ""
    category_name: str = ""
    destination: str = ""


JobStatus = Literal["queued", "running", "succeeded", "failed"]
JobType = Literal[
    "import", "extract", "classify", "analyze", "translate", "embed", "export"
]


class JobRecord(BaseModel):
    id: str
    paper_id: str = ""
    paper_title: str
    job_type: JobType = "import"
    status: JobStatus = "queued"
    progress: int = Field(default=0, ge=0, le=100)
    message: str = ""
    stage: str = "queued"
    updated_at: str = ""
    source_url: str = ""
    error: str = ""
    created_at: str = ""
    result: JobResult | None = None


class ModelStatus(BaseModel):
    provider: str
    model: str
    base_url: str
    configured: bool


class ModelConnectionTest(BaseModel):
    ok: bool
    message: str
    latency_ms: int = Field(ge=0)
    provider: str
    model: str


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
