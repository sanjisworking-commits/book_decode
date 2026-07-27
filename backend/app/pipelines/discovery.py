"""Pass 1: Argument Discovery (whole chapter or per-chunk)."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import Settings
from app.pipelines.chunk import estimate_request_tokens
from app.pipelines.discovery_validate import (
    strip_invalid_discovery_refs,
    validate_discovery,
)
from app.prompts.loader import load_prompt
from app.services.llm import LLMClient, LLMError
from app.utils.ids import utc_now_iso

logger = logging.getLogger(__name__)


def slim_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "block_id": b["block_id"],
            "block_type": b.get("block_type"),
            "text": b.get("text"),
        }
        for b in blocks
        if b.get("block_id")
    ]


def discovery_system_prompt(prompt_markdown: str) -> str:
    return (
        "Follow the Argument Discovery instructions below.\n"
        "Return JSON only.\n\n"
        f"{prompt_markdown}"
    )


def discovery_user_prompt(
    *,
    book: dict[str, Any],
    chapter: dict[str, Any],
    blocks: list[dict[str, Any]],
    chunk_id: str | None = None,
) -> str:
    slim = slim_blocks(blocks)
    payload = {
        "book_id": book["book_id"],
        "book_title": book.get("title"),
        "chapter_id": chapter["chapter_id"],
        "chapter_title": chapter.get("title"),
        "chunk_id": chunk_id,
        "allow_listed_block_ids": [b["block_id"] for b in slim],
        "blocks": slim,
    }
    return (
        "Discover the argument structure for this chapter material.\n"
        "Use only the allow-listed block IDs.\n\n"
        "===DISCOVERY_SOURCE_BLOCKS_JSON===\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


def estimate_discovery_tokens(
    *,
    system: str,
    book: dict[str, Any],
    chapter: dict[str, Any],
    blocks: list[dict[str, Any]],
    chunk_id: str | None = None,
    conservative: bool = False,
) -> int:
    user = discovery_user_prompt(
        book=book, chapter=chapter, blocks=blocks, chunk_id=chunk_id
    )
    return estimate_request_tokens(system, conservative=conservative) + estimate_request_tokens(
        user, conservative=conservative
    )


def fit_blocks_to_discovery_budget(
    *,
    settings: Settings,
    system: str,
    book: dict[str, Any],
    chapter: dict[str, Any],
    blocks: list[dict[str, Any]],
    prompt_budget: int,
    chunk_id: str | None = None,
) -> tuple[list[dict[str, Any]], str, int]:
    """Pack a prefix of blocks so discovery system+user stay under budget."""
    if not blocks:
        raise RuntimeError("No blocks available for discovery prompt.")
    conservative = settings.is_groq()
    slim = slim_blocks(blocks)
    if not slim:
        raise RuntimeError("No blocks with block_id for discovery prompt.")

    def build(n: int) -> tuple[list[dict[str, Any]], str, int]:
        chosen = slim[: max(1, n)]
        user = discovery_user_prompt(
            book=book, chapter=chapter, blocks=chosen, chunk_id=chunk_id
        )
        tokens = estimate_request_tokens(
            system, conservative=conservative
        ) + estimate_request_tokens(user, conservative=conservative)
        return chosen, user, tokens

    lo, hi = 1, len(slim)
    best_n = 1
    while lo <= hi:
        mid = (lo + hi) // 2
        _, _, tokens = build(mid)
        if tokens <= prompt_budget:
            best_n = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return build(best_n)


def postprocess_discovery(
    raw: dict[str, Any],
    *,
    book_id: str,
    chapter_id: str,
    allowed: set[str],
    model: str,
    prompt_hash: str,
) -> dict[str, Any]:
    discovery = dict(raw)
    discovery["schema_version"] = "1.0"
    discovery["book_id"] = book_id
    discovery["chapter_id"] = chapter_id
    discovery.setdefault("chapter_types", ["mixed"])
    discovery.setdefault("argument_movements", [])
    discovery.setdefault("claims", [])
    discovery.setdefault("supporting_material", [])
    discovery.setdefault("recommended_node_types", [])
    discovery.setdefault("omit_or_deemphasize", [])
    discovery.setdefault("conflicts", [])
    discovery = strip_invalid_discovery_refs(discovery, allowed)
    errors = validate_discovery(discovery, allowed)
    now = utc_now_iso()
    discovery["processing"] = {
        "model": model,
        "prompt_versions": {"argument_discovery": f"1.0.0:{prompt_hash}"},
        "pass_name": "discovery",
        "created_at": now,
    }
    if errors:
        notes = (discovery.get("confidence_summary") or {}).get("notes") or ""
        discovery["confidence_summary"] = {
            "overall": (discovery.get("confidence_summary") or {}).get("overall"),
            "notes": (notes + " | discovery_warnings: " + "; ".join(errors[:8])).strip(
                " |"
            ),
        }
        # Fail hard on invented block IDs that survived strip (should be empty)
        hard = [e for e in errors if e.startswith("unknown source_block_id")]
        if hard:
            raise LLMError("Discovery invented block IDs: " + "; ".join(hard[:5]))
    return discovery


def run_discovery_call(
    llm: LLMClient,
    *,
    settings: Settings,
    book: dict[str, Any],
    chapter: dict[str, Any],
    blocks: list[dict[str, Any]],
    chunk_id: str | None = None,
) -> dict[str, Any]:
    prompt_text, prompt_hash = load_prompt("argument_discovery.md")
    system = discovery_system_prompt(prompt_text)
    prompt_budget = settings.extract_prompt_token_budget()
    fitted, user, tokens = fit_blocks_to_discovery_budget(
        settings=settings,
        system=system,
        book=book,
        chapter=chapter,
        blocks=blocks,
        prompt_budget=prompt_budget,
        chunk_id=chunk_id,
    )
    logger.info(
        "Discovery call chapter=%s chunk=%s blocks=%s/%s tokens_est=%s budget=%s",
        chapter.get("chapter_id"),
        chunk_id,
        len(fitted),
        len(blocks),
        tokens,
        prompt_budget,
    )
    raw = llm.complete_json(
        system=system,
        user=user,
        temperature=float(settings.llm_pass_temperature),
        pass_name="discovery",
    )
    return postprocess_discovery(
        raw,
        book_id=book["book_id"],
        chapter_id=chapter["chapter_id"],
        allowed={b["block_id"] for b in fitted},
        model=settings.llm_model if not settings.llm_mock else "mock",
        prompt_hash=prompt_hash,
    )


def chapter_fits_discovery_budget(
    *,
    settings: Settings,
    book: dict[str, Any],
    chapter: dict[str, Any],
    blocks: list[dict[str, Any]],
) -> bool:
    prompt_text, _ = load_prompt("argument_discovery.md")
    system = discovery_system_prompt(prompt_text)
    budget = settings.extract_prompt_token_budget()
    tokens = estimate_discovery_tokens(
        system=system,
        book=book,
        chapter=chapter,
        blocks=blocks,
        conservative=settings.is_groq(),
    )
    return tokens <= budget
