"""KPI widget for displaying key performance indicator cards."""

from typing import Any

import plotly.graph_objects as go

from .base import BaseWidget


class KPIWidget(BaseWidget):
    """Widget for rendering KPI/metric cards."""

    @staticmethod
    def _hex_to_rgba(hex_color: str, alpha: float) -> str:
        """Convert #RRGGBB to rgba(r,g,b,a)."""
        color = hex_color.lstrip("#")
        if len(color) != 6:
            return hex_color
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        return f"rgba({r}, {g}, {b}, {alpha})"

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
        colors = self.theme["colors"]

        # Scaled font sizes with a stronger hierarchy for dashboard cards
        value_font_size = int(62 * font_scale)
        label_font_size = int(17 * font_scale)
        delta_font_size = int(16 * font_scale)

        label_text = label.upper() if len(label) <= 28 else label

        # Label
        fig.add_annotation(
            text=f"<b>{label_text}</b>",
            x=0.02,
            y=0.90,
            xref="paper",
            yref="paper",
            xanchor="left",
            yanchor="top",
            showarrow=False,
            font=dict(size=label_font_size, color=colors["text_secondary"]),
        )

        # Primary value
        fig.add_annotation(
            text=f"<b>{display_value}</b>",
            x=0.02,
            y=0.58,
            xref="paper",
            yref="paper",
            xanchor="left",
            yanchor="middle",
            showarrow=False,
            font=dict(size=value_font_size, color=colors["text"], family=self.theme["fonts"]["title"]),
        )

        # Delta chip
        if delta:
            # Determine arrow prefix based on delta direction
            arrow = "▲" if delta.startswith("+") or (delta[0].isdigit() and not delta.startswith("-")) else "▼"
            fig.add_annotation(
                text=f"<b>{arrow} {delta.lstrip('+-')}</b>",
                x=0.02,
                y=0.20,
                xref="paper",
                yref="paper",
                showarrow=False,
                xanchor="left",
                yanchor="middle",
                bgcolor=self._hex_to_rgba(self._get_delta_color(), 0.14),
                bordercolor=self._hex_to_rgba(self._get_delta_color(), 0.35),
                borderwidth=1,
                borderpad=6,
                font=dict(size=delta_font_size, color=self._get_delta_color()),
            )

        fig.update_xaxes(visible=False, range=[0, 1], fixedrange=True)
        fig.update_yaxes(visible=False, range=[0, 1], fixedrange=True)
        fig.update_layout(
            margin=dict(l=26, r=26, t=20, b=20),
            paper_bgcolor=colors.get("surface", colors["background"]),
            plot_bgcolor=colors.get("surface", colors["background"]),
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
        label_font_size = int(16 * font_scale)
        delta_font_size = int(14 * font_scale)

        # Add sparkline as background
        fig.add_trace(go.Scatter(
            y=sparkline,
            mode="lines",
            fill="tozeroy",
            line=dict(color=colors["primary"], width=3),
            fillcolor=self._hex_to_rgba(colors["primary"], 0.12),
            showlegend=False,
        ))

        # Add value as annotation
        fig.add_annotation(
            text=f"<b>{display_value}</b>",
            x=0.02,
            y=0.72,
            xref="paper",
            yref="paper",
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            font=dict(size=value_font_size, color=colors["text"], family=self.theme["fonts"]["title"]),
        )

        # Add label
        fig.add_annotation(
            text=f"<b>{label.upper()}</b>",
            x=0.02,
            y=0.92,
            xref="paper",
            yref="paper",
            showarrow=False,
            xanchor="left",
            yanchor="top",
            font=dict(size=label_font_size, color=colors["text_secondary"]),
        )

        # Add delta if present
        if delta:
            arrow = "▲" if delta.startswith("+") or (delta[0].isdigit() and not delta.startswith("-")) else "▼"
            fig.add_annotation(
                text=f"<b>{arrow} {delta.lstrip('+-')}</b>",
                x=0.02,
                y=0.20,
                xref="paper",
                yref="paper",
                showarrow=False,
                xanchor="left",
                yanchor="middle",
                bgcolor=self._hex_to_rgba(self._get_delta_color(), 0.14),
                bordercolor=self._hex_to_rgba(self._get_delta_color(), 0.35),
                borderwidth=1,
                borderpad=6,
                font=dict(size=delta_font_size, color=self._get_delta_color()),
            )

        fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=24, r=24, t=20, b=20),
            paper_bgcolor=colors.get("surface", colors["background"]),
            plot_bgcolor=colors.get("surface", colors["background"]),
        )
