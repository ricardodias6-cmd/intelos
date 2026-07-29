"""Persistent models for the evidence-linked knowledge graph."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import ConfigDict, Field, field_validator

from open_notebook.domain.evidence import (
    EvidenceObjectModel,
    RecordReference,
    _record_to_string,
    _validate_stable_id,
)
from open_notebook.knowledge_graph.models import (
    KnowledgeEntityType,
    KnowledgeRelationType,
)


class KnowledgeEntityRecord(EvidenceObjectModel):
    """Canonical entity persisted independently from its evidence links."""

    table_name: ClassVar[str] = "knowledge_entity"

    entity_id: str
    canonical_name: str
    normalized_name: str
    entity_type: KnowledgeEntityType = KnowledgeEntityType.UNKNOWN
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("entity_id")
    @classmethod
    def validate_entity_id(cls, value: str) -> str:
        return _validate_stable_id(value)

    @field_validator("canonical_name", "normalized_name")
    @classmethod
    def validate_names(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("entity names cannot be empty")
        return normalized

    def _prepare_save_data(self) -> dict[str, Any]:
        data = super()._prepare_save_data()
        data["entity_type"] = self.entity_type.value
        return data


class KnowledgeRelationRecord(EvidenceObjectModel):
    """Read model for one directed relation between two entities."""

    table_name: ClassVar[str] = "knowledge_relation"
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
    )

    relation_id: str
    source: RecordReference = Field(alias="in")
    target: RecordReference = Field(alias="out")
    relation_type: KnowledgeRelationType
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(min_length=1)
    metadata: dict[str, Any] | None = None

    @field_validator("relation_id")
    @classmethod
    def validate_relation_id(cls, value: str) -> str:
        return _validate_stable_id(value)

    def source_id(self) -> str:
        return _record_to_string(self.source)

    def target_id(self) -> str:
        return _record_to_string(self.target)
