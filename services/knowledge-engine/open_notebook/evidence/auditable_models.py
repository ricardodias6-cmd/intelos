"""Structured contract for the phase 4 auditable answer pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from open_notebook.evidence.models import ClaimKind, SupportStatus


class AuditableAnswerStatus(StrEnum):
    ANSWERED = "answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICT = "conflict"
    CLARIFICATION_REQUIRED = "clarification_required"


class AnswerCitation(BaseModel):
    """A rendered citation projected from one validated Evidence Block."""

    evidence_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    document_version_id: str = Field(min_length=1)
    document_version_hash: str = Field(min_length=1)
    pdf_page: int | None = Field(default=None, ge=1)
    printed_page: str | None = None
    section_path: list[str] = Field(default_factory=list)
    text: str = Field(min_length=1)


class AnswerClaim(BaseModel):
    """One atomic claim that survived the phase 4 presentation policy."""

    claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=10000)
    kind: ClaimKind
    evidence_ids: list[str] = Field(default_factory=list)
    support_status: SupportStatus
    confidence: float = Field(ge=0, le=1)
    requires_human_review: bool = False
    qualification: str | None = None

    @model_validator(mode="after")
    def validate_presentation_shape(self) -> "AnswerClaim":
        if self.support_status in {
            SupportStatus.DIRECT,
            SupportStatus.PARTIAL,
        } and not self.evidence_ids:
            raise ValueError(
                "presented supported claims require at least one Evidence ID"
            )

        if self.support_status in {
            SupportStatus.INFERENCE,
            SupportStatus.INTERPRETATION,
            SupportStatus.UNSUPPORTED,
            SupportStatus.CONTRADICTED,
        } and not self.qualification:
            raise ValueError(
                "non-definitive claims require a qualification"
            )

        if self.support_status in {
            SupportStatus.UNSUPPORTED,
            SupportStatus.CONTRADICTED,
        } and self.confidence != 0:
            raise ValueError(
                "unsupported or contradicted claims cannot carry presentation confidence"
            )

        return self

    @property
    def is_presentable_fact(self) -> bool:
        return self.support_status in {
            SupportStatus.DIRECT,
            SupportStatus.PARTIAL,
        }


class AnswerAuditMetadata(BaseModel):
    """Metadata needed to reconstruct how the answer was produced."""

    question_hash: str = Field(min_length=1)
    selected_evidence_ids: list[str] = Field(default_factory=list)
    retrieval_scores: dict[str, float] = Field(default_factory=dict)
    embedding_model: str | None = None
    direct_threshold: float = Field(default=0.82, ge=0.6, le=0.98)
    partial_threshold: float = Field(default=0.58, ge=0.5, le=0.9)
    pipeline_version: str = Field(default="phase-4", min_length=1)
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    stage_durations_ms: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_thresholds(self) -> "AnswerAuditMetadata":
        if self.direct_threshold <= self.partial_threshold:
            raise ValueError(
                "direct_threshold must be greater than partial_threshold"
            )
        if not set(self.retrieval_scores).issubset(
            set(self.selected_evidence_ids)
        ):
            raise ValueError(
                "retrieval scores may only reference selected Evidence IDs"
            )
        if any(duration < 0 for duration in self.stage_durations_ms.values()):
            raise ValueError("stage durations cannot be negative")
        return self


class AuditableAnswer(BaseModel):
    """Final response contract for the phase 4 pipeline."""

    answer_id: str | None = Field(default=None, min_length=3, max_length=128)
    audit_report_id: str | None = Field(
        default=None,
        min_length=3,
        max_length=128,
    )
    answer: str = Field(min_length=1, max_length=50000)
    claims: list[AnswerClaim] = Field(default_factory=list)
    citations: list[AnswerCitation] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0, le=1)
    requires_human_review: bool = False
    clarification_question: str | None = Field(default=None, max_length=10000)
    status: AuditableAnswerStatus
    audit: AnswerAuditMetadata

    @model_validator(mode="after")
    def validate_evidence_links(self) -> "AuditableAnswer":
        if self.status == AuditableAnswerStatus.CLARIFICATION_REQUIRED and not self.clarification_question:
            raise ValueError("clarification responses require a clarification question")
        if self.status != AuditableAnswerStatus.CLARIFICATION_REQUIRED and self.clarification_question is not None:
            raise ValueError("clarification question is only valid for clarification responses")

        selected_ids = set(self.audit.selected_evidence_ids)
        citation_ids = {citation.evidence_id for citation in self.citations}

        if len(self.audit.selected_evidence_ids) != len(selected_ids):
            raise ValueError("selected Evidence IDs must be unique")
        if len(citation_ids) != len(self.citations):
            raise ValueError("citations must be unique by Evidence ID")
        if not citation_ids.issubset(selected_ids):
            raise ValueError(
                "citations may only reference selected Evidence IDs"
            )

        claim_ids: set[str] = set()
        for claim in self.claims:
            if claim.claim_id in claim_ids:
                raise ValueError("claim IDs must be unique")
            claim_ids.add(claim.claim_id)

            claim_evidence = set(claim.evidence_ids)
            if not claim_evidence.issubset(selected_ids):
                raise ValueError(
                    "claims may only reference selected Evidence IDs"
                )
            if not claim_evidence.issubset(citation_ids):
                raise ValueError(
                    "every claim Evidence ID must have a citation"
                )

        presentable = [
            claim for claim in self.claims if claim.is_presentable_fact
        ]
        if self.status == AuditableAnswerStatus.ANSWERED and not presentable:
            raise ValueError(
                "answered responses require at least one presentable claim"
            )
        if (
            self.status == AuditableAnswerStatus.INSUFFICIENT_EVIDENCE
            and self.overall_confidence != 0
        ):
            raise ValueError(
                "insufficient-evidence responses must have zero confidence"
            )
        if (
            presentable
            and self.overall_confidence
            > min(claim.confidence for claim in presentable)
        ):
            raise ValueError(
                "overall confidence cannot exceed the weakest presented claim"
            )
        if any(
            claim.requires_human_review for claim in self.claims
        ) and not self.requires_human_review:
            raise ValueError(
                "answer review flag must include claim review requirements"
            )

        return self
