from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from open_notebook.exceptions import InvalidInputError

from open_notebook.knowledge_graph import (
    KnowledgeEntity,
    KnowledgeGraphExtraction,
    KnowledgeRelation,
    extraction,
    persistence,
)


def _extraction() -> KnowledgeGraphExtraction:
    return KnowledgeGraphExtraction(
        evidence_ids=["EV_ONE"],
        entities=[
            KnowledgeEntity(
                entity_id="ENT_AUTHORIZATION",
                canonical_name="Autorização",
                entity_type="concept",
                evidence_ids=["EV_ONE"],
            ),
            KnowledgeEntity(
                entity_id="ENT_AGENCY",
                canonical_name="Entidade competente",
                entity_type="organization",
                evidence_ids=["EV_ONE"],
            ),
        ],
        relations=[
            KnowledgeRelation(
                relation_id="REL_AUTHORIZATION",
                subject_entity_id="ENT_AGENCY",
                object_entity_id="ENT_AUTHORIZATION",
                relation_type="applies_to",
                confidence=0.92,
                evidence_ids=["EV_ONE"],
            )
        ],
    )


def test_graph_normalizes_entity_names_and_preserves_provenance() -> None:
    extraction = _extraction()

    assert extraction.entities[0].normalized_name == "autorização"
    assert extraction.relations[0].evidence_ids == ["EV_ONE"]


def test_graph_rejects_relation_with_unknown_entity() -> None:
    with pytest.raises(ValidationError, match="relation object is not present"):
        KnowledgeGraphExtraction(
            evidence_ids=["EV_ONE"],
            entities=[
                KnowledgeEntity(
                    entity_id="ENT_ONLY",
                    canonical_name="Apenas uma entidade",
                    evidence_ids=["EV_ONE"],
                )
            ],
            relations=[
                KnowledgeRelation(
                    relation_id="REL_INVALID",
                    subject_entity_id="ENT_ONLY",
                    object_entity_id="ENT_MISSING",
                    relation_type="related_to",
                    evidence_ids=["EV_ONE"],
                )
            ],
        )


def test_graph_rejects_entity_with_outside_evidence() -> None:
    with pytest.raises(
        ValidationError,
        match="entity references evidence outside the extraction set",
    ):
        KnowledgeGraphExtraction(
            evidence_ids=["EV_ONE"],
            entities=[
                KnowledgeEntity(
                    entity_id="ENT_ONE",
                    canonical_name="Uma entidade",
                    evidence_ids=["EV_MISSING"],
                )
            ],
        )


def test_graph_rejects_relation_with_outside_evidence() -> None:
    with pytest.raises(
        ValidationError,
        match="outside the extraction set",
    ):
        KnowledgeGraphExtraction(
            evidence_ids=["EV_ONE"],
            entities=[
                KnowledgeEntity(
                    entity_id="ENT_ONE",
                    canonical_name="Uma entidade",
                    evidence_ids=["EV_ONE"],
                ),
                KnowledgeEntity(
                    entity_id="ENT_TWO",
                    canonical_name="Outra entidade",
                    evidence_ids=["EV_ONE"],
                ),
            ],
            relations=[
                KnowledgeRelation(
                    relation_id="REL_INVALID",
                    subject_entity_id="ENT_ONE",
                    object_entity_id="ENT_TWO",
                    relation_type="related_to",
                    evidence_ids=["EV_MISSING"],
                )
            ],
        )


