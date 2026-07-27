"""Pass 1b: merge per-chunk Argument Discovery reports."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import Settings
from app.pipelines.discovery import slim_blocks
from app.pipelines.discovery_validate import (
    strip_invalid_discovery_refs,
    validate_discovery,
)
from app.prompts.loader import load_prompt
from app.services.llm import LLMClient, LLMError
from app.utils.ids import utc_now_iso

logger = logging.getLogger(__name__)


def merge_system_prompt(prompt_markdown: str) -> str:
    return (
        "Follow the Argument Discovery merge instructions below.\n"
        "Return JSON only.\n\n"
        f"{prompt_markdown}"
    )


def merge_user_prompt(
    *,
    book: dict[str, Any],
    chapter: dict[str, Any],
    blocks: list[dict[str, Any]],
    chunk_discoveries: list[dict[str, Any]],
) -> str:
    slim = slim_blocks(blocks)
    payload = {
        "book_id": book["book_id"],
        "book_title": book.get("title"),
        "chapter_id": chapter["chapter_id"],
        "chapter_title": chapter.get("title"),
        "allow_listed_block_ids": [b["block_id"] for b in slim],
        "blocks": slim,
        "chunk_discoveries": chunk_discoveries,
    }
    return (
        "Merge the chunk Argument Discovery reports into one chapter discovery.\n"
        "Use only allow-listed block IDs.\n\n"
        "===CHUNK_DISCOVERIES_JSON===\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


def run_discovery_merge(
    llm: LLMClient,
    *,
    settings: Settings,
    book: dict[str, Any],
    chapter: dict[str, Any],
    blocks: list[dict[str, Any]],
    chunk_discoveries: list[dict[str, Any]],
) -> dict[str, Any]:
    if not chunk_discoveries:
        raise LLMError("No chunk discoveries to merge.")
    if len(chunk_discoveries) == 1:
        return chunk_discoveries[0]

    prompt_text, prompt_hash = load_prompt("argument_discovery_merge.md")
    system = merge_system_prompt(prompt_text)
    user = merge_user_prompt(
        book=book,
        chapter=chapter,
        blocks=blocks,
        chunk_discoveries=chunk_discoveries,
    )
    logger.info(
        "Discovery merge chapter=%s chunks=%s",
        chapter.get("chapter_id"),
        len(chunk_discoveries),
    )
    raw = llm.complete_json(
        system=system,
        user=user,
        temperature=float(settings.llm_pass_temperature),
        pass_name="discovery_merge",
    )
    discovery = dict(raw)
    discovery["schema_version"] = "1.0"
    discovery["book_id"] = book["book_id"]
    discovery["chapter_id"] = chapter["chapter_id"]
    discovery.setdefault("chapter_types", ["mixed"])
    discovery.setdefault("argument_movements", [])
    discovery.setdefault("claims", [])
    discovery.setdefault("supporting_material", [])
    discovery.setdefault("recommended_node_types", [])
    discovery.setdefault("omit_or_deemphasize", [])
    discovery.setdefault("conflicts", [])
    allowed = {b["block_id"] for b in slim_blocks(blocks)}
    discovery = strip_invalid_discovery_refs(discovery, allowed)
    errors = validate_discovery(discovery, allowed)
    now = utc_now_iso()
    versions = dict((discovery.get("processing") or {}).get("prompt_versions") or {})
    versions["argument_discovery_merge"] = f"1.0.0:{prompt_hash}"
    discovery["processing"] = {
        "model": settings.llm_model if not settings.llm_mock else "mock",
        "prompt_versions": versions,
        "pass_name": "discovery_merge",
        "created_at": now,
    }
    if errors:
        notes = (discovery.get("confidence_summary") or {}).get("notes") or ""
        discovery["confidence_summary"] = {
            "overall": (discovery.get("confidence_summary") or {}).get("overall"),
            "notes": (notes + " | merge_warnings: " + "; ".join(errors[:8])).strip(" |"),
        }
        hard = [e for e in errors if e.startswith("unknown source_block_id")]
        if hard:
            raise LLMError("Merged discovery invented block IDs: " + "; ".join(hard[:5]))
    return discovery
