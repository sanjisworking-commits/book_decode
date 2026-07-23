# Prompt: Source Validation Repair

**Status:** Phase 0 stub — responsibilities and IO contract only. Full instruction text refined in Phase 6.  
**File:** `source_validation.md`  
**Used by:** source-reference repair retry

## Purpose

Correct Argument Spine citations so every `source_block_id` exists in the chapter allow-list, without inventing IDs or fake quotations.

## Inputs (runtime)

- Spine JSON with possibly invalid citations
- Allow-listed block IDs (and optionally short text previews)
- List of invalid IDs detected by the validator

## Required behaviour

- Remove or replace invalid citations only with IDs from the allow-list when clearly justified by existing statements
- Prefer empty citation lists + warnings over fabricated IDs
- Downgrade confidence when support weakens
- Do not invent replacement quotations
- Preserve node IDs and logical content unless a node becomes unsupported (then null + warning)
- JSON-only

## Outputs

- Spine JSON candidate for re-validation of source refs

## Non-goals

- Full re-extraction of the chapter (use chapter retry instead if repair cannot fix citations)
