"""Gauge widget for displaying progress/status indicators."""

from typing import Any

import plotly.graph_objects as go

from .base import BaseWidget


class GaugeWidget(BaseWidget):
    """Widget for rendering gauge/dial indicators."""

    def __init__(
        self,
        value: float,
        min_val: float = 0,
        max_val: float = 100,
        label: str | None = None,
        unit: str = "",
        thresholds: list[dict[str, Any]] | None = None,
        theme: str | dict[str, Any] = "corporate",
    ):
        """Initialize gauge widget.

        Args:
            value: Current value to display
            min_val: Minimum gauge value
            max_val: Maximum gauge value
            label: Label describing the metric
            unit: Unit suffix (e.g., '%', 'ms')
            thresholds: List of threshold dicts with value, color, label
            theme: Theme name or dictionary
        """
        config = {
            "value": value,
            "min": min_val,
            "max": max_val,
            "label": label,
            "unit": unit,
            "thresholds": thresholds,
        }
        super().__init__(config, theme)

    def _get_gauge_steps(self) -> list[dict[str, Any]] | None:
        """Generate gauge steps from thresholds."""
        thresholds = self.config.get("thresholds")
        if not thresholds:
            return None

        min_val = self.config["min"]
        steps = []

        # Sort thresholds by value
        sorted_thresholds = sorted(thresholds, key=lambda t: t["value"])

        prev_value = min_val
        for threshold in sorted_thresholds:
            steps.append({
                "range": [prev_value, threshold["value"]],
                "color": threshold.get("color", self.theme["colors"]["neutral"]),
            })
            prev_value = threshold["value"]

        return steps

    def _get_threshold_color(self) -> str:
        """Get the color for the current value based on thresholds."""
        value = self.config["value"]
        thresholds = self.config.get("thresholds")

        if not thresholds:
            return self.theme["colors"]["primary"]

        # Sort thresholds by value descending
        sorted_thresholds = sorted(thresholds, key=lambda t: t["value"], reverse=True)

        for threshold in sorted_thresholds:
            if value <= threshold["value"]:
                return threshold.get("color", self.theme["colors"]["primary"])

        return self.theme["colors"]["primary"]

    def create_figure(self) -> go.Figure:
        """Create the gauge figure."""
        value = self.config["value"]
        min_val = self.config["min"]
        max_val = self.config["max"]
        label = self.config.get("label")
        unit = self.config.get("unit", "")
        colors = self.theme["colors"]
        font_scale = self.config.get("font_scale", 1.0)

        # Scaled font sizes
        value_font_size = int(48 * font_scale)
        label_font_size = int(20 * font_scale)
        tick_font_size = int(12 * font_scale)

        # Build gauge configuration
        gauge_config = {
            "axis": {
                "range": [min_val, max_val],
                "tickcolor": colors["text_secondary"],
                "tickfont": {"color": colors["text_secondary"], "size": tick_font_size},
            },
            "bar": {"color": self._get_threshold_color()},
            "bgcolor": colors["surface"],
            "borderwidth": 2,
            "bordercolor": colors["grid"],
        }

        # Add threshold steps if defined
        steps = self._get_gauge_steps()
        if steps:
            gauge_config["steps"] = steps

        # Add threshold line
        gauge_config["threshold"] = {
            "line": {"color": colors["negative"], "width": 4},
            "thickness": 0.75,
            "value": max_val * 0.9,  # Default threshold at 90%
        }

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=value,
            number={
                "suffix": unit,
                "font": {"size": value_font_size, "color": colors["primary"]},
            },
            title={
                "text": label or "",
                "font": {"size": label_font_size, "color": colors["text_secondary"]},
            },
            gauge=gauge_config,
            domain={"x": [0, 1], "y": [0, 1]},
        ))

        fig.update_layout(
            margin=dict(l=40, r=40, t=80, b=40),
        )

        return fig
