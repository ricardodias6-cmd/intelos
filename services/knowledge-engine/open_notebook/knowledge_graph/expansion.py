"""Bounded knowledge graph expansion for Copilot retrieval."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field

from open_notebook.database.repository import repo_query
from open_notebook.evidence.retrieval import EvidenceSearchHit
from open_notebook.knowledge_graph.models import KnowledgeRelationType


class KnowledgeGraphRelationContext(BaseModel):
    """A graph relation retained with its supporting Evidence IDs."""

    relation_id: str
    subject_entity_id: str
    object_entity_id: str
    relation_type: KnowledgeRelationType
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(min_length=1, max_length=50)


class KnowledgeGraphExpansion(BaseModel):
    """Graph context and evidence blocks added to one retrieval result."""

    seed_evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    entity_ids: list[str] = Field(default_factory=list, max_length=100)
    relations: list[KnowledgeGraphRelationContext] = Field(
        default_factory=list,
        max_length=100,
    )
    related_evidence_ids: list[str] = Field(
        default_factory=list,
        max_length=20,
    )
    extra_hits: list[EvidenceSearchHit] = Field(
        default_factory=list,
        max_length=20,
    )


def _record_component(value: Any) -> str:
    text = str(value)
    return text.split(":", 1)[1] if ":" in text else text


def _selected_version_ids(
    rows: Sequence[dict[str, Any]],
    selected_versions: Mapping[str, str],
) -> set[str]:
    return {
        str(row["id"])
        for row in rows
        if row.get("id") is not None
        and selected_versions.get(str(row.get("source")))
        == str(row.get("version_hash"))
    }


def _evidence_hit_from_row(
    row: dict[str, Any],
    version_hash_by_id: Mapping[str, str],
) -> EvidenceSearchHit | None:
    version_id = str(row.get("document_version"))
    version_hash = version_hash_by_id.get(version_id)
    evidence_id = row.get("evidence_id")
    if not evidence_id or not version_hash:
        return None

    text = str(row.get("verified_text") or row.get("raw_text") or "").strip()
    if not text:
        return None

    return EvidenceSearchHit(
        evidence_id=str(evidence_id),
        source_id=str(row["source"]),
        document_title=None,
        document_version_id=version_id,
        document_version_hash=version_hash,
        text=text,
        pdf_page=row.get("pdf_page"),
        printed_page=row.get("printed_page"),
        section_path=row.get("section_path") or [],
        block_type=str(row.get("block_type") or "text"),
        bbox=row.get("bbox"),
        score=0.0,
        semantic_score=0.0,
        lexical_score=0.0,
        structural_score=0.0,
    )


async def expand_knowledge_graph(
    *,
    evidence_ids: Sequence[str],
    selected_versions: Mapping[str, str],
    max_evidence: int,
    relation_limit: int = 50,
) -> KnowledgeGraphExpansion:
    """Expand retrieval with graph-linked blocks from selected versions only."""

    seed_ids = list(dict.fromkeys(evidence_ids))
    if not seed_ids or max_evidence <= len(seed_ids):
        return KnowledgeGraphExpansion(seed_evidence_ids=seed_ids)

    entity_rows = await repo_query(
        "SELECT in, evidence_id FROM entity_evidence "
        "WHERE evidence_id IN $evidence_ids",
        {"evidence_ids": seed_ids},
    )
    entity_ids = list(
        dict.fromkeys(
            _record_component(row["in"])
            for row in entity_rows
            if row.get("in") is not None
        )
    )
    if not entity_ids:
        return KnowledgeGraphExpansion(
            seed_evidence_ids=seed_ids,
            entity_ids=[],
        )

    relation_rows = await repo_query(
        "SELECT relation_id, in, out, relation_type, confidence, evidence_ids "
        "FROM knowledge_relation "
        "WHERE evidence_ids CONTAINSANY $evidence_ids "
        "LIMIT $relation_limit",
        {
            "evidence_ids": seed_ids,
            "relation_limit": relation_limit,
        },
    )

    relations: list[KnowledgeGraphRelationContext] = []
    related_ids: list[str] = []
    seed_set = set(seed_ids)
    for row in relation_rows:
        relation_evidence_ids = list(
            dict.fromkeys(
                str(item)
                for item in row.get("evidence_ids") or []
            )
        )
        supported_ids = [item for item in relation_evidence_ids if item in seed_set]
        if not supported_ids:
            continue
        relation = KnowledgeGraphRelationContext(
            relation_id=str(row["relation_id"]),
            subject_entity_id=_record_component(row["in"]),
            object_entity_id=_record_component(row["out"]),
            relation_type=KnowledgeRelationType(str(row["relation_type"])),
            confidence=float(row.get("confidence") or 0),
            evidence_ids=relation_evidence_ids,
        )
        relations.append(relation)
        for related_id in relation_evidence_ids:
            if related_id not in seed_set and related_id not in related_ids:
                related_ids.append(related_id)

    remaining = max_evidence - len(seed_ids)
    related_ids = related_ids[:remaining]
    if not related_ids:
        return KnowledgeGraphExpansion(
            seed_evidence_ids=seed_ids,
            entity_ids=entity_ids,
            relations=relations,
        )

    version_rows = await repo_query(
        "SELECT id, source, version_hash FROM document_version "
        "WHERE version_hash IN $version_hashes",
        {"version_hashes": list(selected_versions.values())},
    )
    selected_version_ids = _selected_version_ids(
        version_rows,
        selected_versions,
    )
    version_hash_by_id = {
        str(row["id"]): str(row["version_hash"])
        for row in version_rows
        if str(row.get("id")) in selected_version_ids
    }
    if not selected_version_ids:
        return KnowledgeGraphExpansion(
            seed_evidence_ids=seed_ids,
            entity_ids=entity_ids,
            relations=relations,
        )

    evidence_rows = await repo_query(
        "SELECT id, evidence_id, source, document_version, raw_text, "
        "verified_text, pdf_page, printed_page, section_path, block_type, bbox "
        "FROM evidence_block "
        "WHERE evidence_id IN $evidence_ids "
        "AND document_version IN $version_ids",
        {
            "evidence_ids": related_ids,
            "version_ids": list(selected_version_ids),
        },
    )
    extra_hits: list[EvidenceSearchHit] = []
    for row in evidence_rows:
        hit = _evidence_hit_from_row(row, version_hash_by_id)
        if hit is not None and hit.evidence_id not in seed_set:
            extra_hits.append(hit)
        if len(extra_hits) >= remaining:
            break

    loaded_ids = [hit.evidence_id for hit in extra_hits]
    return KnowledgeGraphExpansion(
        seed_evidence_ids=seed_ids,
        entity_ids=entity_ids,
        relations=relations,
        related_evidence_ids=loaded_ids,
        extra_hits=extra_hits,
    )
