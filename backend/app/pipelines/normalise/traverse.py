"""Single-pass ordered traversal of Docling document dict."""

from __future__ import annotations

from typing import Any, Iterator

from app.pipelines.normalise.types import StreamItem


def iter_docling_stream(docling_json: dict[str, Any]) -> Iterator[StreamItem]:
    """Yield content items in reading order (prefer body refs, else arrays)."""
    texts = docling_json.get("texts") or []
    tables = docling_json.get("tables") or []
    pictures = docling_json.get("pictures") or []

    by_ref: dict[str, StreamItem] = {}
    for i, item in enumerate(texts):
        if isinstance(item, dict):
            ref = item.get("self_ref") or f"#/texts/{i}"
            by_ref[ref] = {
                "kind": "text",
                "index": i,
                "source_ref": ref,
                "payload": item,
            }
    for i, item in enumerate(tables):
        if isinstance(item, dict):
            ref = item.get("self_ref") or f"#/tables/{i}"
            by_ref[ref] = {
                "kind": "table",
                "index": i,
                "source_ref": ref,
                "payload": item,
            }
    for i, item in enumerate(pictures):
        if isinstance(item, dict):
            ref = item.get("self_ref") or f"#/pictures/{i}"
            by_ref[ref] = {
                "kind": "picture",
                "index": i,
                "source_ref": ref,
                "payload": item,
            }

    body = docling_json.get("body")
    emitted: set[str] = set()
    if isinstance(body, dict):
        for ref in _walk_refs(body, docling_json):
            item = by_ref.get(ref)
            if item and ref not in emitted:
                emitted.add(ref)
                yield item

    # Fallback / remainder: preserve array order for anything not reached via body
    for collection_name, kind in (("texts", "text"), ("tables", "table"), ("pictures", "picture")):
        for i, payload in enumerate(docling_json.get(collection_name) or []):
            if not isinstance(payload, dict):
                continue
            ref = payload.get("self_ref") or f"#/{collection_name}/{i}"
            if ref in emitted:
                continue
            emitted.add(ref)
            yield {
                "kind": kind,
                "index": i,
                "source_ref": ref,
                "payload": payload,
            }


def _walk_refs(node: dict[str, Any], doc: dict[str, Any]) -> Iterator[str]:
    """Depth-first walk of Docling body/group children `$ref`s."""
    children = node.get("children") or []
    for child in children:
        ref = None
        if isinstance(child, dict):
            ref = child.get("$ref") or child.get("self_ref")
        elif isinstance(child, str):
            ref = child
        if not ref:
            continue
        yield ref
        resolved = _resolve_ref(doc, ref)
        if isinstance(resolved, dict) and resolved.get("children"):
            yield from _walk_refs(resolved, doc)


def _resolve_ref(doc: dict[str, Any], ref: str) -> Any:
    # refs like #/texts/3 or #/groups/0
    if not ref.startswith("#/"):
        return None
    parts = ref[2:].split("/")
    cur: Any = doc
    for part in parts:
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur
