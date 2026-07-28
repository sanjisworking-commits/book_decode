"""JSON-only source upload path tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import reset_cached_stores
from app.config import get_settings
from app.domain.enums import BookProcessingStatus, ChapterStatus
from app.services.books import BookService
from app.services.source_json_validation import (
    parse_source_json_payload,
    validate_source_book_payload,
    validate_source_chapter_payload,
)
from app.storage.filesystem import FilesystemStore
from app.storage.sqlite_store import SqliteStore


def _sample_source(**overrides) -> dict:
    payload = {
        "schema_version": "2.0",
        "book_id": "life-3-0",
        "chapter_id": "ch01",
        "chapter_number": 1,
        "chapter_title": "Chapter 1",
        "heading_hierarchy": ["Chapter 1"],
        "source_blocks": [
            {
                "block_id": "life-3-0.ch01.sec01.block001",
                "section_id": "sec01",
                "block_type": "paragraph",
                "text": "Life 3.0 can redesign its hardware.",
                "order_index": 0,
            },
            {
                "block_id": "life-3-0.ch01.sec01.block002",
                "section_id": "sec01",
                "block_type": "paragraph",
                "text": "Some experts disagree about timelines.",
                "order_index": 1,
            },
        ],
    }
    payload.update(overrides)
    return payload


def _sample_book(**overrides) -> dict:
    ch2 = _sample_source(
        chapter_id="ch02",
        chapter_number=2,
        chapter_title="Chapter 2",
        heading_hierarchy=["Chapter 2"],
        source_blocks=[
            {
                "block_id": "life-3-0.ch02.sec01.block001",
                "section_id": "sec01",
                "block_type": "paragraph",
                "text": "Chapter two expands the claim.",
                "order_index": 0,
            }
        ],
    )
    payload = {
        "schema_version": "2.0",
        "book_id": "life-3-0",
        "book_title": "Life 3.0",
        "chapters": [_sample_source(), ch2],
    }
    payload.update(overrides)
    return payload


def test_validate_source_chapter_payload_ok() -> None:
    out = validate_source_chapter_payload(_sample_source())
    assert out["chapter_id"] == "ch01"
    assert len(out["source_blocks"]) == 2


def test_validate_rejects_duplicate_block_ids() -> None:
    bad = _sample_source()
    bad["source_blocks"][1]["block_id"] = bad["source_blocks"][0]["block_id"]
    with pytest.raises(ValueError) as exc:
        validate_source_chapter_payload(bad)
    assert exc.value.args[0] == "invalid_source_json"


def test_validate_rejects_empty_blocks() -> None:
    with pytest.raises(ValueError) as exc:
        validate_source_chapter_payload(_sample_source(source_blocks=[]))
    assert exc.value.args[0] == "invalid_source_json"


def test_validate_accepts_caption_block_type() -> None:
    payload = _sample_source()
    payload["source_blocks"][0]["block_type"] = "caption"
    out = validate_source_chapter_payload(payload)
    assert out["source_blocks"][0]["block_type"] == "caption"


def test_validate_coerces_unknown_block_type_to_other() -> None:
    payload = _sample_source()
    payload["source_blocks"][0]["block_type"] = "pullquote"
    out = validate_source_chapter_payload(payload)
    assert out["source_blocks"][0]["block_type"] == "other"


def test_validate_source_book_payload_ok() -> None:
    out = validate_source_book_payload(_sample_book())
    assert out["book_title"] == "Life 3.0"
    assert len(out["chapters"]) == 2
    assert out["chapters"][1]["chapter_id"] == "ch02"


def test_parse_detects_book_vs_chapter() -> None:
    kind, _ = parse_source_json_payload(_sample_book())
    assert kind == "book"
    kind, _ = parse_source_json_payload(_sample_source())
    assert kind == "chapter"


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
    reset_cached_stores()
    settings = get_settings()
    settings.ensure_directories()
    db = SqliteStore(settings)
    fs = FilesystemStore(settings)
    return settings, db, fs


def test_upload_source_json_writes_artefacts(stores) -> None:
    _settings, db, fs = stores
    service = BookService(db, fs)
    payload = json.dumps(_sample_source()).encode("utf-8")
    meta = service.upload_source_json(
        filename="ch01.json", data=payload, max_size_bytes=5_000_000
    )
    book = db.get_book(meta.book_id)
    assert book is not None
    assert book["converter"] == "json"
    chapters = db.list_chapters(meta.book_id)
    assert len(chapters) == 1
    chapter_id = chapters[0]["chapter_id"]
    assert fs.chapter_source_path(meta.book_id, chapter_id).exists()
    assert fs.chapter_chunks_path(meta.book_id, chapter_id).exists()
    source = fs.read_json(fs.chapter_source_path(meta.book_id, chapter_id))
    assert source["source_blocks"]


def test_upload_whole_book_json_creates_all_chapters(stores) -> None:
    _settings, db, fs = stores
    service = BookService(db, fs)
    payload = json.dumps(_sample_book()).encode("utf-8")
    meta = service.upload_source_json(
        filename="life.json", data=payload, max_size_bytes=5_000_000
    )
    assert meta.title == "Life 3.0"
    assert meta.chapter_count == 2
    chapters = db.list_chapters(meta.book_id)
    assert [c["chapter_id"] for c in chapters] == ["ch01", "ch02"]
    for ch in chapters:
        assert fs.chapter_source_path(meta.book_id, ch["chapter_id"]).exists()
        assert ch["status"] == ChapterStatus.PENDING.value


def test_append_preserves_completed_and_resumes(stores) -> None:
    _settings, db, fs = stores
    service = BookService(db, fs)
    meta = service.upload_source_json(
        filename="ch01.json",
        data=json.dumps(_sample_source()).encode("utf-8"),
        max_size_bytes=5_000_000,
    )
    db.update_book(
        meta.book_id,
        job_id="job-json",
        processing_status=BookProcessingStatus.QUEUED.value,
    )
    service.run_ingest_sync(meta.book_id)
    chapters = db.list_chapters(meta.book_id)
    assert chapters[0]["status"] == ChapterStatus.COMPLETED.value
    spine_path = fs.chapter_spine_path(meta.book_id, "ch01")
    assert spine_path.exists()
    spine_before = fs.read_json(spine_path)

    service.append_source_json(
        book_id=meta.book_id,
        filename="ch02.json",
        data=json.dumps(
            _sample_source(
                chapter_id="ch02",
                chapter_number=2,
                chapter_title="Chapter 2",
                source_blocks=[
                    {
                        "block_id": "life-3-0.ch02.sec01.block001",
                        "section_id": "sec01",
                        "block_type": "paragraph",
                        "text": "Second chapter text.",
                        "order_index": 0,
                    }
                ],
            )
        ).encode("utf-8"),
        max_size_bytes=5_000_000,
    )
    chapters = db.list_chapters(meta.book_id)
    assert len(chapters) == 2
    assert chapters[0]["status"] == ChapterStatus.COMPLETED.value
    assert chapters[1]["status"] == ChapterStatus.PENDING.value
    assert fs.read_json(spine_path) == spine_before

    service.resume_processing(meta.book_id)
    service.run_ingest_sync(meta.book_id)
    chapters = db.list_chapters(meta.book_id)
    assert chapters[0]["status"] == ChapterStatus.COMPLETED.value
    assert chapters[1]["status"] == ChapterStatus.COMPLETED.value
    assert fs.read_json(spine_path) == spine_before


def test_run_ingest_sync_json_skips_docling(stores, monkeypatch: pytest.MonkeyPatch) -> None:
    _settings, db, fs = stores
    service = BookService(db, fs)

    def boom_ingest(*_a, **_k):
        raise AssertionError("Docling ingest must be skipped for JSON books")

    monkeypatch.setattr(service.ingest, "run", boom_ingest)

    payload = json.dumps(_sample_source()).encode("utf-8")
    meta = service.upload_source_json(
        filename="ch01.json", data=payload, max_size_bytes=5_000_000
    )
    db.update_book(
        meta.book_id,
        job_id="job-json",
        processing_status=BookProcessingStatus.QUEUED.value,
    )
    service.run_ingest_sync(meta.book_id)

    book = db.get_book(meta.book_id)
    assert book is not None
    assert book["processing_status"] == BookProcessingStatus.COMPLETED.value
    chapters = db.list_chapters(meta.book_id)
    assert chapters[0]["status"] == ChapterStatus.COMPLETED.value
    spine = fs.read_json(fs.chapter_spine_path(meta.book_id, chapters[0]["chapter_id"]))
    assert spine.get("nodes")


def test_api_upload_json_invalid_returns_400(client: TestClient) -> None:
    bad = json.dumps({"chapter_id": "ch01", "source_blocks": []}).encode("utf-8")
    res = client.post(
        "/books/upload-json",
        files={"file": ("bad.json", bad, "application/json")},
    )
    assert res.status_code == 400
    body = res.json()
    assert body["error"]["code"] == "invalid_source_json"


def test_api_upload_json_ok(client: TestClient) -> None:
    payload = json.dumps(_sample_source()).encode("utf-8")
    res = client.post(
        "/books/upload-json",
        files={"file": ("ch01.json", payload, "application/json")},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["book_id"]
    assert body["title"] == "Chapter 1"
    assert body.get("converter") == "json"

    status = client.get(f"/books/{body['book_id']}/chapters")
    assert status.status_code == 200
    chapters = status.json()["chapters"]
    assert len(chapters) == 1
    assert chapters[0]["chapter_id"] == "ch01"

    source = client.get(f"/books/{body['book_id']}/chapters/ch01/source")
    assert source.status_code == 200
    assert len(source.json()["source_blocks"]) == 2


def test_api_upload_whole_book_json(client: TestClient) -> None:
    payload = json.dumps(_sample_book()).encode("utf-8")
    res = client.post(
        "/books/upload-json",
        files={"file": ("book.json", payload, "application/json")},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["title"] == "Life 3.0"
    chapters = client.get(f"/books/{body['book_id']}/chapters").json()["chapters"]
    assert len(chapters) == 2


def test_api_append_chapter_json(client: TestClient) -> None:
    first = json.dumps(_sample_source()).encode("utf-8")
    res = client.post(
        "/books/upload-json",
        files={"file": ("ch01.json", first, "application/json")},
    )
    assert res.status_code == 201
    book_id = res.json()["book_id"]
    # Finish ch01 decode before append in this sync TestClient path.
    client.post(f"/books/{book_id}/process")

    second = json.dumps(
        _sample_source(
            chapter_id="ch02",
            chapter_number=2,
            chapter_title="Chapter 2",
            source_blocks=[
                {
                    "block_id": "life-3-0.ch02.sec01.block001",
                    "section_id": "sec01",
                    "block_type": "paragraph",
                    "text": "Second chapter.",
                    "order_index": 0,
                }
            ],
        )
    ).encode("utf-8")
    append = client.post(
        f"/books/{book_id}/chapters/upload-json",
        files={"file": ("ch02.json", second, "application/json")},
    )
    assert append.status_code == 201, append.text
    chapters = client.get(f"/books/{book_id}/chapters").json()["chapters"]
    assert len(chapters) == 2
    assert {c["chapter_id"] for c in chapters} == {"ch01", "ch02"}


def test_retry_chapter_reextracts_when_spine_missing(stores) -> None:
    """Retry must re-run oneshot extract, not validate-only (no spine artefact)."""
    _settings, db, fs = stores
    service = BookService(db, fs)
    meta = service.upload_source_json(
        filename="ch02.json",
        data=json.dumps(
            _sample_source(
                chapter_id="ch02",
                chapter_number=2,
                chapter_title="Vernon Mountcastle",
            )
        ).encode("utf-8"),
        max_size_bytes=5_000_000,
    )
    chapters = db.list_chapters(meta.book_id)
    db.replace_chapters(
        meta.book_id,
        [
            {
                **chapters[0],
                "status": ChapterStatus.FAILED.value,
                "error": {
                    "code": "extraction_failed",
                    "message": "LLM timeout",
                    "details": {"extract_mode": "oneshot"},
                },
            }
        ],
    )
    db.update_book(
        meta.book_id,
        processing_status=BookProcessingStatus.COMPLETED_WITH_ERRORS.value,
        failed_chapter_count=1,
        processed_chapter_count=0,
    )
    assert not fs.chapter_spine_path(meta.book_id, "ch02").exists()

    status = service.retry_chapter(meta.book_id, "ch02")
    ch = next(c for c in status.chapters if c.chapter_id == "ch02")
    assert ch.status == ChapterStatus.COMPLETED.value, (
        ch.error.message if ch.error else ch.status
    )
    assert fs.chapter_spine_path(meta.book_id, "ch02").exists()
    assert (ch.error is None) or (ch.error.message != "No spine artefact found for validation.")


def test_retry_recovers_after_exhausted_validate_only_retries(stores) -> None:
    """Stuck CH02: retry_count exhausted + no spine must still re-extract."""
    _settings, db, fs = stores
    service = BookService(db, fs)
    payload = Path(
        "/home/ubuntu/.cursor/projects/workspace/uploads/ch02.source_caeb.json"
    )
    if payload.exists():
        data = payload.read_bytes()
    else:
        data = json.dumps(
            _sample_source(
                chapter_id="ch02",
                chapter_number=2,
                chapter_title="Vernon Mountcastle's Big Idea",
            )
        ).encode("utf-8")
    meta = service.upload_source_json(
        filename="ch02.source.json", data=data, max_size_bytes=5_000_000
    )
    chapters = db.list_chapters(meta.book_id)
    db.replace_chapters(
        meta.book_id,
        [
            {
                **chapters[0],
                "status": ChapterStatus.FAILED.value,
                "retry_count": service.validate_persist.max_retries,
                "error": {
                    "code": "validation_failed",
                    "message": "No spine artefact found for validation.",
                    "details": None,
                },
            }
        ],
    )
    db.update_book(
        meta.book_id,
        processing_status=BookProcessingStatus.COMPLETED_WITH_ERRORS.value,
        failed_chapter_count=1,
        processed_chapter_count=0,
    )

    status = service.retry_chapter(meta.book_id, "ch02")
    ch = next(c for c in status.chapters if c.chapter_id == "ch02")
    assert ch.status == ChapterStatus.COMPLETED.value, (
        ch.error.message if ch.error else ch.status
    )
    assert fs.chapter_spine_path(meta.book_id, "ch02").exists()
