# Book Decode — Frontend (Phase 7)

Vite + React + TypeScript UI for According to Logic / Book Decode.

## Run

```bash
# terminal 1 — API (from repo root)
cd backend && LLM_MOCK=true uvicorn app.main:app --reload --port 8000

# terminal 2 — UI
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 — Vite proxies `/books`, `/demo`, `/health` to the API.

### Real Anthropic vs mock

Placeholders like `Mock extraction placeholder` mean the API is in **mock** mode.

1. In repo-root `.env` set (only one of each key; **last** duplicate wins):

```bash
LLM_MOCK=false
LLM_PROVIDER=anthropic
LLM_API_BASE=https://api.anthropic.com
LLM_API_KEY=sk-ant-...
LLM_MODEL=claude-sonnet-4-20250514
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
