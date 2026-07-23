# Testing Strategy

## Goals

Prove the EPUB → Argument Spine → bilingual UI path works without silently accepting invalid AI output or breaking source integrity.

## Test layers

### 1. File validation tests

- Accept valid EPUB fixtures
- Reject wrong MIME/extension
- Reject oversize files
- Reject corrupt archives
- Detect/reject encrypted DRM when detectable
- Missing metadata does not crash (fallback titles)

### 2. Structural / normalisation tests

- Chapters detected from Docling-like input
- Stable block IDs assigned and unique
- Order indices monotonic
- Empty/malformed chapters marked failed cleanly
- Reference fixture [`../sample-data/reference/a_thousand_brains_clean.json`](../sample-data/reference/a_thousand_brains_clean.json) usable for structure tests (not spine content)

### 3. Chunking tests

- Small chapter → single chunk
- Large chapter → heading/section splits before token fallback
- Overlap preserves block ID continuity
- Chunk allow-lists are subsets of chapter blocks

### 4. Schema validation tests

- Valid spine passes
- Missing required fields fail
- Invalid enums fail
- Duplicate node IDs fail
- Reasoning order inconsistencies fail
- EN / Hindi-English node alignment checks

### 5. Source-reference validation tests

- Unknown block IDs fail
- Cross-chapter IDs fail
- Repair path removes invalid IDs without inventing new ones

### 6. API / status tests

- Upload → process → status reflects real stages
- Chapter failure increments failed count
- Retry endpoint transitions chapter to `retrying`
- Partial success book status
- Delete removes artefacts

### 7. Frontend tests

- Renders spine from API mocks (no hardcoded book arguments in app source)
- Language toggle switches fields
- Source preview resolves IDs from mock source chapter
- Processing UI binds to status payload fields
- Empty / error / loading states

### 8. End-to-end (Phase 8)

- One real EPUB through pipeline with LLM credentials in secure env
- Assert chapters ≥ 1, spines validate, UI walkthrough of Book Map → chapter → toggle → source

## What not to test with fabricated narrative fixtures

Do not commit fake Argument Spine “gold” claims for copyrighted books as if they were ground truth. Prefer schema fixtures with **neutral placeholder strings** (e.g. `"statement_en": "PLACEHOLDER"`) for validator unit tests.

## Tooling (planned)

| Area | Tool |
|------|------|
| Backend unit/integration | `pytest` |
| Schema | `jsonschema` |
| Frontend | Vitest + React Testing Library |
| E2E | Playwright (Phase 8) |

## CI (later)

Lint + unit tests on PR; E2E optional/manual for LLM-cost reasons until a recorded fixture mode exists.
