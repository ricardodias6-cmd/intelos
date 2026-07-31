"""Controlled, auditable revalidation of answer reports."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from open_notebook.audit.models import AuditReport
from open_notebook.audit.persistence import (
    get_audit_report_by_id,
)
from open_notebook.database.repository import (
    ensure_record_id,
    repo_query,
    repo_upsert,
)
from open_notebook.exceptions import InvalidInputError
from open_notebook.operational import (
    AuditOperationalEvent,
    record_operational_event,
)


class AuditRevalidationStatus(StrEnum):
    """Lifecycle of one explicitly requested revalidation."""

    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditRevalidationRequest(BaseModel):
    """Explicit request to re-run one persisted audit report."""

    source_audit_id: str = Field(min_length=3, max_length=128)
    idempotency_key: str = Field(
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,127}$",
    )
    reason: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    change_ids: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def normalize_and_validate(self) -> "AuditRevalidationRequest":
        self.reason = self.reason.strip()
        if not self.reason:
            raise ValueError("revalidation reason cannot be blank")

        self.evidence_ids = list(dict.fromkeys(item.strip() for item in self.evidence_ids))
        self.change_ids = list(dict.fromkeys(item.strip() for item in self.change_ids))
        if any(not item for item in [*self.evidence_ids, *self.change_ids]):
            raise ValueError("revalidation identifiers cannot be blank")
        return self


class AuditRevalidationRecord(BaseModel):
    """Durable idempotency record for one revalidation request."""

    idempotency_key: str
    request_fingerprint: str
    source_audit_id: str
    source_answer_id: str
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)
    change_ids: list[str] = Field(default_factory=list)
    status: AuditRevalidationStatus
    result_audit_id: str | None = None
    result_answer_id: str | None = None
    requested_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "AuditRevalidationRecord":
        if self.status == AuditRevalidationStatus.COMPLETED:
            if not self.result_audit_id or not self.result_answer_id:
                raise ValueError(
                    "completed revalidation requires result identifiers"
                )
            if self.completed_at is None:
                raise ValueError("completed revalidation requires completed_at")
        elif self.status == AuditRevalidationStatus.PROCESSING:
            if self.result_audit_id or self.result_answer_id or self.completed_at:
                raise ValueError(
                    "processing revalidation cannot have a completed result"
                )
        return self


class AuditRevalidationResult(BaseModel):
    """Stable response returned after a controlled revalidation."""

    status: AuditRevalidationStatus
    replayed: bool = False
    idempotency_key: str
    source_audit_id: str
    source_answer_id: str
    result_audit_id: str
    result_answer_id: str
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)
    change_ids: list[str] = Field(default_factory=list)
    completed_at: datetime


def _request_fingerprint(
    answer_id: str,
    request: AuditRevalidationRequest,
) -> str:
    payload = {
        "answer_id": answer_id,
        "source_audit_id": request.source_audit_id,
        "reason": request.reason,
        "evidence_ids": request.evidence_ids,
        "change_ids": request.change_ids,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _record_id(idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest().upper()
    return f"audit_revalidation:{digest}"


async def get_audit_revalidation(
    idempotency_key: str,
) -> AuditRevalidationRecord | None:
    """Load one durable idempotency record, if present."""

    rows = await repo_query(
        "SELECT * FROM audit_revalidation "
        "WHERE idempotency_key = $idempotency_key LIMIT 1",
        {"idempotency_key": idempotency_key},
    )
    return AuditRevalidationRecord.model_validate(rows[0]) if rows else None


def _record_data(record: AuditRevalidationRecord) -> dict[str, Any]:
    data: dict[str, Any] = record.model_dump(mode="python")
    data["created"] = record.requested_at
    data["updated"] = record.completed_at or record.requested_at
    return data


async def persist_audit_revalidation(
    record: AuditRevalidationRecord,
) -> None:
    """Upsert one revalidation lifecycle record by deterministic key."""

    await repo_upsert(
        "audit_revalidation",
        _record_id(record.idempotency_key),
        _record_data(record),
    )


async def claim_audit_revalidation(
    record: AuditRevalidationRecord,
) -> None:
    """Create the lifecycle record, failing when the key is already claimed.

    CREATE (rather than UPSERT) makes the idempotency key a real lock: two
    concurrent requests carrying the same key cannot both start the pipeline,
    because the second CREATE hits the existing record and raises.
    """

    try:
        await repo_query(
            "CREATE $record CONTENT $data;",
            {
                "record": ensure_record_id(_record_id(record.idempotency_key)),
                "data": _record_data(record),
            },
        )
    except Exception as exc:
        raise InvalidInputError(
            "revalidation is already registered for this idempotency key"
        ) from exc


def _result_from_record(
    record: AuditRevalidationRecord,
    *,
    replayed: bool,
) -> AuditRevalidationResult:
    if record.status != AuditRevalidationStatus.COMPLETED:
        raise InvalidInputError(
            "revalidation is not completed and cannot be returned"
        )
    return AuditRevalidationResult(
        status=record.status,
        replayed=replayed,
        idempotency_key=record.idempotency_key,
        source_audit_id=record.source_audit_id,
        source_answer_id=record.source_answer_id,
        result_audit_id=record.result_audit_id,
        result_answer_id=record.result_answer_id,
        reason=record.reason,
        evidence_ids=record.evidence_ids,
        change_ids=record.change_ids,
        completed_at=record.completed_at,
    )


def _request_from_report(report: AuditReport):
    """Reconstruct only safe, persisted generation parameters."""

    from open_notebook.evidence.auditable_answer import AuditableAnswerRequest

    metadata = report.metadata

    def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
        value = metadata.get(name)
        return value if isinstance(value, int) and minimum <= value <= maximum else default

    def _bounded_float(name: str, default: float) -> float:
        value = metadata.get(name)
        return value if isinstance(value, (int, float)) and 0 <= float(value) <= 1 else default

    max_evidence = _bounded_int(
        "max_evidence",
        min(max(len(report.audited_evidence_ids), 1), 20),
        1,
        20,
    )
    candidate_limit = max(
        max_evidence,
        _bounded_int("candidate_limit", 250, 1, 2000),
    )
    minimum_score = _bounded_float("minimum_score", 0.05)
    source_id = metadata.get("source_id")
    source_ids = metadata.get("source_ids")
    version_hash = metadata.get("version_hash")
    conversation_context = metadata.get("conversation_context", [])
    if not isinstance(source_id, str):
        source_id = None
    if source_ids is not None and (
        not isinstance(source_ids, list)
        or not all(isinstance(item, str) for item in source_ids)
    ):
        source_ids = None
    if not isinstance(version_hash, str):
        version_hash = None
    if not isinstance(conversation_context, list) or not all(
        isinstance(item, str) for item in conversation_context
    ):
        conversation_context = []

    return AuditableAnswerRequest(
        question=report.question,
        conversation_id=report.conversation_id,
        turn_id=report.turn_id,
        response_mode=report.response_mode,
        max_evidence=max_evidence,
        candidate_limit=candidate_limit,
        minimum_score=minimum_score,
        source_id=source_id,
        source_ids=source_ids,
        version_hash=version_hash,
        conversation_context=conversation_context,
        regeneration_attempts=1,
    )


async def revalidate_audit_report(
    answer_id: str,
    request: AuditRevalidationRequest,
) -> AuditRevalidationResult:
    """Re-run one report without mutating its original audit record."""

    report = await get_audit_report_by_id(request.source_audit_id)
    if report.answer_id != answer_id:
        raise InvalidInputError(
            "source audit report does not belong to the requested answer"
        )

    audited_ids = set(report.audited_evidence_ids)
    if not set(request.evidence_ids).issubset(audited_ids):
        raise InvalidInputError(
            "revalidation Evidence IDs must belong to the source audit report"
        )

    fingerprint = _request_fingerprint(answer_id, request)
    existing = await get_audit_revalidation(request.idempotency_key)
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise InvalidInputError(
                "idempotency key was already used with different parameters"
            )
        if existing.status == AuditRevalidationStatus.COMPLETED:
            record_operational_event(
                AuditOperationalEvent.AUDIT_REVALIDATION_REPLAYED
            )
            return _result_from_record(existing, replayed=True)
        raise InvalidInputError(
            f"revalidation is already {existing.status.value}"
        )

    processing = AuditRevalidationRecord(
        idempotency_key=request.idempotency_key,
        request_fingerprint=fingerprint,
        source_audit_id=report.audit_id,
        source_answer_id=report.answer_id,
        reason=request.reason,
        evidence_ids=request.evidence_ids,
        change_ids=request.change_ids,
        status=AuditRevalidationStatus.PROCESSING,
    )
    await claim_audit_revalidation(processing)
    record_operational_event(
        AuditOperationalEvent.AUDIT_REVALIDATION_STARTED
    )

    try:
        from open_notebook.evidence.auditable_answer import build_auditable_answer

        answer_request = _request_from_report(report)
        metadata_model_id = report.metadata.get("model_id")
        model_id = metadata_model_id if isinstance(metadata_model_id, str) else None
        answer = await build_auditable_answer(
            answer_request,
            model_id=model_id,
        )
        if (
            not answer.answer_id
            or not answer.audit_report_id
            or answer.answer_id == report.answer_id
            or answer.audit_report_id == report.audit_id
        ):
            raise InvalidInputError(
                "revalidation must produce a new answer and audit report"
            )

        completed_at = datetime.now(timezone.utc)
        completed = processing.model_copy(
            update={
                "status": AuditRevalidationStatus.COMPLETED,
                "result_audit_id": answer.audit_report_id,
                "result_answer_id": answer.answer_id,
                "completed_at": completed_at,
            }
        )
        await persist_audit_revalidation(completed)
        record_operational_event(
            AuditOperationalEvent.AUDIT_REVALIDATION_COMPLETED
        )
        return _result_from_record(completed, replayed=False)
    except Exception:
        record_operational_event(
            AuditOperationalEvent.AUDIT_REVALIDATION_FAILED,
            status="failed",
        )
        failed = processing.model_copy(
            update={"status": AuditRevalidationStatus.FAILED}
        )
        await persist_audit_revalidation(failed)
        raise
