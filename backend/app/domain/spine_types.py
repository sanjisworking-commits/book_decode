"""Shared Argument Spine / discovery type constants and alias normalisation."""

from __future__ import annotations

NODE_TYPE_ALIASES: dict[str, str] = {
    "reasoning_steps": "reasoning_step",
    "evidence_and_examples": "evidence",
    "hidden_assumptions": "assumption",
    "strongest_counter_position": "objection",
    "consequence_if_correct": "implication",
    "tensions_or_gaps": "qualification",
    "confidence_and_unresolved": "unresolved_question",
}

CANONICAL_NODE_TYPES = frozenset(
    {
        "chapter_objective",
        "chapter_question",
        "central_claim",
        "organising_idea",
        "supporting_claim",
        "reasoning_step",
        "definition",
        "evidence",
        "example",
        "analogy",
        "quotation",
        "assumption",
        "qualification",
        "objection",
        "response",
        "implication",
        "narrative_context",
        "historical_context",
        "transition",
        "role_in_book",
        "one_sentence_decode",
        "unresolved_question",
        "source_block_references",
        # legacy accepted until postprocess
        "reasoning_steps",
        "evidence_and_examples",
        "hidden_assumptions",
        "tensions_or_gaps",
        "strongest_counter_position",
        "consequence_if_correct",
        "confidence_and_unresolved",
    }
)

SOURCE_STATUS_VALUES = frozenset(
    {
        "explicit_author",
        "author_paraphrase",
        "ai_inference",
        "external_counter",
        "quoted_position",
        "source_based_inference",
        "source_based_objection",
    }
)

RELATION_TYPES = frozenset(
    {
        "supports",
        "explains",
        "provides_evidence_for",
        "illustrates",
        "defines",
        "qualifies",
        "challenges",
        "responds_to",
        "depends_on",
        "leads_to",
        "contrasts_with",
        "provides_context_for",
    }
)

CHAPTER_TYPES = frozenset(
    {
        "theoretical_argument",
        "conceptual_framework",
        "historical_explanation",
        "comparative_argument",
        "evidence_review",
        "narrative_supported_argument",
        "procedural_explanation",
        "descriptive_explanation",
        "mixed",
    }
)


def normalise_node_type(raw: str | None) -> str | None:
    if not raw:
        return None
    t = str(raw).strip()
    return NODE_TYPE_ALIASES.get(t, t)


def normalise_source_status(raw: str | None) -> str:
    if not raw:
        return "ai_inference"
    s = str(raw).strip()
    if s in SOURCE_STATUS_VALUES:
        return s
    # Defensive mapping for older / loose labels
    aliases = {
        "quoted": "quoted_position",
        "quote": "quoted_position",
        "inference": "source_based_inference",
        "objection": "source_based_objection",
        "external": "external_counter",
    }
    return aliases.get(s, "ai_inference")
