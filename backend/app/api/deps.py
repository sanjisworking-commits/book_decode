"""Shared FastAPI dependencies."""

from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.services.books import BookService
from app.storage.filesystem import FilesystemStore
from app.storage.sqlite_store import SqliteStore


@lru_cache
def get_db() -> SqliteStore:
    return SqliteStore(get_settings())


@lru_cache
def get_fs() -> FilesystemStore:
    return FilesystemStore(get_settings())


@lru_cache
def get_book_service() -> BookService:
    return BookService(get_db(), get_fs())


def reset_cached_stores() -> None:
    """Clear cached singletons (tests / demo reset)."""
    get_book_service.cache_clear()
    get_db.cache_clear()
    get_fs.cache_clear()
    get_settings.cache_clear()
