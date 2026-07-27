"""Persistence service for structured Evidence Core ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.evidence import DocumentVersionRecord, EvidenceBlockRecord
from open_notebook.evidence.docling_adapter import StructuredDocumentExtraction
from open_notebook.exceptions import InvalidInputError


@dataclass(frozen=True, slots=True)
class EvidenceIngestionResult:
    document_version_id: str
    created_version: bool
    created_blocks: int
    existing_blocks: int


async def _find_document_version(
    *, source_id: str, version_hash: str
) -> DocumentVersionRecord | None:
    rows = await repo_query(
        "SELECT * FROM document_version WHERE source = $source AND version_hash = $hash LIMIT 1",
        {
            "source": ensure_record_id(source_id),
            "hash": version_hash,
        },
    )
    return DocumentVersionRecord(**rows[0]) if rows else None


async def persist_structured_extraction(
    *, source_id: str, extraction: StructuredDocumentExtraction
) -> EvidenceIngestionResult:
    """Persist one extraction idempotently.

    Reprocessing the same source bytes reuses the existing document version and
    creates only evidence blocks that are not already present. The version and
    each block are identified independently, allowing a failed partial import
    to resume without mutating evidence already stored.
    """

    if not source_id:
        raise InvalidInputError("Source ID is required for evidence ingestion")

    version = await _find_document_version(
        source_id=source_id,
        version_hash=extraction.version_hash,
    )
    created_version = version is None

    if version is None:
        version = DocumentVersionRecord(
            source=source_id,
            version_hash=extraction.version_hash,
            extraction_method="docling",
            page_count=extraction.page_count,
            metadata=extraction.metadata,
        )
        await version.save()

    if not version.id:
        raise RuntimeError("Document version was saved without a record ID")

    existing_rows: list[dict[str, Any]] = await repo_query(
        "SELECT VALUE evidence_id FROM evidence_block WHERE document_version = $version",
        {"version": ensure_record_id(version.id)},
    )
    existing_ids = {str(value) for value in existing_rows}

    created_blocks = 0
    for block in extraction.blocks:
        if block.evidence_id in existing_ids:
            continue

        record = EvidenceBlockRecord(
            evidence_id=block.evidence_id,
            source=source_id,
            document_version=version.id,
            raw_text=block.raw_text,
            verified_text=block.verified_text,
            text_hash=block.text_hash,
            pdf_page=block.pdf_page,
            printed_page=block.printed_page,
            section_path=block.section_path,
            bbox=block.bbox.model_dump() if block.bbox else None,
            block_type=block.block_type,
            extraction_method=block.extraction_method,
            verification_status=block.verification_status,
        )
        await record.save()
        created_blocks += 1

    return EvidenceIngestionResult(
        document_version_id=version.id,
        created_version=created_version,
        created_blocks=created_blocks,
        existing_blocks=len(existing_ids),
    )
