# Prompt: Hindi-English Adaptation

**Status:** Phase 0 stub — responsibilities and IO contract only. Full instruction text refined in Phase 5.  
**File:** `hinglish_adaptation.md`  
**Used by:** language-adaptation pass after validated English spine

## Purpose

Adapt a completed English Argument Spine into natural Hindi-English while preserving logical meaning and structure.

## Inputs (runtime)

- Validated English Argument Spine JSON
- Style constraints: simple Hindi sentence structure; retain important English technical/philosophical/political/academic terms

## Required behaviour

- Adapt only the Argument Spine (not the full chapter text)
- Preserve field structure and node IDs / types / order / source fields
- Fill `statement_hinglish` and `explanation_hinglish`
- Avoid literal word-for-word translation
- Avoid unnecessarily formal or Sanskritised Hindi
- Avoid replacing familiar English concepts with obscure Hindi equivalents
- Do not change logical claims, confidence, or source-block IDs
- JSON-only; same schema

## Outputs

- Bilingual Argument Spine JSON (`language_modes` includes `en` and `hinglish`)

## Non-goals

- IndicTrans2 as reasoning engine (optional comparison only, elsewhere)
- Translating source blocks themselves for storage
