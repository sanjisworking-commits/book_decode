"""Build canonical book.json from Docling JSON (lossless, single-pass)."""

from __future__ import annotations

from typing import Any

from app.pipelines.normalise.hierarchy import HierarchyState
from app.pipelines.normalise.ids import (
    make_block_id,
    make_chapter_id,
    make_front_block_id,
    make_part_id,
    make_section_id,
)
from app.pipelines.normalise.labels import (
    char_count,
    extract_chapter_number,
    is_chapter_heading,
    is_heading_label,
    is_noise_text,
    is_part_heading,
    map_block_type,
    word_count,
)
from app.pipelines.normalise.traverse import iter_docling_stream
from app.pipelines.normalise.types import (
    Block,
    CanonicalBook,
    Chapter,
    FrontMatter,
    Part,
    Section,
    StreamItem,
)
from app.pipelines.normalise.validate import validate_canonical_book


def normalise_book_from_docling(
    *,
    book_id: str,
    docling_json: dict[str, Any],
    title: str | None = None,
    author: str | None = None,
    language: str | None = None,
) -> CanonicalBook:
    """Convert Docling export into canonical hierarchical book (schema 2.0)."""
    builder = _BookBuilder(
        book_id=book_id,
        title=title or docling_json.get("name") or book_id,
        author=author,
        language=language,
        docling_json=docling_json,
    )
    for item in iter_docling_stream(docling_json):
        builder.consume(item)
    book = builder.finish()
    validate_canonical_book(book)
    return book


