"""Docling EPUB → structured JSON conversion."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def convert_epub_with_docling(epub_path: Path) -> dict[str, Any]:
    """Convert an EPUB to Docling document dict.

    Raises RuntimeError if Docling is unavailable or conversion fails.
    """
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:  # pragma: no cover - env dependent
        raise RuntimeError(
            "Docling is not installed. Install with: pip install 'docling>=2.0.0'"
        ) from exc

    try:
        converter = DocumentConverter()
        result = converter.convert(str(epub_path))
        payload = result.document.export_to_dict()
        if not isinstance(payload, dict):
            raise RuntimeError("Docling returned a non-dict document payload.")
        return payload
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Docling conversion failed: {exc}") from exc
