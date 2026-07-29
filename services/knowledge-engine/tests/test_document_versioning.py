from __future__ import annotations

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
