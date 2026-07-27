"""Deterministic validation for evidence-backed claims.

These checks prove structural properties such as identifier resolution, version
integrity and literal quotation matching. They deliberately do not claim to
solve semantic entailment, which requires a separate model or human review.
"""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from collections.abc import Iterable

from open_notebook.evidence.constitution import CONSTITUTION_VERSION
from open_notebook.evidence.models import (
    Claim,
    ClaimKind,
    EvidenceBlock,
    FreshnessStatus,
    IssueSeverity,
    NumericStatus,
    SupportStatus,
    ValidationIssue,
    ValidationReport,
    VerificationStatus,
)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _normalized_literal(value: str) -> str:
    """Normalize representation without weakening literal quote matching."""

    value = html.unescape(value)
    value = _HTML_TAG_RE.sub(" ", value)
    value = unicodedata.normalize("NFKC", value)
    return _WHITESPACE_RE.sub(" ", value).strip()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class EvidenceValidator:
    """Validate claims against a closed registry of immutable evidence blocks."""

    def __init__(self, evidence: Iterable[EvidenceBlock]):
        self._evidence: dict[str, EvidenceBlock] = {}
        for block in evidence:
            if block.evidence_id in self._evidence:
                raise ValueError(f"duplicate evidence_id: {block.evidence_id}")
            self._evidence[block.evidence_id] = block

    def validate(self, claims: Iterable[Claim]) -> ValidationReport:
        claim_list = list(claims)
        issues: list[ValidationIssue] = []

        for block in self._evidence.values():
            issues.extend(self._validate_evidence_integrity(block))

        for claim in claim_list:
            issues.extend(self._validate_claim(claim))

        return ValidationReport(
            constitution_version=CONSTITUTION_VERSION,
            valid=not any(issue.severity == IssueSeverity.ERROR for issue in issues),
            issues=issues,
            checked_claims=len(claim_list),
            checked_evidence=len(self._evidence),
        )

    def _validate_evidence_integrity(
        self, block: EvidenceBlock
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        calculated_hash = _sha256_text(block.raw_text)
        if calculated_hash != block.text_hash:
            issues.append(
                ValidationIssue(
                    code="EVIDENCE_TEXT_HASH_MISMATCH",
                    message=(
                        "O hash do texto não corresponde ao conteúdo extraído. "
                        "A evidência pode ter sido alterada."
                    ),
                    severity=IssueSeverity.ERROR,
                    evidence_id=block.evidence_id,
                )
            )

        if block.verification_status == VerificationStatus.REJECTED:
            issues.append(
                ValidationIssue(
                    code="EVIDENCE_REJECTED",
                    message="A evidência foi rejeitada e não pode sustentar afirmações.",
                    severity=IssueSeverity.ERROR,
                    evidence_id=block.evidence_id,
                )
            )

        if block.pdf_page is None:
            issues.append(
                ValidationIssue(
                    code="EVIDENCE_PAGE_MISSING",
                    message=(
                        "A evidência não tem página física associada. A confirmação "
                        "visual não será possível."
                    ),
                    severity=IssueSeverity.WARNING,
                    evidence_id=block.evidence_id,
                )
            )

        return issues

    def _validate_claim(self, claim: Claim) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        resolved: list[EvidenceBlock] = []

        for evidence_id in claim.evidence_ids:
            block = self._evidence.get(evidence_id)
            if block is None:
                issues.append(
                    ValidationIssue(
                        code="EVIDENCE_NOT_FOUND",
                        message=(
                            "A afirmação referencia um identificador de evidência "
                            "que não existe no registo fechado."
                        ),
                        severity=IssueSeverity.ERROR,
                        claim_id=claim.claim_id,
                        evidence_id=evidence_id,
                    )
                )
                continue
            resolved.append(block)

        if claim.kind == ClaimKind.QUOTE and claim.quoted_text:
            quoted = _normalized_literal(claim.quoted_text)
            if not any(
                quoted in _normalized_literal(block.effective_text)
                for block in resolved
            ):
                issues.append(
                    ValidationIssue(
                        code="QUOTE_NOT_FOUND_IN_EVIDENCE",
                        message=(
                            "O transcrito não ocorre literalmente nas evidências "
                            "associadas após normalização de espaços e HTML."
                        ),
                        severity=IssueSeverity.ERROR,
                        claim_id=claim.claim_id,
                    )
                )

        if claim.kind == ClaimKind.STATISTIC:
            if claim.numeric_status in {NumericStatus.APPROXIMATE, NumericStatus.UNKNOWN}:
                if not claim.uncertainty_note:
                    issues.append(
                        ValidationIssue(
                            code="NUMERIC_UNCERTAINTY_NOT_DISCLOSED",
                            message=(
                                "Um valor aproximado ou não confirmado exige uma "
                                "nota explícita de incerteza."
                            ),
                            severity=IssueSeverity.ERROR,
                            claim_id=claim.claim_id,
                        )
                    )

        if claim.time_sensitive:
            if claim.freshness_status == FreshnessStatus.UNKNOWN:
                issues.append(
                    ValidationIssue(
                        code="FRESHNESS_UNKNOWN",
                        message=(
                            "A afirmação é sensível ao tempo, mas a atualidade da "
                            "fonte não foi confirmada."
                        ),
                        severity=IssueSeverity.ERROR,
                        claim_id=claim.claim_id,
                    )
                )
            elif claim.freshness_status == FreshnessStatus.POSSIBLY_OUTDATED:
                issues.append(
                    ValidationIssue(
                        code="SOURCE_POSSIBLY_OUTDATED",
                        message="A fonte pode estar desatualizada e deve ser verificada.",
                        severity=IssueSeverity.WARNING,
                        claim_id=claim.claim_id,
                    )
                )
            elif claim.freshness_status == FreshnessStatus.OUTDATED:
                issues.append(
                    ValidationIssue(
                        code="SOURCE_OUTDATED",
                        message="A afirmação depende de uma fonte marcada como desatualizada.",
                        severity=IssueSeverity.ERROR,
                        claim_id=claim.claim_id,
                    )
                )

        if claim.support_status in {
            SupportStatus.INFERENCE,
            SupportStatus.INTERPRETATION,
            SupportStatus.PARTIAL,
        } and claim.render_as_definitive:
            issues.append(
                ValidationIssue(
                    code="NON_DIRECT_CLAIM_RENDERED_AS_DEFINITIVE",
                    message=(
                        "Uma inferência, interpretação ou afirmação parcialmente "
                        "sustentada não pode ser apresentada como facto definitivo."
                    ),
                    severity=IssueSeverity.ERROR,
                    claim_id=claim.claim_id,
                )
            )

        if claim.kind == ClaimKind.USER_PROVIDED and claim.render_as_definitive:
            issues.append(
                ValidationIssue(
                    code="USER_ASSERTION_TREATED_AS_VERIFIED",
                    message=(
                        "Uma afirmação fornecida pelo utilizador não pode ser tratada "
                        "automaticamente como facto verificado."
                    ),
                    severity=IssueSeverity.ERROR,
                    claim_id=claim.claim_id,
                )
            )

        if claim.assumptions:
            issues.append(
                ValidationIssue(
                    code="ASSUMPTIONS_PRESENT",
                    message=(
                        "A resposta depende de pressupostos que devem ser apresentados "
                        "explicitamente ao utilizador."
                    ),
                    severity=IssueSeverity.WARNING,
                    claim_id=claim.claim_id,
                )
            )

        return issues
