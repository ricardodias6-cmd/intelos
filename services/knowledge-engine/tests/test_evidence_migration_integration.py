"""Integration test for the Evidence Core SurrealDB migration.

This test requires a disposable SurrealDB instance configured through the
standard SURREAL_* environment variables. The dedicated GitHub Actions job
provides that instance.
"""

import hashlib

import pytest

from open_notebook.database.async_migrate import AsyncMigrationManager
from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.evidence import ClaimRecord
from open_notebook.evidence.docling_adapter import StructuredDocumentExtraction
from open_notebook.evidence.ingestion import persist_structured_extraction
from open_notebook.evidence.models import (
    BoundingBox,
    ClaimKind,
    CoordinateOrigin,
    EvidenceBlock,
    ExtractionMethod,
    SupportStatus,
    VerificationStatus,
)

EVIDENCE_TABLES = {
    "document_version",
    "evidence_block",
    "claim",
    "claim_evidence",
}
EVIDENCE_ANALYZER = "intelos_evidence_analyzer"


async def _database_schema() -> str:
    """Return a stable textual representation of the database schema."""
    return repr(await repo_query("INFO FOR DB;"))


def _assert_evidence_schema_present(schema: str) -> None:
    for table in EVIDENCE_TABLES:
        assert table in schema
    assert EVIDENCE_ANALYZER in schema


def _assert_evidence_schema_absent(schema: str) -> None:
    for table in EVIDENCE_TABLES:
        assert table not in schema
    assert EVIDENCE_ANALYZER not in schema


def _structured_extraction(*, ocr_enabled: bool = False) -> StructuredDocumentExtraction:
    raw_text = "A migração preserva uma passagem verificável."
    version_hash = "a" * 64
    block = EvidenceBlock(
        evidence_id="EV-INTEGRATION-001",
        source_id="source:evidence_test",
        document_version_hash=version_hash,
        raw_text=raw_text,
        pdf_page=1,
        section_path=["Teste de integração"],
        bbox=BoundingBox(
            x0=10,
            y0=20,
            x1=300,
            y1=80,
            coordinate_origin=CoordinateOrigin.BOTTOM_LEFT,
        ),
        block_type="text",
        extraction_method=ExtractionMethod.DOCLING,
        verification_status=VerificationStatus.UNVERIFIED,
        text_hash=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
    )
    return StructuredDocumentExtraction(
        content=raw_text,
        title="Documento de teste",
        identified_type="application/pdf",
        version_hash=version_hash,
        page_count=1,
        blocks=[block],
        metadata={
            "processor": "intelos_docling",
            "docling_output_format": "markdown",
            "evidence_blocks": 1,
            "ocr_enabled": ocr_enabled,
            "formula_enrichment_enabled": False,
            "vision_enrichment_enabled": False,
        },
    )


@pytest.mark.asyncio
async def test_migration_24_up_down_and_reapply_against_real_surrealdb() -> None:
    manager = AsyncMigrationManager()

    assert len(manager.up_migrations) == 24
    assert len(manager.down_migrations) == 24

    await manager.run_migration_up()
    assert await manager.get_current_version() == 24
    assert not await manager.needs_migration()
    _assert_evidence_schema_present(await _database_schema())

    await repo_query(
        "CREATE source:evidence_test SET title = 'Evidence migration integration';"
    )
    extraction = _structured_extraction()

    first = await persist_structured_extraction(
        source_id="source:evidence_test",
        extraction=extraction,
    )
    second = await persist_structured_extraction(
        source_id="source:evidence_test",
        extraction=extraction,
    )

    assert first.created_version is True
    assert first.created_blocks == 1
    assert first.existing_blocks == 0
    assert second.created_version is False
    assert second.created_blocks == 0
    assert second.existing_blocks == 1

    versions = await repo_query("SELECT * FROM document_version;")
    blocks = await repo_query("SELECT * FROM evidence_block;")
    assert len(versions) == 1
    assert len(blocks) == 1
    assert blocks[0]["bbox"]["coordinate_origin"] == "BOTTOMLEFT"

    with pytest.raises(RuntimeError, match="ocr_enabled"):
        await persist_structured_extraction(
            source_id="source:evidence_test",
            extraction=_structured_extraction(ocr_enabled=True),
        )

    claim = ClaimRecord(
        claim_id="CLM-INTEGRATION-001",
        text="A migração preserva uma passagem verificável.",
        claim_kind=ClaimKind.FACT,
        support_status=SupportStatus.DIRECT,
        render_as_definitive=True,
    )
    await claim.save()
    assert claim.id is not None

    await claim.link_evidence(
        blocks[0]["id"],
        relation_type=SupportStatus.DIRECT,
    )
    assert len(await repo_query("SELECT * FROM claim_evidence;")) == 1

    await repo_query(
        "DELETE $evidence;",
        {"evidence": ensure_record_id(blocks[0]["id"])},
    )
    assert await repo_query("SELECT * FROM evidence_block;") == []
    assert await repo_query("SELECT * FROM claim_evidence;") == []

    resumed = await persist_structured_extraction(
        source_id="source:evidence_test",
        extraction=extraction,
    )
    assert resumed.created_version is False
    assert resumed.created_blocks == 1
    assert resumed.existing_blocks == 0

    recreated_blocks = await repo_query("SELECT * FROM evidence_block;")
    assert len(recreated_blocks) == 1
    await claim.link_evidence(
        recreated_blocks[0]["id"],
        relation_type=SupportStatus.DIRECT,
    )
    assert len(await repo_query("SELECT * FROM claim_evidence;")) == 1

    await repo_query(
        "DELETE $claim;",
        {"claim": ensure_record_id(claim.id)},
    )
    assert await repo_query("SELECT * FROM claim_evidence;") == []

    await repo_query(
        "DELETE $version;",
        {"version": ensure_record_id(first.document_version_id)},
    )
    assert await repo_query("SELECT * FROM document_version;") == []
    assert await repo_query("SELECT * FROM evidence_block;") == []

    await manager.runner.run_one_down()
    assert await manager.get_current_version() == 23
    assert await manager.needs_migration()
    _assert_evidence_schema_absent(await _database_schema())

    await manager.runner.run_one_up()
    assert await manager.get_current_version() == 24
    assert not await manager.needs_migration()
    _assert_evidence_schema_present(await _database_schema())
