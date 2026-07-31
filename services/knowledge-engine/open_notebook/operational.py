"""Safe, process-local operational counters for the audit surface."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from loguru import logger
from pydantic import BaseModel, Field


class AuditOperationalEvent(StrEnum):
    """Bounded event names allowed in operational telemetry."""

    AUDIT_REPORT_PERSISTED = "audit_report_persisted"
    AUDIT_REVALIDATION_STARTED = "audit_revalidation_started"
    AUDIT_REVALIDATION_COMPLETED = "audit_revalidation_completed"
    AUDIT_REVALIDATION_REPLAYED = "audit_revalidation_replayed"
    AUDIT_REVALIDATION_FAILED = "audit_revalidation_failed"
    READINESS_CHECK_SUCCEEDED = "readiness_check_succeeded"
    READINESS_CHECK_FAILED = "readiness_check_failed"


class AuditOperationalSnapshot(BaseModel):
    """Safe operational counters; no user or document content is included."""

    captured_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    audit_reports_persisted: int = Field(ge=0)
    audit_revalidations_started: int = Field(ge=0)
    audit_revalidations_completed: int = Field(ge=0)
    audit_revalidations_replayed: int = Field(ge=0)
    audit_revalidations_failed: int = Field(ge=0)
    readiness_checks_succeeded: int = Field(ge=0)
    readiness_checks_failed: int = Field(ge=0)


_EVENT_FIELDS = {
    AuditOperationalEvent.AUDIT_REPORT_PERSISTED: "audit_reports_persisted",
    AuditOperationalEvent.AUDIT_REVALIDATION_STARTED: (
        "audit_revalidations_started"
    ),
    AuditOperationalEvent.AUDIT_REVALIDATION_COMPLETED: (
        "audit_revalidations_completed"
    ),
    AuditOperationalEvent.AUDIT_REVALIDATION_REPLAYED: (
        "audit_revalidations_replayed"
    ),
    AuditOperationalEvent.AUDIT_REVALIDATION_FAILED: (
        "audit_revalidations_failed"
    ),
    AuditOperationalEvent.READINESS_CHECK_SUCCEEDED: (
        "readiness_checks_succeeded"
    ),
    AuditOperationalEvent.READINESS_CHECK_FAILED: "readiness_checks_failed",
}


class _OperationalCounters:
    def __init__(self) -> None:
        self._values = {field: 0 for field in _EVENT_FIELDS.values()}

    def record(self, event: AuditOperationalEvent) -> None:
        self._values[_EVENT_FIELDS[event]] += 1

    def snapshot(self) -> AuditOperationalSnapshot:
        return AuditOperationalSnapshot(**self._values)


_counters = _OperationalCounters()


def record_operational_event(
    event: AuditOperationalEvent,
    *,
    status: str = "success",
    duration_ms: int | None = None,
) -> None:
    """Record bounded telemetry without logging content or exception details."""

    _counters.record(event)
    logger.bind(
        operational_event=event.value,
        status=status,
        duration_ms=duration_ms,
    ).info("audit operational event")


def get_operational_snapshot() -> AuditOperationalSnapshot:
    """Return a safe snapshot of process-local operational counters."""

    return _counters.snapshot()
