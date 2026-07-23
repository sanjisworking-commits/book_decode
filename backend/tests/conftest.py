"""Pytest fixtures for Phase 1 backend tests."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from ebooklib import epub
from fastapi.testclient import TestClient

from app.api.deps import reset_cached_stores
from app.config import Settings, get_settings


def _build_epub(
    *,
    title: str = "Mini Test Book",
    author: str = "Test Author",
    chapters: list[tuple[str, str]] | None = None,
) -> bytes:
    chapters = chapters or [
        ("Chapter 1", "<h1>Chapter 1</h1><p>Hello world paragraph one.</p><p>Second paragraph with enough text.</p>"),
        ("Chapter 2", "<h1>Chapter 2</h1><p>Another chapter body with substance for detection.</p>"),
    ]
    book = epub.EpubBook()
    book.set_identifier("test-mini-book")
    book.set_title(title)
    book.add_author(author)
    items = []
    for idx, (chap_title, html) in enumerate(chapters, start=1):
        item = epub.EpubHtml(title=chap_title, file_name=f"chap{idx}.xhtml", lang="en")
        item.content = html
        book.add_item(item)
        items.append(item)
    book.toc = tuple(
        epub.Link(it.file_name, it.title, f"c{i}") for i, it in enumerate(items, start=1)
    )
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", *items]
    buf = BytesIO()
    epub.write_epub(buf, book)
    return buf.getvalue()


@pytest.fixture()
def mini_epub_bytes() -> bytes:
    return _build_epub()


@pytest.fixture()
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    reset_cached_stores()
    data = tmp_path / "data"
    monkeypatch.setenv("DATA_DIR", str(data))
    monkeypatch.setenv("UPLOAD_DIR", str(data / "uploads"))
    monkeypatch.setenv("PROCESSED_DIR", str(data / "processed"))
    monkeypatch.setenv("BOOKS_DIR", str(data / "books"))
    monkeypatch.setenv("LOG_DIR", str(data / "logs"))
    monkeypatch.setenv("SQLITE_PATH", str(data / "test.db"))
    monkeypatch.setenv("MAX_EPUB_SIZE_MB", "5")
    get_settings.cache_clear()
    s = get_settings()
    s.ensure_directories()
    return s


@pytest.fixture()
def client(settings: Settings) -> TestClient:
    # Import app after settings env is patched
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    reset_cached_stores()
