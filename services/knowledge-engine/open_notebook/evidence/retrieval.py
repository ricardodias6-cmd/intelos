"""Bounded hybrid retrieval over immutable evidence blocks."""

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
_DEFAULT_CANDIDATE_LIMIT = 250
_DEFAULT_BATCH_SIZE = 64
_DEFAULT_MAX_BLOCKS = 5000


class EvidenceSearchFilters(BaseModel):
    source_id: str | None = None
    source_ids: list[str] | None = None
    version_hash: str | None = None
    pdf_page: int | None = Field(default=None, ge=1)
    section: str | None = None
    block_types: list[str] = Field(default_factory=list)

    def has_any(self) -> bool:
        return bool(
            self.source_id
            or self.source_ids is not None
            or self.version_hash
            or self.pdf_page is not None
            or self.section
            or self.block_types
        )


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
    legacy_fallback_reason: str | None = None
    legacy_results: list[dict[str, Any]] = Field(default_factory=list)


class EvidenceIndexResult(BaseModel):
    considered: int
    embedded: int
    skipped: int
    failed: int = 0
    embedding_model: str
    truncated: bool = False


def _tokens(text: str) -> list[str]:
    return [token.casefold() for token in _TOKEN_RE.findall(text)]


def _ngrams(tokens: Sequence[str], size: int) -> set[tuple[str, ...]]:
    if size < 1 or len(tokens) < size:
        return set()
    return {
        tuple(tokens[index : index + size])
        for index in range(len(tokens) - size + 1)
    }


def _answer_specificity_score(query_tokens: Sequence[str], text: str) -> float:
    if not set(query_tokens) & _QUANTITY_QUERY_CUES:
        return 0.0
    if _TEMPORAL_EXPRESSION_RE.search(text):
        return 1.0
    if _NUMBER_RE.search(text):
        return 0.6
    return 0.0


def lexical_score(query: str, text: str) -> float:
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
        len(query_bigrams & text_bigrams) / len(query_bigrams)
        if query_bigrams
        else 0.0
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


async def _resolve_versions(
    filters: EvidenceSearchFilters,
) -> tuple[list[str], dict[str, str], dict[str, str]]:
    clauses: list[str] = []
    variables: dict[str, Any] = {}
    if filters.source_id:
        clauses.append("source = $source")
        variables["source"] = ensure_record_id(filters.source_id)
    if filters.source_ids is not None:
        if not filters.source_ids:
            return [], {}, {}
        clauses.append("source IN $sources")
        variables["sources"] = [
            ensure_record_id(source_id) for source_id in filters.source_ids
        ]
    if filters.version_hash:
        clauses.append("version_hash = $version_hash")
        variables["version_hash"] = filters.version_hash.lower()

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = await repo_query(
        f"SELECT * FROM document_version{where} ORDER BY created DESC, id DESC",
        variables,
    )

    selected: dict[str, dict[str, Any]] = {}
    for row in rows:
        source_id = str(row["source"])
        if source_id not in selected:
            selected[source_id] = row

    version_ids = [str(row["id"]) for row in selected.values()]
    version_hashes = {
        source_id: str(row["version_hash"])
        for source_id, row in selected.items()
    }
    version_hash_by_id = {
        str(row["id"]): str(row["version_hash"])
        for row in selected.values()
    }
    return version_ids, version_hashes, version_hash_by_id


def _candidate_clauses(
    version_ids: list[str], filters: EvidenceSearchFilters
) -> tuple[list[str], dict[str, Any]]:
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
    return clauses, variables


