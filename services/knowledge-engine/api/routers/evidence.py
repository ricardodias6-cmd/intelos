from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from open_notebook.evidence.retrieval import (
    EvidenceIndexResult,
    EvidenceSearchFilters,
    EvidenceSearchResponse,
    index_evidence_blocks,
    retrieve_evidence,
)
from open_notebook.exceptions import InvalidInputError

router = APIRouter()


class EvidenceSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=100)
    minimum_score: float = Field(default=0.05, ge=0, le=1)
    source_id: str | None = None
    version_hash: str | None = None
    pdf_page: int | None = Field(default=None, ge=1)
    section: str | None = None
    block_types: list[str] = Field(default_factory=list)
    allow_legacy_fallback: bool = True


class EvidenceIndexRequest(BaseModel):
    source_id: str | None = None
    document_version_id: str | None = None
    force: bool = False


@router.post("/evidence/search", response_model=EvidenceSearchResponse)
async def search_evidence(request: EvidenceSearchRequest) -> EvidenceSearchResponse:
    try:
        return await retrieve_evidence(
            query=request.query,
            limit=request.limit,
            minimum_score=request.minimum_score,
            filters=EvidenceSearchFilters(
                source_id=request.source_id,
                version_hash=request.version_hash,
                pdf_page=request.pdf_page,
                section=request.section,
                block_types=request.block_types,
            ),
            allow_legacy_fallback=request.allow_legacy_fallback,
        )
    except InvalidInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/evidence/index", response_model=EvidenceIndexResult)
async def index_evidence(request: EvidenceIndexRequest) -> EvidenceIndexResult:
    try:
        return await index_evidence_blocks(
            source_id=request.source_id,
            document_version_id=request.document_version_id,
            force=request.force,
        )
    except InvalidInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
