"""Canonical book normalisation tests (schema 2.0)."""

from __future__ import annotations

import pytest

from app.pipelines.chunk import chunk_source_chapter, validate_chunk_allow_lists
from app.pipelines.normalise import (
    CanonicalBookValidationError,
    assert_unique_block_ids,
    normalise_book_from_docling,
    to_source_chapter,
    validate_canonical_book,
)


def _docling_texts(*items: dict) -> dict:
    texts = []
    for i, item in enumerate(items):
        row = dict(item)
        row.setdefault("self_ref", f"#/texts/{i}")
        texts.append(row)
    return {"name": "Fixture Book", "texts": texts}


def test_parts_and_chapters_hierarchy() -> None:
    docling = _docling_texts(
        {"label": "title", "text": "Part I", "level": 1},
        {"label": "title", "text": "Chapter 1", "level": 1},
        {"label": "text", "text": "Body of chapter one with enough words."},
        {"label": "title", "text": "Chapter 2", "level": 1},
        {"label": "text", "text": "Body of chapter two with enough words."},
        {"label": "title", "text": "Part II", "level": 1},
        {"label": "title", "text": "Chapter 3", "level": 1},
        {"label": "text", "text": "Body of chapter three with enough words."},
    )
    book = normalise_book_from_docling(book_id="demo", docling_json=docling)
    assert book["schema_version"] == "2.0"
    assert len(book.get("parts") or []) == 2
    assert [p["part_id"] for p in book["parts"]] == ["part01", "part02"]
    assert len(book["chapters"]) == 3
    assert book["chapters"][0]["part_id"] == "part01"
    assert book["chapters"][2]["part_id"] == "part02"
    assert book["parts"][0]["chapters"][0]["chapter_id"] == "ch01"


def test_without_parts() -> None:
    docling = _docling_texts(
        {"label": "title", "text": "Chapter 1", "level": 1},
        {"label": "text", "text": "Only chapter body text here."},
    )
    book = normalise_book_from_docling(book_id="demo", docling_json=docling)
    assert not book.get("parts")
    assert len(book["chapters"]) == 1
    assert book["chapters"][0]["chapter_id"] == "ch01"


def test_nested_heading_paths() -> None:
    docling = _docling_texts(
        {"label": "title", "text": "Chapter 1", "level": 1},
        {"label": "section_header", "text": "Reference Frames", "level": 2},
        {"label": "text", "text": "Intro under reference frames."},
        {"label": "section_header", "text": "Local Maps", "level": 3},
        {"label": "text", "text": "Nested under local maps."},
        {"label": "section_header", "text": "Another H2", "level": 2},
        {"label": "text", "text": "Sibling section body."},
    )
    book = normalise_book_from_docling(book_id="demo", docling_json=docling)
    ch = book["chapters"][0]
    assert len(ch["sections"]) >= 3
    nested = next(b for b in ch["blocks"] if "Nested under" in b["text"])
    assert nested["heading_path"] == ["Chapter 1", "Reference Frames", "Local Maps"]
    sibling = next(b for b in ch["blocks"] if "Sibling" in b["text"])
    assert sibling["heading_path"] == ["Chapter 1", "Another H2"]


def test_tables_preserved_structured() -> None:
    docling = {
        "name": "T",
        "texts": [
            {"label": "title", "text": "Chapter 1", "self_ref": "#/texts/0"},
        ],
        "tables": [
            {
                "self_ref": "#/tables/0",
                "label": "table",
                "captions": [{"text": "Table 1"}],
                "data": {
                    "grid": [
                        [
                            {"text": "A", "column_header": True},
                            {"text": "B", "column_header": True},
                        ],
                        [{"text": "1"}, {"text": "2"}],
                    ]
                },
            }
        ],
    }
    book = normalise_book_from_docling(book_id="demo", docling_json=docling)
    tables = [b for b in book["chapters"][0]["blocks"] if b["block_type"] == "table"]
    assert len(tables) == 1
    meta = tables[0]["metadata"]["table"]
    assert meta["headers"] == ["A", "B"]
    assert meta["rows"] == [["1", "2"]]
    assert meta["caption"] == "Table 1"
    assert "A | B" in tables[0]["text"]


def test_lists_as_list_and_list_items() -> None:
    docling = _docling_texts(
        {"label": "title", "text": "Chapter 1", "level": 1},
        {"label": "list_item", "text": "First item"},
        {"label": "list_item", "text": "Second item"},
        {"label": "text", "text": "After the list paragraph."},
    )
    book = normalise_book_from_docling(book_id="demo", docling_json=docling)
    blocks = book["chapters"][0]["blocks"]
    types = [b["block_type"] for b in blocks]
    assert "list" in types
    assert types.count("list_item") == 2
    list_block = next(b for b in blocks if b["block_type"] == "list")
    assert len(list_block["metadata"]["items"]) == 2
    assert "First item" in list_block["text"]


def test_figures_with_caption() -> None:
    docling = {
        "name": "F",
        "texts": [{"label": "title", "text": "Chapter 1", "self_ref": "#/texts/0"}],
        "pictures": [
            {
                "self_ref": "#/pictures/0",
                "label": "picture",
                "captions": [{"text": "A cortical column diagram"}],
            }
        ],
    }
    book = normalise_book_from_docling(book_id="demo", docling_json=docling)
    figs = [b for b in book["chapters"][0]["blocks"] if b["block_type"] == "figure"]
    assert len(figs) == 1
    assert figs[0]["text"] == "A cortical column diagram"
    assert figs[0]["metadata"]["caption"] == "A cortical column diagram"


