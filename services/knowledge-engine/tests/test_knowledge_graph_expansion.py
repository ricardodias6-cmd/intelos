from __future__ import annotations

from typing import Any

import pytest

from open_notebook.knowledge_graph import expansion


@pytest.mark.asyncio
async def test_expansion_loads_related_evidence_from_selected_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_query(
        query: str,
        variables: dict[str, Any],
    ) -> list[dict[str, Any]]:
        calls.append((query, variables))
        if "entity_evidence" in query:
            return [{"in": "knowledge_entity:ENT_ONE", "evidence_id": "EV_ONE"}]
        if "knowledge_relation" in query:
            return [
                {
                    "relation_id": "REL_ONE",
                    "in": "knowledge_entity:ENT_ONE",
                    "out": "knowledge_entity:ENT_TWO",
                    "relation_type": "related_to",
                    "confidence": 0.9,
                    "evidence_ids": ["EV_ONE", "EV_TWO"],
                }
            ]
        if "FROM evidence_block" in query:
            return [
                {
                    "id": "evidence_block:two",
                    "evidence_id": "EV_TWO",
                    "source": "source:one",
                    "document_version": "document_version:one",
                    "raw_text": "Texto relacionado.",
                    "block_type": "text",
                }
            ]
        if "document_version" in query:
            return [
                {
                    "id": "document_version:one",
                    "source": "source:one",
                    "version_hash": "hash:one",
                }
            ]
        return []

    monkeypatch.setattr(expansion, "repo_query", fake_query)

    result = await expansion.expand_knowledge_graph(
        evidence_ids=["EV_ONE"],
        selected_versions={"source:one": "hash:one"},
        max_evidence=2,
    )

    assert result.entity_ids == ["ENT_ONE"]
    assert result.related_evidence_ids == ["EV_TWO"]
    assert result.extra_hits[0].evidence_id == "EV_TWO"
    assert result.relations[0].relation_id == "REL_ONE"
    assert any("CONTAINSANY" in query for query, _ in calls)


@pytest.mark.asyncio
async def test_expansion_does_not_mix_document_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_query(
        query: str,
        variables: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if "entity_evidence" in query:
            return [{"in": "knowledge_entity:ENT_ONE", "evidence_id": "EV_ONE"}]
        if "knowledge_relation" in query:
            return [
                {
                    "relation_id": "REL_ONE",
                    "in": "knowledge_entity:ENT_ONE",
                    "out": "knowledge_entity:ENT_TWO",
                    "relation_type": "related_to",
                    "confidence": 0.9,
                    "evidence_ids": ["EV_ONE", "EV_OTHER_VERSION"],
                }
            ]
        if "FROM evidence_block" in query:
            return [
                {
                    "id": "evidence_block:other",
                    "evidence_id": "EV_OTHER_VERSION",
                    "source": "source:one",
                    "document_version": "document_version:other",
                    "raw_text": "Outra versão.",
                    "block_type": "text",
                }
            ]
        if "document_version" in query:
            return [
                {
                    "id": "document_version:other",
                    "source": "source:one",
                    "version_hash": "hash:other",
                }
            ]
        return []

    monkeypatch.setattr(expansion, "repo_query", fake_query)

    result = await expansion.expand_knowledge_graph(
        evidence_ids=["EV_ONE"],
        selected_versions={"source:one": "hash:one"},
        max_evidence=2,
    )

    assert result.extra_hits == []
    assert result.related_evidence_ids == []
