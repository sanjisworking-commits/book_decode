# Canonical Book Schema

**Schema version:** `2.0`  
**Primary artefact:** `data/books/{book_id}/book.json`  
**JSON Schema:** [`schemas/canonical_book.schema.json`](../schemas/canonical_book.schema.json)

This document is the specification for the lossless book representation produced by Phase 2 normalisation. Downstream pipelines must build on this schema rather than re-parsing Docling output.

## Pipeline role

```text
EPUB → Docling → docling.json → normalise → book.json
                                              ↓
                                    chapter adapter → *.source.json
                                              ↓
                                         chunk → Argument Spine → modes
```

Normalisation **must not** summarise, paraphrase, rewrite, infer arguments, or chunk for the LLM. It only organises and preserves.

## Hierarchy

```text
Book
├── front_matter.blocks[]
├── parts[]?                  (omitted when the book has no parts)
│   └── chapters[]
└── chapters[]                (authoritative flat chapter list; part_id links when parts exist)
    ├── sections[]
    │   └── blocks[]
    └── blocks[]              (chapter reading-order view of the same block objects)
```

Parts are never invented. If Docling/content has no Part markers, `parts` is absent or empty and chapters sit at the book level.

---

## Book fields

| Field | Purpose | Docling source | Downstream |
|-------|---------|----------------|------------|
| `schema_version` | Contract version (`2.0`) | — | All consumers |
| `book_id` | Stable book identity | Upload / metadata | Storage, APIs, block IDs |
| `title` | Book title | Docling `name` / EPUB metadata | UI, prompts |
| `author` | Author string | EPUB metadata hint | UI |
| `language` | Primary language | EPUB metadata hint | Future multi-language |
| `source.converter` | Provenance of extraction | `"docling"` | Debugging |
| `source.docling_schema_name` | Docling schema name | `schema_name` | Debugging |
| `source.docling_version` | Docling doc version | `version` | Debugging |
| `front_matter` | Pre-chapter material | Ordered stream before first chapter | Search, UI |
| `parts` | Optional part grouping | Part headings in stream | Book map |
| `chapters` | Authoritative chapter list | Chapter markers + content | Chunk, spine, modes |

---

## Part fields

| Field | Purpose | Docling source | Downstream |
|-------|---------|----------------|------------|
| `part_id` | Deterministic id (`part01`) | Assigned at normalisation | Book map |
| `title` | Part title text | Heading text | UI |
| `order_index` | Part order | Sequence of part markers | Navigation |
| `source_ref` | Originating Docling ref | `self_ref` of part heading | Provenance |
| `chapters` | Chapters in this part | Nested chapter objects | Book map |

---

## Chapter fields

| Field | Purpose | Docling source | Downstream |
|-------|---------|----------------|------------|
| `chapter_id` | Deterministic id (`ch01`) | Assigned at normalisation | Chunk, spine, APIs |
| `title` | Chapter title | Chapter heading text | UI, prompts |
| `chapter_number` | Numeric chapter when parseable | Title regex | Book map |
| `part_id` | Parent part or null | Current part state | Hierarchy |
| `order_index` | Chapter order in book | Sequence | Navigation |
| `source_ref` | Chapter heading ref | `self_ref` | Provenance |
| `heading_path` | Path at chapter open | Heading stack | UI breadcrumbs |
| `sections` | Nested sections | Headings within chapter | Structure-aware chunking |
| `blocks` | Flat reading-order blocks | Same objects as in sections | Chunk, extract, search |

---

## Section fields

| Field | Purpose | Docling source | Downstream |
|-------|---------|----------------|------------|
| `section_id` | Deterministic id (`sec01`) | Assigned per heading | Block IDs |
| `title` | Section heading text | Heading text | UI |
| `heading_level` | H1–H4 style level | Docling `level` | Hierarchy |
| `heading_path` | Full path including this section | Incremental stack | Breadcrumbs, chunking |
| `order_index` | Order within chapter | Sequence | Navigation |
| `source_ref` | Heading `self_ref` | Docling | Provenance |
| `blocks` | Blocks in this section | Stream membership | Structure |

---

## Block fields

| Field | Purpose | Docling source | Downstream |
|-------|---------|----------------|------------|
| `block_id` | Stable id `book.chapter.section.blockNNN` | Assigned | Citations, spine, notes |
| `block_type` | Semantic type | Label map | Chunk boundaries, UI |
| `text` | Primary readable text | `text` / caption / table serialization | LLM, search |
| `book_id` | Scope | Book | Filters |
| `chapter_id` | Scope (null in front matter) | Current chapter | Filters |
| `section_id` | Scope | Current section | Filters |
| `part_id` | Scope | Current part | Filters |
| `heading_path` | Full path at emission | Heading stack copy | Context for AI / UI |
| `source_ref` | Exact Docling node | `self_ref` | Traceability |
| `docling_index` | Index in texts/tables/pictures | Array index | Traceability |
| `order_index` | Order within chapter (or front matter) | Chapter counter | Reading order |
| `book_order_index` | Global reading order | Book counter | Search, global nav |
| `metadata` | Extensible typed payload | Labels + structured data | Chunking, figures, tables |

### `metadata` common keys

| Key | Purpose | Source |
|-----|---------|--------|
| `label` | Original Docling label | `label` |
| `heading_level` | For headings | `level` |
| `word_count` | Precomputed | Derived from `text` |
| `char_count` | Precomputed | Derived from `text` |

### Type-specific metadata

| `block_type` | Extra metadata | Why |
|--------------|----------------|-----|
| `table` | `table.headers`, `table.rows`, `table.caption`, `table.data` | Lossless table; future Publisher / Decode |
| `list` / `list_item` | `list_style`, `items[]` with refs | Preserve list structure |
| `figure` / `image` | `figure_id`, `caption`, caption ref | Future diagram explanation |
| `note` | `note_kind`, optional `linked_block_id` | Footnotes without merging into body |

---

## Block types

Supported: `heading`, `paragraph`, `quote`, `table`, `list`, `list_item`, `note`, `image`, `figure`, `diagram`, `equation`, `code`, `sidebar`, `callout`, `exercise`, `summary`, `warning`, `example`, `other`.

Unknown Docling labels map to `other` (label preserved in metadata).

---

## Compatibility: `*.source.json`

Adapter flattens one chapter’s `blocks` into `source_blocks` ([`schemas/source_chapter.schema.json`](../schemas/source_chapter.schema.json) v2.0). Phase 3 chunk/extract may ignore extra fields and only require `block_id` + `text`.

---

## Validation rules

- Unique `block_id` across the book
- Unique `(chapter_id, order_index)` and unique `book_order_index`
- Non-empty `block_id`, `chapter_id`, `section_id` where required
- No empty heading titles used as structural markers
- Sections belong to a chapter (no orphans)

---

## Downstream dependents (planned)

| Pipeline / mode | Uses |
|-----------------|------|
| Chunk builder | `blocks`, headings, token estimates from metadata |
| Argument Spine | `source_ref` / `block_id` citations |
| Guide / Decode / Reflect / Remember | Hierarchy + blocks |
| Search / highlights / notes / bookmarks | Stable `block_id` |
| Spaced repetition | Block or spine node ids |
| Publisher mode | Tables, figures, structure |
| Multi-language | Same block ids; adapted fields elsewhere |
