"""Persistence service for structured Evidence Core ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger

from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.evidence import DocumentVersionRecord, EvidenceBlockRecord
from open_notebook.evidence.docling_adapter import StructuredDocumentExtraction
from open_notebook.evidence.models import ExtractionMethod
from open_notebook.exceptions import InvalidInputError

_EXTRACTION_PROFILE_KEYS = (
    "processor",
    "docling_output_format",
    "ocr_enabled",
    "formula_enrichment_enabled",
    "vision_enrichment_enabled",
    "evidence_blocks",
)


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


def _validate_existing_extraction(
    *,
    version: DocumentVersionRecord,
    extraction: StructuredDocumentExtraction,
    existing_ids: set[str],
) -> set[str]:
    """Ensure reprocessing cannot mutate an immutable document version.

    A repeated import may resume a partial write, but it must use the same
    extraction profile and produce the same complete set of evidence IDs.
    """
    if version.extraction_method != ExtractionMethod.DOCLING:
        raise RuntimeError(
            "Existing document version was created by a different extraction method"
        )

    if version.page_count != extraction.page_count:
        raise RuntimeError(
            "Extraction page count does not match the immutable document version"
        )

    stored_metadata = version.metadata or {}
    for key in _EXTRACTION_PROFILE_KEYS:
        if stored_metadata.get(key) != extraction.metadata.get(key):
            raise RuntimeError(
                f"Extraction profile drift detected for immutable field: {key}"
            )

    incoming_ids = [block.evidence_id for block in extraction.blocks]
    incoming_set = set(incoming_ids)
    if len(incoming_set) != len(incoming_ids):
        raise RuntimeError("Extraction produced duplicate evidence identifiers")

    unexpected_existing = existing_ids - incoming_set
    if unexpected_existing:
        raise RuntimeError(
            "Stored evidence does not belong to the current immutable extraction"
        )

    return incoming_set


async def _index_new_blocks(document_version_id: str, created_blocks: int) -> None:
    """Index newly persisted blocks when an embedding model is configured.

    Evidence persistence remains available without an embedding provider. The
    dedicated indexing API can backfill those blocks later.
    """

    if created_blocks == 0:
        return

    from open_notebook.evidence.retrieval import index_evidence_blocks

    try:
        await index_evidence_blocks(document_version_id=document_version_id)
    except InvalidInputError as exc:
        logger.info("Evidence embeddings deferred: {}", exc)
    except Exception:
        logger.exception(
            "Evidence blocks were persisted but automatic embedding indexing failed"
        )
        raise


async def persist_structured_extraction(
    *, source_id: str, extraction: StructuredDocumentExtraction
) -> EvidenceIngestionResult:
    """Persist one extraction idempotently.

    Reprocessing the same source bytes reuses the existing document version and
    creates only evidence blocks that are not already present. A partial import
    can resume, but profile or output drift is rejected to keep each document
    version immutable and internally coherent.
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
            extraction_method=ExtractionMethod.DOCLING,
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
    _validate_existing_extraction(
        version=version,
        extraction=extraction,
        existing_ids=existing_ids,
    )

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
            bbox=block.bbox.model_dump(mode="json") if block.bbox else None,
            block_type=block.block_type,
            extraction_method=block.extraction_method,
            verification_status=block.verification_status,
        )
        await record.save()
        created_blocks += 1

    await _index_new_blocks(version.id, created_blocks)

    return EvidenceIngestionResult(
        document_version_id=version.id,
        created_version=created_version,
        created_blocks=created_blocks,
        existing_blocks=len(existing_ids),
    )
