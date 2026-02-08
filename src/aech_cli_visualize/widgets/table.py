"""Table widget for rendering data tables as images."""

from typing import Any

import plotly.graph_objects as go

from .base import BaseWidget


class TableWidget(BaseWidget):
    """Widget for rendering styled data tables."""

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
        headers: list[str],
        rows: list[list[Any]],
        title: str | None = None,
        column_widths: list[int] | None = None,
        highlight_column: int | None = None,
        alternating_rows: bool = True,
        theme: str | dict[str, Any] = "corporate",
    ):
        """Initialize table widget.

        Args:
            headers: Column header labels
            rows: List of row data (each row is a list of values)
            title: Optional table title
            column_widths: Relative column widths
            highlight_column: Index of column to highlight
            alternating_rows: Whether to use alternating row colors
            theme: Theme name or dictionary
        """
        config = {
            "headers": headers,
            "rows": rows,
            "title": title,
            "column_widths": column_widths,
            "highlight_column": highlight_column,
            "alternating_rows": alternating_rows,
        }
        super().__init__(config, theme)

    def create_figure(self) -> go.Figure:
        """Create the table figure."""
        headers = self.config["headers"]
        rows = self.config["rows"]
        colors = self.theme["colors"]
        font_scale = self.config.get("font_scale", 1.0)

        # Transpose rows to columns for Plotly
        columns = list(zip(*rows)) if rows else [[] for _ in headers]

        # Generate cell colors
        cell_colors = self._get_cell_colors(len(rows), len(headers))
        header_colors = self._get_header_colors(len(headers))
        header_font_size = int(13 * font_scale)
        cell_font_size = int(12 * font_scale)
        row_height = int(34 * font_scale)
        header_height = int(38 * font_scale)

        fig = go.Figure(data=[
            go.Table(
                columnwidth=self.config.get("column_widths"),
                header=dict(
                    values=[f"<b>{h}</b>" for h in headers],
                    fill_color=header_colors,
                    align="left",
                    line=dict(color=colors["grid"], width=1),
                    font=dict(
                        color=colors["text"],
                        size=header_font_size,
                        family=self.theme["fonts"]["title"],
                    ),
                    height=header_height,
                ),
                cells=dict(
                    values=columns,
                    fill_color=cell_colors,
                    align="left",
                    line=dict(color=colors["grid"], width=1),
                    font=dict(
                        color=colors["text"],
                        size=cell_font_size,
                        family=self.theme["fonts"]["body"],
                    ),
                    height=row_height,
                ),
            )
        ])

        # Add title if present
        layout_updates = {
            "margin": dict(l=12, r=12, t=54 if self.config["title"] else 16, b=12),
            "paper_bgcolor": colors.get("surface", colors["background"]),
            "plot_bgcolor": colors.get("surface", colors["background"]),
        }

        if self.config["title"]:
            layout_updates["title"] = dict(
                text=self.config["title"],
                x=0.02,
                xanchor="left",
                y=0.98,
                yanchor="top",
                font=dict(size=int(16 * font_scale), color=colors["text"]),
            )

        fig.update_layout(**layout_updates)

        return fig

    def _get_header_colors(self, num_cols: int) -> list[str]:
        """Get header background colors."""
        colors = self.theme["colors"]
        highlight_col = self.config.get("highlight_column")

        header_colors = [colors["surface"]] * num_cols

        if highlight_col is not None and 0 <= highlight_col < num_cols:
            header_colors[highlight_col] = self._hex_to_rgba(colors["secondary"], 0.14)

        return header_colors

    def _get_cell_colors(self, num_rows: int, num_cols: int) -> list[list[str]]:
        """Get cell background colors for each column."""
        colors = self.theme["colors"]
        alternating = self.config.get("alternating_rows", True)
        highlight_col = self.config.get("highlight_column")

        # Base colors for alternating rows
        if alternating:
            base_colors = [
                colors["surface"] if i % 2 == 0 else self._hex_to_rgba(colors["grid"], 0.18)
                for i in range(num_rows)
            ]
        else:
            base_colors = [colors["surface"]] * num_rows

        # Create color matrix (one list per column)
        cell_colors = [base_colors.copy() for _ in range(num_cols)]

        # Apply highlight to specific column
        if highlight_col is not None and 0 <= highlight_col < num_cols:
            # Slightly tint the highlight column
            highlight_base = self._hex_to_rgba(colors["secondary"], 0.08)
            cell_colors[highlight_col] = [highlight_base] * num_rows

        return cell_colors
