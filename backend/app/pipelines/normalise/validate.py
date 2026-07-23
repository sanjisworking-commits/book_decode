"""Validation for canonical book documents."""

from __future__ import annotations

from typing import Any

from app.pipelines.normalise.types import CanonicalBook


class CanonicalBookValidationError(ValueError):
    pass


def validate_canonical_book(book: CanonicalBook | dict[str, Any]) -> None:
    errors: list[str] = []

    book_id = book.get("book_id")
    if not book_id:
        errors.append("missing book_id")

    if book.get("schema_version") != "2.0":
        errors.append(f"unsupported schema_version: {book.get('schema_version')!r}")

    block_ids: set[str] = set()
    book_orders: set[int] = set()

    for block in (book.get("front_matter") or {}).get("blocks") or []:
        _check_block(block, block_ids, book_orders, errors, context="front_matter")

    chapters = book.get("chapters") or []
    chapter_ids: set[str] = set()
    for ch in chapters:
        cid = ch.get("chapter_id")
        if not cid:
            errors.append("chapter missing chapter_id")
            continue
        if cid in chapter_ids:
            errors.append(f"duplicate chapter_id: {cid}")
        chapter_ids.add(cid)
        if not (ch.get("title") or "").strip():
            errors.append(f"empty chapter title for {cid}")

        seen_order: set[int] = set()
        for block in ch.get("blocks") or []:
            _check_block(block, block_ids, book_orders, errors, context=cid)
            oi = block.get("order_index")
            if isinstance(oi, int):
                if oi in seen_order:
                    errors.append(f"duplicate order_index {oi} in chapter {cid}")
                seen_order.add(oi)

        for section in ch.get("sections") or []:
            sid = section.get("section_id")
            if not sid:
                errors.append(f"orphan/empty section_id in chapter {cid}")
            for block in section.get("blocks") or []:
                if block.get("chapter_id") not in (None, cid):
                    errors.append(
                        f"block {block.get('block_id')} chapter mismatch in section of {cid}"
                    )

    # Part references
    for part in book.get("parts") or []:
        pid = part.get("part_id")
        if not pid:
            errors.append("part missing part_id")
        if not (part.get("title") or "").strip():
            errors.append(f"empty part title for {pid}")

    if errors:
        raise CanonicalBookValidationError(
            "Canonical book validation failed: " + "; ".join(errors[:20])
        )


def assert_valid_book(book: CanonicalBook | dict[str, Any]) -> None:
    validate_canonical_book(book)


def assert_unique_block_ids(source_chapter: dict[str, Any]) -> None:
    """Compatibility helper for per-chapter source views."""
    ids = [b["block_id"] for b in source_chapter.get("source_blocks") or []]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source-block IDs in chapter")


def _check_block(
    block: dict[str, Any],
    block_ids: set[str],
    book_orders: set[int],
    errors: list[str],
    *,
    context: str,
) -> None:
    bid = block.get("block_id")
    if not bid:
        errors.append(f"empty block_id in {context}")
        return
    if bid in block_ids:
        errors.append(f"duplicate block_id: {bid}")
    block_ids.add(bid)
    boi = block.get("book_order_index")
    if isinstance(boi, int):
        if boi in book_orders:
            errors.append(f"duplicate book_order_index: {boi}")
        book_orders.add(boi)
    if block.get("source_ref") is None and block.get("docling_index") is None:
        # Soft warning-level: allow synthetic blocks but flag clearly
        # Keep as error only if both missing AND text empty
        if not (block.get("text") or "").strip():
            errors.append(f"block {bid} missing source provenance and text")
