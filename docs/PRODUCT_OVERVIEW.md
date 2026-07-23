# Product Overview

## Product name

**According to Logic — Book Decode**

## Problem

Serious non-fiction is hard to hold as an argument. Readers finish chapters with a vague sense of “what happened” but without a clear, inspectable chain of:

- the question the chapter answers
- the author’s central claim
- the reasoning steps
- the evidence
- hidden assumptions
- tensions and fair counters

Generic summarisers flatten argument structure. Ebook readers preserve text but do not decode logic. Neither produces a bilingual, source-grounded argument map tied to stable passages in the original EPUB.

## Product objective

Build a functional prototype where a user uploads an EPUB and receives a structured, source-grounded **Argument Spine** for each chapter, available in:

1. **English**
2. **Hindi-English** — simple Hindi sentence structure retaining important English technical, philosophical, political, and academic terms

Defining pipeline:

```text
EPUB → chapter extraction → AI Argument Spine → English and Hindi-English decode → interactive book interface
```

## What this product is

- A chapter-level argument decoder
- A source-referenced reasoning map
- A bilingual (English / Hindi-English) exploration interface for decoded books

## What this product is not

- An ebook reader
- A general summariser
- A chatbot
- A book marketplace
- A public library or social reading network

## Target user

Primary: students, researchers, and serious readers who need to understand how a book argues—especially across language preference for English and natural Hindi-English—without losing contact with the source text.

Secondary: educators and facilitators who want a chapter-level argument map before teaching or discussion.

## Core value

Every Argument Spine element is tied to **stable source-block IDs** in the original chapter text, and every element distinguishes:

| Status | Meaning |
|--------|---------|
| Explicit author statement | Closely tracks wording or direct claim in the text |
| Author paraphrase | Faithful restatement of what the author says |
| AI inference | Analytical reconstruction not stated outright |
| External counter-perspective | Fair opposing position, clearly marked as external |

## Role separation

| Role | Responsibility |
|------|----------------|
| **AI pipeline** | Generate Argument Spine content from uploaded EPUB chapters |
| **Cursor** | Architecture, ingestion, orchestration, validation, storage, API, frontend implementation |
| **Claude Design** | Visual design system, screens, interaction states, Argument Spine visualisation |
| **GitHub** | Single source of truth for code, schemas, prompts, and docs |

Cursor must not invent book claims, assumptions, or counters by hand. Claude Design must not redefine product scope. Content is produced dynamically by the AI pipeline from user-uploaded EPUBs.

## Success for the MVP

A demonstrable end-to-end path: upload EPUB → real processing progress → Book Map → chapter Argument Spine → English / Hindi-English toggle → source-block inspection.

See also:

- [MVP Scope](MVP_SCOPE.md)
- [User Flow](USER_FLOW.md)
- [System Architecture](SYSTEM_ARCHITECTURE.md)
- [Argument Spine Specification](ARGUMENT_SPINE_SPECIFICATION.md)
