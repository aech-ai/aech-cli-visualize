"""Delight rendering backend (Vega-Lite + canvas primitives)."""

from .chart_renderer import render_chart_image, render_chart_file
from .dashboard_composer import DelightDashboardComposer
from .visual_modes import get_available_visual_modes, get_visual_mode_profile, normalize_visual_mode

__all__ = [
    "render_chart_image",
    "render_chart_file",
    "DelightDashboardComposer",
    "get_available_visual_modes",
    "get_visual_mode_profile",
    "normalize_visual_mode",
]
