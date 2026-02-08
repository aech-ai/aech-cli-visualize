"""Dashboard composition engine for multi-widget layouts."""

from pathlib import Path
from typing import Any

import plotly.graph_objects as go

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
        "font_scale": 0.9,
        "h_spacing": 0.02,
        "v_spacing": 0.035,
        "widget_padding": 8,
        "title_margin": 0.01,
    },
    "default": {
        "font_scale": 1.05,
        "h_spacing": 0.03,
        "v_spacing": 0.05,
        "widget_padding": 12,
        "title_margin": 0.01,
    },
    "presentation": {
        "font_scale": 1.3,
        "h_spacing": 0.05,
        "v_spacing": 0.07,
        "widget_padding": 14,
        "title_margin": -0.02,
    },
    "spacious": {
        "font_scale": 1.15,
        "h_spacing": 0.05,
        "v_spacing": 0.08,
        "widget_padding": 16,
        "title_margin": 0.0,
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
        default_title_margin = preset.get("title_margin", 0.01 if self.title else 0.0)
        self.title_margin = style.get("title_margin", default_title_margin)
        self.show_cards = style.get("show_cards", True)
        self.show_legend = style.get("show_legend")
        self.row_heights_override = style.get("row_heights")
        self._row_weights: list[float] = [1.0] * self.rows

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
        outer_pad_x = min(self.padding / 2000.0, 0.12)
        outer_pad_y = min(self.padding / 1200.0, 0.12)

        available_width = max(0.05, 1.0 - (2 * outer_pad_x))
        available_height = max(0.05, 1.0 - title_margin - (2 * outer_pad_y))

        total_h_spacing = h_spacing * max(0, self.columns - 1)
        total_v_spacing = v_spacing * max(0, self.rows - 1)

        cell_width = max(0.001, (available_width - total_h_spacing) / self.columns)
        weighted_height_unit = max(
            0.001,
            (available_height - total_v_spacing) / max(sum(self._row_weights), 0.001),
        )
        row_heights = [weighted_height_unit * w for w in self._row_weights]

        # Calculate position (y is inverted - row 0 is at top)
        x0 = outer_pad_x + col * (cell_width + h_spacing)
        x1 = x0 + colspan * cell_width + (colspan - 1) * h_spacing

        y_top = 1.0 - title_margin - outer_pad_y
        prior_rows_height = sum(row_heights[:row]) + (row * v_spacing)
        y1 = y_top - prior_rows_height
        span_height = sum(row_heights[row:row + rowspan]) + (max(0, rowspan - 1) * v_spacing)
        y0 = y1 - span_height

        # Internal widget padding to keep content away from card boundaries.
        # Use conservative proportional caps so small widgets stay usable.
        inset_x = min(self.widget_padding / 2000.0, max(0.0, (x1 - x0) * 0.12))
        inset_y = min(self.widget_padding / 1200.0, max(0.0, (y1 - y0) * 0.12))
        x0 += inset_x
        x1 -= inset_x
        y0 += inset_y
        y1 -= inset_y

        return [x0, x1], [y0, y1]

    def _compute_row_weights(self, widgets: list[dict[str, Any]]) -> None:
        """Derive row height weights from content type for better visual balance."""
        if self.row_heights_override and isinstance(self.row_heights_override, list):
            cleaned = []
            for value in self.row_heights_override[:self.rows]:
                if isinstance(value, (int, float)) and value > 0:
                    cleaned.append(float(value))
                else:
                    cleaned.append(1.0)
            if len(cleaned) < self.rows:
                cleaned.extend([1.0] * (self.rows - len(cleaned)))
            self._row_weights = cleaned
            return

        row_types: list[set[str]] = [set() for _ in range(self.rows)]
        for widget in widgets:
            widget_type = widget.get("type", "chart")
            pos = widget.get("position", {})
            row = int(pos.get("row", 0))
            rowspan = int(pos.get("rowspan", 1))
            for r in range(max(0, row), min(self.rows, row + rowspan)):
                row_types[r].add(widget_type)

        weights = [1.0] * self.rows
        for i, widget_types in enumerate(row_types):
            if not widget_types:
                continue
            if widget_types.issubset({"kpi", "gauge"}):
                # KPI-only rows should be compact so charts can dominate.
                weights[i] = 0.82
            elif "chart" in widget_types or "table" in widget_types:
                weights[i] = 1.22

        self._row_weights = weights

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
            widget.config["font_scale"] = self.font_scale
        elif widget_type == "gauge":
            widget = GaugeWidget(
                value=config.get("value", 0),
                min_val=config.get("min", 0),
                max_val=config.get("max", 100),
                label=config.get("label"),
                unit=config.get("unit", ""),
                thresholds=config.get("thresholds"),
                target=config.get("target"),
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

        self._compute_row_weights(widgets)

        fig = go.Figure()
        chart_annotations = []
        card_shapes = []

        # Add each widget with calculated domain
        for i, widget_spec in enumerate(widgets):
            pos = widget_spec.get("position", {})
            row = pos.get("row", 0)
            col = pos.get("col", 0)
            rowspan = pos.get("rowspan", 1)
            colspan = pos.get("colspan", 1)

            # Calculate domain for this widget
            x_domain, y_domain = self._calculate_domain(row, col, rowspan, colspan)

            if self.show_cards:
                card_pad_x = max(0.003, self.h_spacing * 0.20)
                card_pad_y = max(0.004, self.v_spacing * 0.20)
                card_shapes.append(dict(
                    type="rect",
                    xref="paper",
                    yref="paper",
                    x0=max(0.0, x_domain[0] - card_pad_x),
                    x1=min(1.0, x_domain[1] + card_pad_x),
                    y0=max(0.0, y_domain[0] - card_pad_y),
                    y1=min(1.0, y_domain[1] + card_pad_y),
                    fillcolor=self.theme["colors"].get("surface", self.theme["colors"]["background"]),
                    line=dict(
                        color=self.theme["colors"].get("card_border", self.theme["colors"]["grid"]),
                        width=1,
                    ),
                    layer="below",
                ))

            # Create widget figure
            widget_fig = self._create_widget_figure(widget_spec)

            # Extract chart title from widget config for charts
            widget_type = widget_spec.get("type")
            if widget_type == "chart":
                chart_title = widget_spec.get("config", {}).get("title")
                if chart_title:
                    # Add title as annotation above the chart
                    chart_title_size = int(15 * self.font_scale)
                    title_offset = max(0.010, self.v_spacing * 0.30)
                    chart_annotations.append(dict(
                        text=f"<b>{chart_title}</b>",
                        x=x_domain[0] + 0.004,
                        y=y_domain[1] + title_offset,
                        xref="paper",
                        yref="paper",
                        showarrow=False,
                        font=dict(
                            size=chart_title_size,
                            color=self.theme["colors"]["text"],
                            family=self.theme["fonts"]["title"],
                        ),
                        xanchor="left",
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
                        showgrid=self.theme.get("chart", {}).get("gridlines", True),
                        gridcolor=self.theme["colors"]["grid"],
                        gridwidth=1,
                        showline=False,
                        zeroline=False,
                        ticks="",
                        automargin=True,
                        tickfont=dict(
                            color=self.theme["colors"]["text_secondary"],
                            size=tick_font_size,
                        ),
                        title=dict(
                            font=dict(size=axis_title_size, color=self.theme["colors"]["text_secondary"])
                        ),
                    )
                    fig.layout[y_axis_key] = dict(
                        domain=y_domain,
                        anchor=f"x{axis_suffix}" if axis_suffix else "x",
                        showgrid=self.theme.get("chart", {}).get("gridlines", True),
                        gridcolor=self.theme["colors"]["grid"],
                        gridwidth=1,
                        showline=False,
                        zeroline=False,
                        ticks="",
                        automargin=True,
                        tickfont=dict(
                            color=self.theme["colors"]["text_secondary"],
                            size=tick_font_size,
                        ),
                        title=dict(
                            font=dict(size=axis_title_size, color=self.theme["colors"]["text_secondary"])
                        ),
                    )

                fig.add_trace(trace)

        named_trace_count = sum(
            1
            for trace in fig.data
            if getattr(trace, "name", None) not in (None, "", " ")
        )
        show_legend = self.show_legend if self.show_legend is not None else named_trace_count > 1

        # Apply theme and title
        layout_updates = {
            "paper_bgcolor": self.theme["colors"]["background"],
            "plot_bgcolor": self.theme["colors"]["background"],
            "font": {
                "family": self.theme["fonts"]["body"],
                "color": self.theme["colors"]["text"],
                "size": int(13 * self.font_scale),
            },
            "showlegend": show_legend,
            "margin": dict(l=36, r=28, t=74 if self.title else 34, b=34),
        }

        if self.title:
            layout_updates["title"] = dict(
                text=self.title,
                x=0.02,
                xanchor="left",
                y=0.985,
                yanchor="top",
                font=dict(
                    size=self.title_size,
                    color=self.theme["colors"]["text"],
                    family=self.theme["fonts"]["title"],
                ),
            )

        if show_legend:
            layout_updates["legend"] = dict(
                orientation="h",
                yanchor="bottom",
                y=1.01,
                xanchor="left",
                x=0.02,
                font=dict(size=int(11 * self.font_scale), color=self.theme["colors"]["text_secondary"]),
                bgcolor="rgba(0,0,0,0)",
            )

        if card_shapes:
            layout_updates["shapes"] = card_shapes

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
