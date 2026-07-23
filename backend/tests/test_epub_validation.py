"""EPUB validation unit tests."""

from __future__ import annotations

import zipfile
from io import BytesIO

from app.services.epub_validation import validate_epub_bytes


def test_rejects_non_epub_extension(mini_epub_bytes: bytes) -> None:
    result = validate_epub_bytes(mini_epub_bytes, filename="book.pdf", max_size_bytes=10_000_000)
    assert result.ok is False
    assert result.error_code == "invalid_extension"


def test_rejects_empty_file() -> None:
    result = validate_epub_bytes(b"", filename="book.epub", max_size_bytes=10_000_000)
    assert result.ok is False
    assert result.error_code == "empty_file"


def test_rejects_oversized(mini_epub_bytes: bytes) -> None:
    result = validate_epub_bytes(mini_epub_bytes, filename="book.epub", max_size_bytes=10)
    assert result.ok is False
    assert result.error_code == "file_too_large"


def test_rejects_corrupt_zip() -> None:
    result = validate_epub_bytes(b"not-a-zip", filename="book.epub", max_size_bytes=10_000_000)
    assert result.ok is False
    assert result.error_code == "corrupt_epub"


def test_rejects_drm_encryption_xml(mini_epub_bytes: bytes) -> None:
    # Inject encryption.xml into a copy of the EPUB zip
    src = zipfile.ZipFile(BytesIO(mini_epub_bytes), "r")
    out = BytesIO()
    with zipfile.ZipFile(out, "w") as dst:
        for info in src.infolist():
            dst.writestr(info, src.read(info.filename))
        dst.writestr("META-INF/encryption.xml", "<encryption/>")
    src.close()
    result = validate_epub_bytes(out.getvalue(), filename="drm.epub", max_size_bytes=10_000_000)
    assert result.ok is False
    assert result.error_code == "drm_protected"


def test_accepts_valid_epub(mini_epub_bytes: bytes) -> None:
    result = validate_epub_bytes(mini_epub_bytes, filename="mini.epub", max_size_bytes=10_000_000)
    assert result.ok is True
    assert result.title
    assert "Mini" in (result.title or "") or result.title == "mini"
