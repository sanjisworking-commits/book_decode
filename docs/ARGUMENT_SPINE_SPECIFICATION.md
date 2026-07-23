# Argument Spine Specification

## Purpose

The Argument Spine is the product’s core object: a structured, source-grounded reconstruction of a chapter’s argument—not a summary and not a free-form essay.

## Required elements (per chapter)

Each chapter decode must include these node types, in logical order:

| Order | Node type key | Role |
|------:|---------------|------|
| 1 | `chapter_question` | What question the chapter addresses |
| 2 | `central_claim` | Author’s main claim for the chapter |
| 3 | `reasoning_steps` | Ordered chain of reasoning (may be multiple nodes) |
| 4 | `evidence_and_examples` | Evidence and examples supporting the claim |
| 5 | `hidden_assumptions` | Unstated assumptions the argument relies on |
| 6 | `tensions_or_gaps` | Tensions, weaknesses, or unresolved gaps |
| 7 | `strongest_counter_position` | Strongest fair counter-position |
| 8 | `consequence_if_correct` | What follows if the author is correct |
| 9 | `role_in_book` | Chapter’s role in the overall book |
| 10 | `one_sentence_decode` | Single-sentence chapter decode |
| 11 | `confidence_and_unresolved` | Confidence notes and unresolved points |
| 12 | `source_block_references` | Aggregate / index of cited source blocks |

`reasoning_steps` and `evidence_and_examples` may contain multiple ordered nodes. Other types are typically one primary node unless the schema allows a list under a parent.

## Source status (required on argument elements)

Every argument element must declare how it relates to the source:

| `source_status` | Meaning |
|-----------------|---------|
| `explicit_author` | Directly supported by clear author wording |
| `author_paraphrase` | Faithful restatement of author content |
| `ai_inference` | Analytical inference not explicitly stated |
| `external_counter` | External or constructed counter-perspective (not claimed as author’s view) |

## Node field model

Each Argument Spine item supports:

| Field | Description |
|-------|-------------|
| `id` | Stable node ID within the chapter spine |
| `node_type` | One of the types above |
| `statement_en` | English core statement |
| `explanation_en` | English explanation |
| `statement_hinglish` | Hindi-English core statement |
| `explanation_hinglish` | Hindi-English explanation |
| `source_status` | Enum above |
| `source_block_ids` | List of stable block IDs |
| `confidence` | Numeric 0–1 or null when unknown |
| `order` | Display / reasoning order |
| `prev_id` | Optional link to previous node |
| `next_id` | Optional link to next node |
| `warnings` | Optional list of warning strings |

English fields are authoritative. Hindi-English fields are produced only after English validation succeeds.

## Chapter-level envelope

Planned chapter spine document includes:

- `book_id`, `chapter_id`, `schema_version`
- `language_modes`: `["en", "hinglish"]`
- `nodes`: array of Argument Spine items
- `confidence_summary` (optional aggregate)
- `processing`: model, prompt versions, timestamps
- `validation`: schema and source-check results

Exact JSON Schema: [`../schemas/argument_spine.schema.json`](../schemas/argument_spine.schema.json).

## Integrity rules

1. No unsupported external knowledge presented as author claim.
2. Null / omit when evidence is insufficient—do not invent.
3. Every substantive node should cite one or more existing source-block IDs (except clearly marked `external_counter` cases, which still must not fabricate chapter quotes).
4. Reasoning order must be coherent (`order`, `prev_id` / `next_id`).
5. English and Hindi-English structures must align (same node IDs and types).

## Frontend rendering implications

- Nodes are expandable.
- Language toggle switches EN ↔ Hindi-English fields without changing structure.
- Source IDs open a preview of the stored original block text.
- Do not render fabricated demo spines; load API JSON only.

See [DESIGN_BRIEF_FOR_CLAUDE.md](DESIGN_BRIEF_FOR_CLAUDE.md) and [SOURCE_INTEGRITY_RULES.md](SOURCE_INTEGRITY_RULES.md).
