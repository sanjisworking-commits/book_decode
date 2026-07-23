# Acceptance Criteria

The MVP is accepted when all of the following are true.

## Functional

1. User can upload a valid EPUB from the landing/upload flow.
2. Invalid EPUB (type, size, corrupt, detectable DRM) is rejected with a clear error.
3. Processing shows **real** stage progress and chapter completed/total counts from the backend status API.
4. System detects chapters and assigns stable source-block IDs.
5. For each successfully processed chapter, an Argument Spine exists covering the twelve required element types.
6. Every substantive spine node distinguishes source status (`explicit_author`, `author_paraphrase`, `ai_inference`, `external_counter` as applicable).
7. Cited source-block IDs resolve to stored original text; invalid IDs are not persisted as success.
8. Hindi-English fields exist for spine nodes after English validation; meaning is adapted, not a full-book pre-translation.
9. User can open Book Map, select a chapter, expand nodes, toggle EN ↔ Hindi-English, inspect sources, and navigate chapters.
10. Failed chapters are visible; retry works; partial success allows exploring completed chapters.
11. Frontend does not contain hardcoded Argument Spine narrative content.

## Technical

1. Backend is Python FastAPI; frontend is React + TypeScript + Vite.
2. Prompts live as versioned files under `backend/app/prompts/`.
3. Stored documents validate against `schemas/*.schema.json`.
4. Storage uses filesystem artefacts + SQLite job/metadata (MVP).
5. README documents setup, env vars, and doc navigation.
6. Out-of-scope items in [MVP_SCOPE.md](MVP_SCOPE.md) are not required for acceptance.

## Demonstration

A single demo path completes:

```text
Upload → Process → Book Map → Chapter Spine → Language toggle → Source preview
```

## Non-acceptance examples

- Cosmetic progress bar with no backend stage truth
- Summaries without Argument Spine structure
- Spines without source-block IDs
- Silently stored invalid JSON
- Hindi full-text EPUB translation as the primary pipeline
