from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

DEFAULT_CORS_ORIGINS = (
    "http://localhost:3100",
    "http://127.0.0.1:3100",
)

# Prompt/schema version. Bumped when deep-analysis prompts change so cached
# results can be invalidated deliberately instead of silently going stale.
ANALYSIS_PROMPT_VERSION = "v1"


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return default
    items = tuple(item.strip().rstrip("/") for item in value.split(",") if item.strip())
    return items or default


@dataclass(frozen=True)
class ResearchSettings:
    paper_root: Path
    storage_dir: Path
    llm_provider: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout_seconds: float
    llm_max_output_tokens: int
    llm_json_mode: bool
    analysis_concurrency: int
    analysis_page_limit: int
    analysis_max_chars: int
    retrieval_top_k: int
    retrieval_candidate_k: int
    lexical_weight: float
    dedupe_threshold: float
    knowledge_vector_root: str
    knowledge_vector_db: str
    retrieval_backend: str
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS

    @classmethod
    def from_env(cls) -> "ResearchSettings":
        default_root = Path(__file__).resolve().parents[3]
        paper_root = Path(os.getenv("RESEARCH_PAPER_ROOT", default_root)).expanduser().resolve()
        storage_dir = Path(
            os.getenv("RESEARCH_STORAGE_DIR", paper_root / "storage" / "research")
        ).expanduser().resolve()
        concurrency = int(os.getenv("RESEARCH_ANALYSIS_CONCURRENCY", "2"))
        weight = float(os.getenv("RESEARCH_LEXICAL_WEIGHT", "0.45"))

        return cls(
            paper_root=paper_root,
            storage_dir=storage_dir,
            # Default is mock: the whole pipeline must run offline until the user
            # fills in RESEARCH_LLM_* themselves.
            llm_provider=os.getenv("RESEARCH_LLM_PROVIDER", "mock").strip() or "mock",
            llm_base_url=os.getenv("RESEARCH_LLM_BASE_URL", "").strip(),
            llm_api_key=os.getenv("RESEARCH_LLM_API_KEY", "").strip(),
            llm_model=os.getenv("RESEARCH_LLM_MODEL", "").strip(),
            llm_timeout_seconds=float(os.getenv("RESEARCH_LLM_TIMEOUT_SECONDS", "600")),
            llm_max_output_tokens=int(os.getenv("RESEARCH_LLM_MAX_OUTPUT_TOKENS", "8000")),
            llm_json_mode=_env_bool("RESEARCH_LLM_JSON_MODE", True),
            analysis_concurrency=max(1, concurrency),
            analysis_page_limit=int(os.getenv("RESEARCH_ANALYSIS_PAGE_LIMIT", "45")),
            analysis_max_chars=int(os.getenv("RESEARCH_ANALYSIS_MAX_CHARS", "120000")),
            retrieval_top_k=int(os.getenv("RESEARCH_RETRIEVAL_TOP_K", "8")),
            retrieval_candidate_k=int(os.getenv("RESEARCH_RETRIEVAL_CANDIDATE_K", "40")),
            lexical_weight=min(1.0, max(0.0, weight)),
            dedupe_threshold=float(os.getenv("RESEARCH_DEDUPE_THRESHOLD", "0.92")),
            knowledge_vector_root=os.getenv("KNOWLEDGE_VECTOR_ROOT", "").strip(),
            knowledge_vector_db=os.getenv("KNOWLEDGE_VECTOR_DB", "").strip(),
            retrieval_backend=os.getenv("RESEARCH_RETRIEVAL_BACKEND", "builtin").strip() or "builtin",
            cors_origins=_env_csv("RESEARCH_CORS_ORIGINS", DEFAULT_CORS_ORIGINS),
        )

    @property
    def database_path(self) -> Path:
        return self.storage_dir / "research.sqlite3"

    @property
    def paper_database_path(self) -> Path:
        """Reading-platform library. Opened read-only; never written by this service."""
        return self.paper_root / "storage" / "api" / "library.sqlite3"

    @property
    def paper_database_uri(self) -> str:
        return f"file:{self.paper_database_path}?mode=ro"

    @property
    def knowledge_base_path(self) -> Path:
        return self.paper_root / "KNOWLEDGE_BASE.md"

    @property
    def completed_dir(self) -> Path:
        return self.paper_root / "completed"

    @property
    def reports_dir(self) -> Path:
        return self.storage_dir / "reports"

    @property
    def reading_platform_app(self) -> Path:
        """Directory holding the reading platform's reusable pure modules."""
        return self.paper_root / "apps" / "api"

    @property
    def model_configured(self) -> bool:
        if self.llm_provider.lower() == "mock":
            return True
        return bool(self.llm_base_url and self.llm_model)

    def ensure_directories(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def reading_platform_available(self) -> bool:
        """True when the reading platform's reusable modules can be located."""
        return (self.reading_platform_app / "app" / "pdf_utils.py").is_file()
