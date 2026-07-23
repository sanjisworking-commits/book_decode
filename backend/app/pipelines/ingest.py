"""Ingestion pipeline: Phase 1 (Docling) + Phase 2 (canonical normalise + chunk)."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.config import get_settings
from app.domain.enums import BookProcessingStatus, ChapterStatus, UIStage
from app.pipelines.chapter_detect import detect_chapters_from_docling
from app.pipelines.chunk import chunk_source_chapter, validate_chunk_allow_lists
from app.pipelines.docling_convert import convert_epub_with_docling
from app.pipelines.normalise import (
    assert_unique_block_ids,
    normalise_book_from_docling,
    to_source_chapter,
)
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
        settings = get_settings()

        try:
            # --- Phase 1: Docling + preview chapter detection ---
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
            preview_chapters = detect_chapters_from_docling(docling_json)
            self.fs.write_json(
                self.fs.chapters_preview_path(book_id), {"chapters": preview_chapters}
            )

            # --- Phase 2: canonical normalisation (authoritative structure) ---
            self._set_status(
                book_id,
                BookProcessingStatus.PREPARING_BLOCKS,
                UIStage.PREPARING_CHAPTER_BLOCKS,
                job_id=job_id,
            )
            canonical = normalise_book_from_docling(
                book_id=book_id,
                docling_json=docling_json,
                title=book.get("title"),
                author=book.get("author"),
                language=book.get("language"),
            )
            self.fs.write_json(self.fs.book_json_path(book_id), canonical)

            chapters = canonical.get("chapters") or []
            if not chapters:
                raise RuntimeError("Canonical normalisation produced no chapters.")

            normalised_summaries: list[dict[str, Any]] = []
            updated_chapters: list[dict[str, Any]] = []

            for ch in chapters:
                chapter_id = ch["chapter_id"]
                self.db.update_book(book_id, current_chapter_id=chapter_id)

                source = to_source_chapter(canonical, chapter_id)
                if not source.get("source_blocks"):
                    updated_chapters.append(
                        {
                            "chapter_id": chapter_id,
                            "title": ch.get("title"),
                            "chapter_number": ch.get("chapter_number"),
                            "order_index": ch.get("order_index", 0),
                            "status": ChapterStatus.FAILED.value,
                            "retry_count": 0,
                            "error": {
                                "code": "empty_chapter",
                                "message": "No source blocks after normalisation.",
                                "details": None,
                            },
                        }
                    )
                    continue

                assert_unique_block_ids(source)
                chunk_plan = chunk_source_chapter(
                    source,
                    token_limit=settings.chunk_token_limit,
                    overlap_blocks=settings.chunk_overlap_blocks,
                )
                validate_chunk_allow_lists(source, chunk_plan)

                self.fs.write_json(self.fs.chapter_source_path(book_id, chapter_id), source)
                self.fs.write_json(self.fs.chapter_chunks_path(book_id, chapter_id), chunk_plan)

                updated_chapters.append(
                    {
                        "chapter_id": chapter_id,
                        "title": ch.get("title"),
                        "chapter_number": ch.get("chapter_number"),
                        "order_index": ch.get("order_index", 0),
                        "status": ChapterStatus.PENDING.value,
                        "retry_count": 0,
                        "error": None,
                        "preview": {
                            "block_count": len(source["source_blocks"]),
                            "chunk_count": len(chunk_plan.get("chunks") or []),
                            "chunk_strategy": chunk_plan.get("strategy"),
                            "section_count": len(ch.get("sections") or []),
                        },
                    }
                )
                normalised_summaries.append(
                    {
                        "chapter_id": chapter_id,
                        "block_count": len(source["source_blocks"]),
                        "chunk_count": len(chunk_plan.get("chunks") or []),
                        "strategy": chunk_plan.get("strategy"),
                    }
                )

            self.db.replace_chapters(book_id, updated_chapters)
            failed_count = sum(
                1 for c in updated_chapters if c["status"] == ChapterStatus.FAILED.value
            )
            ready_count = len(updated_chapters) - failed_count
            if ready_count == 0:
                raise RuntimeError("Normalisation produced no usable chapters.")

            metadata = {
                "schema_version": "1.0",
                "book_id": book_id,
                "title": book["title"],
                "author": book.get("author"),
                "epub_filename": book["epub_filename"],
                "processing_status": BookProcessingStatus.PREPARING_BLOCKS.value,
                "language": book.get("language"),
                "chapter_count": len(updated_chapters),
                "processed_chapter_count": 0,
                "failed_chapter_count": failed_count,
                "upload_timestamp": book["upload_timestamp"],
                "completion_timestamp": None,
                "error": None,
                "phase1": {
                    "docling_path": str(self.fs.docling_json_path(book_id)),
                    "chapters_preview_path": str(self.fs.chapters_preview_path(book_id)),
                    "converter": "docling",
                },
                "phase2": {
                    "note": "Phase 2 complete: canonical book.json + source blocks + chunk plans.",
                    "canonical_schema_version": "2.0",
                    "book_json_path": str(self.fs.book_json_path(book_id)),
                    "part_count": len(canonical.get("parts") or []),
                    "chapters": normalised_summaries,
                },
            }
            self.db.update_book(
                book_id,
                processing_status=BookProcessingStatus.PREPARING_BLOCKS.value,
                current_stage=UIStage.PREPARING_CHAPTER_BLOCKS.value,
                chapter_count=len(updated_chapters),
                processed_chapter_count=0,
                failed_chapter_count=failed_count,
                current_chapter_id=None,
                job_id=job_id,
                converter="docling",
                error=None,
            )
            self.fs.write_json(self.fs.metadata_path(book_id), metadata)
            logger.info(
                "Phase 2 complete book_id=%s chapters=%s failed=%s",
                book_id,
                ready_count,
                failed_count,
            )
        except Exception as exc:
            logger.exception("Ingest failed book_id=%s", book_id)
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
