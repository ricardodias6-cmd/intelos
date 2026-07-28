"""End-to-end validation of a realistic Portuguese PDF ingestion.

The module is deliberately excluded from the normal unit-test environment. The
Phase 1 workflow enables it inside the full application image, with Docling and
a real SurrealDB instance available.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Sequence
from pathlib import Path

import pytest

from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.evidence.docling_adapter import extract_with_docling_evidence
from open_notebook.evidence.ingestion import persist_structured_extraction
from open_notebook.evidence.models import EvidenceBlock

pytestmark = pytest.mark.skipif(
    os.getenv("INTELOS_RUN_DOCUMENT_INGESTION") != "1",
    reason="requires the dedicated Phase 1 Docling and SurrealDB environment",
)

SOURCE_ID = "source:phase1_portuguese_pdf"
EXPECTED_PAGES = 3
ANCHORS = {
    "Compete à entidade X autorizar a medida.": 1,
    "COLUNA ESQUERDA": 2,
    "COLUNA DIREITA": 2,
    "Prazo": 2,
    "24 horas": 2,
    "Versão documental imutável.": 3,
}


def _pdf_string(value: str) -> bytes:
    encoded = value.encode("cp1252")
    return (
        encoded.replace(b"\\", b"\\\\")
        .replace(b"(", b"\\(")
        .replace(b")", b"\\)")
    )


def _page_stream(lines: list[tuple[int, int, int, str]]) -> bytes:
    commands = [b"BT"]
    for size, x, y, text in lines:
        commands.extend(
            [
                f"/F1 {size} Tf".encode(),
                f"1 0 0 1 {x} {y} Tm".encode(),
                b"(" + _pdf_string(text) + b") Tj",
            ]
        )
    commands.append(b"ET")
    return b"\n".join(commands)


def _build_pdf(path: Path) -> bytes:
    """Write a deterministic, valid three-page PDF with realistic structures."""
    pages = [
        _page_stream(
            [
                (9, 55, 810, "INTELOS | TESTE DOCUMENTAL PORTUGUÊS"),
                (18, 55, 760, "Regulamento de Validação Documental"),
                (13, 55, 710, "Artigo 1.º"),
                (11, 55, 680, "Compete à entidade X autorizar a medida."),
                (11, 55, 650, "A decisão deve ficar associada à versão exata da fonte."),
                (9, 55, 35, "Página impressa 101"),
            ]
        ),
        _page_stream(
            [
                (9, 55, 810, "INTELOS | TESTE DOCUMENTAL PORTUGUÊS"),
                (14, 55, 770, "Artigo 2.º | Estrutura em duas colunas"),
                (11, 55, 730, "COLUNA ESQUERDA"),
                (10, 55, 705, "A evidência conserva a página física."),
                (10, 55, 680, "O texto mantém o respetivo hash."),
                (11, 330, 730, "COLUNA DIREITA"),
                (10, 330, 705, "A proveniência inclui coordenadas."),
                (10, 330, 680, "A reimportação deve ser idempotente."),
                (12, 55, 600, "Tabela de controlo"),
                (10, 55, 570, "Campo"),
                (10, 230, 570, "Valor"),
                (10, 55, 545, "Prazo"),
                (10, 230, 545, "24 horas"),
                (10, 55, 520, "Estado"),
                (10, 230, 520, "Confirmado"),
                (9, 55, 35, "Página impressa 102"),
            ]
        ),
        _page_stream(
            [
                (9, 55, 810, "INTELOS | TESTE DOCUMENTAL PORTUGUÊS"),
                (14, 55, 760, "Artigo 3.º | Integridade e notas"),
                (11, 55, 715, "Versão documental imutável."),
                (11, 55, 685, "Uma alteração binária deve criar uma versão distinta."),
                (9, 55, 100, "Nota 1: o rodapé não pertence ao conteúdo normativo."),
                (9, 55, 35, "Página impressa 103"),
            ]
        ),
    ]

    objects: list[bytes] = []

    def add(obj: bytes) -> int:
        objects.append(obj)
        return len(objects)

    add(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>"
    )
    page_ids: list[int] = []
    content_ids: list[int] = []
    for stream in pages:
        content_ids.append(
            add(
                b"<< /Length "
                + str(len(stream)).encode()
                + b" >>\nstream\n"
                + stream
                + b"\nendstream"
            )
        )
        page_ids.append(add(b""))

    kids = b" ".join(f"{page_id} 0 R".encode() for page_id in page_ids)
    objects.insert(
        1,
        b"<< /Type /Pages /Count "
        + str(len(page_ids)).encode()
        + b" /Kids [ "
        + kids
        + b" ] >>",
    )

    shifted_page_ids = [page_id + 1 for page_id in page_ids]
    shifted_content_ids = [content_id + 1 for content_id in content_ids]
    kids = b" ".join(f"{page_id} 0 R".encode() for page_id in shifted_page_ids)
    objects[1] = (
        b"<< /Type /Pages /Count "
        + str(len(shifted_page_ids)).encode()
        + b" /Kids [ "
        + kids
        + b" ] >>"
    )

    for page_id, content_id in zip(shifted_page_ids, shifted_content_ids, strict=True):
        objects[page_id - 1] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 1 0 R >> >> "
            + f"/Contents {content_id} 0 R >>".encode()
        )

    catalog_id = add(b"<< /Type /Catalog /Pages 2 0 R >>")
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode())
        output.extend(obj)
        output.extend(b"\nendobj\n")

    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        b"trailer\n<< /Size "
        + str(len(objects) + 1).encode()
        + f" /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )

    data = bytes(output)
    path.write_bytes(data)
    return data


def _blocks_for_anchor(
    blocks: Sequence[EvidenceBlock],
    anchor: str,
) -> list[EvidenceBlock]:
    return [block for block in blocks if anchor in block.raw_text]


@pytest.mark.asyncio
async def test_01_ingest_realistic_portuguese_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "regulamento-validacao-documental.pdf"
    pdf_bytes = _build_pdf(pdf_path)

    extraction = await extract_with_docling_evidence(
        file_path=str(pdf_path),
        source_id=SOURCE_ID,
        do_ocr=False,
        do_formulas=False,
        do_vision=False,
    )

    assert extraction.version_hash == hashlib.sha256(pdf_bytes).hexdigest()
    assert extraction.page_count == EXPECTED_PAGES
    assert extraction.blocks

    for anchor, expected_page in ANCHORS.items():
        matches = _blocks_for_anchor(extraction.blocks, anchor)
        assert matches, f"Docling did not preserve required anchor: {anchor}"
        assert {block.pdf_page for block in matches} == {expected_page}
        assert all(block.bbox is not None for block in matches)

    evidence_ids = [block.evidence_id for block in extraction.blocks]
    assert len(evidence_ids) == len(set(evidence_ids))
    assert all(block.text_hash for block in extraction.blocks)

    await repo_query("DELETE $source;", {"source": ensure_record_id(SOURCE_ID)})
    await repo_query(
        "CREATE $source SET title = $title;",
        {
            "source": ensure_record_id(SOURCE_ID),
            "title": "Regulamento de Validação Documental",
        },
    )

    first = await persist_structured_extraction(
        source_id=SOURCE_ID,
        extraction=extraction,
    )
    second = await persist_structured_extraction(
        source_id=SOURCE_ID,
        extraction=extraction,
    )

    assert first.created_version is True
    assert first.created_blocks == len(extraction.blocks)
    assert second.created_version is False
    assert second.created_blocks == 0
    assert second.existing_blocks == len(extraction.blocks)


@pytest.mark.asyncio
async def test_02_verify_stable_evidence_after_database_restart(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "regulamento-validacao-documental.pdf"
    _build_pdf(pdf_path)
    extraction = await extract_with_docling_evidence(
        file_path=str(pdf_path),
        source_id=SOURCE_ID,
        do_ocr=False,
        do_formulas=False,
        do_vision=False,
    )

    versions = await repo_query(
        "SELECT * FROM document_version WHERE source = $source;",
        {"source": ensure_record_id(SOURCE_ID)},
    )
    assert len(versions) == 1
    assert versions[0]["version_hash"] == extraction.version_hash

    rows = await repo_query(
        "SELECT * FROM evidence_block WHERE source = $source;",
        {"source": ensure_record_id(SOURCE_ID)},
    )
    assert rows
    assert {row["evidence_id"] for row in rows} == {
        block.evidence_id for block in extraction.blocks
    }

    persisted_by_id = {row["evidence_id"]: row for row in rows}
    for block in extraction.blocks:
        persisted = persisted_by_id[block.evidence_id]
        assert persisted["raw_text"] == block.raw_text
        assert persisted["text_hash"] == block.text_hash
        assert persisted["pdf_page"] == block.pdf_page
        assert persisted["bbox"] == block.bbox.model_dump()