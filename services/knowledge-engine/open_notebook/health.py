"""Readiness checks that never expose database or document details."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from open_notebook.database.async_migrate import AsyncMigrationManager
from open_notebook.operational import (
    AuditOperationalEvent,
    record_operational_event,
)


class ReadinessResponse(BaseModel):
    """Minimal health response suitable for local probes."""

    status: Literal["ready", "not_ready"]
    checks: dict[str, Literal["reachable", "unreachable"]]


async def check_readiness() -> ReadinessResponse:
    """Check database reachability without exposing connection details."""

    try:
        migration_manager = AsyncMigrationManager()
        await migration_manager.ping()
    except Exception:
        record_operational_event(
            AuditOperationalEvent.READINESS_CHECK_FAILED,
            status="not_ready",
        )
        return ReadinessResponse(
            status="not_ready",
            checks={"database": "unreachable"},
        )

    record_operational_event(AuditOperationalEvent.READINESS_CHECK_SUCCEEDED)
    return ReadinessResponse(
        status="ready",
        checks={"database": "reachable"},
    )
