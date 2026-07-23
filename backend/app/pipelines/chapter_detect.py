"""Chapter detection from Docling (or Docling-like) structured JSON."""

from __future__ import annotations

import re
from typing import Any

from app.utils.ids import slugify

_CHAPTER_TITLE_RE = re.compile(
    r"^\s*(chapter|chap\.?|ch\.?)\s+([0-9]+|[ivxlcdm]+)\b",
    re.IGNORECASE,
)
_PART_RE = re.compile(r"^\s*part\s+([0-9]+|[ivxlcdm]+)\b", re.IGNORECASE)
_SKIP_TITLES = {
    "contents",
    "table of contents",
    "toc",
    "copyright",
    "title page",
    "cover",
    "dedication",
    "acknowledgments",
    "acknowledgements",
    "index",
    "about the author",
}


def _is_heading_label(label: str | None) -> bool:
    return (label or "").lower() in {"title", "section_header", "heading"}


def _looks_like_chapter_heading(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned or len(cleaned) > 200:
        return False
    lower = cleaned.lower()
    if lower in _SKIP_TITLES:
        return False
    if _CHAPTER_TITLE_RE.match(cleaned):
        return True
    # Short title-like headings after TOC often mark chapters
    if len(cleaned.split()) <= 12 and not cleaned.endswith("."):
        return True
    return False


def _extract_chapter_number(text: str, fallback: int) -> int | None:
    match = _CHAPTER_TITLE_RE.match(text.strip())
    if not match:
        return fallback
    raw = match.group(2)
    if raw.isdigit():
        return int(raw)
    return fallback


def detect_chapters_from_docling(docling_json: dict[str, Any]) -> list[dict[str, Any]]:
    """Split Docling `texts` into preliminary chapters.

    Phase 1 output is a chapter preview list (ids, titles, text snippets).
    Stable source-block IDs are assigned in Phase 2.
    """
    texts = docling_json.get("texts") or []
    if not isinstance(texts, list) or not texts:
        return []

    # Prefer splitting on title / section_header that look like chapter starts.
    headings: list[tuple[int, str]] = []
    for idx, item in enumerate(texts):
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        text = (item.get("text") or "").strip()
        if not text:
            continue
        if _is_heading_label(label) and _looks_like_chapter_heading(text):
            # Skip pure "Part N" markers as chapter bodies; still allow as headings
            if _PART_RE.match(text) and not _CHAPTER_TITLE_RE.match(text):
                continue
            headings.append((idx, text))

    chapters: list[dict[str, Any]] = []

    if len(headings) >= 2:
        for order, (start_idx, title) in enumerate(headings, start=1):
            end_idx = headings[order][0] if order < len(headings) else len(texts)
            body_parts: list[str] = []
            for item in texts[start_idx + 1 : end_idx]:
                if not isinstance(item, dict):
                    continue
                if _is_heading_label(item.get("label")):
                    # Keep nested headings in preview text
                    pass
                t = (item.get("text") or "").strip()
                if t:
                    body_parts.append(t)
            preview_text = "\n\n".join(body_parts)
            # Drop empty TOC-like chapters with almost no body
            if len(preview_text) < 40 and title.strip().lower() in _SKIP_TITLES:
                continue
            chapter_number = _extract_chapter_number(title, order)
            chapter_id = f"ch{chapter_number:02d}" if chapter_number else f"ch{order:02d}"
            # Ensure uniqueness
            existing = {c["chapter_id"] for c in chapters}
            base = chapter_id
            suffix = 2
            while chapter_id in existing:
                chapter_id = f"{base}-{suffix}"
                suffix += 1
            chapters.append(
                {
                    "chapter_id": chapter_id,
                    "title": title,
                    "chapter_number": chapter_number,
                    "order_index": len(chapters),
                    "status": "pending",
                    "retry_count": 0,
                    "error": None,
                    "preview": {
                        "text_char_count": len(preview_text),
                        "excerpt": preview_text[:400],
                        "source_text_start_index": start_idx,
                        "source_text_end_index": end_idx,
                    },
                }
            )
    else:
        # Fallback: one chapter for the whole document body
        body_parts = [
            (item.get("text") or "").strip()
            for item in texts
            if isinstance(item, dict) and (item.get("text") or "").strip()
        ]
        preview_text = "\n\n".join(body_parts)
        title = docling_json.get("name") or "Full text"
        chapters.append(
            {
                "chapter_id": "ch01",
                "title": str(title),
                "chapter_number": 1,
                "order_index": 0,
                "status": "pending",
                "retry_count": 0,
                "error": None,
                "preview": {
                    "text_char_count": len(preview_text),
                    "excerpt": preview_text[:400],
                    "source_text_start_index": 0,
                    "source_text_end_index": len(texts),
                },
            }
        )

    # Prefer chapters that look like real chapters (have body text)
    substantive = [c for c in chapters if (c.get("preview") or {}).get("text_char_count", 0) >= 20]
    return substantive or chapters


def detect_chapters_from_reference_clean_json(clean_json: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect chapters from the sample-data reference shape (sections[]).

    Used in tests / offline fixtures. Not a substitute for Docling on real uploads.
    """
    sections = clean_json.get("sections") or []
    chapters: list[dict[str, Any]] = []
    order = 0
    i = 0
    while i < len(sections):
        section = sections[i]
        title = (section.get("title") or "").strip()
        if _CHAPTER_TITLE_RE.match(title):
            # Often "CHAPTER N" followed by a title section
            chapter_number = _extract_chapter_number(title, order + 1)
            display_title = title
            body_paras: list[str] = [
                p.get("text", "") for p in (section.get("paragraphs") or []) if p.get("text")
            ]
            j = i + 1
            if j < len(sections):
                nxt = sections[j]
                nxt_title = (nxt.get("title") or "").strip()
                if nxt_title and not _CHAPTER_TITLE_RE.match(nxt_title) and not _PART_RE.match(nxt_title):
                    display_title = f"{title}: {nxt_title}" if title else nxt_title
                    body_paras.extend(
                        p.get("text", "") for p in (nxt.get("paragraphs") or []) if p.get("text")
                    )
                    j += 1
            # Accumulate following non-chapter sections until next CHAPTER heading
            while j < len(sections):
                nxt = sections[j]
                nxt_title = (nxt.get("title") or "").strip()
                if _CHAPTER_TITLE_RE.match(nxt_title):
                    break
                if _PART_RE.match(nxt_title):
                    break
                body_paras.extend(
                    p.get("text", "") for p in (nxt.get("paragraphs") or []) if p.get("text")
                )
                j += 1
            preview_text = "\n\n".join(t for t in body_paras if t)
            order += 1
            chapters.append(
                {
                    "chapter_id": f"ch{chapter_number:02d}",
                    "title": display_title,
                    "chapter_number": chapter_number,
                    "order_index": order - 1,
                    "status": "pending",
                    "retry_count": 0,
                    "error": None,
                    "preview": {
                        "text_char_count": len(preview_text),
                        "excerpt": preview_text[:400],
                    },
                }
            )
            i = j
            continue
        i += 1

    if not chapters and sections:
        # Fallback: each level-1 section with paragraphs
        for idx, section in enumerate(sections, start=1):
            paras = [p.get("text", "") for p in (section.get("paragraphs") or []) if p.get("text")]
            if not paras:
                continue
            title = section.get("title") or f"Section {idx}"
            preview_text = "\n\n".join(paras)
            chapters.append(
                {
                    "chapter_id": f"ch{idx:02d}-{slugify(title)[:20]}",
                    "title": title,
                    "chapter_number": idx,
                    "order_index": len(chapters),
                    "status": "pending",
                    "retry_count": 0,
                    "error": None,
                    "preview": {
                        "text_char_count": len(preview_text),
                        "excerpt": preview_text[:400],
                    },
                }
            )
    return chapters
