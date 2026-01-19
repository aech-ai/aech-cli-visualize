"""KPI widget for displaying key performance indicator cards."""

from typing import Any

import plotly.graph_objects as go

from .base import BaseWidget


class KPIWidget(BaseWidget):
    """Widget for rendering KPI/metric cards."""

    def __init__(
        self,
        value: float | int | str,
        label: str,
        delta: str | None = None,
        delta_good: bool = True,
        format_value: str | None = None,
        sparkline: list[float] | None = None,
        theme: str | dict[str, Any] = "corporate",
    ):
        """Initialize KPI widget.

        Args:
            value: The metric value to display
            label: Label describing the metric
            delta: Change indicator (e.g., '+12%', '-5')
            delta_good: Whether positive delta is good (affects color)
            format_value: Python format string for value (e.g., '{:,.0f}')
            sparkline: Optional list of values for sparkline
            theme: Theme name or dictionary
        """
        config = {
            "value": value,
            "label": label,
            "delta": delta,
            "delta_good": delta_good,
            "format_value": format_value,
            "sparkline": sparkline,
        }
        super().__init__(config, theme)

    def _format_value(self, value: Any) -> str:
        """Format the value using the format string if provided."""
        format_str = self.config.get("format_value")
        if format_str and isinstance(value, (int, float)):
            try:
                return format_str.format(value)
            except (ValueError, KeyError):
                pass
        return str(value)

    def _get_delta_color(self) -> str:
        """Get the appropriate color for the delta indicator."""
        delta = self.config.get("delta", "")
        delta_good = self.config.get("delta_good", True)

        if not delta:
            return self.theme["colors"]["neutral"]

        # Determine if delta is positive or negative
        is_positive = delta.startswith("+") or (
            delta[0].isdigit() and not delta.startswith("-")
        )

        if is_positive:
            return self.theme["colors"]["positive"] if delta_good else self.theme["colors"]["negative"]
        else:
            return self.theme["colors"]["negative"] if delta_good else self.theme["colors"]["positive"]

    def create_figure(self) -> go.Figure:
        """Create the KPI card figure."""
        value = self.config["value"]
        label = self.config["label"]
        delta = self.config.get("delta")
        sparkline = self.config.get("sparkline")

        # Format the display value
        display_value = self._format_value(value)

        fig = go.Figure()

        # Determine layout based on whether we have a sparkline
        if sparkline:
            # KPI with sparkline - split layout
            self._add_kpi_with_sparkline(fig, display_value, label, delta, sparkline)
        else:
            # Simple KPI card using Indicator
            self._add_simple_kpi(fig, display_value, label, delta)

        return fig

    def _add_simple_kpi(
        self,
        fig: go.Figure,
        display_value: str,
        label: str,
        delta: str | None,
    ) -> None:
        """Add a simple KPI indicator without sparkline."""
        # Get font scale from config (passed from dashboard style)
        font_scale = self.config.get("font_scale", 1.0)

        # Use number mode for formatted display
        format_str = self.config.get("format_value") or ",.0f"
        # Strip Python format braces if present
        valueformat = format_str.replace("{:", "").replace("}", "")

        # Scaled font sizes
        value_font_size = int(72 * font_scale)
        label_font_size = int(24 * font_scale)
        delta_font_size = int(28 * font_scale)

        # Vertical centering: content_v_offset shifts content up (positive) or down (negative)
        # Default 0 centers content; range typically -0.1 to 0.1
        content_v_offset = self.config.get("content_v_offset", 0)

        # Base domain positions - centered in widget space
        domain_bottom = 0.08 + content_v_offset if delta else 0.05 + content_v_offset
        domain_top = 0.82 + content_v_offset
        delta_y = 0.12 + content_v_offset

        fig.add_trace(go.Indicator(
            mode="number",
            value=self.config["value"] if isinstance(self.config["value"], (int, float)) else 0,
            number=dict(
                font=dict(size=value_font_size, color=self.theme["colors"]["primary"]),
                valueformat=valueformat,
            ),
            title=dict(
                text=label,
                font=dict(size=label_font_size, color=self.theme["colors"]["text_secondary"]),
            ),
            domain=dict(x=[0, 1], y=[domain_bottom, domain_top]),
        ))

        # Always use annotation for delta - indicator delta mode is buggy
        if delta:
            # Determine arrow prefix based on delta direction
            arrow = "▲" if delta.startswith("+") or (delta[0].isdigit() and not delta.startswith("-")) else "▼"
            fig.add_annotation(
                text=f"{arrow}{delta.lstrip('+-')}",
                x=0.5,
                y=delta_y,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=delta_font_size, color=self._get_delta_color()),
            )

        fig.update_layout(
            margin=dict(l=40, r=40, t=40, b=40),
        )

    def _add_kpi_with_sparkline(
        self,
        fig: go.Figure,
        display_value: str,
        label: str,
        delta: str | None,
        sparkline: list[float],
    ) -> None:
        """Add KPI with sparkline chart."""
        colors = self.theme["colors"]
        font_scale = self.config.get("font_scale", 1.0)

        # Scaled font sizes
        value_font_size = int(64 * font_scale)
        label_font_size = int(20 * font_scale)
        delta_font_size = int(24 * font_scale)

        # Add sparkline as background
        fig.add_trace(go.Scatter(
            y=sparkline,
            mode="lines",
            fill="tozeroy",
            line=dict(color=colors["primary"], width=2),
            fillcolor=f"rgba({int(colors['primary'][1:3], 16)}, {int(colors['primary'][3:5], 16)}, {int(colors['primary'][5:7], 16)}, 0.1)",
            showlegend=False,
        ))

        # Add value as annotation
        fig.add_annotation(
            text=display_value,
            x=0.5,
            y=0.7,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=value_font_size, color=colors["primary"], family=self.theme["fonts"]["title"]),
        )

        # Add label
        fig.add_annotation(
            text=label,
            x=0.5,
            y=0.35,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=label_font_size, color=colors["text_secondary"]),
        )

        # Add delta if present
        if delta:
            arrow = "▲" if delta.startswith("+") or (delta[0].isdigit() and not delta.startswith("-")) else "▼"
            fig.add_annotation(
                text=f"{arrow}{delta.lstrip('+-')}",
                x=0.5,
                y=0.2,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=delta_font_size, color=self._get_delta_color()),
            )

        fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=20, r=20, t=20, b=20),
        )
