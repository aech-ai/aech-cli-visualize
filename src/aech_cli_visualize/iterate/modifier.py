"""LLM-based spec modifier for interpreting user feedback."""

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.settings import ModelSettings


class StyleModification(BaseModel):
    """Structured style modification from LLM."""

    preset: str | None = Field(
        None,
        description="Style preset to apply: 'compact', 'default', 'presentation', 'spacious'",
    )
    font_scale: float | None = Field(
        None,
        description="Font scale multiplier (0.5 to 2.0). Use 1.3-1.5 for 'fonts too small'.",
    )
    h_spacing: float | None = Field(
        None,
        description="Horizontal spacing between widgets (0.01 to 0.1). Increase for 'too crowded'.",
    )
    v_spacing: float | None = Field(
        None,
        description="Vertical spacing between widgets (0.02 to 0.15). Increase for 'too crowded'.",
    )
    widget_padding: int | None = Field(
        None,
        description="Padding inside widgets in pixels (5 to 50).",
    )
    title_size: int | None = Field(
        None,
        description="Dashboard title font size in pixels.",
    )
    title_margin: float | None = Field(
        None,
        description="Space reserved for title area (-0.15 to 0.15). NEGATIVE values push content UP toward title. Use -0.06 to -0.10 to move top row closer to title.",
    )


class WidgetModification(BaseModel):
    """Modification to a specific widget."""

    widget_index: int = Field(description="Index of widget to modify (0-based)")
    config_changes: dict[str, Any] = Field(
        default_factory=dict,
        description="Changes to widget config (label, value, chart_type, etc.)"
    )
    position_changes: dict[str, int] = Field(
        default_factory=dict,
        description="Changes to widget position: row, col, colspan, rowspan. Use to resize widgets."
    )


class SpecModification(BaseModel):
    """Complete specification modification."""

    style: StyleModification | None = Field(
        None, description="Style modifications to apply"
    )
    widget_modifications: list[WidgetModification] = Field(
        default_factory=list, description="Specific widget changes"
    )
    layout_changes: dict[str, Any] = Field(
        default_factory=dict, description="Layout-level changes (columns, rows, etc.)"
    )
    reasoning: str = Field(description="Explanation of changes being made")


