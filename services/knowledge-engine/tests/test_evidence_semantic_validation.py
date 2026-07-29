from __future__ import annotations

from typing import Any

import pytest

from open_notebook.evidence import semantic_validation
from open_notebook.evidence.models import SupportStatus
from open_notebook.evidence.semantic_validation import validate_claim_semantics
from open_notebook.exceptions import InvalidInputError


class _EmbeddingModel:
    model_name = "test-embedding-model"


async def _install_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from open_notebook.ai import models

    async def fake_get_embedding_model() -> _EmbeddingModel:
        return _EmbeddingModel()

    monkeypatch.setattr(
        models.model_manager,
        "get_embedding_model",
        fake_get_embedding_model,
    )


def _row(
    evidence_id: str,
    text: str,
    *,
    source: str = "source:one",
    version: str = "document_version:one",
) -> dict[str, Any]:
    return {
        "id": f"evidence_block:{evidence_id.lower()}",
        "evidence_id": evidence_id,
        "source": source,
        "document_version": version,
        "raw_text": text,
        "verified_text": None,
        "verification_status": "unverified",
    }


@pytest.mark.asyncio
async def test_direct_support_is_recommended(monkeypatch: pytest.MonkeyPatch) -> None:
    await _install_model(monkeypatch)

    async def fake_repo_query(
        query: str, variables: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        assert "FROM evidence_block" in query
        assert variables == {"evidence_ids": ["EV_ONE"]}
        return [_row("EV_ONE", "A autorização deve ser decidida em 24 horas.")]

    async def fake_generate_embeddings(texts: list[str]) -> list[list[float]]:
        assert len(texts) == 2
        return [[1.0, 0.0], [1.0, 0.0]]

    monkeypatch.setattr(semantic_validation, "repo_query", fake_repo_query)
    monkeypatch.setattr(
        semantic_validation,
        "generate_embeddings",
        fake_generate_embeddings,
    )

    result = await validate_claim_semantics(
        claim="A autorização deve ser decidida em 24 horas.",
        evidence_ids=["EV_ONE"],
    )

    assert result.recommended_support_status == SupportStatus.DIRECT
    assert result.confidence == pytest.approx(1.0)
    assert result.requires_human_review is False
    assert result.embedding_model == "test-embedding-model"
    assert result.evidence_findings[0].numeric_conflict is False


@pytest.mark.asyncio
async def test_numeric_conflict_is_contradicted(monkeypatch: pytest.MonkeyPatch) -> None:
    await _install_model(monkeypatch)

    async def fake_repo_query(
        query: str, variables: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return [_row("EV_ONE", "O prazo aplicável é de 48 horas.")]

    async def fake_generate_embeddings(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0], [0.95, 0.05]]

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

    assert result.recommended_support_status == SupportStatus.CONTRADICTED
    assert result.requires_human_review is True
    assert result.evidence_findings[0].numeric_conflict is True


@pytest.mark.asyncio
async def test_mixed_versions_for_same_source_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_repo_query(
        query: str, variables: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return [
            _row("EV_ONE", "Texto um.", version="document_version:one"),
            _row("EV_TWO", "Texto dois.", version="document_version:two"),
        ]

    monkeypatch.setattr(semantic_validation, "repo_query", fake_repo_query)

    with pytest.raises(InvalidInputError, match="cannot mix document versions"):
        await validate_claim_semantics(
            claim="Afirmação atómica.",
            evidence_ids=["EV_ONE", "EV_TWO"],
        )


@pytest.mark.asyncio
async def test_unresolved_ids_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_repo_query(
        query: str, variables: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return [_row("EV_ONE", "A medida é autorizada pela entidade competente.")]

    monkeypatch.setattr(semantic_validation, "repo_query", fake_repo_query)

    with pytest.raises(InvalidInputError, match="Evidence IDs not found: EV_MISSING"):
        await validate_claim_semantics(
            claim="A medida é autorizada pela entidade competente.",
            evidence_ids=["EV_ONE", "EV_MISSING"],
        )
