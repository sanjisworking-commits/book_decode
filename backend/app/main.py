"""FastAPI application entrypoint."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_settings
from app.api.errors import AppError, app_error_handler
from app.api.routes_books import router as books_router
from app.api.routes_demo import router as demo_router
from app.pipelines.llm_bind import log_llm_mode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
log_llm_mode(settings)

app = FastAPI(
    title="According to Logic — Book Decode",
    description="Phase 6: EPUB ingest through validated bilingual Argument Spine persistence.",
    version="0.6.0",
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
async def health() -> dict[str, object]:
    """Liveness + LLM mode diagnostics (no secrets)."""
    get_settings.cache_clear()
    s = get_settings()
    return {
        "status": "ok",
        "phase": "6",
        "llm_mock": s.llm_mock,
        "llm_provider": "mock" if s.llm_mock else s.llm_provider,
        "llm_model": "mock" if s.llm_mock else s.llm_model,
        "llm_api_key_configured": bool(s.llm_api_key and s.llm_api_key.strip()),
    }
