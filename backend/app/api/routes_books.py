"""Book API routes — Phase 1–2 surface."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile

from app.api.deps import get_book_service, get_settings
from app.api.errors import AppError
from app.config import Settings
from app.domain.enums import BookProcessingStatus
from app.schemas.api_models import (
    BookMetadata,
    ChapterListResponse,
    ProcessingStatusResponse,
)
from app.services.books import BookService

router = APIRouter(prefix="/books", tags=["books"])

_ACTIVE_BOOK_STATUSES = {
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


@router.post("/upload", response_model=BookMetadata, status_code=201)
async def upload_book(
    file: UploadFile = File(...),
    service: BookService = Depends(get_book_service),
    settings: Settings = Depends(get_settings),
) -> BookMetadata:
    filename = file.filename or "upload.epub"
    data = await file.read()
    try:
        return service.upload_epub(
            filename=filename,
            data=data,
            max_size_bytes=settings.max_epub_size_bytes,
        )
    except ValueError as exc:
        # upload_epub raises ValueError(code, message) via two-arg form — handle both
        if len(exc.args) >= 2:
            code, message = str(exc.args[0]), str(exc.args[1])
        else:
            code, message = "invalid_epub", str(exc)
        raise AppError(400, code, message) from exc


@router.post("/upload-json", response_model=BookMetadata, status_code=201)
async def upload_source_json(
    file: UploadFile = File(...),
    service: BookService = Depends(get_book_service),
    settings: Settings = Depends(get_settings),
) -> BookMetadata:
    """Upload a source_chapter or whole-book JSON (JSON-only ingest; LLM extract still runs)."""
    filename = file.filename or "chapter.json"
    data = await file.read()
    try:
        return service.upload_source_json(
            filename=filename,
            data=data,
            max_size_bytes=settings.max_epub_size_bytes,
        )
    except ValueError as exc:
        if len(exc.args) >= 2:
            code, message = str(exc.args[0]), str(exc.args[1])
        else:
            code, message = "invalid_source_json", str(exc)
        raise AppError(400, code, message) from exc


@router.post(
    "/{book_id}/chapters/upload-json",
    response_model=BookMetadata,
    status_code=201,
)
async def append_source_json(
    book_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    service: BookService = Depends(get_book_service),
    settings: Settings = Depends(get_settings),
) -> BookMetadata:
    """Append one source_chapter to a JSON book and resume decode for pending chapters."""
    filename = file.filename or "chapter.json"
    data = await file.read()
    try:
        before = service.db.get_book(book_id)
        already_decoding = bool(
            before and before.get("processing_status") in _ACTIVE_BOOK_STATUSES
        )
        meta = service.append_source_json(
            book_id=book_id,
            filename=filename,
            data=data,
            max_size_bytes=settings.max_epub_size_bytes,
        )
    except KeyError as exc:
        raise AppError(404, "book_not_found", f"Book not found: {book_id}") from exc
    except ValueError as exc:
        if len(exc.args) >= 2:
            code, message = str(exc.args[0]), str(exc.args[1])
        else:
            code, message = "invalid_source_json", str(exc)
        status = 409 if code == "duplicate_chapter" else 400
        raise AppError(status, code, message) from exc

    # If a decode loop is already running it will re-list pending chapters.
    # Otherwise resume without wiping completed spines.
    if not already_decoding:
        service.resume_processing(book_id)
        background_tasks.add_task(service.run_ingest_sync, book_id)
    return meta


@router.post("/{book_id}/process", response_model=ProcessingStatusResponse, status_code=202)
async def process_book(
    book_id: str,
    background_tasks: BackgroundTasks,
    service: BookService = Depends(get_book_service),
) -> ProcessingStatusResponse:
    try:
        status = service.start_processing(book_id)
    except KeyError as exc:
        raise AppError(404, "book_not_found", f"Book not found: {book_id}") from exc
    except RuntimeError as exc:
        if str(exc) == "already_processing":
            raise AppError(
                409,
                "already_processing",
                "Book is already being processed.",
            ) from exc
        raise
    background_tasks.add_task(service.run_ingest_sync, book_id)
    return status


@router.get("/{book_id}/status", response_model=ProcessingStatusResponse)
async def book_status(
    book_id: str,
    service: BookService = Depends(get_book_service),
) -> ProcessingStatusResponse:
    try:
        return service.get_status(book_id)
    except KeyError as exc:
        raise AppError(404, "book_not_found", f"Book not found: {book_id}") from exc


@router.get("/{book_id}", response_model=BookMetadata)
async def book_metadata(
    book_id: str,
    service: BookService = Depends(get_book_service),
) -> BookMetadata:
    try:
        return service.get_metadata(book_id)
    except KeyError as exc:
        raise AppError(404, "book_not_found", f"Book not found: {book_id}") from exc


@router.get("/{book_id}/chapters", response_model=ChapterListResponse)
async def book_chapters(
    book_id: str,
    service: BookService = Depends(get_book_service),
) -> ChapterListResponse:
    try:
        return service.list_chapters(book_id)
    except KeyError as exc:
        raise AppError(404, "book_not_found", f"Book not found: {book_id}") from exc


@router.get("/{book_id}/canonical")
async def book_canonical(
    book_id: str,
    service: BookService = Depends(get_book_service),
) -> dict:
    try:
        return service.get_canonical_book(book_id)
    except KeyError as exc:
        raise AppError(404, "book_not_found", f"Book not found: {book_id}") from exc
    except FileNotFoundError as exc:
        raise AppError(
            404,
            "canonical_book_not_found",
            f"Canonical book.json not ready: {book_id}",
        ) from exc


@router.get("/{book_id}/chapters/{chapter_id}/source")
async def chapter_source(
    book_id: str,
    chapter_id: str,
    service: BookService = Depends(get_book_service),
) -> dict:
    try:
        return service.get_chapter_source(book_id, chapter_id)
    except KeyError as exc:
        raise AppError(404, "book_not_found", f"Book not found: {book_id}") from exc
    except FileNotFoundError as exc:
        raise AppError(
            404,
            "chapter_source_not_found",
            f"Source chapter not ready: {chapter_id}",
        ) from exc


@router.get("/{book_id}/chapters/{chapter_id}/chunks")
async def chapter_chunks(
    book_id: str,
    chapter_id: str,
    service: BookService = Depends(get_book_service),
) -> dict:
    try:
        return service.get_chapter_chunks(book_id, chapter_id)
    except KeyError as exc:
        raise AppError(404, "book_not_found", f"Book not found: {book_id}") from exc
    except FileNotFoundError as exc:
        raise AppError(
            404,
            "chapter_chunks_not_found",
            f"Chunk plan not ready: {chapter_id}",
        ) from exc


@router.get("/{book_id}/chapters/{chapter_id}/spine")
async def chapter_spine_candidate(
    book_id: str,
    chapter_id: str,
    service: BookService = Depends(get_book_service),
) -> dict:
    """Return validated bilingual Argument Spine when available."""
    try:
        return service.get_chapter_spine_candidate(book_id, chapter_id)
    except KeyError as exc:
        raise AppError(404, "book_not_found", f"Book not found: {book_id}") from exc
    except FileNotFoundError as exc:
        raise AppError(
            409,
            "spine_not_ready",
            f"Argument Spine candidate not ready: {chapter_id}",
        ) from exc


@router.post(
    "/{book_id}/chapters/{chapter_id}/retry",
    response_model=ProcessingStatusResponse,
    status_code=202,
)
async def retry_chapter(
    book_id: str,
    chapter_id: str,
    service: BookService = Depends(get_book_service),
    force: bool = False,
) -> ProcessingStatusResponse:
    """Re-queue validation/repair for a chapter (Phase 6)."""
    try:
        return service.retry_chapter(book_id, chapter_id, force=force)
    except KeyError as exc:
        raise AppError(404, "book_not_found", f"Book not found: {book_id}") from exc
    except FileNotFoundError as exc:
        raise AppError(404, "chapter_not_found", f"Chapter not found: {chapter_id}") from exc
    except RuntimeError as exc:
        if str(exc) == "max_retries_exceeded":
            raise AppError(
                409,
                "max_retries_exceeded",
                "Chapter has reached the maximum retry count.",
            ) from exc
        raise


@router.delete("/{book_id}", status_code=204)
async def delete_book(
    book_id: str,
    service: BookService = Depends(get_book_service),
) -> None:
    try:
        service.delete_book(book_id)
    except KeyError as exc:
        raise AppError(404, "book_not_found", f"Book not found: {book_id}") from exc
