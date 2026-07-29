"""Contracts for evidence-linked knowledge graph extraction."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

_STABLE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{2,127}$")


class KnowledgeEntityType(StrEnum):
    PERSON = "person"
    ORGANIZATION = "organization"
    PLACE = "place"
    DOCUMENT = "document"
    LAW = "law"
    CONCEPT = "concept"
    DATE = "date"
    EVENT = "event"
    UNKNOWN = "unknown"


class KnowledgeRelationType(StrEnum):
    REFERENCES = "references"
    DEFINES = "defines"
    AMENDS = "amends"
    REPEALS = "repeals"
    APPLIES_TO = "applies_to"
    DEPENDS_ON = "depends_on"
    SAME_AS = "same_as"
    PART_OF = "part_of"
    RELATED_TO = "related_to"


def _normalize_name(value: str) -> str:
    return " ".join(value.casefold().split())


class KnowledgeEntity(BaseModel):
    entity_id: str
    canonical_name: str = Field(min_length=1, max_length=500)
    entity_type: KnowledgeEntityType = KnowledgeEntityType.UNKNOWN
    aliases: list[str] = Field(default_factory=list, max_length=50)
    description: str | None = Field(default=None, max_length=5000)
    metadata: dict[str, str] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(min_length=1, max_length=50)
    normalized_name: str | None = None

    @field_validator("entity_id")
    @classmethod
    def validate_entity_id(cls, value: str) -> str:
        if not _STABLE_ID_RE.fullmatch(value):
            raise ValueError(
                "entity_id must use upper-case letters, numbers, underscores or hyphens"
            )
        return value

    @field_validator("canonical_name")
    @classmethod
    def strip_canonical_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(alias.strip() for alias in value if alias.strip()))

    @model_validator(mode="after")
    def set_normalized_name(self) -> "KnowledgeEntity":
        self.normalized_name = _normalize_name(self.canonical_name)
        return self


class KnowledgeRelation(BaseModel):
    relation_id: str
    subject_entity_id: str
    object_entity_id: str
    relation_type: KnowledgeRelationType
    confidence: float = Field(default=1.0, ge=0, le=1)
    evidence_ids: list[str] = Field(min_length=1, max_length=50)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("relation_id", "subject_entity_id", "object_entity_id")
    @classmethod
    def validate_graph_id(cls, value: str) -> str:
        if not _STABLE_ID_RE.fullmatch(value):
            raise ValueError(
                "graph identifiers must use upper-case letters, numbers, underscores or hyphens"
            )
        return value

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence_ids(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_endpoints(self) -> "KnowledgeRelation":
        if self.subject_entity_id == self.object_entity_id:
            raise ValueError("knowledge graph relations cannot be self-referential")
        return self


class KnowledgeGraphExtraction(BaseModel):
    """A bounded graph fragment extracted from a closed evidence set."""

    evidence_ids: list[str] = Field(min_length=1, max_length=50)
    entities: list[KnowledgeEntity] = Field(min_length=1, max_length=200)
    relations: list[KnowledgeRelation] = Field(default_factory=list, max_length=500)
    extractor_version: str = Field(default="phase-6-contract", min_length=1, max_length=100)

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence_ids(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_graph_fragment(self) -> "KnowledgeGraphExtraction":
        entity_ids = {entity.entity_id for entity in self.entities}
        if len(entity_ids) != len(self.entities):
            raise ValueError("knowledge graph entity IDs must be unique")
        relation_ids = {relation.relation_id for relation in self.relations}
        if len(relation_ids) != len(self.relations):
            raise ValueError("knowledge graph relation IDs must be unique")
        allowed_evidence_ids = set(self.evidence_ids)
        for entity in self.entities:
            if not set(entity.evidence_ids).issubset(allowed_evidence_ids):
                raise ValueError(
                    f"entity references evidence outside the extraction set: "
                    f"{entity.entity_id}"
                )
        for relation in self.relations:
            if relation.subject_entity_id not in entity_ids:
                raise ValueError(
                    f"relation subject is not present: {relation.subject_entity_id}"
                )
            if relation.object_entity_id not in entity_ids:
                raise ValueError(
                    f"relation object is not present: {relation.object_entity_id}"
                )
            if not set(relation.evidence_ids).issubset(set(self.evidence_ids)):
                raise ValueError(
                    f"relation references evidence outside the extraction set: "
                    f"{relation.relation_id}"
                )
        return self


class KnowledgeGraphPersistenceResult(BaseModel):
    entities_upserted: int
    relations_upserted: int
    evidence_links_upserted: int
    evidence_ids: list[str]
