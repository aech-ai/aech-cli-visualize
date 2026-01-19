"""Pydantic models for VLM validation of dashboard renders."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class LayoutIssue(BaseModel):
    """A specific visual issue detected in the dashboard render."""

    issue_type: Literal[
        "overlap",
        "truncation",
        "alignment",
        "spacing",
        "readability",
        "sizing",
    ] = Field(description="Category of the visual issue")

    description: str = Field(
        description="Human-readable description of what's wrong"
    )

    affected_widgets: list[int] = Field(
        default_factory=list,
        description="Indices of widgets affected by this issue (0-indexed)",
    )

    severity: Literal["critical", "major", "minor"] = Field(
        description="How severe the issue is for presentation quality"
    )

    suggested_fix: str = Field(
        description="Recommendation for how to fix this issue"
    )


class ValidationResult(BaseModel):
    """VLM evaluation result for a dashboard render."""

    is_acceptable: bool = Field(
        description="Whether the dashboard is acceptable for presentation"
    )

    issues: list[LayoutIssue] = Field(
        default_factory=list,
        description="List of detected visual issues",
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence level in the assessment (0.0 to 1.0)",
    )

    reasoning: str = Field(
        description="Explanation of the overall assessment"
    )


class LayoutCorrection(BaseModel):
    """A concrete correction to apply to the dashboard spec."""

    action: Literal[
        "increase_rows",
        "increase_columns",
        "adjust_span",
        "adjust_padding",
        "reduce_title_length",
    ] = Field(description="Type of correction to apply")

    target: str = Field(
        description="Target path in spec: 'layout' or 'widgets[i]'"
    )

    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the correction action",
    )


class RenderResult(BaseModel):
    """Result of a validated dashboard render."""

    path: Path = Field(description="Path to the final rendered image")

    iterations: int = Field(
        ge=1,
        description="Number of render iterations performed",
    )

    validation_history: list[ValidationResult] | None = Field(
        default=None,
        description="Validation results from each iteration (None if VLM disabled)",
    )

    final_spec: dict[str, Any] = Field(
        description="Final dashboard spec after corrections"
    )

    corrections_applied: list[LayoutCorrection] = Field(
        default_factory=list,
        description="All corrections applied across iterations",
    )

    warning: str | None = Field(
        default=None,
        description="Warning message if validation didn't fully succeed",
    )

    vlm_error: str | None = Field(
        default=None,
        description="Error message if VLM validation failed",
    )

    class Config:
        arbitrary_types_allowed = True


@dataclass
class ValidationDeps:
    """Dependencies injected into the VLM validator agent."""

    spec: dict[str, Any]
    widget_summary: str