@pytest.mark.asyncio
async def test_persistence_requires_real_evidence_and_is_idempotent_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upserts: list[tuple[str, str, dict[str, Any]]] = []
    relations: list[dict[str, Any]] = []

    async def fake_query(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [{"id": "evidence_block:one", "evidence_id": "EV_ONE"}]

    async def fake_upsert(
        table: str,
        record_id: str,
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        upserts.append((table, record_id, data))
        return []

    async def fake_relate(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        relations.append(kwargs)
        return []

    monkeypatch.setattr(persistence, "repo_query", fake_query)
    monkeypatch.setattr(persistence, "repo_upsert", fake_upsert)
    monkeypatch.setattr(persistence, "repo_relate", fake_relate)

    result = await persistence.persist_knowledge_graph(_extraction())

    assert result.entities_upserted == 2
    assert result.relations_upserted == 1
    assert result.evidence_links_upserted == 2
    assert len(upserts) == 3
    assert len(relations) == 2
    relation_ids = {
        relation["relation_id"]
        for relation in relations
    }
    assert len(relation_ids) == 2


class _StructuredGraphModel:
    def __init__(self, extraction: KnowledgeGraphExtraction) -> None:
        self.extraction = extraction
        self.prompt = ""

    async def ainvoke(self, prompt: str) -> KnowledgeGraphExtraction:
        self.prompt = prompt
        return self.extraction


class _GraphLanguageModel:
    def __init__(self, extraction: KnowledgeGraphExtraction) -> None:
        self.structured = _StructuredGraphModel(extraction)

    def with_structured_output(self, schema: Any) -> _StructuredGraphModel:
        assert schema is KnowledgeGraphExtraction
        return self.structured


@pytest.mark.asyncio
async def test_extraction_is_bound_to_selected_evidence_and_persisted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    language_model = _GraphLanguageModel(_extraction())
    persisted = persistence.KnowledgeGraphPersistenceResult(
        entities_upserted=2,
        relations_upserted=1,
        evidence_links_upserted=2,
        evidence_ids=["EV_ONE"],
    )

    async def fake_query(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [
            {
                "id": "evidence_block:one",
                "evidence_id": "EV_ONE",
                "source": "source:one",
                "document_version": "document_version:one",
                "raw_text": "A entidade competente aplica-se à autorização.",
            }
        ]

    async def fake_provision(*args: Any, **kwargs: Any) -> _GraphLanguageModel:
        return language_model

    async def fake_persist(
        extraction: KnowledgeGraphExtraction,
    ) -> persistence.KnowledgeGraphPersistenceResult:
        assert extraction.evidence_ids == ["EV_ONE"]
        return persisted

    monkeypatch.setattr(extraction, "repo_query", fake_query)
    monkeypatch.setattr(extraction, "provision_langchain_model", fake_provision)
    monkeypatch.setattr(extraction, "persist_knowledge_graph", fake_persist)

    result = await extraction.extract_and_persist_knowledge_graph(
        extraction.KnowledgeGraphExtractionRequest(evidence_ids=["EV_ONE"])
    )

    assert result.persistence == persisted
    assert "[Evidence ID: EV_ONE]" in language_model.structured.prompt


@pytest.mark.asyncio
async def test_extraction_rejects_model_evidence_outside_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid = _extraction().model_copy(
        update={
            "evidence_ids": ["EV_OUTSIDE"],
            "entities": [
                entity.model_copy(update={"evidence_ids": ["EV_OUTSIDE"]})
                for entity in _extraction().entities
            ],
            "relations": [
                relation.model_copy(update={"evidence_ids": ["EV_OUTSIDE"]})
                for relation in _extraction().relations
            ],
        }
    )

    async def fake_query(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [
            {
                "id": "evidence_block:one",
                "evidence_id": "EV_ONE",
                "source": "source:one",
                "document_version": "document_version:one",
                "raw_text": "Texto.",
            }
        ]

    async def fake_provision(*args: Any, **kwargs: Any) -> _GraphLanguageModel:
        return _GraphLanguageModel(invalid)

    monkeypatch.setattr(extraction, "repo_query", fake_query)
    monkeypatch.setattr(extraction, "provision_langchain_model", fake_provision)

    with pytest.raises(InvalidInputError, match="outside the selected set"):
        await extraction.extract_knowledge_graph(
            extraction.KnowledgeGraphExtractionRequest(evidence_ids=["EV_ONE"])
        )
