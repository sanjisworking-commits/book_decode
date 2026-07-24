# Prompt: Hindi-English Adaptation

**Status:** Phase 5 — full instruction text  
**Version:** 5.0.0  
**File:** `hinglish_adaptation.md`  
**Used by:** language-adaptation pass after English spine synthesis (`pipelines.adapt`)

## Purpose

Adapt a completed **English** Argument Spine into natural Hindi-English while preserving logical meaning, structure, and all source grounding.

## Inputs (runtime)

You receive a JSON payload after the marker `===ENGLISH_SPINE_JSON===` containing:

- The full English Argument Spine object (`nodes` with `statement_en` / `explanation_en`)
- Style constraints summarised below

## Style constraints

- Simple Hindi sentence structure mixed with familiar English terms (Hinglish)
- **Retain** important English technical / philosophical / political / academic terms (do not force obscure Hindi replacements)
- Natural spoken register — not textbook Sanskritised Hindi
- Not a word-for-word literal translation

## Required behaviour

1. Adapt **only** the Argument Spine fields — do not translate source-block text for storage.
2. Preserve exact structure:
   - same `id`, `node_type`, `order`, `prev_id`, `next_id`
   - same `source_status`, `source_block_ids`, `confidence`, `warnings`
   - same `statement_en` and `explanation_en` (do not rewrite English)
3. Fill `statement_hinglish` and `explanation_hinglish` for every node that has English text (use `null` only when the English field is null).
4. Do **not** change logical claims, add new claims, or drop nodes.
5. Do **not** invent or alter source-block IDs.
6. Return **JSON only** — one Argument Spine object.
7. Set `language_modes` to `["en", "hinglish"]`.

## Outputs

Bilingual Argument Spine JSON matching the Argument Spine schema, with hinglish fields populated and English fields unchanged.

## Non-goals

- Full-chapter or EPUB Hindi translation
- IndicTrans2 as the adaptation engine (optional comparison only, elsewhere)
- Changing confidence scores or source grounding
- Re-running argument extraction
