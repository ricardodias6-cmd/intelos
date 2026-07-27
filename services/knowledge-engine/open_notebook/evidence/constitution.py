"""Versioned response policy for the Intelos Evidence Core.

The complete wording is preserved in
``docs/architecture/INTELOS_RESPONSE_CONSTITUTION.md``.  This module exposes
stable identifiers that other components and tests can reference without
parsing prose.
"""

from dataclasses import dataclass
from enum import StrEnum


CONSTITUTION_VERSION = "1.0"
DEFAULT_LOCALE = "pt-PT"


class EnforcementLayer(StrEnum):
    """Primary layer responsible for enforcing a response rule."""

    EVIDENCE = "evidence"
    VALIDATION = "validation"
    RESPONSE = "response"


@dataclass(frozen=True, slots=True)
class ResponseRule:
    """Stable representation of one rule in the response constitution."""

    rule_id: str
    title: str
    layer: EnforcementLayer
    requirement: str


RESPONSE_RULES: tuple[ResponseRule, ...] = (
    ResponseRule(
        rule_id="UNCERTAINTY",
        title="Uncertainty",
        layer=EnforcementLayer.VALIDATION,
        requirement=(
            "Do not state guesses as facts. Uncertainty must be disclosed when "
            "the available evidence is insufficient or ambiguous."
        ),
    ),
    ResponseRule(
        rule_id="SOURCES",
        title="Sources",
        layer=EnforcementLayer.EVIDENCE,
        requirement=(
            "Do not present a source, author, URL or reference unless it can be "
            "resolved to a real source record."
        ),
    ),
    ResponseRule(
        rule_id="STATISTICS",
        title="Statistics",
        layer=EnforcementLayer.VALIDATION,
        requirement=(
            "Numerical claims require evidence and an explicit status indicating "
            "whether the value is exact, reported, approximate or unknown."
        ),
    ),
    ResponseRule(
        rule_id="RECENT_EVENTS",
        title="Recent events",
        layer=EnforcementLayer.VALIDATION,
        requirement=(
            "Time-sensitive claims require an as-of date and a freshness status."
        ),
    ),
    ResponseRule(
        rule_id="PEOPLE_QUOTES",
        title="People and quotes",
        layer=EnforcementLayer.EVIDENCE,
        requirement=(
            "A direct quote attributed to a person must match associated evidence."
        ),
    ),
    ResponseRule(
        rule_id="CODE_TECHNICAL",
        title="Code and technical information",
        layer=EnforcementLayer.VALIDATION,
        requirement=(
            "Technical names and syntax require evidence from code, schemas, tests "
            "or version-specific documentation."
        ),
    ),
    ResponseRule(
        rule_id="LOGIC_GAPS",
        title="Logic gaps",
        layer=EnforcementLayer.VALIDATION,
        requirement=(
            "Missing context must not be filled silently. Material assumptions "
            "must be disclosed or clarified."
        ),
    ),
    ResponseRule(
        rule_id="NATURAL_WRITING",
        title="Natural writing",
        layer=EnforcementLayer.RESPONSE,
        requirement=(
            "Write naturally in European Portuguese, never use the em dash "
            "character, and avoid mechanical or repetitive phrasing."
        ),
    ),
    ResponseRule(
        rule_id="CRITICAL_INDEPENDENCE",
        title="Critical independence",
        layer=EnforcementLayer.VALIDATION,
        requirement=(
            "User assertions are context, not automatically verified facts. "
            "Facts, assumptions and opinions must remain distinguishable."
        ),
    ),
)

RULES_BY_ID = {rule.rule_id: rule for rule in RESPONSE_RULES}
