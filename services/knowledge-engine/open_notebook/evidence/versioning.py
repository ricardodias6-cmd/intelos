"""Contracts and persistence helpers for autonomous document maintenance."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from open_notebook.database.repository import ensure_record_id, repo_query, repo_upsert
from open_notebook.evidence.models import ExtractionMethod
from open_notebook.exceptions import InvalidInputError, NotFoundError

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_:-]{1,127}$")
_STABLE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{2,127}$")


def _validate_sha256(value: str) -> str:
    normalized = value.lower()
    if not _SHA256_RE.fullmatch(normalized):
        raise ValueError("hash must be a 64-character hexadecimal SHA-256 value")
    return normalized


def _validate_source_id(value: str) -> str:
    if not _SOURCE_ID_RE.fullmatch(value):
        raise ValueError("source_id is not a valid source or record identifier")
    return value


def _validate_stable_id(value: str) -> str:
    if not _STABLE_ID_RE.fullmatch(value):
        raise ValueError(
            "identifier must use upper-case letters, numbers, underscores or hyphens"
        )
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        ensure_ascii=False,
    )


class DocumentVersionStatus(StrEnum):
    """Lifecycle state of one immutable document version."""

    CURRENT = "current"
    SUPERSEDED = "superseded"
    REVOKED = "revoked"


class DocumentChangeType(StrEnum):
    """Deterministic classification of an observed document state."""

    NEW = "new"
    UNCHANGED = "unchanged"
    MODIFIED = "modified"
    REVOKED = "revoked"


class DocumentVersionCandidate(BaseModel):
    """Input contract used to compare an extraction with stored history."""

    source_id: str
    version_hash: str
    extraction_method: ExtractionMethod
    page_count: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        return _validate_source_id(value)

    @field_validator("version_hash")
    @classmethod
    def validate_version_hash(cls, value: str) -> str:
        return _validate_sha256(value)


class DocumentVersionSnapshot(BaseModel):
    """Comparable projection of a persisted document version."""

    version_id: str | None = None
    source_id: str
    version_hash: str
    extraction_method: ExtractionMethod
    page_count: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: DocumentVersionStatus = DocumentVersionStatus.CURRENT
    version_number: int | None = Field(default=None, ge=1)

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        return _validate_source_id(value)

    @field_validator("version_hash")
    @classmethod
    def validate_version_hash(cls, value: str) -> str:
        return _validate_sha256(value)


class DocumentChange(BaseModel):
    """Auditable result of comparing a candidate with the latest version."""

    change_id: str
    source_id: str
    change_type: DocumentChangeType
    previous_version_id: str | None = None
    current_version_id: str | None = None
    previous_version_hash: str | None = None
    current_version_hash: str
    content_changed: bool
    metadata_changed: bool
    requires_reprocessing: bool
    summary: dict[str, Any] = Field(default_factory=dict)
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @field_validator("change_id")
    @classmethod
    def validate_change_id(cls, value: str) -> str:
        return _validate_stable_id(value)

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        return _validate_source_id(value)

    @field_validator("previous_version_hash", "current_version_hash")
    @classmethod
    def validate_hashes(cls, value: str | None) -> str | None:
        return _validate_sha256(value) if value is not None else value

    @model_validator(mode="after")
    def validate_classification(self) -> "DocumentChange":
        expected_reprocessing = self.change_type != DocumentChangeType.UNCHANGED
        if self.requires_reprocessing != expected_reprocessing:
            raise ValueError(
                "requires_reprocessing must match the document change type"
            )
        if self.change_type == DocumentChangeType.NEW:
            if self.previous_version_hash is not None:
                raise ValueError("new documents cannot have a previous version")
            if not self.content_changed:
                raise ValueError("new documents must be marked as content-changed")
        if self.change_type == DocumentChangeType.UNCHANGED:
            if self.previous_version_hash != self.current_version_hash:
                raise ValueError(
                    "unchanged documents must preserve the version hash"
                )
            if self.content_changed:
                raise ValueError("unchanged documents cannot have content changes")
        if self.change_type == DocumentChangeType.REVOKED:
            if self.content_changed or self.metadata_changed:
                raise ValueError("revoked documents cannot change content metadata")
            if self.previous_version_hash != self.current_version_hash:
                raise ValueError("revoked documents must preserve the version hash")
        if self.change_type == DocumentChangeType.MODIFIED:
            if (
                self.previous_version_hash == self.current_version_hash
                and not self.metadata_changed
            ):
                raise ValueError(
                    "modified documents must change the version hash or metadata"
                )
            if not self.content_changed and not self.metadata_changed:
                raise ValueError(
                    "modified documents must identify a changed dimension"
                )
        return self


class ReprocessingStatus(StrEnum):
    """Lifecycle state of one document reprocessing request."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReprocessingReason(StrEnum):
    """Reason that a document version requires maintenance."""

    DOCUMENT_MODIFIED = "document_modified"
    DOCUMENT_REVOKED = "document_revoked"
    MANUAL_REVIEW = "manual_review"


