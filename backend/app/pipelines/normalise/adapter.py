"""Adapters between canonical book and per-chapter source views."""

from __future__ import annotations

from typing import Any

from app.pipelines.normalise.builder import normalise_book_from_docling
from app.pipelines.normalise.types import CanonicalBook, Chapter


def to_source_chapter(book: CanonicalBook | dict[str, Any], chapter_id: str) -> dict[str, Any]:
    """Flatten one chapter into a Phase-3-compatible source_chapter document."""
    chapter = _find_chapter(book, chapter_id)
    if chapter is None:
        raise KeyError(chapter_id)

    source_blocks = []
    for block in chapter.get("blocks") or []:
        source_blocks.append(
            {
                "block_id": block["block_id"],
                "section_id": block.get("section_id"),
                "block_type": block["block_type"],
                "text": block.get("text") or "",
                "order_index": block.get("order_index", len(source_blocks)),
                "book_id": block.get("book_id") or book.get("book_id"),
                "chapter_id": block.get("chapter_id") or chapter_id,
                "heading_path": list(block.get("heading_path") or []),
                "source_ref": block.get("source_ref"),
                "docling_index": block.get("docling_index"),
                "book_order_index": block.get("book_order_index"),
                "metadata": dict(block.get("metadata") or {}),
            }
        )

    heading_hierarchy = list(chapter.get("heading_path") or [chapter.get("title") or chapter_id])
    return {
        "schema_version": "2.0",
        "book_id": book["book_id"],
        "chapter_id": chapter_id,
        "chapter_number": chapter.get("chapter_number"),
        "chapter_title": chapter.get("title") or chapter_id,
        "heading_hierarchy": heading_hierarchy,
        "source_blocks": source_blocks,
    }


def iter_source_chapters(book: CanonicalBook | dict[str, Any]) -> list[dict[str, Any]]:
    return [to_source_chapter(book, ch["chapter_id"]) for ch in book.get("chapters") or []]


def normalise_chapter_from_docling(
    *,
    book_id: str,
    chapter: dict[str, Any],
    docling_json: dict[str, Any],
) -> dict[str, Any]:
    """Backward-compatible wrapper: normalise full book, return one chapter view.

    Prefer `normalise_book_from_docling` + `to_source_chapter` for new code.
    """
    book = normalise_book_from_docling(
        book_id=book_id,
        docling_json=docling_json,
        title=docling_json.get("name"),
    )
    chapter_id = chapter.get("chapter_id")
    if chapter_id and _find_chapter(book, chapter_id):
        return to_source_chapter(book, chapter_id)

    # Fallback: match by title
    wanted = (chapter.get("title") or "").strip().lower()
    for ch in book.get("chapters") or []:
        if (ch.get("title") or "").strip().lower() == wanted:
            return to_source_chapter(book, ch["chapter_id"])

    # Last resort: use preview indices from old detector by filtering blocks
    # If nothing matches, return empty chapter shell
    if book.get("chapters"):
        return to_source_chapter(book, book["chapters"][0]["chapter_id"])
    return {
        "schema_version": "2.0",
        "book_id": book_id,
        "chapter_id": chapter.get("chapter_id") or "ch01",
        "chapter_number": chapter.get("chapter_number"),
        "chapter_title": chapter.get("title") or "Untitled",
        "heading_hierarchy": [chapter.get("title") or "Untitled"],
        "source_blocks": [],
    }


def normalise_chapters_from_docling(
    *,
    book_id: str,
    chapters: list[dict[str, Any]],
    docling_json: dict[str, Any],
) -> list[dict[str, Any]]:
    book = normalise_book_from_docling(book_id=book_id, docling_json=docling_json)
    return iter_source_chapters(book)


def normalise_from_reference_clean_json(
    *,
    book_id: str,
    chapter: dict[str, Any],
    section_paragraphs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a minimal source chapter from reference-fixture paragraphs (tests)."""
    from app.pipelines.normalise.ids import make_block_id
    from app.pipelines.normalise.labels import is_noise_text

    chapter_id = chapter["chapter_id"]
    chapter_title = chapter.get("title") or chapter_id
    source_blocks: list[dict[str, Any]] = []
    section_id = "sec01"
    ordinal = 0

    ordinal += 1
    source_blocks.append(
        {
            "block_id": make_block_id(book_id, chapter_id, section_id, ordinal),
            "section_id": section_id,
            "block_type": "heading",
            "text": chapter_title,
            "order_index": 0,
            "book_id": book_id,
            "chapter_id": chapter_id,
            "heading_path": [chapter_title],
            "source_ref": None,
            "docling_index": None,
            "book_order_index": 0,
            "metadata": {
                "label": "title",
                "heading_level": 1,
                "word_count": len(chapter_title.split()),
                "char_count": len(chapter_title),
            },
        }
    )
    for para in section_paragraphs:
        text = (para.get("text") or "").strip()
        if is_noise_text(text):
            continue
        ordinal += 1
        source_blocks.append(
            {
                "block_id": make_block_id(book_id, chapter_id, section_id, ordinal),
                "section_id": section_id,
                "block_type": "paragraph",
                "text": text,
                "order_index": len(source_blocks),
                "book_id": book_id,
                "chapter_id": chapter_id,
                "heading_path": [chapter_title],
                "source_ref": None,
                "docling_index": None,
                "book_order_index": len(source_blocks),
                "metadata": {
                    "label": "text",
                    "word_count": len(text.split()),
                    "char_count": len(text),
                },
            }
        )
    return {
        "schema_version": "2.0",
        "book_id": book_id,
        "chapter_id": chapter_id,
        "chapter_number": chapter.get("chapter_number"),
        "chapter_title": chapter_title,
        "heading_hierarchy": [chapter_title],
        "source_blocks": source_blocks,
    }


def _find_chapter(book: dict[str, Any], chapter_id: str) -> Chapter | None:
    for ch in book.get("chapters") or []:
        if ch.get("chapter_id") == chapter_id:
            return ch  # type: ignore[return-value]
    return None
