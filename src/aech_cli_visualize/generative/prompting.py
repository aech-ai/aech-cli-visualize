"""Prompt construction for GPT Image visualizations."""

from __future__ import annotations

import json
from typing import Any

from .models import VisualizationAnalysis


MAX_PROMPT_DATA_CHARS = 20_000


def serialize_data_for_prompt(data: dict[str, Any], max_chars: int = MAX_PROMPT_DATA_CHARS) -> str:
    """Serialize data for the image prompt and fail if it is too large."""
    serialized = json.dumps(data, separators=(",", ":"), sort_keys=True, default=str)
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
    surface: str,
    include_header: bool,
    template_image: str | None = None,
    max_data_chars: int = MAX_PROMPT_DATA_CHARS,
) -> str:
    """Build the final GPT Image prompt from typed analysis and condensed visual evidence."""
    serialized_data = serialize_data_for_prompt(data, max_chars=max_data_chars)
    metrics = [
        f"- {metric.label}: {metric.value}"
        + (f" ({metric.context})" if metric.context else "")
        for metric in analysis.key_metrics[:5]
    ]
    insights = [
        f"- [{insight.severity}] {insight.label}: {insight.explanation}"
        + (f" Evidence: {'; '.join(insight.evidence[:2])}" if insight.evidence else "")
        for insight in analysis.insights[:4]
    ]
    visuals = [
        f"- {visual.kind}: {visual.title}. Purpose: {visual.purpose}. "
        f"Fields: {', '.join(visual.fields) if visual.fields else 'not specified'}"
        for visual in analysis.recommended_visuals[:3]
    ]
    warnings = [f"- {warning}" for warning in analysis.warnings[:3]]

    template_guidance = (
        "The provided template/reference image is the primary composition contract. "
        "Reproduce its layout rhythm, chart structure, annotation density, typography hierarchy, "
        "and color discipline as faithfully as possible. Apply the user's requested changes, "
        "then replace visible content with the data and analysis below."
        if template_image
        else "No template/reference image is provided; create a complete original visualization."
    )
    if surface == "embedded-card":
        surface_guidance = (
            "Quiet in-app analytical card; light product UI surface; restrained typography; "
            "subtle borders; muted accents; no browser chrome or page navigation."
        )
    else:
        surface_guidance = (
            "PowerPoint-ready 16:9 analytical slide with calm executive-report styling."
        )

    header_guidance = (
        "A compact title/header is allowed if it materially improves comprehension."
        if include_header
        else "No large header band, hero title, mascot, logo block, or decorative top banner."
    )

    return "\n".join([
        f"Create one polished {output_format.upper()} analytical visualization.",
        f"Surface: {surface}. {surface_guidance}",
        f"Header: {header_guidance}",
        f"Title/caption: {title or analysis.headline}",
        f"Headline: {analysis.headline}",
        f"Question: {instructions or 'Analyze the dataset for a clear visual.'}",
        f"Story: {analysis.narrative}",
        f"Template: {template_guidance}",
        "",
        "Visible metrics:",
        "\n".join(metrics) if metrics else "- None specified",
        "",
        "Callouts:",
        "\n".join(insights) if insights else "- None specified",
        "",
        "Visual elements:",
        "\n".join(visuals) if visuals else "- Choose the smallest clear set of visuals from the analysis.",
        "",
        f"Layout: {analysis.layout_guidance}",
        "Cautions:",
        "\n".join(warnings) if warnings else "- None",
        "",
        "Visibility boundary:",
        "- Render only the metric, callout, and visual sections listed above.",
        "- Do not add extra KPI strips, scorecards, summary totals, currency rollups, customer rows, or tables.",
        "- Condensed evidence is grounding material for the listed visuals, not permission to surface extra facts.",
        "- If a KPI/card/table/summary value is not explicitly requested above, omit it even when it appears in evidence.",
        "",
        "Condensed visual evidence JSON. Use only these values for the requested visuals; do not infer new numbers:",
        serialized_data,
        "",
        "Constraints: exact visible numbers only; concise legible text; one coherent visual; no watermark or placeholder text.",
    ])
