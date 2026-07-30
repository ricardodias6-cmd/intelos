from __future__ import annotations

from typing import Any

import httpx
import pytest

from api.main import app
from api.routers import copilot
from open_notebook.evidence.auditable_models import (
    AnswerAuditMetadata,
    AnswerCitation,
    AnswerClaim,
    AuditableAnswer,
    AuditableAnswerStatus,
)
from open_notebook.evidence.models import ClaimKind, SupportStatus


@pytest.fixture(autouse=True)
def stub_conversation_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_load(*args: Any, **kwargs: Any) -> list[Any]:
        return []

    async def fake_persist(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(copilot, "load_recent_conversation_context", fake_load)
    monkeypatch.setattr(copilot, "persist_conversation_turn", fake_persist)


def _answered_response() -> AuditableAnswer:
    return AuditableAnswer(
        answer_id="ANSWER_COPILOT_001",
        audit_report_id="AUDIT_COPILOT_001",
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
            pipeline_version="phase-9",
        ),
    )


def _insufficient_response() -> AuditableAnswer:
    return AuditableAnswer(
        answer_id="ANSWER_COPILOT_002",
        audit_report_id="AUDIT_COPILOT_002",
        answer="Não foi encontrada evidência suficiente.",
        claims=[],
        citations=[],
        overall_confidence=0,
        requires_human_review=True,
        status=AuditableAnswerStatus.INSUFFICIENT_EVIDENCE,
        audit=AnswerAuditMetadata(
            question_hash="sha256:question",
            selected_evidence_ids=[],
            retrieval_scores={},
            pipeline_version="phase-9",
        ),
    )


@pytest.mark.asyncio
async def test_copilot_endpoint_returns_auditable_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Any] = []

    async def fake_build(request: Any) -> AuditableAnswer:
        calls.append(request)
        return _answered_response()

    monkeypatch.setattr(copilot, "build_auditable_answer", fake_build)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/copilot/chat",
            json={
                "question": "  Quem decide a autorização?  ",
                "response_mode": "audit",
                "max_evidence": 6,
                "include_knowledge_graph": True,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["response_mode"] == "audit"
    assert body["answer_id"] == "ANSWER_COPILOT_001"
    assert body["audit_report_id"] == "AUDIT_COPILOT_001"
    assert body["conversation_id"].startswith("CONV_")
    assert body["turn_id"].startswith("TURN_")
    assert body["audit"]["pipeline_version"] == "phase-9"
    assert body["claims"][0]["evidence_ids"] == ["EV_ONE"]
    assert body["citations"][0]["evidence_id"] == "EV_ONE"
    assert len(calls) == 1
    assert calls[0].question == "Quem decide a autorização?"
    assert calls[0].max_evidence == 6
    assert calls[0].source_id is None
    assert calls[0].version_hash is None
    assert calls[0].conversation_id == body["conversation_id"]
    assert calls[0].turn_id == body["turn_id"]
    assert calls[0].response_mode == "audit"


@pytest.mark.asyncio
async def test_copilot_reuses_supplied_conversation_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_build(request: Any) -> AuditableAnswer:
        return _answered_response()

    monkeypatch.setattr(copilot, "build_auditable_answer", fake_build)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/copilot/chat",
            json={
                "conversation_id": "CONV_EXISTING",
                "question": "Quem decide?",
            },
        )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == "CONV_EXISTING"


@pytest.mark.asyncio
async def test_copilot_maps_invalid_input_to_bad_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_build(request: Any) -> AuditableAnswer:
        from open_notebook.exceptions import InvalidInputError

        raise InvalidInputError("Evidence search query cannot be empty")

    monkeypatch.setattr(copilot, "build_auditable_answer", fake_build)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/copilot/chat",
            json={"question": "Pergunta válida"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Evidence search query cannot be empty"


@pytest.mark.asyncio
async def test_copilot_rejects_blank_question() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/copilot/chat",
            json={"question": "   "},
        )

    assert response.status_code == 422
    assert "question" in response.text


@pytest.mark.asyncio
async def test_insufficient_evidence_is_exposed_without_factual_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_build(request: Any) -> AuditableAnswer:
        return _insufficient_response()

    monkeypatch.setattr(copilot, "build_auditable_answer", fake_build)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/copilot/chat",
            json={"question": "Pergunta sem evidência"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient_evidence"
    assert body["overall_confidence"] == 0
    assert body["claims"] == []
    assert body["citations"] == []
    assert body["requires_human_review"] is True
