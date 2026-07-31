"""Bounded semantic validation between one atomic claim and evidence blocks."""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from collections.abc import Sequence
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from open_notebook.database.repository import repo_query
from open_notebook.evidence.models import SupportStatus, VerificationStatus
from open_notebook.evidence.retrieval import cosine_similarity
from open_notebook.exceptions import InvalidInputError
from open_notebook.utils.embedding import generate_embeddings

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_NUMBER_RE = re.compile(r"(?<!\w)[+-]?\d+(?:[.,]\d+)?(?!\w)")
_SEGMENT_RE = re.compile(r"(?<=[.!?;])\s+|\n+")
_NEGATION_TOKENS = {
    "não",
    "nao",
    "nunca",
    "jamais",
    "sem",
    "nenhum",
    "nenhuma",
    "not",
    "never",
    "without",
    "no",
}


class SemanticEvidenceFinding(BaseModel):
    evidence_id: str
    semantic_score: float = Field(ge=0, le=1)
    lexical_coverage: float = Field(ge=0, le=1)
    numeric_conflict: bool = False
    polarity_conflict: bool = False
    integrity_failed: bool = False
    literal_quote_match: bool = False
    reasons: list[str] = Field(default_factory=list)


class SemanticValidationResult(BaseModel):
    """Recommended support status for one claim.

    `confidence` is read against `recommended_support_status`: for DIRECT and
    PARTIAL it is the strength of the best supporting evidence, while for
    UNSUPPORTED it is the confidence in the *absence* of support. Callers that
    present claims must not use it as a presentation score without checking the
    status first.
    """

    claim: str
    recommended_support_status: SupportStatus
    confidence: float = Field(ge=0, le=1)
    requires_human_review: bool
    evidence_findings: list[SemanticEvidenceFinding]
    unresolved_evidence_ids: list[str] = Field(default_factory=list)
    embedding_model: str
    direct_threshold: float
    partial_threshold: float
    reasons: list[str] = Field(default_factory=list)


def _tokens(text: str) -> list[str]:
    return [token.casefold() for token in _TOKEN_RE.findall(text)]


def _numbers(text: str) -> set[str]:
    return {match.replace(",", ".") for match in _NUMBER_RE.findall(text)}


def _lexical_coverage(claim: str, evidence: str) -> float:
    claim_tokens = set(_tokens(claim))
    if not claim_tokens:
        return 0.0
    return len(claim_tokens & set(_tokens(evidence))) / len(claim_tokens)


def _most_relevant_segment(claim: str, evidence: str) -> tuple[str, float]:
    segments = [segment.strip() for segment in _SEGMENT_RE.split(evidence) if segment.strip()]
    if not segments:
        return evidence, _lexical_coverage(claim, evidence)
    ranked = [(segment, _lexical_coverage(claim, segment)) for segment in segments]
    return max(ranked, key=lambda item: item[1])


def _has_negation(text: str) -> bool:
    return bool(set(_tokens(text)) & _NEGATION_TOKENS)


def _effective_text(row: dict[str, Any]) -> str:
    return str(row.get("verified_text") or row.get("raw_text") or "").strip()


def _record_identifier(value: Any) -> str:
    return str(value)


def _bounded_similarity(value: float) -> float:
    return max(0.0, min(1.0, value))


def _text_integrity_failed(row: dict[str, Any]) -> bool:
    """Detect evidence whose stored text no longer matches its extraction hash.

    A missing hash cannot be checked, so it is logged and treated as
    unverifiable rather than as tampering: only a real mismatch blocks the
    evidence from supporting a claim.
    """

    stored_hash = str(row.get("text_hash") or "").strip().lower()
    raw_text = row.get("raw_text")
    if not stored_hash or raw_text is None:
        logger.warning(
            "Evidence block {} has no verifiable text hash",
            row.get("evidence_id"),
        )
        return False
    calculated = hashlib.sha256(str(raw_text).encode("utf-8")).hexdigest()
    return calculated != stored_hash


def _literal_quote_match(claim: str, evidence_text: str) -> bool:
    """Check that a quoted claim appears literally in the evidence text."""

    normalized_claim = _normalized_literal(claim)
    if not normalized_claim:
        return False
    return normalized_claim in _normalized_literal(evidence_text)


