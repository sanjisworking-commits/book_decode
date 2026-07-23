"""Deterministic ID helpers for canonical book entities."""

from __future__ import annotations

import re


def slugify(value: str, fallback: str = "item") -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned[:48] or fallback


def make_part_id(ordinal: int) -> str:
    return f"part{ordinal:02d}"


def make_chapter_id(ordinal: int, number: int | None = None) -> str:
    if number is not None and number > 0:
        return f"ch{number:02d}"
    return f"ch{ordinal:02d}"


def make_section_id(ordinal: int) -> str:
    return f"sec{ordinal:02d}"


def make_block_id(
    book_id: str, chapter_id: str, section_id: str, block_ordinal: int
) -> str:
    """Stable ID: book_id.chapter_id.section_id.blockNNN"""
    return f"{book_id}.{chapter_id}.{section_id}.block{block_ordinal:03d}"


def make_front_block_id(book_id: str, block_ordinal: int) -> str:
    return f"{book_id}.front.sec00.block{block_ordinal:03d}"
