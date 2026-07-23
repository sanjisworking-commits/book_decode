"""Chapter detection tests."""

from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.chapter_detect import (
    detect_chapters_from_docling,
    detect_chapters_from_reference_clean_json,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_detect_from_docling_like_texts() -> None:
    docling = {
        "name": "Sample",
        "texts": [
            {"label": "title", "text": "Chapter 1"},
            {"label": "text", "text": "Body of chapter one with enough characters here."},
            {"label": "title", "text": "Chapter 2"},
            {"label": "text", "text": "Body of chapter two with enough characters here."},
        ],
    }
    chapters = detect_chapters_from_docling(docling)
    assert len(chapters) == 2
    assert chapters[0]["chapter_id"] == "ch01"
    assert chapters[1]["chapter_id"] == "ch02"
    assert chapters[0]["preview"]["text_char_count"] > 0


def test_detect_single_fallback_chapter() -> None:
    docling = {
        "name": "Essay",
        "texts": [
            {"label": "text", "text": "Only continuous prose without chapter headings present."},
        ],
    }
    chapters = detect_chapters_from_docling(docling)
    assert len(chapters) == 1
    assert chapters[0]["chapter_id"] == "ch01"


def test_detect_from_reference_fixture() -> None:
    fixture = REPO_ROOT / "sample-data" / "reference" / "a_thousand_brains_clean.json"
    assert fixture.exists(), fixture
    data = json.loads(fixture.read_text(encoding="utf-8"))
    chapters = detect_chapters_from_reference_clean_json(data)
    assert len(chapters) >= 5
    assert any(c.get("chapter_number") for c in chapters)
