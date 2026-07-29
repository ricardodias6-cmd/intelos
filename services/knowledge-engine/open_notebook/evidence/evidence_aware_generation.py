"""Evidence-aware regeneration policy for the phase 5 answer pipeline."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, Field


class RejectedCandidateClaim(BaseModel):
    """A claim rejected before presentation and eligible for regeneration."""

    text: str = Field(min_length=1, max_length=10000)
    evidence_ids: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1, max_length=2000)


class EvidenceAwareGenerationPolicy(BaseModel):
    """Bounded policy for regenerating claims rejected by validation."""

    max_attempts: int = Field(default=1, ge=0, le=2)

    def feedback(self, rejected: Sequence[RejectedCandidateClaim], attempt: int) -> str:
        if not rejected:
            return ""
        entries = []
        for item in rejected:
            ids = ", ".join(item.evidence_ids) or "nenhum"
            entries.append(
                "\n".join(
                    [
                        f"- Claim rejeitada: {item.text}",
                        f"  Evidence IDs apresentados: {ids}",
                        f"  Motivo: {item.reason}",
                    ]
                )
            )
        return (
            f"Regeneração {attempt} de {self.max_attempts}. "
            "Substitui apenas as claims rejeitadas abaixo. "
            "Mantém as claims válidas, se existirem, e devolve o answer completo "
            "com claims atómicas. Cada substituição deve usar apenas Evidence IDs "
            "dos blocos fornecidos; se não houver suporte, omite a claim.\n\n"
            + "\n\n".join(entries)
        )
