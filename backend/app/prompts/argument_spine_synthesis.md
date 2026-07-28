# Prompt: Argument Spine Synthesis

**Status:** Phase 4 — full instruction text  
**Version:** 5.0.0  
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

1. **Merge into one reasoning chain** covering the twelve Argument Spine element types (same schema as extraction). Preserve the full ordered `reasoning_steps` chain — see *Multiplicity* below; do not compress it to a single node.
2. **Remove duplicates** — if two partials repeat the same claim / node_type with near-identical statements, keep one and union their `source_block_ids`.
3. **Preserve competing interpretations** when both are source-supported and materially different — do not invent a false resolution. Prefer keeping the stronger source-supported statement as the primary node; record the competing view in `warnings` (e.g. `competing_interpretation: …`) without inventing new claims.
4. **Retain all valid source references** that support the kept statements (subset of `allow_listed_block_ids` only).
5. **Do not introduce claims** that are absent from the partials and the provided source evidence.
6. **Do not re-extract** the whole chapter from scratch; synthesise from the partials.
7. **JSON only** — return a single Argument Spine object matching the schema.
8. Keep `statement_hinglish` / `explanation_hinglish` as `null` (adaptation is a later phase).
9. Reassign stable `id` / `order` / `prev_id` / `next_id` for the merged node list.
10. Prefer reconstructing one coherent chapter-level chain over concatenating chunk dumps.
11. **Keep `central_claim` punchy.** The merged `central_claim.statement_en` must stay a single, standalone claim — no "because…" clause, no semicolon-joined add-ons; put all supporting reasoning in `explanation_en`.

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

### Multiplicity — do NOT flatten the chain

Two node types are **multi-node and must be preserved as an ordered list**, not collapsed:

- `reasoning_steps` — keep **every distinct step** of the argument as its own node, in logical order (`order`, `prev_id` / `next_id`). A chapter's reasoning is typically **3–5 steps**; collapsing them into one node destroys the logic chain, which is the core of the decode. Merge two steps only when they state the *same* inferential move in near-identical words. **Carry each kept step's `illustrative_example` object through unchanged** (pick the better one when merging duplicates); never fabricate source citations for it — its `source_block_ids` stays `[]`.
- `evidence_and_examples` — keep each materially distinct example/evidence item as its own node.

All **other** node types are single-primary: emit **one** node per type. When partials disagree on a single-primary node, keep the stronger source-supported statement as the primary and record the competing view in `warnings` (`competing_interpretation: …`).

Deduplicate *within* the multi-node types too (union `source_block_ids` for genuine repeats), but never reduce a real multi-step chain to one node to hit a count.

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
