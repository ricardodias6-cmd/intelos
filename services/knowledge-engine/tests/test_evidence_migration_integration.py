"""Integration test for the Evidence Core SurrealDB migrations.

This test requires a disposable SurrealDB instance configured through the
standard SURREAL_* environment variables. The dedicated GitHub Actions job
provides that instance and explicitly enables this module.
"""

import hashlib
import os

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

pytestmark = pytest.mark.skipif(
    os.getenv("INTELOS_RUN_SURREAL_INTEGRATION") != "1",
    reason=(
        "requires the dedicated disposable SurrealDB integration environment; "
        "set INTELOS_RUN_SURREAL_INTEGRATION=1 only when that service is available"
    ),
)

LATEST_MIGRATION = 31
EVIDENCE_TABLES = {
    "document_version",
    "evidence_block",
    "claim",
    "claim_evidence",
}
GRAPH_TABLES = {
    "knowledge_entity",
    "knowledge_relation",
    "entity_evidence",
}
AUDIT_TABLES = {
    "audit_report",
    "audit_evidence",
}
AUDIT_FRESHNESS_FIELDS = {
    "conversation_id",
    "turn_id",
    "response_mode",
    "freshness",
}
VERSIONING_TABLES = {
    "document_change",
}
REPROCESSING_TABLES = {
    "document_reprocessing_request",
}
COPILOT_TABLES = {
    "copilot_conversation_turn",
}
EVIDENCE_ANALYZER = "intelos_evidence_analyzer"
RETRIEVAL_FIELDS = {
    "embedding_model",
    "embedded_text_hash",
}
RETRIEVAL_INDEXES = {
    "idx_evidence_source_version",
    "idx_evidence_version_page",
    "idx_evidence_block_type",
    "idx_evidence_section_path",
}


async def _database_schema() -> str:
    """Return a stable textual representation of the database schema."""
    return repr(await repo_query("INFO FOR DB;"))


async def _evidence_table_schema() -> str:
    """Return evidence_block fields and indexes from the correct schema scope."""
    return repr(await repo_query("INFO FOR TABLE evidence_block;"))


def _assert_evidence_schema_present(schema: str) -> None:
    for table in EVIDENCE_TABLES:
        assert table in schema
    assert EVIDENCE_ANALYZER in schema


def _assert_evidence_schema_absent(schema: str) -> None:
    for table in EVIDENCE_TABLES:
        assert table not in schema
    assert EVIDENCE_ANALYZER not in schema


def _assert_graph_schema_present(schema: str) -> None:
    for table in GRAPH_TABLES:
        assert table in schema


def _assert_graph_schema_absent(schema: str) -> None:
    for table in GRAPH_TABLES:
        assert table not in schema


def _assert_audit_schema_present(schema: str) -> None:
    for table in AUDIT_TABLES:
        assert table in schema


def _assert_audit_schema_absent(schema: str) -> None:
    for table in AUDIT_TABLES:
        assert table not in schema


def _assert_audit_freshness_schema_present(schema: str) -> None:
    for field in AUDIT_FRESHNESS_FIELDS:
        assert field in schema


def _assert_audit_freshness_schema_absent(schema: str) -> None:
    for field in AUDIT_FRESHNESS_FIELDS:
        assert field not in schema


def _assert_versioning_schema_present(schema: str) -> None:
    for table in VERSIONING_TABLES:
        assert table in schema


def _assert_versioning_schema_absent(schema: str) -> None:
    for table in VERSIONING_TABLES:
        assert table not in schema


def _assert_reprocessing_schema_present(schema: str) -> None:
    for table in REPROCESSING_TABLES:
        assert table in schema


def _assert_reprocessing_schema_absent(schema: str) -> None:
    for table in REPROCESSING_TABLES:
        assert table not in schema


def _assert_copilot_schema_present(schema: str) -> None:
    for table in COPILOT_TABLES:
        assert table in schema


def _assert_copilot_schema_absent(schema: str) -> None:
    for table in COPILOT_TABLES:
        assert table not in schema


def _assert_retrieval_schema_present(table_schema: str) -> None:
    for marker in RETRIEVAL_FIELDS | RETRIEVAL_INDEXES:
        assert marker in table_schema


