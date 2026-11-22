from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


JobStatus = Literal["queued", "running", "succeeded", "failed"]
JobType = Literal[
    "corpus_sync", "index_rebuild", "deep_analysis", "ideation", "evolution", "experiment"
]
RetrievalMode = Literal["hybrid", "lexical", "vector"]


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class Innovation(BaseModel):
    claim: str
    evidence_pages: list[int] = Field(default_factory=list)
    evidence_quotes: list[str] = Field(default_factory=list)


class EvidenceCard(BaseModel):
    """Structured snapshot of one paper as seen by the research platform."""

    paper_id: str
    title: str
    title_zh: str = ""
    authors: list[str] = Field(default_factory=list)
    venue: str = ""
    year: int = 0
    category_id: str
    category_name: str = ""
    thesis_zh: str = ""
    novelty_zh: str = ""
    thesis_en: str = ""
    novelty_en: str = ""
    problem: str = ""
    method: str = ""
    findings: list[str] = Field(default_factory=list)
    innovations: list[Innovation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    pdf_path: str = ""
    page_count: int = 0
    sha256: str = ""
    fingerprint: str = ""
    deep_analysis_status: Literal["missing", "pending", "ready", "failed"] = "missing"
    needs_deep_analysis: bool = True


class CorpusSyncResult(BaseModel):
    scanned: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    missing_pdf: int = 0
    needs_deep_analysis: int = 0
    total: int = 0
    errors: list[str] = Field(default_factory=list)


class ChunkRecord(BaseModel):
    chunk_id: str
    paper_id: str
    kind: str
    ordinal: int = 0
    text: str
    category_id: str = ""
    page_number: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchHit(BaseModel):
    chunk_id: str
    paper_id: str
    paper_title: str = ""
    category_id: str = ""
    kind: str = ""
    text: str
    score: float
    lexical_score: float | None = None
    vector_score: float | None = None
    page_number: int | None = None


class IndexStats(BaseModel):
    backend: str
    embedding_model: str
    papers: int = 0
    chunks: int = 0
    categories: int = 0
    updated_at: str = ""


class DeepAnalysisRecord(BaseModel):
    id: str
    paper_id: str
    paper_title: str = ""
    prompt_version: str
    status: Literal["ready", "failed"] = "ready"
    problem: str = ""
    method: str = ""
    findings: list[str] = Field(default_factory=list)
    innovations: list[Innovation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    model: str = ""
    error: str = ""
    created_at: str = ""


class Idea(BaseModel):
    id: str
    title: str
    hypothesis: str = ""
    motivation: str = ""
    method_sketch: str = ""
    expected_contribution: str = ""
    novelty_claim: str = ""
    risks: list[str] = Field(default_factory=list)
    required_resources: list[str] = Field(default_factory=list)
    source_paper_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    category_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    generation: int = 1
    batch_id: str = ""
    created_at: str = ""
    rejected_reason: str = ""
    # Populated by the critique stage; kept as a plain mapping so it can be
    # round-tripped through SQLite without a second table.
    critique: dict[str, Any] = Field(default_factory=dict)


class IdeaCritique(BaseModel):
    novelty: float = Field(default=0.5, ge=0, le=1)
    feasibility: float = Field(default=0.5, ge=0, le=1)
    evidence_support: float = Field(default=0.5, ge=0, le=1)
    risk: float = Field(default=0.5, ge=0, le=1)
    verdict: str = ""
    unsupported_claims: list[str] = Field(default_factory=list)
    suggested_fix: str = ""
    score: float = Field(default=0.0)


class Direction(BaseModel):
    id: str
    name: str
    question: str = ""
    rationale: str = ""
    gap_analysis: str = ""
    member_idea_ids: list[str] = Field(default_factory=list)
    source_paper_ids: list[str] = Field(default_factory=list)
    roadmap: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)
    open_risks: list[str] = Field(default_factory=list)
    priority: float = Field(default=0.0)
    generation: int = 1
    parent_direction_id: str = ""
    status: Literal["proposed", "active", "paused", "retired"] = "proposed"
    batch_id: str = ""
    created_at: str = ""


class ExperimentPlan(BaseModel):
    id: str
    direction_id: str
    direction_name: str = ""
    objective: str = ""
    hypothesis: str = ""
    datasets: list[str] = Field(default_factory=list)
    baselines: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    protocol_steps: list[str] = Field(default_factory=list)
    ablations: list[str] = Field(default_factory=list)
    compute_estimate: str = ""
    falsification_criteria: str = ""
    timeline: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    status: Literal["draft", "running", "done", "abandoned"] = "draft"
    result_summary: str = ""
    result_metrics: dict[str, Any] = Field(default_factory=dict)
    generation: int = 1
    created_at: str = ""
    updated_at: str = ""


FollowupKind = Literal["paper_to_read", "dataset", "tool", "experiment", "question"]


class FollowupItem(BaseModel):
    id: str
    direction_id: str = ""
    experiment_id: str = ""
    kind: FollowupKind = "paper_to_read"
    query: str = ""
    reason: str = ""
    suggested_action: str = ""
    status: Literal["open", "done", "dismissed"] = "open"
    created_at: str = ""


class IdeationRun(BaseModel):
    batch_id: str
    status: JobStatus = "queued"
    generation: int = 1
    provider: str = ""
    model: str = ""
    ideas_total: int = 0
    ideas_accepted: int = 0
    ideas_rejected: int = 0
    directions_total: int = 0
    experiments_total: int = 0
    followups_total: int = 0
    message: str = ""
    created_at: str = ""
    updated_at: str = ""


class ResearchJobResult(BaseModel):
    phase: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)


class ResearchJob(BaseModel):
    id: str
    job_type: JobType
    status: JobStatus = "queued"
    progress: int = Field(default=0, ge=0, le=100)
    stage: str = "queued"
    message: str = ""
    error: str = ""
    batch_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    result: ResearchJobResult | None = None


class PlatformStatus(BaseModel):
    service: str = "research-studio"
    provider: str
    model: str
    model_configured: bool
    retrieval_backend: str
    knowledge_vector_available: bool
    paper_database: str
    paper_database_readable: bool
    papers_indexed: int = 0
    chunks: int = 0
    ideas: int = 0
    directions: int = 0
    experiments: int = 0
    generations: int = 0
    reading_platform_writes: int = 0