async def _load_candidates(
    query: str,
    version_ids: list[str],
    filters: EvidenceSearchFilters,
    candidate_limit: int,
) -> list[dict[str, Any]]:
    if not version_ids:
        return []

    clauses, variables = _candidate_clauses(version_ids, filters)
    variables["query"] = query
    variables["candidate_limit"] = candidate_limit

    rows: list[dict[str, Any]] = []
    try:
        lexical_query = (
            "SELECT *, search::score(1) + search::score(2) AS database_lexical_score "
            "FROM evidence_block WHERE "
            + " AND ".join(clauses)
            + " AND (raw_text @1@ $query OR verified_text @2@ $query) "
            "ORDER BY database_lexical_score DESC, evidence_id ASC "
            "LIMIT $candidate_limit"
        )
        rows = await repo_query(lexical_query, variables)
    except Exception as exc:
        logger.warning("Indexed lexical candidate search unavailable: {}", exc)

    seen = {str(row.get("id")) for row in rows}
    remaining = max(0, candidate_limit - len(rows))
    if remaining:
        bounded_variables = dict(variables)
        bounded_variables["remaining"] = remaining
        bounded_rows = await repo_query(
            "SELECT * FROM evidence_block WHERE "
            + " AND ".join(clauses)
            + " ORDER BY updated DESC, evidence_id ASC LIMIT $remaining",
            bounded_variables,
        )
        rows.extend(
            row for row in bounded_rows if str(row.get("id")) not in seen
        )

    if filters.section:
        needle = filters.section.casefold()
        rows = [
            row
            for row in rows
            if any(
                needle in str(part).casefold()
                for part in row.get("section_path") or []
            )
        ]
    return rows[:candidate_limit]


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


def _fallback_block_reason(
    filters: EvidenceSearchFilters,
    candidate_count: int,
    allow_legacy_fallback: bool,
) -> str | None:
    if not allow_legacy_fallback:
        return "disabled_by_request"
    if filters.has_any():
        return "disabled_by_filters"
    if candidate_count:
        return "evidence_candidates_present"
    return None


