# API Specification

Base URL (local MVP): `http://localhost:8000`

All endpoints are planned for FastAPI. This document is the contract only—**not implemented in Phase 0**.

## Conventions

- JSON request/response bodies unless multipart upload
- Errors: `{ "error": { "code": string, "message": string, "details": object | null } }`
- IDs are path-safe strings (`book_id`, `chapter_id`)
- Status values align with [PROCESSING_STATES.md](PROCESSING_STATES.md)

## Endpoints

### Upload EPUB

`POST /books/upload`

- Content-Type: `multipart/form-data`
- Field: `file` (`.epub`)
- Validates type, size, basic EPUB integrity, rejects DRM when detectable
- Response `201`: book metadata (status `uploaded`)

### Start processing

`POST /books/{book_id}/process`

- Starts background pipeline if status allows
- Response `202`: job accepted + current status payload
- `409` if already processing; `404` if unknown book

### Get processing status

`GET /books/{book_id}/status`

Returns real progress:

```json
{
  "book_id": "string",
  "processing_status": "analysing_chapters",
  "current_stage": "analysing_chapters",
  "stage_index": 5,
  "stages_total": 10,
  "chapter_count": 12,
  "processed_chapter_count": 4,
  "failed_chapter_count": 0,
  "current_chapter_id": "ch05",
  "chapters": [
    {
      "chapter_id": "ch01",
      "title": "string",
      "status": "completed",
      "retry_count": 0,
      "error": null
    }
  ],
  "partial_success": false,
  "error": null
}
```

### Get book metadata

`GET /books/{book_id}`

Returns book metadata document ([DATA_SCHEMA.md](DATA_SCHEMA.md)).

### Get chapter list

`GET /books/{book_id}/chapters`

Returns ordered chapters with titles and per-chapter processing status (no full spine bodies).

### Get chapter Argument Spine

`GET /books/{book_id}/chapters/{chapter_id}/spine`

- Returns bilingual Argument Spine JSON
- `404` if missing; `409` if chapter not ready
- Optional query: `?lang=en|hinglish` may filter presentation fields later; MVP can return full bilingual document and let the client toggle

### Retry failed chapter

`POST /books/{book_id}/chapters/{chapter_id}/retry`

- Re-queues a failed (or optionally completed) chapter
- Respects max retry policy unless `force=true` (prototype flag)
- Response `202`

### Delete uploaded book

`DELETE /books/{book_id}`

- Deletes EPUB, processed artefacts, spines, and DB rows
- Response `204`

### Reset demo

`POST /demo/reset`

- Clears prototype data store for clean demonstration
- Protected or local-only in later deployment docs
- Response `204`

## Non-goals for API (MVP)

- Auth / multi-tenant users
- Streaming token output of LLM to client
- Websocket required (polling status is enough; websockets optional later)
- Public catalogue listing of all books beyond local demo needs

## Related

- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)
- [PROCESSING_STATES.md](PROCESSING_STATES.md)
