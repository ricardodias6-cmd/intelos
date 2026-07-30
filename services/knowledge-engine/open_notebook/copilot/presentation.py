"""Safe presentation projections for validated Copilot answers."""

from __future__ import annotations

from open_notebook.evidence.auditable_models import (
    AnswerClaim,
    AuditableAnswer,
    AuditableAnswerStatus,
)


def _claim_line(claim: AnswerClaim, *, include_evidence: bool) -> str:
    line = f"- {claim.text}"
    if claim.qualification:
        line += f" ({claim.qualification})"
    if include_evidence:
        evidence = ", ".join(claim.evidence_ids) or "none"
        line += f" [status={claim.support_status.value}; evidence={evidence}]"
    return line


def render_copilot_answer(answer: AuditableAnswer, mode: str) -> str:
    """Render validated content without changing its epistemic fields."""

    if answer.status == AuditableAnswerStatus.CLARIFICATION_REQUIRED:
        return answer.answer

    if mode == "concise":
        return answer.answer

    claims = "\n".join(
        _claim_line(claim, include_evidence=mode == "audit")
        for claim in answer.claims
    )
    if mode == "detailed":
        if not claims:
            return answer.answer
        return f"{answer.answer}\n\nClaims validadas:\n{claims}"

    audit = answer.audit
    selected = ", ".join(audit.selected_evidence_ids) or "none"
    stages = ", ".join(
        f"{stage}={duration}ms"
        for stage, duration in audit.stage_durations_ms.items()
    ) or "none"
    diagnostics = [
        "Percurso auditável:",
        f"- Estado: {answer.status.value}",
        f"- Evidence IDs selecionados: {selected}",
        f"- Confiança global: {answer.overall_confidence:.2f}",
        f"- Revisão humana: {'sim' if answer.requires_human_review else 'não'}",
        f"- Etapas: {stages}",
    ]
    if claims:
        diagnostics.append(f"Claims validadas:\n{claims}")
    return f"{answer.answer}\n\n" + "\n".join(diagnostics)
