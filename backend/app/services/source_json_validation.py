"""Validate uploaded source_chapter / source_book JSON for the JSON-only ingest path."""

from __future__ import annotations

from typing import Any, Literal

ALLOWED_BLOCK_TYPES = frozenset(
    {
        "heading",
        "paragraph",
        "quote",
        "table",
        "list",
        "list_item",
        "note",
        "image",
        "figure",
        "diagram",
        "caption",
        "equation",
        "code",
        "sidebar",
        "callout",
        "exercise",
        "summary",
        "warning",
        "example",
        "other",
    }
)


def is_book_wrapper_payload(payload: Any) -> bool:
    """True when the JSON is a whole-book wrapper with chapters[]."""
    return isinstance(payload, dict) and isinstance(payload.get("chapters"), list)


def validate_source_chapter_payload(payload: Any) -> dict[str, Any]:
    """Return a normalised source_chapter dict or raise ValueError(code, message)."""
    if not isinstance(payload, dict):
        raise ValueError("invalid_source_json", "Root JSON value must be an object.")

    schema_version = payload.get("schema_version")
    if schema_version is not None and str(schema_version) not in {"2.0", "1.0"}:
        raise ValueError(
            "invalid_source_json",
            f"Unsupported schema_version: {schema_version!r} (expected 2.0).",
        )

    chapter_id = str(payload.get("chapter_id") or "").strip()
    if not chapter_id:
        raise ValueError("invalid_source_json", "chapter_id is required.")

    chapter_title = str(payload.get("chapter_title") or chapter_id).strip()
    book_id_hint = str(payload.get("book_id") or "").strip()

    chapter_number = payload.get("chapter_number")
    if chapter_number is not None:
        try:
            chapter_number = int(chapter_number)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "invalid_source_json", "chapter_number must be an integer or null."
            ) from exc
        if chapter_number < 1:
            raise ValueError("invalid_source_json", "chapter_number must be >= 1.")

    hierarchy = payload.get("heading_hierarchy")
    if hierarchy is None:
        hierarchy = [chapter_title]
    if not isinstance(hierarchy, list) or not all(isinstance(x, str) for x in hierarchy):
        raise ValueError(
            "invalid_source_json", "heading_hierarchy must be an array of strings."
        )

    blocks_in = payload.get("source_blocks")
    if not isinstance(blocks_in, list) or not blocks_in:
        raise ValueError(
            "invalid_source_json", "source_blocks must be a non-empty array."
        )

    seen: set[str] = set()
    source_blocks: list[dict[str, Any]] = []
    for i, raw in enumerate(blocks_in):
        if not isinstance(raw, dict):
            raise ValueError(
                "invalid_source_json", f"source_blocks[{i}] must be an object."
            )
        block_id = str(raw.get("block_id") or "").strip()
        if not block_id:
            raise ValueError(
                "invalid_source_json", f"source_blocks[{i}].block_id is required."
            )
        if block_id in seen:
            raise ValueError(
                "invalid_source_json", f"Duplicate block_id: {block_id}"
            )
        seen.add(block_id)

        block_type = str(raw.get("block_type") or "paragraph").strip()
        if block_type not in ALLOWED_BLOCK_TYPES:
            # Hand-cleaned JSON may use labels like "caption"; keep text, coerce type.
            block_type = "other"

        text = raw.get("text")
        if text is None:
            text = ""
        if not isinstance(text, str):
            raise ValueError(
                "invalid_source_json", f"source_blocks[{i}].text must be a string."
            )

        order_index = raw.get("order_index", i)
        try:
            order_index = int(order_index)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "invalid_source_json",
                f"source_blocks[{i}].order_index must be an integer.",
            ) from exc
        if order_index < 0:
            raise ValueError(
                "invalid_source_json",
                f"source_blocks[{i}].order_index must be >= 0.",
            )

        block: dict[str, Any] = {
            "block_id": block_id,
            "block_type": block_type,
            "text": text,
            "order_index": order_index,
        }
        if raw.get("section_id") is not None:
            block["section_id"] = str(raw.get("section_id"))
        source_blocks.append(block)

    return {
        "schema_version": "2.0",
        "book_id": book_id_hint or "book",
        "chapter_id": chapter_id,
        "chapter_number": chapter_number,
        "chapter_title": chapter_title,
        "heading_hierarchy": hierarchy,
        "source_blocks": source_blocks,
    }


def validate_source_book_payload(payload: Any) -> dict[str, Any]:
    """Return a normalised whole-book wrapper or raise ValueError(code, message)."""
    if not isinstance(payload, dict):
        raise ValueError("invalid_source_json", "Root JSON value must be an object.")

    schema_version = payload.get("schema_version")
    if schema_version is not None and str(schema_version) not in {"2.0", "1.0"}:
        raise ValueError(
            "invalid_source_json",
            f"Unsupported schema_version: {schema_version!r} (expected 2.0).",
        )

    book_id_hint = str(payload.get("book_id") or "").strip()
    book_title = str(
        payload.get("book_title") or payload.get("title") or book_id_hint or "Untitled book"
    ).strip()

    chapters_in = payload.get("chapters")
    if not isinstance(chapters_in, list) or not chapters_in:
        raise ValueError(
            "invalid_source_json",
            "chapters must be a non-empty array for whole-book JSON.",
        )

    seen_chapter_ids: set[str] = set()
    chapters: list[dict[str, Any]] = []
    for i, raw in enumerate(chapters_in):
        if not isinstance(raw, dict):
            raise ValueError(
                "invalid_source_json", f"chapters[{i}] must be an object."
            )
        merged = dict(raw)
        if not merged.get("book_id") and book_id_hint:
            merged["book_id"] = book_id_hint
        if merged.get("schema_version") is None and schema_version is not None:
            merged["schema_version"] = schema_version
        try:
            chapter = validate_source_chapter_payload(merged)
        except ValueError as exc:
            code = str(exc.args[0]) if exc.args else "invalid_source_json"
            msg = str(exc.args[1]) if len(exc.args) >= 2 else str(exc)
            raise ValueError(code, f"chapters[{i}]: {msg}") from exc
        chapter_id = chapter["chapter_id"]
        if chapter_id in seen_chapter_ids:
            raise ValueError(
                "invalid_source_json",
                f"Duplicate chapter_id in chapters[]: {chapter_id}",
            )
        seen_chapter_ids.add(chapter_id)
        if chapter.get("chapter_number") is None:
            chapter["chapter_number"] = i + 1
        chapters.append(chapter)

    if not book_id_hint:
        book_id_hint = str(chapters[0].get("book_id") or "book")

    return {
        "schema_version": "2.0",
        "book_id": book_id_hint,
        "book_title": book_title,
        "chapters": chapters,
    }


def parse_source_json_payload(
    payload: Any,
) -> tuple[Literal["book", "chapter"], dict[str, Any]]:
    """Detect whole-book vs single-chapter upload and validate."""
    if is_book_wrapper_payload(payload):
        return "book", validate_source_book_payload(payload)
    return "chapter", validate_source_chapter_payload(payload)
