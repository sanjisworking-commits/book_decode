# AI Pipeline

## Rule: English first, then Hindi-English

Do **not** translate the full EPUB into Hindi before argument extraction.

1. Discover argument structure, then synthesise the Argument Spine accurately in **English**.
2. Adapt **only the completed Argument Spine** into Hindi-English (skipped when `PROTOTYPE_ONE_SHOT=true`).
3. Persist chapter JSON (`*.discovery.json`, `*.spine.en.json`, `*.spine.json`).

IndicTrans2 may be evaluated later as an optional comparison layer. It is **not** the reasoning engine. MVP language adaptation uses the same main LLM with a dedicated prompt.

## Adaptive two-pass English path (default)

```text
source_chapter JSON
→ slim allow-listed blocks {block_id, block_type, text}
→ Pass 1: Argument Discovery (whole chapter if under prompt budget)
     └─ if over budget: per-chunk discovery → discovery merge
→ Pass 2: Adaptive Argument Spine synthesis (flexible node types + relations)
→ Schema + source-ref + relation validation (strip / one repair)
→ Persist EN spine artefacts
→ [full path] Hinglish adapt → hard validate
→ [oneshot / PROTOTYPE_ONE_SHOT] soft validate; hinglish stays null
```

`PROTOTYPE_ONE_SHOT=true` means **one whole-chapter discovery call + one synthesis call** (chunk only when over the prompt token budget). It does **not** mean a single fixed extraction prompt.

Phase 4 partial-spine merge (`argument_spine_synthesis.md`) remains in-repo for legacy/rollback but is **not** the default English path.

## End-to-end pipeline

```text
User uploads EPUB or chapter/book JSON
→ Ingestion / normalisation produces source chapters with stable block IDs
→ Oversized chapters get a chunk plan (structure/token) only when needed
→ Pass 1 Argument Discovery (oneshot or chunked+merge)
→ Pass 2 Adaptive Argument Spine synthesis
→ JSON Schema + source-reference + relation validation
→ English Argument Spine saved (`*.spine.en.json`)
→ Optional language-adaptation pass creates Hindi-English fields
→ Final chapter JSON stored (`*.spine.json`)
→ Frontend loads stored JSON (Decode / Remember / canvas remap flexible types)
```

## Stage responsibilities

| Stage | Owner module | Output |
|-------|--------------|--------|
| Upload + file validation | `services` / `pipelines.ingest` | Stored EPUB/JSON, book record |
| Docling conversion | `pipelines.ingest` | Raw structured JSON |
| Normalisation | `pipelines.normalise` | Clean tree, metadata |
| Structure + block IDs | `pipelines.normalise` | Chapters with source blocks |
| Chunking | `pipelines.chunk` | Ordered chunks when over budget |
| Discovery | `pipelines.discovery` (+ merge) | `*.discovery.json` |
| Adaptive synthesis | `pipelines.adaptive_synthesis` | English chapter spine v2 |
| Schema / source / relation validation | `pipelines.validate_spine` / `validate_persist` | Pass / repair |
| Hindi-English adaptation | `pipelines.adapt` | Bilingual fields (full path) |
| Persist | `storage` | `*.spine.json` + status |

## Reasoning LLM duties

- Discover chapter type, movements, claims, support, source-grounded objections
- Choose which node types the chapter warrants (do not force a fixed 12-slot template)
- Separate claims from evidence / examples / definitions
- Preserve qualifications and speaker attribution
- Emit optional `relations[]` among nodes
- Cite only allow-listed `source_block_ids`
- Do not invent external counters in the source-grounded pass
- Return structured JSON only; null hinglish on the English path

## Provenance distinctions

| Status | Meaning |
|--------|---------|
| `quoted_position` | Position attributed / quoted in the source |
| `source_based_objection` | Objection grounded in the source (not invented criticism) |
| `source_based_inference` | Inference tightly tied to source wording |
| `ai_inference` | Analytical inference with weaker/no direct wording |
| `external_counter` | Reserved for future / rare external criticism (not default extract) |

## Hindi-English adaptation duties

- Input: completed English Argument Spine only
- Preserve exact logical meaning and field structure
- Simple Hindi sentence construction
- Retain important English terminology
- Avoid literal word-for-word translation

## Chunking strategy

Priority order:

1. Whole chapter if discovery prompt fits budget
2. Existing chunk plan / token packs for discovery only
3. Merge chunk discoveries, then one chapter-level synthesis

## Fail-closed behaviour

Invalid spines after retries are not marked `completed`. Soft oneshot validation may tolerate minor schema noise for demo UI, but still strips invented block IDs and bad relations.
