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

    # Phase 2 chunking
    chunk_token_limit: int = 6000
    chunk_overlap_blocks: int = 2

    # LLM (multi-provider)
    llm_provider: str = "openai"  # openai | anthropic | openai_compatible
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 8192
    llm_mock: bool = False

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
