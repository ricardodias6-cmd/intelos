"""Safe projections for presenting an evidence audit report."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from open_notebook.audit.models import (
    AuditConflict,
    AuditEvidenceDecision,
    AuditFreshness,
    AuditReport,
    AuditTraceEvent,
)
from open_notebook.evidence.auditable_models import (
    AnswerCitation,
    AnswerClaim,
    AuditableAnswerStatus,
)


class AuditPresentationMode(StrEnum):
    """Display emphasis requested by the audit client."""

    SUMMARY = "summary"
    DETAILED = "detailed"
    AUDIT = "audit"


class AuditPresentationCounts(BaseModel):
    """Stable counts for compact UI summaries."""

    claims: int = Field(ge=0)
    citations: int = Field(ge=0)
    selected_evidence: int = Field(ge=0)
    rejected_evidence: int = Field(ge=0)
    conflicts: int = Field(ge=0)
    trace_events: int = Field(ge=0)


class AuditPresentation(BaseModel):
    """A safe, presentation-oriented view of one AuditReport.

    The projection always retains the complete auditable payload. The mode
    changes presentation emphasis in clients; it never authorizes removal of
    claims, citations, evidence decisions, conflicts, or trace events.
    Conversation metadata is limited to stable identifiers and raw metadata
    from AuditReport is intentionally not exposed.
    """

    mode: AuditPresentationMode
    audit_id: str
    answer_id: str
    conversation_id: str | None = None
    turn_id: str | None = None
    response_mode: str
    question: str
    answer: str
    status: AuditableAnswerStatus
    overall_confidence: float = Field(ge=0, le=1)
    requires_human_review: bool
    freshness: AuditFreshness
    claims: list[AnswerClaim] = Field(default_factory=list, max_length=200)
    citations: list[AnswerCitation] = Field(default_factory=list, max_length=200)
    selected_evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    rejected_evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    evidence_decisions: list[AuditEvidenceDecision] = Field(
        default_factory=list,
        max_length=2000,
    )
    conflicts: list[AuditConflict] = Field(default_factory=list, max_length=100)
    trace: list[AuditTraceEvent] = Field(default_factory=list, max_length=100)
    pipeline_version: str
    embedding_model: str | None = None
    generated_at: datetime
    counts: AuditPresentationCounts

    @model_validator(mode="after")
    def validate_counts(self) -> "AuditPresentation":
        expected = AuditPresentationCounts(
            claims=len(self.claims),
            citations=len(self.citations),
            selected_evidence=len(self.selected_evidence_ids),
            rejected_evidence=len(self.rejected_evidence_ids),
            conflicts=len(self.conflicts),
            trace_events=len(self.trace),
        )
        if self.counts != expected:
            raise ValueError("presentation counts must match the audit payload")
        return self


def build_audit_presentation(
    report: AuditReport,
    mode: AuditPresentationMode = AuditPresentationMode.SUMMARY,
) -> AuditPresentation:
    """Create a complete safe presentation projection without mutating the report."""

    return AuditPresentation(
        mode=mode,
        audit_id=report.audit_id,
        answer_id=report.answer_id,
        conversation_id=report.conversation_id,
        turn_id=report.turn_id,
        response_mode=report.response_mode,
        question=report.question,
        answer=report.answer,
        status=report.status,
        overall_confidence=report.overall_confidence,
        requires_human_review=report.requires_human_review,
        freshness=report.freshness,
        claims=list(report.claims),
        citations=list(report.citations),
        selected_evidence_ids=list(report.selected_evidence_ids),
        rejected_evidence_ids=list(report.rejected_evidence_ids),
        evidence_decisions=list(report.evidence_decisions),
        conflicts=list(report.conflicts),
        trace=list(report.trace),
        pipeline_version=report.pipeline_version,
        embedding_model=report.embedding_model,
        generated_at=report.generated_at,
        counts=AuditPresentationCounts(
            claims=len(report.claims),
            citations=len(report.citations),
            selected_evidence=len(report.selected_evidence_ids),
            rejected_evidence=len(report.rejected_evidence_ids),
            conflicts=len(report.conflicts),
            trace_events=len(report.trace),
        ),
    )