class _BookBuilder:
    def __init__(
        self,
        *,
        book_id: str,
        title: str,
        author: str | None,
        language: str | None,
        docling_json: dict[str, Any],
    ) -> None:
        self.book_id = book_id
        self.title = title
        self.author = author
        self.language = language
        self.docling_json = docling_json

        self.hierarchy = HierarchyState()
        self.front_blocks: list[Block] = []
        self.parts: list[Part] = []
        self.chapters: list[Chapter] = []

        self.current_part: Part | None = None
        self.current_chapter: Chapter | None = None
        self.current_section: Section | None = None

        self.part_ordinal = 0
        self.chapter_ordinal = 0
        self.section_ordinal = 0
        self.block_ordinal = 0
        self.chapter_order_index = 0
        self.book_order_index = 0

        self._pending_list_items: list[dict[str, Any]] = []

    def consume(self, item: StreamItem) -> None:
        kind = item["kind"]
        payload = item["payload"]
        if kind == "text":
            self._consume_text(item)
        elif kind == "table":
            self._flush_list()
            self._emit_table(item)
        elif kind == "picture":
            self._flush_list()
            self._emit_picture(item)

    def finish(self) -> CanonicalBook:
        self._flush_list()
        self._close_section()
        self._close_chapter()

        # Books without explicit "Chapter N" markers: promote body into one chapter
        if not self.chapters and self.front_blocks:
            self._promote_front_matter_to_chapter()

        book: CanonicalBook = {
            "schema_version": "2.0",
            "book_id": self.book_id,
            "title": self.title,
            "author": self.author,
            "language": self.language,
            "source": {
                "converter": "docling",
                "docling_schema_name": self.docling_json.get("schema_name"),
                "docling_version": self.docling_json.get("version"),
            },
            "front_matter": FrontMatter(blocks=self.front_blocks),
            "chapters": self.chapters,
        }
        if self.parts:
            by_part: dict[str, list[Chapter]] = {p["part_id"]: [] for p in self.parts}
            for ch in self.chapters:
                pid = ch.get("part_id")
                if pid and pid in by_part:
                    by_part[pid].append(ch)
            for part in self.parts:
                part["chapters"] = by_part.get(part["part_id"], [])
            book["parts"] = self.parts
        return book

    def _promote_front_matter_to_chapter(self) -> None:
        """When no Chapter markers exist, wrap accumulated blocks as ch01."""
        chapter_id = make_chapter_id(1, 1)
        section_id = make_section_id(1)
        blocks: list[Block] = []
        for i, block in enumerate(self.front_blocks):
            new_block = dict(block)
            new_block["chapter_id"] = chapter_id
            new_block["section_id"] = section_id
            new_block["order_index"] = i
            new_block["block_id"] = make_block_id(
                self.book_id, chapter_id, section_id, i + 1
            )
            blocks.append(new_block)  # type: ignore[arg-type]
        section: Section = {
            "section_id": section_id,
            "title": self.title,
            "heading_level": 1,
            "heading_path": [self.title],
            "order_index": 0,
            "source_ref": None,
            "blocks": blocks,
        }
        chapter: Chapter = {
            "chapter_id": chapter_id,
            "title": self.title,
            "chapter_number": 1,
            "part_id": None,
            "order_index": 0,
            "source_ref": None,
            "heading_path": [self.title],
            "sections": [section],
            "blocks": blocks,
        }
        self.chapters.append(chapter)
        self.front_blocks = []

    def _consume_text(self, item: StreamItem) -> None:
        payload = item["payload"]
        text = (payload.get("text") or "").strip()
        label = payload.get("label")
        if is_noise_text(text) and not is_heading_label(label):
            return

        if is_heading_label(label):
            self._flush_list()
            self._handle_heading(item, text, label)
            return

        block_type = map_block_type(label)
        if block_type == "list_item":
            self._pending_list_items.append(
                {
                    "text": text,
                    "source_ref": item.get("source_ref"),
                    "docling_index": item.get("index"),
                    "label": label,
                }
            )
            return

        self._flush_list()
        if block_type == "note" or (label or "").lower() in {"footnote", "endnote", "caption"}:
            note_kind = (label or "note").lower()
            self._emit_block(
                block_type="note",
                text=text,
                source_ref=item.get("source_ref"),
                docling_index=item.get("index"),
                label=label,
                extra_meta={"note_kind": note_kind},
            )
            return

        if block_type == "quote":
            self._emit_block(
                block_type="quote",
                text=text,
                source_ref=item.get("source_ref"),
                docling_index=item.get("index"),
                label=label,
            )
            return

        self._emit_block(
            block_type=block_type if block_type != "heading" else "paragraph",
            text=text,
            source_ref=item.get("source_ref"),
            docling_index=item.get("index"),
            label=label,
        )

    def _handle_heading(self, item: StreamItem, text: str, label: Any) -> None:
        level = payload_level(item["payload"])
        if is_part_heading(text) and not is_chapter_heading(text):
            self._open_part(text, item)
            return
        if is_chapter_heading(text):
            self._open_chapter(text, item)
            return

        # Section heading within current chapter, or front-matter heading
        path = self.hierarchy.update_heading(level, text)
        if self.current_chapter is None:
            self._emit_block(
                block_type="heading",
                text=text,
                source_ref=item.get("source_ref"),
                docling_index=item.get("index"),
                label=label,
                heading_level=level,
                heading_path_override=path,
            )
            return
        self._open_section(text, item, level, path)

    def _open_part(self, title: str, item: StreamItem) -> None:
        self._flush_list()
        self._close_section()
        self._close_chapter()
        self.part_ordinal += 1
        part_id = make_part_id(self.part_ordinal)
        part: Part = {
            "part_id": part_id,
            "title": title,
            "order_index": self.part_ordinal - 1,
            "source_ref": item.get("source_ref"),
            "chapters": [],
        }
        self.parts.append(part)
        self.current_part = part
        self.hierarchy.replace_root([title])

    def _open_chapter(self, title: str, item: StreamItem) -> None:
        self._flush_list()
        self._close_section()
        self._close_chapter()
        self.chapter_ordinal += 1
        number = extract_chapter_number(title)
        chapter_id = make_chapter_id(self.chapter_ordinal, number)
        # Ensure unique chapter ids
        existing = {c["chapter_id"] for c in self.chapters}
        base = chapter_id
        suffix = 2
        while chapter_id in existing:
            chapter_id = f"{base}-{suffix}"
            suffix += 1

        part_id = self.current_part["part_id"] if self.current_part else None
        path_prefix = [self.current_part["title"], title] if self.current_part else [title]
        path = self.hierarchy.replace_root(path_prefix)

        chapter: Chapter = {
            "chapter_id": chapter_id,
            "title": title,
            "chapter_number": number if number else self.chapter_ordinal,
            "part_id": part_id,
            "order_index": len(self.chapters),
            "source_ref": item.get("source_ref"),
            "heading_path": path,
            "sections": [],
            "blocks": [],
        }
        self.chapters.append(chapter)
        self.current_chapter = chapter
        self.section_ordinal = 0
        self.block_ordinal = 0
        self.chapter_order_index = 0
        # Opening section for chapter body
        self._open_section(title, item, payload_level(item["payload"]) or 1, path)

    def _open_section(
        self,
        title: str,
        item: StreamItem,
        level: int | None,
        path: list[str],
    ) -> None:
        self._close_section()
        if self.current_chapter is None:
            return
        self.section_ordinal += 1
        section_id = make_section_id(self.section_ordinal)
        section: Section = {
            "section_id": section_id,
            "title": title,
            "heading_level": level,
            "heading_path": list(path),
            "order_index": len(self.current_chapter["sections"]),
            "source_ref": item.get("source_ref"),
            "blocks": [],
        }
        self.current_chapter["sections"].append(section)
        self.current_section = section
        # Emit the heading itself as a block inside the section
        self._emit_block(
            block_type="heading",
            text=title,
            source_ref=item.get("source_ref"),
            docling_index=item.get("index"),
            label=item["payload"].get("label"),
            heading_level=level,
            heading_path_override=path,
        )

    def _close_section(self) -> None:
        self.current_section = None

    def _close_chapter(self) -> None:
        self.current_chapter = None
        self.current_section = None

    def _flush_list(self) -> None:
        if not self._pending_list_items:
            return
        items = list(self._pending_list_items)
        self._pending_list_items.clear()
        texts = [i["text"] for i in items if i.get("text")]
        combined = "\n".join(f"• {t}" for t in texts)
        self._emit_block(
            block_type="list",
            text=combined,
            source_ref=items[0].get("source_ref"),
            docling_index=items[0].get("docling_index"),
            label="list",
            extra_meta={
                "list_style": "unknown",
                "items": [
                    {
                        "text": i["text"],
                        "source_ref": i.get("source_ref"),
                        "docling_index": i.get("docling_index"),
                    }
                    for i in items
                ],
            },
        )
        # Also keep individual list_item blocks for lossless item access
        for i in items:
            self._emit_block(
                block_type="list_item",
                text=i["text"],
                source_ref=i.get("source_ref"),
                docling_index=i.get("docling_index"),
                label=i.get("label") or "list_item",
            )

    def _emit_table(self, item: StreamItem) -> None:
        payload = item["payload"]
        headers, rows, plain = _table_as_text(payload)
        caption = _first_caption(payload)
        text = plain
        if caption:
            text = f"{caption}\n{plain}" if plain else caption
        self._emit_block(
            block_type="table",
            text=text or "[table]",
            source_ref=item.get("source_ref"),
            docling_index=item.get("index"),
            label=payload.get("label") or "table",
            extra_meta={
                "table": {
                    "headers": headers,
                    "rows": rows,
                    "caption": caption,
                    "data": payload.get("data"),
                }
            },
        )

    def _emit_picture(self, item: StreamItem) -> None:
        payload = item["payload"]
        caption = _first_caption(payload)
        self._emit_block(
            block_type="figure",
            text=caption or "[figure]",
            source_ref=item.get("source_ref"),
            docling_index=item.get("index"),
            label=payload.get("label") or "picture",
            extra_meta={
                "figure_id": item.get("source_ref"),
                "caption": caption,
                "caption_source_ref": None,
            },
        )

    def _emit_block(
        self,
        *,
        block_type: str,
        text: str,
        source_ref: str | None,
        docling_index: int | None,
        label: Any,
        heading_level: int | None = None,
        heading_path_override: list[str] | None = None,
        extra_meta: dict[str, Any] | None = None,
    ) -> None:
        path = list(heading_path_override or self.hierarchy.path())
        meta: dict[str, Any] = {
            "label": label,
            "heading_level": heading_level,
            "word_count": word_count(text),
            "char_count": char_count(text),
        }
        if extra_meta:
            meta.update(extra_meta)

        if self.current_chapter is None:
            # Front matter
            self.block_ordinal += 1
            block_id = make_front_block_id(self.book_id, self.block_ordinal)
            block: Block = {
                "block_id": block_id,
                "block_type": block_type,
                "text": text,
                "book_id": self.book_id,
                "chapter_id": None,
                "section_id": "sec00",
                "part_id": self.current_part["part_id"] if self.current_part else None,
                "heading_path": path,
                "source_ref": source_ref,
                "docling_index": docling_index,
                "order_index": len(self.front_blocks),
                "book_order_index": self.book_order_index,
                "metadata": meta,
            }
            self.book_order_index += 1
            self.front_blocks.append(block)
            return

        if self.current_section is None:
            # Ensure a default section exists
            self.section_ordinal += 1
            section_id = make_section_id(self.section_ordinal)
            section: Section = {
                "section_id": section_id,
                "title": self.current_chapter["title"],
                "heading_level": 1,
                "heading_path": list(self.current_chapter.get("heading_path") or []),
                "order_index": len(self.current_chapter["sections"]),
                "source_ref": self.current_chapter.get("source_ref"),
                "blocks": [],
            }
            self.current_chapter["sections"].append(section)
            self.current_section = section

        self.block_ordinal += 1
        section_id = self.current_section["section_id"]
        chapter_id = self.current_chapter["chapter_id"]
        block_id = make_block_id(
            self.book_id, chapter_id, section_id, self.block_ordinal
        )
        block = {
            "block_id": block_id,
            "block_type": block_type,
            "text": text,
            "book_id": self.book_id,
            "chapter_id": chapter_id,
            "section_id": section_id,
            "part_id": self.current_chapter.get("part_id"),
            "heading_path": path,
            "source_ref": source_ref,
            "docling_index": docling_index,
            "order_index": self.chapter_order_index,
            "book_order_index": self.book_order_index,
            "metadata": meta,
        }
        self.chapter_order_index += 1
        self.book_order_index += 1
        self.current_section["blocks"].append(block)
        self.current_chapter["blocks"].append(block)


