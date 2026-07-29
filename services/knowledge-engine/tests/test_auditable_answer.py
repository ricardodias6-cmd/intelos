from __future__ import annotations

from typing import Any

import pytest

from open_notebook.evidence import auditable_answer
from open_notebook.evidence.auditable_answer import (
    AuditableAnswerRequest,
    CandidateAnswer,
    CandidateClaim,
    build_auditable_answer,
)
from open_notebook.evidence.models import SupportStatus
from open_notebook.evidence.retrieval import (
    EvidenceSearchHit,
    EvidenceSearchResponse,
)
from open_notebook.evidence.semantic_validation import (
    SemanticEvidenceFinding,
    SemanticValidationResult,
)


class _StructuredModel:
    def __init__(self, candidate: CandidateAnswer) -> None:
        self.candidate = candidate

    async def ainvoke(self, prompt: str) -> CandidateAnswer:
        assert "Evidence ID" in prompt
        return self.candidate


class _LanguageModel:
    def __init__(self, candidate: CandidateAnswer) -> None:
        self.candidate = candidate

    def with_structured_output(self, schema: Any) -> _StructuredModel:
        assert schema is CandidateAnswer
        return _StructuredModel(self.candidate)


def _hit(evidence_id: str = "EV_ONE") -> EvidenceSearchHit:
    return EvidenceSearchHit(
        evidence_id=evidence_id,
        source_id="source:one",
        document_title="Documento de teste",
        document_version_id="document_version:one",
        document_version_hash="hash:one",
        text="A autorização compete à entidade competente.",
        pdf_page=2,
        printed_page="2",
        section_path=["Capítulo I"],
        block_type="text",
        score=0.91,
        semantic_score=0.9,
        lexical_score=0.92,
        structural_score=0.1,
    )


def _retrieval(*hits: EvidenceSearchHit) -> EvidenceSearchResponse:
    return EvidenceSearchResponse(
        query="Quem decide?",
        hits=list(hits),
        selected_versions={"source:one": "hash:one"},
    )


def _validation(
    status: SupportStatus,
    *,
    confidence: float,
    requires_human_review: bool = False,
) -> SemanticValidationResult:
    return SemanticValidationResult(
        claim="A autorização compete à entidade competente.",
        recommended_support_status=status,
        confidence=confidence,
        requires_human_review=requires_human_review,
        evidence_findings=[
            SemanticEvidenceFinding(
                evidence_id="EV_ONE",
                semantic_score=confidence,
                lexical_coverage=0.9,
            )
        ],
        embedding_model="test-embedding-model",
        direct_threshold=0.82,
        partial_threshold=0.58,
    )


@pytest.mark.asyncio
async def test_direct_claim_is_rendered_with_validated_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = CandidateAnswer(
        answer="A autorização compete à entidade competente.",
        claims=[
            CandidateClaim(
                text="A autorização compete à entidade competente.",
                evidence_ids=["EV_ONE"],
            )
        ],
    )

    async def fake_retrieve(**kwargs: Any) -> EvidenceSearchResponse:
        return _retrieval(_hit())

    async def fake_provision(*args: Any, **kwargs: Any) -> _LanguageModel:
        return _LanguageModel(candidate)

    async def fake_validate(**kwargs: Any) -> SemanticValidationResult:
        return _validation(SupportStatus.DIRECT, confidence=0.91)

    monkeypatch.setattr(auditable_answer, "retrieve_evidence", fake_retrieve)
    monkeypatch.setattr(
        auditable_answer,
        "provision_langchain_model",
        fake_provision,
    )
    monkeypatch.setattr(
        auditable_answer,
        "validate_claim_semantics",
        fake_validate,
    )

    result = await build_auditable_answer(
        AuditableAnswerRequest(question="Quem decide?")
    )

    assert result.status == "answered"
    assert result.answer == "A autorização compete à entidade competente."
    assert result.claims[0].claim_id == "CLM_001"
    assert result.claims[0].support_status == SupportStatus.DIRECT
    assert result.citations[0].evidence_id == "EV_ONE"
    assert result.overall_confidence == pytest.approx(0.91)
    assert result.requires_human_review is False