class DocumentReprocessingRequest(BaseModel):
    """Idempotent request to rebuild downstream knowledge artifacts."""

    request_id: str
    source_id: str
    document_version_id: str
    reason: ReprocessingReason
    status: ReprocessingStatus = ReprocessingStatus.PENDING
    idempotency_key: str
    priority: int = Field(default=50, ge=0, le=100)
    attempt_count: int = Field(default=0, ge=0)
    last_error: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    requested_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @field_validator("request_id", "idempotency_key")
    @classmethod
    def validate_stable_fields(cls, value: str) -> str:
        return _validate_stable_id(value)

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        return _validate_source_id(value)

    @field_validator("document_version_id")
    @classmethod
    def validate_document_version_id(cls, value: str) -> str:
        if not value or len(value) > 200:
            raise ValueError("document_version_id must be a non-empty record identifier")
        return value


class DocumentRevocationResult(BaseModel):
    """Result of an idempotent document-version revocation."""

    version_id: str
    source_id: str
    previous_status: DocumentVersionStatus
    status: DocumentVersionStatus
    changed: bool
    change_id: str
    reprocessing_request_id: str


def _maintenance_id(prefix: str, *values: str) -> str:
    value = "|".join(values)
    return f"{prefix}_{sha256(value.encode('utf-8')).hexdigest()[:32].upper()}"


def build_reprocessing_request(
    *,
    source_id: str,
    document_version_id: str,
    reason: ReprocessingReason,
    priority: int = 50,
    metadata: dict[str, Any] | None = None,
) -> DocumentReprocessingRequest:
    """Build a stable request that can be safely enqueued repeatedly."""

    request_id = _maintenance_id(
        "REPROCESS",
        source_id,
        document_version_id,
        reason.value,
    )
    return DocumentReprocessingRequest(
        request_id=request_id,
        source_id=source_id,
        document_version_id=document_version_id,
        reason=reason,
        idempotency_key=request_id,
        priority=priority,
        metadata=metadata or {},
    )


async def enqueue_reprocessing(
    request: DocumentReprocessingRequest,
) -> DocumentReprocessingRequest:
    """Upsert one reprocessing request without creating duplicates."""

    data = request.model_dump(mode="python")
    data["source"] = ensure_record_id(request.source_id)
    data["document_version"] = ensure_record_id(request.document_version_id)
    data.pop("source_id", None)
    data.pop("document_version_id", None)
    data["reason"] = request.reason.value
    data["status"] = request.status.value
    data["created"] = request.requested_at
    data["updated"] = request.requested_at
    await repo_upsert(
        "document_reprocessing_request",
        f"document_reprocessing_request:{request.request_id}",
        data,
    )
    return request


async def revoke_document_version(
    version_id: str,
    *,
    reason: str,
    priority: int = 80,
    metadata: dict[str, Any] | None = None,
) -> DocumentRevocationResult:
    """Revoke a version and enqueue downstream review/reprocessing exactly once."""

    if not reason.strip():
        raise InvalidInputError("Revocation reason cannot be empty")

    rows = await repo_query(
        "SELECT * FROM $version LIMIT 1",
        {"version": ensure_record_id(version_id)},
    )
    if not rows:
        raise NotFoundError(f"Document version {version_id} not found")

    row = rows[0]
    source_id = str(row["source"])
    version_hash = _validate_sha256(str(row["version_hash"]))
    try:
        previous_status = DocumentVersionStatus(
            str(row.get("status") or DocumentVersionStatus.CURRENT.value)
        )
    except ValueError as exc:
        raise InvalidInputError(
            f"Unknown document version status for {version_id}"
        ) from exc

    changed = previous_status != DocumentVersionStatus.REVOKED
    revoked_at = datetime.now(timezone.utc)
    if changed:
        await repo_query(
            "UPDATE $version MERGE $data;",
            {
                "version": ensure_record_id(version_id),
                "data": {
                    "status": DocumentVersionStatus.REVOKED.value,
                    "revoked_at": revoked_at,
                    "revocation_reason": reason.strip(),
                },
            },
        )

    change_id = _maintenance_id(
        "CHANGE_REVOKE",
        version_id,
        version_hash,
        reason.strip(),
    )
    change = DocumentChange(
        change_id=change_id,
        source_id=source_id,
        change_type=DocumentChangeType.REVOKED,
        previous_version_id=version_id,
        current_version_id=version_id,
        previous_version_hash=version_hash,
        current_version_hash=version_hash,
        content_changed=False,
        metadata_changed=False,
        requires_reprocessing=True,
        summary={
            "changed_fields": ["status"],
            "reason": reason.strip(),
            "previous_status": previous_status.value,
        },
        detected_at=revoked_at,
    )
    await persist_document_change(change, current_version_id=version_id)

    request = build_reprocessing_request(
        source_id=source_id,
        document_version_id=version_id,
        reason=ReprocessingReason.DOCUMENT_REVOKED,
        priority=priority,
        metadata=metadata or {"revocation_reason": reason.strip()},
    )
    await enqueue_reprocessing(request)
    return DocumentRevocationResult(
        version_id=version_id,
        source_id=source_id,
        previous_status=previous_status,
        status=DocumentVersionStatus.REVOKED,
        changed=changed,
        change_id=change_id,
        reprocessing_request_id=request.request_id,
    )


