"""Book API routes — Phase 1–2 surface."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile

from app.api.deps import get_book_service, get_settings
from app.api.errors import AppError
from app.config import Settings
from app.schemas.api_models import (
    BookMetadata,
    ChapterListResponse,
    ProcessingStatusResponse,
)
from app.services.books import BookService

router = APIRouter(prefix="/books", tags=["books"])


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
    """Return Phase 4 English chapter spine (post-synthesis)."""
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


@router.delete("/{book_id}", status_code=204)
async def delete_book(
    book_id: str,
    service: BookService = Depends(get_book_service),
) -> None:
    try:
        service.delete_book(book_id)
    except KeyError as exc:
        raise AppError(404, "book_not_found", f"Book not found: {book_id}") from exc
