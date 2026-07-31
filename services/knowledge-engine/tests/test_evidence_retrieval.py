from __future__ import annotations

from typing import Any

import pytest

from open_notebook.evidence import retrieval
from open_notebook.evidence.retrieval import (
    EvidenceSearchFilters,
    cosine_similarity,
    index_evidence_blocks,
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


@pytest.mark.asyncio
async def test_partial_indexing_failure_preserves_successes_and_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from open_notebook.ai.models import model_manager

    rows = [
        {
            "id": "evidence_block:one",
            "raw_text": "Primeiro bloco",
            "verified_text": None,
            "embedding": None,
            "embedding_model": None,
            "embedded_text_hash": None,
            "indexing_status": None,
            "indexing_error": None,
        },
        {
            "id": "evidence_block:two",
            "raw_text": "Segundo bloco",
            "verified_text": None,
            "embedding": None,
            "embedding_model": None,
            "embedded_text_hash": None,
            "indexing_status": None,
            "indexing_error": None,
        },
    ]
    fail_second_update = True

    async def fake_get_embedding_model() -> object:
        return type("EmbeddingModel", (), {"model_name": "test-model"})()

    async def fake_generate_embeddings(texts: list[str]) -> list[list[float]]:
        return [[float(index + 1), 0.0] for index, _ in enumerate(texts)]

    async def fake_repo_query(
        query: str, variables: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        nonlocal fail_second_update
        variables = variables or {}
        if query.startswith("SELECT * FROM evidence_block"):
            offset = int(variables["offset"])
            limit = int(variables["limit"])
            return [dict(row) for row in rows[offset : offset + limit]]
        if query.startswith("UPDATE evidence_block SET indexing_status"):
            ids = {str(value) for value in variables["ids"]}
            for row in rows:
                if row["id"] in ids:
                    row["indexing_status"] = variables["status"]
                    row["indexing_error"] = variables["error"]
            return []
        if query == "UPDATE $id MERGE $data":
            row_id = str(variables["id"])
            if row_id == "evidence_block:two" and fail_second_update:
                fail_second_update = False
                raise RuntimeError("simulated persistence failure")
            row = next(item for item in rows if item["id"] == row_id)
            row.update(variables["data"])
            return []
        raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(model_manager, "get_embedding_model", fake_get_embedding_model)
    monkeypatch.setattr(retrieval, "generate_embeddings", fake_generate_embeddings)
    monkeypatch.setattr(retrieval, "repo_query", fake_repo_query)

    first = await index_evidence_blocks(batch_size=2, max_blocks=10)

    assert first.embedded == 1
    assert first.failed == 1
    assert rows[0]["indexing_status"] == "indexed"
    assert rows[1]["indexing_status"] == "failed"
    assert rows[0]["indexing_error"] is None
    assert rows[1]["indexing_error"] == "simulated persistence failure"

    second = await index_evidence_blocks(batch_size=2, max_blocks=10)

    assert second.embedded == 1
    assert second.failed == 0
    assert second.skipped == 1
    assert all(row["indexing_status"] == "indexed" for row in rows)
    assert all(row["indexing_error"] is None for row in rows)


def _version_row(
    version_id: str,
    *,
    version_hash: str,
    status: str | None,
    created: str,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": version_id,
        "source": "source:one",
        "version_hash": version_hash,
        "created": created,
    }
    if status is not None:
        row["status"] = status
    return row


def _block_row(evidence_id: str, version_id: str) -> dict[str, Any]:
    return {
        "id": f"evidence_block:{evidence_id.lower()}",
        "evidence_id": evidence_id,
        "source": "source:one",
        "document_version": version_id,
        "raw_text": "Compete à entidade X autorizar a medida.",
        "verified_text": None,
        "pdf_page": 1,
        "printed_page": "1",
        "section_path": [],
        "block_type": "paragraph",
        "bbox": None,
        "embedding": None,
        "verification_status": "automatically_verified",
    }


@pytest.mark.asyncio
async def test_revoked_version_is_never_retrieved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A revoked current version removes the source instead of falling back."""

    async def fake_repo_query(
        query: str, variables: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        if "FROM document_version" in query:
            return [
                _version_row(
                    "document_version:new",
                    version_hash="b" * 64,
                    status="revoked",
                    created="2026-07-28T12:00:00Z",
                ),
                _version_row(
                    "document_version:old",
                    version_hash="a" * 64,
                    status="superseded",
                    created="2026-07-27T12:00:00Z",
                ),
            ]
        if "FROM evidence_block" in query:
            raise AssertionError("no version should have been selected")
        if "FROM source" in query:
            return []
        raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(retrieval, "repo_query", fake_repo_query)

    response = await retrieve_evidence(
        query="autorizar a medida",
        filters=EvidenceSearchFilters(),
        allow_legacy_fallback=False,
    )

    assert response.hits == []
    assert response.selected_versions == {}


@pytest.mark.asyncio
async def test_superseded_version_is_reachable_only_when_pinned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_repo_query(
        query: str, variables: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        if "FROM document_version" in query:
            return [
                _version_row(
                    "document_version:old",
                    version_hash="a" * 64,
                    status="superseded",
                    created="2026-07-27T12:00:00Z",
                )
            ]
        if "FROM evidence_block" in query:
            return [_block_row("EV_PINNED_001", "document_version:old")]
        if "FROM source" in query:
            return [{"id": "source:one", "title": "Regulamento"}]
        raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(retrieval, "repo_query", fake_repo_query)

    pinned = await retrieve_evidence(
        query="autorizar a medida",
        filters=EvidenceSearchFilters(version_hash="a" * 64),
        allow_legacy_fallback=False,
    )
    unpinned = await retrieve_evidence(
        query="autorizar a medida",
        filters=EvidenceSearchFilters(),
        allow_legacy_fallback=False,
    )

    assert [hit.evidence_id for hit in pinned.hits] == ["EV_PINNED_001"]
    assert unpinned.hits == []


@pytest.mark.asyncio
async def test_rejected_evidence_is_excluded_from_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rejected blocks are filtered in the query and again before ranking."""

    captured: dict[str, Any] = {}

    async def fake_repo_query(
        query: str, variables: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        if "FROM document_version" in query:
            return [
                _version_row(
                    "document_version:new",
                    version_hash="b" * 64,
                    status="current",
                    created="2026-07-28T12:00:00Z",
                )
            ]
        if "FROM evidence_block" in query:
            captured["clause"] = query
            captured["rejected_status"] = (variables or {}).get("rejected_status")
            rejected = _block_row("EV_REJECTED_001", "document_version:new")
            rejected["verification_status"] = "rejected"
            return [rejected, _block_row("EV_GOOD_001", "document_version:new")]
        if "FROM source" in query:
            return [{"id": "source:one", "title": "Regulamento"}]
        raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(retrieval, "repo_query", fake_repo_query)

    response = await retrieve_evidence(
        query="autorizar a medida",
        filters=EvidenceSearchFilters(),
        allow_legacy_fallback=False,
    )

    assert "verification_status != $rejected_status" in captured["clause"]
    assert captured["rejected_status"] == "rejected"
    assert [hit.evidence_id for hit in response.hits] == ["EV_GOOD_001"]
