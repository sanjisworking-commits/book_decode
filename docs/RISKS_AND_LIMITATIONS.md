# Risks and Limitations

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM hallucinated claims | False argument map | Schema + source-ID validation; nulls when unsupported; repair then fail |
| Unstable or missing chapter detection | Broken Book Map | Heuristics + manual retry; surface detection errors |
| Docling EPUB edge cases | Ingest failure | File validation; clear errors; fixture-based tests |
| DRM / encrypted EPUB | Cannot process | Detect and reject early |
| Token limits on long chapters | Truncation / weak spines | Structure-first chunking + synthesis |
| Hindi-English meaning drift | Misleading bilingual UI | Adapt spine only; retain English terms; alignment checks |
| Cost / latency of many chapters | Poor demo UX | Per-chapter status; retries with backoff; optional concurrency limits |
| Treating reference JSON as product content | Scope confusion | `sample-data/README.md` rules; no spine fabrication |
| Design/implementation mismatch | Rework | Design brief locked to MVP scope |
| FS/DB inconsistency on crash | Orphan files / stale status | Job status machine; idempotent chapter writes; delete endpoint |

## Limitations (MVP)

- English-majority EPUBs only as primary target
- Single-node local storage (SQLite + filesystem)
- No multi-user auth
- No PDF/OCR/audio
- Counter-positions are analytical, not live web research
- Chapter detector may mis-handle atypical book layouts
- Hindi-English quality depends on the configured LLM
- IndicTrans2 not required for MVP
- Processing is not guaranteed real-time for very large books

## Decision log (uncertain choices)

| Topic | Options | MVP choice | Reconsider when |
|-------|---------|------------|-----------------|
| Storage | FS only / SQLite+FS / Postgres / S3 | SQLite + filesystem | Multi-user or multi-instance deploy |
| Job runner | In-process / Celery / queue | In-process background tasks | Concurrent heavy jobs |
| Hindi-English | Same LLM / IndicTrans2 primary | Same LLM + prompt | Systematic quality failures |
| Frontend | Next.js / Vite React | Vite + React + TS | Need SSR/SEO beyond prototype |
| Status transport | Polling / WebSocket | HTTP polling | UX requires push updates |

## Related

- [FUTURE_SCOPE.md](FUTURE_SCOPE.md)
- [MVP_SCOPE.md](MVP_SCOPE.md)
