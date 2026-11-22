from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
)


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
class Settings:
    paper_root: Path
    storage_dir: Path
    llm_provider: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout_seconds: float
    llm_max_output_tokens: int
    llm_json_mode: bool
    allow_private_urls: bool
    max_download_mb: int
    max_text_chars: int
    analysis_page_limit: int
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    auth_username: str = "admin"
    auth_password: str = ""
    auth_session_secret: str = ""
    auth_session_ttl_hours: int = 24
    auth_cookie_secure: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        default_root = Path(__file__).resolve().parents[3]
        paper_root = Path(os.getenv("PAPER_ROOT", default_root)).expanduser().resolve()
        storage_dir = Path(
            os.getenv("PAPER_STORAGE_DIR", paper_root / "storage" / "api")
        ).expanduser().resolve()

        return cls(
            paper_root=paper_root,
            storage_dir=storage_dir,
            llm_provider=os.getenv("LLM_PROVIDER", "openai-compatible").strip(),
            llm_base_url=(
                os.getenv("LLM_BASE_URL")
                or os.getenv("OPENAI_BASE_URL")
                or "https://api.openai.com/v1"
            ).strip(),
            llm_api_key=(os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip(),
            llm_model=(os.getenv("LLM_MODEL") or os.getenv("LLM_MODEL_ID") or "").strip(),
            llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "900")),
            llm_max_output_tokens=int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "6000")),
            llm_json_mode=_env_bool("LLM_JSON_MODE", True),
            allow_private_urls=_env_bool("ALLOW_PRIVATE_URLS", False),
            max_download_mb=int(os.getenv("MAX_DOWNLOAD_MB", "120")),
            max_text_chars=int(os.getenv("MAX_TEXT_CHARS", "120000")),
            analysis_page_limit=int(os.getenv("ANALYSIS_PAGE_LIMIT", "45")),
            cors_origins=_env_csv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS),
            auth_username=os.getenv("AUTH_USERNAME", "admin").strip() or "admin",
            auth_password=os.getenv("AUTH_PASSWORD", ""),
            auth_session_secret=os.getenv("AUTH_SESSION_SECRET", ""),
            auth_session_ttl_hours=int(os.getenv("AUTH_SESSION_TTL_HOURS", "24")),
            auth_cookie_secure=_env_bool("AUTH_COOKIE_SECURE", False),
        )

    @property
    def database_path(self) -> Path:
        return self.storage_dir / "library.sqlite3"

    @property
    def need_organization_dir(self) -> Path:
        return self.paper_root / "need_organization"

    @property
    def completed_dir(self) -> Path:
        return self.paper_root / "completed"

    @property
    def knowledge_base_path(self) -> Path:
        return self.paper_root / "KNOWLEDGE_BASE.md"

    @property
    def translation_dir(self) -> Path:
        # Keep the user-requested directory spelling for compatibility.
        return self.paper_root / "translete"

    @property
    def archive_dir(self) -> Path:
        return self.paper_root / "_archive"

    @property
    def model_configured(self) -> bool:
        if self.llm_provider == "mock":
            return True
        return bool(self.llm_base_url and self.llm_model)

    @property
    def auth_enabled(self) -> bool:
        return bool(self.auth_password)

    @property
    def auth_signing_key(self) -> str:
        return self.auth_session_secret or self.auth_password

    def ensure_directories(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.need_organization_dir.mkdir(parents=True, exist_ok=True)
        self.completed_dir.mkdir(parents=True, exist_ok=True)
        self.translation_dir.mkdir(parents=True, exist_ok=True)
        (self.archive_dir / "duplicates").mkdir(parents=True, exist_ok=True)
        (self.archive_dir / "versions").mkdir(parents=True, exist_ok=True)
