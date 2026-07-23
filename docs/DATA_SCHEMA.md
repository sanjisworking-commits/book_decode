# Data Schema

Canonical machine-readable format: **JSON**.

| Format | Use |
|--------|-----|
| Docling JSON | Raw EPUB extraction |
| Normalised internal JSON | Chapters and source blocks |
| Strict JSON Schema | LLM responses and stored spines |
| One final JSON file per chapter | Argument Spine (bilingual) |
| One metadata JSON per book | Book-level metadata snapshot |
| JSONL | Logging, batch jobs, evaluation datasets only |

Schema files: [`../schemas/`](../schemas/).

## Book metadata

Contract: [`book_metadata.schema.json`](../schemas/book_metadata.schema.json)

| Field | Description |
|-------|-------------|
| `book_id` | Stable ID for this upload/job |
| `title` | Detected or fallback title |
| `author` | Detected author(s) or null |
| `epub_filename` | Original filename |
| `processing_status` | See [PROCESSING_STATES.md](PROCESSING_STATES.md) |
| `language` | Primary source language (MVP expects English-majority EPUBs) |
| `chapter_count` | Detected chapters |
| `processed_chapter_count` | Successfully decoded chapters |
| `upload_timestamp` | ISO-8601 |
| `completion_timestamp` | ISO-8601 or null |
| `error` | Structured error object or null |

Also stored/queryable in SQLite for status APIs; filesystem snapshot under `data/books/{book_id}/metadata.json`.

## Source chapter

Contract: [`source_chapter.schema.json`](../schemas/source_chapter.schema.json)

| Field | Description |
|-------|-------------|
| `chapter_id` | Stable chapter ID |
| `chapter_number` | Ordinal when known |
| `chapter_title` | Title string |
| `heading_hierarchy` | Nested heading path |
| `source_blocks` | Ordered blocks |
| Block: `block_id` | Full stable ID |
| Block: `block_type` | `paragraph`, `heading`, `list_item`, `table`, `quote`, `note`, etc. |
| Block: `text` | Original text |
| Block: `order_index` | Integer order within chapter |

### Reference fixture (not canonical)

[`../sample-data/reference/a_thousand_brains_clean.json`](../sample-data/reference/a_thousand_brains_clean.json) is a **pre-normalisation** EPUB-derived shape (`sections[]` with `paragraphs` lacking stable block IDs). It informs realistic structure detection. **MVP `source_chapter` schema supersedes it.** See [`../sample-data/README.md`](../sample-data/README.md).

## Argument Spine output

Contract: [`argument_spine.schema.json`](../schemas/argument_spine.schema.json)

See [ARGUMENT_SPINE_SPECIFICATION.md](ARGUMENT_SPINE_SPECIFICATION.md) for node types and fields.

## Processing job

Contract: [`processing_job.schema.json`](../schemas/processing_job.schema.json)

Tracks book-level stage, chapter-level states, retry counts, and timestamps for the status API.

## File layout per book

```text
data/books/{book_id}/
  metadata.json
  chapters/
    {chapter_id}.source.json
    {chapter_id}.spine.json
```

## Versioning

- `schema_version` on every stored document
- Prompt versions recorded in spine `processing` metadata
- Breaking schema changes require a new version and migration note in this doc

## Frontend types

Frontend TypeScript types under `frontend/src/types/` must be generated from or kept aligned with `schemas/` (implementation Phase 7). No hardcoded narrative content in types files.
