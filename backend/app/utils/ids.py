"""Shared helpers."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_book_id(title_hint: str | None = None) -> str:
    slug = "book"
    if title_hint:
        cleaned = re.sub(r"[^a-z0-9]+", "-", title_hint.lower()).strip("-")
        if cleaned:
            slug = cleaned[:48]
    return f"{slug}-{uuid.uuid4().hex[:8]}"


def slugify(value: str, fallback: str = "item") -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned[:64] or fallback
