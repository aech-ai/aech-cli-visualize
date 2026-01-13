"""Base widget class for all visualization widgets."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

from ..themes.loader import apply_theme_to_figure, load_theme
from ..utils.export import export_figure, FormatType


class BaseWidget(ABC):
    """Abstract base class for visualization widgets."""

    def __init__(
        self,
        config: dict[str, Any],
        theme: str | dict[str, Any] = "corporate",
    ):
        """Initialize widget with configuration and theme.

        Args:
            config: Widget-specific configuration
            theme: Theme name or theme dictionary
        """
        self.config = config
        self.theme = load_theme(theme) if isinstance(theme, str) else theme

    @abstractmethod
    def create_figure(self) -> go.Figure:
        """Create the Plotly figure for this widget.

        Returns:
            Configured Plotly figure
        """
        pass

    def render(
        self,
        output_dir: str | Path,
        filename: str,
        format: FormatType = "png",
        width: int = 1920,
        height: int = 1080,
        scale: float = 2.0,
    ) -> Path:
        """Render widget to image file.

        Args:
            output_dir: Directory to write the file
            filename: Base filename (without extension)
            format: Output format (png, svg, pdf)
            width: Image width in pixels
            height: Image height in pixels
            scale: Scale factor for higher DPI

        Returns:
            Path to the exported file
        """
        fig = self.create_figure()
        fig = apply_theme_to_figure(fig, self.theme)

        return export_figure(
            fig=fig,
            output_dir=output_dir,
            filename=filename,
            format=format,
            width=width,
            height=height,
            scale=scale,
        )

    def get_figure(self) -> go.Figure:
        """Get the styled figure without rendering to file.

        Returns:
            Styled Plotly figure
        """
        fig = self.create_figure()
        return apply_theme_to_figure(fig, self.theme)
