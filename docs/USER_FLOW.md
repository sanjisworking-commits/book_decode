# User Flow

## Primary MVP flow

```text
Landing page
→ Upload EPUB
→ Validate EPUB
→ Process book
→ Show processing progress
→ Detect chapters
→ Generate Argument Spines
→ Open completed book
→ View Book Map
→ Select chapter
→ View Argument Spine
→ Switch between English and Hindi-English
→ Expand individual argument nodes
→ Inspect source references
→ Navigate between chapters
```

## Screen-by-screen intent

### 1. Landing

Communicate the product: EPUB in → Argument Spine out. Single primary CTA to upload. No fake book library.

### 2. Upload

User selects an `.epub` file. Client and server validate type and size. Reject corrupt, encrypted/DRM, or oversize files with clear errors.

### 3. Processing

Show **real** pipeline progress, not cosmetic percentages only. Reflect:

- Current processing stage (see [PROCESSING_STATES.md](PROCESSING_STATES.md))
- Chapters completed / total
- Current chapter under analysis (when applicable)
- Failed chapters and retry state
- Partial success vs full completion

### 4. Book ready

Transition to the decoded book. Offer Book Map as the primary entry.

### 5. Book Map

Chapter list (or map) for the book. Each chapter shows status (ready / failed / pending). Selecting a ready chapter opens its Argument Spine.

### 6. Chapter Argument Spine

Render the twelve Argument Spine elements as an interactive structure. Support:

- Expand / collapse nodes
- English ↔ Hindi-English toggle (same node structure)
- Source-block reference inspection / preview
- Previous / next chapter navigation

### 7. Error and recovery

- File validation failures stay on upload with message
- Chapter failures surface on Book Map with retry affordance
- Book-level failure explains cause and allows reprocess or delete

## Non-flows (MVP)

- In-app full ebook reading mode
- Chat-with-the-book
- Browse a public catalogue
- Account signup / paywall

## State coverage required

| State | Where |
|-------|--------|
| Empty | Landing / no books |
| Loading | Upload + processing |
| Error | Validation, chapter, book |
| Partial success | Some chapters ready, some failed |
| Complete | All chapters decoded |
| Retrying | Automatic or manual chapter retry |

Design detail for Claude Design: [DESIGN_BRIEF_FOR_CLAUDE.md](DESIGN_BRIEF_FOR_CLAUDE.md).
