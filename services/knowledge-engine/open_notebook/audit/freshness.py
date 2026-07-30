"""Live freshness evaluation for evidence-backed audit reports."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from open_notebook.audit.models import (
    AuditFreshness,
    AuditFreshnessStatus,
)
from open_notebook.database.repository import ensure_record_id, repo_query


def _row_id(row: dict[str, object], field: str) -> str | None:
    value = row.get(field)
    return str(value) if value is not None else None


async def evaluate_audit_freshness(
    selected_evidence_ids: Iterable[str],
) -> AuditFreshness:
    """Classify whether the evidence used by an answer still supports reuse.

    The evaluator is deliberately fail-safe: a revoked version is outdated,
    a superseded or modified version is possibly outdated, and a missing
    evidence/version record requires revalidation.
    """

    evidence_ids = sorted(set(selected_evidence_ids))
    checked_at = datetime.now(timezone.utc)
    if not evidence_ids:
        return AuditFreshness(checked_at=checked_at)

    evidence_rows = await repo_query(
        (
            "SELECT evidence_id, document_version, document_version_hash "
            "FROM evidence_block WHERE evidence_id IN $evidence_ids"
        ),
        {"evidence_ids": evidence_ids},
    )
    evidence_by_id = {
        str(row["evidence_id"]): row
        for row in evidence_rows
        if row.get("evidence_id") is not None
    }
    missing_evidence = sorted(set(evidence_ids) - set(evidence_by_id))
    version_ids = sorted(
        {
            str(row["document_version"])
            for row in evidence_by_id.values()
            if row.get("document_version") is not None
        }
    )
    version_hashes = sorted(
        {
            str(row["document_version_hash"])
            for row in evidence_by_id.values()
            if row.get("document_version_hash") is not None
        }
    )

    version_rows = await repo_query(
        "SELECT id, status, version_hash FROM document_version WHERE id IN $version_ids",
        {
            "version_ids": [
                ensure_record_id(version_id) for version_id in version_ids
            ]
        },
    )
    versions_by_id = {
        str(row["id"]): row
        for row in version_rows
        if row.get("id") is not None
    }
    missing_versions = sorted(
        {
            str(row["document_version"])
            for row in evidence_by_id.values()
            if row.get("document_version") is not None
            and str(row["document_version"]) not in versions_by_id
        }
    )
    missing_version_evidence = sorted(
        {
            evidence_id
            for evidence_id, row in evidence_by_id.items()
            if row.get("document_version") is None
        }
    )
    missing_hash_evidence = sorted(
        {
            evidence_id
            for evidence_id, row in evidence_by_id.items()
            if not row.get("document_version_hash")
        }
    )

    change_rows = await repo_query(
        (
            "SELECT id, change_id, change_type, previous_version, "
            "current_version, previous_version_hash, current_version_hash "
            "FROM document_change WHERE "
            "current_version_hash IN $version_hashes OR "
            "previous_version_hash IN $version_hashes OR "
            "current_version IN $version_ids OR "
            "previous_version IN $version_ids"
        ),
        {
            "version_hashes": version_hashes,
            "version_ids": [
                ensure_record_id(version_id) for version_id in version_ids
            ],
        },
    )

    affected_evidence_ids: set[str] = set(missing_evidence)
    affected_evidence_ids.update(missing_version_evidence)
    affected_evidence_ids.update(missing_hash_evidence)
    affected_evidence_ids.update(
        evidence_id
        for evidence_id, row in evidence_by_id.items()
        if row.get("document_version") is not None
        and str(row["document_version"]) in missing_versions
    )
    change_ids: set[str] = set()
    has_outdated = False
    has_possible_outdated = False
    has_unknown = bool(
        missing_evidence
        or missing_versions
        or missing_version_evidence
        or missing_hash_evidence
    )

    for evidence_id, evidence_row in evidence_by_id.items():
        version_id = _row_id(evidence_row, "document_version")
        version = versions_by_id.get(version_id or "")
        status = str(version.get("status")) if version else "unknown"
        if version is None:
            has_unknown = True
            affected_evidence_ids.add(evidence_id)
        elif status == "revoked":
            has_outdated = True
            affected_evidence_ids.add(evidence_id)
        elif status == "superseded":
            has_possible_outdated = True
            affected_evidence_ids.add(evidence_id)
        elif status == "current":
            evidence_hash = str(evidence_row.get("document_version_hash") or "")
            version_hash = str(version.get("version_hash") or "")
            if not evidence_hash or not version_hash or evidence_hash != version_hash:
                has_unknown = True
                affected_evidence_ids.add(evidence_id)
        else:
            has_unknown = True
            affected_evidence_ids.add(evidence_id)

    for change in change_rows:
        change_type = str(change.get("change_type", ""))
        if change_type not in {"modified", "revoked"}:
            continue

        previous_version_id = _row_id(change, "previous_version")
        current_version_id = _row_id(change, "current_version")
        previous_version_hash = _row_id(change, "previous_version_hash")
        current_version_hash = _row_id(change, "current_version_hash")
        matched_evidence_ids: set[str] = set()
        for evidence_id, evidence_row in evidence_by_id.items():
            evidence_version_id = _row_id(evidence_row, "document_version")
            evidence_hash = _row_id(evidence_row, "document_version_hash")
            if evidence_version_id and (previous_version_id or current_version_id):
                if change_type == "revoked":
                    matches = evidence_version_id in {
                        previous_version_id,
                        current_version_id,
                    }
                else:
                    matches = evidence_version_id == previous_version_id
            elif change_type == "revoked":
                matches = evidence_hash in {
                    previous_version_hash,
                    current_version_hash,
                }
            else:
                matches = evidence_hash == previous_version_hash

            if matches:
                matched_evidence_ids.add(evidence_id)

        if not matched_evidence_ids:
            continue

        change_id = _row_id(change, "change_id") or _row_id(change, "id")
        if change_id:
            change_ids.add(change_id)
        affected_evidence_ids.update(matched_evidence_ids)
        if change_type == "revoked":
            has_outdated = True
        else:
            has_possible_outdated = True

    if has_outdated:
        return AuditFreshness(
            status=AuditFreshnessStatus.OUTDATED,
            requires_revalidation=True,
            reason="A referenced document version was revoked.",
            change_ids=sorted(change_ids),
            affected_evidence_ids=sorted(affected_evidence_ids),
            checked_at=checked_at,
        )
    if has_unknown:
        return AuditFreshness(
            status=AuditFreshnessStatus.UNKNOWN,
            requires_revalidation=True,
            reason="A referenced evidence or document version has an unknown state.",
            change_ids=sorted(change_ids),
            affected_evidence_ids=sorted(affected_evidence_ids),
            checked_at=checked_at,
        )
    if has_possible_outdated:
        return AuditFreshness(
            status=AuditFreshnessStatus.POSSIBLY_OUTDATED,
            requires_revalidation=True,
            reason="A referenced document version was modified or superseded.",
            change_ids=sorted(change_ids),
            affected_evidence_ids=sorted(affected_evidence_ids),
            checked_at=checked_at,
        )
    return AuditFreshness(checked_at=checked_at)
