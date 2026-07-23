"""Demo utility routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_book_service, reset_cached_stores
from app.services.books import BookService

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/reset", status_code=204)
async def reset_demo(service: BookService = Depends(get_book_service)) -> None:
    service.reset_demo()
    reset_cached_stores()
