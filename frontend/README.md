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
