# Backend

## Current phase

**Phase 6 — Validation and storage** (API ready for Phase 7 UI)

Pipeline runs Phase 1 → 5, then Phase 6 validates schema + source refs (with repair retries), persists only valid spines, and sets book status to `completed` or `completed_with_errors`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

Offline / CI:

```bash
LLM_MOCK=true
```

Retry controls (`.env`):

```bash
MAX_CHAPTER_RETRIES=3
RETRY_BACKOFF_SECONDS=2
```

## Run API

```bash
source .venv/bin/activate
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health: `GET /health` → `{"phase":"6"}`

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/books/upload` | Upload EPUB |
| POST | `/books/{id}/process` | Start Phase 1–6 pipeline |
| GET | `/books/{id}/status` | Real processing status |
| GET | `/books/{id}/chapters/{cid}/spine` | Validated bilingual spine |
| POST | `/books/{id}/chapters/{cid}/retry` | Retry failed chapter validation (`?force=true`) |
| DELETE | `/books/{id}` | Delete book artefacts |
| POST | `/demo/reset` | Clear local demo data |

## Success state

- `processing_status` = `completed` (or `completed_with_errors` if some chapters failed)
- `current_stage` = `book_ready`
- Per successful chapter: `status=completed`, `*.spine.json` with `validation.schema_valid=true`
- Invalid spines after max repairs → `*.spine.invalid.json` and chapter `failed` (never marked completed)

## Tests

```bash
source .venv/bin/activate
cd backend
pytest -q
```
