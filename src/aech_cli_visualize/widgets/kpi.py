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
        delta_config = None
        if delta:
            # Parse delta value for indicator
            delta_value = delta.replace("+", "").replace("%", "")
            try:
                delta_num = float(delta_value)
                delta_config = dict(
                    reference=0,
                    relative=False,
                    valueformat=".1f" if "%" in delta else ".0f",
                    suffix="%" if "%" in delta else "",
                )
            except ValueError:
                delta_config = None

        # Use number mode for formatted display
        format_str = self.config.get("format_value") or ",.0f"
        # Strip Python format braces if present
        valueformat = format_str.replace("{:", "").replace("}", "")

        fig.add_trace(go.Indicator(
            mode="number+delta" if delta_config else "number",
            value=self.config["value"] if isinstance(self.config["value"], (int, float)) else 0,
            number=dict(
                font=dict(size=72, color=self.theme["colors"]["primary"]),
                valueformat=valueformat,
            ),
            delta=delta_config,
            title=dict(
                text=label,
                font=dict(size=24, color=self.theme["colors"]["text_secondary"]),
            ),
            domain=dict(x=[0, 1], y=[0.1, 0.9]),
        ))

        # Add delta as annotation if we couldn't use indicator's delta
        if delta and not delta_config:
            fig.add_annotation(
                text=delta,
                x=0.5,
                y=0.25,
                showarrow=False,
                font=dict(size=28, color=self._get_delta_color()),
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
            font=dict(size=64, color=colors["primary"], family=self.theme["fonts"]["title"]),
        )

        # Add label
        fig.add_annotation(
            text=label,
            x=0.5,
            y=0.35,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=20, color=colors["text_secondary"]),
        )

        # Add delta if present
        if delta:
            fig.add_annotation(
                text=delta,
                x=0.5,
                y=0.2,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=24, color=self._get_delta_color()),
            )

        fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=20, r=20, t=20, b=20),
        )
