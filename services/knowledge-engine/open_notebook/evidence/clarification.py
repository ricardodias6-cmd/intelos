"""Deterministic clarification rules for the auditable answer pipeline."""

from __future__ import annotations

import re
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

_AMBIGUOUS_MARKERS = (
    "isso",
    "isto",
    "aquilo",
    "esse",
    "essa",
    "este",
    "esta",
    "ele",
    "ela",
    "eles",
    "elas",
    "qual deles",
    "qual delas",
    "e depois",
    "e então",
    "como assim",
)


class ClarificationDecision(BaseModel):
    """A deterministic decision that asks for scope before factual retrieval."""

    model_config = ConfigDict(extra="forbid")

    required: bool = False
    reason: str | None = Field(default=None, max_length=200)
    question: str | None = Field(default=None, max_length=10000)

    @classmethod
    def not_required(cls) -> "ClarificationDecision":
        """Return the neutral decision for a question that can be retrieved."""

        return cls()

    @classmethod
    def required_for_deictic_reference(cls) -> "ClarificationDecision":
        """Return the stable clarification contract for an unresolved reference."""

        return cls(
            required=True,
            reason="deictic_reference_without_context",
            question="A que documento, entidade ou procedimento se refere?",
        )


def requires_clarification(
    question: str,
    *,
    conversation_context: Sequence[str] = (),
) -> ClarificationDecision:
    """Detect only explicitly ambiguous follow-ups without prior context."""

    if conversation_context:
        return ClarificationDecision.not_required()

    normalized = " ".join(question.casefold().split())
    if any(
        re.search(rf"(?<![A-Za-z0-9_]){re.escape(marker)}(?![A-Za-z0-9_])", normalized)
        for marker in _AMBIGUOUS_MARKERS
    ):
        return ClarificationDecision.required_for_deictic_reference()

    return ClarificationDecision.not_required()
