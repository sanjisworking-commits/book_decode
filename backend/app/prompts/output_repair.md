# Prompt: Output Repair

**Status:** Phase 6 — full instruction text  
**Version:** 6.0.0  
**File:** `output_repair.md`  
**Used by:** schema / JSON repair retry (`pipelines.validate_persist`)

## Purpose

Repair invalid or partially invalid Argument Spine JSON so it matches the Argument Spine JSON Schema—**without inventing new argument content**.

## Inputs (runtime)

Payload after `===REPAIR_SPINE_JSON===`:

- `spine` — raw or partially valid spine object
- `schema_errors` — list of JSON Schema validation error strings
- `target_schema` — `"argument_spine"`

## Required behaviour

1. Return **corrected JSON only** (one Argument Spine object).
2. Fix structure, types, enums, and required fields.
3. Preserve existing `statement_en` / hinglish text and `source_block_ids` when present.
4. Prefer `null` over inventing new claims to satisfy fields.
5. Keep node `id` values stable when possible; do not drop nodes solely to pass schema.
6. Do not escalate into a new analytical / extraction pass.
7. Do not invent source-block IDs.

## Outputs

Schema-shaped Argument Spine JSON candidate for re-validation.

## Non-goals

- Hindi-English rewriting
- Adding new evidence or counters not present in the broken output
- Full chapter re-extraction
