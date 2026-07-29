"""Contracts for explainable, evidence-linked answer audit reports."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from open_notebook.evidence.auditable_models import (
    AnswerCitation,
    AnswerClaim,
    AuditableAnswerStatus,
)

_STABLE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{2,127}$")


def _validate_stable_id(value: str) -> str:
    if not _STABLE_ID_RE.fullmatch(value):
        raise ValueError(
            "identifier must use upper-case letters, numbers, underscores or hyphens"
        )
    return value


class AuditEvidenceDecisionType(StrEnum):
    """Decision taken for a candidate Evidence Block."""

    SELECTED = "selected"
    REJECTED = "rejected"
    NOT_SELECTED = "not_selected"


class AuditConflictSeverity(StrEnum):
    """Severity of a conflict that requires explanation or review."""

    WARNING = "warning"
    ERROR = "error"


class AuditEvidenceDecision(BaseModel):
    """Why one candidate Evidence Block entered or left the answer path."""

    evidence_id: str = Field(min_length=3, max_length=128)
    decision: AuditEvidenceDecisionType
    reason: str | None = Field(default=None, max_length=2000)
    retrieval_score: float | None = Field(default=None, ge=0, le=1)
    rank: int | None = Field(default=None, ge=1)

    @field_validator("evidence_id")
    @classmethod
    def validate_evidence_id(cls, value: str) -> str:
        return _validate_stable_id(value)

    @model_validator(mode="after")
    def validate_explanation(self) -> "AuditEvidenceDecision":
        if self.decision != AuditEvidenceDecisionType.SELECTED and not self.reason:
            raise ValueError(
                "rejected or not-selected evidence requires a reason"
            )
        return self


class AuditConflict(BaseModel):
    """A material disagreement between evidence or claims."""

    conflict_id: str = Field(min_length=3, max_length=128)
    claim_id: str | None = Field(default=None, min_length=3, max_length=128)
    evidence_ids: list[str] = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1, max_length=5000)
    severity: AuditConflictSeverity = AuditConflictSeverity.WARNING

    @field_validator("conflict_id")
    @classmethod
    def validate_conflict_id(cls, value: str) -> str:
        return _validate_stable_id(value)

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, value: list[str]) -> list[str]:
        normalized = [_validate_stable_id(item) for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("conflict Evidence IDs must be unique")
        return normalized


class AuditTraceEvent(BaseModel):
    """One reproducible stage in the answer production path."""

    stage: str = Field(min_length=1, max_length=100)
    status: str = Field(default="completed", min_length=1, max_length=40)
    duration_ms: int = Field(default=0, ge=0)
    details: dict[str, Any] = Field(default_factory=dict)


class AuditReport(BaseModel):
    """Complete explainability record associated with one answer."""

    audit_id: str = Field(min_length=3, max_length=128)
    answer_id: str = Field(min_length=3, max_length=128)
    question: str = Field(min_length=1, max_length=10000)
    question_hash: str = Field(min_length=1, max_length=200)
    answer: str = Field(min_length=1, max_length=50000)
    claims: list[AnswerClaim] = Field(default_factory=list, max_length=200)
    citations: list[AnswerCitation] = Field(default_factory=list, max_length=200)
    overall_confidence: float = Field(ge=0, le=1)
    requires_human_review: bool = False
    status: AuditableAnswerStatus
    selected_evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    evidence_decisions: list[AuditEvidenceDecision] = Field(
        default_factory=list,
        max_length=2000,
    )
    conflicts: list[AuditConflict] = Field(default_factory=list, max_length=100)
    trace: list[AuditTraceEvent] = Field(default_factory=list, max_length=100)
    pipeline_version: str = Field(min_length=1, max_length=100)
    embedding_model: str | None = Field(default=None, max_length=200)
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("audit_id", "answer_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        return _validate_stable_id(value)

    @field_validator("selected_evidence_ids")
    @classmethod
    def validate_selected_evidence_ids(cls, value: list[str]) -> list[str]:
        normalized = [_validate_stable_id(item) for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("selected Evidence IDs must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_report_consistency(self) -> "AuditReport":
        decisions_by_id: dict[str, AuditEvidenceDecision] = {}
        for decision in self.evidence_decisions:
            if decision.evidence_id in decisions_by_id:
                raise ValueError("evidence decisions must be unique by Evidence ID")
            decisions_by_id[decision.evidence_id] = decision

        selected_decisions = {
            evidence_id
            for evidence_id, decision in decisions_by_id.items()
            if decision.decision == AuditEvidenceDecisionType.SELECTED
        }
        if selected_decisions != set(self.selected_evidence_ids):
            raise ValueError(
                "selected Evidence IDs must match selected evidence decisions"
            )

        citation_ids = {citation.evidence_id for citation in self.citations}
        if not citation_ids.issubset(set(self.selected_evidence_ids)):
            raise ValueError(
                "citations may only reference selected Evidence IDs"
            )

        claim_ids: set[str] = set()
        for claim in self.claims:
            if claim.claim_id in claim_ids:
                raise ValueError("claim IDs must be unique")
            claim_ids.add(claim.claim_id)
            if not set(claim.evidence_ids).issubset(
                set(self.selected_evidence_ids)
            ):
                raise ValueError(
                    "claims may only reference selected Evidence IDs"
                )

        for conflict in self.conflicts:
            if not set(conflict.evidence_ids).issubset(decisions_by_id):
                raise ValueError(
                    "conflicts may only reference audited Evidence IDs"
                )
            if conflict.claim_id and conflict.claim_id not in claim_ids:
                raise ValueError(
                    "conflicts may only reference audited claim IDs"
                )

        presentable = [claim for claim in self.claims if claim.is_presentable_fact]
        if self.status == AuditableAnswerStatus.ANSWERED and not presentable:
            raise ValueError(
                "answered audit reports require a presentable claim"
            )
        if (
            self.status == AuditableAnswerStatus.INSUFFICIENT_EVIDENCE
            and self.overall_confidence != 0
        ):
            raise ValueError(
                "insufficient-evidence reports must have zero confidence"
            )
        if presentable and self.overall_confidence > min(
            claim.confidence for claim in presentable
        ):
            raise ValueError(
                "overall confidence cannot exceed the weakest presented claim"
            )
        if any(
            claim.requires_human_review for claim in self.claims
        ) and not self.requires_human_review:
            raise ValueError(
                "report review flag must include claim review requirements"
            )
        return self

    @property
    def rejected_evidence_ids(self) -> list[str]:
        """Return candidate Evidence IDs explicitly rejected by the pipeline."""

        return [
            decision.evidence_id
            for decision in self.evidence_decisions
            if decision.decision == AuditEvidenceDecisionType.REJECTED
        ]

    @property
    def audited_evidence_ids(self) -> list[str]:
        """Return every Evidence ID represented in the audit trail."""

        return [
            decision.evidence_id for decision in self.evidence_decisions
        ]


class AuditReportPersistenceResult(BaseModel):
    """Outcome of persisting one report and its Evidence links."""

    audit_id: str
    answer_id: str
    evidence_links_upserted: int = Field(ge=0)
    evidence_ids: list[str] = Field(default_factory=list)
    persisted: bool = True
