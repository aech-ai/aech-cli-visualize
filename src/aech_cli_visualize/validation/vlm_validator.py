"""VLM-based validation for dashboard renders using pydantic-ai."""

import os
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, BinaryContent
from pydantic_ai.settings import ModelSettings

from .models import ValidationDeps, ValidationResult


VALIDATION_INSTRUCTIONS = """You are a visual QA expert evaluating dashboard layouts for presentation quality.

Analyze the rendered dashboard image and check for these visual issues:

1. **OVERLAP**: Charts, KPIs, gauges, or tables overlapping each other. Elements should have clear boundaries.

2. **TRUNCATION**: Text cut off, labels hidden, values not fully visible. All text should be readable.

3. **ALIGNMENT**: Elements not aligned to grid, uneven spacing between widgets. Layout should look organized.

4. **SPACING**: Elements too close together (cramped) or too far apart (wasted space). Balance is key.

5. **READABILITY**: Text too small to read, poor contrast, cluttered appearance. Users should easily scan the dashboard.

6. **SIZING**: Charts too small to interpret data, KPIs disproportionate to their importance. Size should match content.

For each issue detected:
- Identify which widget(s) are affected by their index (0-indexed based on the spec)
- Rate severity: "critical" (unusable), "major" (significantly impairs readability), "minor" (noticeable but acceptable)
- Suggest a specific fix

Only flag issues that would be noticeable to a business user viewing this dashboard for decision-making.
Pixel-perfect alignment is not required - focus on practical usability.

A dashboard is "acceptable" if it has no critical issues and at most minor issues.
"""


class VLMValidator:
    """Validates dashboard renders using a Vision Language Model."""

    def __init__(self, model: str | None = None):
        """Initialize the validator.

        Args:
            model: Model identifier in format "provider:model" (e.g., "openai:gpt-4o").
                   Defaults to AECH_VLM_MODEL environment variable or "openai:gpt-4o".
        """
        self.model = model or os.environ.get("AECH_VLM_MODEL", "openai:gpt-5-mini")
        self.agent: Agent[ValidationDeps, ValidationResult] = Agent(
            self.model,
            deps_type=ValidationDeps,
            output_type=ValidationResult,
            instructions=VALIDATION_INSTRUCTIONS,
        )

    def _summarize_spec(self, spec: dict[str, Any]) -> str:
        """Create a human-readable summary of the dashboard spec.

        Args:
            spec: Dashboard specification

        Returns:
            Summary string for VLM context
        """
        layout = spec.get("layout", {})
        widgets = spec.get("widgets", [])

        lines = [
            f"Title: {spec.get('title', '(none)')}",
            f"Grid: {layout.get('columns', 12)} columns x {layout.get('rows', 2)} rows",
            f"Widgets: {len(widgets)} total",
            "",
            "Widget positions (index: type @ row,col spanning rowspan x colspan):",
        ]

        for i, widget in enumerate(widgets):
            pos = widget.get("position", {})
            widget_type = widget.get("type", "unknown")
            row = pos.get("row", 0)
            col = pos.get("col", 0)
            rowspan = pos.get("rowspan", 1)
            colspan = pos.get("colspan", 1)
            config = widget.get("config", {})
            title = config.get("title") or config.get("label") or ""

            lines.append(
                f"  [{i}] {widget_type} @ ({row},{col}) spanning {rowspan}x{colspan}"
                + (f' - "{title}"' if title else "")
            )

        return "\n".join(lines)

    def _build_prompt(self, spec: dict[str, Any]) -> str:
        """Build the user prompt for VLM evaluation.

        Args:
            spec: Dashboard specification

        Returns:
            User prompt string
        """
        summary = self._summarize_spec(spec)
        return f"""Evaluate this dashboard render for visual quality issues.

## Dashboard Specification
{summary}

## Task
Analyze the attached image and determine:
1. Is this dashboard acceptable for presentation to business stakeholders?
2. What visual issues exist (if any)?
3. For each issue, which widgets are affected and how should it be fixed?

Provide your assessment as a structured validation result."""

    def evaluate(self, image_path: Path, spec: dict[str, Any]) -> ValidationResult:
        """Evaluate a rendered dashboard image.

        Args:
            image_path: Path to the rendered dashboard PNG
            spec: Dashboard specification used for the render

        Returns:
            ValidationResult with assessment and any issues found
        """
        # Load image using BinaryContent.from_path()
        image = BinaryContent.from_path(image_path)

        # Build dependencies
        deps = ValidationDeps(
            spec=spec,
            widget_summary=self._summarize_spec(spec),
        )

        # Run the agent with image and prompt
        result = self.agent.run_sync(
            [self._build_prompt(spec), image],
            deps=deps,
            model_settings=ModelSettings(temperature=0.0),
        )

        return result.output
