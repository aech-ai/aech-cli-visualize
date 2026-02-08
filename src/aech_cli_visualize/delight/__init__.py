"""Delight rendering backend (Vega-Lite + canvas primitives)."""

from .chart_renderer import render_chart_image, render_chart_file
from .dashboard_composer import DelightDashboardComposer

__all__ = ["render_chart_image", "render_chart_file", "DelightDashboardComposer"]
