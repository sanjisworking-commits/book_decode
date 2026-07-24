# Book Decode — Frontend (Phase 7)

Vite + React + TypeScript UI for According to Logic / Book Decode.

## Run

```bash
# terminal 1 — API (from repo root; use a free port)
cd backend && uvicorn app.main:app --reload --port 8003

# terminal 2 — UI (proxy defaults to :8003 via .env.development)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 — Vite proxies `/books`, `/demo`, `/health` to the API
(default proxy target **`http://127.0.0.1:8003`**, set in `frontend/.env.development`).

If the upload screen spins forever, the proxy port does not match uvicorn. Align them:

```bash
# API
cd backend && uvicorn app.main:app --reload --port 8003

# UI (restart after changing .env.development)
cd frontend && npm run dev
curl -s http://localhost:5173/health   # should return JSON via proxy
```

### Real Anthropic vs mock

Placeholders like `Mock extraction placeholder` mean the API is in **mock** mode.

1. In repo-root `.env` set (only one of each key; **last** duplicate wins):

```bash
LLM_MOCK=false
LLM_PROVIDER=anthropic
LLM_API_BASE=https://api.anthropic.com
LLM_API_KEY=sk-ant-...
LLM_MODEL=claude-sonnet-4-6
```

2. Start backend **without** `LLM_MOCK=true` on the command line (shell env overrides `.env`).

3. Confirm: `curl -s http://127.0.0.1:8003/health` → `"llm_mock": false`, `"llm_provider": "anthropic"`, `"llm_api_key_configured": true`.

4. Delete the book in the UI and re-upload so spines are regenerated.

## Design source

Visual reference: Claude handoff (`Book Decode.dc.html`). Tokens live in `src/styles/tokens.css`. Do **not** port the prototype `support.js`.

Spine layouts: **1a** desktop (node canvas + detail), **1b** mobile (threaded list). No hardcoded Argument Spine content — nodes come from `GET /books/{id}/chapters/{cid}/spine`.

## Scripts

| Command | Purpose |
|---------|---------|
| `npm run dev` | Dev server |
| `npm run build` | Production build |
| `npm test` | Vitest unit/component tests |
| `npm run lint:no-hardcoded-spines` | Guard against hardcoded spine claims |
