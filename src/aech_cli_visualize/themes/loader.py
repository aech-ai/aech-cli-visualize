"""Theme loading and management."""

import json
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

# Directory containing built-in theme JSON files
THEMES_DIR = Path(__file__).parent / "builtin"

# Built-in theme definitions
BUILTIN_THEMES: dict[str, dict[str, Any]] = {
    "corporate": {
        "name": "corporate",
        "colors": {
            "primary": "#1f3b8f",
            "secondary": "#0ea5a4",
            "accent": "#f59e0b",
            "background": "#f3f6fb",
            "surface": "#ffffff",
            "text": "#0f172a",
            "text_secondary": "#475569",
            "grid": "#d7deea",
            "positive": "#16a34a",
            "negative": "#dc2626",
            "neutral": "#64748b",
            "card_border": "#d7deea",
        },
        "fonts": {
            "title": "Avenir Next, Segoe UI, Helvetica Neue, Arial, sans-serif",
            "body": "Avenir Next, Segoe UI, Helvetica Neue, Arial, sans-serif",
            "mono": "SFMono-Regular, Menlo, Consolas, monospace",
        },
        "chart": {
            "palette": ["#1f3b8f", "#0ea5a4", "#f59e0b", "#7c3aed", "#dc2626", "#2563eb", "#14b8a6"],
            "gridlines": True,
            "border_radius": 12,
            "line_width": 3,
            "marker_size": 7,
        },
    },
    "modern": {
        "name": "modern",
        "colors": {
            "primary": "#0f766e",
            "secondary": "#2563eb",
            "accent": "#f97316",
            "background": "#f6faf9",
            "surface": "#ffffff",
            "text": "#0f172a",
            "text_secondary": "#334155",
            "grid": "#dbe4ef",
            "positive": "#15803d",
            "negative": "#dc2626",
            "neutral": "#64748b",
            "card_border": "#dbe4ef",
        },
        "fonts": {
            "title": "Manrope, Avenir Next, Segoe UI, Helvetica Neue, Arial, sans-serif",
            "body": "Manrope, Avenir Next, Segoe UI, Helvetica Neue, Arial, sans-serif",
            "mono": "JetBrains Mono, SFMono-Regular, Menlo, monospace",
        },
        "chart": {
            "palette": ["#0f766e", "#2563eb", "#f97316", "#9333ea", "#dc2626", "#0891b2", "#ca8a04"],
            "gridlines": True,
            "border_radius": 12,
            "line_width": 3,
            "marker_size": 7,
        },
    },
    "minimal": {
        "name": "minimal",
        "colors": {
            "primary": "#000000",
            "secondary": "#404040",
            "accent": "#000000",
            "background": "#ffffff",
            "surface": "#fafafa",
            "text": "#000000",
            "text_secondary": "#666666",
            "grid": "#eeeeee",
            "positive": "#000000",
            "negative": "#666666",
            "neutral": "#999999",
            "card_border": "#e5e7eb",
        },
        "fonts": {
            "title": "IBM Plex Sans, Helvetica Neue, Arial, sans-serif",
            "body": "IBM Plex Sans, Helvetica Neue, Arial, sans-serif",
            "mono": "IBM Plex Mono, Monaco, monospace",
        },
        "chart": {
            "palette": ["#000000", "#404040", "#808080", "#a0a0a0", "#c0c0c0"],
            "gridlines": False,
            "border_radius": 0,
            "line_width": 2,
            "marker_size": 6,
        },
    },
    "dark": {
        "name": "dark",
        "colors": {
            "primary": "#60a5fa",
            "secondary": "#34d399",
            "accent": "#f59e0b",
            "background": "#0f172a",
            "surface": "#111827",
            "text": "#f8fafc",
            "text_secondary": "#94a3b8",
            "grid": "#334155",
            "positive": "#22c55e",
            "negative": "#f87171",
            "neutral": "#64748b",
            "card_border": "#334155",
        },
        "fonts": {
            "title": "Avenir Next, Segoe UI, Helvetica Neue, Arial, sans-serif",
            "body": "Avenir Next, Segoe UI, Helvetica Neue, Arial, sans-serif",
            "mono": "SFMono-Regular, Menlo, Consolas, monospace",
        },
        "chart": {
            "palette": ["#60a5fa", "#34d399", "#f59e0b", "#a78bfa", "#f87171", "#22d3ee", "#f97316"],
            "gridlines": True,
            "border_radius": 10,
            "line_width": 3,
            "marker_size": 7,
        },
    },
    "light": {
        "name": "light",
        "colors": {
            "primary": "#2563eb",
            "secondary": "#0284c7",
            "accent": "#16a34a",
            "background": "#ffffff",
            "surface": "#f8fafc",
            "text": "#111827",
            "text_secondary": "#475569",
            "grid": "#e2e8f0",
            "positive": "#16a34a",
            "negative": "#ef4444",
            "neutral": "#64748b",
            "card_border": "#e2e8f0",
        },
        "fonts": {
            "title": "Avenir Next, Segoe UI, Helvetica Neue, Arial, sans-serif",
            "body": "Avenir Next, Segoe UI, Helvetica Neue, Arial, sans-serif",
            "mono": "SFMono-Regular, Menlo, Consolas, monospace",
        },
        "chart": {
            "palette": ["#2563eb", "#0284c7", "#16a34a", "#f59e0b", "#ef4444", "#7c3aed", "#0ea5e9"],
            "gridlines": True,
            "border_radius": 10,
            "line_width": 3,
            "marker_size": 7,
        },
    },
}