async def retrieve_evidence(
    *,
    query: str,
    limit: int = 10,
    filters: EvidenceSearchFilters | None = None,
    minimum_score: float = 0.05,
    allow_legacy_fallback: bool = True,
    candidate_limit: int = _DEFAULT_CANDIDATE_LIMIT,
) -> EvidenceSearchResponse:
    if not query.strip():
        raise InvalidInputError("Evidence search query cannot be empty")
    if limit < 1 or limit > 100:
        raise InvalidInputError("Evidence search limit must be between 1 and 100")
    if candidate_limit < limit or candidate_limit > 2000:
        raise InvalidInputError(
            "Evidence candidate limit must be between the result limit and 2000"
        )

    active_filters = filters or EvidenceSearchFilters()
    version_ids, selected_versions, version_hash_by_id = await _resolve_versions(
        active_filters
    )
    rows = await _load_candidates(
        query,
        version_ids,
        active_filters,
        candidate_limit,
    )

    query_embedding: list[float] | None = None
    if any(row.get("embedding") for row in rows):
        try:
            query_embedding = await generate_embedding(query)
        except Exception as exc:
            logger.warning("Semantic evidence search unavailable: {}", exc)

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

        score = (
            (lexical * 0.90) + (structural * 0.10)
            if query_embedding is None
            else (semantic * 0.55) + (lexical * 0.40) + (structural * 0.05)
        )
        if score < minimum_score:
            continue

        source_id = str(row["source"])
        version_id = str(row["document_version"])
        version_hash = version_hash_by_id.get(version_id)
        if version_hash is None:
            logger.error("Evidence block references an unselected version: {}", version_id)
            continue
        hits.append(
            EvidenceSearchHit(
                evidence_id=str(row["evidence_id"]),
                source_id=source_id,
                document_title=titles.get(source_id),
                document_version_id=version_id,
                document_version_hash=version_hash,
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
    fallback_reason = _fallback_block_reason(
        active_filters,
        len(rows),
        allow_legacy_fallback,
    )
    if hits or fallback_reason is not None:
        return EvidenceSearchResponse(
            query=query,
            hits=hits,
            selected_versions=selected_versions,
            legacy_fallback_reason=fallback_reason,
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
            legacy_fallback_reason="legacy_search_failed",
        )

    return EvidenceSearchResponse(
        query=query,
        hits=[],
        selected_versions=selected_versions,
        used_legacy_fallback=bool(legacy_results),
        legacy_fallback_reason="used" if legacy_results else "no_legacy_results",
        legacy_results=legacy_results,
    )


async def _mark_index_state(
    row_ids: list[str], status: str, error: str | None = None
) -> None:
    if not row_ids:
        return
    await repo_query(
        "UPDATE evidence_block SET indexing_status = $status, indexing_error = $error "
        "WHERE id IN $ids",
        {
            "ids": [ensure_record_id(row_id) for row_id in row_ids],
            "status": status,
            "error": error,
        },
    )


async def index_evidence_blocks(
    *,
    source_id: str | None = None,
    document_version_id: str | None = None,
    force: bool = False,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    max_blocks: int = _DEFAULT_MAX_BLOCKS,
) -> EvidenceIndexResult:
    from open_notebook.ai.models import model_manager

    if batch_size < 1 or batch_size > 256:
        raise InvalidInputError("Evidence indexing batch size must be between 1 and 256")
    if max_blocks < 1 or max_blocks > 100000:
        raise InvalidInputError("Evidence indexing max_blocks must be between 1 and 100000")
    if force and not source_id and not document_version_id and max_blocks > _DEFAULT_MAX_BLOCKS:
        raise InvalidInputError(
            "Unscoped force indexing cannot exceed the default safety limit"
        )

    embedding_model = await model_manager.get_embedding_model()
    if not embedding_model:
        raise InvalidInputError("Evidence indexing requires an embedding model")
    model_name = str(getattr(embedding_model, "model_name", "unknown"))

    clauses: list[str] = []
    variables: dict[str, Any] = {}
    if source_id:
        clauses.append("source = $source")
        variables["source"] = ensure_record_id(source_id)
    if document_version_id:
        clauses.append("document_version = $version")
        variables["version"] = ensure_record_id(document_version_id)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""

    considered = embedded = skipped = failed = 0
    offset = 0
    truncated = False
    while considered < max_blocks:
        page_size = min(batch_size, max_blocks - considered)
        page_variables = dict(variables)
        page_variables.update({"limit": page_size, "offset": offset})
        rows = await repo_query(
            f"SELECT * FROM evidence_block{where} ORDER BY id ASC "
            "LIMIT $limit START $offset",
            page_variables,
        )
        if not rows:
            break

        considered += len(rows)
        offset += len(rows)
        pending = [
            row
            for row in rows
            if force
            or not row.get("embedding")
            or row.get("embedded_text_hash") != _effective_text_hash(row)
            or row.get("embedding_model") != model_name
            or row.get("indexing_status") == "failed"
        ]
        skipped += len(rows) - len(pending)
        if not pending:
            continue

        row_ids = [str(row["id"]) for row in pending]
        await _mark_index_state(row_ids, "pending")
        try:
            embeddings = await generate_embeddings(
                [_effective_text(row) for row in pending]
            )
            if len(embeddings) != len(pending):
                raise RuntimeError("Embedding provider returned an unexpected batch size")
        except Exception as exc:
            failed += len(pending)
            await _mark_index_state(row_ids, "failed", str(exc)[:1000])
            logger.exception("Evidence embedding batch generation failed")
        else:
            completed_ids: list[str] = []
            for row, embedding in zip(pending, embeddings, strict=True):
                row_id = str(row["id"])
                try:
                    await repo_query(
                        "UPDATE $id MERGE $data",
                        {
                            "id": ensure_record_id(row_id),
                            "data": {
                                "embedding": embedding,
                                "embedding_model": model_name,
                                "embedded_text_hash": _effective_text_hash(row),
                                "indexing_status": "indexed",
                                "indexing_error": None,
                            },
                        },
                    )
                except Exception as exc:
                    remaining_ids = [
                        str(item["id"])
                        for item in pending
                        if str(item["id"]) not in completed_ids
                    ]
                    failed += len(remaining_ids)
                    await _mark_index_state(
                        remaining_ids,
                        "failed",
                        str(exc)[:1000],
                    )
                    logger.exception(
                        "Evidence embedding persistence failed after {} successful updates",
                        len(completed_ids),
                    )
                    break
                completed_ids.append(row_id)
                embedded += 1

        if len(rows) < page_size:
            break

    if considered == max_blocks:
        count_rows = await repo_query(
            f"SELECT count() AS total FROM evidence_block{where} GROUP ALL",
            variables,
        )
        total = int(count_rows[0].get("total", considered)) if count_rows else considered
        truncated = total > considered

    return EvidenceIndexResult(
        considered=considered,
        embedded=embedded,
        skipped=skipped,
        failed=failed,
        embedding_model=model_name,
        truncated=truncated,
    )
