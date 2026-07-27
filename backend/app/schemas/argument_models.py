"""Light Pydantic helpers for Argument Discovery / Spine v2 repair paths."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DiscoveryClaim(BaseModel):
    model_config = ConfigDict(extra="allow")

    claim_id: str
    statement: str
    claim_level: str | None = None
    position_owner: str | None = None
    source_status: str | None = None
    source_block_ids: list[str] = Field(default_factory=list)
    confidence: float | None = None


class DiscoverySupportItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    item_id: str
    material_type: str
    statement: str
    supports_claim_ids: list[str] = Field(default_factory=list)
    source_block_ids: list[str] = Field(default_factory=list)
    confidence: float | None = None


class ArgumentDiscoveryModel(BaseModel):
    """Subset of discovery schema useful for repair / shape checks."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "1.0"
    book_id: str
    chapter_id: str
    chapter_types: list[str] = Field(default_factory=list)
    argument_movements: list[dict[str, Any]] = Field(default_factory=list)
    claims: list[DiscoveryClaim] = Field(default_factory=list)
    supporting_material: list[DiscoverySupportItem] = Field(default_factory=list)
    recommended_node_types: list[str] = Field(default_factory=list)
    omit_or_deemphasize: list[str] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)


class SpineRelationModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    from_node_id: str
    to_node_id: str
    relation_type: str
    explanation_en: str | None = None
    source_block_ids: list[str] = Field(default_factory=list)


class SpineNodeModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    node_type: str
    statement_en: str | None = None
    explanation_en: str | None = None
    statement_hinglish: str | None = None
    explanation_hinglish: str | None = None
    source_status: str = "ai_inference"
    source_block_ids: list[str] = Field(default_factory=list)
    order: int = 0
    custom_label: str | None = None
    claim_level: str | None = None
    importance: str | None = None
    position_owner: str | None = None
    narrating_voice: str | None = None
    scope_qualifiers: list[str] = Field(default_factory=list)
    supports_node_ids: list[str] = Field(default_factory=list)
    supports_claim_ids: list[str] = Field(default_factory=list)
    confidence: float | None = None
    warnings: list[str] = Field(default_factory=list)


class ArgumentSpineModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = "2.0"
    book_id: str
    chapter_id: str
    language_modes: list[str] = Field(default_factory=lambda: ["en"])
    nodes: list[SpineNodeModel] = Field(default_factory=list)
    relations: list[SpineRelationModel] = Field(default_factory=list)
