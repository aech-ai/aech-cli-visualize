"""Correction engine for translating VLM feedback to spec modifications."""

import copy
from typing import Any

from .models import LayoutCorrection, LayoutIssue, ValidationResult


class CorrectionEngine:
    """Translates VLM validation issues into concrete spec corrections."""

    def __init__(self, max_grid_rows: int = 6, max_grid_columns: int = 24):
        """Initialize the correction engine.

        Args:
            max_grid_rows: Maximum rows to expand grid to
            max_grid_columns: Maximum columns to expand grid to
        """
        self.max_grid_rows = max_grid_rows
        self.max_grid_columns = max_grid_columns

    def compute_corrections(
        self,
        result: ValidationResult,
        spec: dict[str, Any],
    ) -> list[LayoutCorrection]:
        """Compute corrections based on validation result.

        Args:
            result: VLM validation result with issues
            spec: Current dashboard spec

        Returns:
            List of corrections to apply
        """
        corrections: list[LayoutCorrection] = []

        # Sort issues by severity (critical first)
        severity_order = {"critical": 0, "major": 1, "minor": 2}
        sorted_issues = sorted(
            result.issues,
            key=lambda x: severity_order.get(x.severity, 3),
        )

        for issue in sorted_issues:
            correction = self._issue_to_correction(issue, spec)
            if correction:
                corrections.append(correction)

        return corrections

    def _issue_to_correction(
        self,
        issue: LayoutIssue,
        spec: dict[str, Any],
    ) -> LayoutCorrection | None:
        """Map a single issue to a correction.

        Args:
            issue: The layout issue to fix
            spec: Current dashboard spec

        Returns:
            Correction to apply, or None if no correction available
        """
        layout = spec.get("layout", {})
        current_rows = layout.get("rows", 2)
        current_cols = layout.get("columns", 12)
        current_padding = layout.get("padding", 20)

        if issue.issue_type == "overlap":
            # Try increasing rows first, then columns
            if current_rows < self.max_grid_rows:
                return LayoutCorrection(
                    action="increase_rows",
                    target="layout",
                    parameters={"rows": current_rows + 1},
                )
            elif current_cols < self.max_grid_columns:
                return LayoutCorrection(
                    action="increase_columns",
                    target="layout",
                    parameters={"columns": current_cols + 2},
                )
            # Last resort: reduce spans of affected widgets
            elif issue.affected_widgets:
                return self._reduce_widget_spans(issue.affected_widgets, spec)

        elif issue.issue_type == "spacing":
            # Adjust padding based on whether things are too close or too far
            if "too close" in issue.description.lower() or "cramped" in issue.description.lower():
                return LayoutCorrection(
                    action="adjust_padding",
                    target="layout",
                    parameters={"padding": current_padding + 10},
                )
            elif "too far" in issue.description.lower() or "wasted" in issue.description.lower():
                new_padding = max(10, current_padding - 10)
                return LayoutCorrection(
                    action="adjust_padding",
                    target="layout",
                    parameters={"padding": new_padding},
                )

        elif issue.issue_type == "truncation":
            # Increase span of affected widgets
            if issue.affected_widgets:
                return self._increase_widget_spans(issue.affected_widgets, spec)

        elif issue.issue_type == "sizing":
            # Similar to truncation - increase affected widget sizes
            if issue.affected_widgets:
                return self._increase_widget_spans(issue.affected_widgets, spec)

        elif issue.issue_type == "alignment":
            # Add rows to give more room for alignment
            if current_rows < self.max_grid_rows:
                return LayoutCorrection(
                    action="increase_rows",
                    target="layout",
                    parameters={"rows": current_rows + 1},
                )

        elif issue.issue_type == "readability":
            # Increase grid size to give widgets more room
            if current_rows < self.max_grid_rows:
                return LayoutCorrection(
                    action="increase_rows",
                    target="layout",
                    parameters={"rows": current_rows + 1},
                )

        return None

    def _reduce_widget_spans(
        self,
        widget_indices: list[int],
        spec: dict[str, Any],
    ) -> LayoutCorrection | None:
        """Create correction to reduce spans of overlapping widgets.

        Args:
            widget_indices: Indices of widgets to adjust
            spec: Current dashboard spec

        Returns:
            Correction to reduce spans, or None
        """
        widgets = spec.get("widgets", [])
        if not widget_indices or not widgets:
            return None

        # Find the first widget that can have its span reduced
        for idx in widget_indices:
            if idx >= len(widgets):
                continue
            widget = widgets[idx]
            pos = widget.get("position", {})
            colspan = pos.get("colspan", 1)
            rowspan = pos.get("rowspan", 1)

            if colspan > 1:
                return LayoutCorrection(
                    action="adjust_span",
                    target=f"widgets[{idx}]",
                    parameters={"colspan": colspan - 1},
                )
            elif rowspan > 1:
                return LayoutCorrection(
                    action="adjust_span",
                    target=f"widgets[{idx}]",
                    parameters={"rowspan": rowspan - 1},
                )

        return None

    def _increase_widget_spans(
        self,
        widget_indices: list[int],
        spec: dict[str, Any],
    ) -> LayoutCorrection | None:
        """Create correction to increase spans of undersized widgets.

        Args:
            widget_indices: Indices of widgets to adjust
            spec: Current dashboard spec

        Returns:
            Correction to increase spans, or None
        """
        widgets = spec.get("widgets", [])
        layout = spec.get("layout", {})
        max_cols = layout.get("columns", 12)
        max_rows = layout.get("rows", 2)

        if not widget_indices or not widgets:
            return None

        # Find the first widget that can have its span increased
        for idx in widget_indices:
            if idx >= len(widgets):
                continue
            widget = widgets[idx]
            pos = widget.get("position", {})
            col = pos.get("col", 0)
            row = pos.get("row", 0)
            colspan = pos.get("colspan", 1)
            rowspan = pos.get("rowspan", 1)

            # Try increasing colspan if room available
            if col + colspan < max_cols:
                return LayoutCorrection(
                    action="adjust_span",
                    target=f"widgets[{idx}]",
                    parameters={"colspan": colspan + 1},
                )
            # Try increasing rowspan if room available
            elif row + rowspan < max_rows:
                return LayoutCorrection(
                    action="adjust_span",
                    target=f"widgets[{idx}]",
                    parameters={"rowspan": rowspan + 1},
                )

        return None

    def apply_corrections(
        self,
        spec: dict[str, Any],
        corrections: list[LayoutCorrection],
    ) -> dict[str, Any]:
        """Apply corrections to a spec, returning a modified copy.

        Args:
            spec: Original dashboard spec
            corrections: List of corrections to apply

        Returns:
            New spec with corrections applied
        """
        new_spec = copy.deepcopy(spec)

        for correction in corrections:
            new_spec = self._apply_single_correction(new_spec, correction)

        return new_spec

    def _apply_single_correction(
        self,
        spec: dict[str, Any],
        correction: LayoutCorrection,
    ) -> dict[str, Any]:
        """Apply a single correction to the spec.

        Args:
            spec: Dashboard spec to modify
            correction: Correction to apply

        Returns:
            Modified spec
        """
        if correction.target == "layout":
            if "layout" not in spec:
                spec["layout"] = {}

            if correction.action == "increase_rows":
                spec["layout"]["rows"] = correction.parameters.get(
                    "rows", spec["layout"].get("rows", 2) + 1
                )

            elif correction.action == "increase_columns":
                spec["layout"]["columns"] = correction.parameters.get(
                    "columns", spec["layout"].get("columns", 12) + 2
                )

            elif correction.action == "adjust_padding":
                spec["layout"]["padding"] = correction.parameters.get(
                    "padding", spec["layout"].get("padding", 20)
                )

        elif correction.target.startswith("widgets["):
            # Parse widget index from target like "widgets[0]"
            try:
                idx_str = correction.target.split("[")[1].rstrip("]")
                idx = int(idx_str)
                widgets = spec.get("widgets", [])

                if 0 <= idx < len(widgets):
                    widget = widgets[idx]
                    if "position" not in widget:
                        widget["position"] = {}

                    if correction.action == "adjust_span":
                        if "colspan" in correction.parameters:
                            widget["position"]["colspan"] = correction.parameters["colspan"]
                        if "rowspan" in correction.parameters:
                            widget["position"]["rowspan"] = correction.parameters["rowspan"]

            except (IndexError, ValueError):
                pass  # Invalid target, skip

        return spec
