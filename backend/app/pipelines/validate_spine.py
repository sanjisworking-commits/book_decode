"""Argument Spine schema and source-reference validation (Phase 3 baseline)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

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
        for bid in node.get("source_block_ids") or []:
            if bid not in allowed_block_ids:
                errors.append(f"unknown source_block_id on {nid}: {bid}")
    return errors


def strip_invalid_source_refs(
    spine: dict[str, Any], allowed_block_ids: set[str]
) -> dict[str, Any]:
    """Drop unknown citations (Phase 3 soft repair before full repair prompt)."""
    import copy

    out = copy.deepcopy(spine)
    for node in out.get("nodes") or []:
        ids = [b for b in (node.get("source_block_ids") or []) if b in allowed_block_ids]
        removed = len(node.get("source_block_ids") or []) - len(ids)
        node["source_block_ids"] = ids
        if removed:
            warnings = list(node.get("warnings") or [])
            warnings.append(f"removed_{removed}_invalid_source_refs")
            node["warnings"] = warnings
    return out
