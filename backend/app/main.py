"""FastAPI application entrypoint."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_settings
from app.api.errors import AppError, app_error_handler
from app.api.routes_books import router as books_router
from app.api.routes_demo import router as demo_router

logging.basicConfig(level=logging.INFO)

settings = get_settings()

app = FastAPI(
    title="According to Logic — Book Decode",
    description="Phase 3: EPUB ingest through English Argument Spine extraction.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.include_router(books_router)
app.include_router(demo_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "phase": "3"}
