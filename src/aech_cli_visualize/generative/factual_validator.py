"""Factual validation for GPT Image visualization outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, BinaryContent

from ..model_utils import build_pydantic_ai_model, get_model_settings
from ..observability import observed_llm_role
from .models import FactualValidationResult, VisualizationAnalysis
from .prompting import MAX_PROMPT_DATA_CHARS, serialize_data_for_prompt


FACTUAL_VALIDATION_INSTRUCTIONS = """You are a strict visual fact-checker for business analytics images.

Compare the generated image against the allowed evidence. The image is allowed
to restyle or rearrange the visual design, but every visible number, category,
label, chart, table row, callout, and conclusion must be grounded in the supplied
analysis and condensed evidence JSON.

Fail the image when:
- It contains a visible number, category, label, or conclusion not present in the evidence.
- It adds a chart, table, or visual section that is not requested by the analysis.
- It surfaces a raw evidence value in a KPI, summary, or rollup that was not
  selected by the analysis, even if that value exists in the evidence JSON.
- It omits a required headline metric or makes a required value unreadable.
- It changes signs, units, dates, ordering, rankings, or comparisons.

Do not penalize harmless visual styling differences. If text is too small to
verify, treat the affected value as unreadable rather than guessing. Business
trust is the priority: when a factual issue is visible, mark the image unacceptable.
"""


class FactualImageValidator:
    """Validate generated visualization images against the exact prompt evidence."""

    def __init__(self, *, model: str, api_key: str | None = None):
        self.model_name = model
        self.agent: Agent[None, FactualValidationResult] = Agent(
            build_pydantic_ai_model(model, api_key=api_key),
            output_type=FactualValidationResult,
            instructions=FACTUAL_VALIDATION_INSTRUCTIONS,
            model_settings=get_model_settings(model),
        )

    def evaluate(
        self,
        *,
        image_path: Path,
        analysis: VisualizationAnalysis,
        prompt_data: dict[str, Any],
        title: str | None,
        instructions: str | None,
        max_data_chars: int = MAX_PROMPT_DATA_CHARS,
    ) -> FactualValidationResult:
        """Evaluate a generated image against the exact evidence package."""
        image = BinaryContent.from_path(image_path)
        prompt = self._build_prompt(
            analysis=analysis,
            prompt_data=prompt_data,
            title=title,
            instructions=instructions,
            max_data_chars=max_data_chars,
        )
        with observed_llm_role("evaluator"):
            result = self.agent.run_sync([prompt, image])
        return result.output

    def _build_prompt(
        self,
        *,
        analysis: VisualizationAnalysis,
        prompt_data: dict[str, Any],
        title: str | None,
        instructions: str | None,
        max_data_chars: int,
    ) -> str:
        allowed_data = serialize_data_for_prompt(prompt_data, max_chars=max_data_chars)
        allowed_analysis = json.dumps(analysis.model_dump(), separators=(",", ":"), sort_keys=True)
        return "\n".join([
            "Fact-check the attached generated visualization image.",
            f"Title: {title or analysis.headline}",
            f"User instructions: {instructions or 'Analyze the dataset for a clear visual.'}",
            "",
            "Allowed typed analysis JSON:",
            allowed_analysis,
            "",
            "Allowed condensed evidence JSON:",
            allowed_data,
            "",
            "Return is_acceptable=false if any visible business fact is fabricated, unsupported, contradictory, missing, or unreadable.",
            "Return correction_instructions that can be appended to a regeneration prompt.",
        ])
