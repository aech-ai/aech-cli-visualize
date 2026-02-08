"""Data analysis for dashboard recommendations."""

import os
from collections import defaultdict
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
- Pie charts: Use sparingly and only for clear part-to-whole with <= 5 categories
- Scatter plots: For relationships between two numeric variables
- Gauges: For progress/score metrics (rate, percent, utilization, SLA)
- Tables: For detailed data that doesn't fit visualizations

Modern dashboard defaults:
- Prefer line/bar over pie for readability
- Prioritize 3-6 high-value widgets over dense layouts
- Ensure visual hierarchy: KPI row first, then trend/comparison charts
- Prefer concise titles and executive-oriented summaries

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
        normalized_data = self._normalize_data_shape(data)
        fields = self._analyze_fields(normalized_data)
        patterns = self._detect_patterns(fields, normalized_data)
        suggestions = self._suggest_widgets(fields, patterns)
        fingerprint = compute_schema_fingerprint(normalized_data)

        # Find matching configs
        matching = self.repository.find_by_fingerprint(fingerprint)
        matching_names = [c.name for c in matching]

        if self.use_llm and include_questions:
            # Use LLM to enhance analysis and generate questions
            return self._llm_analyze(
                fields,
                patterns,
                suggestions,
                fingerprint,
                matching_names,
                normalized_data,
            )

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

    def _flatten_dict(self, value: dict[str, Any], prefix: str = "") -> dict[str, Any]:
        """Flatten nested dictionaries into dot-notated keys."""
        flattened: dict[str, Any] = {}
        for key, sub_value in value.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(sub_value, dict):
                flattened.update(self._flatten_dict(sub_value, full_key))
            else:
                flattened[full_key] = sub_value
        return flattened

    def _normalize_data_shape(self, data: dict[str, Any]) -> dict[str, list[Any]]:
        """Normalize arbitrary JSON-like dicts into columnar field arrays.

        Handles:
        - scalar fields -> single-item arrays
        - nested dicts -> flattened keys
        - list[dict] records -> flattened columns
        - list[scalar] fields -> passthrough
        """
        normalized: dict[str, list[Any]] = {}

        for key, value in data.items():
            # Columnar field already in list form
            if isinstance(value, list):
                if not value:
                    normalized[key] = []
                    continue

                # Row-oriented records: convert list[dict] to columns
                if all(isinstance(item, dict) for item in value):
                    flattened_rows = [self._flatten_dict(item) for item in value]
                    column_values: dict[str, list[Any]] = defaultdict(list)

                    # Keep column lengths consistent by collecting keys in stable order.
                    all_keys: list[str] = []
                    seen_keys: set[str] = set()
                    for row in flattened_rows:
                        for row_key in row.keys():
                            if row_key not in seen_keys:
                                seen_keys.add(row_key)
                                all_keys.append(row_key)

                    for row in flattened_rows:
                        for flat_key in all_keys:
                            column_values[f"{key}.{flat_key}"].append(row.get(flat_key))

                    normalized.update(column_values)
                else:
                    normalized[key] = value
                continue

            # Nested object: flatten into single-item columns
            if isinstance(value, dict):
                flattened = self._flatten_dict(value, key)
                for flat_key, flat_value in flattened.items():
                    normalized[flat_key] = [flat_value]
                continue

            # Scalar field
            normalized[key] = [value]

        return normalized

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
        text_fields = [f for f in fields if f.type == "text"]
        varying_numeric_fields = [f for f in numeric_fields if f.cardinality > 1]
        varying_temporal_fields = [f for f in temporal_fields if f.cardinality > 1]
        varying_categorical_fields = [f for f in categorical_fields if f.cardinality > 1]
        varying_text_fields = [f for f in text_fields if 1 < f.cardinality <= 24]

        def _field_len(field_name: str) -> int:
            values = data.get(field_name, [])
            if isinstance(values, list):
                return len(values)
            return 0

        def _looks_temporal_label(values: list[Any]) -> bool:
            month_tokens = {
                "jan", "january", "feb", "february", "mar", "march",
                "apr", "april", "may", "jun", "june", "jul", "july",
                "aug", "august", "sep", "sept", "september", "oct",
                "october", "nov", "november", "dec", "december",
                "q1", "q2", "q3", "q4",
            }
            normalized = [
                str(v).strip().lower()
                for v in values
                if v is not None and str(v).strip()
            ]
            if not normalized:
                return False
            matches = sum(1 for value in normalized if value in month_tokens)
            return matches / len(normalized) >= 0.7

        # Time series pattern
        if varying_temporal_fields and varying_numeric_fields:
            for temporal_field in varying_temporal_fields:
                for numeric_field in varying_numeric_fields:
                    temporal_len = _field_len(temporal_field.name)
                    numeric_len = _field_len(numeric_field.name)
                    if temporal_len > 1 and temporal_len == numeric_len:
                        patterns.append(
                            DataPattern(
                                pattern_type="time_series",
                                confidence=0.9,
                                involved_fields=[temporal_field.name, numeric_field.name],
                                description=f"Temporal trend: {numeric_field.name} over {temporal_field.name}",
                            )
                        )
                        break
                if patterns and patterns[-1].pattern_type == "time_series":
                    break
        else:
            # Fallback: month/quarter labels often land as plain text.
            for text_field in varying_text_fields:
                text_values = data.get(text_field.name, [])
                if not isinstance(text_values, list) or not _looks_temporal_label(text_values):
                    continue
                for numeric_field in varying_numeric_fields:
                    text_len = _field_len(text_field.name)
                    numeric_len = _field_len(numeric_field.name)
                    if text_len > 1 and text_len == numeric_len:
                        patterns.append(
                            DataPattern(
                                pattern_type="time_series",
                                confidence=0.78,
                                involved_fields=[text_field.name, numeric_field.name],
                                description=f"Temporal-like trend: {numeric_field.name} over {text_field.name}",
                            )
                        )
                        break
                if patterns and patterns[-1].pattern_type == "time_series":
                    break

        # Categorical comparison pattern
        if varying_categorical_fields and varying_numeric_fields:
            for categorical_field in varying_categorical_fields:
                for numeric_field in varying_numeric_fields:
                    categorical_len = _field_len(categorical_field.name)
                    numeric_len = _field_len(numeric_field.name)
                    if categorical_len > 1 and categorical_len == numeric_len:
                        patterns.append(
                            DataPattern(
                                pattern_type="comparison",
                                confidence=0.85,
                                involved_fields=[categorical_field.name, numeric_field.name],
                                description=f"Compare {numeric_field.name} across {categorical_field.name}",
                            )
                        )
                        break
                if patterns and patterns[-1].pattern_type == "comparison":
                    break
        else:
            # Fallback: discrete text fields can still be effective category axes.
            for text_field in varying_text_fields:
                for numeric_field in varying_numeric_fields:
                    text_len = _field_len(text_field.name)
                    numeric_len = _field_len(numeric_field.name)
                    if text_len > 1 and text_len == numeric_len:
                        patterns.append(
                            DataPattern(
                                pattern_type="comparison",
                                confidence=0.72,
                                involved_fields=[text_field.name, numeric_field.name],
                                description=f"Compare {numeric_field.name} across {text_field.name}",
                            )
                        )
                        break
                if patterns and patterns[-1].pattern_type == "comparison":
                    break

        # Distribution pattern (single numeric)
        if varying_numeric_fields:
            for nf in varying_numeric_fields:
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
        if len(varying_numeric_fields) >= 2:
            for i, left in enumerate(varying_numeric_fields):
                for right in varying_numeric_fields[i + 1:]:
                    if _field_len(left.name) > 3 and _field_len(left.name) == _field_len(right.name):
                        patterns.append(
                            DataPattern(
                                pattern_type="relationship",
                                confidence=0.6,
                                involved_fields=[left.name, right.name],
                                description=f"Relationship between {left.name} and {right.name}",
                            )
                        )
                        return patterns

        return patterns

    def _suggest_widgets(
        self, fields: list[FieldAnalysis], patterns: list[DataPattern]
    ) -> list[WidgetSuggestion]:
        """Suggest widgets based on field analysis and patterns."""
        suggestions = []
        priority = 1

        # KPI cards for key numeric metrics
        numeric_fields = [f for f in fields if f.type == "numeric"]
        categorical_fields = [f for f in fields if f.type == "categorical"]
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

        # Add one gauge for percent/score/progress-like metrics
        gauge_tokens = ("rate", "ratio", "pct", "percent", "score", "utilization", "progress", "sla")
        for nf in numeric_fields:
            if any(token in nf.name.lower() for token in gauge_tokens):
                suggestions.append(
                    WidgetSuggestion(
                        widget_type="gauge",
                        data_fields=[nf.name],
                        reason=f"Gauge highlights current status for {nf.name}",
                        priority=priority,
                    )
                )
                priority += 1
                break

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
                # Scatter plots are useful but often noisy for executive dashboards.
                # Suggest only when fields have enough variation.
                if len(pattern.involved_fields) >= 2:
                    left = next((f for f in numeric_fields if f.name == pattern.involved_fields[0]), None)
                    right = next((f for f in numeric_fields if f.name == pattern.involved_fields[1]), None)
                    if left and right and left.cardinality > 10 and right.cardinality > 10:
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

        # Add table when category cardinality is high (detail view fallback)
        high_cardinality_category = next((f for f in categorical_fields if f.cardinality > 10), None)
        if high_cardinality_category and numeric_fields:
            suggestions.append(
                WidgetSuggestion(
                    widget_type="table",
                    data_fields=[high_cardinality_category.name, numeric_fields[0].name],
                    reason=f"Table preserves detail for high-cardinality {high_cardinality_category.name}",
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
