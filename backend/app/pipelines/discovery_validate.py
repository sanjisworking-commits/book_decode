"""Validate Argument Discovery reports (allow-listed citations + shape)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[3]
DISCOVERY_SCHEMA_PATH = REPO_ROOT / "schemas" / "argument_discovery.schema.json"


def load_argument_discovery_schema() -> dict[str, Any]:
    return json.loads(DISCOVERY_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_discovery_schema(discovery: dict[str, Any]) -> list[str]:
    schema = load_argument_discovery_schema()
    validator = Draft202012Validator(schema)
    return sorted(
        f"{'.'.join(str(p) for p in e.path)}: {e.message}" if e.path else e.message
        for e in validator.iter_errors(discovery)
    )


def _collect_block_ids(obj: Any, out: list[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "source_block_ids" and isinstance(value, list):
                out.extend(str(v) for v in value if v)
            else:
                _collect_block_ids(value, out)
    elif isinstance(obj, list):
        for item in obj:
            _collect_block_ids(item, out)


def validate_discovery_source_refs(
    discovery: dict[str, Any], allowed_block_ids: set[str]
) -> list[str]:
    cited: list[str] = []
    _collect_block_ids(discovery, cited)
    errors: list[str] = []
    for bid in cited:
        if bid not in allowed_block_ids:
            errors.append(f"unknown source_block_id in discovery: {bid}")
    return errors


def strip_invalid_discovery_refs(
    discovery: dict[str, Any], allowed_block_ids: set[str]
) -> dict[str, Any]:
    import copy

    out = copy.deepcopy(discovery)

    def scrub(obj: Any) -> Any:
        if isinstance(obj, dict):
            cleaned: dict[str, Any] = {}
            for key, value in obj.items():
                if key == "source_block_ids" and isinstance(value, list):
                    cleaned[key] = [b for b in value if b in allowed_block_ids]
                else:
                    cleaned[key] = scrub(value)
            return cleaned
        if isinstance(obj, list):
            return [scrub(item) for item in obj]
        return obj

    return scrub(out)


def validate_discovery(
    discovery: dict[str, Any], allowed_block_ids: set[str]
) -> list[str]:
    """Schema + citation checks. Empty optional arrays are OK."""
    errors = validate_discovery_schema(discovery)
    errors.extend(validate_discovery_source_refs(discovery, allowed_block_ids))
    # Soft required statement checks: if claim/support objects exist, statement non-empty
    for claim in discovery.get("claims") or []:
        if isinstance(claim, dict) and not str(claim.get("statement") or "").strip():
            errors.append(f"empty claim statement on {claim.get('claim_id')}")
    for item in discovery.get("supporting_material") or []:
        if isinstance(item, dict) and not str(item.get("statement") or "").strip():
            errors.append(f"empty supporting_material statement on {item.get('item_id')}")
    return errors