def get_available_themes() -> list[str]:
    """Get list of available theme names."""
    return list(BUILTIN_THEMES.keys())


def load_theme(name: str) -> dict[str, Any]:
    """Load a theme by name or from file path.

    Args:
        name: Theme name (corporate, modern, minimal, dark, light) or path to JSON file

    Returns:
        Theme configuration dictionary
    """
    # Check built-in themes first
    if name.lower() in BUILTIN_THEMES:
        return BUILTIN_THEMES[name.lower()]

    # Check if it's a file path
    path = Path(name)
    if path.exists() and path.suffix == ".json":
        with open(path) as f:
            return json.load(f)

    raise ValueError(
        f"Theme not found: {name}. "
        f"Available themes: {', '.join(BUILTIN_THEMES.keys())}"
    )


def apply_theme_to_layout(theme: dict[str, Any]) -> dict[str, Any]:
    """Generate Plotly layout settings from theme.

    Args:
        theme: Theme configuration dictionary

    Returns:
        Dictionary of Plotly layout settings
    """
    colors = theme["colors"]
    fonts = theme["fonts"]
    chart = theme.get("chart", {})

    return {
        "paper_bgcolor": colors["background"],
        "plot_bgcolor": colors.get("surface", colors["background"]),
        "font": {
            "family": fonts["body"],
            "color": colors["text"],
        },
        "title": {
            "font": {
                "family": fonts["title"],
                "color": colors["text"],
                "size": 24,
            }
        },
        "xaxis": {
            "gridcolor": colors["grid"] if chart.get("gridlines", True) else "rgba(0,0,0,0)",
            "gridwidth": 1,
            "linecolor": colors["grid"],
            "showline": False,
            "zeroline": False,
            "tickfont": {"color": colors["text_secondary"]},
        },
        "yaxis": {
            "gridcolor": colors["grid"] if chart.get("gridlines", True) else "rgba(0,0,0,0)",
            "gridwidth": 1,
            "linecolor": colors["grid"],
            "showline": False,
            "zeroline": False,
            "tickfont": {"color": colors["text_secondary"]},
        },
        "colorway": chart.get("palette", [colors["primary"]]),
    }


def apply_theme_to_figure(fig: go.Figure, theme: dict[str, Any]) -> go.Figure:
    """Apply theme styling to a Plotly figure.

    Args:
        fig: Plotly figure to style
        theme: Theme configuration dictionary

    Returns:
        Styled figure
    """
    layout_settings = apply_theme_to_layout(theme)
    fig.update_layout(**layout_settings)
    return fig
