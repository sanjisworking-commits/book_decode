# Backend

## Current phase

**Phase 4 — Chapter Argument Spine synthesis**

Pipeline runs Phase 1 (Docling + chapters) → Phase 2 (canonical `book.json` + chunks) → Phase 3 (per-chunk extraction) → Phase 4 (multi-chunk synthesis into one English spine). Spec: [`docs/CANONICAL_BOOK_SCHEMA.md`](../docs/CANONICAL_BOOK_SCHEMA.md).

Hindi-English adaptation is Phase 5.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

For offline / CI tests without an API key:

```bash
# in .env
LLM_MOCK=true
```

## LLM providers

Set `LLM_PROVIDER` to one of: `openai`, `anthropic`, `openai_compatible`.

### OpenAI

```bash
LLM_MOCK=false
LLM_PROVIDER=openai
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o
```

### Anthropic Claude

```bash
LLM_MOCK=false
LLM_PROVIDER=anthropic
LLM_API_BASE=https://api.anthropic.com
LLM_API_KEY=sk-ant-...
LLM_MODEL=claude-sonnet-4-20250514
```

If `LLM_API_BASE` / `LLM_MODEL` are left at OpenAI defaults while `LLM_PROVIDER=anthropic`, the client applies Anthropic defaults automatically.

### Any OpenAI-compatible gateway

Same Chat Completions wire protocol (Groq, Together, Azure OpenAI-compat, Ollama, etc.):

```bash
LLM_MOCK=false
LLM_PROVIDER=openai_compatible
LLM_API_BASE=https://api.groq.com/openai/v1
LLM_API_KEY=...
LLM_MODEL=llama-3.3-70b-versatile
```

## Run API

```bash
source .venv/bin/activate
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health: `GET /health` → `{"phase":"4"}`

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/books/upload` | Upload EPUB |
| POST | `/books/{id}/process` | Start Phase 1–4 pipeline (background) |
| GET | `/books/{id}/status` | Real processing status |
| GET | `/books/{id}` | Book metadata |
| GET | `/books/{id}/chapters` | Detected chapter list |
| GET | `/books/{id}/canonical` | Canonical hierarchical `book.json` |
| GET | `/books/{id}/chapters/{cid}/source` | Normalised source chapter JSON |
| GET | `/books/{id}/chapters/{cid}/chunks` | Chunk plan for extraction |
| GET | `/books/{id}/chapters/{cid}/spine` | English chapter spine (post-synthesis) |
| DELETE | `/books/{id}` | Delete book artefacts |
| POST | `/demo/reset` | Clear local demo data |

## Success state

After process completes with mock or live LLM:

- `processing_status` = `constructing_spines`
- `data/books/{book_id}/book.json` (canonical schema 2.0)
- Per chapter:
  - `*.source.json` / `*.chunks.json`
  - `*.spine.partial.{chunk_id}.json`
  - `*.spine.en.json` — synthesised English chapter spine
  - `*.spine.candidate.json` — same English spine (API reads EN first)

Block ID format: `{book_id}.{chapter_id}.{section_id}.blockNNN`

## Tests

```bash
source .venv/bin/activate
cd backend
pytest -q
```

Tests force `LLM_MOCK=true`.
