"""Phase 4 synthesis / merge unit tests."""

from __future__ import annotations

from app.pipelines.merge_spines import (
    claim_supported_by_partials,
    collect_claim_statements,
    merge_partial_spines,
    statements_equivalent,
)
from app.pipelines.validate_spine import validate_source_refs
from app.config import Settings
from app.services.llm import MockLLMClient
import json


def _partial(
    *,
    book_id: str,
    chapter_id: str,
    claim: str,
    evidence: str,
    block_ids: list[str],
    extra_claim: str | None = None,
) -> dict:
    nodes = [
        {
            "id": f"{chapter_id}-n01",
            "node_type": "chapter_question",
            "statement_en": "What claim does this chapter advance?",
            "source_status": "author_paraphrase",
            "source_block_ids": block_ids[:1],
            "order": 0,
            "warnings": [],
        },
        {
            "id": f"{chapter_id}-n02",
            "node_type": "central_claim",
            "statement_en": claim,
            "source_status": "author_paraphrase",
            "source_block_ids": block_ids[:1],
            "order": 1,
            "warnings": [],
        },
        {
            "id": f"{chapter_id}-n03",
            "node_type": "evidence_and_examples",
            "statement_en": evidence,
            "source_status": "author_paraphrase",
            "source_block_ids": block_ids,
            "order": 2,
            "warnings": [],
        },
        {
            "id": f"{chapter_id}-n04",
            "node_type": "one_sentence_decode",
            "statement_en": "This chapter contributes one step in the book's overall argument.",
            "source_status": "ai_inference",
            "source_block_ids": block_ids[:1],
            "order": 3,
            "warnings": [],
        },
    ]
    if extra_claim:
        nodes.append(
            {
                "id": f"{chapter_id}-n99",
                "node_type": "tensions_or_gaps",
                "statement_en": extra_claim,
                "source_status": "ai_inference",
                "source_block_ids": block_ids[-1:],
                "order": 4,
                "warnings": [],
            }
        )
    return {
        "schema_version": "1.0",
        "book_id": book_id,
        "chapter_id": chapter_id,
        "language_modes": ["en"],
        "nodes": nodes,
    }


def test_statements_equivalent_dedupes_near_duplicates() -> None:
    a = "Local circuits form reference frames in the neocortex."
    b = "Local circuits form reference frames in the neocortex"
    assert statements_equivalent(a, b)


def test_merge_removes_duplicate_claims_and_unions_refs() -> None:
    allowed = {"b.ch01.sec01.block001", "b.ch01.sec01.block002", "b.ch01.sec02.block003"}
    p1 = _partial(
        book_id="b",
        chapter_id="ch01",
        claim="Local circuits form reference frames in the neocortex.",
        evidence="Hawkins describes columns as voting.",
        block_ids=["b.ch01.sec01.block001", "b.ch01.sec01.block002"],
    )
    p2 = _partial(
        book_id="b",
        chapter_id="ch01",
        claim="Local circuits form reference frames in the neocortex",
        evidence="Voting across columns selects predictions.",
        block_ids=["b.ch01.sec01.block002", "b.ch01.sec02.block003"],
    )
    merged = merge_partial_spines(
        book_id="b", chapter_id="ch01", partials=[p1, p2], allowed_block_ids=allowed
    )
    claims = [n for n in merged["nodes"] if n["node_type"] == "central_claim"]
    assert len(claims) == 1
    assert set(claims[0]["source_block_ids"]) >= {
        "b.ch01.sec01.block001",
        "b.ch01.sec01.block002",
    }
    evidence = [n for n in merged["nodes"] if n["node_type"] == "evidence_and_examples"]
    assert len(evidence) == 1
    # Competing distinct evidence noted
    assert any("competing_interpretation" in w for w in evidence[0]["warnings"])
    assert validate_source_refs(merged, allowed) == []


