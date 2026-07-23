"""EPUB file validation for Phase 1 ingestion."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

from ebooklib import epub


@dataclass
class EpubValidationResult:
    ok: bool
    title: str | None = None
    author: str | None = None
    language: str | None = None
    error_code: str | None = None
    error_message: str | None = None


def _reject(code: str, message: str) -> EpubValidationResult:
    return EpubValidationResult(ok=False, error_code=code, error_message=message)


def validate_epub_bytes(
    data: bytes,
    *,
    filename: str,
    max_size_bytes: int,
) -> EpubValidationResult:
    if not filename.lower().endswith(".epub"):
        return _reject("invalid_extension", "File must have a .epub extension.")

    if len(data) == 0:
        return _reject("empty_file", "Uploaded file is empty.")

    if len(data) > max_size_bytes:
        mb = max_size_bytes // (1024 * 1024)
        return _reject("file_too_large", f"EPUB exceeds the maximum size of {mb} MB.")

    # EPUB is a ZIP archive; PK header required.
    if not data.startswith(b"PK"):
        return _reject("corrupt_epub", "File is not a valid EPUB/ZIP archive.")

    try:
        from io import BytesIO

        with zipfile.ZipFile(BytesIO(data)) as zf:
            names = set(zf.namelist())
            if "mimetype" not in names and not any(n.endswith(".opf") for n in names):
                # Soft check: many EPUBs include mimetype; require zip integrity at minimum.
                pass
            if "META-INF/encryption.xml" in names:
                return _reject(
                    "drm_protected",
                    "EPUB appears DRM-protected (META-INF/encryption.xml present).",
                )
            # Probe zip integrity
            bad = zf.testzip()
            if bad is not None:
                return _reject("corrupt_epub", f"Corrupt EPUB member: {bad}")
            # Ensure container or OPF exists
            has_container = "META-INF/container.xml" in names
            has_opf = any(n.lower().endswith(".opf") for n in names)
            if not has_container and not has_opf:
                return _reject("corrupt_epub", "EPUB is missing container/OPF metadata.")
    except zipfile.BadZipFile:
        return _reject("corrupt_epub", "File is not a valid ZIP/EPUB archive.")

    title = Path(filename).stem.replace("_", " ").replace("-", " ").strip() or "Untitled"
    author = None
    language = None

    try:
        from io import BytesIO

        book = epub.read_epub(BytesIO(data))
        meta_title = book.get_metadata("DC", "title")
        if meta_title:
            title = str(meta_title[0][0]).strip() or title
        meta_creator = book.get_metadata("DC", "creator")
        if meta_creator:
            author = str(meta_creator[0][0]).strip() or None
        meta_lang = book.get_metadata("DC", "language")
        if meta_lang:
            language = str(meta_lang[0][0]).strip() or None
    except Exception:
        # Metadata extraction failure is non-fatal after structural checks.
        pass

    return EpubValidationResult(
        ok=True,
        title=title,
        author=author,
        language=language,
    )


def validate_epub_path(path: Path, *, max_size_bytes: int) -> EpubValidationResult:
    data = path.read_bytes()
    return validate_epub_bytes(data, filename=path.name, max_size_bytes=max_size_bytes)
