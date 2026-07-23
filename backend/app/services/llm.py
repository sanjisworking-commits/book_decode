"""Multi-provider LLM clients for Argument Spine extraction.

Providers:
- openai / openai_compatible → Chat Completions API
- anthropic → Anthropic Messages API (Claude)
- mock → deterministic offline client (LLM_MOCK=true)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Protocol

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)

DEFAULT_OPENAI_BASE = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_ANTHROPIC_BASE = "https://api.anthropic.com"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
ANTHROPIC_VERSION = "2023-06-01"

VALID_PROVIDERS = frozenset({"openai", "anthropic", "openai_compatible"})


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        ...


def parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    text = _FENCE_RE.sub("", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM returned invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMError("LLM JSON root must be an object")
    return data


class OpenAICompatibleClient:
    """OpenAI Chat Completions wire protocol (OpenAI, Groq, Together, Ollama, etc.)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        if not self.settings.llm_api_key:
            raise LLMError(
                "LLM_API_KEY is not configured. Set LLM_API_KEY or LLM_MOCK=true."
            )

        url = self.settings.llm_api_base.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "temperature": self.settings.llm_temperature,
            "max_tokens": self.settings.llm_max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        # Some compatible gateways reject response_format; keep for OpenAI-like APIs.
        if self.settings.llm_provider in {"openai", "openai_compatible"}:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM HTTP error: {exc}") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Unexpected OpenAI-compatible response shape") from exc

        return parse_json_content(content)


class AnthropicClient:
    """Anthropic Messages API (Claude)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        if not self.settings.llm_api_key:
            raise LLMError(
                "LLM_API_KEY is not configured. Set LLM_API_KEY or LLM_MOCK=true."
            )

        base = self.settings.llm_api_base.rstrip("/")
        # Accept either https://api.anthropic.com or .../v1
        if base.endswith("/v1"):
            url = base + "/messages"
        else:
            url = base + "/v1/messages"

        payload = {
            "model": self.settings.llm_model,
            "max_tokens": self.settings.llm_max_tokens,
            "temperature": self.settings.llm_temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {
            "x-api-key": self.settings.llm_api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"Anthropic HTTP error: {exc}") from exc

        content = _anthropic_text_content(data)
        return parse_json_content(content)


def _anthropic_text_content(data: dict[str, Any]) -> str:
    blocks = data.get("content")
    if not isinstance(blocks, list) or not blocks:
        raise LLMError("Unexpected Anthropic response shape: missing content")
    texts: list[str] = []
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            texts.append(str(block.get("text") or ""))
    if not texts:
        raise LLMError("Unexpected Anthropic response shape: no text blocks")
    return "\n".join(texts)


class MockLLMClient:
    """Deterministic extractor for tests / offline demo (LLM_MOCK=true)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        book_id = "book"
        chapter_id = "ch01"
        block_ids: list[str] = []
        excerpt = ""
        try:
            marker = "===SOURCE_BLOCKS_JSON==="
            if marker in user:
                raw = user.split(marker, 1)[1].strip()
                payload = json.loads(raw)
                book_id = payload.get("book_id") or book_id
                chapter_id = payload.get("chapter_id") or chapter_id
                blocks = payload.get("blocks") or []
                block_ids = [b["block_id"] for b in blocks if b.get("block_id")]
                excerpt = " ".join((b.get("text") or "")[:120] for b in blocks[:3])
        except Exception:
            logger.exception("Mock LLM failed to parse user payload; using defaults")

        cited = block_ids[:3] if block_ids else []
        nodes = _mock_nodes(chapter_id, cited, excerpt)
        return {
            "schema_version": "1.0",
            "book_id": book_id,
            "chapter_id": chapter_id,
            "language_modes": ["en"],
            "nodes": nodes,
            "confidence_summary": {
                "overall": 0.55,
                "notes": "Generated by MockLLMClient (LLM_MOCK=true).",
            },
            "processing": {
                "model": "mock",
                "prompt_versions": {"argument_spine_extraction": "3.0.0"},
                "created_at": None,
                "updated_at": None,
            },
            "validation": None,
        }


