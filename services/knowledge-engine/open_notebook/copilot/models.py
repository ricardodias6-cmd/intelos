"""Structured contracts for the Intelos Copilot API."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from open_notebook.audit.models import AuditConflict
from open_notebook.copilot.presentation import render_copilot_answer
from open_notebook.evidence.auditable_answer import AuditableAnswerRequest
from open_notebook.evidence.auditable_models import (
    AnswerAuditMetadata,
    AnswerCitation,
    AnswerClaim,
    AuditableAnswer,
)
from open_notebook.evidence.models import SupportStatus


class CopilotResponseMode(StrEnum):
    """Presentation detail requested for a Copilot turn."""

    CONCISE = "concise"
    DETAILED = "detailed"
    AUDIT = "audit"


class CopilotTurnStatus(StrEnum):
    """Public status of one Copilot turn."""

    ANSWERED = "answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICT = "conflict"
    CLARIFICATION_REQUIRED = "clarification_required"
    TECHNICAL_ERROR = "technical_error"


class CopilotNextActionType(StrEnum):
    """Safe follow-up action suggested by the Copilot."""

    CLARIFICATION = "clarification"


class CopilotNextAction(BaseModel):
    """A non-destructive next step suggested to the client."""

    model_config = ConfigDict(extra="forbid")

    type: CopilotNextActionType
    question: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def validate_action(self) -> "CopilotNextAction":
        if self.type == CopilotNextActionType.CLARIFICATION and not self.question:
            raise ValueError("clarification actions require a question")
        return self


class CopilotChatRequest(BaseModel):
    """Validated input for one Copilot chat turn."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str | None = Field(default=None, min_length=3, max_length=128)
    question: str = Field(min_length=1, max_length=10000)
    response_mode: CopilotResponseMode = CopilotResponseMode.CONCISE
    max_evidence: int = Field(default=8, ge=1, le=20)
    source_id: str | None = Field(default=None, min_length=1, max_length=128)
    version_hash: str | None = Field(default=None, min_length=1, max_length=200)
    include_knowledge_graph: bool = True

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question cannot be blank")
        return normalized

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("conversation_id cannot be blank")
        return normalized

    def to_auditable_answer_request(
        self,
        *,
        conversation_context: Sequence[str] = (),
    ) -> AuditableAnswerRequest:
        """Build the phase 4 request without exposing Copilot-only fields."""

        return AuditableAnswerRequest(
            question=self.question,
            max_evidence=self.max_evidence,
            source_id=self.source_id,
            version_hash=self.version_hash,
            conversation_context=list(conversation_context),
            include_knowledge_graph=self.include_knowledge_graph,
        )


class CopilotChatResponse(BaseModel):
    """Public response contract for one auditable Copilot turn."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(min_length=3, max_length=128)
    turn_id: str = Field(min_length=3, max_length=128)
    answer_id: str = Field(min_length=3, max_length=128)
    audit_report_id: str = Field(min_length=3, max_length=128)
    response_mode: CopilotResponseMode
    answer: str = Field(min_length=1, max_length=50000)
    claims: list[AnswerClaim] = Field(default_factory=list, max_length=200)
    citations: list[AnswerCitation] = Field(default_factory=list, max_length=200)
    overall_confidence: float = Field(ge=0, le=1)
    conflicts: list[AuditConflict] = Field(default_factory=list, max_length=100)
    gaps: list[str] = Field(default_factory=list, max_length=100)
    requires_human_review: bool = False
    status: CopilotTurnStatus
    next_actions: list[CopilotNextAction] = Field(
        default_factory=list,
        max_length=20,
    )
    audit: AnswerAuditMetadata | None = None

    @model_validator(mode="after")
    def validate_presentation(self) -> "CopilotChatResponse":
        presentable = [
            claim for claim in self.claims if claim.is_presentable_fact
        ]
        if self.status == CopilotTurnStatus.ANSWERED and not presentable:
            raise ValueError("answered Copilot turns require a presentable claim")
        if (
            self.status == CopilotTurnStatus.INSUFFICIENT_EVIDENCE
            and self.overall_confidence != 0
        ):
            raise ValueError(
                "insufficient-evidence Copilot turns must have zero confidence"
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
                "Copilot review flag must include claim review requirements"
            )
        if (
            self.response_mode == CopilotResponseMode.AUDIT
            and self.audit is None
        ):
            raise ValueError("audit response mode requires audit metadata")
        if not set(self.gaps).issubset(
            {
                claim.qualification
                for claim in self.claims
                if claim.qualification
            }
        ):
            raise ValueError("gaps must be claim qualifications from the response")
        return self

    @classmethod
    def from_auditable_answer(
        cls,
        request: CopilotChatRequest,
        answer: AuditableAnswer,
        *,
        conversation_id: str,
        turn_id: str,
    ) -> "CopilotChatResponse":
        """Project the validated phase 4 response into the Copilot contract."""

        if not answer.answer_id or not answer.audit_report_id:
            raise ValueError(
                "auditable answers must expose answer and audit report identifiers"
            )

        conflicts = [
            AuditConflict(
                conflict_id=f"CONFLICT_{claim.claim_id}",
                claim_id=claim.claim_id,
                evidence_ids=claim.evidence_ids,
                description=(
                    claim.qualification
                    or "A claim has contradictory supporting evidence."
                ),
            )
            for claim in answer.claims
            if (
                claim.support_status == SupportStatus.CONTRADICTED
                and claim.evidence_ids
            )
        ]
        gaps = [
            claim.qualification
            for claim in answer.claims
            if (
                claim.support_status
                in {
                    SupportStatus.UNSUPPORTED,
                    SupportStatus.INFERENCE,
                    SupportStatus.INTERPRETATION,
                }
                and claim.qualification
            )
        ]

        next_actions = []
        if answer.status.value == CopilotTurnStatus.CLARIFICATION_REQUIRED.value:
            next_actions = [
                CopilotNextAction(
                    type=CopilotNextActionType.CLARIFICATION,
                    question=answer.clarification_question,
                )
            ]

        return cls(
            conversation_id=conversation_id,
            turn_id=turn_id,
            answer_id=answer.answer_id,
            audit_report_id=answer.audit_report_id,
            response_mode=request.response_mode,
            answer=render_copilot_answer(answer, request.response_mode.value),
            claims=answer.claims,
            citations=answer.citations,
            overall_confidence=answer.overall_confidence,
            conflicts=conflicts,
            gaps=gaps,
            requires_human_review=answer.requires_human_review,
            status=CopilotTurnStatus(answer.status.value),
            next_actions=next_actions,
            audit=(
                answer.audit
                if request.response_mode == CopilotResponseMode.AUDIT
                else None
            ),
        )


def new_conversation_id() -> str:
    """Create a stable-format identifier for a new local conversation."""

    return f"CONV_{uuid4().hex.upper()}"


def new_turn_id() -> str:
    """Create a stable-format identifier for a conversation turn."""

    return f"TURN_{uuid4().hex.upper()}"
