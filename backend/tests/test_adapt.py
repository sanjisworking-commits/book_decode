"""Phase 5 Hindi-English adaptation / alignment tests."""

from __future__ import annotations

import copy
import json

from app.config import Settings
from app.pipelines.align_spine import (
    apply_hinglish_fields,
    check_bilingual_alignment,
    mock_adapt_spine,
)
from app.services.llm import MockLLMClient


def _english_spine() -> dict:
    return {
        "schema_version": "1.0",
        "book_id": "b1",
        "chapter_id": "ch01",
        "language_modes": ["en"],
        "nodes": [
            {
                "id": "ch01-n01",
                "node_type": "chapter_question",
                "statement_en": "What claim does this chapter advance?",
                "explanation_en": "Sets the chapter question.",
                "statement_hinglish": None,
                "explanation_hinglish": None,
                "source_status": "author_paraphrase",
                "source_block_ids": ["b1.ch01.sec01.block001"],
                "confidence": 0.7,
                "order": 0,
                "prev_id": None,
                "next_id": "ch01-n02",
                "warnings": [],
            },
            {
                "id": "ch01-n02",
                "node_type": "central_claim",
                "statement_en": "Local circuits form reference frames.",
                "explanation_en": "Core claim of the chapter.",
                "statement_hinglish": None,
                "explanation_hinglish": None,
                "source_status": "author_paraphrase",
                "source_block_ids": ["b1.ch01.sec01.block001", "b1.ch01.sec01.block002"],
                "confidence": 0.8,
                "order": 1,
                "prev_id": "ch01-n01",
                "next_id": None,
                "warnings": [],
            },
        ],
        "confidence_summary": {"overall": 0.75, "notes": "test"},
        "processing": {
            "model": "mock",
            "prompt_versions": {"argument_spine_synthesis": "4.0.0"},
            "created_at": None,
            "updated_at": None,
        },
        "validation": {
            "schema_valid": True,
            "source_refs_valid": True,
            "bilingual_aligned": False,
            "checked_at": None,
        },
    }


def test_mock_adapt_preserves_ids_and_types() -> None:
    english = _english_spine()
    bilingual = mock_adapt_spine(english)
    assert bilingual["language_modes"] == ["en", "hinglish"]
    assert [n["id"] for n in bilingual["nodes"]] == [n["id"] for n in english["nodes"]]
    assert [n["node_type"] for n in bilingual["nodes"]] == [
        n["node_type"] for n in english["nodes"]
    ]
    assert check_bilingual_alignment(english, bilingual) == []
    for node in bilingual["nodes"]:
        assert node["statement_hinglish"]
        assert node["explanation_hinglish"]
        assert node["statement_en"]  # English retained


def test_alignment_detects_dropped_node() -> None:
    english = _english_spine()
    bilingual = mock_adapt_spine(english)
    bilingual["nodes"] = bilingual["nodes"][:1]
    errors = check_bilingual_alignment(english, bilingual)
    assert any("missing node id" in e for e in errors)


def test_alignment_detects_changed_source_ids() -> None:
    english = _english_spine()
    bilingual = mock_adapt_spine(english)
    bilingual["nodes"][0]["source_block_ids"] = ["evil"]
    errors = check_bilingual_alignment(english, bilingual)
    assert any("source_block_ids changed" in e for e in errors)


def test_apply_hinglish_fields_does_not_rewrite_english() -> None:
    english = _english_spine()
    adapted = mock_adapt_spine(english)
    # Corrupt English in adapted payload — merge must ignore it
    adapted["nodes"][0]["statement_en"] = "CHANGED ENGLISH CLAIM"
    adapted["nodes"][0]["id"] = "hijacked"
    merged = apply_hinglish_fields(english, adapted)
    # First node keeps English id/text; hinglish only applied when ids match
    assert merged["nodes"][0]["id"] == "ch01-n01"
    assert merged["nodes"][0]["statement_en"] == english["nodes"][0]["statement_en"]
    # Because adapted ids were hijacked, hinglish for n01 may be missing from overlay
    # Restore proper adapted and re-check overlay
    adapted2 = mock_adapt_spine(english)
    merged2 = apply_hinglish_fields(english, adapted2)
    assert merged2["nodes"][0]["statement_hinglish"]
    assert merged2["nodes"][0]["statement_en"] == english["nodes"][0]["statement_en"]
    assert check_bilingual_alignment(english, merged2) == []


def test_mock_llm_adapt_path() -> None:
    client = MockLLMClient(Settings(llm_mock=True))
    english = _english_spine()
    user = (
        "Adapt...\n===ENGLISH_SPINE_JSON===\n"
        + json.dumps({"spine": english, "style": {}})
    )
    out = client.complete_json(system="sys", user=user)
    assert out["language_modes"] == ["en", "hinglish"]
    assert [n["id"] for n in out["nodes"]] == [n["id"] for n in english["nodes"]]
    assert check_bilingual_alignment(english, out) == []


def test_no_id_drops_across_adaptation() -> None:
    english = _english_spine()
    before = {n["id"] for n in english["nodes"]}
    after = {n["id"] for n in mock_adapt_spine(copy.deepcopy(english))["nodes"]}
    assert before == after
