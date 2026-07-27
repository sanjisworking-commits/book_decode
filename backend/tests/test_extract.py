"""Phase 3 extraction / validation / multi-provider LLM unit tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.config import Settings
from app.pipelines.validate_spine import (
    strip_invalid_source_refs,
    validate_source_refs,
    validate_spine_schema,
)
from app.services.llm import (
    AnthropicClient,
    LLMError,
    MockLLMClient,
    OpenAICompatibleClient,
    _httpx_timeout,
    get_llm_client,
    parse_json_content,
    resolve_llm_settings,
)


def test_parse_json_content_strips_fences() -> None:
    data = parse_json_content('```json\n{"a": 1}\n```')
    assert data == {"a": 1}


def test_parse_json_unterminated_string_hints_truncation() -> None:
    with pytest.raises(LLMError, match="truncated|LLM_MAX_TOKENS"):
        parse_json_content('{"statement_en": "this never ends')


def test_anthropic_rejects_max_tokens_stop_reason() -> None:
    settings = Settings(
        llm_provider="anthropic",
        llm_api_key="sk-ant-test",
        llm_api_base="https://api.anthropic.com",
        llm_model="claude-sonnet-4-6",
        llm_max_tokens=8192,
    )
    client = AnthropicClient(settings)
    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json.return_value = {
        "stop_reason": "max_tokens",
        "content": [
            {
                "type": "text",
                "text": '{"nodes": [{"statement_en": "cut off"}]}',
            }
        ],
    }
    fake_http = MagicMock()
    fake_http.__enter__.return_value = fake_http
    fake_http.post.return_value = fake_resp

    with patch("app.services.llm.httpx.Client", return_value=fake_http):
        with pytest.raises(LLMError, match="truncated at max_tokens"):
            client.complete_json(system="sys", user="user")


def test_mock_llm_returns_schema_shaped_spine() -> None:
    settings = Settings(llm_mock=True)
    client = MockLLMClient(settings)
    user = (
        "Extract...\n===SOURCE_BLOCKS_JSON===\n"
        + json.dumps(
            {
                "book_id": "b1",
                "chapter_id": "ch01",
                "blocks": [
                    {
                        "block_id": "b1.ch01.sec01.block001",
                        "block_type": "paragraph",
                        "text": "Authors argue that local circuits matter.",
                    }
                ],
            }
        )
    )
    spine = client.complete_json(system="sys", user=user)
    assert spine["book_id"] == "b1"
    assert spine["chapter_id"] == "ch01"
    assert spine["language_modes"] == ["en"]
    errors = validate_spine_schema(spine)
    assert errors == [], errors
    allowed = {"b1.ch01.sec01.block001"}
    assert validate_source_refs(spine, allowed) == []


def test_strip_invalid_source_refs() -> None:
    spine = {
        "schema_version": "1.0",
        "book_id": "b1",
        "chapter_id": "ch01",
        "language_modes": ["en"],
        "nodes": [
            {
                "id": "n1",
                "node_type": "central_claim",
                "statement_en": "Claim",
                "source_status": "ai_inference",
                "source_block_ids": ["ok.block", "bad.block"],
                "order": 0,
            }
        ],
    }
    cleaned = strip_invalid_source_refs(spine, {"ok.block"})
    assert cleaned["nodes"][0]["source_block_ids"] == ["ok.block"]
    assert any("removed_" in w for w in cleaned["nodes"][0]["warnings"])


def test_factory_returns_mock() -> None:
    client = get_llm_client(Settings(llm_mock=True))
    assert isinstance(client, MockLLMClient)


def test_oneshot_block_budget_auto_caps_groq() -> None:
    groq = Settings(
        llm_api_base="https://api.groq.com/openai/v1",
        llm_model="llama-3.3-70b-versatile",
        chunk_token_limit=20000,
        llm_max_input_tokens=0,
        llm_max_tokens=8192,
    )
    # TPM 12k → max_tokens clamped to 35% (4200), prompt = 12k - 4200 - 500
    assert groq.effective_llm_max_tokens() == 4200
    assert groq.extract_prompt_token_budget() == 7300
    assert groq.effective_llm_max_tokens() + groq.extract_prompt_token_budget() <= 12000
    scout = Settings(
        llm_api_base="https://api.groq.com/openai/v1",
        llm_model="meta-llama/llama-4-scout-17b-16e-instruct",
        llm_max_input_tokens=0,
        llm_max_tokens=8192,
    )
    assert scout.effective_llm_max_tokens() == 8192  # 35% of 30k = 10500, min(8192,10500)
    assert scout.extract_prompt_token_budget() == 30000 - 8192 - 500
    anthropic = Settings(
        llm_api_base="https://api.anthropic.com",
        chunk_token_limit=20000,
        llm_max_input_tokens=0,
        llm_max_tokens=16384,
    )
    assert anthropic.effective_llm_max_tokens() == 16384
    assert anthropic.extract_prompt_token_budget() == 24000
    explicit = Settings(
        llm_api_base="https://api.groq.com/openai/v1",
        llm_model="llama-3.3-70b-versatile",
        llm_max_input_tokens=5000,
        llm_max_tokens=8192,
    )
    assert explicit.extract_prompt_token_budget() == 5000


def test_groq_prompt_plus_max_tokens_under_tpm() -> None:
    """Regression: Requested 15389 was ~7.2k prompt + 8192 max_tokens."""
    s = Settings(
        llm_api_base="https://api.groq.com/openai/v1",
        llm_model="llama-3.3-70b-versatile",
        llm_max_tokens=8192,
        llm_max_input_tokens=0,
    )
    assert s.extract_prompt_token_budget() + s.effective_llm_max_tokens() <= 12000


def test_http_413_mentions_input_budget_hint() -> None:
    settings = Settings(
        llm_provider="openai_compatible",
        llm_api_base="https://api.groq.com/openai/v1",
        llm_api_key="gsk-test",
        llm_model="llama-3.3-70b-versatile",
        llm_http_retries=0,
    )
    client = OpenAICompatibleClient(settings)
    fake_resp = MagicMock()
    fake_resp.status_code = 413
    fake_resp.text = '{"error":{"message":"Request too large","code":"rate_limit_exceeded"}}'
    err = httpx.HTTPStatusError("413", request=MagicMock(), response=fake_resp)
    fake_http = MagicMock()
    fake_http.__enter__.return_value = fake_http
    fake_http.post.side_effect = err

    with patch("app.services.llm.httpx.Client", return_value=fake_http):
        with pytest.raises(LLMError, match="LLM_MAX_INPUT_TOKENS"):
            client.complete_json(system="sys", user="user")


def test_factory_returns_openai_compatible() -> None:
    client = get_llm_client(
        Settings(llm_mock=False, llm_provider="openai", llm_api_key="sk-test")
    )
    assert isinstance(client, OpenAICompatibleClient)


def test_factory_returns_openai_compatible_for_gateway() -> None:
    client = get_llm_client(
        Settings(
            llm_mock=False,
            llm_provider="openai_compatible",
            llm_api_base="https://api.groq.com/openai/v1",
            llm_api_key="gsk-test",
            llm_model="llama-3.3-70b-versatile",
        )
    )
    assert isinstance(client, OpenAICompatibleClient)


def test_factory_returns_anthropic() -> None:
    client = get_llm_client(
        Settings(llm_mock=False, llm_provider="anthropic", llm_api_key="sk-ant-test")
    )
    assert isinstance(client, AnthropicClient)


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(LLMError, match="Unknown LLM_PROVIDER"):
        get_llm_client(Settings(llm_mock=False, llm_provider="gemini_native", llm_api_key="x"))


def test_anthropic_defaults_when_openai_base_left() -> None:
    resolved = resolve_llm_settings(
        Settings(
            llm_provider="anthropic",
            llm_api_base="https://api.openai.com/v1",
            llm_model="gpt-4o",
            llm_api_key="sk-ant-test",
        )
    )
    assert resolved.llm_api_base == "https://api.anthropic.com"
    assert resolved.llm_model == "claude-sonnet-4-6"


def test_anthropic_remaps_retired_sonnet_4_model() -> None:
    resolved = resolve_llm_settings(
        Settings(
            llm_provider="anthropic",
            llm_api_base="https://api.anthropic.com",
            llm_model="claude-sonnet-4-20250514",
            llm_api_key="sk-ant-test",
        )
    )
    assert resolved.llm_model == "claude-sonnet-4-6"


def test_openai_compatible_client_parses_chat_completions() -> None:
    settings = Settings(
        llm_provider="openai",
        llm_api_key="sk-test",
        llm_api_base="https://api.openai.com/v1",
        llm_model="gpt-4o",
    )
    client = OpenAICompatibleClient(settings)
    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json.return_value = {
        "choices": [{"message": {"content": '{"hello": "world"}'}}]
    }
    fake_http = MagicMock()
    fake_http.__enter__.return_value = fake_http
    fake_http.post.return_value = fake_resp

    with patch("app.services.llm.httpx.Client", return_value=fake_http):
        data = client.complete_json(system="sys", user="user")

    assert data == {"hello": "world"}
    args, kwargs = fake_http.post.call_args
    assert args[0].endswith("/chat/completions")
    assert kwargs["headers"]["Authorization"] == "Bearer sk-test"
    assert kwargs["json"]["response_format"] == {"type": "json_object"}


def test_anthropic_client_parses_messages_api() -> None:
    settings = Settings(
        llm_provider="anthropic",
        llm_api_key="sk-ant-test",
        llm_api_base="https://api.anthropic.com",
        llm_model="claude-sonnet-4-6",
    )
    client = AnthropicClient(settings)
    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json.return_value = {
        "content": [{"type": "text", "text": '{"ok": true}'}]
    }
    fake_http = MagicMock()
    fake_http.__enter__.return_value = fake_http
    fake_http.post.return_value = fake_resp

    with patch("app.services.llm.httpx.Client", return_value=fake_http):
        data = client.complete_json(system="sys", user="user")

    assert data == {"ok": True}
    args, kwargs = fake_http.post.call_args
    assert args[0] == "https://api.anthropic.com/v1/messages"
    assert kwargs["headers"]["x-api-key"] == "sk-ant-test"
    assert kwargs["headers"]["anthropic-version"] == "2023-06-01"
    assert kwargs["json"]["system"] == "sys"
    assert kwargs["json"]["messages"] == [{"role": "user", "content": "user"}]


def test_anthropic_retries_on_read_timeout() -> None:
    settings = Settings(
        llm_provider="anthropic",
        llm_api_key="sk-ant-test",
        llm_api_base="https://api.anthropic.com",
        llm_model="claude-sonnet-4-6",
        llm_timeout_seconds=90,
        llm_http_retries=2,
    )
    client = AnthropicClient(settings)
    ok_resp = MagicMock()
    ok_resp.raise_for_status = MagicMock()
    ok_resp.json.return_value = {
        "content": [{"type": "text", "text": '{"ok": true}'}]
    }
    fake_http = MagicMock()
    fake_http.__enter__.return_value = fake_http
    fake_http.post.side_effect = [
        httpx.ReadTimeout("The read operation timed out."),
        ok_resp,
    ]

    with patch("app.services.llm.httpx.Client", return_value=fake_http):
        with patch("time.sleep"):
            data = client.complete_json(system="sys", user="user")

    assert data == {"ok": True}
    assert fake_http.post.call_count == 2
    assert float(_httpx_timeout(settings).read) == 90.0


def test_httpx_timeout_defaults_to_300() -> None:
    assert float(_httpx_timeout(Settings()).read) == 300.0
