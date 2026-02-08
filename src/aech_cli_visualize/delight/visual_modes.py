"""Visual mode presets for the delight rendering backend."""

from __future__ import annotations

import copy
from typing import Any

_MODE_ALIASES = {
    "default": "premium_executive",
    "premium": "premium_executive",
    "premium-executive": "premium_executive",
    "executive": "premium_executive",
    "editorial": "editorial",
    "data_journal": "data_journal",
    "data-journal": "data_journal",
    "journal": "data_journal",
}

_MODE_PROFILES: dict[str, dict[str, Any]] = {
    "premium_executive": {
        "dashboard": {
            "font_scale": 1.0,
            "widget_padding": 18,
            "gradient_strength": 0.1,
            "card_radius": 22,
            "card_border_width": 1,
            "shadow_alpha": 26,
            "shadow_blur": 9,
            "shadow_offset_x": 2,
            "shadow_offset_y": 6,
            "title_size": 48,
            "title_weight_bold": True,
            "label_case": "title",
            "show_cards": True,
        },
        "chart": {
            "title_size": 20,
            "axis_label_size": 12,
            "axis_title_size": 12,
            "grid_mix": 0.22,
            "grid_width": 1,
            "grid_dash": [1, 0],
            "y_tick_count": 6,
            "line_width": 3,
            "line_interpolate": "monotone",
            "point_size": 52,
            "bar_radius": 6,
            "area_opacity": 0.18,
            "annotation_max": 3,
            "annotation_font_size": 12,
            "annotation_point_size": 95,
            "annotation_dx": 10,
            "annotation_dy": -10,
            "annotations": True,
        },
    },
    "editorial": {
        "dashboard": {
            "font_scale": 1.02,
            "widget_padding": 20,
            "gradient_strength": 0.0,
            "card_radius": 8,
            "card_border_width": 0,
            "shadow_alpha": 0,
            "shadow_blur": 0,
            "shadow_offset_x": 0,
            "shadow_offset_y": 0,
            "title_size": 52,
            "title_weight_bold": True,
            "label_case": "upper",
            "show_cards": True,
        },
        "chart": {
            "title_size": 21,
            "axis_label_size": 14,
            "axis_title_size": 12,
            "grid_mix": 0.48,
            "grid_width": 1,
            "grid_dash": [3, 3],
            "y_tick_count": 5,
            "line_width": 4.5,
            "line_interpolate": "linear",
            "point_size": 38,
            "bar_radius": 1,
            "area_opacity": 0.16,
            "annotation_max": 2,
            "annotation_font_size": 13,
            "annotation_point_size": 110,
            "annotation_dx": 10,
            "annotation_dy": -12,
            "annotations": True,
        },
    },
    "data_journal": {
        "dashboard": {
            "font_scale": 0.98,
            "widget_padding": 16,
            "gradient_strength": 0.0,
            "card_radius": 10,
            "card_border_width": 1,
            "shadow_alpha": 0,
            "shadow_blur": 0,
            "shadow_offset_x": 0,
            "shadow_offset_y": 0,
            "title_size": 44,
            "title_weight_bold": True,
            "label_case": "title",
            "show_cards": False,
        },
        "chart": {
            "title_size": 19,
            "axis_label_size": 12,
            "axis_title_size": 11,
            "grid_mix": 0.08,
            "grid_width": 1,
            "grid_dash": [1, 0],
            "y_tick_count": 8,
            "line_width": 2.2,
            "line_interpolate": "linear",
            "point_size": 34,
            "bar_radius": 0,
            "area_opacity": 0.12,
            "annotation_max": 4,
            "annotation_font_size": 11,
            "annotation_point_size": 80,
            "annotation_dx": 8,
            "annotation_dy": -9,
            "annotations": True,
        },
    },
}


def normalize_visual_mode(mode: str | None) -> str:
    """Resolve aliases and validate the visual mode name."""
    if mode is None:
        return "premium_executive"

    key = str(mode).strip().lower().replace(" ", "_")
    resolved = _MODE_ALIASES.get(key, key)
    if resolved not in _MODE_PROFILES:
        valid = ", ".join(sorted(_MODE_PROFILES))
        raise ValueError(f"Invalid visual mode: {mode}. Valid modes: {valid}")
    return resolved


def get_visual_mode_profile(mode: str | None) -> dict[str, Any]:
    """Return a deep-copied visual mode profile."""
    resolved = normalize_visual_mode(mode)
    return copy.deepcopy(_MODE_PROFILES[resolved])


def get_available_visual_modes() -> list[str]:
    """List canonical visual mode names."""
    return list(_MODE_PROFILES.keys())
