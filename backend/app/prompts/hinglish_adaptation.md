# Prompt: Hindi-English Adaptation

**Status:** Phase 5 — full instruction text  
**Version:** 6.0.0  
**File:** `hinglish_adaptation.md`  
**Used by:** language-adaptation pass after English spine synthesis (`pipelines.adapt`)

## Purpose

Adapt a completed **English** Argument Spine into natural Hindi-English while preserving logical meaning, structure, and all source grounding.

## Inputs (runtime)

You receive a JSON payload after the marker `===ENGLISH_SPINE_JSON===` containing:

- The full English Argument Spine object (`nodes` with `statement_en` / `explanation_en`)
- Style constraints summarised below

## Style & script constraints

- **Script — this is required.** Write the Hindi portions in **Devanagari script (देवनागरी)**. Do **not** romanize Hindi into Latin letters. Write `आज का`, `करके`, `क्योंकि`, `लेकिन` — **not** `aaj ka`, `karke`, `kyunki`, `lekin`.
- **Keep English terms in Latin script, inline.** Retain important English technical / philosophical / political / academic terms exactly as they are, in Roman letters (e.g. `AGI`, `single-task performance`, `benchmarks`, `reference frames`, `neocortex`). Do **not** force obscure Hindi replacements and do **not** transliterate those English terms into Devanagari.
- The result is natural **code-mixed** Hindi-English: Devanagari Hindi as the connective tissue with English terms embedded in Latin. Example:
  > `आज का AI narrow, single-task performance को optimize करके success पाता है (यह 'dedicated' path है), जो इसके impressive benchmarks को explain करता है लेकिन इसकी total inflexibility को भी।`
- Natural spoken register — not textbook Sanskritised Hindi.
- Not a word-for-word literal translation.
- Use the Devanagari full stop `।` to end Hindi sentences where natural; keep Latin punctuation around English terms.

## Required behaviour

1. Adapt **only** the Argument Spine fields — do not translate source-block text for storage.
2. Preserve exact structure:
   - same `id`, `node_type`, `order`, `prev_id`, `next_id`
   - same `source_status`, `source_block_ids`, `confidence`, `warnings`
   - same `statement_en` and `explanation_en` (do not rewrite English)
3. Fill `statement_hinglish` and `explanation_hinglish` for every node that has English text (use `null` only when the English field is null). When a node has an `illustrative_example`, also fill its `title_hinglish` (from `title_en`) and `text_hinglish` (from `text_en`) using the same Devanagari script rules; leave the example's other fields unchanged.
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
