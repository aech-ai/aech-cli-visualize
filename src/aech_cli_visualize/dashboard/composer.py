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

# Style presets for different use cases
STYLE_PRESETS = {
    "compact": {
        "font_scale": 0.8,
        "h_spacing": 0.015,
        "v_spacing": 0.03,
        "widget_padding": 10,
        "title_margin": 0.04,
    },
    "default": {
        "font_scale": 1.0,
        "h_spacing": 0.02,
        "v_spacing": 0.04,
        "widget_padding": 15,
        "title_margin": 0.06,
    },
    "presentation": {
        "font_scale": 1.45,
        "h_spacing": 0.10,
        "v_spacing": 0.10,
        "widget_padding": 22,
        "title_margin": -0.10,
    },
    "spacious": {
        "font_scale": 1.2,
        "h_spacing": 0.04,
        "v_spacing": 0.07,
        "widget_padding": 30,
        "title_margin": 0.02,
    },
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

        # Extract style settings
        style = spec.get("style", {})
        preset_name = style.get("preset", "default")
        preset = STYLE_PRESETS.get(preset_name, STYLE_PRESETS["default"])

        # Style values (explicit values override preset)
        self.font_scale = style.get("font_scale", preset["font_scale"])
        self.h_spacing = style.get("h_spacing", preset["h_spacing"])
        self.v_spacing = style.get("v_spacing", preset["v_spacing"])
        self.widget_padding = style.get("widget_padding", preset["widget_padding"])
        self.title_size = style.get("title_size", int(28 * self.font_scale))
        # Title margin: space reserved for title area (negative values push content up toward title)
        default_title_margin = preset.get("title_margin", 0.06 if self.title else 0.02)
        self.title_margin = style.get("title_margin", default_title_margin)

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
        # Use style settings for spacing
        h_spacing = self.h_spacing
        v_spacing = self.v_spacing
        title_margin = self.title_margin

        # Available space after margins
        cell_width = (1.0 - h_spacing * (self.columns + 1)) / self.columns
        cell_height = (1.0 - title_margin - v_spacing * (self.rows + 1)) / self.rows

        # Calculate position (y is inverted - row 0 is at top)
        x0 = h_spacing + col * (cell_width + h_spacing)
        x1 = x0 + colspan * cell_width + (colspan - 1) * h_spacing

        y1 = 1.0 - title_margin - v_spacing - row * (cell_height + v_spacing)
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
        config = widget_spec.get("config", {}).copy()

        # Inject font_scale into config for widgets that support it
        config["font_scale"] = self.font_scale

        if widget_type == "chart":
            widget = ChartWidget(
                chart_type=config.get("chart_type", "bar"),
                data=config.get("data", {}),
                title=config.get("title"),
                theme=self.theme,
            )
            # Pass font_scale via widget config
            widget.config["font_scale"] = self.font_scale
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
            # Pass font_scale via widget config
            widget.config["font_scale"] = self.font_scale
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
            # Pass font_scale via widget config
            widget.config["font_scale"] = self.font_scale
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
        chart_annotations = []

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

            # Extract chart title from widget config for charts
            widget_type = widget_spec.get("type")
            if widget_type == "chart":
                chart_title = widget_spec.get("config", {}).get("title")
                if chart_title:
                    # Add title as annotation above the chart
                    chart_title_size = int(18 * self.font_scale)
                    chart_annotations.append(dict(
                        text=f"<b>{chart_title}</b>",
                        x=(x_domain[0] + x_domain[1]) / 2,
                        y=y_domain[1] + 0.02,
                        xref="paper",
                        yref="paper",
                        showarrow=False,
                        font=dict(
                            size=chart_title_size,
                            color=self.theme["colors"]["text"],
                        ),
                        xanchor="center",
                        yanchor="bottom",
                    ))

            # Transfer widget annotations (like KPI deltas) with remapped coordinates
            if widget_fig.layout.annotations:
                for ann in widget_fig.layout.annotations:
                    # Remap paper coordinates from widget space to dashboard space
                    ann_dict = ann.to_plotly_json()
                    if ann_dict.get("xref") == "paper" and ann_dict.get("yref") == "paper":
                        # Map x from [0,1] in widget to [x_domain[0], x_domain[1]] in dashboard
                        orig_x = ann_dict.get("x", 0.5)
                        orig_y = ann_dict.get("y", 0.5)
                        ann_dict["x"] = x_domain[0] + orig_x * (x_domain[1] - x_domain[0])
                        ann_dict["y"] = y_domain[0] + orig_y * (y_domain[1] - y_domain[0])
                    chart_annotations.append(ann_dict)

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

                    tick_font_size = int(14 * self.font_scale)
                    axis_title_size = int(14 * self.font_scale)
                    fig.layout[x_axis_key] = dict(
                        domain=x_domain,
                        anchor=f"y{axis_suffix}" if axis_suffix else "y",
                        gridcolor=self.theme["colors"]["grid"],
                        linecolor=self.theme["colors"]["grid"],
                        tickfont=dict(
                            color=self.theme["colors"]["text_secondary"],
                            size=tick_font_size,
                        ),
                        title=dict(font=dict(size=axis_title_size)),
                    )
                    fig.layout[y_axis_key] = dict(
                        domain=y_domain,
                        anchor=f"x{axis_suffix}" if axis_suffix else "x",
                        gridcolor=self.theme["colors"]["grid"],
                        linecolor=self.theme["colors"]["grid"],
                        tickfont=dict(
                            color=self.theme["colors"]["text_secondary"],
                            size=tick_font_size,
                        ),
                        title=dict(font=dict(size=axis_title_size)),
                    )

                fig.add_trace(trace)

        # Apply theme and title
        layout_updates = {
            "paper_bgcolor": self.theme["colors"]["background"],
            "plot_bgcolor": self.theme["colors"]["background"],
            "font": {
                "family": self.theme["fonts"]["body"],
                "color": self.theme["colors"]["text"],
                "size": int(14 * self.font_scale),
            },
            "showlegend": False,
            "margin": dict(l=60, r=40, t=100 if self.title else 60, b=60),
        }

        if self.title:
            layout_updates["title"] = dict(
                text=self.title,
                x=0.5,
                xanchor="center",
                font=dict(size=self.title_size, color=self.theme["colors"]["text"]),
            )

        # Add chart title annotations
        if chart_annotations:
            layout_updates["annotations"] = chart_annotations

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
