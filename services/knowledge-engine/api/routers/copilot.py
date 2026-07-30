"""HTTP boundary for the Intelos Copilot."""

from fastapi import APIRouter, HTTPException

from open_notebook.copilot.models import (
    CopilotChatRequest,
    CopilotChatResponse,
    new_conversation_id,
    new_turn_id,
)
from open_notebook.evidence.auditable_answer import build_auditable_answer
from open_notebook.exceptions import InvalidInputError

router = APIRouter()


@router.post("/copilot/chat", response_model=CopilotChatResponse)
async def chat_with_copilot(
    request: CopilotChatRequest,
) -> CopilotChatResponse:
    """Answer one question through the auditable evidence pipeline."""

    conversation_id = request.conversation_id or new_conversation_id()
    turn_id = new_turn_id()

    try:
        answer = await build_auditable_answer(
            request.to_auditable_answer_request()
        )
    except InvalidInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        return CopilotChatResponse.from_auditable_answer(
            request,
            answer,
            conversation_id=conversation_id,
            turn_id=turn_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
