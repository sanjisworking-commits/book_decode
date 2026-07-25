"""Prototype one-shot decode path tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.config import get_settings
from app.domain.enums import BookProcessingStatus, ChapterStatus, UIStage
from app.pipelines.extract import ExtractPipeline
from app.pipelines.validate_persist import ValidatePersistPipeline
from app.services.books import BookService
from app.services.llm import MockLLMClient
from app.storage.filesystem import FilesystemStore
from app.storage.sqlite_store import SqliteStore
from app.utils.ids import utc_now_iso


@pytest.fixture()
def stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("PROCESSED_DIR", str(tmp_path / "processed"))
    monkeypatch.setenv("BOOKS_DIR", str(tmp_path / "books"))
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("LLM_MOCK", "true")
    monkeypatch.setenv("PROTOTYPE_ONE_SHOT", "true")
    get_settings.cache_clear()
    settings = get_settings()
    settings.ensure_directories()
    db = SqliteStore(settings)
    fs = FilesystemStore(settings)
    return settings, db, fs


def _seed_chapter(db: SqliteStore, fs: FilesystemStore, book_id: str = "b1") -> dict:
    chapter_id = "ch01"
    now = utc_now_iso()
    db.insert_book(
        {
            "book_id": book_id,
            "title": "Life 3.0",
            "author": "Max Tegmark",
            "epub_filename": "life.epub",
            "upload_timestamp": now,
            "processing_status": BookProcessingStatus.PREPARING_BLOCKS.value,
            "current_stage": UIStage.PREPARING_CHAPTER_BLOCKS.value,
            "chapter_count": 1,
            "processed_chapter_count": 0,
            "failed_chapter_count": 0,
            "job_id": "job-1",
            "error": None,
            "language": "en",
            "completion_timestamp": None,
            "current_chapter_id": None,
            "converter": "docling",
        }
    )
    chapter = {
        "chapter_id": chapter_id,
        "title": "Chapter 1",
        "chapter_number": 1,
        "order_index": 0,
        "status": ChapterStatus.PENDING.value,
        "retry_count": 0,
        "error": None,
        "preview": {},
    }
    db.replace_chapters(book_id, [chapter])
    block_id = f"{book_id}.{chapter_id}.sec01.block001"
    source = {
        "schema_version": "1.0",
        "book_id": book_id,
        "chapter_id": chapter_id,
        "source_blocks": [
            {
                "block_id": block_id,
                "block_type": "paragraph",
                "text": "Life 3.0 can redesign its hardware and software.",
                "section_id": "sec01",
            }
        ],
    }
    fs.write_json(fs.chapter_source_path(book_id, chapter_id), source)
    fs.write_json(
        fs.chapter_chunks_path(book_id, chapter_id),
        {
            "schema_version": "1.0",
            "book_id": book_id,
            "chapter_id": chapter_id,
            "chunks": [
                {
                    "chunk_id": f"{chapter_id}.c00",
                    "block_ids": [block_id],
                    "strategy": "single_chapter",
                }
            ],
            "strategy": "single_chapter",
        },
    )
    return chapter


def test_extract_chapter_oneshot_single_llm_call(stores) -> None:
    settings, db, fs = stores
    chapter = _seed_chapter(db, fs)
    pipe = ExtractPipeline(db, fs, settings)
    mock = MagicMock(wraps=MockLLMClient(settings))
    pipe.llm = mock

    result = pipe.extract_chapter_oneshot("b1", chapter, book=db.get_book("b1"))
    assert result["summary"]["ok"] is True
    assert result["summary"]["extract_mode"] == "oneshot"
    assert mock.complete_json.call_count == 1
    assert fs.chapter_spine_en_path("b1", "ch01").exists()
    assert fs.chapter_spine_path("b1", "ch01").exists()
    spine = fs.read_json(fs.chapter_spine_path("b1", "ch01"))
    assert spine["language_modes"] == ["en"]
    assert spine.get("nodes")


def test_validate_chapter_soft_completes_en_only(stores) -> None:
    settings, db, fs = stores
    chapter = _seed_chapter(db, fs)
    extract = ExtractPipeline(db, fs, settings)
    out = extract.extract_chapter_oneshot("b1", chapter, book=db.get_book("b1"))
    assert out["summary"]["ok"]

    validate = ValidatePersistPipeline(db, fs, settings)
    result = validate.validate_chapter_soft("b1", "ch01", chapter=out["chapter"])
    assert result["summary"]["ok"] is True
    assert result["chapter"]["status"] == ChapterStatus.COMPLETED.value
    spine = fs.read_json(fs.chapter_spine_path("b1", "ch01"))
    assert "hinglish" not in (spine.get("language_modes") or [])
    assert spine["validation"].get("mode") == "soft"


def test_run_ingest_sync_oneshot_skips_synth_adapt(
    stores, mini_epub_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, db, fs = stores
    service = BookService(db, fs)

    def boom_synth(*_a, **_k):
        raise AssertionError("synthesise should be skipped in oneshot mode")

    def boom_adapt(*_a, **_k):
        raise AssertionError("adapt should be skipped in oneshot mode")

    monkeypatch.setattr(service.synthesise, "synthesise_chapter", boom_synth)
    monkeypatch.setattr(service.adapt, "adapt_chapter", boom_adapt)

    real_oneshot = service.extract.extract_chapter_oneshot
    call_count = {"n": 0}

    def counting_oneshot(*args, **kwargs):
        call_count["n"] += 1
        return real_oneshot(*args, **kwargs)

    monkeypatch.setattr(service.extract, "extract_chapter_oneshot", counting_oneshot)

    meta = service.upload_epub(
        filename="mini.epub", data=mini_epub_bytes, max_size_bytes=5_000_000
    )
    db.update_book(
        meta.book_id,
        processing_status=BookProcessingStatus.UPLOADED.value,
        current_stage=UIStage.UPLOADING_EPUB.value,
        job_id="job-oneshot",
    )

    service.run_ingest_sync(meta.book_id)

    book = db.get_book(meta.book_id)
    assert book is not None
    assert book["processing_status"] == BookProcessingStatus.COMPLETED.value
    chapters = db.list_chapters(meta.book_id)
    assert chapters
    assert all(c["status"] == ChapterStatus.COMPLETED.value for c in chapters)
    assert call_count["n"] == len(chapters)
    first = chapters[0]["chapter_id"]
    spine = fs.read_json(fs.chapter_spine_path(meta.book_id, first))
    assert spine.get("nodes")
    assert spine["language_modes"] == ["en"]
