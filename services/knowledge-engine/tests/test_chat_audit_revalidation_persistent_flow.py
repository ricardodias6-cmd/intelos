from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from api.routers._chat_shared import extract_chat_messages
from open_notebook.audit import (
    AuditFreshness,
    AuditFreshnessStatus,
    AuditPresentationMode,
    AuditRevalidationRequest,
    get_audit_presentation,
    revalidate_audit_report,
)
from open_notebook.audit import persistence as audit_persistence
from open_notebook.audit import revalidation as audit_revalidation
from open_notebook.evidence import auditable_answer
from open_notebook.evidence.auditable_answer import (
    CandidateAnswer,
    CandidateClaim,
)
from open_notebook.evidence.models import SupportStatus
from open_notebook.evidence.retrieval import (
    EvidenceSearchHit,
    EvidenceSearchResponse,
)
from open_notebook.evidence.semantic_validation import (
    SemanticEvidenceFinding,
    SemanticValidationResult,
)
from open_notebook.graphs import chat


class _FileAuditStore:
    """Small file-backed adapter used to exercise persistence across flow steps."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

    async def persist_report(self, report: Any) -> None:
        data = self._read()
        data[f"report:{report.audit_id}"] = report.model_dump(mode="json")
        self._write(data)

    async def get_report_by_audit_id(self, audit_id: str) -> Any:
        from open_notebook.audit.models import AuditReport

        record = self._read()[f"report:{audit_id}"]
        return AuditReport.model_validate(record)

    async def get_report_by_answer_id(self, answer_id: str) -> Any:
        from open_notebook.audit.models import AuditReport

        for key, record in self._read().items():
            if key.startswith("report:") and record["answer_id"] == answer_id:
                return AuditReport.model_validate(record)
        raise AssertionError(f"report not found for {answer_id}")

    async def get_revalidation(self, idempotency_key: str) -> Any:
        from open_notebook.audit.revalidation import AuditRevalidationRecord

        record = self._read().get(f"revalidation:{idempotency_key}")
        return AuditRevalidationRecord.model_validate(record) if record else None

    async def persist_revalidation(self, record: Any) -> None:
        data = self._read()
        data[f"revalidation:{record.idempotency_key}"] = record.model_dump(
            mode="json"
        )
        self._write(data)

    def reports(self) -> list[Any]:
        from open_notebook.audit.models import AuditReport

        return [
            AuditReport.model_validate(record)
            for key, record in self._read().items()
            if key.startswith("report:")
        ]


class _StructuredModel:
    def __init__(self, candidates: list[CandidateAnswer]) -> None:
        self.candidates = candidates

    async def ainvoke(self, prompt: str) -> CandidateAnswer:
        return self.candidates.pop(0)


class _Provider:
    def __init__(self, candidates: list[CandidateAnswer]) -> None:
        self._candidates = candidates

    def with_structured_output(self, schema: Any) -> _StructuredModel:
        assert schema is CandidateAnswer
        return _StructuredModel(self._candidates)


def _hit() -> EvidenceSearchHit:
    return EvidenceSearchHit(
        evidence_id="EV_PERSISTENT_001",
        source_id="source:one",
        document_title="Documento persistente",
        document_version_id="document_version:one",
        document_version_hash="hash:one",
        text="A entidade competente decide.",
        section_path=["Decisão"],
        block_type="text",
        score=0.95,
    )


def _candidate(answer: str) -> CandidateAnswer:
    return CandidateAnswer(
        answer=answer,
        claims=[
            CandidateClaim(
                text=answer,
                evidence_ids=["EV_PERSISTENT_001"],
            )
        ],
    )


@pytest.mark.asyncio
async def test_chat_audit_revalidation_persists_full_flow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _FileAuditStore(tmp_path / "audit-store.json")
    candidates = [
        _candidate("A entidade competente decide."),
        _candidate("Após revalidação, a entidade competente decide."),
    ]

    async def fake_retrieve(**kwargs: Any) -> EvidenceSearchResponse:
        filters = kwargs["filters"]
        assert filters.source_ids == ["source:one"]
        return EvidenceSearchResponse(
            query=kwargs["query"],
            hits=[_hit()],
            selected_versions={"source:one": "hash:one"},
        )

    async def fake_provision(*args: Any, **kwargs: Any) -> _Provider:
        return _Provider(candidates)

    async def fake_validate(**kwargs: Any) -> SemanticValidationResult:
        return SemanticValidationResult(
            claim=kwargs["claim"],
            recommended_support_status=SupportStatus.DIRECT,
            confidence=0.95,
            requires_human_review=False,
            evidence_findings=[
                SemanticEvidenceFinding(
                    evidence_id="EV_PERSISTENT_001",
                    semantic_score=0.95,
                    lexical_coverage=0.95,
                )
            ],
            embedding_model="test-model",
            direct_threshold=0.82,
            partial_threshold=0.58,
        )

    monkeypatch.setattr(auditable_answer, "persist_audit_report", store.persist_report)
    monkeypatch.setattr(auditable_answer, "retrieve_evidence", fake_retrieve)
    monkeypatch.setattr(auditable_answer, "provision_langchain_model", fake_provision)
    monkeypatch.setattr(auditable_answer, "validate_claim_semantics", fake_validate)
    monkeypatch.setattr(
        audit_revalidation,
        "get_audit_report_by_id",
        store.get_report_by_audit_id,
    )
    monkeypatch.setattr(
        audit_revalidation,
        "get_audit_revalidation",
        store.get_revalidation,
    )
    monkeypatch.setattr(
        audit_revalidation,
        "persist_audit_revalidation",
        store.persist_revalidation,
    )

    async def get_report_for_presentation(answer_id: str) -> Any:
        return await store.get_report_by_answer_id(answer_id)

    monkeypatch.setattr(
        audit_persistence,
        "get_audit_report",
        get_report_for_presentation,
    )

    result = chat.call_model_with_messages(
        {
            "messages": [
                HumanMessage(content="Quem decide?"),
            ],
            "notebook": None,
            "context": {
                "sources": [{"id": "source:one", "title": "Documento"}],
                "notes": [],
            },
            "context_config": None,
            "model_override": None,
            "audit_enabled": True,
            "audit_conversation_id": "chat_session:PERSISTENT_001",
            "audit_turn_id": "TURN_PERSISTENT_001",
            "audit_response_mode": "detailed",
        },
        RunnableConfig(),
    )

    message = result["messages"]
    extracted = extract_chat_messages([message])[0]
    assert extracted.answer_id == message.id
    assert extracted.audit_report_id is not None

    initial_presentation = await get_audit_presentation(
        extracted.answer_id,
        AuditPresentationMode.SUMMARY,
    )
    assert initial_presentation.audit_id == extracted.audit_report_id
    assert initial_presentation.freshness.status == AuditFreshnessStatus.CURRENT

    source_report = await store.get_report_by_answer_id(extracted.answer_id)
    stale_report = source_report.model_copy(
        update={
            "freshness": AuditFreshness(
                status=AuditFreshnessStatus.OUTDATED,
                requires_revalidation=True,
                reason="A versão do documento foi alterada.",
                change_ids=["CHANGE_PERSISTENT_001"],
                affected_evidence_ids=["EV_PERSISTENT_001"],
            )
        }
    )
    await store.persist_report(stale_report)

    stale_presentation = await get_audit_presentation(
        extracted.answer_id,
        AuditPresentationMode.SUMMARY,
    )
    assert stale_presentation.freshness.requires_revalidation is True

    result_revalidation = await revalidate_audit_report(
        extracted.answer_id,
        AuditRevalidationRequest(
            source_audit_id=source_report.audit_id,
            idempotency_key="persistent-flow-key-0001",
            reason="A versão do documento foi alterada.",
            evidence_ids=["EV_PERSISTENT_001"],
            change_ids=["CHANGE_PERSISTENT_001"],
        ),
    )

    assert result_revalidation.result_answer_id != extracted.answer_id
    assert result_revalidation.result_audit_id != source_report.audit_id

    refreshed_presentation = await get_audit_presentation(
        result_revalidation.result_answer_id,
        AuditPresentationMode.SUMMARY,
    )
    assert refreshed_presentation.freshness.status == AuditFreshnessStatus.CURRENT

    persisted_reports = store.reports()
    assert len(persisted_reports) == 2
    assert {
        report.answer_id for report in persisted_reports
    } == {
        extracted.answer_id,
        result_revalidation.result_answer_id,
    }
    assert Path(store.path).exists()
