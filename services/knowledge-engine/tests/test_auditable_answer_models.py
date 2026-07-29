from __future__ import annotations

import pytest
from pydantic import ValidationError

from open_notebook.evidence.auditable_models import (
    AnswerAuditMetadata,
    AnswerCitation,
    AnswerClaim,
    AuditableAnswer,
    AuditableAnswerStatus,
)
from open_notebook.evidence.models import ClaimKind, SupportStatus


def _audit(*evidence_ids: str) -> AnswerAuditMetadata:
    return AnswerAuditMetadata(
        question_hash="sha256:question",
        selected_evidence_ids=list(evidence_ids),
        retrieval_scores={evidence_id: 0.9 for evidence_id in evidence_ids},
    )


def _citation(evidence_id: str) -> AnswerCitation:
    return AnswerCitation(
        evidence_id=evidence_id,
        source_id="source:one",
        document_version_id="document_version:one",
        document_version_hash="sha256:version",
        pdf_page=1,
        text="Excerto documental.",
    )


def _direct_claim(evidence_id: str = "EV_ONE") -> AnswerClaim:
    return AnswerClaim(
        claim_id="CLM_ONE",
        text="A autorização compete à entidade competente.",
        kind=ClaimKind.FACT,
        evidence_ids=[evidence_id],
        support_status=SupportStatus.DIRECT,
        confidence=0.91,
    )


def test_valid_answer_requires_citations_for_claim_evidence() -> None:
    result = AuditableAnswer(
        answer="A autorização compete à entidade competente.",
        claims=[_direct_claim()],
        citations=[_citation("EV_ONE")],
        overall_confidence=0.91,
        status=AuditableAnswerStatus.ANSWERED,
        audit=_audit("EV_ONE"),
    )

    assert result.claims[0].is_presentable_fact is True
    assert result.overall_confidence == pytest.approx(0.91)


def test_claim_evidence_must_be_selected_and_cited() -> None:
    with pytest.raises(
        ValidationError,
        match="claims may only reference selected Evidence IDs",
    ):
        AuditableAnswer(
            answer="Resposta.",
            claims=[_direct_claim("EV_MISSING")],
            citations=[_citation("EV_MISSING")],
            overall_confidence=0.91,
            status=AuditableAnswerStatus.ANSWERED,
            audit=_audit("EV_ONE"),
        )


def test_unsupported_claim_requires_qualification_and_zero_confidence() -> None:
    with pytest.raises(
        ValidationError,
        match="non-definitive claims require a qualification",
    ):
        AnswerClaim(
            claim_id="CLM_UNSUPPORTED",
            text="A afirmação não está demonstrada.",
            kind=ClaimKind.FACT,
            support_status=SupportStatus.UNSUPPORTED,
            confidence=0,
        )


def test_insufficient_evidence_has_zero_confidence() -> None:
    with pytest.raises(
        ValidationError,
        match="insufficient-evidence responses must have zero confidence",
    ):
        AuditableAnswer(
            answer="Não foi encontrada evidência suficiente.",
            claims=[],
            citations=[],
            overall_confidence=0.2,
            status=AuditableAnswerStatus.INSUFFICIENT_EVIDENCE,
            audit=_audit(),
        )


def test_overall_confidence_cannot_exceed_weakest_claim() -> None:
    with pytest.raises(
        ValidationError,
        match="overall confidence cannot exceed",
    ):
        AuditableAnswer(
            answer="Resposta.",
            claims=[_direct_claim()],
            citations=[_citation("EV_ONE")],
            overall_confidence=0.95,
            status=AuditableAnswerStatus.ANSWERED,
            audit=_audit("EV_ONE"),
        )


def test_claim_review_requires_answer_review_flag() -> None:
    claim = AnswerClaim(
        claim_id="CLM_PARTIAL",
        text="A afirmação é apenas parcialmente suportada.",
        kind=ClaimKind.FACT,
        evidence_ids=["EV_ONE"],
        support_status=SupportStatus.PARTIAL,
        confidence=0.62,
        requires_human_review=True,
        qualification="A informação deve ser confirmada.",
    )

    with pytest.raises(
        ValidationError,
        match="answer review flag",
    ):
        AuditableAnswer(
            answer="A informação deve ser confirmada.",
            claims=[claim],
            citations=[_citation("EV_ONE")],
            overall_confidence=0.62,
            status=AuditableAnswerStatus.ANSWERED,
            audit=_audit("EV_ONE"),
        )
