"""Canonical book normalisation public API."""

from app.pipelines.normalise.adapter import (
    iter_source_chapters,
    normalise_chapter_from_docling,
    normalise_chapters_from_docling,
    normalise_from_reference_clean_json,
    to_source_chapter,
)
from app.pipelines.normalise.builder import normalise_book_from_docling
from app.pipelines.normalise.ids import make_block_id
from app.pipelines.normalise.validate import (
    CanonicalBookValidationError,
    assert_unique_block_ids,
    assert_valid_book,
    validate_canonical_book,
)

__all__ = [
    "CanonicalBookValidationError",
    "assert_unique_block_ids",
    "assert_valid_book",
    "iter_source_chapters",
    "make_block_id",
    "normalise_book_from_docling",
    "normalise_chapter_from_docling",
    "normalise_chapters_from_docling",
    "normalise_from_reference_clean_json",
    "to_source_chapter",
    "validate_canonical_book",
]
