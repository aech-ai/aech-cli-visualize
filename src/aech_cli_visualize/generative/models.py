"""Typed models for generative data visualizations."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class KeyMetric(BaseModel):
    """A metric that should be visible in the generated image."""

    label: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    context: str | None = None


class DataInsight(BaseModel):
    """A data-backed observation for the visual narrative."""

    label: str = Field(..., min_length=1)
    explanation: str = Field(..., min_length=1)
    severity: Literal["info", "positive", "warning", "critical"] = "info"
    evidence: list[str] = Field(default_factory=list)


class VisualElement(BaseModel):
    """A visual element the image should include."""

    kind: Literal[
        "line_chart",
        "bar_chart",
        "scatter_plot",
        "heatmap",
        "kpi_card",
        "table",
        "timeline",
        "callout",
        "flow",
        "other",
    ]
    title: str = Field(..., min_length=1)
    fields: list[str] = Field(default_factory=list)
    purpose: str = Field(..., min_length=1)


class VisualizationAnalysis(BaseModel):
    """Typed analysis used to brief GPT Image."""

    model_config = ConfigDict(extra="forbid")

    headline: str = Field(..., min_length=1)
    narrative: str = Field(..., min_length=1)
    key_metrics: list[KeyMetric] = Field(default_factory=list)
    insights: list[DataInsight] = Field(default_factory=list)
    recommended_visuals: list[VisualElement] = Field(default_factory=list)
    layout_guidance: str = Field(..., min_length=1)
    warnings: list[str] = Field(default_factory=list)


class VisualizationPayload(BaseModel):
    """Normalized CLI payload for a generative visualization request."""

    model_config = ConfigDict(extra="forbid")

    data: dict[str, Any]
    title: str | None = None
    instructions: str | None = None
    analysis: VisualizationAnalysis | None = None


class FactualValidationIssue(BaseModel):
    """A visible image element that is not grounded in the supplied evidence."""

    kind: Literal[
        "fabricated_value",
        "unsupported_chart",
        "unsupported_label",
        "missing_required_value",
        "unreadable_value",
        "other",
    ]
    description: str = Field(..., min_length=1)
    evidence: str = Field(..., min_length=1)
    severity: Literal["critical", "major", "minor"] = "major"


class FactualValidationResult(BaseModel):
    """Post-generation factual QA result for a generated visualization image."""

    model_config = ConfigDict(extra="forbid")

    is_acceptable: bool
    summary: str = Field(..., min_length=1)
    issues: list[FactualValidationIssue] = Field(default_factory=list)
    correction_instructions: str = Field(
        ...,
        min_length=1,
        description="Specific corrective instruction to feed back into image regeneration.",
    )
