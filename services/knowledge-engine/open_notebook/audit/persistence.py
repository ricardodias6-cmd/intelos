"""Persistence for explainable answer audit reports."""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from open_notebook.audit.freshness import evaluate_audit_freshness
from open_notebook.audit.models import (
    AuditFreshness,
    AuditReport,
    AuditReportPersistenceResult,
)
from open_notebook.database.repository import (
    ensure_record_id,
    repo_query,
    repo_relate,
    repo_upsert,
)
from open_notebook.exceptions import InvalidInputError, NotFoundError


def _stable_edge_id(audit_id: str, evidence_id: str, decision: str) -> str:
    digest = sha256(
        f"{audit_id}|{evidence_id}|{decision}".encode("utf-8")
    ).hexdigest().upper()
    return f"EDGE_AUDIT_{digest[:48]}"


async def persist_audit_report(
    report: AuditReport,
) -> AuditReportPersistenceResult:
    """Upsert a report and its deterministic links to Evidence Blocks."""

    evidence_ids = report.audited_evidence_ids
    known_rows: dict[str, str] = {}
    if evidence_ids:
        rows = await repo_query(
            "SELECT id, evidence_id FROM evidence_block WHERE evidence_id IN $evidence_ids",
            {"evidence_ids": evidence_ids},
        )
        known_rows = {
            str(row["evidence_id"]): str(row["id"])
            for row in rows
            if row.get("evidence_id") is not None and row.get("id") is not None
        }

    missing = sorted(set(evidence_ids) - set(known_rows))
    if missing:
        raise InvalidInputError(
            "Audit report references unknown Evidence IDs: "
            + ", ".join(missing)
        )

    record_id = f"audit_report:{report.audit_id}"
    data: dict[str, Any] = report.model_dump(mode="python")
    data["rejected_evidence_ids"] = report.rejected_evidence_ids
    data["created"] = report.generated_at
    data["updated"] = report.generated_at
    await repo_upsert("audit_report", record_id, data)

    await repo_query(
        "DELETE audit_evidence WHERE in = $report;",
        {"report": ensure_record_id(record_id)},
    )

    for decision in report.evidence_decisions:
        await repo_relate(
            record_id,
            "audit_evidence",
            known_rows[decision.evidence_id],
            decision.model_dump(mode="python"),
            relation_id=_stable_edge_id(
                report.audit_id,
                decision.evidence_id,
                decision.decision.value,
            ),
        )

    return AuditReportPersistenceResult(
        audit_id=report.audit_id,
        answer_id=report.answer_id,
        evidence_links_upserted=len(report.evidence_decisions),
        evidence_ids=evidence_ids,
    )


async def get_audit_report(answer_id: str) -> AuditReport:
    """Load the persisted audit report associated with one answer."""

    rows = await repo_query(
        "SELECT * FROM audit_report WHERE answer_id = $answer_id LIMIT 1",
        {"answer_id": answer_id},
    )
    if not rows:
        raise NotFoundError(
            f"No audit report found for answer {answer_id}"
        )
    report = AuditReport.model_validate(rows[0])
    freshness = await evaluate_audit_freshness(report.selected_evidence_ids)
    return report.model_copy(update={"freshness": freshness})


async def get_audit_freshness(answer_id: str) -> AuditFreshness:
    """Return the current freshness assessment for one answer."""

    return (await get_audit_report(answer_id)).freshness
