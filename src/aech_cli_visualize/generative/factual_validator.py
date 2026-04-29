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


FACTUAL_VALIDATION_INSTRUCTIONS = """You are a cooperative visual fact-checker for business analytics images.

Compare the generated image against the supplied typed analysis and condensed
evidence JSON. The evidence JSON is the source of truth. The typed analysis is
helpful guidance, not the full universe of allowed facts.

Mark the image unacceptable only when a visible business fact is false,
contradictory, misleading, or cannot be grounded in the evidence. A number,
category, label, chart, table row, callout, or conclusion is grounded when it is
present in the evidence JSON or is mechanically derivable from evidence values
using clear grouping, counting, filtering, or arithmetic.

Do not fail the image merely because it features extra factual data that was not
preselected by the analysis, adds a factual KPI/table/chart section, or chooses a
different factual emphasis than the recommended layout. Layout guidance and
recommended visuals are not exclusion rules unless the user explicitly states a
factual constraint such as "only include these values".

Fail the image when:
- It contains a visible number, category, label, row, or conclusion not present
  in or mechanically derivable from the evidence.
- It changes signs, units, currencies, dates, ordering, rankings, comparisons,
  or totals in a way that misstates the data.
- It combines currencies or units without clear labeling.
- It presents a derived value whose calculation is unsupported or incorrect.

Do not use formatting quality as a factual rejection. If text is too small,
overlapped, or garbled, mention it as an advisory readability issue when useful,
but keep is_acceptable=true unless a false or contradictory business fact is
visible. Business trust is the priority: reject bad facts, not imperfect design.
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
            "Return is_acceptable=false only for false, unsupported, contradictory, misleading, or incorrectly derived visible business facts.",
            "Extra facts are acceptable when present in or mechanically derivable from the evidence JSON.",
            "Formatting/readability issues may be listed as advisory issues, but they should not make the image unacceptable by themselves.",
            "Return correction_instructions that can be appended to a regeneration prompt.",
        ])
