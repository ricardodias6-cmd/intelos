from __future__ import annotations

from typing import Any

import httpx
import pytest

from api.main import app
from open_notebook.audit import AuditReport
from api.routers import evidence
from open_notebook.evidence.auditable_models import (
    AnswerAuditMetadata,
    AnswerCitation,
    AnswerClaim,
    AuditableAnswer,
    AuditableAnswerStatus,
)
from open_notebook.evidence.models import ClaimKind, SupportStatus
from open_notebook.exceptions import InvalidInputError


def _answered_response() -> AuditableAnswer:
    return AuditableAnswer(
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
                source_id="source:one",
                document_version_id="document_version:one",
                document_version_hash="hash:one",
                pdf_page=2,
                text="A autorização compete à entidade competente.",
            )
        ],
        overall_confidence=0.91,
        status=AuditableAnswerStatus.ANSWERED,
        audit=AnswerAuditMetadata(
            question_hash="sha256:question",
            selected_evidence_ids=["EV_ONE"],
            retrieval_scores={"EV_ONE": 0.91},
            embedding_model="test-embedding-model",
        ),
    )


@pytest.mark.asyncio
async def test_answer_endpoint_returns_structured_auditable_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Any] = []

    async def fake_build(request: Any) -> AuditableAnswer:
        calls.append(request)
        return _answered_response()

    monkeypatch.setattr(evidence, "build_auditable_answer", fake_build)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/evidence/answer",
            json={
                "question": "Quem decide a autorização?",
                "max_evidence": 6,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["claims"][0]["evidence_ids"] == ["EV_ONE"]
    assert body["citations"][0]["evidence_id"] == "EV_ONE"
    assert len(calls) == 1
    assert calls[0].question == "Quem decide a autorização?"
    assert calls[0].max_evidence == 6


@pytest.mark.asyncio
async def test_answer_endpoint_maps_invalid_input_to_bad_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_build(request: Any) -> AuditableAnswer:
        raise InvalidInputError("Evidence search query cannot be empty")

    monkeypatch.setattr(evidence, "build_auditable_answer", fake_build)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/evidence/answer",
            json={"question": "Pergunta válida"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Evidence search query cannot be empty"


@pytest.mark.asyncio
async def test_answer_endpoint_rejects_invalid_request_shape() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/evidence/answer",
            json={
                "question": "Pergunta válida",
                "max_evidence": 8,
                "candidate_limit": 2,
            },
        )

    assert response.status_code == 422
    assert "candidate_limit" in response.text


def _insufficient_audit_report() -> AuditReport:
    return AuditReport(
        audit_id="AUDIT_API_001",
        answer_id="ANSWER_API_001",
        question="Pergunta sem evidência",
        question_hash="sha256:question",
        answer="Não foi encontrada evidência suficiente.",
        overall_confidence=0,
        status=AuditableAnswerStatus.INSUFFICIENT_EVIDENCE,
        pipeline_version="phase-7",
    )


@pytest.mark.asyncio
async def test_audit_endpoint_returns_persisted_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(answer_id: str) -> AuditReport:
        assert answer_id == "ANSWER_API_001"
        return _insufficient_audit_report()

    monkeypatch.setattr(evidence, "get_audit_report", fake_get)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/evidence/answer/ANSWER_API_001/audit"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["audit_id"] == "AUDIT_API_001"
    assert body["answer_id"] == "ANSWER_API_001"
    assert body["status"] == "insufficient_evidence"
