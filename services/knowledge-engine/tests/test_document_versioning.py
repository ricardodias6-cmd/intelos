from __future__ import annotations

from typing import Any

import pytest

from open_notebook.evidence.models import ExtractionMethod
from open_notebook.evidence.versioning import (
    DocumentChangeType,
    DocumentVersionCandidate,
    DocumentVersionSnapshot,
    detect_document_change,
)


def _candidate(
    *,
    version_hash: str = "a" * 64,
    metadata: dict[str, object] | None = None,
) -> DocumentVersionCandidate:
    return DocumentVersionCandidate(
        source_id="source:versioning",
        version_hash=version_hash,
        extraction_method=ExtractionMethod.DOCLING,
        page_count=2,
        metadata=metadata or {"processor": "intelos_docling"},
    )


def _previous(
    *,
    version_hash: str = "a" * 64,
    metadata: dict[str, object] | None = None,
) -> DocumentVersionSnapshot:
    return DocumentVersionSnapshot(
        version_id="document_version:previous",
        source_id="source:versioning",
        version_hash=version_hash,
        extraction_method=ExtractionMethod.DOCLING,
        page_count=2,
        metadata=metadata or {"processor": "intelos_docling"},
        version_number=1,
    )


def test_new_document_requires_processing() -> None:
    change = detect_document_change(None, _candidate())

    assert change.change_type == DocumentChangeType.NEW
    assert change.content_changed is True
    assert change.requires_reprocessing is True
    assert change.previous_version_hash is None


def test_identical_document_is_unchanged_and_idempotent() -> None:
    first = detect_document_change(_previous(), _candidate())
    second = detect_document_change(_previous(), _candidate())

    assert first.change_type == DocumentChangeType.UNCHANGED
    assert first.content_changed is False
    assert first.metadata_changed is False
    assert first.requires_reprocessing is False
    assert first.change_id == second.change_id


def test_changed_hash_creates_reprocessing_signal() -> None:
    change = detect_document_change(
        _previous(),
        _candidate(version_hash="b" * 64),
    )

    assert change.change_type == DocumentChangeType.MODIFIED
    assert change.content_changed is True
    assert change.requires_reprocessing is True
    assert "version_hash" in change.summary["changed_fields"]


def test_extraction_profile_drift_is_detected_without_content_change() -> None:
    change = detect_document_change(
        _previous(),
        _candidate(metadata={"processor": "intelos_docling", "ocr_enabled": True}),
    )

    assert change.change_type == DocumentChangeType.MODIFIED
    assert change.content_changed is False
    assert change.metadata_changed is True
    assert change.requires_reprocessing is True


def test_revoked_document_change_requires_reprocessing() -> None:
    from open_notebook.evidence.versioning import DocumentChange

    change = DocumentChange(
        change_id="CHANGE_REVOKE_001",
        source_id="source:versioning",
        change_type=DocumentChangeType.REVOKED,
        previous_version_id="document_version:one",
        current_version_id="document_version:one",
        previous_version_hash="a" * 64,
        current_version_hash="a" * 64,
        content_changed=False,
        metadata_changed=False,
        requires_reprocessing=True,
        summary={"reason": "Fonte invalidada."},
    )

    assert change.change_type == DocumentChangeType.REVOKED
    assert change.requires_reprocessing is True


def test_reprocessing_request_is_stable_and_idempotent() -> None:
    from open_notebook.evidence.versioning import (
        ReprocessingReason,
        build_reprocessing_request,
    )

    first = build_reprocessing_request(
        source_id="source:versioning",
        document_version_id="document_version:one",
        reason=ReprocessingReason.DOCUMENT_REVOKED,
    )
    second = build_reprocessing_request(
        source_id="source:versioning",
        document_version_id="document_version:one",
        reason=ReprocessingReason.DOCUMENT_REVOKED,
    )

    assert first.request_id == second.request_id
    assert first.idempotency_key == first.request_id
    assert first.status.value == "pending"


@pytest.mark.asyncio
async def test_revocation_is_idempotent_and_enqueues_reprocessing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"status": "current"}
    writes: list[tuple[str, str]] = []

    async def fake_query(
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if query.startswith("SELECT * FROM $version"):
            return [
                {
                    "id": "document_version:one",
                    "source": "source:versioning",
                    "version_hash": "a" * 64,
                    "status": state["status"],
                }
            ]
        if query.startswith("UPDATE $version"):
            state["status"] = "revoked"
            return []
        raise AssertionError(f"unexpected query: {query}")

    async def fake_upsert(
        table: str,
        record_id: str,
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        writes.append((table, record_id))
        return []

    monkeypatch.setattr(
        "open_notebook.evidence.versioning.repo_query",
        fake_query,
    )
    monkeypatch.setattr(
        "open_notebook.evidence.versioning.repo_upsert",
        fake_upsert,
    )

    first = await revoke_document_version(
        "document_version:one",
        reason="Fonte revogada pela entidade emissora.",
    )
    second = await revoke_document_version(
        "document_version:one",
        reason="Fonte revogada pela entidade emissora.",
    )

    assert first.changed is True
    assert second.changed is False
    assert first.change_id == second.change_id
    assert first.reprocessing_request_id == second.reprocessing_request_id
    assert state["status"] == "revoked"
    assert len(writes) == 4
