"""Prompt construction for GPT Image visualizations."""

from __future__ import annotations

import json
from typing import Any

from .models import VisualizationAnalysis


MAX_PROMPT_DATA_CHARS = 18_000


def serialize_data_for_prompt(data: dict[str, Any], max_chars: int = MAX_PROMPT_DATA_CHARS) -> str:
    """Serialize data for the image prompt and fail if it is too large."""
    serialized = json.dumps(data, indent=2, sort_keys=True, default=str)
    if len(serialized) > max_chars:
        raise ValueError(
            "Data is too large for a single image-generation prompt "
            f"({len(serialized)} chars > {max_chars}). Pre-aggregate the dataset "
            "or pass a higher max_data_chars value explicitly."
        )
    return serialized


def build_image_prompt(
    *,
    data: dict[str, Any],
    analysis: VisualizationAnalysis,
    title: str | None,
    instructions: str | None,
    output_format: str,
    template_image: str | None = None,
    max_data_chars: int = MAX_PROMPT_DATA_CHARS,
) -> str:
    """Build the final GPT Image prompt from typed analysis and source data."""
    serialized_data = serialize_data_for_prompt(data, max_chars=max_data_chars)
    metrics = [
        f"- {metric.label}: {metric.value}"
        + (f" ({metric.context})" if metric.context else "")
        for metric in analysis.key_metrics
    ]
    insights = [
        f"- [{insight.severity}] {insight.label}: {insight.explanation}"
        + (f" Evidence: {'; '.join(insight.evidence)}" if insight.evidence else "")
        for insight in analysis.insights
    ]
    visuals = [
        f"- {visual.kind}: {visual.title}. Purpose: {visual.purpose}. "
        f"Fields: {', '.join(visual.fields) if visual.fields else 'not specified'}"
        for visual in analysis.recommended_visuals
    ]
    warnings = [f"- {warning}" for warning in analysis.warnings]

    template_guidance = (
        "Use the provided template/reference image only for visual consistency: "
        "layout rhythm, typography feel, color discipline, and overall polish. "
        "Replace its content with the data and analysis below."
        if template_image
        else "No template/reference image is provided; create a complete original visualization."
    )

    return "\n".join([
        "Use case: productivity-visual",
        "Asset type: executive analytical data visualization",
        f"Primary request: Create one polished {output_format.upper()} image where analysis and visualization are integrated.",
        f"Title: {title or analysis.headline}",
        f"Analysis headline: {analysis.headline}",
        f"Narrative: {analysis.narrative}",
        f"User instructions: {instructions or 'Use the typed analysis to choose the clearest visual story.'}",
        f"Template guidance: {template_guidance}",
        "",
        "Key metrics to render visibly:",
        "\n".join(metrics) if metrics else "- None specified",
        "",
        "Insights to integrate into chart annotations, callouts, or side notes:",
        "\n".join(insights) if insights else "- None specified",
        "",
        "Recommended visual elements:",
        "\n".join(visuals) if visuals else "- Choose the smallest clear set of visuals from the analysis.",
        "",
        f"Layout guidance: {analysis.layout_guidance}",
        "",
        "Known cautions:",
        "\n".join(warnings) if warnings else "- None",
        "",
        "Source data to visualize. Do not invent values outside this data:",
        serialized_data,
        "",
        "Rendering constraints:",
        "- The image must contain both the visualized data and the analytical interpretation.",
        "- Prefer a single coherent dashboard/poster over separate disconnected charts.",
        "- Use exact labels and numeric values from the source data and typed analysis wherever visible.",
        "- Keep text concise and legible; prioritize the headline, key metrics, and most important insight callouts.",
        "- If there is too much data for every value to be legible, summarize visually and call out the important values explicitly.",
        "- Do not include watermarks, fake UI chrome, or placeholder lorem ipsum.",
    ])