def _normalized_literal(value: str) -> str:
    value = html.unescape(value)
    value = _HTML_TAG_RE.sub(" ", value)
    value = unicodedata.normalize("NFKC", value)
    return _WHITESPACE_RE.sub(" ", value).strip().casefold()


async def validate_claim_semantics(
    *,
    claim: str,
    evidence_ids: Sequence[str],
    direct_threshold: float = 0.82,
    partial_threshold: float = 0.58,
) -> SemanticValidationResult:
    """Recommend a support status without promoting the result to verified truth."""

    normalized_claim = claim.strip()
    unique_ids = list(dict.fromkeys(identifier.strip() for identifier in evidence_ids))
    if not normalized_claim:
        raise InvalidInputError("Semantic validation requires a non-empty claim")
    if not unique_ids or any(not identifier for identifier in unique_ids):
        raise InvalidInputError("Semantic validation requires valid Evidence IDs")
    if len(unique_ids) > 50:
        raise InvalidInputError("Semantic validation accepts at most 50 Evidence IDs")
    if not 0.5 <= partial_threshold <= 0.9:
        raise InvalidInputError("partial_threshold must be between 0.5 and 0.9")
    if not 0.6 <= direct_threshold <= 0.98:
        raise InvalidInputError("direct_threshold must be between 0.6 and 0.98")
    if direct_threshold <= partial_threshold:
        raise InvalidInputError("direct_threshold must be greater than partial_threshold")

    rows = await repo_query(
        "SELECT * FROM evidence_block WHERE evidence_id IN $evidence_ids",
        {"evidence_ids": unique_ids},
    )
    by_id = {str(row.get("evidence_id")): row for row in rows}
    unresolved = [identifier for identifier in unique_ids if identifier not in by_id]
    if unresolved:
        raise InvalidInputError("Evidence IDs not found: " + ", ".join(unresolved))
    resolved = [by_id[identifier] for identifier in unique_ids]

    rejected = [
        str(row["evidence_id"])
        for row in resolved
        if str(row.get("verification_status")) == VerificationStatus.REJECTED.value
    ]
    if rejected:
        raise InvalidInputError(
            "Rejected evidence cannot be used for semantic validation: "
            + ", ".join(rejected)
        )

    versions_by_source: dict[str, set[str]] = {}
    for row in resolved:
        source = _record_identifier(row.get("source"))
        version = _record_identifier(row.get("document_version"))
        versions_by_source.setdefault(source, set()).add(version)
    if any(len(versions) > 1 for versions in versions_by_source.values()):
        raise InvalidInputError(
            "Semantic validation cannot mix document versions for the same source"
        )

    from open_notebook.ai.models import model_manager

    embedding_model = await model_manager.get_embedding_model()
    if not embedding_model:
        raise InvalidInputError("Semantic validation requires an embedding model")
    model_name = str(getattr(embedding_model, "model_name", "unknown"))

    evidence_texts = [_effective_text(row) for row in resolved]
    if any(not text for text in evidence_texts):
        raise InvalidInputError("Evidence blocks must contain text")

    embeddings = await generate_embeddings([normalized_claim, *evidence_texts])
    if len(embeddings) != len(evidence_texts) + 1:
        raise RuntimeError("Embedding provider returned an unexpected batch size")
    claim_embedding = embeddings[0]

    claim_numbers = _numbers(normalized_claim)
    claim_negation = _has_negation(normalized_claim)
    findings: list[SemanticEvidenceFinding] = []
    for row, text, embedding in zip(resolved, evidence_texts, embeddings[1:], strict=True):
        semantic = _bounded_similarity(cosine_similarity(claim_embedding, embedding))
        relevant_segment, segment_coverage = _most_relevant_segment(normalized_claim, text)
        relevant_for_conflict = (
            semantic >= partial_threshold and segment_coverage >= 0.45
        )
        evidence_numbers = _numbers(relevant_segment)
        numeric_conflict = bool(
            relevant_for_conflict
            and claim_numbers
            and evidence_numbers
            and claim_numbers.isdisjoint(evidence_numbers)
        )
        polarity_conflict = bool(
            relevant_for_conflict
            and segment_coverage >= 0.55
            and claim_negation != _has_negation(relevant_segment)
        )
        integrity_failed = _text_integrity_failed(row)
        literal_quote_match = _literal_quote_match(normalized_claim, text)
        reasons: list[str] = []
        if integrity_failed:
            reasons.append(
                "O texto da evidência não corresponde ao hash da extração."
            )
        if numeric_conflict:
            reasons.append("Os valores numéricos relevantes não coincidem.")
        if polarity_conflict:
            reasons.append("Foi detetada possível inversão de polaridade por negação.")
        if semantic >= direct_threshold:
            reasons.append("Compatibilidade semântica elevada.")
        elif semantic >= partial_threshold:
            reasons.append("Compatibilidade semântica moderada.")
        else:
            reasons.append("Compatibilidade semântica insuficiente.")
        findings.append(
            SemanticEvidenceFinding(
                evidence_id=str(row["evidence_id"]),
                semantic_score=round(semantic, 6),
                lexical_coverage=round(segment_coverage, 6),
                numeric_conflict=numeric_conflict,
                polarity_conflict=polarity_conflict,
                integrity_failed=integrity_failed,
                literal_quote_match=literal_quote_match,
                reasons=reasons,
            )
        )

    # Evidence that failed the integrity check can neither support nor
    # contradict a claim: its stored text is no longer the extracted text.
    trusted = [finding for finding in findings if not finding.integrity_failed]
    tampered = [finding for finding in findings if finding.integrity_failed]
    non_conflicting = [
        finding
        for finding in trusted
        if not finding.numeric_conflict and not finding.polarity_conflict
    ]
    conflicting = [
        finding
        for finding in trusted
        if finding.numeric_conflict or finding.polarity_conflict
    ]
    best_support = max((finding.semantic_score for finding in non_conflicting), default=0.0)
    best_conflict = max((finding.semantic_score for finding in conflicting), default=0.0)
    reasons: list[str] = []

    if tampered:
        reasons.append(
            "Evidência com integridade não confirmada foi excluída da avaliação."
        )

    if not trusted:
        status = SupportStatus.UNSUPPORTED
        confidence = 0.0
        human_review = True
        reasons.append(
            "Nenhuma evidência com integridade confirmada suporta esta afirmação."
        )
    elif conflicting and best_support >= direct_threshold:
        status = SupportStatus.PARTIAL
        confidence = max(best_support, best_conflict)
        human_review = True
        reasons.append(
            "Existem sinais mistos: evidência de suporte direto e evidência materialmente conflitante."
        )
    elif conflicting:
        status = SupportStatus.CONTRADICTED
        confidence = max(
            max(finding.lexical_coverage, finding.semantic_score)
            for finding in conflicting
        )
        human_review = True
        reasons.append("Existe evidência relevante com conflito material.")
    elif best_support >= direct_threshold:
        status = SupportStatus.DIRECT
        confidence = best_support
        # Support that only just clears the threshold still needs review. The
        # margin is capped so a perfect match never requires review just
        # because the configured threshold is close to 1.
        human_review = best_support < min(direct_threshold + 0.05, 1.0)
        reasons.append("A melhor evidência ultrapassa o limiar de suporte direto.")
    elif best_support >= partial_threshold:
        status = SupportStatus.PARTIAL
        confidence = best_support
        human_review = True
        reasons.append("A evidência apenas ultrapassa o limiar de suporte parcial.")
    else:
        status = SupportStatus.UNSUPPORTED
        confidence = 1.0 - best_support
        human_review = True
        reasons.append("Nenhuma evidência ultrapassa o limiar mínimo de suporte.")

    return SemanticValidationResult(
        claim=normalized_claim,
        recommended_support_status=status,
        confidence=round(_bounded_similarity(confidence), 6),
        requires_human_review=human_review,
        evidence_findings=findings,
        unresolved_evidence_ids=[],
        embedding_model=model_name,
        direct_threshold=direct_threshold,
        partial_threshold=partial_threshold,
        reasons=reasons,
    )
