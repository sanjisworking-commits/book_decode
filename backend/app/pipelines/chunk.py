"""Phase 2: structure-first chapter chunking for later LLM extraction."""

from __future__ import annotations

from typing import Any


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) for MVP chunk budgeting."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _block_tokens(block: dict[str, Any]) -> int:
    return estimate_tokens(block.get("text") or "")


def _section_boundaries(blocks: list[dict[str, Any]]) -> list[int]:
    """Indices where a new section/heading starts."""
    bounds = [0]
    for i, block in enumerate(blocks):
        if i == 0:
            continue
        if block.get("block_type") == "heading":
            bounds.append(i)
        else:
            # Section change via section_id
            prev = blocks[i - 1].get("section_id")
            cur = block.get("section_id")
            if cur and prev and cur != prev and i not in bounds:
                bounds.append(i)
    return bounds


def chunk_source_chapter(
    source_chapter: dict[str, Any],
    *,
    token_limit: int = 6000,
    overlap_blocks: int = 2,
) -> dict[str, Any]:
    """Create a chunk plan for one normalised chapter.

    Priority: whole chapter → heading/section groups → paragraph packs →
    hard token-limit splits. Chunks carry allow-listed block IDs only
    (no new content IDs).
    """
    chapter_id = source_chapter["chapter_id"]
    blocks: list[dict[str, Any]] = list(source_chapter.get("source_blocks") or [])
    total_tokens = sum(_block_tokens(b) for b in blocks)

    base = {
        "schema_version": "1.0",
        "book_id": source_chapter["book_id"],
        "chapter_id": chapter_id,
        "token_limit": token_limit,
        "overlap_blocks": overlap_blocks,
        "total_blocks": len(blocks),
        "total_tokens_estimate": total_tokens,
    }

    if not blocks:
        return {**base, "chunks": [], "strategy": "empty"}

    if total_tokens <= token_limit:
        chunk = _make_chunk(chapter_id, 0, blocks, strategy="single_chapter")
        return {**base, "chunks": [chunk], "strategy": "single_chapter"}

    # Try section/heading groups first
    bounds = _section_boundaries(blocks)
    section_slices: list[list[dict[str, Any]]] = []
    for i, start in enumerate(bounds):
        end = bounds[i + 1] if i + 1 < len(bounds) else len(blocks)
        section_slices.append(blocks[start:end])

    # If every section fits, emit one chunk per section (with overlap)
    if section_slices and all(sum(_block_tokens(b) for b in s) <= token_limit for s in section_slices):
        chunks = _with_overlap(chapter_id, section_slices, overlap_blocks, strategy="section")
        return {**base, "chunks": chunks, "strategy": "section"}

    # Otherwise pack paragraphs with token budget; split sections that overflow
    packed: list[list[dict[str, Any]]] = []
    for section in section_slices or [blocks]:
        packed.extend(_pack_by_token_limit(section, token_limit))

    chunks = _with_overlap(chapter_id, packed, overlap_blocks, strategy="token_fallback")
    return {**base, "chunks": chunks, "strategy": "token_fallback"}


def _pack_by_token_limit(
    blocks: list[dict[str, Any]], token_limit: int
) -> list[list[dict[str, Any]]]:
    packs: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_tokens = 0
    for block in blocks:
        t = _block_tokens(block)
        # Single oversized block still becomes its own pack
        if t > token_limit and not current:
            packs.append([block])
            continue
        if current and current_tokens + t > token_limit:
            packs.append(current)
            current = [block]
            current_tokens = t
        else:
            current.append(block)
            current_tokens += t
    if current:
        packs.append(current)
    return packs


def _with_overlap(
    chapter_id: str,
    slices: list[list[dict[str, Any]]],
    overlap_blocks: int,
    *,
    strategy: str,
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    prev_tail: list[dict[str, Any]] = []
    for idx, slice_blocks in enumerate(slices):
        merged = list(prev_tail) + list(slice_blocks)
        # Deduplicate by block_id while preserving order
        seen: set[str] = set()
        ordered: list[dict[str, Any]] = []
        for b in merged:
            bid = b["block_id"]
            if bid in seen:
                continue
            seen.add(bid)
            ordered.append(b)
        chunks.append(_make_chunk(chapter_id, idx, ordered, strategy=strategy))
        if overlap_blocks > 0:
            prev_tail = slice_blocks[-overlap_blocks:]
        else:
            prev_tail = []
    return chunks


def _make_chunk(
    chapter_id: str,
    index: int,
    blocks: list[dict[str, Any]],
    *,
    strategy: str,
) -> dict[str, Any]:
    block_ids = [b["block_id"] for b in blocks]
    text = "\n\n".join(b.get("text") or "" for b in blocks)
    return {
        "chunk_id": f"{chapter_id}.chunk{index:02d}",
        "order_index": index,
        "strategy": strategy,
        "block_ids": block_ids,
        "token_estimate": estimate_tokens(text),
        "block_count": len(block_ids),
    }


def validate_chunk_allow_lists(
    source_chapter: dict[str, Any], chunk_plan: dict[str, Any]
) -> None:
    allowed = {b["block_id"] for b in source_chapter.get("source_blocks") or []}
    for chunk in chunk_plan.get("chunks") or []:
        for bid in chunk.get("block_ids") or []:
            if bid not in allowed:
                raise ValueError(f"Chunk cites unknown block_id: {bid}")
