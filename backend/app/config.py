"""Application settings loaded from environment / .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]


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

    def is_groq(self) -> bool:
        return "groq.com" in (self.llm_api_base or "").lower()

    def provider_input_token_limit(self) -> int | None:
        """Hard provider ceiling for prompt tokens when known (e.g. Groq TPM)."""
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

    def extract_prompt_token_budget(self) -> int:
        """Max estimated tokens for system+user messages in one extract call.

        Uses a conservative estimator for Groq (see ``estimate_request_tokens``):
        chars/4 under-counts Llama tokenizers by ~1.4× on Life Ch1 payloads.
        """
        explicit = int(self.llm_max_input_tokens or 0)
        if explicit > 0:
            return max(1500, explicit)

        provider = self.provider_input_token_limit()
        if provider is not None:
            # Stay under TPM with headroom for tokenizer variance.
            return max(1500, int(provider * 0.7))
        # Non-Groq: generous budget; still pack by serialized prompt size.
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
