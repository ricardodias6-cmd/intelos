"""Docling adapter that preserves document provenance for the Evidence Core."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from open_notebook.evidence.models import (
    BoundingBox,
    CoordinateOrigin,
    EvidenceBlock,
    ExtractionMethod,
    VerificationStatus,
)


class DoclingRuntimeUnavailable(RuntimeError):
    """Raised when the optional Docling runtime is not installed."""


@dataclass(slots=True)
class StructuredDocumentExtraction:
    """One Docling conversion shared by source text and evidence ingestion."""

    content: str
    title: str
    identified_type: str
    version_hash: str
    page_count: int | None
    blocks: list[EvidenceBlock] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _enum_value(value: Any, default: str) -> str:
    if value is None:
        return default
    enum_value = getattr(value, "value", None)
    return str(enum_value if enum_value is not None else value)


def _item_text(item: Any, document: Any) -> str:
    text = getattr(item, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    export = getattr(item, "export_to_markdown", None)
    if callable(export):
        try:
            value = export(doc=document)
        except TypeError:
            try:
                value = export(document)
            except TypeError:
                value = None
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def _section_path_for_item(
    *, label: str, text: str, level: int, headings: dict[int, str]
) -> list[str]:
    normalized_label = label.lower().replace("-", "_")
    is_heading = normalized_label in {"title", "section_header"} or (
        "section" in normalized_label and "header" in normalized_label
    )

    if is_heading and text:
        headings[level] = text
        for heading_level in list(headings):
            if heading_level > level:
                del headings[heading_level]

    return [headings[key] for key in sorted(headings) if headings[key]]


def _bbox_from_provenance(provenance: Any) -> BoundingBox | None:
    bbox = getattr(provenance, "bbox", None)
    if bbox is None:
        return None

    left = getattr(bbox, "l", None)
    top = getattr(bbox, "t", None)
    right = getattr(bbox, "r", None)
    bottom = getattr(bbox, "b", None)
    if any(value is None for value in (left, top, right, bottom)):
        return None

    try:
        left_value = float(left)
        top_value = float(top)
        right_value = float(right)
        bottom_value = float(bottom)
        origin_value = _enum_value(
            getattr(bbox, "coord_origin", None), CoordinateOrigin.TOP_LEFT.value
        ).upper()
        try:
            coordinate_origin = CoordinateOrigin(origin_value)
        except ValueError:
            coordinate_origin = CoordinateOrigin.UNKNOWN

        return BoundingBox(
            x0=min(left_value, right_value),
            y0=min(top_value, bottom_value),
            x1=max(left_value, right_value),
            y1=max(top_value, bottom_value),
            coordinate_origin=coordinate_origin,
        )
    except (TypeError, ValueError):
        return None


def _text_for_provenance(text: str, provenance: Any) -> str:
    charspan = getattr(provenance, "charspan", None)
    if not isinstance(charspan, (list, tuple)) or len(charspan) != 2:
        return text

    start, end = charspan
    if not isinstance(start, int) or not isinstance(end, int):
        return text
    if start < 0 or end <= start or end > len(text):
        return text

    selected = text[start:end].strip()
    return selected or text


def build_evidence_blocks(
    *, document: Any, source_id: str, version_hash: str
) -> list[EvidenceBlock]:
    """Convert a DoclingDocument into immutable Evidence Core blocks.

    The implementation intentionally uses the stable public document contract
    through ``iterate_items()``, ``item.prov``, ``page_no`` and ``bbox``. Items
    without textual content are skipped because they cannot yet support a
    textual claim. Image evidence will be handled by a later multimodal phase.
    """

    blocks: list[EvidenceBlock] = []
    headings: dict[int, str] = {}

    for item_index, (item, level) in enumerate(document.iterate_items()):
        text = _item_text(item, document)
        if not text:
            continue

        label = _enum_value(getattr(item, "label", None), "text")
        section_path = _section_path_for_item(
            label=label,
            text=text,
            level=int(level),
            headings=headings,
        )
        provenance_items = list(getattr(item, "prov", None) or [])

        if not provenance_items:
            block_text = text
            identity = (
                f"{source_id}:{version_hash}:none:{item_index}:0:{block_text}"
            )
            blocks.append(
                EvidenceBlock(
                    evidence_id=f"EV-{_sha256_text(identity)[:24].upper()}",
                    source_id=source_id,
                    document_version_hash=version_hash,
                    raw_text=block_text,
                    pdf_page=None,
                    section_path=section_path,
                    bbox=None,
                    block_type=label,
                    extraction_method=ExtractionMethod.DOCLING,
                    verification_status=VerificationStatus.UNVERIFIED,
                    text_hash=_sha256_text(block_text),
                )
            )
            continue

        for provenance_index, provenance in enumerate(provenance_items):
            block_text = _text_for_provenance(text, provenance)
            page_no = getattr(provenance, "page_no", None)
            pdf_page = int(page_no) if isinstance(page_no, int) and page_no >= 1 else None
            bbox = _bbox_from_provenance(provenance)
            identity = (
                f"{source_id}:{version_hash}:{pdf_page}:{item_index}:"
                f"{provenance_index}:{block_text}"
            )
            blocks.append(
                EvidenceBlock(
                    evidence_id=f"EV-{_sha256_text(identity)[:24].upper()}",
                    source_id=source_id,
                    document_version_hash=version_hash,
                    raw_text=block_text,
                    pdf_page=pdf_page,
                    section_path=section_path,
                    bbox=bbox,
                    block_type=label,
                    extraction_method=ExtractionMethod.DOCLING,
                    verification_status=VerificationStatus.UNVERIFIED,
                    text_hash=_sha256_text(block_text),
                )
            )

    return blocks


def _convert_sync(
    *,
    file_path: str,
    source_id: str,
    do_ocr: bool,
    do_formulas: bool,
    do_vision: bool,
) -> StructuredDocumentExtraction:
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except ImportError as exc:
        raise DoclingRuntimeUnavailable(
            "Docling is not installed in the current runtime."
        ) from exc

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Document not found: {file_path}")

    if path.suffix.lower() == ".pdf":
        pipeline_options = PdfPipelineOptions(
            do_ocr=do_ocr,
            do_formula_enrichment=do_formulas,
            do_picture_description=do_vision,
            do_chart_extraction=do_vision,
        )
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
    else:
        converter = DocumentConverter()

    result = converter.convert(str(path))
    document = result.document
    content = document.export_to_markdown()
    if not content or not content.strip():
        raise ValueError("Docling did not extract textual content from the document")

    version_hash = _sha256_bytes(path.read_bytes())
    pages = getattr(document, "pages", None)
    page_count = len(pages) if pages is not None else None
    blocks = build_evidence_blocks(
        document=document,
        source_id=source_id,
        version_hash=version_hash,
    )

    return StructuredDocumentExtraction(
        content=content,
        title=getattr(document, "name", None) or path.stem,
        identified_type="application/pdf"
        if path.suffix.lower() == ".pdf"
        else path.suffix.lower().lstrip("."),
        version_hash=version_hash,
        page_count=page_count,
        blocks=blocks,
        metadata={
            "processor": "intelos_docling",
            "docling_output_format": "markdown",
            "evidence_blocks": len(blocks),
            "ocr_enabled": do_ocr,
            "formula_enrichment_enabled": do_formulas,
            "vision_enrichment_enabled": do_vision,
        },
    )


async def extract_with_docling_evidence(
    *,
    file_path: str,
    source_id: str,
    do_ocr: bool = False,
    do_formulas: bool = False,
    do_vision: bool = False,
) -> StructuredDocumentExtraction:
    """Run the blocking Docling conversion outside the event loop."""

    return await asyncio.to_thread(
        _convert_sync,
        file_path=file_path,
        source_id=source_id,
        do_ocr=do_ocr,
        do_formulas=do_formulas,
        do_vision=do_vision,
    )
