from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from open_notebook.audit import (
    AuditConflict,
    AuditEvidenceDecision,
    AuditEvidenceDecisionType,
    AuditReport,
    AuditTraceEvent,
    persist_audit_report,
)
from open_notebook.evidence.auditable_models import (
    AnswerCitation,
    AnswerClaim,
    AuditableAnswerStatus,
)
from open_notebook.evidence.models import ClaimKind, SupportStatus
from open_notebook.exceptions import InvalidInputError


def _report() -> AuditReport:
    return AuditReport(
        audit_id="AUDIT_PHASE7_001",
        answer_id="ANSWER_PHASE7_001",
        question="Quem decide?",
        question_hash="sha256:question",
        answer="A autorização compete à entidade competente.",
        claims=[
            AnswerClaim(
                claim_id="CLM_PHASE7_001",
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
        selected_evidence_ids=["EV_ONE"],
        evidence_decisions=[
            AuditEvidenceDecision(
                evidence_id="EV_ONE",
                decision=AuditEvidenceDecisionType.SELECTED,
                retrieval_score=0.91,
                rank=1,
            ),
            AuditEvidenceDecision(
                evidence_id="EV_REJECTED",
                decision=AuditEvidenceDecisionType.REJECTED,
                reason="A validação semântica encontrou conflito material.",
                retrieval_score=0.42,
                rank=4,
            ),
        ],
        conflicts=[
            AuditConflict(
                conflict_id="CONFLICT_PHASE7_001",
                claim_id="CLM_PHASE7_001",
                evidence_ids=["EV_ONE", "EV_REJECTED"],
                description="As fontes apresentam conclusões incompatíveis.",
            )
        ],
        trace=[
            AuditTraceEvent(
                stage="retrieval",
                duration_ms=12,
                details={"candidate_count": 4},
            ),
            AuditTraceEvent(
                stage="generation",
                duration_ms=38,
                details={"model": "test-model"},
            ),
        ],
        pipeline_version="phase-7",
        embedding_model="test-embedding-model",
    )


def test_audit_report_preserves_explainability_contract() -> None:
    report = _report()

    assert report.rejected_evidence_ids == ["EV_REJECTED"]
    assert report.audited_evidence_ids == ["EV_ONE", "EV_REJECTED"]
    assert report.conflicts[0].claim_id == "CLM_PHASE7_001"
    assert report.trace[1].details["model"] == "test-model"


def test_audit_report_rejects_unexplained_evidence() -> None:
    with pytest.raises(ValidationError, match="requires a reason"):
        AuditEvidenceDecision(
            evidence_id="EV_REJECTED",
            decision=AuditEvidenceDecisionType.REJECTED,
        )


def test_audit_report_rejects_inconsistent_selected_set() -> None:
    with pytest.raises(
        ValidationError,
        match="match selected evidence decisions",
    ):
        report = _report().model_copy(
            update={"selected_evidence_ids": ["EV_REJECTED"]}
        )
        AuditReport.model_validate(report.model_dump())


@pytest.mark.asyncio
async def test_persist_audit_report_is_evidence_bounded_and_idempotent_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upserts: list[tuple[str, str, dict[str, Any]]] = []
    relations: list[dict[str, Any]] = []
    queries: list[str] = []

    async def fake_query(
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        queries.append(query)
        if query.startswith("SELECT id, evidence_id"):
            return [
                {"id": "evidence_block:one", "evidence_id": "EV_ONE"},
                {"id": "evidence_block:rejected", "evidence_id": "EV_REJECTED"},
            ]
        return []

    async def fake_upsert(
        table: str,
        record_id: str,
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        upserts.append((table, record_id, data))
        return []

    async def fake_relate(
        source: str,
        relationship: str,
        target: str,
        data: dict[str, Any],
        relation_id: str,
    ) -> list[dict[str, Any]]:
        relations.append(
            {
                "source": source,
                "relationship": relationship,
                "target": target,
                "data": data,
                "relation_id": relation_id,
            }
        )
        return []

    monkeypatch.setattr(
        "open_notebook.audit.persistence.repo_query",
        fake_query,
    )
    monkeypatch.setattr(
        "open_notebook.audit.persistence.repo_upsert",
        fake_upsert,
    )
    monkeypatch.setattr(
        "open_notebook.audit.persistence.repo_relate",
        fake_relate,
    )

    first = await persist_audit_report(_report())
    second = await persist_audit_report(_report())

    assert first == second
    assert len(upserts) == 2
    assert all(item[0] == "audit_report" for item in upserts)
    assert len(relations) == 4
    assert relations[0]["relation_id"] == relations[2]["relation_id"]
    assert relations[1]["relation_id"] == relations[3]["relation_id"]
    assert "DELETE audit_evidence" in queries[-1]


@pytest.mark.asyncio
async def test_persist_audit_report_rejects_unknown_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_query(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [{"id": "evidence_block:one", "evidence_id": "EV_ONE"}]

    monkeypatch.setattr(
        "open_notebook.audit.persistence.repo_query",
        fake_query,
    )

    with pytest.raises(InvalidInputError, match="unknown Evidence IDs"):
        await persist_audit_report(_report())
