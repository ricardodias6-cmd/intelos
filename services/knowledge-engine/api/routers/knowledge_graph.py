from fastapi import APIRouter, HTTPException

from open_notebook.exceptions import InvalidInputError
from open_notebook.knowledge_graph.models import (
    KnowledgeGraphExtraction,
    KnowledgeGraphPersistenceResult,
)
from open_notebook.knowledge_graph.persistence import persist_knowledge_graph

router = APIRouter()


@router.post(
    "/knowledge-graph/ingest",
    response_model=KnowledgeGraphPersistenceResult,
)
async def ingest_knowledge_graph(
    request: KnowledgeGraphExtraction,
) -> KnowledgeGraphPersistenceResult:
    try:
        return await persist_knowledge_graph(request)
    except InvalidInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
