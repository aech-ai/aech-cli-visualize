"""Delight chart renderer built on Vega-Lite + vl-convert."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from ..themes.loader import load_theme
from ..utils.export import FormatType


def _import_vl_convert() -> Any:
    """Import vl_convert with a clear dependency error."""
    try:
        import vl_convert as vlc  # type: ignore
    except ImportError as exc:  # pragma: no cover - runtime dependency check
        raise RuntimeError(
            "Delight backend requires 'vl-convert-python'. Install dependencies and retry."
        ) from exc
    return vlc


def _import_pillow_image() -> Any:
    """Import PIL.Image with a clear dependency error."""
    try:
        from PIL import Image  # type: ignore
    except ImportError as exc:  # pragma: no cover - runtime dependency check
        raise RuntimeError(
            "Delight backend requires 'Pillow'. Install dependencies and retry."
        ) from exc
    return Image


def _primary_font(theme: dict[str, Any], key: str) -> str:
    """Extract the first font in a CSS fallback stack."""
    stack = theme.get("fonts", {}).get(key, "Arial")
    if not isinstance(stack, str):
        return "Arial"
    return stack.split(",")[0].strip().strip('"').strip("'")


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert #RRGGBB into an RGB tuple."""
    value = str(hex_color).strip().lstrip("#")
    if len(value) != 6:
        return (0, 0, 0)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (0, 0, 0)


def _mix_hex(a: str, b: str, ratio: float) -> str:
    """Blend two hex colors and return a hex color string."""
    ratio = max(0.0, min(1.0, ratio))
    a_rgb = _hex_to_rgb(a)
    b_rgb = _hex_to_rgb(b)
    mixed = tuple(int((a_rgb[i] * (1.0 - ratio)) + (b_rgb[i] * ratio)) for i in range(3))
    return f"#{mixed[0]:02x}{mixed[1]:02x}{mixed[2]:02x}"


def _looks_temporal(value: Any) -> bool:
    """Best-effort temporal detection for common ISO-like formats."""
    if isinstance(value, (int, float)):
        return False
    if not isinstance(value, str):
        return False

    text = value.strip()
    if not text:
        return False

    # Common month labels should remain ordinal to preserve provided order.
    lowered = text.lower()
    if lowered in {
        "jan", "january", "feb", "february", "mar", "march", "apr", "april",
        "may", "jun", "june", "jul", "july", "aug", "august", "sep", "sept",
        "september", "oct", "october", "nov", "november", "dec", "december",
        "q1", "q2", "q3", "q4",
    }:
        return False

    parse_formats = (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d",
    )
    for fmt in parse_formats:
        try:
            datetime.strptime(text, fmt)
            return True
        except ValueError:
            continue

    # fromisoformat catches additional subsecond variants
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _infer_x_type(values: list[Any]) -> str:
    """Infer a sensible Vega-Lite type for x values."""
    if not values:
        return "ordinal"
    if all(isinstance(v, (int, float)) for v in values):
        return "quantitative"
    temporal_count = sum(1 for v in values if _looks_temporal(v))
    if temporal_count / max(len(values), 1) >= 0.8:
        return "temporal"
    return "ordinal"


def _base_spec(
    width: int,
    height: int,
    theme: dict[str, Any],
    show_legend: bool,
    embedded: bool = False,
) -> dict[str, Any]:
    """Create a base Vega-Lite spec with consistent delight styling."""
    colors = theme["colors"]
    chart = theme.get("chart", {})
    palette = chart.get("palette", [colors["primary"]])
    grid_color = _mix_hex(colors.get("grid", "#d7deea"), colors.get("background", "#ffffff"), 0.22)

    spec: dict[str, Any] = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "width": max(120, int(width)),
        "height": max(120, int(height)),
        "background": colors.get("surface", colors["background"]),
        "config": {
            "font": _primary_font(theme, "body"),
            "title": {
                "font": _primary_font(theme, "title"),
                "fontSize": 20,
                "anchor": "start",
                "color": colors["text"],
                "offset": 14,
            },
            "axis": {
                "domain": False,
                "ticks": False,
                "labelColor": colors["text_secondary"],
                "titleColor": colors["text_secondary"],
                "labelFontSize": 12,
                "titleFontSize": 12,
                "grid": False,
                "gridColor": grid_color,
                "gridWidth": 1,
                "labelPadding": 8,
            },
            "axisX": {
                "grid": False,
                "labelAngle": 0,
                "labelLimit": 130,
            },
            "axisY": {
                "grid": chart.get("gridlines", True),
                "tickCount": 6,
            },
            "legend": {
                "disable": not show_legend,
                "labelColor": colors["text_secondary"],
                "titleColor": colors["text_secondary"],
                "labelFontSize": 12,
                "titleFontSize": 12,
                "orient": "top",
            },
            "view": {
                "stroke": None if embedded else colors.get("card_border", colors["grid"]),
                "strokeWidth": 0 if embedded else 1,
                "cornerRadius": int(chart.get("border_radius", 10)),
            },
            "range": {
                "category": palette,
            },
        },
    }
    if embedded:
        spec["background"] = None
    return spec


