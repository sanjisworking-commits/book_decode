# Prompt: Argument Spine Synthesis

**Status:** Phase 0 stub — responsibilities and IO contract only. Full instruction text refined in Phase 4.  
**File:** `argument_spine_synthesis.md`  
**Used by:** multi-chunk chapter merge pass

## Purpose

Combine partial English Argument Spine outputs from the same chapter into one coherent chapter-level Argument Spine.

## Inputs (runtime)

- Ordered list of partial spine JSON objects
- Full allow-listed source-block ID set for the chapter
- Chapter metadata (id, title, number)

## Required behaviour

- Merge into one coherent reasoning chain
- Remove duplicate nodes/claims
- Preserve competing interpretations when both are source-supported
- Retain all valid source references
- Do not introduce claims absent from partials and source evidence
- JSON-only; schema compliant
- Hindi-English fields remain null until adaptation

## Outputs

- Single English chapter Argument Spine JSON

## Non-goals

- Re-reading the entire raw EPUB outside provided partials + necessary block texts
- Language adaptation
