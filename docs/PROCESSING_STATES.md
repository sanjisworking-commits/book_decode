# Processing States

The functional prototype must report **real** pipeline progress. Do not rely only on simulated frontend percentages.

## UI stages (book-level)

Ordered stages shown to the user:

1. Uploading EPUB
2. Reading book structure
3. Detecting chapters
4. Preparing chapter blocks
5. Analysing chapters
6. Constructing Argument Spines
7. Creating Hindi-English versions
8. Validating output
9. Saving decoded book
10. Book ready

Map these to internal pipeline stages one-to-one where possible. Stage 5–8 may advance per chapter while the book remains in a global “processing” status.

## Book-level statuses

| Status | Meaning |
|--------|---------|
| `uploaded` | File stored; not started |
| `queued` | Process requested |
| `uploading` | Transfer in progress (client/server) |
| `reading_structure` | Docling / structure read |
| `detecting_chapters` | Chapter detection |
| `preparing_blocks` | Normalisation + block IDs |
| `analysing_chapters` | LLM extraction running |
| `constructing_spines` | Synthesis |
| `creating_hinglish` | Language adaptation |
| `validating` | Schema + source checks |
| `saving` | Persist artefacts |
| `completed` | All required chapters succeeded |
| `completed_with_errors` | Partial success |
| `failed` | Book-level failure (ingest/structure) |
| `cancelled` | Optional later |

## Chapter-level statuses

| Status | Meaning |
|--------|---------|
| `pending` | Not started |
| `chunking` | Preparing chunks |
| `extracting` | Partial extraction |
| `synthesising` | Combining partials |
| `adapting_hinglish` | Hindi-English pass |
| `validating` | Checks running |
| `retrying` | Automatic or manual retry |
| `completed` | Spine saved |
| `failed` | Exhausted retries or hard error |

## Progress payload fields

Status API must expose:

- Book-level processing state / current stage
- Chapter-level processing state (list)
- Number of completed chapters / total
- Current processing stage
- Failed chapter state
- Automatic retry state (`retry_count`, `retrying`)
- Partial-success flag
- Final completion state

## Retry strategy

| Layer | Behaviour |
|-------|-----------|
| Schema-repair retry | Call `output_repair` prompt; re-validate |
| Source-reference repair | Call `source_validation` prompt; re-validate |
| Chapter retry | Re-run extract→…→persist for that chapter |
| Backoff | Exponential (`RETRY_BACKOFF_SECONDS` base) |
| Max retries | `MAX_CHAPTER_RETRIES` (default 3) |
| Failed-chapter reporting | Visible on Book Map + status API |
| Manual reprocess | `POST .../retry` |

Never silently accept invalid LLM output.

## Partial success

If some chapters complete and others fail after max retries:

- Book status = `completed_with_errors`
- Ready chapters are explorable
- Failed chapters show error + retry

## Completion

Book status = `completed` only when every detected content chapter has a validated bilingual spine (front matter–only sections may be excluded by chapter detector rules documented in implementation).
