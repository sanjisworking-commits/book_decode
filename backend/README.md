# Backend

## Current phase

**Phase 2 — Canonical normalisation and chunking**

Builds on Phase 1 (upload + Docling + chapter detection) by producing hierarchical `book.json` (schema 2.0), emitting compatible per-chapter `*.source.json`, and structure-first chunk plans. Spec: [`docs/CANONICAL_BOOK_SCHEMA.md`](../docs/CANONICAL_BOOK_SCHEMA.md).

Argument Spine generation is **not** included (Phases 3–5).

## Setup

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

## Run API

```bash
source .venv/bin/activate
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check: `GET http://localhost:8000/health` → `{"phase":"2"}`

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/books/upload` | Upload EPUB |
| POST | `/books/{id}/process` | Start Phase 1–2 ingest (background) |
| GET | `/books/{id}/status` | Real processing status |
| GET | `/books/{id}` | Book metadata |
| GET | `/books/{id}/chapters` | Detected chapter list |
| GET | `/books/{id}/canonical` | Canonical hierarchical `book.json` |
| GET | `/books/{id}/chapters/{cid}/source` | Normalised source chapter JSON |
| GET | `/books/{id}/chapters/{cid}/chunks` | Chunk plan for extraction |
| DELETE | `/books/{id}` | Delete book artefacts |
| POST | `/demo/reset` | Clear local demo data |

## Tests

```bash
source .venv/bin/activate
cd backend
pytest -q
```

## Phase 2 success state

After a successful process job:

- `processing_status` = `preparing_blocks`
- `current_stage` = `preparing_chapter_blocks`
- `chapter_count` > 0
- `data/books/{book_id}/book.json` (canonical schema 2.0)
- Per chapter:
  - `data/books/{book_id}/chapters/{chapter_id}.source.json`
  - `data/books/{book_id}/chapters/{chapter_id}.chunks.json`

Block ID format: `{book_id}.{chapter_id}.{section_id}.blockNNN`

Phase 3 will consume chunk allow-lists for Argument Spine extraction.