def test_footnotes_as_note() -> None:
    docling = _docling_texts(
        {"label": "title", "text": "Chapter 1", "level": 1},
        {"label": "text", "text": "Main paragraph with a reference."},
        {"label": "footnote", "text": "See Hawkins 2021 for details."},
    )
    book = normalise_book_from_docling(book_id="demo", docling_json=docling)
    notes = [b for b in book["chapters"][0]["blocks"] if b["block_type"] == "note"]
    assert len(notes) == 1
    assert notes[0]["metadata"]["note_kind"] == "footnote"


def test_duplicate_headings_unique_ids() -> None:
    docling = _docling_texts(
        {"label": "title", "text": "Chapter 1", "level": 1},
        {"label": "section_header", "text": "Overview", "level": 2},
        {"label": "text", "text": "First overview body."},
        {"label": "section_header", "text": "Overview", "level": 2},
        {"label": "text", "text": "Second overview body."},
    )
    book = normalise_book_from_docling(book_id="demo", docling_json=docling)
    ids = [b["block_id"] for b in book["chapters"][0]["blocks"]]
    assert len(ids) == len(set(ids))


def test_duplicate_id_validation_fails() -> None:
    book = normalise_book_from_docling(
        book_id="demo",
        docling_json=_docling_texts(
            {"label": "title", "text": "Chapter 1", "level": 1},
            {"label": "text", "text": "Some real prose content."},
        ),
    )
    book["chapters"][0]["blocks"][0]["block_id"] = book["chapters"][0]["blocks"][1][
        "block_id"
    ]
    with pytest.raises(CanonicalBookValidationError):
        validate_canonical_book(book)


def test_noise_dropped_prose_kept() -> None:
    docling = _docling_texts(
        {"label": "title", "text": "Chapter 1", "level": 1},
        {"label": "text", "text": "."},
        {"label": "text", "text": "•"},
        {"label": "text", "text": "image"},
        {"label": "text", "text": "Jeff Hawkins wrote about the neocortex."},
    )
    book = normalise_book_from_docling(book_id="demo", docling_json=docling)
    texts = [b["text"] for b in book["chapters"][0]["blocks"] if b["block_type"] == "paragraph"]
    assert texts == ["Jeff Hawkins wrote about the neocortex."]


def test_no_chapter_markers_promotes_body() -> None:
    docling = _docling_texts(
        {"label": "text", "text": "Preface style opening paragraph."},
        {"label": "section_header", "text": "A Theme", "level": 1},
        {"label": "text", "text": "Continuing without chapter markers."},
    )
    book = normalise_book_from_docling(book_id="demo", docling_json=docling)
    assert len(book["chapters"]) == 1
    assert book["chapters"][0]["chapter_id"] == "ch01"
    assert not book["front_matter"]["blocks"]
    assert any("Continuing" in b["text"] for b in book["chapters"][0]["blocks"])


def test_adapter_output_chunkable() -> None:
    docling = _docling_texts(
        {"label": "title", "text": "Chapter 1", "level": 1},
        {"label": "text", "text": "Paragraph one for chunking."},
        {"label": "list_item", "text": "Bullet one"},
        {"label": "list_item", "text": "Bullet two"},
        {"label": "text", "text": "Paragraph two after list."},
    )
    book = normalise_book_from_docling(book_id="demo", docling_json=docling)
    source = to_source_chapter(book, "ch01")
    assert source["schema_version"] == "2.0"
    assert_unique_block_ids(source)
    assert all(b.get("text") is not None for b in source["source_blocks"])
    assert all(b.get("block_id") for b in source["source_blocks"])
    plan = chunk_source_chapter(source, token_limit=6000, overlap_blocks=1)
    validate_chunk_allow_lists(source, plan)


def test_front_matter_before_first_chapter() -> None:
    docling = _docling_texts(
        {"label": "text", "text": "Copyright page text retained."},
        {"label": "title", "text": "Chapter 1", "level": 1},
        {"label": "text", "text": "Chapter body after front matter."},
    )
    book = normalise_book_from_docling(book_id="demo", docling_json=docling)
    assert any("Copyright" in b["text"] for b in book["front_matter"]["blocks"])
    assert book["chapters"][0]["chapter_id"] == "ch01"


def test_part_interstitial_not_front_matter_duplicate_ids() -> None:
    """Content between Part and next Chapter must not reuse front.sec00 IDs."""
    # Enough front-matter blocks that a reset chapter counter would collide
    front_items = [
        {"label": "text", "text": f"Front matter paragraph number {i}."}
        for i in range(1, 12)
    ]
    docling = _docling_texts(
        *front_items,
        {"label": "title", "text": "Chapter 1", "level": 1},
        {"label": "text", "text": "First chapter body with enough words here."},
        {"label": "title", "text": "Part 2", "level": 1},
        {"label": "section_header", "text": "Human Intelligence", "level": 2},
        {"label": "text", "text": "Part preamble before the next numbered chapter."},
        {"label": "title", "text": "Chapter 2", "level": 1},
        {"label": "text", "text": "Second chapter body with enough words here."},
    )
    book = normalise_book_from_docling(book_id="demo", docling_json=docling)
    validate_canonical_book(book)

    front_ids = [b["block_id"] for b in book["front_matter"]["blocks"]]
    assert all(".front.sec00." in bid for bid in front_ids)
    assert "Part preamble" not in " ".join(b["text"] for b in book["front_matter"]["blocks"])

    intro = next(c for c in book["chapters"] if c["chapter_id"].endswith("-intro"))
    assert any("Part preamble" in b["text"] for b in intro["blocks"])
    assert any("Human Intelligence" in b["text"] for b in intro["blocks"])
    assert book["chapters"][-1]["chapter_id"] == "ch02"
