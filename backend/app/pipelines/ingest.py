"""Phase 1 ingestion pipeline: Docling convert + chapter detection."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from app.domain.enums import BookProcessingStatus, UIStage
from app.pipelines.chapter_detect import detect_chapters_from_docling
from app.pipelines.docling_convert import convert_epub_with_docling
from app.storage.filesystem import FilesystemStore
from app.storage.sqlite_store import SqliteStore
from app.utils.ids import utc_now_iso

logger = logging.getLogger(__name__)


class IngestPipeline:
    def __init__(self, db: SqliteStore, fs: FilesystemStore) -> None:
        self.db = db
        self.fs = fs

    def run(self, book_id: str) -> None:
        book = self.db.get_book(book_id)
        if not book:
            logger.error("Ingest requested for unknown book_id=%s", book_id)
            return

        job_id = book.get("job_id") or f"job-{uuid.uuid4().hex[:10]}"
        epub_path = self.fs.epub_path(book_id, book["epub_filename"])

        try:
            self._set_status(
                book_id,
                BookProcessingStatus.READING_STRUCTURE,
                UIStage.READING_BOOK_STRUCTURE,
                job_id=job_id,
            )
            docling_json = convert_epub_with_docling(epub_path)
            self.fs.write_json(self.fs.docling_json_path(book_id), docling_json)

            self._set_status(
                book_id,
                BookProcessingStatus.DETECTING_CHAPTERS,
                UIStage.DETECTING_CHAPTERS,
                job_id=job_id,
            )
            chapters = detect_chapters_from_docling(docling_json)
            if not chapters:
                raise RuntimeError("No chapters detected in EPUB structure.")

            self.fs.write_json(self.fs.chapters_preview_path(book_id), {"chapters": chapters})
            self.db.replace_chapters(book_id, chapters)

            # Phase 1 stops after chapter detection. Later phases continue the pipeline.
            metadata = {
                "schema_version": "1.0",
                "book_id": book_id,
                "title": book["title"],
                "author": book.get("author"),
                "epub_filename": book["epub_filename"],
                "processing_status": BookProcessingStatus.DETECTING_CHAPTERS.value,
                "language": book.get("language"),
                "chapter_count": len(chapters),
                "processed_chapter_count": 0,
                "failed_chapter_count": 0,
                "upload_timestamp": book["upload_timestamp"],
                "completion_timestamp": None,
                "error": None,
                "phase1": {
                    "docling_path": str(self.fs.docling_json_path(book_id)),
                    "chapters_preview_path": str(self.fs.chapters_preview_path(book_id)),
                    "converter": "docling",
                    "note": "Phase 1 complete: structure read and chapters detected. "
                    "Argument Spine generation begins in later phases.",
                },
            }
            # Mark a distinct Phase-1 success status: chapters detected, awaiting later phases.
            # Use detecting_chapters as terminal Phase-1 state with chapter_count set;
            # expose via status API as stage detecting_chapters with chapters listed.
            self.db.update_book(
                book_id,
                processing_status=BookProcessingStatus.DETECTING_CHAPTERS.value,
                current_stage=UIStage.DETECTING_CHAPTERS.value,
                chapter_count=len(chapters),
                processed_chapter_count=0,
                failed_chapter_count=0,
                current_chapter_id=None,
                job_id=job_id,
                converter="docling",
                error=None,
            )
            metadata["processing_status"] = BookProcessingStatus.DETECTING_CHAPTERS.value
            self.fs.write_json(self.fs.metadata_path(book_id), metadata)
            logger.info(
                "Phase 1 ingest complete book_id=%s chapters=%s", book_id, len(chapters)
            )
        except Exception as exc:
            logger.exception("Phase 1 ingest failed book_id=%s", book_id)
            error = {"code": "ingest_failed", "message": str(exc), "details": None}
            self.db.update_book(
                book_id,
                processing_status=BookProcessingStatus.FAILED.value,
                current_stage=UIStage.READING_BOOK_STRUCTURE.value,
                error=error,
                job_id=job_id,
            )
            failed_meta = {
                "schema_version": "1.0",
                "book_id": book_id,
                "title": book["title"],
                "author": book.get("author"),
                "epub_filename": book["epub_filename"],
                "processing_status": BookProcessingStatus.FAILED.value,
                "language": book.get("language"),
                "chapter_count": book.get("chapter_count", 0),
                "processed_chapter_count": 0,
                "failed_chapter_count": 0,
                "upload_timestamp": book["upload_timestamp"],
                "completion_timestamp": utc_now_iso(),
                "error": error,
            }
            self.fs.write_json(self.fs.metadata_path(book_id), failed_meta)

    def _set_status(
        self,
        book_id: str,
        status: BookProcessingStatus,
        stage: UIStage,
        *,
        job_id: str,
    ) -> None:
        self.db.update_book(
            book_id,
            processing_status=status.value,
            current_stage=stage.value,
            job_id=job_id,
        )
