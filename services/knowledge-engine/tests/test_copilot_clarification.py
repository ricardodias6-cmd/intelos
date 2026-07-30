from __future__ import annotations

from typing import Any

import pytest

from open_notebook.copilot.models import (
    CopilotChatRequest,
    CopilotChatResponse,
    CopilotResponseMode,
)
from open_notebook.evidence.clarification import requires_clarification
from open_notebook.evidence import auditable_answer
from open_notebook.evidence.auditable_answer import (
    AuditableAnswerRequest,
    build_auditable_answer,
)
from open_notebook.evidence.auditable_models import (
    AnswerAuditMetadata,
    AnswerCitation,
    AnswerClaim,
    AuditableAnswer,
    AuditableAnswerStatus,
)
from open_notebook.evidence.models import ClaimKind, SupportStatus
from open_notebook.evidence.retrieval import EvidenceSearchResponse


def _answered_answer() -> AuditableAnswer:
    return AuditableAnswer(
        answer_id="ANSWER_CLARIFICATION_001",
        audit_report_id="AUDIT_CLARIFICATION_001",
        answer="A autorização compete à entidade competente.",
        claims=[
            AnswerClaim(
                claim_id="CLM_001",
                text="A autorização compete à entidade competente.",
                kind=ClaimKind.FACT,
                evidence_ids=["EV_ONE"],
                support_status=SupportStatus.DIRECT,
                confidence=0.91,
            )
        ],
        citations=[
            AnswerCitation(
                evidence_id="EV_ONE",
                source_id="SOURCE_ONE",
                document_version_id="DOCUMENT_VERSION_ONE",
                document_version_hash="HASH_ONE",
                text="Texto documental que não deve ser repetido na projeção.",
            )
        ],
        overall_confidence=0.91,
        status=AuditableAnswerStatus.ANSWERED,
        audit=AnswerAuditMetadata(
            question_hash="sha256:question",
            selected_evidence_ids=["EV_ONE"],
            retrieval_scores={"EV_ONE": 0.91},
            pipeline_version="phase-9",
            stage_durations_ms={"retrieval": 4, "generation": 8},
        ),
    )


def test_deictic_question_without_context_requires_clarification() -> None:
    decision = requires_clarification("O que é isso?")

    assert decision.required is True
    assert decision.reason == "deictic_reference_without_context"
    assert decision.question is not None


def test_deictic_question_with_context_uses_normal_pipeline() -> None:
    decision = requires_clarification(
        "O que é isso?",
        conversation_context=["Previous answer: ..."],
    )

    assert decision.required is False


@pytest.mark.asyncio
async def test_clarification_does_not_call_retrieval_or_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unexpected_retrieve(**kwargs: Any) -> EvidenceSearchResponse:
        raise AssertionError("clarification must happen before retrieval")

    async def unexpected_persist(report: Any) -> None:
        return None

    monkeypatch.setattr(auditable_answer, "retrieve_evidence", unexpected_retrieve)
    monkeypatch.setattr(auditable_answer, "persist_audit_report", unexpected_persist)

    result = await build_auditable_answer(
        AuditableAnswerRequest(question="O que é isso?")
    )

    assert result.status == AuditableAnswerStatus.CLARIFICATION_REQUIRED
    assert result.claims == []
    assert result.citations == []
    assert result.overall_confidence == 0
    assert result.answer_id is not None
    assert result.audit_report_id is not None
    assert result.clarification_question is not None
    assert result.audit.stage_durations_ms["clarification"] == 0


def test_response_modes_preserve_validated_contract() -> None:
    answer = _answered_answer()
    responses = [
        CopilotChatResponse.from_auditable_answer(
            CopilotChatRequest(
                question="Quem decide?",
                response_mode=mode,
                include_knowledge_graph=False,
            ),
            answer,
            conversation_id="CONV_MODES",
            turn_id=f"TURN_{mode.value.upper()}",
        )
        for mode in CopilotResponseMode
    ]

    assert {response.claims[0].evidence_ids[0] for response in responses} == {
        "EV_ONE"
    }
    assert {response.overall_confidence for response in responses} == {0.91}
    assert {response.status.value for response in responses} == {"answered"}
    assert responses[0].answer == answer.answer
    assert "Claims validadas" in responses[1].answer
    assert "Percurso auditável" in responses[2].answer
    assert "Texto documental que não deve ser repetido" not in responses[2].answer


def test_clarification_response_exposes_one_safe_next_action() -> None:
    answer = AuditableAnswer(
        answer_id="ANSWER_CLARIFICATION_002",
        audit_report_id="AUDIT_CLARIFICATION_002",
        answer="Preciso de um esclarecimento para responder com precisão.",
        claims=[],
        citations=[],
        overall_confidence=0,
        status=AuditableAnswerStatus.CLARIFICATION_REQUIRED,
        clarification_question="A que documento se refere?",
        audit=AnswerAuditMetadata(
            question_hash="sha256:question",
            pipeline_version="phase-9",
        ),
    )
    response = CopilotChatResponse.from_auditable_answer(
        CopilotChatRequest(question="O que é isso?"),
        answer,
        conversation_id="CONV_CLARIFICATION",
        turn_id="TURN_CLARIFICATION",
    )

    assert response.status.value == "clarification_required"
    assert len(response.next_actions) == 1
    assert response.next_actions[0].question == "A que documento se refere?"
    assert response.claims == []
    assert response.citations == []
