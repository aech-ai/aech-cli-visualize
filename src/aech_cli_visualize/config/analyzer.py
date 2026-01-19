"""Data analysis for dashboard recommendations."""

import os
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.settings import ModelSettings

from ..model_utils import parse_model_string, get_model_settings
from .fingerprint import analyze_field, compute_schema_fingerprint
from .models import (
    AnalysisQuestion,
    AnalysisResult,
    DataPattern,
    FieldAnalysis,
    WidgetSuggestion,
)
from .repository import ConfigRepository


ANALYSIS_INSTRUCTIONS = """You are a data visualization expert analyzing datasets to recommend dashboard designs.

Given a dataset with field information:
1. Identify patterns in the data (time series, comparisons, distributions, relationships)
2. Suggest appropriate visualizations for each pattern
3. Generate clarifying questions to refine the dashboard design

Guidelines for widget suggestions:
- KPI cards: For key numeric metrics (totals, averages, percentages)
- Line charts: For temporal trends
- Bar charts: For categorical comparisons
- Pie charts: For part-to-whole relationships (max 5-7 categories)
- Scatter plots: For relationships between two numeric variables
- Gauges: For progress toward a target
- Tables: For detailed data that doesn't fit visualizations

Guidelines for questions:
- Ask about the dashboard's purpose (executive summary, operational monitoring, analysis)
- Ask which metrics are most important
- Ask about the target audience
- Keep questions concise and actionable

Provide practical, actionable recommendations for business dashboards."""