def _compute_numeric_domain(values: list[Any]) -> list[float] | None:
    """Compute a padded numeric domain for better focus on trend data."""
    numeric: list[float] = []
    for value in values:
        if isinstance(value, (int, float)):
            numeric.append(float(value))
    if len(numeric) < 2:
        return None

    low = min(numeric)
    high = max(numeric)
    if low == high:
        pad = abs(low) * 0.05 if low else 1.0
        return [low - pad, high + pad]

    span = high - low
    pad = span * 0.12
    domain_low = low - pad
    domain_high = high + pad

    # Keep zero if values cross it; otherwise focus tightly around observed range.
    if low >= 0 and domain_low < 0:
        domain_low = max(0.0, low - (span * 0.04))
    return [domain_low, domain_high]


def _records_single_series(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert {x, y} into tabular records."""
    x_values = data.get("x", [])
    y_values = data.get("y", [])
    if not isinstance(x_values, list) or not isinstance(y_values, list):
        return []
    length = min(len(x_values), len(y_values))
    return [{"x": x_values[i], "y": y_values[i], "order": i} for i in range(length)]


def _records_multi_series(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert {x, series:[{name, values}]} into tabular records."""
    x_values = data.get("x", [])
    series_list = data.get("series", [])
    if not isinstance(x_values, list) or not isinstance(series_list, list):
        return []

    records: list[dict[str, Any]] = []
    for series in series_list:
        if not isinstance(series, dict):
            continue
        name = str(series.get("name", "Series"))
        values = series.get("values", [])
        if not isinstance(values, list):
            continue
        length = min(len(x_values), len(values))
        for i in range(length):
            records.append(
                {"x": x_values[i], "value": values[i], "series": name, "order": i}
            )
    return records


def _records_heatmap(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert heatmap matrix into records."""
    z_values = data.get("z", data.get("values", []))
    if not isinstance(z_values, list):
        return []

    x_values = data.get("x")
    y_values = data.get("y")

    records: list[dict[str, Any]] = []
    for row_idx, row in enumerate(z_values):
        if not isinstance(row, list):
            continue
        for col_idx, cell in enumerate(row):
            x_label = x_values[col_idx] if isinstance(x_values, list) and col_idx < len(x_values) else col_idx
            y_label = y_values[row_idx] if isinstance(y_values, list) and row_idx < len(y_values) else row_idx
            records.append({"x": x_label, "y": y_label, "value": cell})
    return records


def _records_pie(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert pie inputs into records."""
    labels = data.get("x", data.get("labels", []))
    values = data.get("y", data.get("values", []))
    if not isinstance(labels, list) or not isinstance(values, list):
        return []
    length = min(len(labels), len(values))
    return [{"category": labels[i], "value": values[i]} for i in range(length)]


def build_chart_spec(
    chart_type: str,
    data: dict[str, Any],
    width: int,
    height: int,
    theme: str | dict[str, Any] = "modern",
    title: str | None = None,
    show_legend: bool = True,
    embedded: bool = False,
) -> dict[str, Any]:
    """Build a Vega-Lite spec for a supported chart type."""
    theme_data = load_theme(theme) if isinstance(theme, str) else theme
    palette = theme_data.get("chart", {}).get("palette", [theme_data["colors"]["primary"]])
    spec = _base_spec(
        width=width,
        height=height,
        theme=theme_data,
        show_legend=show_legend,
        embedded=embedded,
    )
    if title:
        spec["title"] = title

    x_values = data.get("x", [])
    x_type = _infer_x_type(x_values if isinstance(x_values, list) else [])
    y_domain: list[float] | None = None
    if chart_type in ("line", "area"):
        if isinstance(data.get("series"), list):
            all_values: list[Any] = []
            for series in data.get("series", []):
                if isinstance(series, dict) and isinstance(series.get("values"), list):
                    all_values.extend(series.get("values", []))
            y_domain = _compute_numeric_domain(all_values)
        else:
            y_domain = _compute_numeric_domain(data.get("y", []) if isinstance(data.get("y"), list) else [])

    if chart_type == "bar":
        multi_series = isinstance(data.get("series"), list)
        if multi_series:
            records = _records_multi_series(data)
            spec.update(
                {
                    "data": {"values": records},
                    "mark": {"type": "bar", "cornerRadiusTopLeft": 6, "cornerRadiusTopRight": 6},
                    "encoding": {
                        "x": {
                            "field": "x",
                            "type": "ordinal",
                            "sort": None,
                            "axis": {"title": None},
                            "scale": {"paddingInner": 0.24, "paddingOuter": 0.08},
                        },
                        "xOffset": {"field": "series"},
                        "y": {
                            "field": "value",
                            "type": "quantitative",
                            "axis": {"title": None, "format": "~s"},
                            "scale": {"zero": True, "nice": True},
                        },
                        "color": {"field": "series", "type": "nominal", "legend": {"title": None}},
                        "tooltip": [
                            {"field": "x", "type": "ordinal", "title": "Category"},
                            {"field": "series", "type": "nominal", "title": "Series"},
                            {"field": "value", "type": "quantitative", "title": "Value", "format": ",.2~s"},
                        ],
                    },
                }
            )
        else:
            records = _records_single_series(data)
            spec.update(
                {
                    "data": {"values": records},
                    "mark": {
                        "type": "bar",
                        "cornerRadiusTopLeft": 6,
                        "cornerRadiusTopRight": 6,
                        "color": palette[0],
                    },
                    "encoding": {
                        "x": {
                            "field": "x",
                            "type": "ordinal",
                            "sort": None,
                            "axis": {"title": None},
                            "scale": {"paddingInner": 0.24, "paddingOuter": 0.08},
                        },
                        "y": {
                            "field": "y",
                            "type": "quantitative",
                            "axis": {"title": None, "format": "~s"},
                            "scale": {"zero": True, "nice": True},
                        },
                        "tooltip": [
                            {"field": "x", "type": "ordinal", "title": "Category"},
                            {"field": "y", "type": "quantitative", "title": "Value", "format": ",.2~s"},
                        ],
                    },
                }
            )
    elif chart_type == "line":
        multi_series = isinstance(data.get("series"), list)
        if multi_series:
            records = _records_multi_series(data)
            spec.update(
                {
                    "data": {"values": records},
                    "mark": {
                        "type": "line",
                        "strokeWidth": 3,
                        "interpolate": "monotone",
                        "point": {"filled": True, "size": 52},
                    },
                    "encoding": {
                        "x": {"field": "x", "type": x_type, "sort": None, "axis": {"title": None, "labelAngle": 0}},
                        "y": {
                            "field": "value",
                            "type": "quantitative",
                            "axis": {"title": None, "format": "~s"},
                            "scale": (
                                {"domain": y_domain, "nice": True}
                                if y_domain
                                else {"zero": False, "nice": True}
                            ),
                        },
                        "color": {"field": "series", "type": "nominal", "legend": {"title": None}},
                        "tooltip": [
                            {"field": "series", "type": "nominal", "title": "Series"},
                            {"field": "x", "type": x_type, "title": "X"},
                            {"field": "value", "type": "quantitative", "title": "Value", "format": ",.2~s"},
                        ],
                    },
                }
            )
        else:
            records = _records_single_series(data)
            spec.update(
                {
                    "data": {"values": records},
                    "mark": {
                        "type": "line",
                        "strokeWidth": 3,
                        "interpolate": "monotone",
                        "point": {"filled": True, "size": 52},
                        "color": palette[0],
                    },
                    "encoding": {
                        "x": {"field": "x", "type": x_type, "sort": None, "axis": {"title": None, "labelAngle": 0}},
                        "y": {
                            "field": "y",
                            "type": "quantitative",
                            "axis": {"title": None, "format": "~s"},
                            "scale": (
                                {"domain": y_domain, "nice": True}
                                if y_domain
                                else {"zero": False, "nice": True}
                            ),
                        },
                        "tooltip": [
                            {"field": "x", "type": x_type, "title": "X"},
                            {"field": "y", "type": "quantitative", "title": "Value", "format": ",.2~s"},
                        ],
                    },
                }
            )
    elif chart_type == "area":
        records = _records_single_series(data)
        spec.update(
            {
                "data": {"values": records},
                "mark": {
                    "type": "area",
                    "line": {"color": palette[0], "strokeWidth": 2.5},
                    "opacity": 0.2,
                    "color": palette[0],
                    "interpolate": "monotone",
                },
                "encoding": {
                    "x": {"field": "x", "type": x_type, "sort": None, "axis": {"title": None, "labelAngle": 0}},
                    "y": {
                        "field": "y",
                        "type": "quantitative",
                        "axis": {"title": None, "format": "~s"},
                        "scale": (
                            {"domain": y_domain, "nice": True}
                            if y_domain
                            else {"zero": False, "nice": True}
                        ),
                    },
                    "tooltip": [
                        {"field": "x", "type": x_type, "title": "X"},
                        {"field": "y", "type": "quantitative", "title": "Value", "format": ",.2~s"},
                    ],
                },
            }
        )
    elif chart_type == "scatter":
        records = _records_single_series(data)
        spec.update(
            {
                "data": {"values": records},
                "mark": {"type": "point", "filled": True, "size": 90, "color": palette[0], "opacity": 0.9},
                "encoding": {
                    "x": {
                        "field": "x",
                        "type": "quantitative",
                        "axis": {"title": None, "format": "~s"},
                        "scale": {"zero": False, "nice": True},
                    },
                    "y": {
                        "field": "y",
                        "type": "quantitative",
                        "axis": {"title": None, "format": "~s"},
                        "scale": {"zero": False, "nice": True},
                    },
                    "tooltip": [
                        {"field": "x", "type": "quantitative", "title": "X", "format": ",.2~s"},
                        {"field": "y", "type": "quantitative", "title": "Y", "format": ",.2~s"},
                    ],
                },
            }
        )
    elif chart_type == "heatmap":
        records = _records_heatmap(data)
        spec.update(
            {
                "data": {"values": records},
                "mark": {"type": "rect"},
                "encoding": {
                    "x": {"field": "x", "type": "ordinal", "axis": {"title": None, "labelAngle": 0}},
                    "y": {"field": "y", "type": "ordinal", "axis": {"title": None}},
                    "color": {
                        "field": "value",
                        "type": "quantitative",
                        "legend": {"title": None},
                    },
                    "tooltip": [
                        {"field": "x", "type": "ordinal", "title": "X"},
                        {"field": "y", "type": "ordinal", "title": "Y"},
                        {"field": "value", "type": "quantitative", "title": "Value", "format": ",.2~s"},
                    ],
                },
            }
        )
    elif chart_type == "pie":
        records = _records_pie(data)
        spec.update(
            {
                "data": {"values": records},
                "mark": {"type": "arc", "innerRadius": 58},
                "encoding": {
                    "theta": {"field": "value", "type": "quantitative"},
                    "color": {"field": "category", "type": "nominal", "legend": {"title": None}},
                    "tooltip": [
                        {"field": "category", "type": "nominal", "title": "Category"},
                        {"field": "value", "type": "quantitative", "title": "Value", "format": ",.2~s"},
                    ],
                },
                "view": {"stroke": None},
            }
        )
    else:
        raise ValueError(f"Unsupported chart type for delight backend: {chart_type}")

    return spec


def render_chart_image(
    chart_type: str,
    data: dict[str, Any],
    width: int,
    height: int,
    theme: str | dict[str, Any] = "modern",
    title: str | None = None,
    show_legend: bool = True,
    scale: float = 1.0,
    embedded: bool = False,
) -> Any:
    """Render a chart as a PIL image."""
    vlc = _import_vl_convert()
    Image = _import_pillow_image()

    spec = build_chart_spec(
        chart_type=chart_type,
        data=data,
        width=width,
        height=height,
        theme=theme,
        title=title,
        show_legend=show_legend,
        embedded=embedded,
    )
    png_bytes = vlc.vegalite_to_png(spec, scale=scale)
    return Image.open(BytesIO(png_bytes)).convert("RGBA")


def render_chart_file(
    chart_type: str,
    data: dict[str, Any],
    output_dir: str | Path,
    filename: str = "chart",
    format: FormatType = "png",
    width: int = 1920,
    height: int = 1080,
    theme: str | dict[str, Any] = "modern",
    title: str | None = None,
    show_legend: bool = True,
    scale: float = 1.0,
) -> Path:
    """Render a chart to a file path using the delight backend."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    file_path = output_path / f"{filename}.{format}"

    if format == "svg":
        vlc = _import_vl_convert()
        spec = build_chart_spec(
            chart_type=chart_type,
            data=data,
            width=width,
            height=height,
            theme=theme,
            title=title,
            show_legend=show_legend,
            embedded=False,
        )
        svg_text = vlc.vegalite_to_svg(spec)
        file_path.write_text(svg_text, encoding="utf-8")
        return file_path

    image = render_chart_image(
        chart_type=chart_type,
        data=data,
        width=width,
        height=height,
        theme=theme,
        title=title,
        show_legend=show_legend,
        scale=scale,
        embedded=False,
    )

    if format == "pdf":
        image.convert("RGB").save(file_path, "PDF", resolution=144.0)
    else:
        image.save(file_path, "PNG")

    return file_path
