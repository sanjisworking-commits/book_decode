# Prompt: Argument Spine Extraction

**Status:** Phase 0 stub — responsibilities and IO contract only. Full instruction text refined in Phase 3.  
**File:** `argument_spine_extraction.md`  
**Used by:** chapter or chunk extraction pass

## Purpose

Analyse provided chapter/chunk source blocks and return a structured English Argument Spine fragment (or full spine for small chapters) as JSON only.

## Inputs (runtime)

- Book ID, chapter ID
- Allow-listed source-block IDs and their texts
- Optional: book title, chapter title, chapter role hints from structure detector
- JSON Schema for Argument Spine nodes

## Required behaviour

- JSON-only output; no markdown fences in production mode
- Strict schema compliance
- No unsupported external knowledge presented as author claims
- Attach `source_block_ids` to every relevant node
- Set `source_status` distinctly: `explicit_author` | `author_paraphrase` | `ai_inference` | `external_counter`
- Include confidence values; use null statements when evidence is insufficient
- Do not invent claims
- Reconstruct reasoning; do not summarise like a book blurb

## Outputs

- Partial or full English Argument Spine JSON matching `schemas/argument_spine.schema.json` (Hindi-English fields may be null at this stage)

## Non-goals

- Full-book translation
- Hindi-English adaptation (separate prompt)
- Web research
