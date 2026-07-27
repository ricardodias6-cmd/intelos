"""Tests for the Intelos Evidence Core foundation."""

import hashlib
from datetime import date

import pytest
from pydantic import ValidationError

from open_notebook.evidence.constitution import RESPONSE_RULES
from open_notebook.evidence.models import (
    BoundingBox,
    Claim,
    ClaimKind,
    EvidenceBlock,
    ExtractionMethod,
    FreshnessStatus,
    NumericStatus,
    SupportStatus,
    VerificationStatus,
)
from open_notebook.evidence.validation import EvidenceValidator


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _evidence(
    *,
    raw_text: str = "Compete à entidade X autorizar a medida.",
    text_hash: str | None = None,
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED,
    verified_text: str | None = None,
) -> EvidenceBlock:
    return EvidenceBlock(
        evidence_id="EV-001",
        source_id="source:abc123",
        document_version_hash="a" * 64,
        raw_text=raw_text,
        verified_text=verified_text,
        pdf_page=18,
        printed_page="15",
        section_path=["Artigo 12.º", "n.º 3"],
        bbox=BoundingBox(x0=10, y0=20, x1=300, y1=80),
        extraction_method=ExtractionMethod.DOCLING,
        verification_status=verification_status,
        text_hash=text_hash or _hash(raw_text),
    )


def test_response_constitution_has_exactly_nine_rules():
    assert len(RESPONSE_RULES) == 9
    assert {rule.rule_id for rule in RESPONSE_RULES} == {
        "UNCERTAINTY",
        "SOURCES",
        "STATISTICS",
        "RECENT_EVENTS",
        "PEOPLE_QUOTES",
        "CODE_TECHNICAL",
        "LOGIC_GAPS",
        "NATURAL_WRITING",
        "CRITICAL_INDEPENDENCE",
    }


def test_evidence_accepts_open_notebook_record_identifier():
    block = _evidence()
    assert block.source_id == "source:abc123"
    assert block.effective_text == block.raw_text


def test_human_confirmation_requires_verified_text():
    with pytest.raises(ValidationError, match="requires verified_text"):
        _evidence(verification_status=VerificationStatus.HUMAN_CONFIRMED)


def test_human_confirmed_text_becomes_effective_text():
    block = _evidence(
        verification_status=VerificationStatus.HUMAN_CONFIRMED,
        verified_text="Texto confirmado por uma pessoa.",
    )
    assert block.effective_text == "Texto confirmado por uma pessoa."


def test_valid_fact_claim_passes_structural_validation():
    block = _evidence()
    claim = Claim(
        claim_id="CLM-001",
        text="A competência pertence à entidade X.",
        kind=ClaimKind.FACT,
        evidence_ids=[block.evidence_id],
        support_status=SupportStatus.DIRECT,
        render_as_definitive=True,
    )

    report = EvidenceValidator([block]).validate([claim])

    assert report.valid is True
    assert report.issues == []
    assert report.checked_claims == 1
    assert report.checked_evidence == 1
    assert report.locale == "pt-PT"


def test_missing_evidence_identifier_is_rejected():
    claim = Claim(
        claim_id="CLM-002",
        text="A competência pertence à entidade X.",
        kind=ClaimKind.FACT,
        evidence_ids=["EV-MISSING"],
        support_status=SupportStatus.DIRECT,
    )

    report = EvidenceValidator([]).validate([claim])

    assert report.valid is False
    assert {issue.code for issue in report.issues} == {"EVIDENCE_NOT_FOUND"}


def test_quote_must_occur_in_associated_evidence():
    block = _evidence(raw_text="<p>A medida é obrigatória.</p>")
    valid_quote = Claim(
        claim_id="CLM-003",
        text="A fonte afirma que a medida é obrigatória.",
        kind=ClaimKind.QUOTE,
        quoted_text="A medida é obrigatória.",
        evidence_ids=[block.evidence_id],
        support_status=SupportStatus.DIRECT,
    )
    invalid_quote = Claim(
        claim_id="CLM-004",
        text="A fonte contém outro texto.",
        kind=ClaimKind.QUOTE,
        quoted_text="A medida é facultativa.",
        evidence_ids=[block.evidence_id],
        support_status=SupportStatus.DIRECT,
    )

    valid_report = EvidenceValidator([block]).validate([valid_quote])
    invalid_report = EvidenceValidator([block]).validate([invalid_quote])

    assert valid_report.valid is True
    assert invalid_report.valid is False
    assert "QUOTE_NOT_FOUND_IN_EVIDENCE" in {
        issue.code for issue in invalid_report.issues
    }


def test_modified_evidence_text_is_detected_by_hash():
    block = _evidence(text_hash="b" * 64)
    report = EvidenceValidator([block]).validate([])

    assert report.valid is False
    assert "EVIDENCE_TEXT_HASH_MISMATCH" in {
        issue.code for issue in report.issues
    }


def test_approximate_statistic_requires_uncertainty_note():
    block = _evidence(raw_text="O valor comunicado foi aproximadamente 95 por cento.")
    claim = Claim(
        claim_id="CLM-005",
        text="O valor foi aproximadamente 95 por cento.",
        kind=ClaimKind.STATISTIC,
        numeric_status=NumericStatus.APPROXIMATE,
        evidence_ids=[block.evidence_id],
        support_status=SupportStatus.DIRECT,
    )

    report = EvidenceValidator([block]).validate([claim])

    assert report.valid is False
    assert "NUMERIC_UNCERTAINTY_NOT_DISCLOSED" in {
        issue.code for issue in report.issues
    }


def test_time_sensitive_claim_requires_confirmed_freshness():
    block = _evidence()
    claim = Claim(
        claim_id="CLM-006",
        text="A regra encontra-se atualmente em vigor.",
        kind=ClaimKind.FACT,
        evidence_ids=[block.evidence_id],
        support_status=SupportStatus.DIRECT,
        time_sensitive=True,
        as_of=date(2026, 7, 27),
        freshness_status=FreshnessStatus.UNKNOWN,
    )

    report = EvidenceValidator([block]).validate([claim])

    assert report.valid is False
    assert "FRESHNESS_UNKNOWN" in {issue.code for issue in report.issues}


def test_inference_cannot_be_rendered_as_definitive():
    block = _evidence()
    claim = Claim(
        claim_id="CLM-007",
        text="Da norma resulta necessariamente a conclusão Y.",
        kind=ClaimKind.FACT,
        evidence_ids=[block.evidence_id],
        support_status=SupportStatus.INFERENCE,
        render_as_definitive=True,
    )

    report = EvidenceValidator([block]).validate([claim])

    assert report.valid is False
    assert "NON_DIRECT_CLAIM_RENDERED_AS_DEFINITIVE" in {
        issue.code for issue in report.issues
    }


def test_user_assertion_is_not_automatically_verified():
    claim = Claim(
        claim_id="CLM-008",
        text="O utilizador afirmou que o documento está em vigor.",
        kind=ClaimKind.USER_PROVIDED,
        support_status=SupportStatus.DIRECT,
        render_as_definitive=True,
    )

    report = EvidenceValidator([]).validate([claim])

    assert report.valid is False
    assert "USER_ASSERTION_TREATED_AS_VERIFIED" in {
        issue.code for issue in report.issues
    }
