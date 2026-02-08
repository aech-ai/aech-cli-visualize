"""Chart widget for bar, line, pie, scatter, area, and heatmap charts."""

from typing import Any, Literal

import plotly.graph_objects as go

from .base import BaseWidget

ChartType = Literal["bar", "line", "pie", "scatter", "area", "heatmap"]


class ChartWidget(BaseWidget):
    """Widget for rendering various chart types."""

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
        marker_line_color = self.theme["colors"].get("surface", self.theme["colors"]["background"])

        if "series" in data:
            # Multiple series
            fig = go.Figure()
            for i, series in enumerate(data["series"]):
                fig.add_trace(go.Bar(
                    name=series.get("name", f"Series {i+1}"),
                    x=x,
                    y=series["values"],
                    marker=dict(
                        color=palette[i % len(palette)],
                        line=dict(color=marker_line_color, width=1),
                    ),
                    text=series["values"] if self.config["show_values"] else None,
                    textposition="outside" if self.config["show_values"] else None,
                    opacity=0.92,
                    cliponaxis=False,
                ))
            fig.update_layout(barmode="group", bargap=0.24, bargroupgap=0.10)
        else:
            # Single series
            y = data.get("y", [])
            fig = go.Figure(data=[
                go.Bar(
                    x=x,
                    y=y,
                    marker=dict(
                        color=palette[0],
                        line=dict(color=marker_line_color, width=1),
                    ),
                    text=y if self.config["show_values"] else None,
                    textposition="outside" if self.config["show_values"] else None,
                    opacity=0.94,
                    cliponaxis=False,
                )
            ])
            fig.update_layout(bargap=0.24)

        return fig

    def _create_line_chart(self, data: dict[str, Any]) -> go.Figure:
        """Create line chart."""
        x = data.get("x", [])
        palette = self.theme["chart"]["palette"]
        line_width = self.theme.get("chart", {}).get("line_width", 3)
        marker_size = self.theme.get("chart", {}).get("marker_size", 7)

        if "series" in data:
            fig = go.Figure()
            for i, series in enumerate(data["series"]):
                fig.add_trace(go.Scatter(
                    name=series.get("name", f"Series {i+1}"),
                    x=x,
                    y=series["values"],
                    mode="lines+markers" if self.config["show_values"] else "lines",
                    line=dict(color=palette[i % len(palette)], width=line_width),
                    marker=dict(size=marker_size, line=dict(color="#ffffff", width=1)),
                    connectgaps=True,
                ))
        else:
            y = data.get("y", [])
            fig = go.Figure(data=[
                go.Scatter(
                    x=x,
                    y=y,
                    mode="lines+markers" if self.config["show_values"] else "lines",
                    line=dict(color=palette[0], width=line_width),
                    marker=dict(size=marker_size, line=dict(color="#ffffff", width=1)),
                    connectgaps=True,
                )
            ])

        return fig

    def _create_pie_chart(self, data: dict[str, Any]) -> go.Figure:
        """Create pie chart."""
        labels = data.get("x", data.get("labels", []))
        values = data.get("y", data.get("values", []))
        palette = self.theme["chart"]["palette"]
        textinfo = "label+percent" if self.config["show_values"] else "percent"

        fig = go.Figure(data=[
            go.Pie(
                labels=labels,
                values=values,
                marker=dict(
                    colors=palette[:len(labels)],
                    line=dict(
                        color=self.theme["colors"].get("background", "#ffffff"),
                        width=2,
                    ),
                ),
                textinfo=textinfo,
                textposition="inside",
                insidetextorientation="horizontal",
                hole=0.55,
                sort=False,
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
                    marker=dict(
                        color=palette[i % len(palette)],
                        size=10,
                        opacity=0.85,
                        line=dict(color="#ffffff", width=1),
                    ),
                ))
        else:
            y = data.get("y", [])
            fig = go.Figure(data=[
                go.Scatter(
                    x=x,
                    y=y,
                    mode="markers",
                    marker=dict(
                        color=palette[0],
                        size=10,
                        opacity=0.85,
                        line=dict(color="#ffffff", width=1),
                    ),
                )
            ])

        return fig

    def _create_area_chart(self, data: dict[str, Any]) -> go.Figure:
        """Create area chart."""
        x = data.get("x", [])
        palette = self.theme["chart"]["palette"]
        line_width = self.theme.get("chart", {}).get("line_width", 3)

        if "series" in data:
            fig = go.Figure()
            for i, series in enumerate(data["series"]):
                color = palette[i % len(palette)]
                fig.add_trace(go.Scatter(
                    name=series.get("name", f"Series {i+1}"),
                    x=x,
                    y=series["values"],
                    mode="lines",
                    fill="tozeroy" if i == 0 else "tonexty",
                    fillcolor=self._hex_to_rgba(color, 0.16 if i == 0 else 0.12),
                    line=dict(color=color, width=line_width),
                ))
        else:
            y = data.get("y", [])
            color = palette[0]
            fig = go.Figure(data=[
                go.Scatter(
                    x=x,
                    y=y,
                    mode="lines",
                    fill="tozeroy",
                    fillcolor=self._hex_to_rgba(color, 0.16),
                    line=dict(color=color, width=line_width),
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
                    [0.0, self.theme["colors"]["surface"]],
                    [0.5, self._hex_to_rgba(self.theme["colors"]["secondary"], 0.65)],
                    [1.0, self.theme["colors"]["primary"]],
                ],
                showscale=True,
            )
        ])

        return fig

    def _apply_common_layout(self, fig: go.Figure) -> None:
        """Apply common layout settings to the figure."""
        font_scale = self.config.get("font_scale", 1.0)
        colors = self.theme["colors"]
        chart_theme = self.theme.get("chart", {})

        # Scaled font sizes
        title_size = int(17 * font_scale)
        axis_title_size = int(13 * font_scale)
        tick_size = int(11 * font_scale)
        legend_size = int(11 * font_scale)

        layout_updates = {
            "template": "none",
            "showlegend": self.config["show_legend"],
            "margin": dict(l=42, r=24, t=62 if self.config["title"] else 28, b=42),
            "font": dict(
                size=tick_size,
                family=self.theme["fonts"]["body"],
                color=colors["text"],
            ),
            "paper_bgcolor": colors.get("surface", colors["background"]),
            "plot_bgcolor": colors.get("surface", colors["background"]),
            "colorway": chart_theme.get("palette", [colors["primary"]]),
        }

        if self.config["title"]:
            layout_updates["title"] = dict(
                text=self.config["title"],
                x=0.02,
                xanchor="left",
                y=0.98,
                yanchor="top",
                font=dict(size=title_size, color=colors["text"], family=self.theme["fonts"]["title"]),
            )

        # Apply axis font sizes
        layout_updates["xaxis"] = dict(
            showgrid=self.theme.get("chart", {}).get("gridlines", True),
            gridcolor=colors["grid"],
            gridwidth=1,
            showline=False,
            zeroline=False,
            automargin=True,
            ticks="",
            tickfont=dict(size=tick_size),
            title=dict(font=dict(size=axis_title_size, color=colors["text_secondary"])),
        )
        layout_updates["yaxis"] = dict(
            showgrid=self.theme.get("chart", {}).get("gridlines", True),
            gridcolor=colors["grid"],
            gridwidth=1,
            showline=False,
            zeroline=False,
            automargin=True,
            ticks="",
            separatethousands=True,
            tickfont=dict(size=tick_size),
            title=dict(font=dict(size=axis_title_size, color=colors["text_secondary"])),
        )

        if self.config["x_label"]:
            layout_updates["xaxis"]["title"]["text"] = self.config["x_label"]

        if self.config["y_label"]:
            layout_updates["yaxis"]["title"]["text"] = self.config["y_label"]

        # Legend font
        if self.config["show_legend"]:
            layout_updates["legend"] = dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0.0,
                font=dict(size=legend_size, color=colors["text_secondary"]),
                bgcolor="rgba(0,0,0,0)",
            )

        fig.update_layout(**layout_updates)
