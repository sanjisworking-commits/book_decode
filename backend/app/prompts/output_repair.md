# Prompt: Output Repair

**Status:** Phase 0 stub — responsibilities and IO contract only. Full instruction text refined in Phase 6.  
**File:** `output_repair.md`  
**Used by:** schema / JSON repair retry

## Purpose

Repair invalid or partially invalid model output so it matches the Argument Spine JSON Schema—without inventing new argument content.

## Inputs (runtime)

- Raw or partially parsed model output
- JSON Schema validation error list
- Target schema identity (`argument_spine`)

## Required behaviour

- Return corrected JSON only
- Fix structure, types, enums, required fields
- Preserve existing statements and source-block IDs when present
- Use nulls rather than inventing new claims to satisfy fields
- Do not escalate into a new analytical pass unless content is entirely unusable (then signal failure)

## Outputs

- Schema-shaped JSON candidate for re-validation

## Non-goals

- Hindi-English rewriting
- Adding new evidence or counters not present in the broken output
