# Prompt Architecture

Prompts are version-controlled markdown files. Do **not** embed one large prompt in application code.

## Directory

```text
backend/app/prompts/
├── argument_spine_extraction.md
├── argument_spine_synthesis.md
├── hinglish_adaptation.md
├── output_repair.md
└── source_validation.md
```

## Responsibilities

### `argument_spine_extraction.md`

Used for chapter or chunk-level extraction.

Must require:

- JSON-only output
- Strict schema compliance
- No unsupported external knowledge as author claims
- Source-block references on relevant fields
- Clear separation of explicit vs inferred content (`source_status`)
- Confidence values
- Nulls when evidence is insufficient
- No invented claims
- Reasoning reconstruction rather than summary

### `argument_spine_synthesis.md`

Used when a chapter was processed in multiple chunks.

Must:

- Combine partial outputs into one coherent chapter Argument Spine
- Remove duplicates
- Preserve competing interpretations when both are source-supported
- Reconstruct one coherent reasoning chain
- Retain all valid source references
- Avoid introducing new claims not present in partials or source

### `hinglish_adaptation.md`

Used only after a validated English Argument Spine exists.

Must:

- Adapt only the completed Argument Spine
- Preserve field structure and node IDs
- Retain important English terms
- Use natural Hindi-English (simple Hindi structure)
- Avoid literal translation
- Avoid changing logical claims

### `output_repair.md`

Used when JSON parse or JSON Schema validation fails.

Must:

- Accept invalid/partial model output + schema errors
- Return corrected JSON matching schema
- Not invent new argument content beyond fixing structure/types
- Preserve existing source-block IDs when present

### `source_validation.md`

Used when cited block IDs are missing or inconsistent.

Must:

- Accept spine JSON + allowed block ID set
- Remove or correct invalid citations
- Downgrade confidence / add warnings when support is weak
- Not invent replacement quotations
- Prefer null citations over fake IDs

## Runtime loading (planned)

- Load prompt text from files at job start
- Record filename + content hash / version in spine `processing` metadata
- Allow env override of prompt directory for experiments

## Out of scope for prompts

- Full-book Hindi translation before extraction
- Chat-style multi-turn tutoring prompts (future)
- External web research prompts (out of MVP)