@pytest.mark.asyncio
async def test_partial_claim_is_qualified_but_not_misclassified_as_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = CandidateAnswer(
        answer="A autorização pode competir à entidade competente.",
        claims=[
            CandidateClaim(
                text="A autorização pode competir à entidade competente.",
                evidence_ids=["EV_ONE"],
            )
        ],
    )

    async def fake_retrieve(**kwargs: Any) -> EvidenceSearchResponse:
        return _retrieval(_hit())

    async def fake_provision(*args: Any, **kwargs: Any) -> _LanguageModel:
        return _LanguageModel(candidate)

    async def fake_validate(**kwargs: Any) -> SemanticValidationResult:
        return _validation(
            SupportStatus.PARTIAL,
            confidence=0.64,
            requires_human_review=True,
        )

    monkeypatch.setattr(auditable_answer, "retrieve_evidence", fake_retrieve)
    monkeypatch.setattr(
        auditable_answer,
        "provision_langchain_model",
        fake_provision,
    )
    monkeypatch.setattr(
        auditable_answer,
        "validate_claim_semantics",
        fake_validate,
    )

    result = await build_auditable_answer(
        AuditableAnswerRequest(question="Quem decide?")
    )

    assert result.status == "answered"
    assert result.claims[0].support_status == SupportStatus.PARTIAL
    assert result.requires_human_review is True
    assert "parcialmente" in result.answer


@pytest.mark.asyncio
async def test_no_retrieved_evidence_never_calls_the_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_retrieve(**kwargs: Any) -> EvidenceSearchResponse:
        return _retrieval()

    async def unexpected_provision(*args: Any, **kwargs: Any) -> _LanguageModel:
        raise AssertionError("the LLM must not run without evidence")

    monkeypatch.setattr(auditable_answer, "retrieve_evidence", fake_retrieve)
    monkeypatch.setattr(
        auditable_answer,
        "provision_langchain_model",
        unexpected_provision,
    )

    result = await build_auditable_answer(
        AuditableAnswerRequest(question="Pergunta sem evidência?")
    )

    assert result.status == "insufficient_evidence"
    assert result.overall_confidence == 0
    assert result.claims == []
    assert result.citations == []


@pytest.mark.asyncio
async def test_candidate_evidence_outside_retrieved_set_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = CandidateAnswer(
        answer="A autorização compete à entidade competente.",
        claims=[
            CandidateClaim(
                text="A autorização compete à entidade competente.",
                evidence_ids=["EV_MISSING"],
            )
        ],
    )

    async def fake_retrieve(**kwargs: Any) -> EvidenceSearchResponse:
        return _retrieval(_hit())

    async def fake_provision(*args: Any, **kwargs: Any) -> _LanguageModel:
        return _LanguageModel(candidate)

    async def unexpected_validate(**kwargs: Any) -> SemanticValidationResult:
        raise AssertionError("invalid candidate IDs must not reach validation")

    monkeypatch.setattr(auditable_answer, "retrieve_evidence", fake_retrieve)
    monkeypatch.setattr(
        auditable_answer,
        "provision_langchain_model",
        fake_provision,
    )
    monkeypatch.setattr(
        auditable_answer,
        "validate_claim_semantics",
        unexpected_validate,
    )

    result = await build_auditable_answer(
        AuditableAnswerRequest(question="Quem decide?")
    )

    assert result.status == "insufficient_evidence"
    assert result.claims[0].support_status == SupportStatus.UNSUPPORTED
    assert result.claims[0].evidence_ids == []
    assert result.citations == []


@pytest.mark.asyncio
async def test_contradicted_claim_is_not_rendered_as_fact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = CandidateAnswer(
        answer="A autorização compete à entidade competente.",
        claims=[
            CandidateClaim(
                text="A autorização compete à entidade competente.",
                evidence_ids=["EV_ONE"],
            )
        ],
    )

    async def fake_retrieve(**kwargs: Any) -> EvidenceSearchResponse:
        return _retrieval(_hit())

    async def fake_provision(*args: Any, **kwargs: Any) -> _LanguageModel:
        return _LanguageModel(candidate)

    async def fake_validate(**kwargs: Any) -> SemanticValidationResult:
        return _validation(
            SupportStatus.CONTRADICTED,
            confidence=0.9,
            requires_human_review=True,
        )

    monkeypatch.setattr(auditable_answer, "retrieve_evidence", fake_retrieve)
    monkeypatch.setattr(
        auditable_answer,
        "provision_langchain_model",
        fake_provision,
    )
    monkeypatch.setattr(
        auditable_answer,
        "validate_claim_semantics",
        fake_validate,
    )

    result = await build_auditable_answer(
        AuditableAnswerRequest(question="Quem decide?")
    )

    assert result.status == "conflict"
    assert result.answer.startswith("A evidência recuperada contém conflito")
    assert result.claims[0].confidence == 0
    assert result.claims[0].evidence_ids == ["EV_ONE"]
    assert result.requires_human_review is True
