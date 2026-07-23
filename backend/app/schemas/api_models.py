"""API / domain Pydantic models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class BookMetadata(BaseModel):
    schema_version: str = "1.0"
    book_id: str
    title: str
    author: str | None = None
    epub_filename: str
    processing_status: str
    language: str | None = None
    chapter_count: int = 0
    processed_chapter_count: int = 0
    failed_chapter_count: int = 0
    upload_timestamp: str
    completion_timestamp: str | None = None
    error: ErrorBody | None = None


class ChapterSummary(BaseModel):
    chapter_id: str
    title: str | None = None
    chapter_number: int | None = None
    status: str
    retry_count: int = 0
    error: ErrorBody | None = None


class ProcessingStatusResponse(BaseModel):
    schema_version: str = "1.0"
    book_id: str
    job_id: str | None = None
    processing_status: str
    current_stage: str
    stage_index: int
    stages_total: int = 10
    chapter_count: int = 0
    processed_chapter_count: int = 0
    failed_chapter_count: int = 0
    current_chapter_id: str | None = None
    partial_success: bool = False
    error: ErrorBody | None = None
    chapters: list[ChapterSummary] = Field(default_factory=list)
    updated_at: str | None = None


class ChapterListResponse(BaseModel):
    book_id: str
    chapters: list[ChapterSummary]