def _mock_nodes(chapter_id: str, cited: list[str], excerpt: str) -> list[dict[str, Any]]:
    types = [
        "chapter_question",
        "central_claim",
        "reasoning_steps",
        "evidence_and_examples",
        "hidden_assumptions",
        "tensions_or_gaps",
        "strongest_counter_position",
        "consequence_if_correct",
        "role_in_book",
        "one_sentence_decode",
        "confidence_and_unresolved",
        "source_block_references",
    ]
    nodes: list[dict[str, Any]] = []
    for i, node_type in enumerate(types):
        node_id = f"{chapter_id}-n{i+1:02d}"
        status = (
            "external_counter"
            if node_type == "strongest_counter_position"
            else "ai_inference"
        )
        if node_type in {"chapter_question", "central_claim", "evidence_and_examples"}:
            status = "author_paraphrase"
        statement = None
        if node_type == "chapter_question":
            statement = "What claim does this chapter advance?"
        elif node_type == "central_claim":
            statement = (
                "The chapter advances a central claim grounded in the source text."
                + (f" Context: {excerpt[:160]}" if excerpt else "")
            )
        elif node_type == "one_sentence_decode":
            statement = "This chapter contributes one step in the book's overall argument."
        elif node_type == "source_block_references":
            statement = "Cited source blocks for this decode."
        else:
            statement = f"[{node_type}] reconstructed from available evidence."

        nodes.append(
            {
                "id": node_id,
                "node_type": node_type,
                "statement_en": statement,
                "explanation_en": "Mock extraction placeholder for pipeline testing.",
                "statement_hinglish": None,
                "explanation_hinglish": None,
                "source_status": status,
                "source_block_ids": list(cited),
                "confidence": 0.5,
                "order": i,
                "prev_id": nodes[-1]["id"] if nodes else None,
                "next_id": None,
                "warnings": ["mock_llm"],
            }
        )
    for i in range(len(nodes) - 1):
        nodes[i]["next_id"] = nodes[i + 1]["id"]
    return nodes


def _apply_provider_defaults(settings: Settings) -> Settings:
    """Apply Anthropic base/model defaults when still on OpenAI defaults."""
    updates: dict[str, Any] = {}
    if settings.llm_api_base.rstrip("/") == DEFAULT_OPENAI_BASE.rstrip("/"):
        updates["llm_api_base"] = DEFAULT_ANTHROPIC_BASE
    if settings.llm_model == DEFAULT_OPENAI_MODEL:
        updates["llm_model"] = DEFAULT_ANTHROPIC_MODEL
    if not updates:
        return settings
    return settings.model_copy(update=updates)


def resolve_llm_settings(settings: Settings) -> Settings:
    """Normalize provider name and apply Anthropic defaults when needed."""
    provider = (settings.llm_provider or "openai").strip().lower()
    if provider not in VALID_PROVIDERS and provider:
        # Leave unknown provider for get_llm_client to reject
        return settings.model_copy(update={"llm_provider": provider})

    updated = settings.model_copy(update={"llm_provider": provider or "openai"})
    if updated.llm_provider == "anthropic":
        updated = _apply_provider_defaults(updated)
    return updated


def get_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_mock:
        return MockLLMClient(settings)

    resolved = resolve_llm_settings(settings)
    provider = (resolved.llm_provider or "openai").strip().lower()
    if provider not in VALID_PROVIDERS:
        raise LLMError(
            f"Unknown LLM_PROVIDER={settings.llm_provider!r}. "
            f"Use one of: {', '.join(sorted(VALID_PROVIDERS))}."
        )

    if provider == "anthropic":
        return AnthropicClient(resolved)

    # openai and openai_compatible share the Chat Completions client
    return OpenAICompatibleClient(resolved)