MODIFICATION_INSTRUCTIONS = """You are an expert dashboard designer with deep knowledge of visual hierarchy, spatial composition, and data visualization best practices.

## Design Principles

**Visual Hierarchy**: Elements should have size proportional to their importance.
- KPIs and headline metrics should DOMINATE - they're the hero elements
- Charts should fill their allocated space generously
- No widget should appear "lost" in empty space or squeezed into a corner

**Spatial Balance**: Every pixel should feel intentional.
- EMPTY SPACE IS A PROBLEM if it's unintentional (e.g., huge gap at top, tiny chart in corner)
- Crowding is also a problem (overlapping text, cramped widgets)
- Good balance: widgets fill ~80-90% of their allocated regions

**Typography Hierarchy**:
- Dashboard title: Prominent but not overwhelming (24-36pt)
- KPI values: LARGE and readable from distance (48-72pt effective size)
- KPI labels: Clear secondary text (18-24pt)
- Chart axis labels: Must be readable (12-16pt minimum)

**Common Visual Problems to Detect in Images**:
1. **Empty space at top / top row too low**: title_margin too large → Use NEGATIVE title_margin (-0.06 to -0.10) to push content UP
2. **Tiny gauge/KPI**: Widget not filling its allocated space → Increase colspan or reduce h_spacing
3. **Text cut off/truncated**: Font too large for space → Reduce font_scale OR increase colspan
4. **Widgets overlapping**: Spacing too small OR fonts too large → Increase h_spacing OR reduce font_scale
5. **Charts with tiny labels**: font_scale not propagating to charts → Increase font_scale to 1.4+
6. **Unbalanced layout**: Some widgets huge, others tiny → Adjust colspan/rowspan for proportion
7. **Charts too close together**: h_spacing too small → DOUBLE or TRIPLE h_spacing (e.g., 0.04 → 0.10)

## Style Parameters

| Parameter | Range | Effect |
|-----------|-------|--------|
| font_scale | 0.6-2.0 | Multiplies ALL text. Use 1.3-1.5 for presentation. |
| h_spacing | 0.02-0.15 | Gap between columns. 0.04 = modest, 0.10+ = generous |
| v_spacing | 0.03-0.15 | Gap between rows. 0.06 = modest, 0.10+ = generous |
| title_margin | -0.15-0.15 | Space for title. **NEGATIVE values push content UP** toward title. Use -0.06 to -0.10 to move top row closer to title. |
| widget_padding | 10-40 | Internal padding in pixels |
| title_size | 20-42 | Dashboard title size in pixels |

## Decision Framework

When analyzing feedback + image:
1. LOOK at the image - where is the wasted space? Where is it cramped?
2. Match visual problems to parameters that control them
3. Make BOLD changes - if something is "too small", don't add 10%, double it
4. Consider trade-offs: bigger fonts may need more spacing to avoid overlap

## Critical Rules

- MAKE MEANINGFUL CHANGES. If spacing needs to increase, jump from 0.04 to 0.10, not 0.04 to 0.05.
- If you see massive empty space, something is WRONG - address it.
- Balance is key: if KPIs are taking 40% of vertical space but charts only 30%, that's wrong.
- Only include fields that need to change - leave others as None/empty.

## Layout Constraints (IMPORTANT)

- **Minimum v_spacing**: When KPIs with deltas are above charts with titles, use v_spacing >= 0.06.
  Setting v_spacing < 0.06 will cause KPI deltas to overlap with chart titles.
- **12-column math**: Widget colspans must sum to ≤12 per row. Common patterns:
  - 3 equal widgets: 4+4+4 (recommended) or 3+3+6
  - 2 equal widgets: 6+6
  - Unequal: 7+5 or 8+4
- **Row math**: Widget rowspans must not exceed layout rows.
- **Position changes**: When resizing widgets (colspan/rowspan), ensure adjacent widgets don't overlap."""


