from __future__ import annotations

from typing import Any

import pytest

from open_notebook.evidence import semantic_validation
from open_notebook.evidence.models import SupportStatus
from open_notebook.evidence.semantic_validation import validate_claim_semantics


class _EmbeddingModel:
    model_name = "test-embedding-model"


def _row(evidence_id: str, text: str) -> dict[str, Any]:
    return {
        "id": f"evidence_block:{evidence_id.lower()}",
        "evidence_id": evidence_id,
        "source": "source:one",
        "document_version": "document_version:one",
        "raw_text": text,
        "verified_text": None,
        "verification_status": "unverified",
    }


async def _install_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from open_notebook.ai import models

    async def fake_get_embedding_model() -> _EmbeddingModel:
        return _EmbeddingModel()

    monkeypatch.setattr(
        models.model_manager,
        "get_embedding_model",
        fake_get_embedding_model,
    )


@pytest.mark.asyncio
async def test_irrelevant_number_does_not_create_contradiction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _install_model(monkeypatch)

    async def fake_repo_query(
        query: str, variables: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return [_row("EV_ONE", "O edifício tem 48 lugares de estacionamento.")]

    async def fake_generate_embeddings(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0], [-1.0, 0.0]]

    monkeypatch.setattr(semantic_validation, "repo_query", fake_repo_query)
    monkeypatch.setattr(
        semantic_validation,
        "generate_embeddings",
        fake_generate_embeddings,
    )

    result = await validate_claim_semantics(
        claim="O prazo aplicável é de 24 horas.",
        evidence_ids=["EV_ONE"],
    )

    assert result.recommended_support_status == SupportStatus.UNSUPPORTED
    assert result.evidence_findings[0].numeric_conflict is False


@pytest.mark.asyncio
async def test_direct_and_conflicting_evidence_require_partial_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _install_model(monkeypatch)

    async def fake_repo_query(
        query: str, variables: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return [
            _row("EV_SUPPORT", "O prazo aplicável é de 24 horas."),
            _row("EV_CONFLICT", "O prazo aplicável é de 48 horas."),
        ]

    async def fake_generate_embeddings(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0], [1.0, 0.0], [0.95, 0.05]]

    monkeypatch.setattr(semantic_validation, "repo_query", fake_repo_query)
    monkeypatch.setattr(
        semantic_validation,
        "generate_embeddings",
        fake_generate_embeddings,
    )

    result = await validate_claim_semantics(
        claim="O prazo aplicável é de 24 horas.",
        evidence_ids=["EV_SUPPORT", "EV_CONFLICT"],
    )

    assert result.recommended_support_status == SupportStatus.PARTIAL
    assert result.requires_human_review is True


@pytest.mark.asyncio
async def test_negative_similarity_is_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    await _install_model(monkeypatch)

    async def fake_repo_query(
        query: str, variables: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return [_row("EV_ONE", "Conteúdo sem correspondência temática.")]

    async def fake_generate_embeddings(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0], [-1.0, 0.0]]

    monkeypatch.setattr(semantic_validation, "repo_query", fake_repo_query)
    monkeypatch.setattr(
        semantic_validation,
        "generate_embeddings",
        fake_generate_embeddings,
    )

    result = await validate_claim_semantics(
        claim="A autorização foi concedida.",
        evidence_ids=["EV_ONE"],
    )

    assert result.evidence_findings[0].semantic_score == 0.0
    assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_unrelated_negation_does_not_create_polarity_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _install_model(monkeypatch)

    async def fake_repo_query(
        query: str, variables: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return [
            _row(
                "EV_ONE",
                "A autorização foi concedida. O requerente não apresentou recurso.",
            )
        ]

    async def fake_generate_embeddings(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0], [1.0, 0.0]]

    monkeypatch.setattr(semantic_validation, "repo_query", fake_repo_query)
    monkeypatch.setattr(
        semantic_validation,
        "generate_embeddings",
        fake_generate_embeddings,
    )

    result = await validate_claim_semantics(
        claim="A autorização foi concedida.",
        evidence_ids=["EV_ONE"],
    )

    assert result.recommended_support_status == SupportStatus.DIRECT
    assert result.evidence_findings[0].polarity_conflict is False
