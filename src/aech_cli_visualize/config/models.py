"""Pydantic models for config repository."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ConfigMetadata(BaseModel):
    """Metadata for a saved dashboard configuration."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(description="Human-readable name for the config")
    description: str | None = Field(
        default=None, description="Description of what this dashboard shows"
    )
    tags: list[str] = Field(
        default_factory=list, description="Tags for categorization"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: datetime | None = Field(default=None)
    usage_count: int = Field(default=0)
    schema_fingerprint: str = Field(
        default="", description="Hash of data schema for auto-matching"
    )
    spec_path: str = Field(description="Relative path to spec file")
    preview_path: str | None = Field(
        default=None, description="Relative path to preview image"
    )


class ConfigIndex(BaseModel):
    """Index of all saved configurations."""

    version: int = Field(default=1)
    configs: list[ConfigMetadata] = Field(default_factory=list)


class FieldAnalysis(BaseModel):
    """Analysis of a single data field."""

    name: str = Field(description="Field name")
    type: str = Field(description="Inferred type: numeric, categorical, temporal, text")
    cardinality: int = Field(description="Number of unique values")
    sample_values: list[Any] = Field(
        default_factory=list, description="Sample values from the field"
    )
    summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Type-specific summary (min/max/mean for numeric, etc.)",
    )


class DataPattern(BaseModel):
    """A detected pattern in the data."""

    pattern_type: str = Field(
        description="Pattern type: time_series, comparison, distribution, relationship"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in detection")
    involved_fields: list[str] = Field(description="Fields involved in this pattern")
    description: str = Field(description="Human-readable description")


class WidgetSuggestion(BaseModel):
    """A suggested widget for the dashboard."""

    widget_type: str = Field(description="Widget type: chart, kpi, table, gauge")
    chart_type: str | None = Field(
        default=None, description="Chart type if widget_type is chart"
    )
    data_fields: list[str] = Field(description="Fields to use for this widget")
    reason: str = Field(description="Why this visualization is recommended")
    priority: int = Field(
        ge=1, le=10, description="Priority (1 = highest, 10 = lowest)"
    )


class AnalysisQuestion(BaseModel):
    """A clarifying question for the user."""

    id: str = Field(description="Unique question ID")
    question: str = Field(description="The question to ask")
    options: list[str] | None = Field(
        default=None, description="Predefined options if applicable"
    )
    suggestions: list[str] | None = Field(
        default=None, description="Suggested answers based on data"
    )
    required: bool = Field(default=False)
    multi_select: bool = Field(default=False)


class AnalysisResult(BaseModel):
    """Complete analysis result for dashboard recommendation."""

    fields: list[FieldAnalysis] = Field(description="Analysis of each field")
    patterns: list[DataPattern] = Field(description="Detected data patterns")
    suggested_widgets: list[WidgetSuggestion] = Field(
        description="Recommended visualizations"
    )
    questions: list[AnalysisQuestion] = Field(
        default_factory=list, description="Clarifying questions for user"
    )
    schema_fingerprint: str = Field(description="Hash for config matching")
    matching_configs: list[str] = Field(
        default_factory=list, description="Names of configs matching this schema"
    )
