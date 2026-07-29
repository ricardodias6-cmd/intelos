"""End-to-end validation of hybrid retrieval over versioned evidence blocks."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

import pytest

from open_notebook.ai.models import model_manager
from open_notebook.database.async_migrate import AsyncMigrationManager
from open_notebook.database.repository import repo_query
from open_notebook.evidence.docling_adapter import StructuredDocumentExtraction
from open_notebook.evidence.ingestion import persist_structured_extraction
from open_notebook.evidence.models import (
    BoundingBox,
    CoordinateOrigin,
    EvidenceBlock,
    ExtractionMethod,
    VerificationStatus,
)
from open_notebook.evidence.retrieval import (
    EvidenceSearchFilters,
    index_evidence_blocks,
    retrieve_evidence,
)

pytestmark = pytest.mark.skipif(
    os.getenv("INTELOS_RUN_EVIDENCE_RETRIEVAL") != "1",
    reason="requires the dedicated Phase 2 SurrealDB integration environment",
)


@dataclass
class _FakeEmbeddingModel:
    model_name: str = "phase2-deterministic-embedding"


def _block(
    *,
    evidence_id: str,
    source_id: str,
    version_hash: str,
    text: str,
    page: int,
    section: str,
    block_type: str,
    bbox: tuple[float, float, float, float],
) -> EvidenceBlock:
    return EvidenceBlock(
        evidence_id=evidence_id,
        source_id=source_id,
        document_version_hash=version_hash,
        raw_text=text,
        pdf_page=page,
        printed_page=str(100 + page),
        section_path=[section],
        bbox=BoundingBox(
            x0=bbox[0],
            y0=bbox[1],
            x1=bbox[2],
            y1=bbox[3],
            coordinate_origin=CoordinateOrigin.TOP_LEFT,
        ),
        block_type=block_type,
        extraction_method=ExtractionMethod.DOCLING,
        verification_status=VerificationStatus.AUTOMATICALLY_VERIFIED,
        text_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _extraction(
    *, version_hash: str, title: str, blocks: list[EvidenceBlock]
) -> StructuredDocumentExtraction:
    return StructuredDocumentExtraction(
        content="\n".join(block.raw_text for block in blocks),
        title=title,
        identified_type="application/pdf",
        version_hash=version_hash,
        page_count=max(block.pdf_page or 1 for block in blocks),
        blocks=blocks,
        metadata={
            "processor": "intelos_docling",
            "docling_output_format": "markdown",
            "evidence_blocks": len(blocks),
            "ocr_enabled": False,
            "formula_enrichment_enabled": False,
            "vision_enrichment_enabled": False,
        },
    )


def _deterministic_vector(text: str) -> list[float]:
    normalized = text.casefold()
    if "24 horas" in normalized or "prazo para decidir" in normalized:
        return [1.0, 0.0, 0.0]
    if "confirma" in normalized and "autorização" in normalized:
        return [0.70, 0.70, 0.0]
    if "setenta e duas horas" in normalized:
        return [0.85, 0.0, 0.15]
    return [0.0, 0.0, 1.0]


@pytest.mark.asyncio
async def test_hybrid_retrieval_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = AsyncMigrationManager()
    await manager.run_migration_up()

    source_a = "source:phase2_regulation"
    source_b = "source:phase2_manual"
    old_hash = "a" * 64
    current_hash = "b" * 64
    manual_hash = "c" * 64

    await repo_query(
        "CREATE source:phase2_regulation SET title = 'Regulamento operacional';"
    )
    await repo_query("CREATE source:phase2_manual SET title = 'Manual de procedimentos';")

    old_block = _block(
        evidence_id="EV-PHASE2-OLD-001",
        source_id=source_a,
        version_hash=old_hash,
        text="A versão revogada fixava o prazo em setenta e duas horas.",
        page=1,
        section="Regime anterior",
        block_type="text",
        bbox=(10, 20, 400, 80),
    )
    current_table = _block(
        evidence_id="EV-PHASE2-CURRENT-001",
        source_id=source_a,
        version_hash=current_hash,
        text="O pedido de autorização deve ser decidido no prazo de 24 horas.",
        page=2,
        section="Prazos de autorização",
        block_type="table",
        bbox=(40, 120, 520, 260),
    )
    current_note = _block(
        evidence_id="EV-PHASE2-CURRENT-002",
        source_id=source_a,
        version_hash=current_hash,
        text="A decisão é registada na versão documental em vigor.",
        page=3,
        section="Registo da decisão",
        block_type="text",
        bbox=(55, 300, 510, 360),
    )
    manual_block = _block(
        evidence_id="EV-PHASE2-MANUAL-001",
        source_id=source_b,
        version_hash=manual_hash,
        text="O responsável confirma a autorização antes da execução da medida.",
        page=4,
        section="Controlo operacional",
        block_type="text",
        bbox=(25, 100, 500, 170),
    )

    await persist_structured_extraction(
        source_id=source_a,
        extraction=_extraction(
            version_hash=old_hash,
            title="Regulamento operacional, versão antiga",
            blocks=[old_block],
        ),
    )
    await persist_structured_extraction(
        source_id=source_a,
        extraction=_extraction(
            version_hash=current_hash,
            title="Regulamento operacional",
            blocks=[current_table, current_note],
        ),
    )
    await persist_structured_extraction(
        source_id=source_b,
        extraction=_extraction(
            version_hash=manual_hash,
            title="Manual de procedimentos",
            blocks=[manual_block],
        ),
    )

    active_model = {"name": "phase2-deterministic-embedding"}

    async def fake_get_embedding_model() -> _FakeEmbeddingModel:
        return _FakeEmbeddingModel(model_name=active_model["name"])

    async def fake_generate_embeddings(texts: list[str]) -> list[list[float]]:
        return [_deterministic_vector(text) for text in texts]

    async def fake_generate_embedding(query: str) -> list[float]:
        return _deterministic_vector(query)

    monkeypatch.setattr(model_manager, "get_embedding_model", fake_get_embedding_model)
    monkeypatch.setattr(
        "open_notebook.evidence.retrieval.generate_embeddings",
        fake_generate_embeddings,
    )
    monkeypatch.setattr(
        "open_notebook.evidence.retrieval.generate_embedding",
        fake_generate_embedding,
    )

    indexed = await index_evidence_blocks(force=True, batch_size=2)
    assert indexed.considered == 4
    assert indexed.embedded == 4
    assert indexed.failed == 0
    assert indexed.embedding_model == "phase2-deterministic-embedding"

    active_model["name"] = "phase2-deterministic-embedding-v2"
    reindexed = await index_evidence_blocks(force=False, batch_size=2)
    assert reindexed.embedded == 4
    assert reindexed.embedding_model == active_model["name"]

    stored = await repo_query(
        "SELECT evidence_id, embedding, embedding_model, embedded_text_hash, indexing_status "
        "FROM evidence_block ORDER BY evidence_id"
    )
    assert len(stored) == 4
    assert all(row["embedding"] for row in stored)
    assert all(row["embedded_text_hash"] for row in stored)
    assert all(row["embedding_model"] == active_model["name"] for row in stored)
    assert all(row["indexing_status"] == "indexed" for row in stored)

    response = await retrieve_evidence(
        query="Qual é o prazo para decidir a autorização?",
        limit=3,
        minimum_score=0.05,
        allow_legacy_fallback=False,
    )
    assert response.selected_versions[source_a] == current_hash
    assert response.selected_versions[source_b] == manual_hash
    assert response.hits[0].evidence_id == "EV-PHASE2-CURRENT-001"
    assert all(hit.evidence_id != "EV-PHASE2-OLD-001" for hit in response.hits)

    first = response.hits[0]
    manual = next(
        hit for hit in response.hits if hit.evidence_id == "EV-PHASE2-MANUAL-001"
    )
    assert first.semantic_score > manual.semantic_score
    assert first.lexical_score > manual.lexical_score
    assert first.score > manual.score
    assert first.document_title == "Regulamento operacional"
    assert first.document_version_hash == current_hash
    assert first.pdf_page == 2
    assert first.printed_page == "102"
    assert first.section_path == ["Prazos de autorização"]
    assert first.bbox == {
        "x0": 40.0,
        "y0": 120.0,
        "x1": 520.0,
        "y1": 260.0,
        "coordinate_origin": "TOPLEFT",
    }

    filtered = await retrieve_evidence(
        query="prazo de autorização 24 horas",
        filters=EvidenceSearchFilters(
            source_id=source_a,
            pdf_page=2,
            section="Prazos",
            block_types=["table"],
        ),
        allow_legacy_fallback=True,
    )
    assert [hit.evidence_id for hit in filtered.hits] == ["EV-PHASE2-CURRENT-001"]
    assert filtered.hits[0].structural_score == 1.0

    historical = await retrieve_evidence(
        query="setenta e duas horas",
        filters=EvidenceSearchFilters(source_id=source_a, version_hash=old_hash),
        allow_legacy_fallback=True,
    )
    assert historical.selected_versions == {source_a: old_hash}
    assert [hit.evidence_id for hit in historical.hits] == ["EV-PHASE2-OLD-001"]

    legacy_called = False

    async def fake_legacy_vector_search(**_: object) -> list[dict[str, object]]:
        nonlocal legacy_called
        legacy_called = True
        return [{"id": source_b, "title": "Manual de procedimentos", "similarity": 0.8}]

    monkeypatch.setattr(
        "open_notebook.evidence.retrieval.legacy_vector_search",
        fake_legacy_vector_search,
    )
    filtered_miss = await retrieve_evidence(
        query="expressão inexistente no corpus",
        filters=EvidenceSearchFilters(block_types=["nonexistent"]),
        allow_legacy_fallback=True,
    )
    assert filtered_miss.hits == []
    assert filtered_miss.used_legacy_fallback is False
    assert filtered_miss.legacy_fallback_reason == "disabled_by_filters"
    assert legacy_called is False
