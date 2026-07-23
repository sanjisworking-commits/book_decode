# Sample data

This directory holds **structural reference fixtures only**.

## Rules

- Do **not** treat files here as final product architecture.
- Do **not** hardcode fixture prose into the frontend.
- Do **not** invent or commit Argument Spine claims, assumptions, counters, or chapter decodes here.
- Canonical contracts live in [`../schemas/`](../schemas/) and are documented in [`../docs/DATA_SCHEMA.md`](../docs/DATA_SCHEMA.md).

## `reference/a_thousand_brains_clean.json`

Pre-normalisation EPUB-derived book JSON for *A Thousand Brains* (Jeff Hawkins).

| Property | Value |
|----------|--------|
| Purpose | Realistic EPUB messiness for chapter-detection and normalisation design/tests |
| Shape | Top-level metadata + `sections[]` with `paragraphs` / `lists` / `tables` |
| Missing vs MVP | Stable `book.chapter.section.block` IDs, ordered source blocks, chapter-level Argument Spine |
| Allowed later use | Phase 1–2 fixtures for structure detection and block-ID assignment |
| Forbidden use | Static demo Argument Spine; frontend chapter content |

MVP schemas supersede this file’s shape. See [`../docs/SOURCE_INTEGRITY_RULES.md`](../docs/SOURCE_INTEGRITY_RULES.md).
