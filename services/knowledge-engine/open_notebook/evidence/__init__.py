"""Evidence Core primitives for verifiable Intelos responses."""

from open_notebook.evidence.constitution import CONSTITUTION_VERSION, RESPONSE_RULES
from open_notebook.evidence.models import (
    BoundingBox,
    Claim,
    ClaimKind,
    CoordinateOrigin,
    EvidenceBlock,
    ExtractionMethod,
    FreshnessStatus,
    NumericStatus,
    SupportStatus,
    ValidationIssue,
    ValidationReport,
    VerificationStatus,
)
from open_notebook.evidence.validation import EvidenceValidator
from open_notebook.evidence.versioning import (
    DocumentChange,
    DocumentChangeType,
    DocumentVersionCandidate,
    DocumentVersionSnapshot,
    DocumentVersionStatus,
    detect_document_change,
    persist_document_change,
)

__all__ = [
    "BoundingBox",
    "Claim",
    "ClaimKind",
    "CONSTITUTION_VERSION",
    "CoordinateOrigin",
    "DocumentChange",
    "DocumentChangeType",
    "DocumentVersionCandidate",
    "DocumentVersionSnapshot",
    "DocumentVersionStatus",
    "EvidenceBlock",
    "EvidenceValidator",
    "ExtractionMethod",
    "FreshnessStatus",
    "NumericStatus",
    "RESPONSE_RULES",
    "SupportStatus",
    "ValidationIssue",
    "ValidationReport",
    "VerificationStatus",
    "detect_document_change",
    "persist_document_change",
]
