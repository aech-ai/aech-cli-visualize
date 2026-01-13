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
            "primary": "#1e3a5f",
            "secondary": "#4a90d9",
            "accent": "#2ecc71",
            "background": "#ffffff",
            "surface": "#f8f9fa",
            "text": "#2c3e50",
            "text_secondary": "#7f8c8d",
            "grid": "#ecf0f1",
            "positive": "#27ae60",
            "negative": "#e74c3c",
            "neutral": "#95a5a6",
        },
        "fonts": {
            "title": "Arial",
            "body": "Arial",
            "mono": "Consolas",
        },
        "chart": {
            "palette": ["#1e3a5f", "#4a90d9", "#2ecc71", "#f39c12", "#9b59b6", "#e74c3c", "#1abc9c"],
            "gridlines": True,
            "border_radius": 4,
        },
    },
    "modern": {
        "name": "modern",
        "colors": {
            "primary": "#6366f1",
            "secondary": "#8b5cf6",
            "accent": "#06b6d4",
            "background": "#ffffff",
            "surface": "#f1f5f9",
            "text": "#1e293b",
            "text_secondary": "#64748b",
            "grid": "#e2e8f0",
            "positive": "#22c55e",
            "negative": "#ef4444",
            "neutral": "#94a3b8",
        },
        "fonts": {
            "title": "Inter",
            "body": "Inter",
            "mono": "JetBrains Mono",
        },
        "chart": {
            "palette": ["#6366f1", "#8b5cf6", "#06b6d4", "#f59e0b", "#ec4899", "#14b8a6", "#f97316"],
            "gridlines": True,
            "border_radius": 8,
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
        },
        "fonts": {
            "title": "Helvetica",
            "body": "Helvetica",
            "mono": "Monaco",
        },
        "chart": {
            "palette": ["#000000", "#404040", "#808080", "#a0a0a0", "#c0c0c0"],
            "gridlines": False,
            "border_radius": 0,
        },
    },
    "dark": {
        "name": "dark",
        "colors": {
            "primary": "#60a5fa",
            "secondary": "#a78bfa",
            "accent": "#34d399",
            "background": "#1e1e1e",
            "surface": "#2d2d2d",
            "text": "#f5f5f5",
            "text_secondary": "#a3a3a3",
            "grid": "#404040",
            "positive": "#4ade80",
            "negative": "#f87171",
            "neutral": "#737373",
        },
        "fonts": {
            "title": "Arial",
            "body": "Arial",
            "mono": "Consolas",
        },
        "chart": {
            "palette": ["#60a5fa", "#a78bfa", "#34d399", "#fbbf24", "#f472b6", "#2dd4bf", "#fb923c"],
            "gridlines": True,
            "border_radius": 4,
        },
    },
    "light": {
        "name": "light",
        "colors": {
            "primary": "#3b82f6",
            "secondary": "#8b5cf6",
            "accent": "#10b981",
            "background": "#ffffff",
            "surface": "#f9fafb",
            "text": "#111827",
            "text_secondary": "#6b7280",
            "grid": "#e5e7eb",
            "positive": "#10b981",
            "negative": "#ef4444",
            "neutral": "#9ca3af",
        },
        "fonts": {
            "title": "Arial",
            "body": "Arial",
            "mono": "Consolas",
        },
        "chart": {
            "palette": ["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ec4899", "#14b8a6", "#f97316"],
            "gridlines": True,
            "border_radius": 6,
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
        "plot_bgcolor": colors["background"],
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
            "linecolor": colors["grid"],
            "tickfont": {"color": colors["text_secondary"]},
        },
        "yaxis": {
            "gridcolor": colors["grid"] if chart.get("gridlines", True) else "rgba(0,0,0,0)",
            "linecolor": colors["grid"],
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
