"""SurrealDB persistence models for the Intelos Evidence Core."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, ClassVar, Optional, Union

from pydantic import ConfigDict, field_validator
from surrealdb import RecordID

from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.base import ObjectModel
from open_notebook.evidence.models import (
    BoundingBox,
    Claim,
    ClaimKind,
    EvidenceBlock,
    ExtractionMethod,
    FreshnessStatus,
    NumericStatus,
    SupportStatus,
    VerificationStatus,
)
from open_notebook.exceptions import InvalidInputError

RecordReference = Union[str, RecordID]


def _record_to_string(value: RecordReference) -> str:
    return str(value)


class DocumentVersionRecord(ObjectModel):
    """One immutable extraction version of an Open Notebook source."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    table_name: ClassVar[str] = "document_version"

    source: RecordReference
    version_hash: str
    extraction_method: ExtractionMethod
    page_count: Optional[int] = None
    source_date: Optional[datetime] = None
    metadata: Optional[dict[str, Any]] = None

    @field_validator("source", mode="before")
    @classmethod
    def parse_source(cls, value: Any) -> RecordReference:
        if not value:
            raise InvalidInputError("Document version source is required")
        return value

    def _prepare_save_data(self) -> dict[str, Any]:
        data = super()._prepare_save_data()
        data["source"] = ensure_record_id(_record_to_string(self.source))
        return data

    @classmethod
    async def get_for_source(cls, source_id: str) -> list["DocumentVersionRecord"]:
        if not source_id:
            raise InvalidInputError("Source ID is required")
        rows = await repo_query(
            "SELECT * FROM document_version WHERE source = $source ORDER BY created DESC",
            {"source": ensure_record_id(source_id)},
        )
        return [cls(**row) for row in rows]


class EvidenceBlockRecord(ObjectModel):
    """Persistent evidence block tied to a source and document version."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    table_name: ClassVar[str] = "evidence_block"

    evidence_id: str
    source: RecordReference
    document_version: RecordReference
    raw_text: str
    verified_text: Optional[str] = None
    text_hash: str
    pdf_page: Optional[int] = None
    printed_page: Optional[str] = None
    section_path: Optional[list[str]] = None
    bbox: Optional[dict[str, float]] = None
    block_type: str = "text"
    extraction_method: ExtractionMethod
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    embedding: Optional[list[float]] = None

    @field_validator("source", "document_version", mode="before")
    @classmethod
    def parse_record_reference(cls, value: Any) -> RecordReference:
        if not value:
            raise InvalidInputError("Evidence record references are required")
        return value

    def _prepare_save_data(self) -> dict[str, Any]:
        data = super()._prepare_save_data()
        data["source"] = ensure_record_id(_record_to_string(self.source))
        data["document_version"] = ensure_record_id(
            _record_to_string(self.document_version)
        )
        return data

    def to_domain(self, *, document_version_hash: str) -> EvidenceBlock:
        bbox = BoundingBox(**self.bbox) if self.bbox else None
        return EvidenceBlock(
            evidence_id=self.evidence_id,
            source_id=_record_to_string(self.source),
            document_version_hash=document_version_hash,
            raw_text=self.raw_text,
            verified_text=self.verified_text,
            pdf_page=self.pdf_page,
            printed_page=self.printed_page,
            section_path=self.section_path or [],
            bbox=bbox,
            block_type=self.block_type,
            extraction_method=self.extraction_method,
            verification_status=self.verification_status,
            text_hash=self.text_hash,
            created_at=self.created or datetime.now(),
        )

    @classmethod
    async def get_for_version(
        cls, document_version_id: str
    ) -> list["EvidenceBlockRecord"]:
        if not document_version_id:
            raise InvalidInputError("Document version ID is required")
        rows = await repo_query(
            "SELECT * FROM evidence_block WHERE document_version = $version ORDER BY pdf_page, created",
            {"version": ensure_record_id(document_version_id)},
        )
        return [cls(**row) for row in rows]


class ClaimRecord(ObjectModel):
    """Persistent atomic assertion produced or confirmed by Intelos."""

    table_name: ClassVar[str] = "claim"

    claim_id: str
    text: str
    claim_kind: ClaimKind = ClaimKind.FACT
    support_status: SupportStatus = SupportStatus.UNSUPPORTED
    quoted_text: Optional[str] = None
    uncertainty_note: Optional[str] = None
    assumptions: Optional[list[str]] = None
    time_sensitive: bool = False
    as_of: Optional[datetime] = None
    freshness_status: FreshnessStatus = FreshnessStatus.UNKNOWN
    numeric_status: Optional[NumericStatus] = None
    render_as_definitive: bool = False

    def to_domain(self, *, evidence_ids: list[str]) -> Claim:
        as_of_date: date | None = self.as_of.date() if self.as_of else None
        return Claim(
            claim_id=self.claim_id,
            text=self.text,
            kind=self.claim_kind,
            evidence_ids=evidence_ids,
            support_status=self.support_status,
            quoted_text=self.quoted_text,
            uncertainty_note=self.uncertainty_note,
            assumptions=self.assumptions or [],
            time_sensitive=self.time_sensitive,
            as_of=as_of_date,
            freshness_status=self.freshness_status,
            numeric_status=self.numeric_status,
            render_as_definitive=self.render_as_definitive,
        )

    async def link_evidence(
        self,
        evidence_record_id: str,
        *,
        relation_type: SupportStatus,
        note: str | None = None,
    ) -> Any:
        if self.id is None:
            raise InvalidInputError("Claim must be saved before linking evidence")
        data: dict[str, Any] = {"relation_type": relation_type.value}
        if note:
            data["note"] = note
        return await self.relate("claim_evidence", evidence_record_id, data)

    async def get_evidence_ids(self) -> list[str]:
        if self.id is None:
            raise InvalidInputError("Claim must be saved before reading evidence")
        rows = await repo_query(
            "SELECT VALUE out.evidence_id FROM claim_evidence WHERE in = $claim",
            {"claim": ensure_record_id(self.id)},
        )
        return [str(value) for value in rows]
