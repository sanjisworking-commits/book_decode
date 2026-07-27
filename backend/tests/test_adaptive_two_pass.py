"""Adaptive two-pass Argument Spine extraction tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.config import get_settings
from app.domain.enums import BookProcessingStatus, ChapterStatus, UIStage
from app.pipelines.discovery_validate import (
    strip_invalid_discovery_refs,
    validate_discovery,
)
from app.pipelines.extract import ExtractPipeline
from app.pipelines.validate_spine import (
    strip_invalid_relations,
    validate_relations,
    validate_spine_schema,
)
from app.services.llm import MockLLMClient
from app.storage.filesystem import FilesystemStore
from app.storage.sqlite_store import SqliteStore
from app.utils.ids import utc_now_iso

FIXTURE = Path(__file__).parent / "fixtures" / "ch02.source.json"


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


def _seed(
    db: SqliteStore,
    fs: FilesystemStore,
    *,
    book_id: str = "b1",
    chapter_id: str = "ch02",
    source: dict | None = None,
) -> dict:
    now = utc_now_iso()
    db.insert_book(
        {
            "book_id": book_id,
            "title": "Fixture Book",
            "author": "Test Author",
            "epub_filename": "fixture.json",
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
            "converter": "json",
        }
    )
    chapter = {
        "chapter_id": chapter_id,
        "title": "Chapter 2",
        "chapter_number": 2,
        "order_index": 0,
        "status": ChapterStatus.PENDING.value,
        "retry_count": 0,
        "error": None,
        "preview": {},
    }
    db.replace_chapters(book_id, [chapter])
    if source is None:
        source = json.loads(FIXTURE.read_text(encoding="utf-8"))
        source["book_id"] = book_id
        source["chapter_id"] = chapter_id
    fs.write_json(fs.chapter_source_path(book_id, chapter_id), source)
    block_ids = [b["block_id"] for b in source.get("source_blocks") or []]
    fs.write_json(
        fs.chapter_chunks_path(book_id, chapter_id),
        {
            "schema_version": "1.0",
            "book_id": book_id,
            "chapter_id": chapter_id,
            "chunks": [
                {
                    "chunk_id": f"{chapter_id}.c00",
                    "block_ids": block_ids,
                    "strategy": "single_chapter",
                }
            ],
            "strategy": "single_chapter",
        },
    )
    return chapter


def test_discovery_validate_rejects_invented_block_ids() -> None:
    discovery = {
        "schema_version": "1.0",
        "book_id": "b1",
        "chapter_id": "ch02",
        "chapter_types": ["conceptual_framework"],
        "argument_movements": [],
        "claims": [
            {
                "claim_id": "c01",
                "statement": "A claim",
                "source_block_ids": ["real.block", "invented.block"],
            }
        ],
        "supporting_material": [],
        "recommended_node_types": ["central_claim"],
        "omit_or_deemphasize": [],
    }
    errors = validate_discovery(discovery, {"real.block"})
    assert any("invented.block" in e for e in errors)
    cleaned = strip_invalid_discovery_refs(discovery, {"real.block"})
    assert cleaned["claims"][0]["source_block_ids"] == ["real.block"]


def test_empty_optional_discovery_arrays_ok() -> None:
    discovery = {
        "schema_version": "1.0",
        "book_id": "b1",
        "chapter_id": "ch02",
        "chapter_types": ["mixed"],
        "argument_movements": [],
        "claims": [],
        "supporting_material": [],
        "recommended_node_types": [],
        "omit_or_deemphasize": [],
    }
    errors = validate_discovery(discovery, set())
    assert errors == []


def test_relation_validation_and_strip() -> None:
    spine = {
        "schema_version": "2.0",
        "book_id": "b1",
        "chapter_id": "ch02",
        "language_modes": ["en"],
        "nodes": [
            {
                "id": "n1",
                "node_type": "central_claim",
                "statement_en": "Claim",
                "source_status": "author_paraphrase",
                "source_block_ids": ["b1"],
                "order": 0,
            },
            {
                "id": "n2",
                "node_type": "evidence",
                "statement_en": "Evidence",
                "source_status": "author_paraphrase",
                "source_block_ids": ["b1"],
                "order": 1,
            },
        ],
        "relations": [
            {
                "from_node_id": "n2",
                "to_node_id": "n1",
                "relation_type": "supports",
                "source_block_ids": ["b1"],
            },
            {
                "from_node_id": "missing",
                "to_node_id": "n1",
                "relation_type": "supports",
            },
            {
                "from_node_id": "n2",
                "to_node_id": "n1",
                "relation_type": "not_a_real_type",
            },
        ],
    }
    # Bad relation_type fails schema; strip_invalid_relations drops it anyway.
    schema_errors = validate_spine_schema(spine)
    assert any("relation_type" in e for e in schema_errors)
    errors = validate_relations(spine)
    assert len(errors) >= 2
    cleaned = strip_invalid_relations(spine, {"b1"})
    assert len(cleaned["relations"]) == 1
    assert cleaned["relations"][0]["from_node_id"] == "n2"
    assert validate_spine_schema(cleaned) == []
    assert validate_relations(cleaned) == []


def test_adaptive_oneshot_two_llm_calls(stores) -> None:
    settings, db, fs = stores
    chapter = _seed(db, fs)
    pipe = ExtractPipeline(db, fs, settings)
    mock = MagicMock(wraps=MockLLMClient(settings))
    pipe.llm = mock

    result = pipe.extract_chapter_oneshot("b1", chapter, book=db.get_book("b1"))
    assert result["summary"]["ok"] is True
    assert result["summary"]["adaptive_two_pass"] is True
    assert mock.complete_json.call_count == 2
    assert fs.chapter_discovery_path("b1", "ch02").exists()
    spine = fs.read_json(fs.chapter_spine_path("b1", "ch02"))
    assert spine["schema_version"] == "2.0"
    assert spine["language_modes"] == ["en"]
    assert any(n["node_type"] == "central_claim" for n in spine["nodes"])
    assert any(n["node_type"] == "objection" for n in spine["nodes"])
    assert spine.get("relations")
    for node in spine["nodes"]:
        assert node.get("statement_hinglish") is None


def test_ch02_fixture_two_pass_coverage(stores) -> None:
    settings, db, fs = stores
    chapter = _seed(db, fs)
    pipe = ExtractPipeline(db, fs, settings)
    result = pipe.extract_chapter_oneshot("b1", chapter, book=db.get_book("b1"))
    assert result["summary"]["ok"]
    discovery = fs.read_json(fs.chapter_discovery_path("b1", "ch02"))
    assert discovery.get("claims")
    assert discovery.get("supporting_material") is not None
    spine = fs.read_json(fs.chapter_spine_en_path("b1", "ch02"))
    types = {n["node_type"] for n in spine["nodes"]}
    assert "central_claim" in types or "organising_idea" in types
    assert "evidence" in types or "example" in types
    assert "objection" in types


def test_oversized_chapter_chunk_discovery_merge(stores, monkeypatch) -> None:
    settings, db, fs = stores
    # Force chunk path regardless of actual token size.
    monkeypatch.setattr(
        "app.pipelines.discovery.chapter_fits_discovery_budget",
        lambda **_k: False,
    )
    source = json.loads(FIXTURE.read_text(encoding="utf-8"))
    source["book_id"] = "b1"
    source["chapter_id"] = "ch02"
    # Split into two chunks in the plan
    blocks = source["source_blocks"]
    mid = max(1, len(blocks) // 2)
    chapter = _seed(db, fs, source=source)
    fs.write_json(
        fs.chapter_chunks_path("b1", "ch02"),
        {
            "schema_version": "1.0",
            "book_id": "b1",
            "chapter_id": "ch02",
            "chunks": [
                {
                    "chunk_id": "ch02.c00",
                    "block_ids": [b["block_id"] for b in blocks[:mid]],
                    "strategy": "token_fallback",
                },
                {
                    "chunk_id": "ch02.c01",
                    "block_ids": [b["block_id"] for b in blocks[mid:]],
                    "strategy": "token_fallback",
                },
            ],
            "strategy": "token_fallback",
        },
    )

    pipe = ExtractPipeline(db, fs, settings)
    mock = MagicMock(wraps=MockLLMClient(settings))
    pipe.llm = mock
    result = pipe.extract_chapter_oneshot("b1", chapter, book=db.get_book("b1"))
    assert result["summary"]["ok"] is True
    # 2 chunk discoveries + 1 merge + 1 synthesis
    assert mock.complete_json.call_count == 4
    assert result["summary"]["llm_calls"] == 4
    assert fs.chapter_discovery_path("b1", "ch02").exists()
