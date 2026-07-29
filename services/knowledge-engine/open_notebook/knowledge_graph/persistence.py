"""Persistence for bounded, evidence-linked knowledge graph fragments."""

from __future__ import annotations

import hashlib
from typing import Any

from open_notebook.database.repository import (
    ensure_record_id,
    repo_query,
    repo_relate,
    repo_upsert,
)
from open_notebook.exceptions import InvalidInputError
from open_notebook.knowledge_graph.models import (
    KnowledgeGraphExtraction,
    KnowledgeGraphPersistenceResult,
)


def _stable_edge_id(kind: str, *parts: str) -> str:
    payload = "|".join((kind, *parts)).encode("utf-8")
    return f"EDGE_{hashlib.sha256(payload).hexdigest()[:40].upper()}"


async def persist_knowledge_graph(
    extraction: KnowledgeGraphExtraction,
) -> KnowledgeGraphPersistenceResult:
    """Persist one graph fragment while requiring every edge to retain evidence."""

    rows = await repo_query(
        "SELECT id, evidence_id FROM evidence_block WHERE evidence_id IN $evidence_ids",
        {"evidence_ids": extraction.evidence_ids},
    )
    evidence_by_id = {str(row["evidence_id"]): row for row in rows}
    missing = [
        evidence_id
        for evidence_id in extraction.evidence_ids
        if evidence_id not in evidence_by_id
    ]
    if missing:
        raise InvalidInputError(
            "Knowledge graph references unknown Evidence IDs: "
            + ", ".join(missing)
        )

    entity_record_ids: dict[str, str] = {}
    for entity in extraction.entities:
        record_id = f"knowledge_entity:{entity.entity_id}"
        entity_record_ids[entity.entity_id] = record_id
        await repo_upsert(
            "knowledge_entity",
            record_id,
            {
                "entity_id": entity.entity_id,
                "canonical_name": entity.canonical_name,
                "normalized_name": entity.normalized_name,
                "entity_type": entity.entity_type.value,
                "aliases": entity.aliases,
                "description": entity.description,
                "metadata": entity.metadata,
            },
        )

        for evidence_id in extraction.evidence_ids:
            await repo_relate(
                source=record_id,
                relationship="entity_evidence",
                target=str(evidence_by_id[evidence_id]["id"]),
                relation_id=_stable_edge_id(
                    "entity-evidence",
                    entity.entity_id,
                    evidence_id,
                ),
                data={
                    "evidence_id": evidence_id,
                    "extractor_version": extraction.extractor_version,
                    "confidence": 1.0,
                },
            )

    for relation in extraction.relations:
        relation_record_id = f"knowledge_relation:{relation.relation_id}"
        await repo_upsert(
            "knowledge_relation",
            relation_record_id,
            {
                "relation_id": relation.relation_id,
                "in": ensure_record_id(
                    entity_record_ids[relation.subject_entity_id]
                ),
                "out": ensure_record_id(
                    entity_record_ids[relation.object_entity_id]
                ),
                "relation_type": relation.relation_type.value,
                "confidence": relation.confidence,
                "evidence_ids": relation.evidence_ids,
                "metadata": relation.metadata,
            },
        )

    return KnowledgeGraphPersistenceResult(
        entities_upserted=len(extraction.entities),
        relations_upserted=len(extraction.relations),
        evidence_links_upserted=(
            len(extraction.entities) * len(extraction.evidence_ids)
        ),
        evidence_ids=extraction.evidence_ids,
    )