class SpecModifier:
    """Modifies dashboard specs based on user feedback using LLM."""

    def __init__(self, model: str | None = None, enable_thinking: bool = True):
        """Initialize the modifier.

        Args:
            model: LLM model identifier (e.g., "openai:gpt-4o", "anthropic:claude-sonnet-4-20250514")
            enable_thinking: Enable extended thinking for Anthropic models (default: True)
        """
        self.model = model or os.environ.get("AECH_LLM_WORKER_MODEL", "anthropic:claude-sonnet-4-20250514")
        self.enable_thinking = enable_thinking
        self.agent: Agent[None, SpecModification] = Agent(
            self.model,
            output_type=SpecModification,
            instructions=MODIFICATION_INSTRUCTIONS,
        )

    def interpret_feedback(
        self,
        feedback: str,
        current_spec: dict[str, Any],
        image_path: Path | None = None,
    ) -> SpecModification:
        """Interpret user feedback and generate spec modifications.

        Args:
            feedback: User's feedback about the dashboard
            current_spec: Current dashboard specification
            image_path: Optional path to current render for visual context

        Returns:
            SpecModification with changes to apply
        """
        # Build prompt with current spec context
        current_style = current_spec.get("style", {})
        widgets_summary = self._summarize_widgets(current_spec)

        layout = current_spec.get("layout", {})
        prompt = f"""User feedback: "{feedback}"

Current dashboard state:
- Title: {current_spec.get('title', 'None')}
- Grid: {layout.get('columns', 12)} columns × {layout.get('rows', 2)} rows
- Current style: {json.dumps(current_style) if current_style else 'default (no custom style)'}
- Widgets:
{widgets_summary}

IMPORTANT: If an image is provided, ANALYZE it carefully:
- Is there excessive empty space anywhere? (top, between rows, around widgets)
- Are widgets filling their allocated space appropriately?
- Is text readable at presentation distance?
- Are elements visually balanced (no tiny widgets next to huge ones)?
- Do charts have readable axis labels?

Based on the feedback AND your visual analysis, what modifications would fix the issues?
Be BOLD with changes - small tweaks won't fix significant visual problems."""

        # Include image if provided for visual context
        messages: list[Any] = [prompt]
        if image_path and image_path.exists():
            messages.append(BinaryContent.from_path(image_path))

        # Configure model settings with extended thinking for complex visual reasoning
        settings = ModelSettings(temperature=0.2)
        if self.enable_thinking and self.model.startswith("anthropic:"):
            # Enable extended thinking for Anthropic models - this helps with
            # complex visual analysis and parameter calculation
            settings = ModelSettings(
                temperature=1.0,  # Required for extended thinking
                thinking={"type": "enabled", "budget_tokens": 8000},
            )

        result = self.agent.run_sync(messages, model_settings=settings)

        return result.output

    def apply_modifications(
        self,
        spec: dict[str, Any],
        modifications: SpecModification,
    ) -> dict[str, Any]:
        """Apply modifications to a spec.

        Args:
            spec: Original dashboard specification
            modifications: Modifications to apply

        Returns:
            Modified spec (new copy)
        """
        # Deep copy spec
        new_spec = json.loads(json.dumps(spec))

        # Apply style modifications
        if modifications.style:
            if "style" not in new_spec:
                new_spec["style"] = {}

            style_mod = modifications.style
            if style_mod.preset:
                new_spec["style"]["preset"] = style_mod.preset
            if style_mod.font_scale is not None:
                new_spec["style"]["font_scale"] = style_mod.font_scale
            if style_mod.h_spacing is not None:
                new_spec["style"]["h_spacing"] = style_mod.h_spacing
            if style_mod.v_spacing is not None:
                new_spec["style"]["v_spacing"] = style_mod.v_spacing
            if style_mod.widget_padding is not None:
                new_spec["style"]["widget_padding"] = style_mod.widget_padding
            if style_mod.title_size is not None:
                new_spec["style"]["title_size"] = style_mod.title_size
            if style_mod.title_margin is not None:
                new_spec["style"]["title_margin"] = style_mod.title_margin

        # Apply layout changes
        if modifications.layout_changes:
            if "layout" not in new_spec:
                new_spec["layout"] = {}
            new_spec["layout"].update(modifications.layout_changes)

        # Apply widget modifications
        widgets = new_spec.get("widgets", [])
        for widget_mod in modifications.widget_modifications:
            if 0 <= widget_mod.widget_index < len(widgets):
                widget = widgets[widget_mod.widget_index]

                # Apply config changes
                if widget_mod.config_changes:
                    if "config" not in widget:
                        widget["config"] = {}
                    widget["config"].update(widget_mod.config_changes)

                # Apply position changes (colspan, rowspan, row, col)
                if widget_mod.position_changes:
                    if "position" not in widget:
                        widget["position"] = {}
                    widget["position"].update(widget_mod.position_changes)

        return new_spec

    def _summarize_widgets(self, spec: dict[str, Any]) -> str:
        """Create a summary of widgets for the prompt."""
        widgets = spec.get("widgets", [])
        if not widgets:
            return "No widgets"

        summaries = []
        for i, w in enumerate(widgets):
            w_type = w.get("type", "unknown")
            pos = w.get("position", {})
            config = w.get("config", {})

            label = config.get("label") or config.get("title") or ""
            row = pos.get("row", 0)
            col = pos.get("col", 0)
            rowspan = pos.get("rowspan", 1)
            colspan = pos.get("colspan", 1)

            summaries.append(
                f"  [{i}] {w_type}: \"{label}\" at row={row} col={col}, spans {colspan}×{rowspan} (col×row)"
            )

        return "\n".join(summaries)
