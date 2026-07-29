from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from open_notebook.evidence.retrieval import (
    EvidenceIndexResult,
    EvidenceSearchFilters,
    EvidenceSearchResponse,
    index_evidence_blocks,
    retrieve_evidence,
)
from open_notebook.evidence.semantic_validation import (
    SemanticValidationResult,
    validate_claim_semantics,
)
from open_notebook.exceptions import InvalidInputError

router = APIRouter()


class EvidenceSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=100)
    candidate_limit: int = Field(default=250, ge=1, le=2000)
    minimum_score: float = Field(default=0.05, ge=0, le=1)
    source_id: str | None = None
    version_hash: str | None = None
    pdf_page: int | None = Field(default=None, ge=1)
    section: str | None = None
    block_types: list[str] = Field(default_factory=list)
    allow_legacy_fallback: bool = True

    @model_validator(mode="after")
    def validate_candidate_limit(self) -> "EvidenceSearchRequest":
        if self.candidate_limit < self.limit:
            raise ValueError("candidate_limit must be greater than or equal to limit")
        return self


class EvidenceIndexRequest(BaseModel):
    source_id: str | None = None
    document_version_id: str | None = None
    force: bool = False
    batch_size: int = Field(default=64, ge=1, le=256)
    max_blocks: int = Field(default=5000, ge=1, le=100000)


class ClaimSemanticValidationRequest(BaseModel):
    claim: str = Field(min_length=1, max_length=10000)
    evidence_ids: list[str] = Field(min_length=1, max_length=50)
    direct_threshold: float = Field(default=0.82, ge=0.6, le=0.98)
    partial_threshold: float = Field(default=0.58, ge=0.5, le=0.9)

    @model_validator(mode="after")
    def validate_thresholds(self) -> "ClaimSemanticValidationRequest":
        if self.direct_threshold <= self.partial_threshold:
            raise ValueError("direct_threshold must be greater than partial_threshold")
        return self


@router.post("/evidence/search", response_model=EvidenceSearchResponse)
async def search_evidence(request: EvidenceSearchRequest) -> EvidenceSearchResponse:
    try:
        return await retrieve_evidence(
            query=request.query,
            limit=request.limit,
            candidate_limit=request.candidate_limit,
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
            batch_size=request.batch_size,
            max_blocks=request.max_blocks,
        )
    except InvalidInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/evidence/validate-claim",
    response_model=SemanticValidationResult,
)
async def validate_claim_evidence(
    request: ClaimSemanticValidationRequest,
) -> SemanticValidationResult:
    try:
        return await validate_claim_semantics(
            claim=request.claim,
            evidence_ids=request.evidence_ids,
            direct_threshold=request.direct_threshold,
            partial_threshold=request.partial_threshold,
        )
    except InvalidInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
