"""Data path resolution relative to repo root."""

from pathlib import Path

from app.config import ROOT_DIR, Settings, get_settings


def test_relative_books_dir_resolves_to_repo_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # pretend cwd is unrelated
    monkeypatch.setenv("BOOKS_DIR", "./data/books")
    monkeypatch.setenv("DATA_DIR", "./data")
    monkeypatch.setenv("UPLOAD_DIR", "./data/uploads")
    monkeypatch.setenv("PROCESSED_DIR", "./data/processed")
    monkeypatch.setenv("LOG_DIR", "./data/logs")
    monkeypatch.setenv("SQLITE_PATH", "./data/test.db")
    get_settings.cache_clear()
    s = Settings()
    assert s.books_dir == (ROOT_DIR / "data" / "books").resolve()
    assert s.data_dir == (ROOT_DIR / "data").resolve()
