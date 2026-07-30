from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from api.main import app
from api.routers import evidence
from open_notebook.audit import (
    AuditEvidenceDecision,
    AuditEvidenceDecisionType,
    AuditReport,
    AuditRevalidationRequest,
    AuditRevalidationResult,
    AuditRevalidationStatus,
    revalidate_audit_report,
)
from open_notebook.evidence.auditable_models import (
    AnswerClaim,
    AuditableAnswerStatus,
)
from open_notebook.evidence.models import ClaimKind, SupportStatus
from open_notebook.exceptions import InvalidInputError


def _report() -> AuditReport:
    return AuditReport(
        audit_id="AUDIT_REVALIDATION_001",
        answer_id="ANSWER_REVALIDATION_001",
        question="Quem decide?",
        question_hash="sha256:question",
        answer="A autorização compete à entidade competente.",
        claims=[
            AnswerClaim(
                claim_id="CLM_REVALIDATION_001",
                text="A autorização compete à entidade competente.",
                kind=ClaimKind.FACT,
                evidence_ids=["EV_REVALIDATION_001"],
                support_status=SupportStatus.DIRECT,
                confidence=0.91,
            )
        ],
        citations=[],
        overall_confidence=0.91,
        status=AuditableAnswerStatus.ANSWERED,
        selected_evidence_ids=["EV_REVALIDATION_001"],
        evidence_decisions=[
            AuditEvidenceDecision(
                evidence_id="EV_REVALIDATION_001",
                decision=AuditEvidenceDecisionType.SELECTED,
                retrieval_score=0.91,
                rank=1,
            )
        ],
        pipeline_version="phase-10-3",
        generated_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
    )


def test_revalidation_contract_requires_strong_idempotency_key() -> None:
    with pytest.raises(ValidationError, match="String should have at least 16 characters"):
        AuditRevalidationRequest(
            source_audit_id="AUDIT_REVALIDATION_001",
            idempotency_key="short",
            reason="Refresh current evidence",
        )


@pytest.mark.asyncio
async def test_revalidation_is_idempotent_and_preserves_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _report()
    records: dict[str, Any] = {}
    build_calls = 0

    async def fake_get_report(audit_id: str) -> AuditReport:
        assert audit_id == source.audit_id
        return source

    async def fake_get_record(key: str) -> Any:
        return records.get(key)

    async def fake_persist(record: Any) -> None:
        records[record.idempotency_key] = record

    async def fake_build(request: Any, *, model_id: str | None = None) -> Any:
        nonlocal build_calls
        build_calls += 1
        assert request.question == source.question
        return SimpleNamespace(
            answer_id="ANSWER_REVALIDATION_002",
            audit_report_id="AUDIT_REVALIDATION_002",
        )

    monkeypatch.setattr(
        "open_notebook.audit.revalidation.get_audit_report_by_id",
        fake_get_report,
    )
    monkeypatch.setattr(
        "open_notebook.audit.revalidation.get_audit_revalidation",
        fake_get_record,
    )
    monkeypatch.setattr(
        "open_notebook.audit.revalidation.persist_audit_revalidation",
        fake_persist,
    )
    monkeypatch.setattr(
        "open_notebook.evidence.auditable_answer.build_auditable_answer",
        fake_build,
    )

    request = AuditRevalidationRequest(
        source_audit_id=source.audit_id,
        idempotency_key="revalidation-key-0001",
        reason="Document version changed.",
        evidence_ids=["EV_REVALIDATION_001"],
        change_ids=["CHANGE_REVALIDATION_001"],
    )

    first = await revalidate_audit_report(source.answer_id, request)
    second = await revalidate_audit_report(source.answer_id, request)

    assert first.replayed is False
    assert second.replayed is True
    assert first.result_answer_id == second.result_answer_id
    assert build_calls == 1
    assert source.answer_id == "ANSWER_REVALIDATION_001"
    assert source.audit_id == "AUDIT_REVALIDATION_001"


@pytest.mark.asyncio
async def test_revalidation_rejects_evidence_outside_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _report()

    async def fake_get_report(audit_id: str) -> AuditReport:
        return source

    monkeypatch.setattr(
        "open_notebook.audit.revalidation.get_audit_report_by_id",
        fake_get_report,
    )
    request = AuditRevalidationRequest(
        source_audit_id=source.audit_id,
        idempotency_key="revalidation-key-0002",
        reason="Changed evidence.",
        evidence_ids=["EV_NOT_IN_REPORT"],
    )

    with pytest.raises(InvalidInputError, match="belong"):
        await revalidate_audit_report(source.answer_id, request)


@pytest.mark.asyncio
async def test_revalidation_endpoint_returns_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_revalidate(
        answer_id: str,
        request: AuditRevalidationRequest,
    ) -> AuditRevalidationResult:
        assert answer_id == "ANSWER_REVALIDATION_001"
        assert request.source_audit_id == "AUDIT_REVALIDATION_001"
        return AuditRevalidationResult(
            status=AuditRevalidationStatus.COMPLETED,
            idempotency_key=request.idempotency_key,
            source_audit_id=request.source_audit_id,
            source_answer_id=answer_id,
            result_audit_id="AUDIT_REVALIDATION_002",
            result_answer_id="ANSWER_REVALIDATION_002",
            reason=request.reason,
            completed_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
        )

    monkeypatch.setattr(evidence, "revalidate_audit_report", fake_revalidate)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/evidence/answer/ANSWER_REVALIDATION_001/audit/revalidate",
            json={
                "source_audit_id": "AUDIT_REVALIDATION_001",
                "idempotency_key": "revalidation-key-0003",
                "reason": "Document version changed.",
                "evidence_ids": ["EV_REVALIDATION_001"],
                "change_ids": ["CHANGE_REVALIDATION_001"],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["replayed"] is False
    assert payload["result_answer_id"] == "ANSWER_REVALIDATION_002"
