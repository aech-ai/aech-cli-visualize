"""Image export utilities using Kaleido."""

from pathlib import Path
from typing import Literal

import plotly.graph_objects as go

# Standard resolutions for presentations
RESOLUTIONS: dict[str, tuple[int, int]] = {
    "1080p": (1920, 1080),
    "4k": (3840, 2160),
    "720p": (1280, 720),
}

FormatType = Literal["png", "svg", "pdf"]


def parse_resolution(resolution: str) -> tuple[int, int]:
    """Parse resolution string into width, height tuple.

    Args:
        resolution: Either a preset name (1080p, 4k) or WxH format (1920x1080)

    Returns:
        Tuple of (width, height)
    """
    if resolution.lower() in RESOLUTIONS:
        return RESOLUTIONS[resolution.lower()]

    if "x" in resolution.lower():
        try:
            w, h = resolution.lower().split("x")
            return int(w), int(h)
        except ValueError:
            pass

    raise ValueError(
        f"Invalid resolution: {resolution}. "
        f"Use preset ({', '.join(RESOLUTIONS.keys())}) or WxH format (e.g., 1920x1080)"
    )


def export_figure(
    fig: go.Figure,
    output_dir: str | Path,
    filename: str,
    format: FormatType = "png",
    width: int = 1920,
    height: int = 1080,
    scale: float = 2.0,
) -> Path:
    """Export Plotly figure to image file.

    Args:
        fig: Plotly figure to export
        output_dir: Directory to write the file
        filename: Base filename (without extension)
        format: Output format (png, svg, pdf)
        width: Image width in pixels
        height: Image height in pixels
        scale: Scale factor for higher DPI output

    Returns:
        Path to the exported file
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    file_path = output_path / f"{filename}.{format}"

    fig.write_image(
        str(file_path),
        format=format,
        width=width,
        height=height,
        scale=scale,
        engine="kaleido",
    )

    return file_path
