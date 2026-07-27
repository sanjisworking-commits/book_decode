# Argument Spine Specification

## Purpose

The Argument Spine is the product’s core object: a structured, source-grounded reconstruction of a chapter’s argument—not a summary and not a free-form essay.

## Adaptive node inventory (schema 2.0)

Pass 2 chooses which types the chapter warrants. Do **not** force every chapter into a fixed 12-slot template.

| Node type | Role |
|-----------|------|
| `chapter_objective` | What the chapter sets out to do |
| `chapter_question` | What question the chapter addresses |
| `central_claim` | Author’s main claim for the chapter |
| `organising_idea` | Organising idea when a single “claim” underspecifies the chapter |
| `supporting_claim` | Subordinate claim |
| `reasoning_step` | Ordered reasoning link (legacy alias: `reasoning_steps`) |
| `definition` | Definition introduced in source |
| `evidence` | Evidence (legacy blob: `evidence_and_examples`) |
| `example` | Example / illustration |
| `analogy` | Analogy |
| `quotation` | Quotation |
| `assumption` | Assumption (legacy: `hidden_assumptions`) |
| `qualification` | Scope limit / hedge (legacy: `tensions_or_gaps`) |
| `objection` | Source-grounded objection (legacy counter: `strongest_counter_position`) |
| `response` | Author response to an objection |
| `implication` | Implication / consequence (legacy: `consequence_if_correct`) |
| `narrative_context` / `historical_context` | Context nodes when present |
| `transition` | Structural transition |
| `role_in_book` | Chapter’s role in the book |
| `one_sentence_decode` | Single-sentence decode |
| `unresolved_question` | Open questions (legacy: `confidence_and_unresolved`) |
| `source_block_references` | Aggregate index of cited blocks (program may rebuild) |

Normally prefer: objective or question; central claim or organising idea; decode sentence; role; unresolved when warranted.

## Relations (optional top-level)

`relations[]` entries:

| Field | Description |
|-------|-------------|
| `from_node_id` / `to_node_id` | Endpoints in `nodes` |
| `relation_type` | e.g. `supports`, `challenges`, `responds_to`, `provides_evidence_for`, … |
| `explanation_en` | Optional |
| `source_block_ids` | Allow-listed citations |

## Source status

| `source_status` | Meaning |
|-----------------|---------|
| `explicit_author` | Directly supported by clear author wording |
| `author_paraphrase` | Faithful restatement of author content |
| `quoted_position` | Position quoted / attributed in the source |
| `source_based_inference` | Inference tightly grounded in source |
| `source_based_objection` | Objection grounded in the source (not invented external criticism) |
| `ai_inference` | Analytical inference |
| `external_counter` | External criticism — **not** invented on the default source-grounded path |

## Node field model

| Field | Description |
|-------|-------------|
| `id` | Stable node ID within the chapter spine |
| `node_type` | Adaptive type (aliases normalised in postprocess) |
| `custom_label` | Optional short label |
| `statement_en` / `explanation_en` | English content |
| `statement_hinglish` / `explanation_hinglish` | Hindi-English (null on EN-only path) |
| `claim_level` / `importance` | Optional ranking |
| `position_owner` / `narrating_voice` | Speaker attribution |
| `scope_qualifiers` | Preserved hedges / limits |
| `supports_node_ids` / `supports_claim_ids` | Optional support pointers |
| `source_status` | Enum above |
| `source_block_ids` | Allow-listed block IDs |
| `confidence` | 0–1 or null |
| `order` / `prev_id` / `next_id` | Program-owned sequencing |
| `warnings` | Optional |

## Decode / Remember mapping (UI)

| View slot | Preferred node types |
|-----------|----------------------|
| Claim / takeaway | `central_claim` else `organising_idea` |
| Logic chain / key points | `reasoning_step` / `supporting_claim` (ordered) |
| Evidence / example | first `evidence` or `example` |
| Counter | `objection` (source-grounded; not invented external) |
| Flash front | `chapter_question` or `chapter_objective` |
| Hook | `one_sentence_decode` |

## Chapter-level envelope

- `schema_version`: `"2.0"` ( `"1.0"` still accepted for legacy artefacts)
- `book_id`, `chapter_id`, `language_modes`
- `nodes`, optional `relations`
- `confidence_summary`, `processing`, `validation` (includes `relations_valid`)

Exact JSON Schema: [`../schemas/argument_spine.schema.json`](../schemas/argument_spine.schema.json).  
Discovery contract: [`../schemas/argument_discovery.schema.json`](../schemas/argument_discovery.schema.json).

## Integrity rules

1. No unsupported external knowledge presented as author claim.
2. Null / omit when evidence is insufficient—do not invent empty slots.
3. Cite only existing source-block IDs.
4. Prefer source-grounded objections / quoted positions over `external_counter`.
5. English and Hindi-English structures must align when both modes are present.
