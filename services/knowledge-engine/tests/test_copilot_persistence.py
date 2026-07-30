from __future__ import annotations

from typing import Any

import pytest

from open_notebook.copilot import persistence


@pytest.mark.asyncio
async def test_load_context_returns_bounded_history_in_chronological_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_query(
        query: str,
        variables: dict[str, Any],
    ) -> list[dict[str, Any]]:
        assert "LIMIT $limit" in query
        assert variables["limit"] == 6
        return [
            {
                "conversation_id": "CONV_ONE",
                "turn_id": "TURN_TWO",
                "question": "Segunda pergunta",
                "answer": "Segunda resposta",
                "claim_summaries": ["direct: segunda claim"],
                "response_mode": "concise",
                "status": "answered",
                "created_at": "2026-07-30T12:01:00Z",
            },
            {
                "conversation_id": "CONV_ONE",
                "turn_id": "TURN_ONE",
                "question": "Primeira pergunta",
                "answer": "Primeira resposta",
                "claim_summaries": ["direct: primeira claim"],
                "response_mode": "concise",
                "status": "answered",
                "created_at": "2026-07-30T12:00:00Z",
            },
        ]

    monkeypatch.setattr(persistence, "repo_query", fake_query)

    turns = await persistence.load_recent_conversation_context("CONV_ONE")

    assert [turn.turn_id for turn in turns] == ["TURN_ONE", "TURN_TWO"]
    assert "Evidence text" not in turns[0].render_for_context()
