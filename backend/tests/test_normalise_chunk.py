"""Phase 2 normalisation and chunking unit tests."""

from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.chapter_detect import detect_chapters_from_reference_clean_json
from app.pipelines.chunk import chunk_source_chapter, validate_chunk_allow_lists
from app.pipelines.normalise import (
    assert_unique_block_ids,
    make_block_id,
    normalise_chapter_from_docling,
    normalise_from_reference_clean_json,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_make_block_id_format() -> None:
    bid = make_block_id("my-book", "ch03", "sec02", 14)
    assert bid == "my-book.ch03.sec02.block014"


def test_normalise_docling_assigns_unique_stable_ids() -> None:
    docling = {
        "name": "Sample",
        "texts": [
            {"label": "title", "text": "Chapter 1"},
            {"label": "text", "text": "First paragraph of the chapter."},
            {"label": "section_header", "text": "A subsection"},
            {"label": "text", "text": "Second paragraph under subsection."},
            {"label": "list_item", "text": "A list item"},
            {"label": "title", "text": "Chapter 2"},
            {"label": "text", "text": "Other chapter body."},
        ],
    }
    chapter = {
        "chapter_id": "ch01",
        "title": "Chapter 1",
        "chapter_number": 1,
        "preview": {"source_text_start_index": 0, "source_text_end_index": 5},
    }
    source = normalise_chapter_from_docling(
        book_id="demo-book", chapter=chapter, docling_json=docling
    )
    assert source["schema_version"] == "2.0"
    assert source["book_id"] == "demo-book"
    assert len(source["source_blocks"]) >= 3
    assert_unique_block_ids(source)
    ids = [b["block_id"] for b in source["source_blocks"]]
    assert all(i.startswith("demo-book.ch01.") for i in ids)
    assert any(b["block_type"] == "heading" for b in source["source_blocks"])
    assert any(b["block_type"] == "paragraph" for b in source["source_blocks"])


def test_chunk_small_chapter_single_unit() -> None:
    source = {
        "schema_version": "1.0",
        "book_id": "b1",
        "chapter_id": "ch01",
        "chapter_number": 1,
        "chapter_title": "Short",
        "heading_hierarchy": ["Short"],
        "source_blocks": [
            {
                "block_id": "b1.ch01.sec01.block001",
                "section_id": "sec01",
                "block_type": "paragraph",
                "text": "Short body.",
                "order_index": 0,
            }
        ],
    }
    plan = chunk_source_chapter(source, token_limit=6000, overlap_blocks=2)
    assert plan["strategy"] == "single_chapter"
    assert len(plan["chunks"]) == 1
    validate_chunk_allow_lists(source, plan)


def test_chunk_large_chapter_splits_and_preserves_allow_list() -> None:
    blocks = []
    for i in range(20):
        section = f"sec{(i // 5) + 1:02d}"
        btype = "heading" if i % 5 == 0 else "paragraph"
        text = ("word " * 400) if btype == "paragraph" else f"Heading {i}"
        blocks.append(
            {
                "block_id": f"b1.ch01.{section}.block{i+1:03d}",
                "section_id": section,
                "block_type": btype,
                "text": text,
                "order_index": i,
            }
        )
    source = {
        "schema_version": "1.0",
        "book_id": "b1",
        "chapter_id": "ch01",
        "chapter_number": 1,
        "chapter_title": "Long",
        "heading_hierarchy": ["Long"],
        "source_blocks": blocks,
    }
    plan = chunk_source_chapter(source, token_limit=500, overlap_blocks=1)
    assert len(plan["chunks"]) >= 2
    validate_chunk_allow_lists(source, plan)
    # Overlap may duplicate ids across adjacent chunks; within a chunk still unique
    for chunk in plan["chunks"]:
        assert len(chunk["block_ids"]) == len(set(chunk["block_ids"]))


def test_normalise_reference_fixture_chapter() -> None:
    fixture = REPO_ROOT / "sample-data" / "reference" / "a_thousand_brains_clean.json"
    data = json.loads(fixture.read_text(encoding="utf-8"))
    detected = detect_chapters_from_reference_clean_json(data)
    assert detected
    # Build paragraphs from matching sections for first detected chapter
    ch = detected[0]
    # Use a few paragraphs from front sections as stand-in body
    paras = []
    for section in data["sections"]:
        for p in section.get("paragraphs") or []:
            if p.get("text"):
                paras.append(p)
            if len(paras) >= 5:
                break
        if len(paras) >= 5:
            break
    source = normalise_from_reference_clean_json(
        book_id="a-thousand-brains", chapter=ch, section_paragraphs=paras
    )
    assert_unique_block_ids(source)
    assert source["source_blocks"]
    assert source["source_blocks"][0]["block_id"].startswith("a-thousand-brains.")
