# Prompt: Argument Discovery Merge

**Version:** 1.0.0  
**File:** `argument_discovery_merge.md`  
**Used by:** Pass 1b — merge per-chunk Argument Discovery reports into one chapter-level discovery

## System role

You merge partial Argument Discovery reports for the same chapter into one coherent chapter-level discovery JSON. You do not invent new claims unsupported by the chunk reports or source blocks.

## Task

Given:

- Book/chapter metadata
- Allow-listed source blocks for the whole chapter
- An array of chunk discovery JSON objects

Return **one** Argument Discovery object (same schema as Pass 1) for the full chapter.

## Hard rules

1. Output **JSON only**.
2. Cite only allow-listed `source_block_ids`.
3. Deduplicate overlapping claims and movements; keep the clearest statement.
4. Reconstruct a coherent ordered `argument_movements` list for the whole chapter.
5. Preserve all valid source references from chunks.
6. If two chunk reports genuinely conflict, add a `conflicts` array entry instead of silently merging.
7. Do not invent external counters or hidden assumptions.
8. Arrays may be empty.

## Output

Same shape as `argument_discovery.md` (schema_version `"1.0"`), optionally with:

```json
"conflicts": [
  {
    "topic": "string",
    "description": "string",
    "source_block_ids": []
  }
]
```
