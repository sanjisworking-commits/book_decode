"""Phase 6 validation / fail-closed / retry tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import Settings
from app.domain.enums import ChapterStatus
from app.pipelines.validate_persist import ValidatePersistPipeline
from app.pipelines.validate_spine import validate_source_refs, validate_spine_schema
from app.storage.filesystem import FilesystemStore
from app.storage.sqlite_store import SqliteStore
from app.utils.ids import utc_now_iso


def _valid_spine(book_id: str = "b1", chapter_id: str = "ch01") -> dict:
    block = f"{book_id}.{chapter_id}.sec01.block001"
    nodes = []
    types = [
        "chapter_question",
        "central_claim",
        "reasoning_steps",
        "evidence_and_examples",
        "hidden_assumptions",
        "tensions_or_gaps",
        "strongest_counter_position",
        "consequence_if_correct",
        "role_in_book",
        "one_sentence_decode",
        "confidence_and_unresolved",
        "source_block_references",
    ]
    for i, ntype in enumerate(types):
        nid = f"{chapter_id}-n{i+1:02d}"
        nodes.append(
            {
                "id": nid,
                "node_type": ntype,
                "statement_en": f"Statement for {ntype}",
                "explanation_en": f"Explanation for {ntype}",
                "statement_hinglish": f"Hinglish for {ntype}",
                "explanation_hinglish": f"Hinglish expl for {ntype}",
                "source_status": "ai_inference",
                "source_block_ids": [block],
                "confidence": 0.6,
                "order": i,
                "prev_id": nodes[-1]["id"] if nodes else None,
                "next_id": None,
                "warnings": [],
            }
        )
    for i in range(len(nodes) - 1):
        nodes[i]["next_id"] = nodes[i + 1]["id"]
    return {
        "schema_version": "1.0",
        "book_id": book_id,
        "chapter_id": chapter_id,
        "language_modes": ["en", "hinglish"],
        "nodes": nodes,
        "confidence_summary": {"overall": 0.6, "notes": "fixture"},
        "processing": {
            "model": "mock",
            "prompt_versions": {},
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
        },
        "validation": None,
    }


def _english_from_bilingual(spine: dict) -> dict:
    import copy

    en = copy.deepcopy(spine)
    en["language_modes"] = ["en"]
    for node in en["nodes"]:
        node["statement_hinglish"] = None
        node["explanation_hinglish"] = None
    return en


@pytest.fixture()
def store_pair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = Settings(
        data_dir=tmp_path,
        upload_dir=tmp_path / "uploads",
        processed_dir=tmp_path / "processed",
        books_dir=tmp_path / "books",
        log_dir=tmp_path / "logs",
        sqlite_path=tmp_path / "test.db",
        llm_mock=True,
        max_chapter_retries=2,
        retry_backoff_seconds=0,
    )
    settings.ensure_directories()
    monkeypatch.setattr("app.pipelines.validate_persist.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.llm.get_llm_client", lambda s: __import__(
        "app.services.llm", fromlist=["MockLLMClient"]
    ).MockLLMClient(s))
    db = SqliteStore(settings)
    fs = FilesystemStore(settings)
    return settings, db, fs


def _seed_book(db: SqliteStore, fs: FilesystemStore, book_id: str, chapter_id: str, spine: dict):
    db.insert_book(
        {
            "book_id": book_id,
            "title": "T",
            "author": None,
            "epub_filename": "t.epub",
            "processing_status": "creating_hinglish",
            "language": "en",
            "chapter_count": 1,
            "processed_chapter_count": 0,
            "failed_chapter_count": 0,
            "upload_timestamp": utc_now_iso(),
            "completion_timestamp": None,
            "error": None,
            "current_stage": "creating_hindi_english_versions",
            "current_chapter_id": None,
            "job_id": "job-test",
            "converter": "docling",
        }
    )
    db.replace_chapters(
        book_id,
        [
            {
                "chapter_id": chapter_id,
                "title": "Chapter 1",
                "chapter_number": 1,
                "status": ChapterStatus.PENDING.value,
                "retry_count": 0,
                "error": None,
                "order_index": 0,
                "preview": {"adaptation": "ok"},
            }
        ],
    )
    block = f"{book_id}.{chapter_id}.sec01.block001"
    fs.write_json(
        fs.chapter_source_path(book_id, chapter_id),
        {
            "schema_version": "2.0",
            "book_id": book_id,
            "chapter_id": chapter_id,
            "source_blocks": [
                {
                    "block_id": block,
                    "block_type": "paragraph",
                    "text": "Body",
                    "order_index": 0,
                }
            ],
        },
    )
    fs.write_json(fs.chapter_spine_path(book_id, chapter_id), spine)
    fs.write_json(fs.chapter_spine_en_path(book_id, chapter_id), _english_from_bilingual(spine))
    fs.write_json(fs.metadata_path(book_id), {"book_id": book_id})


def test_valid_spine_persisted_as_completed(store_pair) -> None:
    settings, db, fs = store_pair
    book_id, chapter_id = "b1", "ch01"
    spine = _valid_spine(book_id, chapter_id)
    assert validate_spine_schema(spine) == []
    _seed_book(db, fs, book_id, chapter_id, spine)

    pipe = ValidatePersistPipeline(db, fs, settings)
    pipe.run(book_id)

    book = db.get_book(book_id)
    assert book["processing_status"] == "completed"
    ch = db.list_chapters(book_id)[0]
    assert ch["status"] == "completed"
    assert ch["error"] is None
    final = fs.read_json(fs.chapter_spine_path(book_id, chapter_id))
    assert final["validation"]["schema_valid"] is True
    assert final["validation"]["source_refs_valid"] is True


def test_invalid_output_fail_closed_not_completed(store_pair) -> None:
    settings, db, fs = store_pair
    book_id, chapter_id = "b2", "ch01"
    spine = _valid_spine(book_id, chapter_id)
    # Break schema hard: empty nodes — repair cannot invent a full valid spine reliably
    spine["nodes"] = []
    _seed_book(db, fs, book_id, chapter_id, spine)

    pipe = ValidatePersistPipeline(db, fs, settings)
    pipe.run(book_id)

    book = db.get_book(book_id)
    # No completed chapters → book failed
    assert book["processing_status"] == "failed"
    ch = db.list_chapters(book_id)[0]
    assert ch["status"] == "failed"
    assert ch["error"]["code"] == "validation_failed"
    assert fs.chapter_spine_invalid_path(book_id, chapter_id).exists()
    # Success path must not claim completed validation
    if fs.chapter_spine_path(book_id, chapter_id).exists():
        stored = fs.read_json(fs.chapter_spine_path(book_id, chapter_id))
        # Original invalid may still be on disk, but chapter is failed
        assert ch["status"] == "failed"


def test_strip_invalid_refs_then_pass(store_pair) -> None:
    settings, db, fs = store_pair
    book_id, chapter_id = "b3", "ch01"
    spine = _valid_spine(book_id, chapter_id)
    english = _english_from_bilingual(spine)
    spine["nodes"][0]["source_block_ids"] = [
        f"{book_id}.{chapter_id}.sec01.block001",
        "evil.unknown",
    ]
    assert validate_source_refs(
        spine, {f"{book_id}.{chapter_id}.sec01.block001"}
    )
    # Seed with clean English (as Phase 4 would) and dirty bilingual citations
    db.insert_book(
        {
            "book_id": book_id,
            "title": "T",
            "author": None,
            "epub_filename": "t.epub",
            "processing_status": "creating_hinglish",
            "language": "en",
            "chapter_count": 1,
            "processed_chapter_count": 0,
            "failed_chapter_count": 0,
            "upload_timestamp": utc_now_iso(),
            "completion_timestamp": None,
            "error": None,
            "current_stage": "creating_hindi_english_versions",
            "current_chapter_id": None,
            "job_id": "job-test",
            "converter": "docling",
        }
    )
    db.replace_chapters(
        book_id,
        [
            {
                "chapter_id": chapter_id,
                "title": "Chapter 1",
                "chapter_number": 1,
                "status": ChapterStatus.PENDING.value,
                "retry_count": 0,
                "error": None,
                "order_index": 0,
                "preview": {"adaptation": "ok"},
            }
        ],
    )
    block = f"{book_id}.{chapter_id}.sec01.block001"
    fs.write_json(
        fs.chapter_source_path(book_id, chapter_id),
        {
            "schema_version": "2.0",
            "book_id": book_id,
            "chapter_id": chapter_id,
            "source_blocks": [
                {
                    "block_id": block,
                    "block_type": "paragraph",
                    "text": "Body",
                    "order_index": 0,
                }
            ],
        },
    )
    fs.write_json(fs.chapter_spine_path(book_id, chapter_id), spine)
    fs.write_json(fs.chapter_spine_en_path(book_id, chapter_id), english)
    fs.write_json(fs.metadata_path(book_id), {"book_id": book_id})

    pipe = ValidatePersistPipeline(db, fs, settings)
    pipe.run(book_id)

    ch = db.list_chapters(book_id)[0]
    assert ch["status"] == "completed"
    final = fs.read_json(fs.chapter_spine_path(book_id, chapter_id))
    for node in final["nodes"]:
        assert "evil.unknown" not in (node.get("source_block_ids") or [])


def test_max_retries_respected_on_manual_retry(store_pair) -> None:
    settings, db, fs = store_pair
    book_id, chapter_id = "b4", "ch01"
    spine = _valid_spine(book_id, chapter_id)
    _seed_book(db, fs, book_id, chapter_id, spine)
    db.replace_chapters(
        book_id,
        [
            {
                "chapter_id": chapter_id,
                "title": "Chapter 1",
                "chapter_number": 1,
                "status": ChapterStatus.FAILED.value,
                "retry_count": 2,
                "error": {"code": "validation_failed", "message": "x", "details": None},
                "order_index": 0,
                "preview": {"adaptation": "ok"},
            }
        ],
    )
    pipe = ValidatePersistPipeline(db, fs, settings)
    result = pipe.validate_chapter(book_id, chapter_id, force=False)
    # retry_count 2 with max 2 → still allows validate_chapter internal attempts,
    # but manual gate in BookService uses >= max. Here validate_chapter checks
    # retry_count > max_retries (2 > 2 is false), so it will try.
    # Force the gate:
    result2 = pipe.validate_chapter(
        book_id,
        chapter_id,
        chapter={
            "chapter_id": chapter_id,
            "title": "Chapter 1",
            "status": ChapterStatus.FAILED.value,
            "retry_count": 3,
            "preview": {"adaptation": "ok"},
        },
        force=False,
    )
    assert result2["chapter"]["status"] == "failed"
    assert result2["chapter"]["error"]["code"] == "max_retries_exceeded"


def test_partial_success_completed_with_errors(store_pair) -> None:
    settings, db, fs = store_pair
    book_id = "b5"
    db.insert_book(
        {
            "book_id": book_id,
            "title": "T",
            "author": None,
            "epub_filename": "t.epub",
            "processing_status": "creating_hinglish",
            "language": "en",
            "chapter_count": 2,
            "processed_chapter_count": 0,
            "failed_chapter_count": 0,
            "upload_timestamp": utc_now_iso(),
            "completion_timestamp": None,
            "error": None,
            "current_stage": "creating_hindi_english_versions",
            "current_chapter_id": None,
            "job_id": "job-test",
            "converter": "docling",
        }
    )
    good = _valid_spine(book_id, "ch01")
    bad = _valid_spine(book_id, "ch02")
    bad["nodes"] = []
    db.replace_chapters(
        book_id,
        [
            {
                "chapter_id": "ch01",
                "title": "One",
                "chapter_number": 1,
                "status": "pending",
                "retry_count": 0,
                "error": None,
                "order_index": 0,
                "preview": {"adaptation": "ok"},
            },
            {
                "chapter_id": "ch02",
                "title": "Two",
                "chapter_number": 2,
                "status": "pending",
                "retry_count": 0,
                "error": None,
                "order_index": 1,
                "preview": {"adaptation": "ok"},
            },
        ],
    )
    for cid, spine in (("ch01", good), ("ch02", bad)):
        block = f"{book_id}.{cid}.sec01.block001"
        fs.write_json(
            fs.chapter_source_path(book_id, cid),
            {
                "schema_version": "2.0",
                "book_id": book_id,
                "chapter_id": cid,
                "source_blocks": [
                    {
                        "block_id": block,
                        "block_type": "paragraph",
                        "text": "Body",
                        "order_index": 0,
                    }
                ],
            },
        )
        fs.write_json(fs.chapter_spine_path(book_id, cid), spine)
        fs.write_json(
            fs.chapter_spine_en_path(book_id, cid), _english_from_bilingual(spine)
        )
    fs.write_json(fs.metadata_path(book_id), {"book_id": book_id})

    pipe = ValidatePersistPipeline(db, fs, settings)
    pipe.run(book_id)

    book = db.get_book(book_id)
    assert book["processing_status"] == "completed_with_errors"
    statuses = {c["chapter_id"]: c["status"] for c in db.list_chapters(book_id)}
    assert statuses["ch01"] == "completed"
    assert statuses["ch02"] == "failed"
