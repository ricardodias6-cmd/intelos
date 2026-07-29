"""Bounded semantic validation between one atomic claim and evidence blocks."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, Field

from open_notebook.database.repository import repo_query
from open_notebook.evidence.models import SupportStatus, VerificationStatus
from open_notebook.evidence.retrieval import cosine_similarity
from open_notebook.exceptions import InvalidInputError
from open_notebook.utils.embedding import generate_embeddings

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_NUMBER_RE = re.compile(r"(?<!\w)[+-]?\d+(?:[.,]\d+)?(?!\w)")
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
    reasons: list[str] = Field(default_factory=list)


class SemanticValidationResult(BaseModel):
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


def _has_negation(text: str) -> bool:
    return bool(set(_tokens(text)) & _NEGATION_TOKENS)


def _effective_text(row: dict[str, Any]) -> str:
    return str(row.get("verified_text") or row.get("raw_text") or "").strip()


def _record_identifier(value: Any) -> str:
    return str(value)


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
    resolved = [by_id[identifier] for identifier in unique_ids if identifier in by_id]

    if not resolved:
        return SemanticValidationResult(
            claim=normalized_claim,
            recommended_support_status=SupportStatus.UNSUPPORTED,
            confidence=1.0,
            requires_human_review=True,
            evidence_findings=[],
            unresolved_evidence_ids=unresolved,
            embedding_model="unavailable",
            direct_threshold=direct_threshold,
            partial_threshold=partial_threshold,
            reasons=["Nenhum Evidence ID foi resolvido no registo."],
        )

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
    mixed_sources = [source for source, versions in versions_by_source.items() if len(versions) > 1]
    if mixed_sources:
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
        semantic = cosine_similarity(claim_embedding, embedding)
        lexical = _lexical_coverage(normalized_claim, text)
        evidence_numbers = _numbers(text)
        numeric_conflict = bool(
            claim_numbers and evidence_numbers and claim_numbers.isdisjoint(evidence_numbers)
        )
        polarity_conflict = claim_negation != _has_negation(text) and lexical >= 0.45
        reasons: list[str] = []
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
                lexical_coverage=round(lexical, 6),
                numeric_conflict=numeric_conflict,
                polarity_conflict=polarity_conflict,
                reasons=reasons,
            )
        )

    best_score = max(finding.semantic_score for finding in findings)
    conflict_findings = [
        finding
        for finding in findings
        if finding.numeric_conflict or finding.polarity_conflict
    ]
    reasons: list[str] = []
    if conflict_findings:
        status = SupportStatus.CONTRADICTED
        confidence = max(
            max(finding.lexical_coverage, finding.semantic_score)
            for finding in conflict_findings
        )
        human_review = True
        reasons.append("Existe pelo menos um conflito material nos blocos avaliados.")
    elif best_score >= direct_threshold:
        status = SupportStatus.DIRECT
        confidence = best_score
        human_review = bool(unresolved or best_score < direct_threshold + 0.05)
        reasons.append("A melhor evidência ultrapassa o limiar de suporte direto.")
    elif best_score >= partial_threshold:
        status = SupportStatus.PARTIAL
        confidence = best_score
        human_review = True
        reasons.append("A evidência apenas ultrapassa o limiar de suporte parcial.")
    else:
        status = SupportStatus.UNSUPPORTED
        confidence = 1.0 - best_score
        human_review = True
        reasons.append("Nenhuma evidência ultrapassa o limiar mínimo de suporte.")

    if unresolved:
        reasons.append("Existem Evidence IDs não resolvidos.")

    return SemanticValidationResult(
        claim=normalized_claim,
        recommended_support_status=status,
        confidence=round(max(0.0, min(1.0, confidence)), 6),
        requires_human_review=human_review,
        evidence_findings=findings,
        unresolved_evidence_ids=unresolved,
        embedding_model=model_name,
        direct_threshold=direct_threshold,
        partial_threshold=partial_threshold,
        reasons=reasons,
    )
