"""Hybrid retrieval over immutable evidence blocks.

The service combines semantic similarity, lexical relevance and structural
filters. By default it searches only the newest document version for each
source, preventing evidence from obsolete versions from being mixed silently
with the current corpus.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.notebook import vector_search as legacy_vector_search
from open_notebook.exceptions import InvalidInputError
from open_notebook.utils.embedding import generate_embedding, generate_embeddings

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_NUMBER_RE = re.compile(r"(?<!\w)\d+(?:[.,]\d+)?(?!\w)")
_TEMPORAL_EXPRESSION_RE = re.compile(
    r"(?<!\w)\d+(?:[.,]\d+)?\s*"
    r"(?:segundos?|minutos?|horas?|dias?|semanas?|meses?|anos?)(?!\w)",
    re.IGNORECASE,
)
_QUANTITY_QUERY_CUES = {
    "quanto",
    "quantos",
    "quantas",
    "prazo",
    "duração",
    "duracao",
    "quando",
    "data",
    "hora",
    "horas",
    "dias",
    "meses",
    "anos",
}


class EvidenceSearchFilters(BaseModel):
    source_id: str | None = None
    version_hash: str | None = None
    pdf_page: int | None = Field(default=None, ge=1)
    section: str | None = None
    block_types: list[str] = Field(default_factory=list)


class EvidenceSearchHit(BaseModel):
    evidence_id: str
    source_id: str
    document_title: str | None = None
    document_version_id: str
    document_version_hash: str
    text: str
    pdf_page: int | None = None
    printed_page: str | None = None
    section_path: list[str] = Field(default_factory=list)
    block_type: str
    bbox: dict[str, Any] | None = None
    score: float
    semantic_score: float = 0.0
    lexical_score: float = 0.0
    structural_score: float = 0.0


class EvidenceSearchResponse(BaseModel):
    query: str
    hits: list[EvidenceSearchHit]
    selected_versions: dict[str, str]
    used_legacy_fallback: bool = False
    legacy_results: list[dict[str, Any]] = Field(default_factory=list)


class EvidenceIndexResult(BaseModel):
    considered: int
    embedded: int
    skipped: int
    embedding_model: str


def _tokens(text: str) -> list[str]:
    return [token.casefold() for token in _TOKEN_RE.findall(text)]


def _ngrams(tokens: Sequence[str], size: int) -> set[tuple[str, ...]]:
    if size < 1 or len(tokens) < size:
        return set()
    return {tuple(tokens[index : index + size]) for index in range(len(tokens) - size + 1)}


def _answer_specificity_score(query_tokens: Sequence[str], text: str) -> float:
    """Reward concrete numeric or temporal answers when the query asks for one."""

    if not set(query_tokens) & _QUANTITY_QUERY_CUES:
        return 0.0
    if _TEMPORAL_EXPRESSION_RE.search(text):
        return 1.0
    if _NUMBER_RE.search(text):
        return 0.6
    return 0.0


def lexical_score(query: str, text: str) -> float:
    """Return a deterministic lexical score in the 0..1 interval.

    Besides token overlap, the score rewards exact phrases, shared multi-word
    expressions and concrete numeric or temporal answers to quantity-oriented
    questions. This prevents a generic topical match from outranking the block
    that contains the actual deadline, amount or duration being requested.
    """

    query_tokens = _tokens(query)
    text_tokens = _tokens(text)
    if not query_tokens or not text_tokens:
        return 0.0

    query_set = set(query_tokens)
    text_set = set(text_tokens)
    common = query_set & text_set
    coverage = len(common) / len(query_set)
    precision = len(common) / len(text_set)
    exact_phrase = 1.0 if query.casefold().strip() in text.casefold() else 0.0

    query_bigrams = _ngrams(query_tokens, 2)
    text_bigrams = _ngrams(text_tokens, 2)
    bigram_overlap = (
        len(query_bigrams & text_bigrams) / len(query_bigrams) if query_bigrams else 0.0
    )
    specificity = _answer_specificity_score(query_tokens, text)

    score = (
        (coverage * 0.45)
        + (precision * 0.10)
        + (bigram_overlap * 0.15)
        + (exact_phrase * 0.15)
        + (specificity * 0.20)
    )
    return min(1.0, score)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    raw = dot / (left_norm * right_norm)
    return max(0.0, min(1.0, raw))


def _effective_text(row: dict[str, Any]) -> str:
    return str(row.get("verified_text") or row.get("raw_text") or "").strip()


def _effective_text_hash(row: dict[str, Any]) -> str:
    return hashlib.sha256(_effective_text(row).encode("utf-8")).hexdigest()


async def _resolve_versions(filters: EvidenceSearchFilters) -> tuple[list[str], dict[str, str]]:
    clauses: list[str] = []
    variables: dict[str, Any] = {}
    if filters.source_id:
        clauses.append("source = $source")
        variables["source"] = ensure_record_id(filters.source_id)
    if filters.version_hash:
        clauses.append("version_hash = $version_hash")
        variables["version_hash"] = filters.version_hash.lower()

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = await repo_query(
        f"SELECT * FROM document_version{where} ORDER BY created DESC",
        variables,
    )

    selected: dict[str, dict[str, Any]] = {}
    for row in rows:
        source_id = str(row["source"])
        if filters.version_hash:
            selected[source_id] = row
        elif source_id not in selected:
            selected[source_id] = row

    version_ids = [str(row["id"]) for row in selected.values()]
    version_hashes = {
        source_id: str(row["version_hash"]) for source_id, row in selected.items()
    }
    return version_ids, version_hashes


async def _load_candidates(
    version_ids: list[str], filters: EvidenceSearchFilters
) -> list[dict[str, Any]]:
    if not version_ids:
        return []

    clauses = ["document_version IN $versions"]
    variables: dict[str, Any] = {
        "versions": [ensure_record_id(version_id) for version_id in version_ids]
    }
    if filters.pdf_page is not None:
        clauses.append("pdf_page = $pdf_page")
        variables["pdf_page"] = filters.pdf_page
    if filters.block_types:
        clauses.append("block_type IN $block_types")
        variables["block_types"] = filters.block_types

    rows = await repo_query(
        "SELECT * FROM evidence_block WHERE " + " AND ".join(clauses),
        variables,
    )
    if filters.section:
        needle = filters.section.casefold()
        rows = [
            row
            for row in rows
            if any(needle in str(part).casefold() for part in row.get("section_path") or [])
        ]
    return rows


async def _source_titles(source_ids: set[str]) -> dict[str, str]:
    if not source_ids:
        return {}
    rows = await repo_query(
        "SELECT id, title FROM source WHERE id IN $sources",
        {"sources": [ensure_record_id(source_id) for source_id in source_ids]},
    )
    return {
        str(row["id"]): str(row["title"])
        for row in rows
        if row.get("title") is not None
    }


async def retrieve_evidence(
    *,
    query: str,
    limit: int = 10,
    filters: EvidenceSearchFilters | None = None,
    minimum_score: float = 0.05,
    allow_legacy_fallback: bool = True,
) -> EvidenceSearchResponse:
    if not query.strip():
        raise InvalidInputError("Evidence search query cannot be empty")
    if limit < 1 or limit > 100:
        raise InvalidInputError("Evidence search limit must be between 1 and 100")

    active_filters = filters or EvidenceSearchFilters()
    version_ids, selected_versions = await _resolve_versions(active_filters)
    rows = await _load_candidates(version_ids, active_filters)

    query_embedding: list[float] | None = None
    if any(row.get("embedding") for row in rows):
        try:
            query_embedding = await generate_embedding(query)
        except Exception as exc:
            logger.warning("Semantic evidence search unavailable: {}", exc)

    version_hash_by_id: dict[str, str] = {}
    for source_id, version_hash in selected_versions.items():
        for row in rows:
            if str(row.get("source")) == source_id:
                version_hash_by_id[str(row["document_version"])] = version_hash

    titles = await _source_titles({str(row["source"]) for row in rows})
    hits: list[EvidenceSearchHit] = []
    for row in rows:
        text = _effective_text(row)
        lexical = lexical_score(query, text)
        semantic = (
            cosine_similarity(query_embedding, row.get("embedding") or [])
            if query_embedding
            else 0.0
        )
        structural = 0.0
        if active_filters.pdf_page is not None:
            structural += 0.35
        if active_filters.section:
            structural += 0.35
        if active_filters.block_types:
            structural += 0.30
        structural = min(1.0, structural)

        if query_embedding is None:
            score = (lexical * 0.90) + (structural * 0.10)
        else:
            score = (semantic * 0.55) + (lexical * 0.40) + (structural * 0.05)
        if score < minimum_score:
            continue

        source_id = str(row["source"])
        version_id = str(row["document_version"])
        hits.append(
            EvidenceSearchHit(
                evidence_id=str(row["evidence_id"]),
                source_id=source_id,
                document_title=titles.get(source_id),
                document_version_id=version_id,
                document_version_hash=version_hash_by_id[version_id],
                text=text,
                pdf_page=row.get("pdf_page"),
                printed_page=row.get("printed_page"),
                section_path=row.get("section_path") or [],
                block_type=str(row.get("block_type") or "text"),
                bbox=row.get("bbox"),
                score=round(score, 6),
                semantic_score=round(semantic, 6),
                lexical_score=round(lexical, 6),
                structural_score=round(structural, 6),
            )
        )

    hits.sort(key=lambda hit: (-hit.score, hit.evidence_id))
    hits = hits[:limit]
    if hits or not allow_legacy_fallback:
        return EvidenceSearchResponse(
            query=query,
            hits=hits,
            selected_versions=selected_versions,
        )

    legacy_results: list[dict[str, Any]] = []
    try:
        legacy_results = await legacy_vector_search(
            keyword=query,
            results=limit,
            source=True,
            note=False,
            minimum_score=minimum_score,
        )
    except Exception as exc:
        logger.warning("Legacy source_embedding fallback unavailable: {}", exc)

    return EvidenceSearchResponse(
        query=query,
        hits=[],
        selected_versions=selected_versions,
        used_legacy_fallback=bool(legacy_results),
        legacy_results=legacy_results,
    )


async def index_evidence_blocks(
    *,
    source_id: str | None = None,
    document_version_id: str | None = None,
    force: bool = False,
) -> EvidenceIndexResult:
    from open_notebook.ai.models import model_manager

    embedding_model = await model_manager.get_embedding_model()
    if not embedding_model:
        raise InvalidInputError("Evidence indexing requires an embedding model")

    clauses: list[str] = []
    variables: dict[str, Any] = {}
    if source_id:
        clauses.append("source = $source")
        variables["source"] = ensure_record_id(source_id)
    if document_version_id:
        clauses.append("document_version = $version")
        variables["version"] = ensure_record_id(document_version_id)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = await repo_query(f"SELECT * FROM evidence_block{where}", variables)

    pending = [
        row
        for row in rows
        if force
        or not row.get("embedding")
        or row.get("embedded_text_hash") != _effective_text_hash(row)
    ]
    model_name = str(getattr(embedding_model, "model_name", "unknown"))
    if not pending:
        return EvidenceIndexResult(
            considered=len(rows),
            embedded=0,
            skipped=len(rows),
            embedding_model=model_name,
        )

    embeddings = await generate_embeddings([_effective_text(row) for row in pending])
    for row, embedding in zip(pending, embeddings, strict=True):
        await repo_query(
            "UPDATE $id MERGE $data",
            {
                "id": ensure_record_id(str(row["id"])),
                "data": {
                    "embedding": embedding,
                    "embedding_model": model_name,
                    "embedded_text_hash": _effective_text_hash(row),
                },
            },
        )

    return EvidenceIndexResult(
        considered=len(rows),
        embedded=len(pending),
        skipped=len(rows) - len(pending),
        embedding_model=model_name,
    )