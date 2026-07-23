"""Domain types for canonical book normalisation (schema 2.0)."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

BlockType = Literal[
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
    "equation",
    "code",
    "sidebar",
    "callout",
    "exercise",
    "summary",
    "warning",
    "example",
    "other",
]


class BlockMetadata(TypedDict, total=False):
    label: str | None
    heading_level: int | None
    word_count: int
    char_count: int
    table: dict[str, Any]
    list_style: str
    items: list[dict[str, Any]]
    figure_id: str | None
    caption: str | None
    caption_source_ref: str | None
    note_kind: str
    linked_block_id: str | None


class Block(TypedDict):
    block_id: str
    block_type: str
    text: str
    book_id: str
    chapter_id: str | None
    section_id: str | None
    part_id: str | None
    heading_path: list[str]
    source_ref: str | None
    docling_index: int | None
    order_index: int
    book_order_index: int
    metadata: dict[str, Any]


class Section(TypedDict):
    section_id: str
    title: str | None
    heading_level: int | None
    heading_path: list[str]
    order_index: int
    source_ref: str | None
    blocks: list[Block]


class Chapter(TypedDict):
    chapter_id: str
    title: str
    chapter_number: int | None
    part_id: str | None
    order_index: int
    source_ref: str | None
    heading_path: list[str]
    sections: list[Section]
    blocks: list[Block]


class Part(TypedDict):
    part_id: str
    title: str
    order_index: int
    source_ref: str | None
    chapters: list[Chapter]


class FrontMatter(TypedDict):
    blocks: list[Block]


class CanonicalBook(TypedDict):
    schema_version: str
    book_id: str
    title: str
    author: str | None
    language: str | None
    source: dict[str, Any]
    front_matter: FrontMatter
    parts: NotRequired[list[Part]]
    chapters: list[Chapter]


class StreamItem(TypedDict):
    kind: str  # text | table | picture
    index: int
    source_ref: str | None
    payload: dict[str, Any]
