"""Chart widget for bar, line, pie, scatter, area, and heatmap charts."""

from typing import Any, Literal

import plotly.express as px
import plotly.graph_objects as go

from .base import BaseWidget

ChartType = Literal["bar", "line", "pie", "scatter", "area", "heatmap"]


class ChartWidget(BaseWidget):
    """Widget for rendering various chart types."""

    def __init__(
        self,
        chart_type: ChartType,
        data: dict[str, Any],
        title: str | None = None,
        x_label: str | None = None,
        y_label: str | None = None,
        show_legend: bool = True,
        show_values: bool = False,
        theme: str | dict[str, Any] = "corporate",
    ):
        """Initialize chart widget.

        Args:
            chart_type: Type of chart (bar, line, pie, scatter, area, heatmap)
            data: Chart data with x, y, and optional series
            title: Chart title
            x_label: X-axis label
            y_label: Y-axis label
            show_legend: Whether to show legend
            show_values: Whether to show values on data points
            theme: Theme name or dictionary
        """
        config = {
            "chart_type": chart_type,
            "data": data,
            "title": title,
            "x_label": x_label,
            "y_label": y_label,
            "show_legend": show_legend,
            "show_values": show_values,
        }
        super().__init__(config, theme)

    def create_figure(self) -> go.Figure:
        """Create the chart figure based on chart type."""
        chart_type = self.config["chart_type"]
        data = self.config["data"]

        # Route to appropriate chart builder
        builders = {
            "bar": self._create_bar_chart,
            "line": self._create_line_chart,
            "pie": self._create_pie_chart,
            "scatter": self._create_scatter_chart,
            "area": self._create_area_chart,
            "heatmap": self._create_heatmap,
        }

        builder = builders.get(chart_type)
        if not builder:
            raise ValueError(f"Unknown chart type: {chart_type}")

        fig = builder(data)
        self._apply_common_layout(fig)
        return fig

    def _create_bar_chart(self, data: dict[str, Any]) -> go.Figure:
        """Create bar chart."""
        x = data.get("x", [])
        palette = self.theme["chart"]["palette"]

        if "series" in data:
            # Multiple series
            fig = go.Figure()
            for i, series in enumerate(data["series"]):
                fig.add_trace(go.Bar(
                    name=series.get("name", f"Series {i+1}"),
                    x=x,
                    y=series["values"],
                    marker_color=palette[i % len(palette)],
                    text=series["values"] if self.config["show_values"] else None,
                    textposition="outside" if self.config["show_values"] else None,
                ))
            fig.update_layout(barmode="group")
        else:
            # Single series
            y = data.get("y", [])
            fig = go.Figure(data=[
                go.Bar(
                    x=x,
                    y=y,
                    marker_color=palette[0],
                    text=y if self.config["show_values"] else None,
                    textposition="outside" if self.config["show_values"] else None,
                )
            ])

        return fig

    def _create_line_chart(self, data: dict[str, Any]) -> go.Figure:
        """Create line chart."""
        x = data.get("x", [])
        palette = self.theme["chart"]["palette"]

        if "series" in data:
            fig = go.Figure()
            for i, series in enumerate(data["series"]):
                fig.add_trace(go.Scatter(
                    name=series.get("name", f"Series {i+1}"),
                    x=x,
                    y=series["values"],
                    mode="lines+markers" if self.config["show_values"] else "lines",
                    line=dict(color=palette[i % len(palette)], width=2),
                    marker=dict(size=8),
                ))
        else:
            y = data.get("y", [])
            fig = go.Figure(data=[
                go.Scatter(
                    x=x,
                    y=y,
                    mode="lines+markers" if self.config["show_values"] else "lines",
                    line=dict(color=palette[0], width=2),
                    marker=dict(size=8),
                )
            ])

        return fig

    def _create_pie_chart(self, data: dict[str, Any]) -> go.Figure:
        """Create pie chart."""
        labels = data.get("x", data.get("labels", []))
        values = data.get("y", data.get("values", []))
        palette = self.theme["chart"]["palette"]

        fig = go.Figure(data=[
            go.Pie(
                labels=labels,
                values=values,
                marker=dict(colors=palette[:len(labels)]),
                textinfo="percent+label" if self.config["show_values"] else "percent",
                hole=0.3,  # Donut style
            )
        ])

        return fig

    def _create_scatter_chart(self, data: dict[str, Any]) -> go.Figure:
        """Create scatter plot."""
        x = data.get("x", [])
        palette = self.theme["chart"]["palette"]

        if "series" in data:
            fig = go.Figure()
            for i, series in enumerate(data["series"]):
                fig.add_trace(go.Scatter(
                    name=series.get("name", f"Series {i+1}"),
                    x=x,
                    y=series["values"],
                    mode="markers",
                    marker=dict(color=palette[i % len(palette)], size=10),
                ))
        else:
            y = data.get("y", [])
            fig = go.Figure(data=[
                go.Scatter(
                    x=x,
                    y=y,
                    mode="markers",
                    marker=dict(color=palette[0], size=10),
                )
            ])

        return fig

    def _create_area_chart(self, data: dict[str, Any]) -> go.Figure:
        """Create area chart."""
        x = data.get("x", [])
        palette = self.theme["chart"]["palette"]

        if "series" in data:
            fig = go.Figure()
            for i, series in enumerate(data["series"]):
                fig.add_trace(go.Scatter(
                    name=series.get("name", f"Series {i+1}"),
                    x=x,
                    y=series["values"],
                    mode="lines",
                    fill="tozeroy" if i == 0 else "tonexty",
                    line=dict(color=palette[i % len(palette)], width=2),
                ))
        else:
            y = data.get("y", [])
            fig = go.Figure(data=[
                go.Scatter(
                    x=x,
                    y=y,
                    mode="lines",
                    fill="tozeroy",
                    line=dict(color=palette[0], width=2),
                )
            ])

        return fig

    def _create_heatmap(self, data: dict[str, Any]) -> go.Figure:
        """Create heatmap."""
        z = data.get("z", data.get("values", []))
        x = data.get("x", None)
        y = data.get("y", None)

        fig = go.Figure(data=[
            go.Heatmap(
                z=z,
                x=x,
                y=y,
                colorscale=[
                    [0, self.theme["colors"]["surface"]],
                    [1, self.theme["colors"]["primary"]],
                ],
            )
        ])

        return fig

    def _apply_common_layout(self, fig: go.Figure) -> None:
        """Apply common layout settings to the figure."""
        font_scale = self.config.get("font_scale", 1.0)

        # Scaled font sizes
        title_size = int(18 * font_scale)
        axis_title_size = int(14 * font_scale)
        tick_size = int(12 * font_scale)
        legend_size = int(12 * font_scale)

        layout_updates = {
            "showlegend": self.config["show_legend"],
            "margin": dict(l=60, r=40, t=80, b=60),
            "font": dict(size=tick_size),
        }

        if self.config["title"]:
            layout_updates["title"] = dict(
                text=self.config["title"],
                x=0.5,
                xanchor="center",
                font=dict(size=title_size),
            )

        # Apply axis font sizes
        layout_updates["xaxis"] = dict(
            tickfont=dict(size=tick_size),
            title=dict(font=dict(size=axis_title_size)),
        )
        layout_updates["yaxis"] = dict(
            tickfont=dict(size=tick_size),
            title=dict(font=dict(size=axis_title_size)),
        )

        if self.config["x_label"]:
            layout_updates["xaxis"]["title"]["text"] = self.config["x_label"]

        if self.config["y_label"]:
            layout_updates["yaxis"]["title"]["text"] = self.config["y_label"]

        # Legend font
        if self.config["show_legend"]:
            layout_updates["legend"] = dict(font=dict(size=legend_size))

        fig.update_layout(**layout_updates)
