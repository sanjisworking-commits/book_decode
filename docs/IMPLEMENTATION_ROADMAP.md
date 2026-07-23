# Implementation Roadmap

Phases below are sequential unless noted. **Phase 0 is documentation and scaffold only** (this repository state). Application code begins at Phase 1.

---

## Phase 0 — Planning and repository setup

| | |
|--|--|
| **Goal** | Docs, architecture, schemas, prompts stubs, env decisions, empty scaffold |
| **Inputs** | Product brief; optional reference JSON under `sample-data/reference/` |
| **Outputs** | `docs/*`, `schemas/*`, `backend/app/prompts/*`, README, `.env.example`, folder tree |
| **Main tasks** | Write planning docs; define schemas; define prompt responsibilities; choose MVP stack |
| **Dependencies** | None |
| **Tests** | Doc completeness review; schema files parse as JSON Schema |
| **Completion criteria** | All listed docs present; schemas validate structurally; no app runtime required |
| **Risks** | Over-scoping docs into implementation; fabricating sample spines |

---

## Phase 1 — EPUB ingestion

| | |
|--|--|
| **Goal** | Upload, Docling conversion, metadata extraction, chapter detection |
| **Inputs** | EPUB file |
| **Outputs** | Stored EPUB; Docling JSON; preliminary chapter list; book metadata row |
| **Main tasks** | FastAPI upload endpoint; file validation; Docling integration; chapter detector heuristics |
| **Dependencies** | Phase 0 schemas/docs |
| **Tests** | File validation; Docling smoke; chapter count > 0 on sample EPUB |
| **Completion criteria** | Upload + process start produces detected chapters in status API |
| **Risks** | Docling EPUB edge cases; DRM; weird TOC structures |

---

## Phase 2 — Normalisation and chunking

| | |
|--|--|
| **Goal** | Stable block IDs, chapter separation, logical chunks |
| **Inputs** | Docling / cleaned structural JSON |
| **Outputs** | `*.source.json` per chapter; chunk plans |
| **Main tasks** | Noise removal; ID assignment; structure-first chunker; token fallback |
| **Dependencies** | Phase 1 |
| **Tests** | ID uniqueness; chunk allow-lists; small vs large chapter behaviour; fixture from `sample-data/reference/` |
| **Completion criteria** | Every content chapter has ordered source blocks with stable IDs |
| **Risks** | Unstable IDs if re-run mid-job; oversplitting |

---

## Phase 3 — AI extraction

| | |
|--|--|
| **Goal** | Argument Spine extraction with schema-constrained JSON and source references |
| **Inputs** | Chapter or chunk text + allow-listed block IDs |
| **Outputs** | Partial or full English spine JSON candidates |
| **Main tasks** | Wire `argument_spine_extraction` prompt; LLM client; JSON parse |
| **Dependencies** | Phase 2; LLM credentials |
| **Tests** | Mocked LLM returns; schema validation on fixtures |
| **Completion criteria** | Extraction produces schema-validatable English JSON for a chapter/chunk |
| **Risks** | Hallucinated claims; missing citations; cost/latency |

---

## Phase 4 — Chapter synthesis

| | |
|--|--|
| **Goal** | Combine partial extractions into one chapter Argument Spine |
| **Inputs** | Partial spines |
| **Outputs** | Single English chapter spine |
| **Main tasks** | `argument_spine_synthesis` prompt; dedupe; conflict handling |
| **Dependencies** | Phase 3 |
| **Tests** | Duplicate removal; no new claims introduced in unit tests with fixtures |
| **Completion criteria** | Multi-chunk chapters yield one coherent English spine |
| **Risks** | Over-aggregation; dropping minority but valid interpretations |

---

## Phase 5 — Hindi-English adaptation

| | |
|--|--|
| **Goal** | Bilingual fields aligned to English spine |
| **Inputs** | Validated English spine |
| **Outputs** | Spine with `statement_hinglish` / `explanation_hinglish` |
| **Main tasks** | `hinglish_adaptation` prompt; alignment check; optional IndicTrans2 comparison flag |
| **Dependencies** | Phase 4 (or single-pass Phase 3 when no chunking) |
| **Tests** | Same node IDs/types; no ID drops |
| **Completion criteria** | Stored bilingual spine for completed chapters |
| **Risks** | Over-translation of technical terms; meaning drift |

---

## Phase 6 — Validation and storage

| | |
|--|--|
| **Goal** | Schema + source validation, retries, persistence, status tracking |
| **Inputs** | Candidate spines |
| **Outputs** | Persisted spines; accurate status; failed chapters reported |
| **Main tasks** | Validators; repair prompts; SQLite + filesystem persistence; retry/backoff |
| **Dependencies** | Phases 3–5 |
| **Tests** | Fail-closed invalid output; retry limits; partial success |
| **Completion criteria** | Status API matches real job state; invalid output never saved as success |
| **Risks** | Infinite repair loops; inconsistent FS/DB state |

---

## Phase 7 — Frontend implementation

| | |
|--|--|
| **Goal** | Implement Claude Design output; connect APIs |
| **Inputs** | Approved design; live/mock API |
| **Outputs** | Landing, upload, processing, Book Map, spine view, toggle, source preview |
| **Main tasks** | Vite React app; API client; state wiring; responsive UI |
| **Dependencies** | Phase 6 API; Claude Design handoff |
| **Tests** | Component tests; no hardcoded spines in `src/` |
| **Completion criteria** | Full MVP user flow against backend |
| **Risks** | Design lag; treating placeholders as content |

---

## Phase 8 — Testing and deployment

| | |
|--|--|
| **Goal** | E2E verification, docs polish, deploy, demonstration |
| **Inputs** | Working stack |
| **Outputs** | Test report; deployment instructions; demo script |
| **Main tasks** | E2E path; harden `.env` docs; license/attribution; demo reset |
| **Dependencies** | Phases 1–7 |
| **Tests** | Playwright (or equivalent) happy path + failure path |
| **Completion criteria** | [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) satisfied |
| **Risks** | LLM flakiness in live demo; environment drift |

---

## Deliverable mapping

| Academic / project deliverable | Repository location | Milestone |
|--------------------------------|---------------------|-----------|
| Project documentation | `docs/` | Phase 0 |
| JSON Schemas | `schemas/` | Phase 0 |
| Prompt files | `backend/app/prompts/` | Phase 0 stubs; refined 3–5 |
| Backend source | `backend/` | Phases 1–6 |
| Frontend source | `frontend/` | Phase 7 |
| Tests | `backend/tests/`, `frontend/tests/` | Ongoing |
| Setup / env / license | `README.md`, `.env.example`, `LICENSE` | Phase 0 + 8 |
| Functional prototype | Running app | Phase 8 |
