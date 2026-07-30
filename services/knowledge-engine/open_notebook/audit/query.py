"""Contracts for bounded AuditReport queries."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from open_notebook.audit.models import AuditFreshnessStatus


class AuditReportQuery(BaseModel):
    """Bounded, deterministic filters for audit report history."""

    answer_id: str | None = Field(default=None, min_length=3, max_length=128)
    conversation_id: str | None = Field(default=None, min_length=3, max_length=128)
    turn_id: str | None = Field(default=None, min_length=3, max_length=128)
    freshness_status: AuditFreshnessStatus | None = None
    generated_from: datetime | None = None
    generated_to: datetime | None = None
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0, le=950)

    @model_validator(mode="after")
    def validate_date_range(self) -> "AuditReportQuery":
        if (
            self.generated_from is not None
            and self.generated_to is not None
            and self.generated_from > self.generated_to
        ):
            raise ValueError("generated_from must be before or equal to generated_to")
        return self


class AuditReportPage(BaseModel):
    """A bounded page of reports with explicit pagination state."""

    items: list = Field(default_factory=list, max_length=50)
    limit: int = Field(ge=1, le=50)
    offset: int = Field(ge=0, le=950)
    has_more: bool = False
    next_offset: int | None = Field(default=None, ge=0, le=950)
    scan_truncated: bool = False
