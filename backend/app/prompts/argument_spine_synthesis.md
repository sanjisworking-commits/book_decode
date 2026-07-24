# Prompt: Argument Spine Synthesis

**Status:** Phase 4 — full instruction text  
**Version:** 4.0.0  
**File:** `argument_spine_synthesis.md`  
**Used by:** multi-chunk chapter merge pass (`pipelines.synthesise`)

## Purpose

Combine partial English Argument Spine outputs from the same chapter into **one** coherent chapter-level Argument Spine JSON.

## Inputs (runtime)

You receive a JSON payload after the marker `===PARTIAL_SPINES_JSON===` containing:

- `book_id`, `chapter_id`, `chapter_title`, `chapter_number`
- `allow_listed_block_ids` — full chapter allow-list (citations must be a subset)
- `partials` — ordered list of partial spine objects (each already schema-shaped with `nodes`)
- optional `source_excerpts` — small set of cited block texts for disambiguation only

## Required behaviour

1. **Merge into one reasoning chain** covering the twelve Argument Spine element types (same schema as extraction).
2. **Remove duplicates** — if two partials repeat the same claim / node_type with near-identical statements, keep one and union their `source_block_ids`.
3. **Preserve competing interpretations** when both are source-supported and materially different — do not invent a false resolution. Prefer keeping the stronger source-supported statement as the primary node; record the competing view in `warnings` (e.g. `competing_interpretation: …`) without inventing new claims.
4. **Retain all valid source references** that support the kept statements (subset of `allow_listed_block_ids` only).
5. **Do not introduce claims** that are absent from the partials and the provided source evidence.
6. **Do not re-extract** the whole chapter from scratch; synthesise from the partials.
7. **JSON only** — return a single Argument Spine object matching the schema.
8. Keep `statement_hinglish` / `explanation_hinglish` as `null` (adaptation is a later phase).
9. Reassign stable `id` / `order` / `prev_id` / `next_id` for the merged node list.
10. Prefer reconstructing one coherent chapter-level chain over concatenating chunk dumps.

## Node types (exactly the extraction set)

Use the same `node_type` enum as extraction:

- `chapter_question`
- `central_claim`
- `reasoning_steps`
- `evidence_and_examples`
- `hidden_assumptions`
- `tensions_or_gaps`
- `strongest_counter_position`
- `consequence_if_correct`
- `role_in_book`
- `one_sentence_decode`
- `confidence_and_unresolved`
- `source_block_references`

When multiple partials supply the same `node_type`, synthesise **one** primary node for that type (deduped / competing noted in warnings), unless the schema-compatible approach of a single ordered list with one primary per type is clearer — always prefer one primary node per type for MVP.

## Outputs

A single English Argument Spine JSON object with:

- `schema_version`: `"1.0"`
- `book_id`, `chapter_id`
- `language_modes`: `["en"]`
- `nodes`: merged ordered list
- optional `confidence_summary`
- hinglish fields null

## Non-goals

- Re-reading the entire raw EPUB outside provided partials + necessary block texts
- Hindi-English adaptation
- Inventing missing chapter conclusions not supported by partials
- Dropping minority but source-supported interpretations without noting them
