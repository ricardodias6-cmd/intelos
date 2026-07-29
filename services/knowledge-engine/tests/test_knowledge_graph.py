from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from open_notebook.knowledge_graph import (
    KnowledgeEntity,
    KnowledgeGraphExtraction,
    KnowledgeRelation,
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
                ),
                KnowledgeEntity(
                    entity_id="ENT_TWO",
                    canonical_name="Outra entidade",
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
