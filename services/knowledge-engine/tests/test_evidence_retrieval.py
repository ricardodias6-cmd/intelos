from __future__ import annotations

from typing import Any

import pytest

from open_notebook.evidence import retrieval
from open_notebook.evidence.retrieval import (
    EvidenceSearchFilters,
    cosine_similarity,
    lexical_score,
    retrieve_evidence,
)


def test_lexical_score_rewards_exact_phrase() -> None:
    exact = lexical_score(
        "autorizar a medida", "Compete à entidade X autorizar a medida imediatamente."
    )
    partial = lexical_score(
        "autorizar a medida", "A entidade deve avaliar uma medida diferente."
    )

    assert exact > partial
    assert 0 <= partial <= 1
    assert 0 <= exact <= 1


def test_lexical_score_rewards_concrete_temporal_answer() -> None:
    query = "Qual é o prazo para decidir a autorização?"
    concrete = "O pedido de autorização deve ser decidido no prazo de 24 horas."
    generic = "O responsável confirma a autorização antes da execução da medida."

    assert lexical_score(query, concrete) > lexical_score(query, generic)


def test_numeric_bonus_is_not_applied_to_unrelated_queries() -> None:
    query = "Quem confirma a autorização?"
    relevant = "O responsável confirma a autorização antes da execução da medida."
    numeric_but_generic = "A autorização é arquivada durante 24 horas."

    assert lexical_score(query, relevant) > lexical_score(query, numeric_but_generic)


def test_semantic_similarity_distinguishes_direct_and_generic_matches() -> None:
    query = [1.0, 0.0, 0.0]
    direct_answer = [1.0, 0.0, 0.0]
    generic_topic_match = [0.70, 0.70, 0.0]
    unrelated = [0.0, 0.0, 1.0]

    assert cosine_similarity(query, direct_answer) == pytest.approx(1.0)
    assert cosine_similarity(query, direct_answer) > cosine_similarity(
        query, generic_topic_match
    )
    assert cosine_similarity(query, generic_topic_match) > cosine_similarity(
        query, unrelated
    )


def test_cosine_similarity_handles_invalid_and_identical_vectors() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0], [1.0, 0.0]) == 0.0
    assert cosine_similarity([], []) == 0.0


@pytest.mark.asyncio
async def test_search_uses_only_latest_version_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    queries: list[str] = []

    async def fake_repo_query(
        query: str, variables: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        queries.append(query)
        if "FROM document_version" in query:
            return [
                {
                    "id": "document_version:new",
                    "source": "source:one",
                    "version_hash": "b" * 64,
                    "created": "2026-07-28T12:00:00Z",
                },
                {
                    "id": "document_version:old",
                    "source": "source:one",
                    "version_hash": "a" * 64,
                    "created": "2026-07-27T12:00:00Z",
                },
            ]
        if "FROM evidence_block" in query:
            assert variables is not None
            assert [str(value) for value in variables["versions"]] == [
                "document_version:new"
            ]
            return [
                {
                    "id": "evidence_block:one",
                    "evidence_id": "EV_CURRENT_001",
                    "source": "source:one",
                    "document_version": "document_version:new",
                    "raw_text": "Compete à entidade X autorizar a medida.",
                    "verified_text": None,
                    "pdf_page": 4,
                    "printed_page": "12",
                    "section_path": ["Artigo 4.º"],
                    "block_type": "paragraph",
                    "bbox": {
                        "x0": 1.0,
                        "y0": 2.0,
                        "x1": 3.0,
                        "y1": 4.0,
                        "coordinate_origin": "TOPLEFT",
                    },
                    "embedding": None,
                }
            ]
        if "FROM source" in query:
            return [{"id": "source:one", "title": "Regulamento"}]
        raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(retrieval, "repo_query", fake_repo_query)

    response = await retrieve_evidence(
        query="autorizar a medida",
        filters=EvidenceSearchFilters(),
        allow_legacy_fallback=False,
    )

    assert response.selected_versions == {"source:one": "b" * 64}
    assert len(response.hits) == 1
    hit = response.hits[0]
    assert hit.evidence_id == "EV_CURRENT_001"
    assert hit.document_title == "Regulamento"
    assert hit.document_version_hash == "b" * 64
    assert hit.pdf_page == 4
    assert hit.bbox is not None
    assert any("FROM evidence_block" in query for query in queries)


@pytest.mark.asyncio
async def test_search_can_target_explicit_old_version(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_repo_query(
        query: str, variables: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        if "FROM document_version" in query:
            assert variables is not None
            assert variables["version_hash"] == "a" * 64
            return [
                {
                    "id": "document_version:old",
                    "source": "source:one",
                    "version_hash": "a" * 64,
                    "created": "2026-07-27T12:00:00Z",
                }
            ]
        if "FROM evidence_block" in query:
            return [
                {
                    "id": "evidence_block:old",
                    "evidence_id": "EV_OLD_001",
                    "source": "source:one",
                    "document_version": "document_version:old",
                    "raw_text": "Texto histórico específico.",
                    "verified_text": None,
                    "pdf_page": 2,
                    "printed_page": None,
                    "section_path": ["Histórico"],
                    "block_type": "paragraph",
                    "bbox": None,
                    "embedding": None,
                }
            ]
        if "FROM source" in query:
            return [{"id": "source:one", "title": "Regulamento"}]
        raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(retrieval, "repo_query", fake_repo_query)

    response = await retrieve_evidence(
        query="texto histórico",
        filters=EvidenceSearchFilters(version_hash="a" * 64),
        allow_legacy_fallback=False,
    )

    assert [hit.evidence_id for hit in response.hits] == ["EV_OLD_001"]
    assert response.hits[0].document_version_hash == "a" * 64