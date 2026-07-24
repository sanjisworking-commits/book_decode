# Prompt: Source Validation Repair

**Status:** Phase 6 — full instruction text  
**Version:** 6.0.0  
**File:** `source_validation.md`  
**Used by:** source-reference repair retry (`pipelines.validate_persist`)

## Purpose

Correct Argument Spine citations so every `source_block_id` exists in the chapter allow-list, without inventing IDs or fake quotations.

## Inputs (runtime)

Payload after `===SOURCE_REPAIR_JSON===`:

- `spine` — spine JSON with possibly invalid citations
- `allow_listed_block_ids` — valid block IDs for the chapter
- `invalid_ids` — IDs rejected by the validator
- optional `block_previews` — short text for allow-listed IDs

## Required behaviour

1. Remove invalid citations, or replace them only with allow-listed IDs when clearly justified by the existing statement.
2. Prefer empty citation lists + `warnings` over fabricated IDs.
3. Downgrade `confidence` when support weakens.
4. Do not invent replacement quotations.
5. Preserve node IDs and logical content; if a node becomes unsupported, keep the statement and clear citations with a warning.
6. JSON only — return one spine object.

## Outputs

Spine JSON candidate for re-validation of source refs.

## Non-goals

- Full re-extraction of the chapter (use chapter retry instead if repair cannot fix citations)
- Changing English logical claims
