from __future__ import annotations

from typing import Any

import pytest

from open_notebook.audit.freshness import evaluate_audit_freshness
from open_notebook.audit.models import AuditFreshnessStatus


def _rows_for(
    *,
    evidence: list[dict[str, Any]],
    versions: list[dict[str, Any]],
    changes: list[dict[str, Any]],
):
    async def fake_query(
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if "FROM evidence_block" in query:
            return evidence
        if "FROM document_version" in query:
            return versions
        if "FROM document_change" in query:
            return changes
        raise AssertionError(f"unexpected query: {query}")

    return fake_query


@pytest.mark.asyncio
async def test_freshness_is_current_without_maintenance_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "open_notebook.audit.freshness.repo_query",
        _rows_for(
            evidence=[
                {
                    "evidence_id": "EV_ONE",
                    "document_version": "document_version:one",
                    "document_version_hash": "hash-one",
                }
            ],
            versions=[
                {
                    "id": "document_version:one",
                    "status": "current",
                    "version_hash": "hash-one",
                }
            ],
            changes=[],
        ),
    )

    result = await evaluate_audit_freshness(["EV_ONE"])

    assert result.status == AuditFreshnessStatus.CURRENT
    assert result.requires_revalidation is False
    assert result.affected_evidence_ids == []


@pytest.mark.asyncio
async def test_modified_version_is_possibly_outdated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "open_notebook.audit.freshness.repo_query",
        _rows_for(
            evidence=[
                {
                    "evidence_id": "EV_ONE",
                    "document_version": "document_version:one",
                    "document_version_hash": "hash-one",
                }
            ],
            versions=[
                {
                    "id": "document_version:one",
                    "status": "superseded",
                    "version_hash": "hash-one",
                }
            ],
            changes=[
                {
                    "id": "document_change:one",
                    "change_id": "CHANGE_ONE",
                    "change_type": "modified",
                    "previous_version": "document_version:one",
                    "current_version": "document_version:two",
                    "previous_version_hash": "hash-one",
                    "current_version_hash": "hash-two",
                }
            ],
        ),
    )

    result = await evaluate_audit_freshness(["EV_ONE"])

    assert result.status == AuditFreshnessStatus.POSSIBLY_OUTDATED
    assert result.requires_revalidation is True
    assert result.change_ids == ["CHANGE_ONE"]
    assert result.affected_evidence_ids == ["EV_ONE"]


@pytest.mark.asyncio
async def test_current_version_with_own_change_remains_current(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "open_notebook.audit.freshness.repo_query",
        _rows_for(
            evidence=[
                {
                    "evidence_id": "EV_CURRENT",
                    "document_version": "document_version:two",
                    "document_version_hash": "hash-two",
                }
            ],
            versions=[
                {
                    "id": "document_version:two",
                    "status": "current",
                    "version_hash": "hash-two",
                }
            ],
            changes=[
                {
                    "id": "document_change:one",
                    "change_id": "CHANGE_ONE",
                    "change_type": "modified",
                    "previous_version": "document_version:one",
                    "current_version": "document_version:two",
                    "previous_version_hash": "hash-one",
                    "current_version_hash": "hash-two",
                }
            ],
        ),
    )

    result = await evaluate_audit_freshness(["EV_CURRENT"])

    assert result.status == AuditFreshnessStatus.CURRENT
    assert result.requires_revalidation is False
    assert result.change_ids == []
    assert result.affected_evidence_ids == []


@pytest.mark.asyncio
async def test_unknown_version_status_requires_revalidation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "open_notebook.audit.freshness.repo_query",
        _rows_for(
            evidence=[
                {
                    "evidence_id": "EV_UNKNOWN",
                    "document_version": "document_version:one",
                    "document_version_hash": "hash-one",
                }
            ],
            versions=[
                {
                    "id": "document_version:one",
                    "status": None,
                    "version_hash": "hash-one",
                }
            ],
            changes=[],
        ),
    )

    result = await evaluate_audit_freshness(["EV_UNKNOWN"])

    assert result.status == AuditFreshnessStatus.UNKNOWN
    assert result.requires_revalidation is True
    assert result.affected_evidence_ids == ["EV_UNKNOWN"]


@pytest.mark.asyncio
async def test_revoked_version_is_outdated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "open_notebook.audit.freshness.repo_query",
        _rows_for(
            evidence=[
                {
                    "evidence_id": "EV_ONE",
                    "document_version": "document_version:one",
                    "document_version_hash": "hash-one",
                }
            ],
            versions=[
                {
                    "id": "document_version:one",
                    "status": "revoked",
                    "version_hash": "hash-one",
                }
            ],
            changes=[
                {
                    "id": "document_change:revoke",
                    "change_id": "CHANGE_REVOKE",
                    "change_type": "revoked",
                    "previous_version": "document_version:one",
                    "current_version": "document_version:one",
                    "previous_version_hash": "hash-one",
                    "current_version_hash": "hash-one",
                }
            ],
        ),
    )

    result = await evaluate_audit_freshness(["EV_ONE"])

    assert result.status == AuditFreshnessStatus.OUTDATED
    assert result.requires_revalidation is True
    assert result.change_ids == ["CHANGE_REVOKE"]


@pytest.mark.asyncio
async def test_missing_evidence_requires_revalidation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "open_notebook.audit.freshness.repo_query",
        _rows_for(evidence=[], versions=[], changes=[]),
    )

    result = await evaluate_audit_freshness(["EV_MISSING"])

    assert result.status == AuditFreshnessStatus.UNKNOWN
    assert result.requires_revalidation is True
    assert result.affected_evidence_ids == ["EV_MISSING"]
