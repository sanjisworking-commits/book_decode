# MVP Scope

## In scope

### Pipeline

- EPUB upload and file validation
- Docling conversion to structured JSON
- Document normalisation and chapter detection
- Stable source-block ID assignment
- Structure-aware chapter chunking
- LLM Argument Spine extraction (English first)
- Chapter-level synthesis of partial outputs
- Hindi-English adaptation of the completed Argument Spine only
- JSON Schema and source-reference validation
- Retries with backoff and failed-chapter reporting
- Persistence of book metadata and per-chapter bilingual JSON

### Product experience

- Landing page
- Upload EPUB
- Real processing progress (book-level and chapter-level)
- Open completed book
- Book Map
- Chapter Argument Spine view
- English / Hindi-English language toggle
- Expandable argument nodes
- Source-reference preview
- Chapter navigation
- Error, empty, loading, partial-success, and completion states

### Platform

- Python / FastAPI backend
- React + TypeScript + Vite frontend
- Local filesystem + SQLite storage
- Versioned prompts under `backend/app/prompts/`
- Shared JSON Schemas under `schemas/`

## Explicitly out of scope (MVP)

Do not implement:

- PDF input
- OCR
- Audiobooks
- Multiple upload formats beyond EPUB
- Public book library
- Payments or subscriptions
- Community comments
- Publisher moderation
- Social sharing
- Multi-user collaboration
- Native mobile application
- Full spaced-repetition system
- Voice interaction
- Automatic external research
- Cross-book knowledge graph

These items belong in [Future Scope](FUTURE_SCOPE.md).

## Optional extensions (document only unless trivial)

Reflections, active recall, and notes may be documented as future extensions. They must not distract from the EPUB → Argument Spine MVP.

## Content policy for this repository

- No hardcoded chapter Argument Spines in the frontend
- No fabricated sample claims, assumptions, counters, or chapter decodes in planning docs
- Reference EPUB-derived JSON (if present under `sample-data/`) is structural only

## Acceptance pointer

MVP acceptance criteria: [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md).
