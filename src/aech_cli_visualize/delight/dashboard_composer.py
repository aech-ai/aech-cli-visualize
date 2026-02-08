"""Canvas-based dashboard composer for the delight backend."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..themes.loader import load_theme
from ..utils.export import FormatType, parse_resolution
from .chart_renderer import render_chart_image


def _import_pillow() -> tuple[Any, Any, Any, Any]:
    """Import Pillow modules with a clear dependency error."""
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont  # type: ignore
    except ImportError as exc:  # pragma: no cover - runtime dependency check
        raise RuntimeError(
            "Delight backend requires 'Pillow'. Install dependencies and retry."
        ) from exc
    return Image, ImageDraw, ImageFont, ImageFilter


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert #RRGGBB into RGB tuple."""
    value = hex_color.lstrip("#")
    if len(value) != 6:
        return (255, 255, 255)
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


class DelightDashboardComposer:
    """Compose dashboards with explicit canvas primitives and chart images."""

    _FONT_PATHS_REGULAR = [
        "/System/Library/Fonts/Supplemental/Avenir.ttc",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    _FONT_PATHS_BOLD = [
        "/System/Library/Fonts/Supplemental/Avenir.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ]

    def __init__(self, spec: dict[str, Any], theme: str | dict[str, Any] = "modern"):
        """Initialize delight composer."""
        self.spec = spec
        self.theme = load_theme(theme) if isinstance(theme, str) else theme
        self.layout = spec.get("layout", {})
        self.style = spec.get("style", {})

        self.columns = int(self.layout.get("columns", 12))
        self.rows = int(self.layout.get("rows", 2))
        self.padding = int(self.layout.get("padding", 28))

        self.font_scale = float(self.style.get("font_scale", 1.0))
        self.h_spacing = float(self.style.get("h_spacing", 0.03))
        self.v_spacing = float(self.style.get("v_spacing", 0.05))
        self.widget_padding = int(self.style.get("widget_padding", 18))
        self.show_cards = bool(self.style.get("show_cards", True))
        self.row_heights_override = self.style.get("row_heights")

        self.Image, self.ImageDraw, self.ImageFont, self.ImageFilter = _import_pillow()
        self._font_cache: dict[tuple[int, bool], Any] = {}

    def _load_font(self, size: int, bold: bool = False) -> Any:
        """Load a system font with fallback to Pillow default."""
        size = max(10, int(size))
        cache_key = (size, bold)
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        font_paths = self._FONT_PATHS_BOLD if bold else self._FONT_PATHS_REGULAR
        for path in font_paths:
            try:
                font = self.ImageFont.truetype(path, size=size)
                self._font_cache[cache_key] = font
                return font
            except OSError:
                continue

        font = self.ImageFont.load_default()
        self._font_cache[cache_key] = font
        return font

    @staticmethod
    def _mix_color(a: tuple[int, int, int], b: tuple[int, int, int], ratio: float) -> tuple[int, int, int]:
        """Blend RGB colors with ratio in [0, 1]."""
        ratio = max(0.0, min(1.0, ratio))
        return tuple(int((a[i] * (1.0 - ratio)) + (b[i] * ratio)) for i in range(3))

    def _paint_background(self, canvas: Any) -> None:
        """Paint a subtle vertical gradient background."""
        colors = self.theme["colors"]
        width, height = canvas.size
        top = _hex_to_rgb(colors["background"])
        accent = _hex_to_rgb(colors.get("secondary", colors["primary"]))
        bottom = self._mix_color(top, accent, 0.08)

        draw = self.ImageDraw.Draw(canvas, "RGBA")
        for y in range(height):
            ratio = y / max(1, height - 1)
            line_color = self._mix_color(top, bottom, ratio)
            draw.line((0, y, width, y), fill=line_color + (255,))

    def _draw_card(
        self,
        canvas: Any,
        draw: Any,
        rect: tuple[int, int, int, int],
        colors: dict[str, Any],
    ) -> None:
        """Draw card surface with soft elevation."""
        x0, y0, x1, y1 = rect
        shadow_layer = self.Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        shadow_draw = self.ImageDraw.Draw(shadow_layer)
        shadow_draw.rounded_rectangle(
            (x0 + 2, y0 + 6, x1 + 2, y1 + 6),
            radius=24,
            fill=(15, 23, 42, 26),
        )
        shadow_layer = shadow_layer.filter(self.ImageFilter.GaussianBlur(radius=9))
        canvas.alpha_composite(shadow_layer)
        draw.rounded_rectangle(
            rect,
            radius=22,
            fill=_hex_to_rgb(colors["surface"]),
            outline=_hex_to_rgb(colors.get("card_border", colors["grid"])),
            width=1,
        )

    def _row_weights(self, widgets: list[dict[str, Any]]) -> list[float]:
        """Compute row weights from explicit style or widget content."""
        if isinstance(self.row_heights_override, list) and self.row_heights_override:
            normalized = []
            for value in self.row_heights_override[: self.rows]:
                if isinstance(value, (int, float)) and value > 0:
                    normalized.append(float(value))
                else:
                    normalized.append(1.0)
            if len(normalized) < self.rows:
                normalized.extend([1.0] * (self.rows - len(normalized)))
            return normalized

        row_types: list[set[str]] = [set() for _ in range(self.rows)]
        for widget in widgets:
            w_type = widget.get("type", "chart")
            position = widget.get("position", {})
            row = int(position.get("row", 0))
            rowspan = int(position.get("rowspan", 1))
            for index in range(max(0, row), min(self.rows, row + rowspan)):
                row_types[index].add(w_type)

        weights = [1.0] * self.rows
        for idx, types in enumerate(row_types):
            if not types:
                continue
            if types.issubset({"kpi", "gauge"}):
                weights[idx] = 0.82
            elif "chart" in types or "table" in types:
                weights[idx] = 1.22
        return weights

    def _format_value(self, value: Any, format_value: str | None = None) -> str:
        """Format KPI values with optional python format template."""
        if format_value and isinstance(value, (int, float)):
            try:
                return format_value.format(value)
            except Exception:
                pass
        if isinstance(value, float):
            if value.is_integer():
                return f"{int(value):,}"
            return f"{value:,.1f}"
        if isinstance(value, int):
            return f"{value:,}"
        return str(value)

    def _draw_centered_text(
        self,
        draw: Any,
        rect: tuple[int, int, int, int],
        text: str,
        font: Any,
        fill: tuple[int, int, int],
    ) -> None:
        """Draw text centered in the provided rectangle."""
        x0, y0, x1, y1 = rect
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = x0 + ((x1 - x0 - text_w) // 2)
        y = y0 + ((y1 - y0 - text_h) // 2)
        draw.text((x, y), text, font=font, fill=fill)

    def _draw_kpi(self, draw: Any, rect: tuple[int, int, int, int], config: dict[str, Any]) -> None:
        """Draw KPI card primitive."""
        x0, y0, x1, y1 = rect
        colors = self.theme["colors"]
        pad = self.widget_padding

        label = str(config.get("label", ""))
        value = config.get("value", 0)
        delta = config.get("delta")
        delta_good = bool(config.get("delta_good", True))
        display = self._format_value(value, config.get("format_value"))

        label_font = self._load_font(int(22 * self.font_scale), bold=True)
        value_font = self._load_font(int(74 * self.font_scale), bold=True)
        delta_font = self._load_font(int(20 * self.font_scale), bold=True)

        draw.text(
            (x0 + pad, y0 + pad),
            label,
            font=label_font,
            fill=_hex_to_rgb(colors["text_secondary"]),
        )
        draw.text(
            (x0 + pad, y0 + pad + int(58 * self.font_scale)),
            display,
            font=value_font,
            fill=_hex_to_rgb(colors["text"]),
        )

        if delta:
            positive = str(delta).startswith("+") or (
                str(delta) and str(delta)[0].isdigit() and not str(delta).startswith("-")
            )
            if delta_good:
                delta_color = colors["positive"] if positive else colors["negative"]
            else:
                delta_color = colors["negative"] if positive else colors["positive"]
            chip_fill = "#e7f7ee" if delta_color == colors["positive"] else "#fdecec"
            chip_border = "#d1efdc" if delta_color == colors["positive"] else "#f7d7d9"

            chip_text = f"▲ {str(delta).lstrip('+-')}" if positive else f"▼ {str(delta).lstrip('+-')}"
            chip_bbox = draw.textbbox((0, 0), chip_text, font=delta_font)
            chip_w = chip_bbox[2] - chip_bbox[0] + 22
            chip_h = chip_bbox[3] - chip_bbox[1] + 14
            chip_x = x0 + pad
            chip_y = y1 - pad - chip_h
            draw.rounded_rectangle(
                (chip_x, chip_y, chip_x + chip_w, chip_y + chip_h),
                radius=10,
                fill=_hex_to_rgb(chip_fill),
                outline=_hex_to_rgb(chip_border),
                width=1,
            )
            draw.text(
                (chip_x + 11, chip_y + 7),
                chip_text,
                font=delta_font,
                fill=_hex_to_rgb(delta_color),
            )

    def _draw_gauge(self, draw: Any, rect: tuple[int, int, int, int], config: dict[str, Any]) -> None:
        """Draw horizontal bullet gauge primitive."""
        x0, y0, x1, y1 = rect
        colors = self.theme["colors"]
        pad = self.widget_padding

        label = str(config.get("label", ""))
        min_val = float(config.get("min", 0))
        max_val = float(config.get("max", 100))
        value = float(config.get("value", 0))
        target = config.get("target")
        unit = str(config.get("unit", ""))

        if max_val <= min_val:
            max_val = min_val + 1
        value = max(min_val, min(max_val, value))
        ratio = (value - min_val) / (max_val - min_val)

        label_font = self._load_font(int(22 * self.font_scale), bold=True)
        value_font = self._load_font(int(58 * self.font_scale), bold=True)
        meta_font = self._load_font(int(16 * self.font_scale))

        draw.text(
            (x0 + pad, y0 + pad),
            label,
            font=label_font,
            fill=_hex_to_rgb(colors["text_secondary"]),
        )
        value_text = f"{value:g}{unit}"
        value_bbox = draw.textbbox((0, 0), value_text, font=value_font)
        value_w = value_bbox[2] - value_bbox[0]
        draw.text(
            (x1 - pad - value_w, y0 + pad + int(44 * self.font_scale)),
            value_text,
            font=value_font,
            fill=_hex_to_rgb(colors["text"]),
        )

        bar_left = x0 + pad
        bar_right = x1 - pad
        bar_top = y0 + pad + int(120 * self.font_scale)
        bar_bottom = bar_top + int(32 * self.font_scale)
        draw.rounded_rectangle(
            (bar_left, bar_top, bar_right, bar_bottom),
            radius=8,
            fill=_hex_to_rgb(colors["grid"]),
        )

        fill_right = int(bar_left + (bar_right - bar_left) * ratio)
        draw.rounded_rectangle(
            (bar_left, bar_top, fill_right, bar_bottom),
            radius=8,
            fill=_hex_to_rgb(colors["primary"]),
        )

        if target is not None:
            try:
                target_val = float(target)
                target_ratio = (target_val - min_val) / (max_val - min_val)
                target_ratio = max(0.0, min(1.0, target_ratio))
                tx = int(bar_left + (bar_right - bar_left) * target_ratio)
                draw.line(
                    (tx, bar_top - 16, tx, bar_bottom + 16),
                    fill=_hex_to_rgb(colors.get("accent", colors["negative"])),
                    width=4,
                )
            except (TypeError, ValueError):
                pass

        draw.text(
            (bar_left, bar_bottom + 14),
            f"{min_val:g} - {max_val:g}",
            font=meta_font,
            fill=_hex_to_rgb(colors["text_secondary"]),
        )

    def _draw_table(self, draw: Any, rect: tuple[int, int, int, int], config: dict[str, Any]) -> None:
        """Draw simple table primitive."""
        x0, y0, x1, y1 = rect
        colors = self.theme["colors"]
        pad = self.widget_padding

        headers = config.get("headers", [])
        rows = config.get("rows", [])
        title = config.get("title")
        if not isinstance(headers, list) or not headers:
            return
        if not isinstance(rows, list):
            rows = []

        title_font = self._load_font(int(20 * self.font_scale), bold=True)
        header_font = self._load_font(int(18 * self.font_scale), bold=True)
        body_font = self._load_font(int(16 * self.font_scale))

        top = y0 + pad
        if title:
            draw.text((x0 + pad, top), str(title), font=title_font, fill=_hex_to_rgb(colors["text"]))
            top += int(38 * self.font_scale)

        col_count = max(1, len(headers))
        table_w = (x1 - x0) - (2 * pad)
        col_w = table_w // col_count
        header_h = int(36 * self.font_scale)
        row_h = int(30 * self.font_scale)

        draw.rectangle(
            (x0 + pad, top, x1 - pad, top + header_h),
            fill=_hex_to_rgb(colors["surface"]),
            outline=_hex_to_rgb(colors.get("card_border", colors["grid"])),
            width=1,
        )

        for idx, header in enumerate(headers):
            cell_x = x0 + pad + (idx * col_w)
            draw.text(
                (cell_x + 8, top + 8),
                str(header),
                font=header_font,
                fill=_hex_to_rgb(colors["text_secondary"]),
            )

        max_rows = max(0, (y1 - (top + header_h) - pad) // max(1, row_h))
        for row_idx, row in enumerate(rows[:max_rows]):
            if not isinstance(row, list):
                continue
            row_top = top + header_h + (row_idx * row_h)
            bg = colors["surface"] if row_idx % 2 == 0 else colors["background"]
            draw.rectangle(
                (x0 + pad, row_top, x1 - pad, row_top + row_h),
                fill=_hex_to_rgb(bg),
                outline=_hex_to_rgb(colors.get("card_border", colors["grid"])),
                width=1,
            )
            for col_idx in range(col_count):
                text = str(row[col_idx]) if col_idx < len(row) else ""
                cell_x = x0 + pad + (col_idx * col_w)
                draw.text(
                    (cell_x + 8, row_top + 6),
                    text,
                    font=body_font,
                    fill=_hex_to_rgb(colors["text"]),
                )

    def _draw_chart(self, canvas: Any, draw: Any, rect: tuple[int, int, int, int], config: dict[str, Any]) -> None:
        """Render and place a chart image into a widget card."""
        x0, y0, x1, y1 = rect
        colors = self.theme["colors"]
        pad = self.widget_padding

        chart_type = str(config.get("chart_type", "bar"))
        data = config.get("data", {})
        title = config.get("title")

        title_font = self._load_font(int(24 * self.font_scale), bold=True)
        chart_x = x0 + pad
        chart_y = y0 + pad
        chart_w = max(120, (x1 - x0) - (2 * pad))
        chart_h = max(120, (y1 - y0) - (2 * pad))

        if title:
            draw.text(
                (chart_x, chart_y),
                str(title),
                font=title_font,
                fill=_hex_to_rgb(colors["text"]),
            )
            chart_y += int(34 * self.font_scale)
            chart_h -= int(34 * self.font_scale)

        chart_img = render_chart_image(
            chart_type=chart_type,
            data=data if isinstance(data, dict) else {},
            width=chart_w,
            height=chart_h,
            theme=self.theme,
            title=None,
            show_legend=False,
            scale=2.0,
            embedded=True,
        )
        resampling = getattr(self.Image, "Resampling", self.Image).LANCZOS
        chart_img = chart_img.resize((chart_w, chart_h), resampling)
        canvas.paste(chart_img, (chart_x, chart_y), chart_img)

    def _compute_widget_rects(
        self, width: int, height: int, widgets: list[dict[str, Any]]
    ) -> list[tuple[dict[str, Any], tuple[int, int, int, int]]]:
        """Compute pixel rectangles for each widget from grid positions."""
        title = self.spec.get("title")
        top_area = int((84 if title else 32) * self.font_scale)
        outer = max(16, self.padding)

        grid_x0 = outer
        grid_x1 = width - outer
        grid_y0 = outer + top_area
        grid_y1 = height - outer
        grid_w = max(120, grid_x1 - grid_x0)
        grid_h = max(120, grid_y1 - grid_y0)

        gap_x = max(10, int(self.h_spacing * width))
        gap_y = max(10, int(self.v_spacing * height * 0.8))

        col_w = max(32, int((grid_w - (gap_x * max(0, self.columns - 1))) / max(1, self.columns)))
        row_weights = self._row_weights(widgets)
        row_weight_sum = max(0.001, sum(row_weights))
        row_unit = (grid_h - (gap_y * max(0, self.rows - 1))) / row_weight_sum
        row_heights = [max(32, int(row_unit * weight)) for weight in row_weights]

        row_starts = [grid_y0]
        for index in range(1, self.rows):
            row_starts.append(row_starts[index - 1] + row_heights[index - 1] + gap_y)

        results: list[tuple[dict[str, Any], tuple[int, int, int, int]]] = []
        for widget in widgets:
            position = widget.get("position", {})
            row = int(position.get("row", 0))
            col = int(position.get("col", 0))
            rowspan = max(1, int(position.get("rowspan", 1)))
            colspan = max(1, int(position.get("colspan", 1)))

            row = max(0, min(self.rows - 1, row))
            col = max(0, min(self.columns - 1, col))
            rowspan = min(rowspan, self.rows - row)
            colspan = min(colspan, self.columns - col)

            x0 = grid_x0 + col * (col_w + gap_x)
            x1 = x0 + (colspan * col_w) + ((colspan - 1) * gap_x)
            y0 = row_starts[row]
            y1 = y0 + sum(row_heights[row: row + rowspan]) + ((rowspan - 1) * gap_y)

            results.append((widget, (x0, y0, x1, y1)))

        return results

    def compose(self, width: int, height: int) -> Any:
        """Compose the dashboard image in memory."""
        colors = self.theme["colors"]
        canvas = self.Image.new("RGBA", (width, height), _hex_to_rgb(colors["background"]) + (255,))
        self._paint_background(canvas)
        draw = self.ImageDraw.Draw(canvas)

        # Title
        title = self.spec.get("title")
        if title:
            title_font = self._load_font(int(48 * self.font_scale), bold=True)
            draw.text(
                (self.padding, self.padding),
                str(title),
                font=title_font,
                fill=_hex_to_rgb(colors["text"]),
            )

        widgets = self.spec.get("widgets", [])
        if not isinstance(widgets, list):
            widgets = []

        widget_rects = self._compute_widget_rects(width=width, height=height, widgets=widgets)
        for widget, rect in widget_rects:
            w_type = widget.get("type", "chart")
            config = widget.get("config", {})
            if not isinstance(config, dict):
                config = {}

            if self.show_cards:
                self._draw_card(canvas, draw, rect, colors)

            if w_type == "kpi":
                self._draw_kpi(draw, rect, config)
            elif w_type == "gauge":
                self._draw_gauge(draw, rect, config)
            elif w_type == "table":
                self._draw_table(draw, rect, config)
            elif w_type == "chart":
                self._draw_chart(canvas, draw, rect, config)

        return canvas

    def render(
        self,
        output_dir: str | Path,
        filename: str = "dashboard",
        format: FormatType = "png",
        resolution: str = "1080p",
        scale: float = 1.0,
    ) -> Path:
        """Render dashboard to file."""
        width, height = parse_resolution(resolution)
        width = max(120, int(width * max(0.2, scale)))
        height = max(120, int(height * max(0.2, scale)))

        image = self.compose(width=width, height=height)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        file_path = output_path / f"{filename}.{format}"

        if format == "svg":
            raise ValueError("Delight dashboard backend currently supports png and pdf only.")
        if format == "pdf":
            image.convert("RGB").save(file_path, "PDF", resolution=144.0)
        else:
            image.save(file_path, "PNG")

        return file_path