def test_merge_preserves_competing_interpretation_warning() -> None:
    allowed = {"a", "b"}
    p1 = _partial(
        book_id="b",
        chapter_id="ch01",
        claim="Claim A about cortical columns voting.",
        evidence="Evidence from chunk one.",
        block_ids=["a"],
        extra_claim="The chapter leaves open how voting scales.",
    )
    p2 = _partial(
        book_id="b",
        chapter_id="ch01",
        claim="Claim B about maps being learned locally.",
        evidence="Evidence from chunk two.",
        block_ids=["b"],
        extra_claim="Scaling may require a different mechanism entirely.",
    )
    merged = merge_partial_spines(
        book_id="b", chapter_id="ch01", partials=[p1, p2], allowed_block_ids=allowed
    )
    central = next(n for n in merged["nodes"] if n["node_type"] == "central_claim")
    assert any("competing_interpretation" in w for w in central["warnings"])
    tensions = next(n for n in merged["nodes"] if n["node_type"] == "tensions_or_gaps")
    assert tensions["statement_en"]
    assert any("competing_interpretation" in w for w in tensions["warnings"])


def test_merge_does_not_introduce_new_source_ids() -> None:
    allowed = {"ok1", "ok2"}
    p1 = _partial(
        book_id="b",
        chapter_id="ch01",
        claim="A grounded claim from partial one.",
        evidence="Evidence one.",
        block_ids=["ok1"],
    )
    # Smuggle an invalid id in a partial — merge must filter to allow-list
    p1["nodes"][1]["source_block_ids"] = ["ok1", "evil.block"]
    p2 = _partial(
        book_id="b",
        chapter_id="ch01",
        claim="A grounded claim from partial one.",
        evidence="Evidence two.",
        block_ids=["ok2"],
    )
    merged = merge_partial_spines(
        book_id="b", chapter_id="ch01", partials=[p1, p2], allowed_block_ids=allowed
    )
    for node in merged["nodes"]:
        assert set(node["source_block_ids"]).issubset(allowed)


def test_no_new_claims_helper() -> None:
    partials = [
        _partial(
            book_id="b",
            chapter_id="ch01",
            claim="Reference frames are learned locally.",
            evidence="Columns vote.",
            block_ids=["x"],
        )
    ]
    claims = collect_claim_statements(partials)
    assert claim_supported_by_partials("Reference frames are learned locally.", claims)
    assert not claim_supported_by_partials(
        "Quantum entanglement explains cortical maps.", claims
    )


def test_mock_llm_synthesis_path() -> None:
    client = MockLLMClient(Settings(llm_mock=True))
    p1 = _partial(
        book_id="b",
        chapter_id="ch01",
        claim="Reference frames are learned locally in cortical columns.",
        evidence="Hawkins describes voting.",
        block_ids=["b.ch01.sec01.block001"],
    )
    p2 = _partial(
        book_id="b",
        chapter_id="ch01",
        claim="Reference frames are learned locally in cortical columns.",
        evidence="Maps form through sensorimotor sequences.",
        block_ids=["b.ch01.sec01.block002"],
    )
    user = (
        "Synthesise...\n===PARTIAL_SPINES_JSON===\n"
        + json.dumps(
            {
                "book_id": "b",
                "chapter_id": "ch01",
                "allow_listed_block_ids": [
                    "b.ch01.sec01.block001",
                    "b.ch01.sec01.block002",
                ],
                "partials": [p1, p2],
            }
        )
    )
    spine = client.complete_json(system="sys", user=user)
    assert spine["chapter_id"] == "ch01"
    assert spine["nodes"]
    # Schema may warn if not all 12 types present — still must have nodes
    assert all(n.get("statement_hinglish") is None for n in spine["nodes"])
    allowed = {"b.ch01.sec01.block001", "b.ch01.sec01.block002"}
    assert validate_source_refs(spine, allowed) == []


def test_multi_chunk_merge_yields_one_spine() -> None:
    allowed = {f"b.ch01.sec01.block{i:03d}" for i in range(1, 5)}
    partials = [
        _partial(
            book_id="b",
            chapter_id="ch01",
            claim="The neocortex learns reference frames.",
            evidence=f"Evidence chunk {i}.",
            block_ids=[f"b.ch01.sec01.block{i:03d}", f"b.ch01.sec01.block{i+1:03d}"],
        )
        for i in (1, 2, 3)
    ]
    merged = merge_partial_spines(
        book_id="b", chapter_id="ch01", partials=partials, allowed_block_ids=allowed
    )
    assert merged["schema_version"] == "1.0"
    assert merged["language_modes"] == ["en"]
    types = [n["node_type"] for n in merged["nodes"]]
    assert len(types) == len(set(types))
    assert "central_claim" in types
    # No new claims beyond partial statement set
    claims = collect_claim_statements(partials)
    for node in merged["nodes"]:
        assert claim_supported_by_partials(node.get("statement_en"), claims)
