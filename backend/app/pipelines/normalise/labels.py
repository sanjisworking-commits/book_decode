"""Label mapping and conservative noise filtering."""

from __future__ import annotations

import re

_NOISE_EXACT = {
    "",
    ".",
    "•",
    "·",
    "image",
    "cover",
}

_LABEL_TO_BLOCK_TYPE: dict[str, str] = {
    "title": "heading",
    "section_header": "heading",
    "heading": "heading",
    "list_item": "list_item",
    "text": "paragraph",
    "paragraph": "paragraph",
    "caption": "note",
    "footnote": "note",
    "endnote": "note",
    "quote": "quote",
    "table": "table",
    "picture": "figure",
    "image": "image",
    "figure": "figure",
    "code": "code",
    "formula": "equation",
    "equation": "equation",
    "checkbox": "other",
    "page_header": "other",
    "page_footer": "other",
}

_PART_RE = re.compile(r"^\s*part\s+([0-9]+|[ivxlcdm]+)\b", re.IGNORECASE)
_CHAPTER_RE = re.compile(
    r"^\s*(chapter|chap\.?|ch\.?)\s+([0-9]+|[ivxlcdm]+)\b",
    re.IGNORECASE,
)


def map_block_type(label: str | None) -> str:
    if not label:
        return "other"
    return _LABEL_TO_BLOCK_TYPE.get(label.lower(), "other")


def is_noise_text(text: str) -> bool:
    cleaned = text.strip()
    if cleaned.lower() in _NOISE_EXACT:
        return True
    if len(cleaned) <= 1:
        return True
    return False


def is_heading_label(label: str | None) -> bool:
    return (label or "").lower() in {"title", "section_header", "heading"}


def is_part_heading(text: str) -> bool:
    return bool(_PART_RE.match(text.strip()))


def is_chapter_heading(text: str) -> bool:
    return bool(_CHAPTER_RE.match(text.strip()))


def extract_chapter_number(text: str) -> int | None:
    match = _CHAPTER_RE.match(text.strip())
    if not match:
        return None
    raw = match.group(2)
    if raw.isdigit():
        return int(raw)
    return None


def word_count(text: str) -> int:
    return len([w for w in text.split() if w])


def char_count(text: str) -> int:
    return len(text)
