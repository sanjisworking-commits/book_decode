# AI Pipeline

## Rule: English first, then Hindi-English

Do **not** translate the full EPUB into Hindi before argument extraction.

1. Extract and synthesise the Argument Spine accurately in **English**.
2. Adapt **only the completed Argument Spine** into Hindi-English.
3. Persist one bilingual chapter JSON.

IndicTrans2 may be evaluated later as an optional comparison layer. It is **not** the reasoning engine. MVP language adaptation uses the same main LLM with a dedicated prompt.

## End-to-end pipeline

```text
User uploads EPUB
→ Python ingestion service receives the file
→ Docling converts EPUB into structured JSON
→ Document normalisation removes irrelevant metadata and formatting noise
→ Book structure detector identifies title, metadata, chapters, headings and paragraphs
→ Each paragraph or logical block receives a stable source-block ID
→ Chapters are separated
→ Oversized chapters are divided by headings, sections and paragraphs
→ Individual chapter chunks are sent to the reasoning LLM
→ The LLM generates partial Argument Spine outputs
→ A synthesis pass combines partial outputs into one chapter-level Argument Spine
→ JSON Schema validation checks the response
→ Source-reference validation checks that cited block IDs exist
→ English Argument Spine is saved (in-memory / staging)
→ A language-adaptation pass creates the Hindi-English version
→ Final bilingual chapter JSON is stored
→ Frontend loads the stored JSON
→ User explores the Argument Spine
```

## Stage responsibilities

| Stage | Owner module (planned) | Output |
|-------|------------------------|--------|
| Upload + file validation | `services` / `pipelines.ingest` | Stored EPUB, book record |
| Docling conversion | `pipelines.ingest` | Raw structured JSON |
| Normalisation | `pipelines.normalise` | Clean tree, metadata |
| Structure + block IDs | `pipelines.normalise` | Chapters with source blocks |
| Chunking | `pipelines.chunk` | Ordered chunks with block ID sets |
| Extraction | `pipelines.extract` + prompt | Partial English spines |
| Synthesis | `pipelines.synthesise` + prompt | One English chapter spine |
| Schema validation | `pipelines.validate` | Pass / repair request |
| Source validation | `pipelines.validate` | Pass / repair request |
| Hindi-English adaptation | `pipelines.adapt` + prompt | Bilingual fields |
| Alignment check | `pipelines.validate` | EN / Hinglish structure match |
| Persist | `storage` | `*.spine.json` + status |

## Reasoning LLM duties

- Analyse chapter (or chunk) content
- Identify chapter question and central claim
- Reconstruct reasoning chain; separate evidence from reasoning
- Identify hidden assumptions, tensions, fair counter-position
- Explain consequence and chapter role in the book
- Return structured JSON only
- Attach source-block IDs to every relevant output
- Use nulls when evidence is insufficient; do not invent claims
- Prefer reasoning reconstruction over summary

## Hindi-English adaptation duties

- Input: completed English Argument Spine only
- Preserve exact logical meaning and field structure
- Simple Hindi sentence construction
- Retain important English terminology
- Avoid literal word-for-word translation
- Avoid unnecessarily formal / Sanskritised Hindi
- Avoid obscure Hindi replacements for familiar English concepts

## Chunking strategy

Priority order:

1. Chapter boundaries
2. Heading boundaries
3. Section boundaries
4. Paragraph boundaries
5. Token-limit fallback

| Case | Approach |
|------|----------|
| Small chapter | Single extraction pass |
| Large chapter | Section chunks → partial extraction → synthesis → source validation |
| Very long chapter | Same as large; stricter token limit; more sections |
| Empty / malformed | Mark chapter failed with structured error; do not invent content |
| Tables / notes / quotes | Preserve as typed source blocks; cite when used as evidence |

### Chunk integrity concerns

| Concern | Planned handling |
|---------|------------------|
| Context overlap | Small overlap of trailing/leading blocks between adjacent chunks |
| Duplicate claims | Synthesis prompt removes duplicates |
| Conflicting partials | Synthesis preserves competing interpretations when both are source-supported; does not invent a false resolution |
| Source-block preservation | Chunks carry explicit block ID lists; citations must be subset |
| Token limits | Env `CHUNK_TOKEN_LIMIT`; fallback split at paragraph boundaries |

## Prompt files

See [PROMPT_ARCHITECTURE.md](PROMPT_ARCHITECTURE.md). Files live in `backend/app/prompts/`.

## Validation and retry

See [PROCESSING_STATES.md](PROCESSING_STATES.md) and [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md). Invalid LLM output is never silently accepted.
