from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from api.main import app
from api.routers import evidence
from open_notebook.audit import (
    AuditConflict,
    AuditEvidenceDecision,
    AuditEvidenceDecisionType,
    AuditFreshnessStatus,
    AuditPresentation,
    AuditPresentationMode,
    AuditReport,
    build_audit_presentation,
)
from open_notebook.evidence.auditable_models import (
    AnswerCitation,
    AnswerClaim,
    AuditableAnswerStatus,
)
from open_notebook.evidence.models import ClaimKind, SupportStatus


def _report() -> AuditReport:
    return AuditReport(
        audit_id="AUDIT_PRESENTATION_001",
        answer_id="ANSWER_PRESENTATION_001",
        conversation_id="CONV_PRESENTATION_001",
        turn_id="TURN_PRESENTATION_001",
        response_mode="audit",
        question="Quem decide?",
        question_hash="sha256:question",
        answer="A autorização compete à entidade competente.",
        claims=[
            AnswerClaim(
                claim_id="CLM_PRESENTATION_001",
                text="A autorização compete à entidade competente.",
                kind=ClaimKind.FACT,
                evidence_ids=["EV_PRESENTATION_001"],
                support_status=SupportStatus.DIRECT,
                confidence=0.91,
            )
        ],
        citations=[
            AnswerCitation(
                evidence_id="EV_PRESENTATION_001",
                source_id="SOURCE_PRESENTATION_001",
                document_version_id="VERSION_PRESENTATION_001",
                document_version_hash="hash:presentation",
                pdf_page=2,
                text="A autorização compete à entidade competente.",
            )
        ],
        overall_confidence=0.91,
        status=AuditableAnswerStatus.ANSWERED,
        selected_evidence_ids=["EV_PRESENTATION_001"],
        evidence_decisions=[
            AuditEvidenceDecision(
                evidence_id="EV_PRESENTATION_001",
                decision=AuditEvidenceDecisionType.SELECTED,
                retrieval_score=0.91,
                rank=1,
            )
        ],
        conflicts=[
            AuditConflict(
                conflict_id="CONFLICT_PRESENTATION_001",
                evidence_ids=["EV_PRESENTATION_001"],
                description="Sem conflito material.",
            )
        ],
        pipeline_version="phase-10",
        generated_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
    )


def test_presentation_preserves_auditable_payload() -> None:
    report = _report()

    presentation = build_audit_presentation(
        report,
        AuditPresentationMode.AUDIT,
    )

    assert isinstance(presentation, AuditPresentation)
    assert presentation.mode == AuditPresentationMode.AUDIT
    assert presentation.answer_id == report.answer_id
    assert presentation.claims[0].evidence_ids == ["EV_PRESENTATION_001"]
    assert presentation.citations[0].evidence_id == "EV_PRESENTATION_001"
    assert presentation.freshness.status == AuditFreshnessStatus.CURRENT
    assert presentation.counts.claims == 1
    assert presentation.counts.trace_events == 0
    assert "metadata" not in presentation.model_fields


def test_presentation_rejects_inconsistent_counts() -> None:
    with pytest.raises(ValidationError, match="counts"):
        payload = build_audit_presentation(_report()).model_dump(
            mode="python"
        )
        payload["counts"] = {
            "claims": 0,
            "citations": 0,
            "selected_evidence": 0,
            "rejected_evidence": 0,
            "conflicts": 0,
            "trace_events": 0,
        }
        AuditPresentation(**payload)


@pytest.mark.asyncio
async def test_presentation_endpoint_returns_requested_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(
        answer_id: str,
        mode: AuditPresentationMode,
    ) -> AuditPresentation:
        assert answer_id == "ANSWER_PRESENTATION_001"
        assert mode == AuditPresentationMode.DETAILED
        return build_audit_presentation(_report(), mode)

    monkeypatch.setattr(evidence, "get_audit_presentation", fake_get)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/evidence/answer/ANSWER_PRESENTATION_001/audit/presentation",
            params={"mode": "detailed"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "detailed"
    assert body["answer_id"] == "ANSWER_PRESENTATION_001"
    assert body["counts"]["claims"] == 1
    assert body["freshness"]["status"] == "current"