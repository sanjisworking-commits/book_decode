"""Argument Spine schema and source-reference validation."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from app.domain.spine_types import RELATION_TYPES, normalise_source_status

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "schemas" / "argument_spine.schema.json"


def load_argument_spine_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_spine_schema(spine: dict[str, Any]) -> list[str]:
    schema = load_argument_spine_schema()
    validator = Draft202012Validator(schema)
    return sorted(
        f"{'.'.join(str(p) for p in e.path)}: {e.message}" if e.path else e.message
        for e in validator.iter_errors(spine)
    )


def validate_source_refs(
    spine: dict[str, Any], allowed_block_ids: set[str]
) -> list[str]:
    errors: list[str] = []
    seen_node_ids: set[str] = set()
    for node in spine.get("nodes") or []:
        nid = node.get("id")
        if not nid:
            errors.append("node missing id")
            continue
        if nid in seen_node_ids:
            errors.append(f"duplicate node id: {nid}")
        seen_node_ids.add(nid)
        status = node.get("source_status")
        if status and status not in {
            "explicit_author",
            "author_paraphrase",
            "ai_inference",
            "external_counter",
            "quoted_position",
            "source_based_inference",
            "source_based_objection",
        }:
            errors.append(f"unknown source_status on {nid}: {status}")
        for bid in node.get("source_block_ids") or []:
            if bid not in allowed_block_ids:
                errors.append(f"unknown source_block_id on {nid}: {bid}")
    for rel in spine.get("relations") or []:
        for bid in rel.get("source_block_ids") or []:
            if bid not in allowed_block_ids:
                errors.append(
                    f"unknown source_block_id on relation "
                    f"{rel.get('from_node_id')}->{rel.get('to_node_id')}: {bid}"
                )
    return errors


def validate_relations(
    spine: dict[str, Any], allowed_block_ids: set[str] | None = None
) -> list[str]:
    """Validate relation endpoints and types. ``allowed_block_ids`` optional."""
    _ = allowed_block_ids
    errors: list[str] = []
    node_ids = {n.get("id") for n in (spine.get("nodes") or []) if n.get("id")}
    for i, rel in enumerate(spine.get("relations") or []):
        frm = rel.get("from_node_id")
        to = rel.get("to_node_id")
        rtype = rel.get("relation_type")
        if not frm or frm not in node_ids:
            errors.append(f"relations[{i}]: unknown from_node_id {frm!r}")
        if not to or to not in node_ids:
            errors.append(f"relations[{i}]: unknown to_node_id {to!r}")
        if rtype and rtype not in RELATION_TYPES:
            errors.append(f"relations[{i}]: unknown relation_type {rtype!r}")
    return errors


def strip_invalid_source_refs(
    spine: dict[str, Any], allowed_block_ids: set[str]
) -> dict[str, Any]:
    """Drop unknown citations (soft repair before full repair prompt)."""
    out = copy.deepcopy(spine)
    for node in out.get("nodes") or []:
        ids = [b for b in (node.get("source_block_ids") or []) if b in allowed_block_ids]
        removed = len(node.get("source_block_ids") or []) - len(ids)
        node["source_block_ids"] = ids
        if removed:
            warnings = list(node.get("warnings") or [])
            warnings.append(f"removed_{removed}_invalid_source_refs")
            node["warnings"] = warnings
        # Defensive source_status normalisation
        if node.get("source_status"):
            node["source_status"] = normalise_source_status(node.get("source_status"))
    for rel in out.get("relations") or []:
        rel["source_block_ids"] = [
            b for b in (rel.get("source_block_ids") or []) if b in allowed_block_ids
        ]
    return out


def strip_invalid_relations(
    spine: dict[str, Any], allowed_block_ids: set[str] | None = None
) -> dict[str, Any]:
    """Drop relations with missing endpoints or bad types; strip bad block refs."""
    out = copy.deepcopy(spine)
    node_ids = {n.get("id") for n in (out.get("nodes") or []) if n.get("id")}
    cleaned: list[dict[str, Any]] = []
    removed = 0
    for rel in out.get("relations") or []:
        frm = rel.get("from_node_id")
        to = rel.get("to_node_id")
        rtype = rel.get("relation_type")
        if frm not in node_ids or to not in node_ids or rtype not in RELATION_TYPES:
            removed += 1
            continue
        if allowed_block_ids is not None:
            rel = {
                **rel,
                "source_block_ids": [
                    b
                    for b in (rel.get("source_block_ids") or [])
                    if b in allowed_block_ids
                ],
            }
        cleaned.append(rel)
    out["relations"] = cleaned
    if removed:
        notes = (out.get("confidence_summary") or {}).get("notes") or ""
        out["confidence_summary"] = {
            "overall": (out.get("confidence_summary") or {}).get("overall"),
            "notes": (notes + f" | removed_{removed}_invalid_relations").strip(" |"),
        }
    return out
