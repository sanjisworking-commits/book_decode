"""Application settings loaded from environment / .env."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]

_PATH_FIELDS = (
    "data_dir",
    "upload_dir",
    "processed_dir",
    "books_dir",
    "log_dir",
    "sqlite_path",
)


def _resolve_repo_path(value: Path | str) -> Path:
    """Resolve relative data paths against the repo root, not process cwd.

    ``BOOKS_DIR=./data/books`` in ``.env`` otherwise lands under ``backend/data``
    when uvicorn is started from ``backend/``.
    """
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path.resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    data_dir: Path = ROOT_DIR / "data"
    upload_dir: Path = ROOT_DIR / "data" / "uploads"
    processed_dir: Path = ROOT_DIR / "data" / "processed"
    books_dir: Path = ROOT_DIR / "data" / "books"
    log_dir: Path = ROOT_DIR / "data" / "logs"
    sqlite_path: Path = ROOT_DIR / "data" / "book_decode.db"

    max_epub_size_mb: int = 50

    # Phase 2 chunking — prototype default keeps typical chapters as one LLM call
    chunk_token_limit: int = 20000
    chunk_overlap_blocks: int = 2

    # LLM (multi-provider)
    llm_provider: str = "openai"  # openai | anthropic | openai_compatible
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.2
    # Full-chapter Argument Spines often exceed 8k output tokens when truncated mid-JSON.
    llm_max_tokens: int = 16384
    llm_mock: bool = False
    # Per-request HTTP timeout for LLM calls (large Argument Spine JSON can be slow).
    llm_timeout_seconds: float = 300.0
    llm_http_retries: int = 2
    # Cap on *full prompt* tokens (system+user) for one extract request (0 = auto).
    # Groq free llama-3.3-70b-versatile TPM is ~12k for the whole request.
    llm_max_input_tokens: int = 0

    # Phase 6 validation / retries
    max_chapter_retries: int = 3
    retry_backoff_seconds: float = 2.0

    # Prototype: one Anthropic call per chapter (skip multi-chunk + synth + hinglish)
    prototype_one_shot: bool = True

    @field_validator(*_PATH_FIELDS, mode="before")
    @classmethod
    def _repo_relative_paths(cls, value: Path | str) -> Path:
        return _resolve_repo_path(value)

    def is_groq(self) -> bool:
        return "groq.com" in (self.llm_api_base or "").lower()

    def provider_input_token_limit(self) -> int | None:
        """Hard provider ceiling for prompt+max_tokens when known (e.g. Groq TPM)."""
        if not self.is_groq():
            return None
        model = (self.llm_model or "").lower()
        if "scout" in model:
            return 30000
        if "8b" in model or "instant" in model:
            return 6000
        if "qwen" in model:
            return 6000
        # llama-3.3-70b-versatile and unknown Groq models
        return 12000

    def effective_llm_max_tokens(self) -> int:
        """Completion budget that still leaves room for the extract prompt on Groq.

        Groq free-tier 413s use Requested ≈ prompt_tokens + max_tokens against TPM.
        Life Ch1: ~7.2k prompt + 8192 max_tokens → 15389 > 12000.
        """
        configured = max(256, int(self.llm_max_tokens))
        tpm = self.provider_input_token_limit()
        if tpm is None:
            return configured
        # Reserve ~60% of TPM for the prompt, rest for completion (min 2k).
        max_for_tpm = max(2048, int(tpm * 0.35))
        return min(configured, max_for_tpm)

    def extract_prompt_token_budget(self) -> int:
        """Max estimated tokens for system+user messages in one extract call.

        For Groq, subtract ``effective_llm_max_tokens`` from TPM so
        prompt + max_tokens stays under the provider ceiling.
        """
        explicit = int(self.llm_max_input_tokens or 0)
        if explicit > 0:
            return max(1500, explicit)

        tpm = self.provider_input_token_limit()
        if tpm is not None:
            max_out = self.effective_llm_max_tokens()
            # Conservative estimator (~3 chars/token) + small safety margin.
            return max(1500, tpm - max_out - 500)
        return max(4000, int(self.chunk_token_limit) + 4000)

    def oneshot_block_token_budget(self) -> int:
        """Deprecated alias — prefer ``extract_prompt_token_budget`` (prompt-sized)."""
        return self.extract_prompt_token_budget()

    def ensure_directories(self) -> None:
        for path in (
            self.data_dir,
            self.upload_dir,
            self.processed_dir,
            self.books_dir,
            self.log_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def max_epub_size_bytes(self) -> int:
        return self.max_epub_size_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
