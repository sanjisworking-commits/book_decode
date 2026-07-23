# Phase 1 backend

## Scope

EPUB upload, validation, Docling conversion, chapter detection, and status APIs.

Argument Spine generation is **not** included (Phases 3–5).

## Setup

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pip install 'docling>=2.0.0'   # required for real EPUB conversion
cp .env.example .env
```

## Run API

```bash
source .venv/bin/activate
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check: `GET http://localhost:8000/health`

## Phase 1 endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/books/upload` | Upload EPUB |
| POST | `/books/{id}/process` | Start Phase 1 ingest (background) |
| GET | `/books/{id}/status` | Real processing status |
| GET | `/books/{id}` | Book metadata |
| GET | `/books/{id}/chapters` | Detected chapter list |
| DELETE | `/books/{id}` | Delete book artefacts |
| POST | `/demo/reset` | Clear local demo data |

## Tests

```bash
source .venv/bin/activate
cd backend
pytest -q
```

The API integration test runs Docling on a tiny synthetic EPUB and may take up to ~2 minutes on first model/cache warm-up.

## Phase 1 success state

After a successful process job:

- `processing_status` = `detecting_chapters`
- `chapter_count` > 0
- `chapters` listed as `pending`
- Docling JSON at `data/processed/{book_id}/docling.json`
- Chapter preview at `data/processed/{book_id}/chapters_preview.json`

Later phases continue from this point (normalisation, AI spine, etc.).
