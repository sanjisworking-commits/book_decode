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
import time
from typing import Any, Protocol

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)

DEFAULT_OPENAI_BASE = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_ANTHROPIC_BASE = "https://api.anthropic.com"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
ANTHROPIC_VERSION = "2023-06-01"
# Retired Anthropic model IDs → recommended replacements (404 after retirement).
RETIRED_ANTHROPIC_MODELS: dict[str, str] = {
    "claude-sonnet-4-20250514": "claude-sonnet-4-6",
    "claude-opus-4-20250514": "claude-opus-4-8",
    "claude-sonnet-4-0": "claude-sonnet-4-6",
    "claude-opus-4-0": "claude-opus-4-8",
}

VALID_PROVIDERS = frozenset({"openai", "anthropic", "openai_compatible"})


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    def complete_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float | None = None,
        pass_name: str | None = None,
    ) -> dict[str, Any]:
        ...


def parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    text = _FENCE_RE.sub("", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        hint = ""
        if "Unterminated string" in str(exc) or "Expecting" in str(exc):
            hint = (
                " Response looks truncated — raise LLM_MAX_TOKENS "
                f"(current response length {len(text)} chars) or use a smaller chapter/chunk."
            )
        raise LLMError(f"LLM returned invalid JSON: {exc}.{hint}") from exc
    if not isinstance(data, dict):
        raise LLMError("LLM JSON root must be an object")
    return data


def _ensure_complete_generation(
    *,
    stop_reason: str | None,
    finish_reason: str | None,
    max_tokens: int,
) -> None:
    """Fail closed when the model stopped because the output budget was hit."""
    if stop_reason == "max_tokens" or finish_reason == "length":
        raise LLMError(
            f"LLM output truncated at max_tokens={max_tokens}. "
            "Increase LLM_MAX_TOKENS or reduce chapter/chunk size so the Argument Spine fits."
        )


def _httpx_timeout(settings: Settings) -> httpx.Timeout:
    read = max(30.0, float(settings.llm_timeout_seconds or 300.0))
    return httpx.Timeout(connect=30.0, read=read, write=60.0, pool=30.0)


def _post_json(
    *,
    settings: Settings,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    error_prefix: str,
) -> dict[str, Any]:
    """POST JSON with timeout + retries for transient network/read timeouts."""
    attempts = max(1, int(settings.llm_http_retries or 0) + 1)
    timeout = _httpx_timeout(settings)
    last_exc: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, dict):
                    raise LLMError(f"{error_prefix}: response JSON root must be an object")
                return data
        except httpx.HTTPStatusError as exc:
            detail = (exc.response.text or "")[:500]
            hint = ""
            status = exc.response.status_code
            detail_l = detail.lower()
            if status in (413, 429) or "rate_limit" in detail_l or "request too large" in detail_l:
                hint = (
                    " Request exceeded the provider token budget. Groq free tier "
                    "counts prompt_tokens + max_tokens against TPM (12k on 70b). "
                    "Latest code auto-clamps both; set LLM_MAX_TOKENS=4096 and "
                    "LLM_MAX_INPUT_TOKENS=6000 if you still 413 after pulling."
                )
            raise LLMError(
                f"{error_prefix} {status}: {detail or exc}.{hint}"
            ) from exc
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout) as exc:
            last_exc = exc
            logger.warning(
                "%s timeout attempt %s/%s (read=%ss): %s",
                error_prefix,
                attempt,
                attempts,
                timeout.read,
                exc,
            )
            if attempt >= attempts:
                break
            time.sleep(min(2.0 * attempt, 8.0))
        except httpx.HTTPError as exc:
            last_exc = exc
            logger.warning(
                "%s HTTP error attempt %s/%s: %s",
                error_prefix,
                attempt,
                attempts,
                exc,
            )
            if attempt >= attempts:
                break
            time.sleep(min(2.0 * attempt, 8.0))

    raise LLMError(
        f"{error_prefix} timed out after {attempts} attempt(s) "
        f"(LLM_TIMEOUT_SECONDS={timeout.read}). Last error: {last_exc}"
    ) from last_exc


