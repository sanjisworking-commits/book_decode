"""Pass 2: Adaptive Argument Spine synthesis from discovery + source blocks."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import Settings
from app.domain.spine_types import (
    normalise_node_type,
    normalise_source_status,
)
from app.pipelines.chunk import estimate_request_tokens
from app.pipelines.discovery import slim_blocks
from app.pipelines.validate_spine import (
    strip_invalid_relations,
    strip_invalid_source_refs,
    validate_relations,
    validate_source_refs,
    validate_spine_schema,
)
from app.prompts.loader import load_prompt
from app.services.llm import LLMClient, LLMError
from app.utils.ids import utc_now_iso

logger = logging.getLogger(__name__)


def synthesis_system_prompt(prompt_markdown: str) -> str:
    return (
        "Follow the Adaptive Argument Spine synthesis instructions below.\n"
        "Return JSON only.\n\n"
        f"{prompt_markdown}"
    )


def synthesis_user_prompt(
    *,
    book: dict[str, Any],
    chapter: dict[str, Any],
    blocks: list[dict[str, Any]],
    discovery: dict[str, Any],
) -> str:
    slim = slim_blocks(blocks)
    meta = {
        "book_id": book["book_id"],
        "book_title": book.get("title"),
        "chapter_id": chapter["chapter_id"],
        "chapter_title": chapter.get("title"),
        "allow_listed_block_ids": [b["block_id"] for b in slim],
        "blocks": slim,
    }
    return (
        "Synthesise the final English Argument Spine from discovery + source blocks.\n"
        "Use only allow-listed block IDs. Set hinglish fields to null.\n\n"
        "===SYNTHESIS_SOURCE_BLOCKS_JSON===\n"
        f"{json.dumps(meta, ensure_ascii=False)}\n\n"
        "===ARGUMENT_DISCOVERY_JSON===\n"
        f"{json.dumps(discovery, ensure_ascii=False)}"
    )


def fit_blocks_to_synthesis_budget(
    *,
    settings: Settings,
    system: str,
    book: dict[str, Any],
    chapter: dict[str, Any],
    blocks: list[dict[str, Any]],
    discovery: dict[str, Any],
    prompt_budget: int,
) -> tuple[list[dict[str, Any]], str, int]:
    if not blocks:
        raise RuntimeError("No blocks available for synthesis prompt.")
    conservative = settings.is_groq()
    slim = slim_blocks(blocks)
    if not slim:
        raise RuntimeError("No blocks with block_id for synthesis prompt.")

    def build(n: int) -> tuple[list[dict[str, Any]], str, int]:
        chosen = slim[: max(1, n)]
        user = synthesis_user_prompt(
            book=book, chapter=chapter, blocks=chosen, discovery=discovery
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


def rebuild_source_block_references(
    spine: dict[str, Any], allowed: set[str]
) -> dict[str, Any]:
    """Deterministic index node listing cited blocks."""
    cited: list[str] = []
    seen: set[str] = set()
    for node in spine.get("nodes") or []:
        if node.get("node_type") == "source_block_references":
            continue
        for bid in node.get("source_block_ids") or []:
            if bid in allowed and bid not in seen:
                seen.add(bid)
                cited.append(bid)
    for rel in spine.get("relations") or []:
        for bid in rel.get("source_block_ids") or []:
            if bid in allowed and bid not in seen:
                seen.add(bid)
                cited.append(bid)

    nodes = [
        n for n in (spine.get("nodes") or []) if n.get("node_type") != "source_block_references"
    ]
    order = len(nodes)
    chapter_id = spine.get("chapter_id") or "ch"
    nodes.append(
        {
            "id": f"{chapter_id}-src-index",
            "node_type": "source_block_references",
            "statement_en": "Cited source blocks for this decode.",
            "explanation_en": None,
            "statement_hinglish": None,
            "explanation_hinglish": None,
            "source_status": "ai_inference",
            "source_block_ids": cited,
            "confidence": 1.0,
            "order": order,
            "warnings": [],
        }
    )
    spine["nodes"] = nodes
    return spine


def normalise_adaptive_spine(
    raw: dict[str, Any],
    *,
    book_id: str,
    chapter_id: str,
    allowed: set[str],
    model: str,
    prompt_hash: str,
    discovery_prompt_hash: str | None = None,
) -> dict[str, Any]:
    """Program-owned IDs, order, prev/next, aliases, timestamps, relation cleanup."""
    spine = dict(raw)
    spine["schema_version"] = "2.0"
    spine["book_id"] = book_id
    spine["chapter_id"] = chapter_id
    spine["language_modes"] = ["en"]
    spine.setdefault("nodes", [])
    spine.setdefault("relations", [])

    id_map: dict[str, str] = {}
    normalised_nodes: list[dict[str, Any]] = []
    for i, node in enumerate(spine["nodes"]):
        if not isinstance(node, dict):
            continue
        old_id = str(node.get("id") or f"tmp-n{i+1:02d}")
        new_id = f"{chapter_id}-n{i+1:02d}"
        id_map[old_id] = new_id
        nt = normalise_node_type(node.get("node_type")) or "organising_idea"
        node_out = {
            **node,
            "id": new_id,
            "node_type": nt,
            "order": i,
            "source_status": normalise_source_status(node.get("source_status")),
            "statement_hinglish": None,
            "explanation_hinglish": None,
            "warnings": list(node.get("warnings") or []),
        }
        node_out.setdefault("statement_en", None)
        node_out.setdefault("explanation_en", None)
        node_out.setdefault("source_block_ids", [])
        # Remap support pointers when present
        supports = []
        for sid in node.get("supports_node_ids") or []:
            supports.append(id_map.get(str(sid), str(sid)))
        if supports:
            node_out["supports_node_ids"] = supports
        normalised_nodes.append(node_out)

    # Second pass: remap supports that pointed forward before id_map was complete
    for node in normalised_nodes:
        if node.get("supports_node_ids"):
            node["supports_node_ids"] = [
                id_map.get(str(sid), str(sid)) for sid in node["supports_node_ids"]
            ]

    for i, node in enumerate(normalised_nodes):
        node["prev_id"] = normalised_nodes[i - 1]["id"] if i > 0 else None
        node["next_id"] = (
            normalised_nodes[i + 1]["id"] if i + 1 < len(normalised_nodes) else None
        )

    spine["nodes"] = normalised_nodes

    remapped_relations: list[dict[str, Any]] = []
    for rel in spine.get("relations") or []:
        if not isinstance(rel, dict):
            continue
        frm = id_map.get(str(rel.get("from_node_id") or ""), str(rel.get("from_node_id") or ""))
        to = id_map.get(str(rel.get("to_node_id") or ""), str(rel.get("to_node_id") or ""))
        remapped_relations.append(
            {
                **rel,
                "from_node_id": frm,
                "to_node_id": to,
                "source_block_ids": list(rel.get("source_block_ids") or []),
            }
        )
    spine["relations"] = remapped_relations

    spine = strip_invalid_source_refs(spine, allowed)
    spine = strip_invalid_relations(spine, allowed)
    spine = rebuild_source_block_references(spine, allowed)

    # Re-link prev/next after index node append
    nodes = spine["nodes"]
    for i, node in enumerate(nodes):
        node["order"] = i
        node["prev_id"] = nodes[i - 1]["id"] if i > 0 else None
        node["next_id"] = nodes[i + 1]["id"] if i + 1 < len(nodes) else None

    schema_errors = validate_spine_schema(spine)
    ref_errors = validate_source_refs(spine, allowed)
    rel_errors = validate_relations(spine, allowed)

    now = utc_now_iso()
    versions: dict[str, str] = {
        "argument_spine_adaptive_synthesis": f"4.0.0:{prompt_hash}",
    }
    if discovery_prompt_hash:
        versions["argument_discovery"] = f"1.0.0:{discovery_prompt_hash}"
    spine["processing"] = {
        "model": model,
        "prompt_versions": versions,
        "created_at": now,
        "updated_at": now,
    }
    spine["validation"] = {
        "schema_valid": len(schema_errors) == 0,
        "source_refs_valid": len(ref_errors) == 0,
        "relations_valid": len(rel_errors) == 0,
        "bilingual_aligned": False,
        "checked_at": now,
        "mode": None,
    }
    if schema_errors:
        if not spine.get("nodes"):
            raise LLMError(
                "Adaptive synthesis produced no nodes: " + "; ".join(schema_errors[:5])
            )
        notes = (spine.get("confidence_summary") or {}).get("notes") or ""
        spine["confidence_summary"] = {
            "overall": (spine.get("confidence_summary") or {}).get("overall"),
            "notes": (notes + " | schema_warnings: " + "; ".join(schema_errors[:5])).strip(
                " |"
            ),
        }
    if ref_errors:
        raise LLMError(
            "Invalid source refs after adaptive repair: " + "; ".join(ref_errors[:5])
        )
    return spine


def run_adaptive_synthesis(
    llm: LLMClient,
    *,
    settings: Settings,
    book: dict[str, Any],
    chapter: dict[str, Any],
    blocks: list[dict[str, Any]],
    discovery: dict[str, Any],
    discovery_prompt_hash: str | None = None,
) -> dict[str, Any]:
    prompt_text, prompt_hash = load_prompt("argument_spine_adaptive_synthesis.md")
    system = synthesis_system_prompt(prompt_text)
    prompt_budget = settings.extract_prompt_token_budget()
    fitted, user, tokens = fit_blocks_to_synthesis_budget(
        settings=settings,
        system=system,
        book=book,
        chapter=chapter,
        blocks=blocks,
        discovery=discovery,
        prompt_budget=prompt_budget,
    )
    logger.info(
        "Adaptive synthesis chapter=%s blocks=%s/%s tokens_est=%s budget=%s",
        chapter.get("chapter_id"),
        len(fitted),
        len(blocks),
        tokens,
        prompt_budget,
    )
    raw = llm.complete_json(
        system=system,
        user=user,
        temperature=float(settings.llm_pass_temperature),
        pass_name="adaptive_synthesis",
    )
    return normalise_adaptive_spine(
        raw,
        book_id=book["book_id"],
        chapter_id=chapter["chapter_id"],
        allowed={b["block_id"] for b in fitted},
        model=settings.llm_model if not settings.llm_mock else "mock",
        prompt_hash=prompt_hash,
        discovery_prompt_hash=discovery_prompt_hash,
    )