def _assert_retrieval_schema_absent(table_schema: str) -> None:
    for marker in RETRIEVAL_FIELDS | RETRIEVAL_INDEXES:
        assert marker not in table_schema


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
async def test_evidence_migrations_up_down_and_reapply_against_real_surrealdb() -> None:
    manager = AsyncMigrationManager()

    assert len(manager.up_migrations) == LATEST_MIGRATION
    assert len(manager.down_migrations) == LATEST_MIGRATION

    await manager.run_migration_up()
    assert await manager.get_current_version() == LATEST_MIGRATION
    assert not await manager.needs_migration()
    _assert_evidence_schema_present(await _database_schema())
    _assert_retrieval_schema_present(await _evidence_table_schema())
    _assert_graph_schema_present(await _database_schema())
    _assert_audit_schema_present(await _database_schema())
    _assert_audit_freshness_schema_present(await _database_schema())
    _assert_versioning_schema_present(await _database_schema())
    _assert_reprocessing_schema_present(await _database_schema())
    _assert_copilot_schema_present(await _database_schema())

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
    assert await manager.get_current_version() == 30
    _assert_audit_schema_present(await _database_schema())
    _assert_audit_freshness_schema_absent(await _database_schema())

    await manager.runner.run_one_down()
    assert await manager.get_current_version() == 29
    _assert_copilot_schema_absent(await _database_schema())
    _assert_reprocessing_schema_present(await _database_schema())

    await manager.runner.run_one_down()
    assert await manager.get_current_version() == 28
    _assert_versioning_schema_present(await _database_schema())
    _assert_reprocessing_schema_absent(await _database_schema())
    _assert_copilot_schema_absent(await _database_schema())

    await manager.runner.run_one_down()
    assert await manager.get_current_version() == 27
    _assert_audit_schema_present(await _database_schema())
    _assert_versioning_schema_absent(await _database_schema())
    _assert_reprocessing_schema_absent(await _database_schema())
    _assert_copilot_schema_absent(await _database_schema())

    await manager.runner.run_one_down()
    assert await manager.get_current_version() == 26
    assert await manager.needs_migration()
    _assert_evidence_schema_present(await _database_schema())
    _assert_retrieval_schema_present(await _evidence_table_schema())
    _assert_graph_schema_present(await _database_schema())
    _assert_audit_schema_absent(await _database_schema())

    await manager.runner.run_one_down()
    assert await manager.get_current_version() == 25
    _assert_evidence_schema_present(await _database_schema())
    _assert_retrieval_schema_present(await _evidence_table_schema())
    _assert_graph_schema_absent(await _database_schema())
    _assert_audit_schema_absent(await _database_schema())

    await manager.runner.run_one_down()
    assert await manager.get_current_version() == 24
    _assert_evidence_schema_present(await _database_schema())
    _assert_retrieval_schema_absent(await _evidence_table_schema())
    _assert_graph_schema_absent(await _database_schema())

    await manager.runner.run_one_down()
    assert await manager.get_current_version() == 23
    _assert_evidence_schema_absent(await _database_schema())

    await manager.runner.run_one_up()
    assert await manager.get_current_version() == 24
    _assert_evidence_schema_present(await _database_schema())

    await manager.runner.run_one_up()
    assert await manager.get_current_version() == 25
    _assert_retrieval_schema_present(await _evidence_table_schema())

    await manager.runner.run_one_up()
    assert await manager.get_current_version() == 26
    _assert_graph_schema_present(await _database_schema())
    _assert_audit_schema_absent(await _database_schema())
    _assert_versioning_schema_absent(await _database_schema())

    await manager.runner.run_one_up()
    assert await manager.get_current_version() == 27
    _assert_audit_schema_present(await _database_schema())
    _assert_versioning_schema_absent(await _database_schema())
    _assert_reprocessing_schema_absent(await _database_schema())

    await manager.runner.run_one_up()
    assert await manager.get_current_version() == 28
    _assert_audit_schema_present(await _database_schema())
    _assert_versioning_schema_present(await _database_schema())
    _assert_reprocessing_schema_absent(await _database_schema())

    await manager.runner.run_one_up()
    assert await manager.get_current_version() == 29
    _assert_reprocessing_schema_present(await _database_schema())
    _assert_copilot_schema_absent(await _database_schema())

    await manager.runner.run_one_up()
    assert await manager.get_current_version() == 30
    _assert_audit_schema_present(await _database_schema())
    _assert_audit_freshness_schema_absent(await _database_schema())

    await manager.runner.run_one_up()
    assert await manager.get_current_version() == LATEST_MIGRATION
    assert not await manager.needs_migration()
    _assert_evidence_schema_present(await _database_schema())
    _assert_retrieval_schema_present(await _evidence_table_schema())
    _assert_graph_schema_present(await _database_schema())
    _assert_audit_schema_present(await _database_schema())
    _assert_audit_freshness_schema_present(await _database_schema())
    _assert_versioning_schema_present(await _database_schema())
    _assert_reprocessing_schema_present(await _database_schema())
    _assert_copilot_schema_present(await _database_schema())
