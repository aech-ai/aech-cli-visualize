"""Table widget for rendering data tables as images."""

from typing import Any

import plotly.graph_objects as go

from .base import BaseWidget


class TableWidget(BaseWidget):
    """Widget for rendering styled data tables."""

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

        # Transpose rows to columns for Plotly
        columns = list(zip(*rows)) if rows else [[] for _ in headers]

        # Generate cell colors
        cell_colors = self._get_cell_colors(len(rows), len(headers))
        header_colors = self._get_header_colors(len(headers))

        fig = go.Figure(data=[
            go.Table(
                columnwidth=self.config.get("column_widths"),
                header=dict(
                    values=[f"<b>{h}</b>" for h in headers],
                    fill_color=header_colors,
                    align="left",
                    font=dict(
                        color=colors["background"],
                        size=14,
                        family=self.theme["fonts"]["title"],
                    ),
                    height=40,
                ),
                cells=dict(
                    values=columns,
                    fill_color=cell_colors,
                    align="left",
                    font=dict(
                        color=colors["text"],
                        size=13,
                        family=self.theme["fonts"]["body"],
                    ),
                    height=35,
                ),
            )
        ])

        # Add title if present
        layout_updates = {
            "margin": dict(l=20, r=20, t=60 if self.config["title"] else 20, b=20),
        }

        if self.config["title"]:
            layout_updates["title"] = dict(
                text=self.config["title"],
                x=0.5,
                xanchor="center",
                font=dict(size=20, color=colors["text"]),
            )

        fig.update_layout(**layout_updates)

        return fig

    def _get_header_colors(self, num_cols: int) -> list[str]:
        """Get header background colors."""
        colors = self.theme["colors"]
        highlight_col = self.config.get("highlight_column")

        header_colors = [colors["primary"]] * num_cols

        if highlight_col is not None and 0 <= highlight_col < num_cols:
            header_colors[highlight_col] = colors["secondary"]

        return header_colors

    def _get_cell_colors(self, num_rows: int, num_cols: int) -> list[list[str]]:
        """Get cell background colors for each column."""
        colors = self.theme["colors"]
        alternating = self.config.get("alternating_rows", True)
        highlight_col = self.config.get("highlight_column")

        # Base colors for alternating rows
        if alternating:
            base_colors = [
                colors["background"] if i % 2 == 0 else colors["surface"]
                for i in range(num_rows)
            ]
        else:
            base_colors = [colors["background"]] * num_rows

        # Create color matrix (one list per column)
        cell_colors = [base_colors.copy() for _ in range(num_cols)]

        # Apply highlight to specific column
        if highlight_col is not None and 0 <= highlight_col < num_cols:
            # Slightly tint the highlight column
            highlight_base = colors["surface"]
            cell_colors[highlight_col] = [highlight_base] * num_rows

        return cell_colors
