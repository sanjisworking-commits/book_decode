# Prompt Architecture

Prompts are version-controlled markdown files. Do **not** embed one large prompt in application code.

## Directory

```text
backend/app/prompts/
├── argument_discovery.md                 # Pass 1 (v1.0.0)
├── argument_discovery_merge.md           # Pass 1b chunk merge (v1.0.0)
├── argument_spine_adaptive_synthesis.md  # Pass 2 final spine (v4.0.0)
├── argument_spine_extraction.md          # DEPRECATED — fixed one-prompt extract (rollback only)
├── argument_spine_synthesis.md           # Legacy Phase 4 partial-spine merge (not default EN path)
├── hinglish_adaptation.md
├── output_repair.md
└── source_validation.md
```

## Responsibilities

### `argument_discovery.md` (Pass 1)

Used for whole-chapter or chunk-level **Argument Discovery**.

Must require:

- JSON-only output matching discovery schema
- Chapter type(s), movements, claims, supporting material
- Source-grounded objections only when present in source
- Recommended / omit node types for Pass 2
- Allow-listed `source_block_ids` only
- Empty arrays OK when unsupported

### `argument_discovery_merge.md` (Pass 1b)

Used when a chapter needed multiple discovery calls.

Must:

- Merge chunk discoveries into one chapter discovery
- Deduplicate claims/movements; mark true conflicts
- Preserve valid source references
- Not invent external counters

### `argument_spine_adaptive_synthesis.md` (Pass 2)

Builds the final English Argument Spine (`schema_version` `"2.0"`) from discovery + source blocks.

Must:

- Choose flexible node types warranted by the chapter
- Emit optional `relations[]`
- Preserve qualifications / position owners
- Set hinglish fields to null
- Not invent `external_counter` nodes in this pass

### `argument_spine_extraction.md` (deprecated)

Fixed 12-slot one-prompt extraction. Kept for rollback experiments only. Default English path uses discovery → adaptive synthesis.

### `argument_spine_synthesis.md` (legacy Phase 4)

Combines **partial spines** from the old multi-chunk extract path. Not used when adaptive two-pass already wrote a complete English spine.

### `hinglish_adaptation.md`

Used only after a validated English Argument Spine exists (skipped under `PROTOTYPE_ONE_SHOT`).

### `output_repair.md` / `source_validation.md`

Schema and citation repair prompts for hard validation retries.

## Runtime loading

- Load prompt text from files; record filename + content hash in `processing.prompt_versions`
- Discovery / adaptive synthesis use `llm_pass_temperature` (default `0.1`)
- Optional disk cache under `data/cache/llm/` when `LLM_CACHE_ENABLED=true`

## Out of scope for prompts

- Full-book Hindi translation before extraction
- Separate external-criticism pipeline
- Chat-style multi-turn tutoring prompts (future)
