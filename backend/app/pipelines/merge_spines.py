"""Deterministic merge helpers for partial Argument Spines (Phase 4)."""

from __future__ import annotations

import re
from typing import Any

NODE_TYPE_ORDER: list[str] = [
    "chapter_question",
    "central_claim",
    "reasoning_steps",
    "evidence_and_examples",
    "hidden_assumptions",
    "tensions_or_gaps",
    "strongest_counter_position",
    "consequence_if_correct",
    "role_in_book",
    "one_sentence_decode",
    "confidence_and_unresolved",
    "source_block_references",
]

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)


def normalise_statement(text: str | None) -> str:
    if not text:
        return ""
    cleaned = _PUNCT_RE.sub(" ", text.lower())
    return _WS_RE.sub(" ", cleaned).strip()


def statements_equivalent(a: str | None, b: str | None) -> bool:
    na, nb = normalise_statement(a), normalise_statement(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # Near-duplicate: one contains the other and lengths are close
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    if shorter in longer and len(shorter) >= 24:
        return (len(longer) - len(shorter)) / max(len(longer), 1) <= 0.35
    return False


def collect_claim_statements(partials: list[dict[str, Any]]) -> set[str]:
    """Normalised statement set from partials (for 'no new claims' checks)."""
    out: set[str] = set()
    for partial in partials:
        for node in partial.get("nodes") or []:
            norm = normalise_statement(node.get("statement_en"))
            if norm:
                out.add(norm)
    return out


def claim_supported_by_partials(statement: str | None, partial_claims: set[str]) -> bool:
    norm = normalise_statement(statement)
    if not norm:
        return True
    if norm in partial_claims:
        return True
    for claim in partial_claims:
        if statements_equivalent(norm, claim):
            return True
        # Allow mild synthesis stitching: statement is concatenation/subset of known claims
        if norm in claim or claim in norm:
            return True
    return False


def merge_partial_spines(
    *,
    book_id: str,
    chapter_id: str,
    partials: list[dict[str, Any]],
    allowed_block_ids: set[str],
) -> dict[str, Any]:
    """Merge partial spines without inventing claims (deterministic, testable).

    Used by MockLLM synthesis and as a non-LLM fallback. Keeps one primary node
    per node_type, dedupes near-identical statements, unions source refs, and
    records competing interpretations in warnings.
    """
    by_type: dict[str, list[dict[str, Any]]] = {t: [] for t in NODE_TYPE_ORDER}
    extras: list[dict[str, Any]] = []

    for partial in partials:
        for node in partial.get("nodes") or []:
            ntype = node.get("node_type")
            if ntype in by_type:
                by_type[ntype].append(node)
            else:
                extras.append(node)

    merged_nodes: list[dict[str, Any]] = []
    for ntype in NODE_TYPE_ORDER:
        candidates = by_type.get(ntype) or []
        if not candidates:
            continue
        primary, warnings = _select_primary(candidates)
        source_ids = _union_source_ids(candidates, allowed_block_ids)
        # Prefer primary's citations first, then union
        primary_ids = [
            b for b in (primary.get("source_block_ids") or []) if b in allowed_block_ids
        ]
        ordered_ids: list[str] = []
        for bid in primary_ids + source_ids:
            if bid not in ordered_ids:
                ordered_ids.append(bid)

        node_warnings = list(primary.get("warnings") or [])
        node_warnings.extend(warnings)
        if "synthesised" not in node_warnings:
            node_warnings.append("synthesised")

        merged_nodes.append(
            {
                "id": f"{chapter_id}-n{len(merged_nodes)+1:02d}",
                "node_type": ntype,
                "statement_en": primary.get("statement_en"),
                "explanation_en": primary.get("explanation_en"),
                "statement_hinglish": None,
                "explanation_hinglish": None,
                "source_status": primary.get("source_status") or "ai_inference",
                "source_block_ids": ordered_ids,
                "confidence": primary.get("confidence"),
                "order": len(merged_nodes),
                "prev_id": None,
                "next_id": None,
                "warnings": node_warnings,
            }
        )

    for i, node in enumerate(merged_nodes):
        node["order"] = i
        node["prev_id"] = merged_nodes[i - 1]["id"] if i else None
        node["next_id"] = merged_nodes[i + 1]["id"] if i + 1 < len(merged_nodes) else None

    overall = None
    confidences = [
        n.get("confidence")
        for n in merged_nodes
        if isinstance(n.get("confidence"), (int, float))
    ]
    if confidences:
        overall = sum(confidences) / len(confidences)

    return {
        "schema_version": "1.0",
        "book_id": book_id,
        "chapter_id": chapter_id,
        "language_modes": ["en"],
        "nodes": merged_nodes,
        "confidence_summary": {
            "overall": overall,
            "notes": f"Synthesised from {len(partials)} partial spine(s).",
        },
    }


def _select_primary(
    candidates: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    """Pick primary node; note competing distinct interpretations."""
    unique: list[dict[str, Any]] = []
    for cand in candidates:
        if any(
            statements_equivalent(cand.get("statement_en"), u.get("statement_en"))
            for u in unique
        ):
            continue
        unique.append(cand)

    if not unique:
        return candidates[0], []

    def score(node: dict[str, Any]) -> tuple[int, float, int]:
        refs = len(node.get("source_block_ids") or [])
        conf = float(node.get("confidence") or 0.0)
        length = len(node.get("statement_en") or "")
        return (refs, conf, length)

    unique_sorted = sorted(unique, key=score, reverse=True)
    primary = unique_sorted[0]
    warnings: list[str] = []
    for rival in unique_sorted[1:]:
        stmt = (rival.get("statement_en") or "").strip()
        if stmt:
            snippet = stmt if len(stmt) <= 160 else stmt[:157] + "..."
            warnings.append(f"competing_interpretation: {snippet}")
    return primary, warnings


def _union_source_ids(
    candidates: list[dict[str, Any]], allowed: set[str]
) -> list[str]:
    out: list[str] = []
    for node in candidates:
        for bid in node.get("source_block_ids") or []:
            if bid in allowed and bid not in out:
                out.append(bid)
    return out
