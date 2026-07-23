"""Phase 3 extraction / validation unit tests."""

from __future__ import annotations

import json

from app.config import Settings
from app.pipelines.validate_spine import (
    strip_invalid_source_refs,
    validate_source_refs,
    validate_spine_schema,
)
from app.services.llm import MockLLMClient, parse_json_content


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
