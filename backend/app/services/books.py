"""Book upload / status / lifecycle services."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.pipelines.adapt import AdaptPipeline
from app.pipelines.chunk import chunk_source_chapter, validate_chunk_allow_lists
from app.pipelines.extract import ExtractPipeline
from app.pipelines.ingest import IngestPipeline
from app.pipelines.llm_bind import log_llm_mode
from app.pipelines.synthesise import SynthesisePipeline
from app.pipelines.validate_persist import ValidatePersistPipeline
from app.config import get_settings
from app.domain.enums import (
    BOOK_STATUS_TO_UI_STAGE,
    UI_STAGE_ORDER,
    BookProcessingStatus,
    ChapterStatus,
    UIStage,
)
from app.schemas.api_models import (
    BookMetadata,
    ChapterListResponse,
    ChapterSummary,
    ErrorBody,
    ProcessingStatusResponse,
)
from app.services.epub_validation import validate_epub_bytes
from app.services.source_json_validation import validate_source_chapter_payload
from app.storage.filesystem import FilesystemStore
from app.storage.sqlite_store import SqliteStore
from app.utils.ids import new_book_id, utc_now_iso

logger = logging.getLogger(__name__)

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

_IDLE_COMPLETE_STATUSES = {
    BookProcessingStatus.DETECTING_CHAPTERS.value,
    BookProcessingStatus.PREPARING_BLOCKS.value,
    BookProcessingStatus.ANALYSING_CHAPTERS.value,
    BookProcessingStatus.CONSTRUCTING_SPINES.value,
    BookProcessingStatus.CREATING_HINGLISH.value,
    BookProcessingStatus.VALIDATING.value,
}


def _chapter_progress_label(chapter: dict[str, Any]) -> str | None:
    """Build a short progress string from chapter preview (e.g. extract chunk N/M)."""
    preview = chapter.get("preview") or {}
    total = preview.get("extract_chunk_total")
    index = preview.get("extract_chunk_index")
    if (
        chapter.get("status") == ChapterStatus.EXTRACTING.value
        and isinstance(total, int)
        and total > 0
        and isinstance(index, int)
        and index > 0
    ):
        return f"chunk {index}/{total}"
    if chapter.get("status") == ChapterStatus.SYNTHESISING.value:
        return "synthesising"
    if chapter.get("status") == ChapterStatus.ADAPTING_HINGLISH.value:
        return "adapting"
    if chapter.get("status") == ChapterStatus.VALIDATING.value:
        return "validating"
    return None


class BookService:
    def __init__(self, db: SqliteStore, fs: FilesystemStore) -> None:
        self.db = db
        self.fs = fs
        self.settings = get_settings()
        self.ingest = IngestPipeline(db, fs)
        self.extract = ExtractPipeline(db, fs)
        self.synthesise = SynthesisePipeline(db, fs)
        self.adapt = AdaptPipeline(db, fs)
        self.validate_persist = ValidatePersistPipeline(db, fs)

    def _refresh_llm_clients(self) -> None:
        """Re-read .env / process env and rebind LLM clients before a pipeline run."""
        get_settings.cache_clear()
        settings = get_settings()
        log_llm_mode(settings)
        self.settings = settings
        self.extract.reload_llm(settings)
        self.synthesise.reload_llm(settings)
        self.adapt.reload_llm(settings)
        self.validate_persist.reload_llm(settings)

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

    def upload_source_json(
        self, *, filename: str, data: bytes, max_size_bytes: int
    ) -> BookMetadata:
        """Accept a clean source_chapter JSON and prepare artefacts for LLM extract."""
        import json

        safe_name = filename.rsplit("/", 1)[-1] or "chapter.json"
        if not safe_name.lower().endswith(".json"):
            raise ValueError("invalid_extension", "File must have a .json extension.")
        if len(data) > max_size_bytes:
            raise ValueError(
                "file_too_large",
                f"JSON exceeds the maximum size of {max_size_bytes // (1024 * 1024)} MB.",
            )
        try:
            raw = json.loads(data.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise ValueError("invalid_source_json", "JSON must be UTF-8 text.") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(
                "invalid_source_json", f"Malformed JSON: {exc.msg} (line {exc.lineno})."
            ) from exc

        source = validate_source_chapter_payload(raw)
        settings = getattr(self, "settings", None) or get_settings()

        title_hint = source.get("chapter_title") or source.get("book_id") or "Chapter"
        book_id = new_book_id(str(source.get("book_id") or title_hint))
        chapter_id = source["chapter_id"]
        source["book_id"] = book_id

        chunk_plan = chunk_source_chapter(
            source,
            token_limit=settings.chunk_token_limit,
            overlap_blocks=settings.chunk_overlap_blocks,
        )
        validate_chunk_allow_lists(source, chunk_plan)

        upload_ts = utc_now_iso()
        # Persist original bytes for audit; artefacts drive the pipeline.
        upload_copy = self.fs.book_upload_dir(book_id) / safe_name
        upload_copy.write_bytes(data)

        self.fs.write_json(self.fs.chapter_source_path(book_id, chapter_id), source)
        self.fs.write_json(self.fs.chapter_chunks_path(book_id, chapter_id), chunk_plan)

        record = {
            "book_id": book_id,
            "title": source.get("chapter_title") or title_hint,
            "author": None,
            "epub_filename": safe_name,
            "processing_status": BookProcessingStatus.UPLOADED.value,
            "language": "en",
            "chapter_count": 1,
            "processed_chapter_count": 0,
            "failed_chapter_count": 0,
            "upload_timestamp": upload_ts,
            "completion_timestamp": None,
            "error": None,
            "current_stage": UIStage.UPLOADING_EPUB.value,
            "current_chapter_id": None,
            "job_id": None,
            "converter": "json",
        }
        self.db.insert_book(record)
        self.db.replace_chapters(
            book_id,
            [
                {
                    "chapter_id": chapter_id,
                    "title": source.get("chapter_title") or chapter_id,
                    "chapter_number": source.get("chapter_number") or 1,
                    "order_index": 0,
                    "status": ChapterStatus.PENDING.value,
                    "retry_count": 0,
                    "error": None,
                    "preview": {
                        "block_count": len(source["source_blocks"]),
                        "chunk_count": len(chunk_plan.get("chunks") or []),
                        "chunk_strategy": chunk_plan.get("strategy"),
                        "source": "json_upload",
                    },
                }
            ],
        )
        metadata = self._to_metadata(record)
        self.fs.write_json(self.fs.metadata_path(book_id), metadata.model_dump())
        logger.info(
            "JSON source uploaded book=%s chapter=%s blocks=%s",
            book_id,
            chapter_id,
            len(source["source_blocks"]),
        )
        return metadata

    def start_processing(self, book_id: str) -> ProcessingStatusResponse:
        book = self.db.get_book(book_id)
        if not book:
            raise KeyError(book_id)
        status = book["processing_status"]
        phase_idle_complete = (book.get("chapter_count") or 0) > 0 and status in _IDLE_COMPLETE_STATUSES
        if status in _ACTIVE_STATUSES and not phase_idle_complete:
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
        """Run ingest then decode chapters progressively.

        Prototype (``PROTOTYPE_ONE_SHOT``): one LLM extract per chapter + soft
        validate; skips synthesise and hinglish adapt.

        Full path: extract→synth→adapt→validate per chapter so chapter 1 can
        open while later chapters continue decoding.
        """
        self._refresh_llm_clients()
        settings = getattr(self, "settings", None) or get_settings()
        oneshot = bool(settings.prototype_one_shot)

        book = self.db.get_book(book_id)
        if not book:
            return

        if book.get("converter") == "json":
            # Artefacts already written at upload — skip Docling/normalise.
            logger.info("JSON ingest skip Docling book=%s", book_id)
            if not self.db.list_chapters(book_id):
                self.validate_persist._fail_book(
                    book, book.get("job_id"), "No chapters available for JSON book."
                )
                return
            chapter_id = self.db.list_chapters(book_id)[0]["chapter_id"]
            if not self.fs.chapter_source_path(book_id, chapter_id).exists():
                self.validate_persist._fail_book(
                    book,
                    book.get("job_id"),
                    "Missing source JSON artefact for JSON book.",
                )
                return
            self.db.update_book(
                book_id,
                processing_status=BookProcessingStatus.PREPARING_BLOCKS.value,
                current_stage=UIStage.PREPARING_CHAPTER_BLOCKS.value,
                chapter_count=len(self.db.list_chapters(book_id)),
                error=None,
            )
        else:
            self.ingest.run(book_id)

        book = self.db.get_book(book_id)
        if not book:
            return
        if book["processing_status"] == BookProcessingStatus.FAILED.value:
            return
        if book["processing_status"] != BookProcessingStatus.PREPARING_BLOCKS.value:
            return

        job_id = book.get("job_id")
        chapters = self.db.list_chapters(book_id)
        if not chapters:
            self.validate_persist._fail_book(
                book, job_id, "No chapters available after ingest."
            )
            return

        self.db.update_book(
            book_id,
            chapter_count=len(chapters),
            processed_chapter_count=0,
            failed_chapter_count=0,
        )

        summaries: list[dict[str, Any]] = []
        updated = list(chapters)
        logger.info(
            "Decode path book=%s oneshot=%s chapters=%s",
            book_id,
            oneshot,
            len(chapters),
        )

        for index, ch in enumerate(list(updated)):
            if ch.get("status") == ChapterStatus.FAILED.value:
                summaries.append(
                    {
                        "chapter_id": ch["chapter_id"],
                        "ok": False,
                        "reason": "failed_before_decode",
                    }
                )
                continue

            chapter_id = ch["chapter_id"]
            book = self.db.get_book(book_id) or book

            # --- extract ---
            self.db.update_book(
                book_id,
                processing_status=BookProcessingStatus.ANALYSING_CHAPTERS.value,
                current_stage=UIStage.ANALYSING_CHAPTERS.value,
                current_chapter_id=chapter_id,
                job_id=job_id,
            )
            if oneshot:
                extract_result = self.extract.extract_chapter_oneshot(
                    book_id, ch, book=book
                )
            else:
                extract_result = self.extract.extract_chapter(book_id, ch, book=book)
            ch = extract_result["chapter"]
            updated = self._merge_chapter(book_id, chapter_id, ch)
            if ch.get("status") == ChapterStatus.FAILED.value:
                summaries.append(extract_result["summary"])
                self._refresh_progress_counts(book_id, updated)
                continue

            if oneshot:
                # Prototype: soft EN-only persist; skip synth + hinglish.
                self.db.update_book(
                    book_id,
                    processing_status=BookProcessingStatus.VALIDATING.value,
                    current_stage=UIStage.VALIDATING_OUTPUT.value,
                    current_chapter_id=chapter_id,
                )
                validate_result = self.validate_persist.validate_chapter_soft(
                    book_id, chapter_id, chapter=ch
                )
                ch = validate_result["chapter"]
                updated = self._merge_chapter(book_id, chapter_id, ch)
                summaries.append(validate_result["summary"])
                self._refresh_progress_counts(book_id, updated)
                logger.info(
                    "Oneshot chapter done book=%s chapter=%s index=%s/%s status=%s",
                    book_id,
                    chapter_id,
                    index + 1,
                    len(updated),
                    ch.get("status"),
                )
                continue

            # --- synthesise ---
            self.db.update_book(
                book_id,
                processing_status=BookProcessingStatus.CONSTRUCTING_SPINES.value,
                current_stage=UIStage.CONSTRUCTING_ARGUMENT_SPINES.value,
                current_chapter_id=chapter_id,
            )
            synth_result = self.synthesise.synthesise_chapter(
                book_id, ch, book=self.db.get_book(book_id) or book
            )
            ch = synth_result["chapter"]
            updated = self._merge_chapter(book_id, chapter_id, ch)
            if ch.get("status") == ChapterStatus.FAILED.value:
                summaries.append(synth_result["summary"])
                self._refresh_progress_counts(book_id, updated)
                continue

            # --- adapt ---
            self.db.update_book(
                book_id,
                processing_status=BookProcessingStatus.CREATING_HINGLISH.value,
                current_stage=UIStage.CREATING_HINDI_ENGLISH_VERSIONS.value,
                current_chapter_id=chapter_id,
            )
            adapt_result = self.adapt.adapt_chapter(book_id, ch)
            ch = adapt_result["chapter"]
            updated = self._merge_chapter(book_id, chapter_id, ch)
            if ch.get("status") == ChapterStatus.FAILED.value:
                summaries.append(adapt_result["summary"])
                self._refresh_progress_counts(book_id, updated)
                continue

            # --- validate / persist ---
            self.db.update_book(
                book_id,
                processing_status=BookProcessingStatus.VALIDATING.value,
                current_stage=UIStage.VALIDATING_OUTPUT.value,
                current_chapter_id=chapter_id,
            )
            validate_result = self.validate_persist.validate_chapter(
                book_id, chapter_id, chapter=ch
            )
            ch = validate_result["chapter"]
            updated = self._merge_chapter(book_id, chapter_id, ch)
            summaries.append(validate_result["summary"])
            self._refresh_progress_counts(book_id, updated)

            logger.info(
                "Progressive chapter done book=%s chapter=%s index=%s/%s status=%s",
                book_id,
                chapter_id,
                index + 1,
                len(updated),
                ch.get("status"),
            )

        book = self.db.get_book(book_id) or book
        updated = self.db.list_chapters(book_id)
        completed = sum(
            1 for c in updated if c["status"] == ChapterStatus.COMPLETED.value
        )
        if completed == 0:
            # Prefer a precise early-phase failure over a generic validation rollup.
            extract_failures = [
                c
                for c in updated
                if c.get("status") == ChapterStatus.FAILED.value
                and ((c.get("error") or {}).get("code") == "extraction_failed")
            ]
            if extract_failures and len(extract_failures) == len(updated):
                first_err = (extract_failures[0].get("error") or {}).get("message")
                message = "All chapters failed Argument Spine extraction."
                if first_err:
                    message = f"{message} First error: {first_err}"
                self.extract._fail(
                    book,
                    job_id,
                    message,
                    details={
                        "chapter_errors": [
                            {
                                "chapter_id": c["chapter_id"],
                                "message": ((c.get("error") or {}).get("message")),
                            }
                            for c in extract_failures[:12]
                        ],
                    },
                )
                return

        self.validate_persist._finalise_book(book, job_id, updated, summaries)

    def _merge_chapter(
        self, book_id: str, chapter_id: str, chapter: dict[str, Any]
    ) -> list[dict[str, Any]]:
        chapters = self.db.list_chapters(book_id)
        updated = [
            chapter if c["chapter_id"] == chapter_id else c for c in chapters
        ]
        self.db.replace_chapters(book_id, updated)
        return updated

    def _refresh_progress_counts(
        self, book_id: str, chapters: list[dict[str, Any]]
    ) -> None:
        completed = sum(
            1 for c in chapters if c["status"] == ChapterStatus.COMPLETED.value
        )
        failed = sum(1 for c in chapters if c["status"] == ChapterStatus.FAILED.value)
        self.db.update_book(
            book_id,
            processed_chapter_count=completed,
            failed_chapter_count=failed,
            chapter_count=len(chapters),
        )

    def retry_chapter(
        self, book_id: str, chapter_id: str, *, force: bool = False
    ) -> ProcessingStatusResponse:
        """Re-queue validation/repair for a failed chapter (Phase 6)."""
        self._refresh_llm_clients()
        book = self.db.get_book(book_id)
        if not book:
            raise KeyError(book_id)
        chapters = self.db.list_chapters(book_id)
        target = next((c for c in chapters if c["chapter_id"] == chapter_id), None)
        if not target:
            raise FileNotFoundError(chapter_id)

        retry_count = int(target.get("retry_count") or 0)
        max_retries = self.validate_persist.max_retries
        if not force and retry_count >= max_retries:
            raise RuntimeError("max_retries_exceeded")

        # Mark retrying and bump count
        updated = []
        for c in chapters:
            if c["chapter_id"] == chapter_id:
                updated.append(
                    {
                        **c,
                        "status": ChapterStatus.RETRYING.value,
                        "retry_count": retry_count + 1,
                        "error": None,
                    }
                )
            else:
                updated.append(c)
        self.db.replace_chapters(book_id, updated)
        self.db.update_book(
            book_id,
            processing_status=BookProcessingStatus.VALIDATING.value,
            current_stage=UIStage.VALIDATING_OUTPUT.value,
            current_chapter_id=chapter_id,
        )

        result = self.validate_persist.validate_chapter(
            book_id, chapter_id, force=force
        )
        # Merge result back into chapter list
        final_chapters = []
        for c in self.db.list_chapters(book_id):
            if c["chapter_id"] == chapter_id:
                final_chapters.append(result["chapter"])
            else:
                final_chapters.append(c)
        self.db.replace_chapters(book_id, final_chapters)
        self.validate_persist._finalise_book(
            self.db.get_book(book_id) or book,
            book.get("job_id"),
            final_chapters,
            [
                result["summary"],
                *[
                    {
                        "chapter_id": c["chapter_id"],
                        "ok": c["status"] == ChapterStatus.COMPLETED.value,
                    }
                    for c in final_chapters
                    if c["chapter_id"] != chapter_id
                ],
            ],
        )
        return self.get_status(book_id)

    def get_chapter_source(self, book_id: str, chapter_id: str) -> dict[str, Any]:
        book = self.db.get_book(book_id)
        if not book:
            raise KeyError(book_id)
        path = self.fs.chapter_source_path(book_id, chapter_id)
        if not path.exists():
            raise FileNotFoundError(chapter_id)
        return self.fs.read_json(path)

    def get_canonical_book(self, book_id: str) -> dict[str, Any]:
        book = self.db.get_book(book_id)
        if not book:
            raise KeyError(book_id)
        path = self.fs.book_json_path(book_id)
        if not path.exists():
            raise FileNotFoundError(book_id)
        return self.fs.read_json(path)

    def get_chapter_chunks(self, book_id: str, chapter_id: str) -> dict[str, Any]:
        book = self.db.get_book(book_id)
        if not book:
            raise KeyError(book_id)
        path = self.fs.chapter_chunks_path(book_id, chapter_id)
        if not path.exists():
            raise FileNotFoundError(chapter_id)
        return self.fs.read_json(path)

    def get_chapter_spine_candidate(self, book_id: str, chapter_id: str) -> dict[str, Any]:
        book = self.db.get_book(book_id)
        if not book:
            raise KeyError(book_id)
        # Prefer bilingual spine, then English synthesised, then candidate
        bilingual = self.fs.chapter_spine_path(book_id, chapter_id)
        if bilingual.exists():
            return self.fs.read_json(bilingual)
        en_path = self.fs.chapter_spine_en_path(book_id, chapter_id)
        if en_path.exists():
            return self.fs.read_json(en_path)
        path = self.fs.chapter_spine_candidate_path(book_id, chapter_id)
        if not path.exists():
            raise FileNotFoundError(chapter_id)
        return self.fs.read_json(path)

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
                    progress=_chapter_progress_label(c),
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
                    progress=_chapter_progress_label(c),
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