class DataAnalyzer:
    """Analyzes data to generate dashboard recommendations."""

    def __init__(self, model: str | None = None, use_llm: bool = True):
        """Initialize the analyzer.

        Args:
            model: LLM model identifier (e.g., "openai:gpt-4o")
            use_llm: Whether to use LLM for analysis (False = rule-based only)
        """
        self.use_llm = use_llm
        model_string = model or os.environ.get("AECH_LLM_WORKER_MODEL", "anthropic:claude-sonnet-4-20250514")
        self.model, _ = parse_model_string(model_string)
        self._model_settings = get_model_settings(model_string)

        if use_llm:
            self.agent: Agent[None, AnalysisResult] = Agent(
                self.model,
                output_type=AnalysisResult,
                instructions=ANALYSIS_INSTRUCTIONS,
                model_settings=self._model_settings,
            )

        self.repository = ConfigRepository()

    def analyze(
        self, data: dict[str, Any], include_questions: bool = True
    ) -> AnalysisResult:
        """Analyze data and return recommendations.

        Args:
            data: Dictionary with field names as keys and lists of values
            include_questions: Whether to include clarifying questions

        Returns:
            AnalysisResult with field analysis, patterns, suggestions, and questions
        """
        # First, do rule-based analysis
        fields = self._analyze_fields(data)
        patterns = self._detect_patterns(fields, data)
        suggestions = self._suggest_widgets(fields, patterns)
        fingerprint = compute_schema_fingerprint(data)

        # Find matching configs
        matching = self.repository.find_by_fingerprint(fingerprint)
        matching_names = [c.name for c in matching]

        if self.use_llm and include_questions:
            # Use LLM to enhance analysis and generate questions
            return self._llm_analyze(fields, patterns, suggestions, fingerprint, matching_names, data)

        # Rule-based questions
        questions = self._generate_questions(fields, patterns) if include_questions else []

        return AnalysisResult(
            fields=fields,
            patterns=patterns,
            suggested_widgets=suggestions,
            questions=questions,
            schema_fingerprint=fingerprint,
            matching_configs=matching_names,
        )

    def _analyze_fields(self, data: dict[str, Any]) -> list[FieldAnalysis]:
        """Analyze each field in the data."""
        fields = []
        for name, values in data.items():
            if isinstance(values, list):
                analysis = analyze_field(name, values)
                fields.append(FieldAnalysis.model_validate(analysis))
        return fields

    def _detect_patterns(
        self, fields: list[FieldAnalysis], data: dict[str, Any]
    ) -> list[DataPattern]:
        """Detect patterns in the data based on field types."""
        patterns = []

        # Find temporal fields
        temporal_fields = [f for f in fields if f.type == "temporal"]
        numeric_fields = [f for f in fields if f.type == "numeric"]
        categorical_fields = [f for f in fields if f.type == "categorical"]

        # Time series pattern
        if temporal_fields and numeric_fields:
            patterns.append(
                DataPattern(
                    pattern_type="time_series",
                    confidence=0.9,
                    involved_fields=[temporal_fields[0].name] + [f.name for f in numeric_fields],
                    description=f"Temporal trend: {', '.join(f.name for f in numeric_fields)} over {temporal_fields[0].name}",
                )
            )

        # Categorical comparison pattern
        if categorical_fields and numeric_fields:
            patterns.append(
                DataPattern(
                    pattern_type="comparison",
                    confidence=0.85,
                    involved_fields=[categorical_fields[0].name] + [f.name for f in numeric_fields[:2]],
                    description=f"Compare {', '.join(f.name for f in numeric_fields[:2])} across {categorical_fields[0].name}",
                )
            )

        # Distribution pattern (single numeric)
        if len(numeric_fields) >= 1:
            for nf in numeric_fields:
                if nf.cardinality > 10:  # Enough variation
                    patterns.append(
                        DataPattern(
                            pattern_type="distribution",
                            confidence=0.7,
                            involved_fields=[nf.name],
                            description=f"Distribution of {nf.name}",
                        )
                    )

        # Relationship pattern (multiple numerics)
        if len(numeric_fields) >= 2:
            patterns.append(
                DataPattern(
                    pattern_type="relationship",
                    confidence=0.6,
                    involved_fields=[f.name for f in numeric_fields[:2]],
                    description=f"Relationship between {numeric_fields[0].name} and {numeric_fields[1].name}",
                )
            )

        return patterns

    def _suggest_widgets(
        self, fields: list[FieldAnalysis], patterns: list[DataPattern]
    ) -> list[WidgetSuggestion]:
        """Suggest widgets based on field analysis and patterns."""
        suggestions = []
        priority = 1

        # KPI cards for key numeric metrics
        numeric_fields = [f for f in fields if f.type == "numeric"]
        for nf in numeric_fields[:3]:  # Top 3 as KPIs
            suggestions.append(
                WidgetSuggestion(
                    widget_type="kpi",
                    data_fields=[nf.name],
                    reason=f"Highlight {nf.name} as a key metric",
                    priority=priority,
                )
            )
            priority += 1

        # Charts based on patterns
        for pattern in patterns:
            if pattern.pattern_type == "time_series":
                suggestions.append(
                    WidgetSuggestion(
                        widget_type="chart",
                        chart_type="line",
                        data_fields=pattern.involved_fields,
                        reason=pattern.description,
                        priority=priority,
                    )
                )
                priority += 1
            elif pattern.pattern_type == "comparison":
                suggestions.append(
                    WidgetSuggestion(
                        widget_type="chart",
                        chart_type="bar",
                        data_fields=pattern.involved_fields,
                        reason=pattern.description,
                        priority=priority,
                    )
                )
                priority += 1
            elif pattern.pattern_type == "relationship":
                suggestions.append(
                    WidgetSuggestion(
                        widget_type="chart",
                        chart_type="scatter",
                        data_fields=pattern.involved_fields,
                        reason=pattern.description,
                        priority=priority,
                    )
                )
                priority += 1

        return suggestions

    def _generate_questions(
        self, fields: list[FieldAnalysis], patterns: list[DataPattern]
    ) -> list[AnalysisQuestion]:
        """Generate clarifying questions based on analysis."""
        questions = []

        # Purpose question
        questions.append(
            AnalysisQuestion(
                id="purpose",
                question="What is the primary purpose of this dashboard?",
                options=[
                    "Executive summary (high-level KPIs)",
                    "Operational monitoring (real-time status)",
                    "Detailed analysis (exploration)",
                ],
                required=True,
            )
        )

        # Key metrics question
        numeric_fields = [f for f in fields if f.type == "numeric"]
        if len(numeric_fields) > 1:
            questions.append(
                AnalysisQuestion(
                    id="key_metrics",
                    question="Which metrics should be most prominent?",
                    suggestions=[f.name for f in numeric_fields],
                    multi_select=True,
                )
            )

        # Time range question if temporal data
        temporal_fields = [f for f in fields if f.type == "temporal"]
        if temporal_fields:
            questions.append(
                AnalysisQuestion(
                    id="time_range",
                    question="What time range should the dashboard focus on?",
                    options=[
                        "All available data",
                        "Most recent period",
                        "Specific comparison periods",
                    ],
                )
            )

        return questions

    def _llm_analyze(
        self,
        fields: list[FieldAnalysis],
        patterns: list[DataPattern],
        suggestions: list[WidgetSuggestion],
        fingerprint: str,
        matching_names: list[str],
        data: dict[str, Any],
    ) -> AnalysisResult:
        """Use LLM to enhance analysis and generate better questions."""
        # Build prompt with pre-analyzed data
        prompt = self._build_llm_prompt(fields, patterns, data)

        try:
            result = self.agent.run_sync(prompt)
            # Merge LLM results with our computed fingerprint and matching configs
            output = result.output
            output.schema_fingerprint = fingerprint
            output.matching_configs = matching_names
            return output
        except Exception:
            # Fallback to rule-based if LLM fails
            return AnalysisResult(
                fields=fields,
                patterns=patterns,
                suggested_widgets=suggestions,
                questions=self._generate_questions(fields, patterns),
                schema_fingerprint=fingerprint,
                matching_configs=matching_names,
            )

    def _build_llm_prompt(
        self,
        fields: list[FieldAnalysis],
        patterns: list[DataPattern],
        data: dict[str, Any],
    ) -> str:
        """Build prompt for LLM analysis."""
        field_summary = "\n".join(
            f"- {f.name}: {f.type}, {f.cardinality} unique values, sample: {f.sample_values[:3]}"
            for f in fields
        )

        pattern_summary = "\n".join(
            f"- {p.pattern_type}: {p.description} (confidence: {p.confidence:.0%})"
            for p in patterns
        )

        return f"""Analyze this dataset for dashboard visualization recommendations.

## Fields
{field_summary}

## Detected Patterns
{pattern_summary}

## Task
1. Confirm or refine the detected patterns
2. Suggest specific widget types and configurations
3. Generate 2-4 clarifying questions to refine the dashboard design

Focus on practical business dashboard recommendations."""
