"""Domain models for versioned evidence and verifiable claims."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_STABLE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{2,127}$")


class ExtractionMethod(StrEnum):
    NATIVE_TEXT = "native_text"
    DOCLING = "docling"
    CHANDRA = "chandra"
    MANUAL = "manual"


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    AUTOMATICALLY_VERIFIED = "automatically_verified"
    HUMAN_CONFIRMED = "human_confirmed"
    REJECTED = "rejected"


class ClaimKind(StrEnum):
    FACT = "fact"
    QUOTE = "quote"
    STATISTIC = "statistic"
    TECHNICAL = "technical"
    ASSUMPTION = "assumption"
    OPINION = "opinion"
    USER_PROVIDED = "user_provided"


class SupportStatus(StrEnum):
    DIRECT = "direct"
    PARTIAL = "partial"
    INFERENCE = "inference"
    INTERPRETATION = "interpretation"
    CONTRADICTED = "contradicted"
    UNSUPPORTED = "unsupported"


class FreshnessStatus(StrEnum):
    CURRENT = "current"
    POSSIBLY_OUTDATED = "possibly_outdated"
    OUTDATED = "outdated"
    UNKNOWN = "unknown"


class NumericStatus(StrEnum):
    EXACT = "exact"
    REPORTED = "reported"
    APPROXIMATE = "approximate"
    UNKNOWN = "unknown"


class IssueSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class BoundingBox(BaseModel):
    """Coordinates on the rendered page, in the page coordinate system."""

    model_config = ConfigDict(frozen=True)

    x0: float = Field(ge=0)
    y0: float = Field(ge=0)
    x1: float = Field(gt=0)
    y1: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_geometry(self) -> "BoundingBox":
        if self.x1 <= self.x0:
            raise ValueError("x1 must be greater than x0")
        if self.y1 <= self.y0:
            raise ValueError("y1 must be greater than y0")
        return self


class EvidenceBlock(BaseModel):
    """An immutable passage tied to one exact version of a source."""

    model_config = ConfigDict(str_strip_whitespace=True)

    evidence_id: str
    source_id: str
    document_version_hash: str
    raw_text: str = Field(min_length=1)
    verified_text: str | None = None
    pdf_page: int | None = Field(default=None, ge=1)
    printed_page: str | None = None
    section_path: list[str] = Field(default_factory=list)
    bbox: BoundingBox | None = None
    block_type: str = "text"
    extraction_method: ExtractionMethod
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    text_hash: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @field_validator("evidence_id", "source_id")
    @classmethod
    def validate_stable_id(cls, value: str) -> str:
        if not _STABLE_ID_RE.fullmatch(value):
            raise ValueError(
                "identifier must use upper-case letters, numbers, underscores or hyphens"
            )
        return value

    @field_validator("document_version_hash", "text_hash")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        normalized = value.lower()
        if not _SHA256_RE.fullmatch(normalized):
            raise ValueError("hash must be a 64-character hexadecimal SHA-256 value")
        return normalized

    @field_validator("section_path")
    @classmethod
    def remove_empty_sections(cls, value: list[str]) -> list[str]:
        return [section.strip() for section in value if section.strip()]

    @model_validator(mode="after")
    def validate_confirmation(self) -> "EvidenceBlock":
        if (
            self.verification_status == VerificationStatus.HUMAN_CONFIRMED
            and not self.verified_text
        ):
            raise ValueError("human-confirmed evidence requires verified_text")
        if self.verification_status == VerificationStatus.REJECTED and self.verified_text:
            raise ValueError("rejected evidence cannot expose verified_text")
        return self

    @property
    def effective_text(self) -> str:
        """Return human-confirmed text when available, otherwise extracted text."""

        return self.verified_text or self.raw_text


class Claim(BaseModel):
    """One atomic statement with an explicit epistemic status."""

    model_config = ConfigDict(str_strip_whitespace=True)

    claim_id: str
    text: str = Field(min_length=1)
    kind: ClaimKind = ClaimKind.FACT
    evidence_ids: list[str] = Field(default_factory=list)
    support_status: SupportStatus = SupportStatus.UNSUPPORTED
    quoted_text: str | None = None
    uncertainty_note: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    time_sensitive: bool = False
    as_of: date | None = None
    freshness_status: FreshnessStatus = FreshnessStatus.UNKNOWN
    numeric_status: NumericStatus | None = None
    render_as_definitive: bool = False

    @field_validator("claim_id")
    @classmethod
    def validate_claim_id(cls, value: str) -> str:
        if not _STABLE_ID_RE.fullmatch(value):
            raise ValueError(
                "identifier must use upper-case letters, numbers, underscores or hyphens"
            )
        return value

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence_ids(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @field_validator("assumptions")
    @classmethod
    def remove_empty_assumptions(cls, value: list[str]) -> list[str]:
        return [assumption.strip() for assumption in value if assumption.strip()]

    @model_validator(mode="after")
    def validate_claim_shape(self) -> "Claim":
        evidence_required = self.kind in {
            ClaimKind.FACT,
            ClaimKind.QUOTE,
            ClaimKind.STATISTIC,
            ClaimKind.TECHNICAL,
        }
        if evidence_required and not self.evidence_ids:
            raise ValueError(f"{self.kind.value} claims require evidence_ids")

        if self.kind == ClaimKind.QUOTE and not self.quoted_text:
            raise ValueError("quote claims require quoted_text")

        if self.kind == ClaimKind.STATISTIC and self.numeric_status is None:
            raise ValueError("statistic claims require numeric_status")

        if self.time_sensitive and self.as_of is None:
            raise ValueError("time-sensitive claims require an as_of date")

        if self.support_status == SupportStatus.UNSUPPORTED and self.render_as_definitive:
            raise ValueError("unsupported claims cannot be rendered as definitive")

        if self.support_status == SupportStatus.CONTRADICTED and self.render_as_definitive:
            raise ValueError("contradicted claims cannot be rendered as definitive")

        return self


class ValidationIssue(BaseModel):
    """One deterministic validation finding."""

    code: str
    message: str
    severity: IssueSeverity
    claim_id: str | None = None
    evidence_id: str | None = None


class ValidationReport(BaseModel):
    """Machine-readable result of validating a set of claims."""

    constitution_version: str
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    checked_claims: int = 0
    checked_evidence: int = 0
    locale: Literal["pt-PT"] = "pt-PT"
