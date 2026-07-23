"""Phase 2: normalise Docling chapter spans into source chapters with stable block IDs."""

from __future__ import annotations

from typing import Any

from app.utils.ids import slugify

_NOISE_EXACT = {
    "",
    ".",
    "•",
    "image",
    "cover",
}

_LABEL_TO_BLOCK_TYPE = {
    "title": "heading",
    "section_header": "heading",
    "heading": "heading",
    "list_item": "list_item",
    "text": "paragraph",
    "paragraph": "paragraph",
    "caption": "note",
    "footnote": "note",
    "quote": "quote",
    "table": "table",
}


def _map_block_type(label: str | None) -> str:
    return _LABEL_TO_BLOCK_TYPE.get((label or "").lower(), "other")


def _is_noise_text(text: str) -> bool:
    cleaned = text.strip()
    if cleaned.lower() in _NOISE_EXACT:
        return True
    # Drop tiny decorative leftovers
    if len(cleaned) <= 1:
        return True
    return False


def make_block_id(book_id: str, chapter_id: str, section_id: str, block_ordinal: int) -> str:
    """Stable ID: book_id.chapter_id.section_id.blockNNN"""
    return f"{book_id}.{chapter_id}.{section_id}.block{block_ordinal:03d}"


def normalise_chapter_from_docling(
    *,
    book_id: str,
    chapter: dict[str, Any],
    docling_json: dict[str, Any],
) -> dict[str, Any]:
    """Build a source_chapter document for one detected chapter.

    Uses Phase 1 preview indices when present; otherwise falls back to matching
    the chapter title in Docling texts.
    """
    texts = docling_json.get("texts") or []
    preview = chapter.get("preview") or {}
    start = preview.get("source_text_start_index")
    end = preview.get("source_text_end_index")

    if start is None or end is None:
        start, end = _find_span_by_title(texts, chapter.get("title") or "")

    start = max(0, int(start or 0))
    end = min(len(texts), int(end if end is not None else len(texts)))

    chapter_id = chapter["chapter_id"]
    chapter_title = chapter.get("title") or chapter_id
    heading_hierarchy: list[str] = [chapter_title]

    source_blocks: list[dict[str, Any]] = []
    section_ordinal = 0
    section_id = "sec00"
    block_ordinal = 0

    for item in texts[start:end]:
        if not isinstance(item, dict):
            continue
        text = (item.get("text") or "").strip()
        if _is_noise_text(text):
            continue
        label = item.get("label")
        block_type = _map_block_type(label)

        if block_type == "heading":
            section_ordinal += 1
            section_id = f"sec{section_ordinal:02d}"
            # Keep hierarchy shallow: chapter + current heading
            heading_hierarchy = [chapter_title, text]

        block_ordinal += 1
        block_id = make_block_id(book_id, chapter_id, section_id, block_ordinal)
        source_blocks.append(
            {
                "block_id": block_id,
                "section_id": section_id,
                "block_type": block_type,
                "text": text,
                "order_index": len(source_blocks),
            }
        )

    return {
        "schema_version": "1.0",
        "book_id": book_id,
        "chapter_id": chapter_id,
        "chapter_number": chapter.get("chapter_number"),
        "chapter_title": chapter_title,
        "heading_hierarchy": heading_hierarchy,
        "source_blocks": source_blocks,
    }


def normalise_chapters_from_docling(
    *,
    book_id: str,
    chapters: list[dict[str, Any]],
    docling_json: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        normalise_chapter_from_docling(
            book_id=book_id, chapter=ch, docling_json=docling_json
        )
        for ch in chapters
    ]


def normalise_from_reference_clean_json(
    *,
    book_id: str,
    chapter: dict[str, Any],
    section_paragraphs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Normalise a reference-fixture chapter body into source blocks (tests)."""
    chapter_id = chapter["chapter_id"]
    chapter_title = chapter.get("title") or chapter_id
    source_blocks: list[dict[str, Any]] = []
    section_ordinal = 1
    section_id = "sec01"
    block_ordinal = 0

    # Leading heading block for the chapter title
    block_ordinal += 1
    source_blocks.append(
        {
            "block_id": make_block_id(book_id, chapter_id, section_id, block_ordinal),
            "section_id": section_id,
            "block_type": "heading",
            "text": chapter_title,
            "order_index": 0,
        }
    )

    for para in section_paragraphs:
        text = (para.get("text") or "").strip()
        if _is_noise_text(text):
            continue
        block_ordinal += 1
        source_blocks.append(
            {
                "block_id": make_block_id(book_id, chapter_id, section_id, block_ordinal),
                "section_id": section_id,
                "block_type": "paragraph",
                "text": text,
                "order_index": len(source_blocks),
            }
        )

    return {
        "schema_version": "1.0",
        "book_id": book_id,
        "chapter_id": chapter_id,
        "chapter_number": chapter.get("chapter_number"),
        "chapter_title": chapter_title,
        "heading_hierarchy": [chapter_title],
        "source_blocks": source_blocks,
    }


def assert_unique_block_ids(source_chapter: dict[str, Any]) -> None:
    ids = [b["block_id"] for b in source_chapter.get("source_blocks") or []]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source-block IDs in chapter")


def _find_span_by_title(texts: list[Any], title: str) -> tuple[int, int]:
    title_l = title.strip().lower()
    start = 0
    for idx, item in enumerate(texts):
        if not isinstance(item, dict):
            continue
        t = (item.get("text") or "").strip().lower()
        if t == title_l or (title_l and title_l in t):
            start = idx
            break
    # End at next heading-like item after start
    end = len(texts)
    for idx in range(start + 1, len(texts)):
        item = texts[idx]
        if not isinstance(item, dict):
            continue
        label = (item.get("label") or "").lower()
        if label in {"title", "section_header", "heading"}:
            end = idx
            break
    return start, end
