from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from api.main import app
from api.routers import evidence
from open_notebook.audit import (
    AuditFreshness,
    AuditFreshnessStatus,
    AuditReport,
    AuditReportPage,
    AuditReportQuery,
    list_audit_reports,
)
from open_notebook.evidence.auditable_models import AuditableAnswerStatus


def _report(answer_id: str, generated_at: datetime) -> AuditReport:
    return AuditReport(
        audit_id=f"AUDIT_{answer_id}",
        answer_id=answer_id,
        conversation_id="CONV_QUERY_001",
        turn_id=f"TURN_{answer_id}",
        question="Pergunta?",
        question_hash="sha256:question",
        answer="Não foi encontrada evidência suficiente.",
        overall_confidence=0,
        status=AuditableAnswerStatus.INSUFFICIENT_EVIDENCE,
        pipeline_version="phase-10",
        generated_at=generated_at,
    )


def test_query_rejects_inverted_date_range() -> None:
    with pytest.raises(ValidationError, match="generated_from"):
        AuditReportQuery(
            generated_from=datetime(2026, 7, 30, tzinfo=timezone.utc),
            generated_to=datetime(2026, 7, 29, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio
async def test_list_audit_reports_is_bounded_and_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _report(
        "ANSWER_QUERY_002",
        datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc),
    )
    second = _report(
        "ANSWER_QUERY_001",
        datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc),
    )
    rows = [first.model_dump(mode="python"), second.model_dump(mode="python")]

    queries: list[tuple[str, dict[str, Any] | None]] = []

    async def fake_query(
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        queries.append((query, variables))
        return rows

    async def fake_freshness(
        evidence_ids: list[str],
    ) -> AuditFreshness:
        return AuditFreshness(status=AuditFreshnessStatus.CURRENT)

    monkeypatch.setattr("open_notebook.audit.persistence.repo_query", fake_query)
    monkeypatch.setattr(
        "open_notebook.audit.persistence.evaluate_audit_freshness",
        fake_freshness,
    )

    page = await list_audit_reports(
        AuditReportQuery(
            conversation_id="CONV_QUERY_001",
            limit=1,
        )
    )

    assert isinstance(page, AuditReportPage)
    assert [item.answer_id for item in page.items] == ["ANSWER_QUERY_002"]
    assert page.has_more is True
    assert page.next_offset == 1
    assert page.scan_truncated is False
    assert "ORDER BY generated_at DESC, audit_id DESC" in queries[0][0]
    assert "LIMIT $scan_limit" in queries[0][0]
    assert queries[0][1]["conversation_id"] == "CONV_QUERY_001"


@pytest.mark.asyncio
async def test_list_audit_reports_filters_live_freshness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _report(
        "ANSWER_QUERY_003",
        datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc),
    )
    async def fake_query(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [report.model_dump(mode="python")]

    async def fake_freshness(
        evidence_ids: list[str],
    ) -> AuditFreshness:
        return AuditFreshness(
            status=AuditFreshnessStatus.UNKNOWN,
            requires_revalidation=True,
            reason="missing",
        )

    monkeypatch.setattr("open_notebook.audit.persistence.repo_query", fake_query)
    monkeypatch.setattr(
        "open_notebook.audit.persistence.evaluate_audit_freshness",
        fake_freshness,
    )

    page = await list_audit_reports(
        AuditReportQuery(
            freshness_status=AuditFreshnessStatus.UNKNOWN,
            limit=10,
        )
    )

    assert [item.answer_id for item in page.items] == ["ANSWER_QUERY_003"]
    assert page.items[0].freshness.status == AuditFreshnessStatus.UNKNOWN
    assert page.items[0].freshness.requires_revalidation is True


@pytest.mark.asyncio
async def test_audit_query_endpoint_returns_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_list(query: AuditReportQuery) -> AuditReportPage:
        assert query.conversation_id == "CONV_QUERY_001"
        assert query.limit == 5
        return AuditReportPage(
            items=[],
            limit=query.limit,
            offset=query.offset,
            has_more=False,
        )

    monkeypatch.setattr(evidence, "list_audit_reports", fake_list)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/evidence/audit-reports",
            params={
                "conversation_id": "CONV_QUERY_001",
                "limit": 5,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["limit"] == 5
    assert body["has_more"] is False

@pytest.mark.asyncio
async def test_truncated_scan_still_exposes_a_usable_next_offset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A truncated scan must not leave the client without a way to page on."""

    rows = [
        _report(
            f"ANSWER_QUERY_{index:04d}",
            datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc),
        ).model_dump(mode="python")
        for index in range(1000)
    ]
    refreshed: list[str] = []

    async def fake_query(
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return rows

    async def fake_freshness(evidence_ids: list[str]) -> AuditFreshness:
        refreshed.append("call")
        return AuditFreshness(status=AuditFreshnessStatus.CURRENT)

    monkeypatch.setattr("open_notebook.audit.persistence.repo_query", fake_query)
    monkeypatch.setattr(
        "open_notebook.audit.persistence.evaluate_audit_freshness",
        fake_freshness,
    )

    page = await list_audit_reports(
        AuditReportQuery(conversation_id="CONV_QUERY_001", limit=20)
    )

    assert page.scan_truncated is True
    assert page.has_more is True
    assert page.next_offset == 20
    assert len(page.items) == 20
    # Freshness is evaluated for the returned page only, not the whole scan.
    assert len(refreshed) == 20
