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
from open_notebook.audit.query import AuditReportPage, AuditReportQuery
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


_MAX_AUDIT_QUERY_SCAN = 1000


async def _refresh_audit_report(row: dict[str, Any]) -> AuditReport:
    """Validate one stored report and replace its freshness with a live result."""

    report = AuditReport.model_validate(row)
    freshness = await evaluate_audit_freshness(report.selected_evidence_ids)
    return report.model_copy(update={"freshness": freshness})


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
    return await _refresh_audit_report(rows[0])


async def list_audit_reports(query: AuditReportQuery) -> AuditReportPage:
    """Return a bounded, deterministic page of live audit reports."""

    clauses: list[str] = []
    variables: dict[str, Any] = {"scan_limit": _MAX_AUDIT_QUERY_SCAN}

    if query.answer_id is not None:
        clauses.append("answer_id = $answer_id")
        variables["answer_id"] = query.answer_id
    if query.conversation_id is not None:
        clauses.append("conversation_id = $conversation_id")
        variables["conversation_id"] = query.conversation_id
    if query.turn_id is not None:
        clauses.append("turn_id = $turn_id")
        variables["turn_id"] = query.turn_id
    if query.generated_from is not None:
        clauses.append("generated_at >= $generated_from")
        variables["generated_from"] = query.generated_from
    if query.generated_to is not None:
        clauses.append("generated_at <= $generated_to")
        variables["generated_to"] = query.generated_to

    statement = "SELECT * FROM audit_report"
    if clauses:
        statement += " WHERE " + " AND ".join(clauses)
    statement += " ORDER BY generated_at DESC, audit_id DESC LIMIT $scan_limit"

    rows = await repo_query(statement, variables)
    reports: list[AuditReport] = []
    for row in rows:
        report = await _refresh_audit_report(row)
        if (
            query.freshness_status is None
            or report.freshness.status == query.freshness_status
        ):
            reports.append(report)

    page_end = query.offset + query.limit
    scan_truncated = len(rows) >= _MAX_AUDIT_QUERY_SCAN
    has_more = len(reports) > page_end or scan_truncated
    next_offset = page_end if has_more and not scan_truncated else None
    return AuditReportPage(
        items=reports[query.offset:page_end],
        limit=query.limit,
        offset=query.offset,
        has_more=has_more,
        next_offset=next_offset,
        scan_truncated=scan_truncated,
    )


async def get_audit_freshness(answer_id: str) -> AuditFreshness:
    """Return the current freshness assessment for one answer."""

    return (await get_audit_report(answer_id)).freshness