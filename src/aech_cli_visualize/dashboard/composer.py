"""Dashboard composition engine for multi-widget layouts."""

from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..themes.loader import load_theme, apply_theme_to_figure
from ..utils.export import export_figure, parse_resolution, FormatType
from ..widgets.chart import ChartWidget
from ..widgets.kpi import KPIWidget
from ..widgets.table import TableWidget
from ..widgets.gauge import GaugeWidget


# Standard aspect ratios
ASPECT_RATIOS = {
    "16:9": (16, 9),
    "4:3": (4, 3),
    "1:1": (1, 1),
}


class DashboardComposer:
    """Compose multiple widgets into a single dashboard image."""

    def __init__(
        self,
        spec: dict[str, Any],
        theme: str | dict[str, Any] = "corporate",
    ):
        """Initialize dashboard composer.

        Args:
            spec: Dashboard specification with layout and widgets
            theme: Theme name or dictionary (overrides spec theme)
        """
        self.spec = spec
        self.theme = load_theme(theme) if isinstance(theme, str) else theme

        # Extract layout settings
        layout = spec.get("layout", {})
        self.columns = layout.get("columns", 12)
        self.rows = layout.get("rows", 2)
        self.aspect_ratio = layout.get("aspect_ratio", "16:9")
        self.title = spec.get("title")
        self.padding = layout.get("padding", 20)

    def _get_widget_type_category(self, widget_type: str) -> str:
        """Categorize widget type for subplot handling.

        Args:
            widget_type: The widget type string

        Returns:
            Category: 'domain' for indicators, 'xy' for charts, 'table' for tables
        """
        if widget_type in ("kpi", "gauge"):
            return "domain"
        elif widget_type == "table":
            return "table"
        else:
            return "xy"

    def _calculate_domain(
        self,
        row: int,
        col: int,
        rowspan: int,
        colspan: int,
    ) -> tuple[list[float], list[float]]:
        """Calculate the domain (x, y ranges) for a widget position.

        Args:
            row: Grid row (0-indexed)
            col: Grid column (0-indexed)
            rowspan: Number of rows to span
            colspan: Number of columns to span

        Returns:
            Tuple of (x_domain, y_domain) as [min, max] pairs
        """
        # Calculate cell dimensions
        h_spacing = 0.02
        v_spacing = 0.04
        title_space = 0.08 if self.title else 0.02

        # Available space after margins
        cell_width = (1.0 - h_spacing * (self.columns + 1)) / self.columns
        cell_height = (1.0 - title_space - v_spacing * (self.rows + 1)) / self.rows

        # Calculate position (y is inverted - row 0 is at top)
        x0 = h_spacing + col * (cell_width + h_spacing)
        x1 = x0 + colspan * cell_width + (colspan - 1) * h_spacing

        y1 = 1.0 - title_space - v_spacing - row * (cell_height + v_spacing)
        y0 = y1 - rowspan * cell_height - (rowspan - 1) * v_spacing

        return [x0, x1], [y0, y1]

    def _create_widget_figure(self, widget_spec: dict[str, Any]) -> go.Figure:
        """Create a widget figure from specification.

        Args:
            widget_spec: Widget specification with type and config

        Returns:
            Widget figure
        """
        widget_type = widget_spec["type"]
        config = widget_spec.get("config", {})

        if widget_type == "chart":
            widget = ChartWidget(
                chart_type=config.get("chart_type", "bar"),
                data=config.get("data", {}),
                title=config.get("title"),
                theme=self.theme,
            )
        elif widget_type == "kpi":
            widget = KPIWidget(
                value=config.get("value", 0),
                label=config.get("label", ""),
                delta=config.get("delta"),
                delta_good=config.get("delta_good", True),
                format_value=config.get("format_value"),
                sparkline=config.get("sparkline"),
                theme=self.theme,
            )
        elif widget_type == "table":
            widget = TableWidget(
                headers=config.get("headers", []),
                rows=config.get("rows", []),
                title=config.get("title"),
                theme=self.theme,
            )
        elif widget_type == "gauge":
            widget = GaugeWidget(
                value=config.get("value", 0),
                min_val=config.get("min", 0),
                max_val=config.get("max", 100),
                label=config.get("label"),
                thresholds=config.get("thresholds"),
                theme=self.theme,
            )
        else:
            raise ValueError(f"Unknown widget type: {widget_type}")

        return widget.create_figure()

    def _build_subplot_specs(
        self, widgets: list[dict[str, Any]]
    ) -> list[list[dict[str, Any] | None]]:
        """Build subplot specification matrix with correct types.

        Args:
            widgets: List of widget specifications

        Returns:
            2D list of subplot specs with None for empty cells
        """
        # Initialize empty grid
        specs = [[{} for _ in range(self.columns)] for _ in range(self.rows)]

        # Map positions to widget types
        pos_to_widget = {}
        for widget in widgets:
            pos = widget.get("position", {})
            row = pos.get("row", 0)
            col = pos.get("col", 0)
            pos_to_widget[(row, col)] = widget

        for widget in widgets:
            pos = widget.get("position", {})
            row = pos.get("row", 0)
            col = pos.get("col", 0)
            rowspan = pos.get("rowspan", 1)
            colspan = pos.get("colspan", 1)
            widget_type = widget.get("type", "chart")

            # Get the subplot type for this widget
            subplot_type = self._get_widget_type_category(widget_type)

            # Mark occupied cells
            for r in range(row, min(row + rowspan, self.rows)):
                for c in range(col, min(col + colspan, self.columns)):
                    if r == row and c == col:
                        spec = {"rowspan": rowspan, "colspan": colspan}
                        if subplot_type == "domain":
                            spec["type"] = "domain"
                        elif subplot_type == "table":
                            spec["type"] = "table"
                        # xy is the default, no need to specify
                        specs[r][c] = spec
                    else:
                        specs[r][c] = None

        return specs

    def compose(self) -> go.Figure:
        """Compose all widgets into a single figure.

        Uses domain-based positioning for flexibility.

        Returns:
            Composed dashboard figure
        """
        widgets = self.spec.get("widgets", [])
        if not widgets:
            # Return empty figure
            fig = go.Figure()
            fig.update_layout(
                title=self.title,
                paper_bgcolor=self.theme["colors"]["background"],
            )
            return fig

        fig = go.Figure()

        # Add each widget with calculated domain
        for i, widget_spec in enumerate(widgets):
            pos = widget_spec.get("position", {})
            row = pos.get("row", 0)
            col = pos.get("col", 0)
            rowspan = pos.get("rowspan", 1)
            colspan = pos.get("colspan", 1)

            # Calculate domain for this widget
            x_domain, y_domain = self._calculate_domain(row, col, rowspan, colspan)

            # Create widget figure
            widget_fig = self._create_widget_figure(widget_spec)

            # Add traces with updated domain
            for trace in widget_fig.data:
                # Update trace domain based on trace type
                if hasattr(trace, 'domain'):
                    trace.domain = dict(x=x_domain, y=y_domain)

                # For scatter/bar traces, we need to use xaxis/yaxis references
                if isinstance(trace, (go.Scatter, go.Bar)):
                    axis_suffix = "" if i == 0 else str(i + 1)
                    trace.xaxis = f"x{axis_suffix}"
                    trace.yaxis = f"y{axis_suffix}"

                    # Create axis for this widget
                    x_axis_key = f"xaxis{axis_suffix}"
                    y_axis_key = f"yaxis{axis_suffix}"

                    fig.layout[x_axis_key] = dict(
                        domain=x_domain,
                        anchor=f"y{axis_suffix}" if axis_suffix else "y",
                        gridcolor=self.theme["colors"]["grid"],
                        linecolor=self.theme["colors"]["grid"],
                        tickfont=dict(color=self.theme["colors"]["text_secondary"]),
                    )
                    fig.layout[y_axis_key] = dict(
                        domain=y_domain,
                        anchor=f"x{axis_suffix}" if axis_suffix else "x",
                        gridcolor=self.theme["colors"]["grid"],
                        linecolor=self.theme["colors"]["grid"],
                        tickfont=dict(color=self.theme["colors"]["text_secondary"]),
                    )

                fig.add_trace(trace)

        # Apply theme and title
        layout_updates = {
            "paper_bgcolor": self.theme["colors"]["background"],
            "plot_bgcolor": self.theme["colors"]["background"],
            "font": {
                "family": self.theme["fonts"]["body"],
                "color": self.theme["colors"]["text"],
            },
            "showlegend": False,
            "margin": dict(l=40, r=40, t=80 if self.title else 40, b=40),
        }

        if self.title:
            layout_updates["title"] = dict(
                text=self.title,
                x=0.5,
                xanchor="center",
                font=dict(size=28, color=self.theme["colors"]["text"]),
            )

        fig.update_layout(**layout_updates)

        return fig

    def render(
        self,
        output_dir: str | Path,
        filename: str = "dashboard",
        format: FormatType = "png",
        resolution: str = "1080p",
        scale: float = 2.0,
    ) -> Path:
        """Render dashboard to image file.

        Args:
            output_dir: Directory to write the file
            filename: Base filename (without extension)
            format: Output format (png, svg, pdf)
            resolution: Resolution preset or WxH
            scale: Scale factor for higher DPI

        Returns:
            Path to the exported file
        """
        fig = self.compose()
        width, height = parse_resolution(resolution)

        return export_figure(
            fig=fig,
            output_dir=output_dir,
            filename=filename,
            format=format,
            width=width,
            height=height,
            scale=scale,
        )
