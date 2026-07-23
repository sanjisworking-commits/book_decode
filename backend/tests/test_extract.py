"""Phase 3 extraction / validation / multi-provider LLM unit tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

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
    get_llm_client,
    parse_json_content,
    resolve_llm_settings,
)


def test_parse_json_content_strips_fences() -> None:
    data = parse_json_content('```json\n{"a": 1}\n```')
    assert data == {"a": 1}


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
    assert resolved.llm_model == "claude-sonnet-4-20250514"


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
        llm_model="claude-sonnet-4-20250514",
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
