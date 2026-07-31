from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from api.main import app
from api.routers import evidence
from open_notebook.health import ReadinessResponse, check_readiness
from open_notebook.operational import (
    AuditOperationalEvent,
    AuditOperationalSnapshot,
    get_operational_snapshot,
    record_operational_event,
)


def test_operational_snapshot_has_no_content_fields() -> None:
    snapshot = get_operational_snapshot()

    assert isinstance(snapshot, AuditOperationalSnapshot)
    assert "question" not in snapshot.model_fields
    assert "answer" not in snapshot.model_fields
    assert "metadata" not in snapshot.model_fields
    assert snapshot.audit_reports_persisted >= 0


def test_operational_event_increments_only_bounded_counter() -> None:
    before = get_operational_snapshot()
    record_operational_event(AuditOperationalEvent.AUDIT_REPORT_PERSISTED)
    after = get_operational_snapshot()

    assert after.audit_reports_persisted == before.audit_reports_persisted + 1
    assert after.audit_revalidations_started == before.audit_revalidations_started


@pytest.mark.asyncio
async def test_readiness_returns_safe_database_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeMigrationManager:
        async def ping(self) -> None:
            return None

    monkeypatch.setattr(
        "open_notebook.health.AsyncMigrationManager",
        FakeMigrationManager,
    )

    result = await check_readiness()

    assert isinstance(result, ReadinessResponse)
    assert result.status == "ready"
    assert result.checks == {"database": "reachable"}


@pytest.mark.asyncio
async def test_readiness_failure_does_not_expose_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeMigrationManager:
        async def ping(self) -> None:
            raise RuntimeError("secret database password")

    monkeypatch.setattr(
        "open_notebook.health.AsyncMigrationManager",
        FakeMigrationManager,
    )

    result = await check_readiness()

    assert result.status == "not_ready"
    assert result.checks == {"database": "unreachable"}
    assert "secret" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_health_and_operational_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_readiness() -> ReadinessResponse:
        return ReadinessResponse(
            status="ready",
            checks={"database": "reachable"},
        )

    monkeypatch.setattr("api.main.check_readiness", fake_readiness)
    monkeypatch.setattr(
        evidence,
        "get_operational_snapshot",
        lambda: AuditOperationalSnapshot(
            captured_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
            audit_reports_persisted=1,
            audit_revalidations_started=2,
            audit_revalidations_completed=1,
            audit_revalidations_replayed=1,
            audit_revalidations_failed=0,
            readiness_checks_succeeded=3,
            readiness_checks_failed=0,
        ),
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        live = await client.get("/health/live")
        ready = await client.get("/health/ready")
        operational = await client.get("/api/evidence/operational")

    assert live.status_code == 200
    assert live.json() == {"status": "alive"}
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert operational.status_code == 200
    assert operational.json()["audit_revalidations_replayed"] == 1
