# Backend

## Current phase

**Phase 3 — AI Argument Spine extraction**

Pipeline runs Phase 1 (Docling + chapters) → Phase 2 (normalise + chunks) → Phase 3 (English spine extraction per chunk).

Hindi-English adaptation and multi-chunk synthesis are later phases.

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

Health: `GET /health` → `{"phase":"3"}`

## Phase 3 endpoints (additions)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/books/{id}/chapters/{cid}/spine` | English spine candidate (or `needs_synthesis` manifest) |

Existing upload/process/status/source/chunks endpoints remain.

## Success state

After process completes with mock or live LLM:

- `processing_status` = `analysing_chapters`
- Per chapter:
  - `*.spine.partial.{chunk_id}.json`
  - `*.spine.candidate.json` (full English spine if single chunk; synthesis manifest if multi-chunk)

## Tests

```bash
source .venv/bin/activate
cd backend
pytest -q
```

Tests force `LLM_MOCK=true`.
