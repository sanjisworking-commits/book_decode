"""Book upload / status / lifecycle services."""

from __future__ import annotations

import uuid
from typing import Any

from app.domain.enums import (
    BOOK_STATUS_TO_UI_STAGE,
    UI_STAGE_ORDER,
    BookProcessingStatus,
    UIStage,
)
from app.pipelines.ingest import IngestPipeline
from app.schemas.api_models import (
    BookMetadata,
    ChapterListResponse,
    ChapterSummary,
    ErrorBody,
    ProcessingStatusResponse,
)
from app.services.epub_validation import validate_epub_bytes
from app.storage.filesystem import FilesystemStore
from app.storage.sqlite_store import SqliteStore
from app.utils.ids import new_book_id, utc_now_iso


_ACTIVE_STATUSES = {
    BookProcessingStatus.QUEUED.value,
    BookProcessingStatus.READING_STRUCTURE.value,
    BookProcessingStatus.DETECTING_CHAPTERS.value,
    BookProcessingStatus.PREPARING_BLOCKS.value,
    BookProcessingStatus.ANALYSING_CHAPTERS.value,
    BookProcessingStatus.CONSTRUCTING_SPINES.value,
    BookProcessingStatus.CREATING_HINGLISH.value,
    BookProcessingStatus.VALIDATING.value,
    BookProcessingStatus.SAVING.value,
}