class OpenAICompatibleClient:
    """OpenAI Chat Completions wire protocol (OpenAI, Groq, Together, Ollama, etc.)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float | None = None,
        pass_name: str | None = None,
    ) -> dict[str, Any]:
        _ = pass_name
        if not self.settings.llm_api_key:
            raise LLMError(
                "LLM_API_KEY is not configured. Set LLM_API_KEY or LLM_MOCK=true."
            )

        url = self.settings.llm_api_base.rstrip("/") + "/chat/completions"
        max_tokens = self.settings.effective_llm_max_tokens()
        temp = (
            float(temperature)
            if temperature is not None
            else float(self.settings.llm_temperature)
        )
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "temperature": temp,
            "max_tokens": max_tokens,
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
        data = _post_json(
            settings=self.settings,
            url=url,
            headers=headers,
            payload=payload,
            error_prefix="LLM HTTP",
        )

        try:
            choice = data["choices"][0]
            content = choice["message"]["content"]
            finish_reason = choice.get("finish_reason")
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Unexpected OpenAI-compatible response shape") from exc

        _ensure_complete_generation(
            stop_reason=None,
            finish_reason=finish_reason if isinstance(finish_reason, str) else None,
            max_tokens=max_tokens,
        )
        return parse_json_content(content)


class AnthropicClient:
    """Anthropic Messages API (Claude)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float | None = None,
        pass_name: str | None = None,
    ) -> dict[str, Any]:
        _ = pass_name
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

        temp = (
            float(temperature)
            if temperature is not None
            else float(self.settings.llm_temperature)
        )
        payload = {
            "model": self.settings.llm_model,
            "max_tokens": self.settings.llm_max_tokens,
            "temperature": temp,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {
            "x-api-key": self.settings.llm_api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }
        data = _post_json(
            settings=self.settings,
            url=url,
            headers=headers,
            payload=payload,
            error_prefix="Anthropic HTTP",
        )

        stop_reason = data.get("stop_reason")
        _ensure_complete_generation(
            stop_reason=stop_reason if isinstance(stop_reason, str) else None,
            finish_reason=None,
            max_tokens=self.settings.llm_max_tokens,
        )
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
    """Deterministic extractor/synthesis for tests / offline demo (LLM_MOCK=true)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float | None = None,
        pass_name: str | None = None,
    ) -> dict[str, Any]:
        _ = temperature  # deterministic mock ignores temperature
        _ = pass_name
        # Phase 6 repair paths
        if "===REPAIR_SPINE_JSON===" in user:
            return self._mock_repair_schema(user)
        if "===SOURCE_REPAIR_JSON===" in user:
            return self._mock_repair_sources(user)

        # Phase 5 hinglish adaptation path
        adapt_marker = "===ENGLISH_SPINE_JSON==="
        if adapt_marker in user:
            return self._mock_adapt(user)

        # Phase 4 synthesis path (partial merge)
        synth_marker = "===PARTIAL_SPINES_JSON==="
        if synth_marker in user:
            return self._mock_synthesis(user)

        # Adaptive Pass 2
        if "===ARGUMENT_DISCOVERY_JSON===" in user:
            return self._mock_adaptive_synthesis(user)

        # Discovery merge
        if "===CHUNK_DISCOVERIES_JSON===" in user:
            return self._mock_discovery_merge(user)

        # Adaptive Pass 1 discovery
        if "===DISCOVERY_SOURCE_BLOCKS_JSON===" in user or (
            "Argument Discovery" in system and "===SOURCE_BLOCKS_JSON===" in user
        ):
            return self._mock_discovery(user)

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

    def _mock_repair_schema(self, user: str) -> dict[str, Any]:
        import copy

        try:
            raw = user.split("===REPAIR_SPINE_JSON===", 1)[1].strip()
            payload = json.loads(raw)
            spine = copy.deepcopy(payload.get("spine") or {})
        except Exception as exc:
            raise LLMError(f"Mock schema repair parse failed: {exc}") from exc
        spine["schema_version"] = "1.0"
        spine.setdefault("language_modes", ["en"])
        spine.setdefault("nodes", [])
        for i, node in enumerate(spine["nodes"]):
            node.setdefault("id", f"repair-n{i+1:02d}")
            node.setdefault("node_type", "central_claim")
            node.setdefault("statement_en", node.get("statement_en"))
            node.setdefault("source_status", "ai_inference")
            node.setdefault("source_block_ids", [])
            node.setdefault("order", i)
            node.setdefault("warnings", [])
            warnings = list(node.get("warnings") or [])
            if "mock_schema_repair" not in warnings:
                warnings.append("mock_schema_repair")
            node["warnings"] = warnings
        return spine

    def _mock_repair_sources(self, user: str) -> dict[str, Any]:
        import copy

        from app.pipelines.validate_spine import strip_invalid_source_refs

        try:
            raw = user.split("===SOURCE_REPAIR_JSON===", 1)[1].strip()
            payload = json.loads(raw)
            spine = copy.deepcopy(payload.get("spine") or {})
            allowed = set(payload.get("allow_listed_block_ids") or [])
        except Exception as exc:
            raise LLMError(f"Mock source repair parse failed: {exc}") from exc
        cleaned = strip_invalid_source_refs(spine, allowed)
        for node in cleaned.get("nodes") or []:
            warnings = list(node.get("warnings") or [])
            if "mock_source_repair" not in warnings:
                warnings.append("mock_source_repair")
            node["warnings"] = warnings
        return cleaned

    def _mock_adapt(self, user: str) -> dict[str, Any]:
        from app.pipelines.align_spine import mock_adapt_spine

        try:
            raw = user.split("===ENGLISH_SPINE_JSON===", 1)[1].strip()
            payload = json.loads(raw)
            english = payload.get("spine") or payload
        except Exception as exc:
            raise LLMError(f"Mock adapt payload parse failed: {exc}") from exc
        return mock_adapt_spine(english)

    def _mock_synthesis(self, user: str) -> dict[str, Any]:
        from app.pipelines.merge_spines import merge_partial_spines

        try:
            raw = user.split("===PARTIAL_SPINES_JSON===", 1)[1].strip()
            payload = json.loads(raw)
        except Exception as exc:
            raise LLMError(f"Mock synthesis payload parse failed: {exc}") from exc

        book_id = payload.get("book_id") or "book"
        chapter_id = payload.get("chapter_id") or "ch01"
        partials = payload.get("partials") or []
        allowed = set(payload.get("allow_listed_block_ids") or [])
        if not allowed:
            for partial in partials:
                for node in partial.get("nodes") or []:
                    allowed.update(node.get("source_block_ids") or [])
        spine = merge_partial_spines(
            book_id=book_id,
            chapter_id=chapter_id,
            partials=partials,
            allowed_block_ids=allowed,
        )
        spine["confidence_summary"] = {
            "overall": (spine.get("confidence_summary") or {}).get("overall"),
            "notes": "Generated by MockLLMClient synthesis (LLM_MOCK=true).",
        }
        spine["processing"] = {
            "model": "mock",
            "prompt_versions": {"argument_spine_synthesis": "4.0.0"},
            "created_at": None,
            "updated_at": None,
        }
        return spine

    def _mock_discovery(self, prompt: str) -> dict[str, Any]:
        block_ids = re.findall(r'"block_id"\s*:\s*"([^"]+)"', prompt)
        ids = block_ids[:8] if block_ids else ["b1"]
        first = ids[0]
        second = ids[1] if len(ids) > 1 else first
        third = ids[2] if len(ids) > 2 else first
        book_id, chapter_id = "mock-book", "ch01"
        try:
            marker = "===DISCOVERY_SOURCE_BLOCKS_JSON==="
            if marker not in prompt:
                marker = "===SOURCE_BLOCKS_JSON==="
            if marker in prompt:
                raw = prompt.split(marker, 1)[1].strip()
                payload = json.loads(raw)
                book_id = payload.get("book_id") or book_id
                chapter_id = payload.get("chapter_id") or chapter_id
                blocks = payload.get("blocks") or []
                if blocks:
                    ids = [b["block_id"] for b in blocks if b.get("block_id")][:8] or ids
                    first = ids[0]
                    second = ids[1] if len(ids) > 1 else first
                    third = ids[2] if len(ids) > 2 else first
        except Exception:
            logger.exception("Mock discovery failed to parse payload; using defaults")

        return {
            "schema_version": "1.0",
            "book_id": book_id,
            "chapter_id": chapter_id,
            "chapter_types": ["conceptual_framework"],
            "chapter_objective": {
                "statement": "Understand the chapter's organising argument",
                "source_block_ids": [first],
                "confidence": 0.8,
            },
            "central_problem": {
                "statement": "What claim does this chapter advance?",
                "source_block_ids": [first],
                "confidence": 0.75,
            },
            "argument_movements": [
                {
                    "movement_id": "m01",
                    "title": "Setup",
                    "function": "introduces_core_claim",
                    "description": "Introduces the chapter problem",
                    "source_block_ids": ids[:2],
                    "order": 0,
                }
            ],
            "claims": [
                {
                    "claim_id": "c01",
                    "statement": "Mock central claim from discovery",
                    "claim_level": "major",
                    "position_owner": "author",
                    "source_status": "author_paraphrase",
                    "source_block_ids": [first],
                    "confidence": 0.9,
                }
            ],
            "supporting_material": [
                {
                    "item_id": "s01",
                    "material_type": "empirical_evidence",
                    "statement": "Mock supporting evidence",
                    "supports_claim_ids": ["c01"],
                    "source_block_ids": [second],
                    "confidence": 0.85,
                },
                {
                    "item_id": "s02",
                    "material_type": "example",
                    "statement": "Mock example",
                    "supports_claim_ids": ["c01"],
                    "source_block_ids": [third],
                    "confidence": 0.8,
                },
            ],
            "objections_and_limits": [
                {
                    "statement": "Mock source-grounded objection",
                    "source_block_ids": [third],
                    "response": "Mock response in source",
                }
            ],
            "position_owners": [{"owner": "author", "role": "narrator"}],
            "recommended_node_types": [
                "chapter_objective",
                "organising_idea",
                "central_claim",
                "supporting_claim",
                "reasoning_step",
                "evidence",
                "example",
                "objection",
                "response",
                "one_sentence_decode",
                "chapter_question",
            ],
            "omit_or_deemphasize": ["analogy", "historical_context", "external_counter"],
            "unresolved_questions": [],
            "confidence_summary": {
                "overall": 0.8,
                "notes": "Generated by MockLLMClient discovery (LLM_MOCK=true).",
            },
            "conflicts": [],
        }

    def _mock_discovery_merge(self, prompt: str) -> dict[str, Any]:
        merged = self._mock_discovery(prompt)
        merged["confidence_summary"] = {
            "overall": 0.78,
            "notes": "Generated by MockLLMClient discovery merge (LLM_MOCK=true).",
        }
        return merged

    def _mock_adaptive_synthesis(self, prompt: str) -> dict[str, Any]:
        block_ids = re.findall(r'"block_id"\s*:\s*"([^"]+)"', prompt)
        if not block_ids:
            block_ids = re.findall(r'"source_block_ids"\s*:\s*\["([^"]+)"', prompt)
        ids = block_ids[:6] if block_ids else ["b1"]
        first = ids[0]
        second = ids[1] if len(ids) > 1 else first
        third = ids[2] if len(ids) > 2 else first
        fourth = ids[3] if len(ids) > 3 else first
        book_id, chapter_id = "mock-book", "ch01"
        try:
            for marker in (
                "===SYNTHESIS_SOURCE_BLOCKS_JSON===",
                "===SOURCE_BLOCKS_JSON===",
            ):
                if marker in prompt:
                    raw = prompt.split(marker, 1)[1].strip()
                    # User message may contain a second JSON blob after discovery marker.
                    decoder = json.JSONDecoder()
                    payload, _ = decoder.raw_decode(raw)
                    if isinstance(payload, dict):
                        book_id = payload.get("book_id") or book_id
                        chapter_id = payload.get("chapter_id") or chapter_id
                        blocks = payload.get("blocks") or []
                        if blocks:
                            ids = [
                                b["block_id"] for b in blocks if b.get("block_id")
                            ][:6] or ids
                            first = ids[0]
                            second = ids[1] if len(ids) > 1 else first
                            third = ids[2] if len(ids) > 2 else first
                            fourth = ids[3] if len(ids) > 3 else first
                    break
        except Exception:
            logger.debug("Mock adaptive synthesis meta parse fallback", exc_info=True)

        nodes = [
            {
                "id": "tmp-n01",
                "node_type": "chapter_objective",
                "order": 0,
                "statement_en": "Understand the chapter's organising argument",
                "statement_hinglish": None,
                "explanation_en": "Derived from discovery + source.",
                "explanation_hinglish": None,
                "source_status": "ai_inference",
                "source_block_ids": [first],
                "confidence": 0.8,
                "importance": "important",
                "warnings": ["mock_llm"],
            },
            {
                "id": "tmp-n02",
                "node_type": "organising_idea",
                "order": 1,
                "statement_en": "Mock organising idea from adaptive synthesis",
                "statement_hinglish": None,
                "explanation_en": "Grounded in source blocks.",
                "explanation_hinglish": None,
                "source_status": "author_paraphrase",
                "source_block_ids": [first],
                "confidence": 0.9,
                "claim_level": "chapter",
                "importance": "central",
                "warnings": ["mock_llm"],
            },
            {
                "id": "tmp-n03",
                "node_type": "central_claim",
                "order": 2,
                "statement_en": "Mock central claim from adaptive synthesis",
                "statement_hinglish": None,
                "explanation_en": "Primary claim.",
                "explanation_hinglish": None,
                "source_status": "author_paraphrase",
                "source_block_ids": [first],
                "confidence": 0.92,
                "claim_level": "chapter",
                "importance": "central",
                "warnings": ["mock_llm"],
            },
            {
                "id": "tmp-n04",
                "node_type": "reasoning_step",
                "order": 3,
                "statement_en": "Mock reasoning step",
                "statement_hinglish": None,
                "explanation_en": "Links claim to evidence.",
                "explanation_hinglish": None,
                "source_status": "source_based_inference",
                "source_block_ids": [second],
                "supports_node_ids": ["tmp-n03"],
                "confidence": 0.85,
                "warnings": ["mock_llm"],
            },
            {
                "id": "tmp-n05",
                "node_type": "evidence",
                "order": 4,
                "statement_en": "Mock evidence node",
                "statement_hinglish": None,
                "explanation_en": "Supports the claim.",
                "explanation_hinglish": None,
                "source_status": "author_paraphrase",
                "source_block_ids": [third],
                "supports_node_ids": ["tmp-n03"],
                "confidence": 0.88,
                "warnings": ["mock_llm"],
            },
            {
                "id": "tmp-n06",
                "node_type": "example",
                "order": 5,
                "statement_en": "Mock example node",
                "statement_hinglish": None,
                "explanation_en": "Illustrates the claim.",
                "explanation_hinglish": None,
                "source_status": "author_paraphrase",
                "source_block_ids": [third],
                "confidence": 0.8,
                "warnings": ["mock_llm"],
            },
            {
                "id": "tmp-n07",
                "node_type": "objection",
                "order": 6,
                "statement_en": "Mock source-grounded objection",
                "statement_hinglish": None,
                "explanation_en": "Position discussed in source.",
                "explanation_hinglish": None,
                "source_status": "quoted_position",
                "source_block_ids": [fourth],
                "position_owner": "interlocutor in source",
                "confidence": 0.82,
                "warnings": ["mock_llm"],
            },
            {
                "id": "tmp-n08",
                "node_type": "response",
                "order": 7,
                "statement_en": "Mock response to the objection",
                "statement_hinglish": None,
                "explanation_en": "Author's reply in source.",
                "explanation_hinglish": None,
                "source_status": "source_based_objection",
                "source_block_ids": [fourth],
                "confidence": 0.8,
                "warnings": ["mock_llm"],
            },
            {
                "id": "tmp-n09",
                "node_type": "one_sentence_decode",
                "order": 8,
                "statement_en": (
                    "The chapter argues a clear organising claim with support "
                    "and a source-grounded objection."
                ),
                "statement_hinglish": None,
                "explanation_en": "Decode summary.",
                "explanation_hinglish": None,
                "source_status": "ai_inference",
                "source_block_ids": [first, second],
                "confidence": 0.86,
                "warnings": ["mock_llm"],
            },
            {
                "id": "tmp-n10",
                "node_type": "chapter_question",
                "order": 9,
                "statement_en": (
                    "What is the chapter's organising claim and how is it supported?"
                ),
                "statement_hinglish": None,
                "explanation_en": "Study prompt.",
                "explanation_hinglish": None,
                "source_status": "ai_inference",
                "source_block_ids": [first],
                "confidence": 0.84,
                "warnings": ["mock_llm"],
            },
        ]
        return {
            "schema_version": "2.0",
            "book_id": book_id,
            "chapter_id": chapter_id,
            "language_modes": ["en"],
            "nodes": nodes,
            "relations": [
                {
                    "from_node_id": "tmp-n04",
                    "to_node_id": "tmp-n03",
                    "relation_type": "supports",
                    "explanation_en": "Reasoning supports claim",
                    "source_block_ids": [second],
                },
                {
                    "from_node_id": "tmp-n05",
                    "to_node_id": "tmp-n03",
                    "relation_type": "provides_evidence_for",
                    "explanation_en": "Evidence supports claim",
                    "source_block_ids": [third],
                },
                {
                    "from_node_id": "tmp-n07",
                    "to_node_id": "tmp-n03",
                    "relation_type": "challenges",
                    "explanation_en": "Objection challenges claim",
                    "source_block_ids": [fourth],
                },
                {
                    "from_node_id": "tmp-n08",
                    "to_node_id": "tmp-n07",
                    "relation_type": "responds_to",
                    "explanation_en": "Response answers objection",
                    "source_block_ids": [fourth],
                },
            ],
            "confidence_summary": {
                "overall": 0.84,
                "notes": "Generated by MockLLMClient adaptive synthesis (LLM_MOCK=true).",
            },
            "processing": {
                "model": "mock",
                "prompt_versions": {"argument_spine_adaptive_synthesis": "4.0.0"},
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


class CachingLLMClient:
    """Best-effort disk cache around an LLM client (content-hash keyed)."""

    def __init__(self, inner: LLMClient, settings: Settings) -> None:
        self.inner = inner
        self.settings = settings

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float | None = None,
        pass_name: str | None = None,
    ) -> dict[str, Any]:
        import hashlib
        from pathlib import Path

        cache_dir = Path(self.settings.llm_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        model = self.settings.llm_model if not self.settings.llm_mock else "mock"
        temp = (
            float(temperature)
            if temperature is not None
            else float(self.settings.llm_temperature)
        )
        key_material = "|".join(
            [
                pass_name or "complete_json",
                model,
                f"{temp:.3f}",
                system,
                user,
            ]
        )
        digest = hashlib.sha256(key_material.encode("utf-8")).hexdigest()
        path = cache_dir / f"{digest}.json"
        if path.exists():
            try:
                cached = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(cached, dict):
                    return cached
            except Exception:
                logger.exception("LLM cache read failed path=%s", path)

        max_attempts = max(1, int(self.settings.llm_json_max_retries) + 1)
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                # Inner clients may not accept pass_name
                result = self.inner.complete_json(
                    system=system, user=user, temperature=temperature
                )
                try:
                    path.write_text(
                        json.dumps(result, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                except Exception:
                    logger.exception("LLM cache write failed path=%s", path)
                return result
            except LLMError as exc:
                last_exc = exc
                if "invalid JSON" not in str(exc).lower() or attempt >= max_attempts:
                    raise
                logger.warning(
                    "LLM JSON parse retry %s/%s pass=%s: %s",
                    attempt,
                    max_attempts,
                    pass_name,
                    exc,
                )
        assert last_exc is not None
        raise last_exc


def _apply_provider_defaults(settings: Settings) -> Settings:
    """Apply Anthropic base/model defaults when still on OpenAI or retired IDs."""
    updates: dict[str, Any] = {}
    if settings.llm_api_base.rstrip("/") == DEFAULT_OPENAI_BASE.rstrip("/"):
        updates["llm_api_base"] = DEFAULT_ANTHROPIC_BASE
    model = settings.llm_model
    if model == DEFAULT_OPENAI_MODEL:
        updates["llm_model"] = DEFAULT_ANTHROPIC_MODEL
    elif model in RETIRED_ANTHROPIC_MODELS:
        updates["llm_model"] = RETIRED_ANTHROPIC_MODELS[model]
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
        client: LLMClient = MockLLMClient(settings)
    else:
        resolved = resolve_llm_settings(settings)
        provider = (resolved.llm_provider or "openai").strip().lower()
        if provider not in VALID_PROVIDERS:
            raise LLMError(
                f"Unknown LLM_PROVIDER={settings.llm_provider!r}. "
                f"Use one of: {', '.join(sorted(VALID_PROVIDERS))}."
            )

        if provider == "anthropic":
            client = AnthropicClient(resolved)
        else:
            # openai and openai_compatible share the Chat Completions client
            client = OpenAICompatibleClient(resolved)

    if settings.llm_cache_enabled:
        return CachingLLMClient(client, settings)
    return client
