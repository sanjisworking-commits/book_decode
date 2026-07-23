# Design Brief for Claude Design

## Purpose

This brief gives Claude Design enough product clarity to design the visual system and screens **without redefining scope**.

According to Logic — Book Decode turns an uploaded EPUB into a chapter-level **Argument Spine** (English + Hindi-English), with source-block references. It is not a reader, chatbot, marketplace, or summariser app.

Full product context: [PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md), [USER_FLOW.md](USER_FLOW.md), [MVP_SCOPE.md](MVP_SCOPE.md).

## Design ownership

| Claude Design owns | Claude Design does not own |
|--------------------|----------------------------|
| Visual design system | AI prompt wording |
| Upload UI | EPUB parsing logic |
| Processing screen | Backend architecture |
| Book Map | Inventing sample chapter arguments |
| Chapter Argument Spine visualisation | Hardcoded demo book content |
| EN / Hindi-English toggle | Pipeline implementation |
| Responsive layouts | Changing MVP scope |
| Interaction + empty/loading/error/complete states | |

Cursor will implement the approved design against the API in [API_SPECIFICATION.md](API_SPECIFICATION.md).

## Screens to design

1. **Landing** — brand-first; one composition; one CTA to upload EPUB
2. **Upload** — file picker, validation errors
3. **Processing** — real stages (not fake-only progress); chapter counters; failure/retry affordances
4. **Book ready / Book Map** — chapter navigation with per-chapter status
5. **Chapter Argument Spine** — twelve element types as interactive structure
6. **Source preview** — inspect original blocks tied to a node
7. **Global error / empty / partial-success** treatments

## Argument Spine UI requirements

- Expandable nodes for argument elements
- Clear visual distinction of `source_status` (explicit / paraphrase / inference / external counter)
- Language toggle: English ↔ Hindi-English (same structure, swapped fields)
- Source-block references accessible from nodes
- Previous / next chapter navigation
- Do not present the spine as a generic chat transcript

## Processing screen requirements

Reflect stages from [PROCESSING_STATES.md](PROCESSING_STATES.md):

1. Uploading EPUB  
2. Reading book structure  
3. Detecting chapters  
4. Preparing chapter blocks  
5. Analysing chapters  
6. Constructing Argument Spines  
7. Creating Hindi-English versions  
8. Validating output  
9. Saving decoded book  
10. Book ready  

Show completed/total chapters, current stage, failed chapters, retrying, partial success.

## Content constraint

**No invented book arguments in mockups as if they were product content.** Use clearly labelled placeholder copy (e.g. “Chapter question”, “Central claim”) or abstract wire labels. Do not write fake claims/assumptions/counters for a real book title in the design as shipping content.

## Responsive

Desktop and mobile. Argument Spine must remain readable on small screens (stacked nodes, not only wide canvases).

## Motion

Prefer 2–3 intentional motions that clarify hierarchy (e.g. stage advance, node expand, language switch)—not decorative noise.

## Handoff

Deliver design system tokens, screen specs, and component states suitable for React + TypeScript + Vite implementation.