class BookService:
    def __init__(self, db: SqliteStore, fs: FilesystemStore) -> None:
        self.db = db
        self.fs = fs
        self.ingest = IngestPipeline(db, fs)

    def upload_epub(self, *, filename: str, data: bytes, max_size_bytes: int) -> BookMetadata:
        result = validate_epub_bytes(data, filename=filename, max_size_bytes=max_size_bytes)
        if not result.ok:
            raise ValueError(result.error_code or "invalid_epub", result.error_message or "Invalid EPUB")

        safe_name = filename.rsplit("/", 1)[-1]
        if not safe_name.lower().endswith(".epub"):
            safe_name = f"{safe_name}.epub"

        book_id = new_book_id(result.title)
        upload_ts = utc_now_iso()
        path = self.fs.epub_path(book_id, safe_name)
        path.write_bytes(data)

        record = {
            "book_id": book_id,
            "title": result.title or "Untitled",
            "author": result.author,
            "epub_filename": safe_name,
            "processing_status": BookProcessingStatus.UPLOADED.value,
            "language": result.language,
            "chapter_count": 0,
            "processed_chapter_count": 0,
            "failed_chapter_count": 0,
            "upload_timestamp": upload_ts,
            "completion_timestamp": None,
            "error": None,
            "current_stage": UIStage.UPLOADING_EPUB.value,
            "current_chapter_id": None,
            "job_id": None,
            "converter": None,
        }
        self.db.insert_book(record)
        metadata = self._to_metadata(record)
        self.fs.write_json(self.fs.metadata_path(book_id), metadata.model_dump())
        return metadata

    def start_processing(self, book_id: str) -> ProcessingStatusResponse:
        book = self.db.get_book(book_id)
        if not book:
            raise KeyError(book_id)
        status = book["processing_status"]
        phase1_idle_complete = (
            status == BookProcessingStatus.DETECTING_CHAPTERS.value
            and (book.get("chapter_count") or 0) > 0
        )
        if status in _ACTIVE_STATUSES and not phase1_idle_complete:
            raise RuntimeError("already_processing")

        job_id = f"job-{uuid.uuid4().hex[:10]}"
        self.db.update_book(
            book_id,
            processing_status=BookProcessingStatus.QUEUED.value,
            current_stage=UIStage.READING_BOOK_STRUCTURE.value,
            job_id=job_id,
            error=None,
            chapter_count=0,
            processed_chapter_count=0,
            failed_chapter_count=0,
            current_chapter_id=None,
        )
        return self.get_status(book_id)

    def run_ingest_sync(self, book_id: str) -> None:
        """Run Phase 1 ingest (called from background task or tests)."""
        self.ingest.run(book_id)

    def get_metadata(self, book_id: str) -> BookMetadata:
        book = self.db.get_book(book_id)
        if not book:
            raise KeyError(book_id)
        return self._to_metadata(book)

    def get_status(self, book_id: str) -> ProcessingStatusResponse:
        book = self.db.get_book(book_id)
        if not book:
            raise KeyError(book_id)
        chapters = self.db.list_chapters(book_id)
        status = BookProcessingStatus(book["processing_status"])
        stage_name = book.get("current_stage") or BOOK_STATUS_TO_UI_STAGE.get(
            status, UIStage.UPLOADING_EPUB
        ).value
        try:
            stage = UIStage(stage_name)
        except ValueError:
            stage = BOOK_STATUS_TO_UI_STAGE.get(status, UIStage.UPLOADING_EPUB)
        stage_index = UI_STAGE_ORDER.index(stage) + 1
        failed = sum(1 for c in chapters if c["status"] == "failed")
        processed = sum(1 for c in chapters if c["status"] == "completed")
        partial = processed > 0 and failed > 0
        return ProcessingStatusResponse(
            book_id=book_id,
            job_id=book.get("job_id"),
            processing_status=book["processing_status"],
            current_stage=stage.value,
            stage_index=stage_index,
            stages_total=10,
            chapter_count=book.get("chapter_count") or len(chapters),
            processed_chapter_count=book.get("processed_chapter_count") or processed,
            failed_chapter_count=book.get("failed_chapter_count") or failed,
            current_chapter_id=book.get("current_chapter_id"),
            partial_success=partial,
            error=ErrorBody(**book["error"]) if book.get("error") else None,
            chapters=[
                ChapterSummary(
                    chapter_id=c["chapter_id"],
                    title=c.get("title"),
                    chapter_number=c.get("chapter_number"),
                    status=c["status"],
                    retry_count=c.get("retry_count") or 0,
                    error=ErrorBody(**c["error"]) if c.get("error") else None,
                )
                for c in chapters
            ],
            updated_at=book.get("updated_at"),
        )

    def list_chapters(self, book_id: str) -> ChapterListResponse:
        book = self.db.get_book(book_id)
        if not book:
            raise KeyError(book_id)
        chapters = self.db.list_chapters(book_id)
        return ChapterListResponse(
            book_id=book_id,
            chapters=[
                ChapterSummary(
                    chapter_id=c["chapter_id"],
                    title=c.get("title"),
                    chapter_number=c.get("chapter_number"),
                    status=c["status"],
                    retry_count=c.get("retry_count") or 0,
                    error=ErrorBody(**c["error"]) if c.get("error") else None,
                )
                for c in chapters
            ],
        )

    def delete_book(self, book_id: str) -> None:
        book = self.db.get_book(book_id)
        if not book:
            raise KeyError(book_id)
        self.db.delete_book(book_id)
        self.fs.delete_book_artefacts(book_id)

    def reset_demo(self) -> None:
        self.db.reset_all()
        self.fs.reset_all()

    @staticmethod
    def _to_metadata(book: dict[str, Any]) -> BookMetadata:
        return BookMetadata(
            book_id=book["book_id"],
            title=book["title"],
            author=book.get("author"),
            epub_filename=book["epub_filename"],
            processing_status=book["processing_status"],
            language=book.get("language"),
            chapter_count=book.get("chapter_count") or 0,
            processed_chapter_count=book.get("processed_chapter_count") or 0,
            failed_chapter_count=book.get("failed_chapter_count") or 0,
            upload_timestamp=book["upload_timestamp"],
            completion_timestamp=book.get("completion_timestamp"),
            error=ErrorBody(**book["error"]) if book.get("error") else None,
        )
