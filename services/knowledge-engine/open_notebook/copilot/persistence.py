"""Persistence for bounded, non-probative Copilot conversation context."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from open_notebook.copilot.models import CopilotChatResponse
from open_notebook.database.repository import repo_query, repo_upsert


class ConversationTurnContext(BaseModel):
    """A prior turn summary safe to use for query disambiguation only."""

    conversation_id: str = Field(min_length=3, max_length=128)
    turn_id: str = Field(min_length=3, max_length=128)
    question: str = Field(min_length=1, max_length=10000)
    answer: str = Field(min_length=1, max_length=50000)
    claim_summaries: list[str] = Field(default_factory=list, max_length=200)
    response_mode: str = Field(min_length=1, max_length=20)
    status: str = Field(min_length=1, max_length=40)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def render_for_context(self) -> str:
        """Render history as untrusted disambiguation data, never as evidence."""

        claims = "\n".join(f"- {summary}" for summary in self.claim_summaries)
        return (
            f"Previous user question: {self.question}\n"
            f"Previous Copilot response: {self.answer}\n"
            f"Previous claim summaries:\n{claims or '- none'}"
        )


async def load_recent_conversation_context(
    conversation_id: str,
    *,
    limit: int = 6,
) -> list[ConversationTurnContext]:
    """Load a bounded history without loading citation or evidence text."""

    if limit < 1 or limit > 12:
        raise ValueError("conversation context limit must be between 1 and 12")

    rows = await repo_query(
        "SELECT conversation_id, turn_id, question, answer, claim_summaries, "
        "response_mode, status, created_at "
        "FROM copilot_conversation_turn "
        "WHERE conversation_id = $conversation_id "
        "ORDER BY created_at DESC LIMIT $limit",
        {"conversation_id": conversation_id, "limit": limit},
    )
    turns = [
        ConversationTurnContext.model_validate(row)
        for row in rows
    ]
    return list(reversed(turns))


async def persist_conversation_turn(
    response: CopilotChatResponse,
    *,
    question: str,
) -> None:
    """Upsert a turn summary with no raw Evidence Block content."""

    claim_summaries = [
        (
            f"{claim.support_status.value}: {claim.text}"
            + (
                f" ({claim.qualification})"
                if claim.qualification
                else ""
            )
        )
        for claim in response.claims
    ]
    now = datetime.now(timezone.utc)
    await repo_upsert(
        "copilot_conversation_turn",
        f"copilot_conversation_turn:{response.turn_id}",
        {
            "conversation_id": response.conversation_id,
            "turn_id": response.turn_id,
            "question": question,
            "answer": response.answer,
            "claim_summaries": claim_summaries,
            "response_mode": response.response_mode.value,
            "status": response.status.value,
            "answer_id": response.answer_id,
            "audit_report_id": response.audit_report_id,
            "created_at": now,
            "updated_at": now,
        },
    )