def payload_level(payload: dict[str, Any]) -> int | None:
    level = payload.get("level")
    if isinstance(level, int):
        return level
    return None


def _first_caption(payload: dict[str, Any]) -> str | None:
    captions = payload.get("captions") or []
    for cap in captions:
        if isinstance(cap, dict):
            t = (cap.get("text") or "").strip()
            if t:
                return t
        elif isinstance(cap, str) and cap.strip():
            return cap.strip()
    return None


def _table_as_text(payload: dict[str, Any]) -> tuple[list[str], list[list[str]], str]:
    data = payload.get("data") or {}
    grid = data.get("grid") or []
    headers: list[str] = []
    rows: list[list[str]] = []
    if grid:
        for r_idx, row in enumerate(grid):
            cells = []
            for cell in row or []:
                if isinstance(cell, dict):
                    cells.append(str(cell.get("text") or ""))
                else:
                    cells.append(str(cell or ""))
            if r_idx == 0 and any(
                isinstance(c, dict) and c.get("column_header") for c in (row or [])
            ):
                headers = cells
            else:
                rows.append(cells)
    else:
        # Fallback from table_cells
        cells = data.get("table_cells") or []
        for cell in cells:
            if isinstance(cell, dict) and cell.get("column_header"):
                headers.append(str(cell.get("text") or ""))
    lines: list[str] = []
    if headers:
        lines.append(" | ".join(headers))
    for row in rows:
        lines.append(" | ".join(row))
    return headers, rows, "\n".join(lines)
