"""Shared LLM settings binding for pipeline classes."""

from __future__ import annotations

import logging

from app.config import Settings, get_settings
from app.services.llm import get_llm_client, resolve_llm_settings

logger = logging.getLogger(__name__)


def bind_llm(
    settings: Settings | None = None, *, refresh_env: bool = False
) -> tuple[Settings, object]:
    """Load settings and construct the LLM client.

    When ``refresh_env`` is True (or settings is omitted), clears the settings
    cache so .env edits are picked up. Shell environment variables still win
    over values in ``.env``.
    """
    if settings is None or refresh_env:
        get_settings.cache_clear()
        raw = get_settings()
    else:
        raw = settings
    resolved = resolve_llm_settings(raw) if not raw.llm_mock else raw
    client = get_llm_client(resolved if not raw.llm_mock else raw)
    return resolved, client


def log_llm_mode(settings: Settings) -> None:
    if settings.llm_mock:
        logger.warning(
            "LLM_MOCK=true — using MockLLMClient (placeholder Argument Spines). "
            "Unset LLM_MOCK in the shell and set LLM_MOCK=false in .env to use Anthropic/OpenAI."
        )
    else:
        resolved = resolve_llm_settings(settings)
        logger.info(
            "LLM client ready provider=%s model=%s api_key_configured=%s",
            resolved.llm_provider,
            resolved.llm_model,
            bool(resolved.llm_api_key),
        )