def _change_id(
    source_id: str,
    previous_version_hash: str | None,
    current_version_hash: str,
) -> str:
    value = "|".join(
        (source_id, previous_version_hash or "NONE", current_version_hash)
    )
    return f"CHANGE_{sha256(value.encode('utf-8')).hexdigest()[:32].upper()}"


def detect_document_change(
    previous: DocumentVersionSnapshot | None,
    candidate: DocumentVersionCandidate,
) -> DocumentChange:
    """Compare one candidate with the latest stored version deterministically."""

    if previous is not None and previous.source_id != candidate.source_id:
        raise InvalidInputError(
            "Document version comparison requires the same source identifier"
        )

    previous_hash = previous.version_hash if previous else None
    content_changed = previous is None or previous_hash != candidate.version_hash
    metadata_changed = previous is None or (
        _canonical_json(previous.metadata)
        != _canonical_json(candidate.metadata)
        or previous.page_count != candidate.page_count
        or previous.extraction_method != candidate.extraction_method
    )

    if previous is None:
        change_type = DocumentChangeType.NEW
    elif not content_changed and not metadata_changed:
        change_type = DocumentChangeType.UNCHANGED
    else:
        change_type = DocumentChangeType.MODIFIED

    changed_fields: list[str] = []
    if content_changed:
        changed_fields.append("version_hash")
    if metadata_changed:
        changed_fields.append("extraction_profile")

    return DocumentChange(
        change_id=_change_id(
            candidate.source_id,
            previous_hash,
            candidate.version_hash,
        ),
        source_id=candidate.source_id,
        change_type=change_type,
        previous_version_id=previous.version_id if previous else None,
        previous_version_hash=previous_hash,
        current_version_hash=candidate.version_hash,
        content_changed=content_changed,
        metadata_changed=metadata_changed,
        requires_reprocessing=change_type != DocumentChangeType.UNCHANGED,
        summary={
            "changed_fields": changed_fields,
            "previous_version_number": (
                previous.version_number if previous else None
            ),
            "current_extraction_method": candidate.extraction_method.value,
        },
    )


async def persist_document_change(
    change: DocumentChange,
    *,
    current_version_id: str | None = None,
) -> DocumentChange:
    """Persist one deterministic change record after its version is saved."""

    resolved_current_id = current_version_id or change.current_version_id
    if not resolved_current_id:
        raise InvalidInputError(
            "A persisted document change requires a current version record"
        )

    data: dict[str, Any] = {
        "change_id": change.change_id,
        "source": ensure_record_id(change.source_id),
        "previous_version": (
            ensure_record_id(change.previous_version_id)
            if change.previous_version_id
            else None
        ),
        "current_version": ensure_record_id(resolved_current_id),
        "previous_version_hash": change.previous_version_hash,
        "current_version_hash": change.current_version_hash,
        "change_type": change.change_type.value,
        "content_changed": change.content_changed,
        "metadata_changed": change.metadata_changed,
        "requires_reprocessing": change.requires_reprocessing,
        "summary": change.summary,
        "detected_at": change.detected_at,
        "created": change.detected_at,
        "updated": change.detected_at,
    }
    await repo_upsert("document_change", f"document_change:{change.change_id}", data)
    return change.model_copy(update={"current_version_id": resolved_current_id})


async def mark_version_superseded(
    version_id: str,
    *,
    superseded_at: datetime | None = None,
) -> None:
    """Move the previous current version out of the active retrieval set."""

    await repo_query(
        "UPDATE $version MERGE $data;",
        {
            "version": ensure_record_id(version_id),
            "data": {
                "status": DocumentVersionStatus.SUPERSEDED.value,
                "superseded_at": superseded_at or datetime.now(timezone.utc),
            },
        },
    )
