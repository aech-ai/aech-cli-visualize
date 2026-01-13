"""CLI entry point for aech-cli-visualize."""

import json
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

from .dashboard.composer import DashboardComposer
from .themes.loader import get_available_themes
from .utils.data import parse_data_input
from .utils.export import parse_resolution
from .widgets.chart import ChartWidget, ChartType
from .widgets.gauge import GaugeWidget
from .widgets.kpi import KPIWidget
from .widgets.table import TableWidget

app = typer.Typer(
    help="Render charts, KPIs, tables, and dashboards to presentation-ready images.",
    no_args_is_help=True,
    add_completion=False,
)


def output_json(data: dict) -> None:
    """Output JSON to stdout."""
    print(json.dumps(data, indent=2))


def get_file_info(path: Path) -> dict:
    """Get file info for output."""
    return {
        "path": str(path),
        "format": path.suffix[1:],
        "size_bytes": path.stat().st_size,
    }


@app.command("chart")
def chart_command(
    chart_type: Annotated[str, typer.Argument(help="Chart type: bar, line, pie, scatter, area, heatmap")],
    data_file: Annotated[Optional[str], typer.Argument(help="Path to JSON data file (reads stdin if omitted)")] = None,
    output_dir: Annotated[str, typer.Option("--output-dir", help="Directory for output image")] = ".",
    title: Annotated[Optional[str], typer.Option("--title", help="Chart title")] = None,
    theme: Annotated[str, typer.Option("--theme", help="Visual theme")] = "corporate",
    format: Annotated[str, typer.Option("--format", help="Output format: png, svg, pdf")] = "png",
) -> None:
    """Render a chart from data.

    Input: JSON with x/y values or series data.
    Output: chart image at <output-dir>/chart.<format>.
    """
    try:
        # Parse input data
        data = parse_data_input(data_file)

        # Validate chart type
        valid_types = ["bar", "line", "pie", "scatter", "area", "heatmap"]
        if chart_type not in valid_types:
            output_json({
                "success": False,
                "error": f"Invalid chart type: {chart_type}. Valid types: {', '.join(valid_types)}",
            })
            raise typer.Exit(1)

        # Create and render widget
        widget = ChartWidget(
            chart_type=chart_type,  # type: ignore
            data=data,
            title=title,
            theme=theme,
        )

        output_path = widget.render(
            output_dir=output_dir,
            filename="chart",
            format=format,  # type: ignore
        )

        output_json({
            "success": True,
            "output_files": [get_file_info(output_path)],
            "message": f"Chart rendered successfully",
        })

    except Exception as e:
        output_json({
            "success": False,
            "error": str(e),
        })
        raise typer.Exit(1)


@app.command("kpi")
def kpi_command(
    value: Annotated[str, typer.Option("--value", help="Metric value to display")],
    label: Annotated[str, typer.Option("--label", help="Label describing the metric")],
    output_dir: Annotated[str, typer.Option("--output-dir", help="Directory for output image")] = ".",
    delta: Annotated[Optional[str], typer.Option("--delta", help="Change indicator (e.g., '+12%')")] = None,
    delta_good: Annotated[bool, typer.Option("--delta-good/--delta-bad", help="Whether positive delta is good")] = True,
    format_value: Annotated[Optional[str], typer.Option("--format-value", help="Python format string")] = None,
    theme: Annotated[str, typer.Option("--theme", help="Visual theme")] = "corporate",
    format: Annotated[str, typer.Option("--format", help="Output format: png, svg, pdf")] = "png",
) -> None:
    """Render a KPI metric card.

    Input: value and label via options.
    Output: KPI card image at <output-dir>/kpi.<format>.
    """
    try:
        # Try to convert value to number
        try:
            numeric_value: float | int | str = float(value)
            if numeric_value == int(numeric_value):
                numeric_value = int(numeric_value)
        except ValueError:
            numeric_value = value

        widget = KPIWidget(
            value=numeric_value,
            label=label,
            delta=delta,
            delta_good=delta_good,
            format_value=format_value,
            theme=theme,
        )

        output_path = widget.render(
            output_dir=output_dir,
            filename="kpi",
            format=format,  # type: ignore
        )

        output_json({
            "success": True,
            "output_files": [get_file_info(output_path)],
            "message": "KPI rendered successfully",
        })

    except Exception as e:
        output_json({
            "success": False,
            "error": str(e),
        })
        raise typer.Exit(1)


@app.command("table")
def table_command(
    data_file: Annotated[Optional[str], typer.Argument(help="Path to JSON file (reads stdin if omitted)")] = None,
    output_dir: Annotated[str, typer.Option("--output-dir", help="Directory for output image")] = ".",
    title: Annotated[Optional[str], typer.Option("--title", help="Table title")] = None,
    theme: Annotated[str, typer.Option("--theme", help="Visual theme")] = "corporate",
    format: Annotated[str, typer.Option("--format", help="Output format: png, svg, pdf")] = "png",
) -> None:
    """Render a data table as an image.

    Input: JSON with headers and rows.
    Output: table image at <output-dir>/table.<format>.
    """
    try:
        data = parse_data_input(data_file)

        headers = data.get("headers", [])
        rows = data.get("rows", [])

        if not headers:
            output_json({
                "success": False,
                "error": "Data must include 'headers' array",
            })
            raise typer.Exit(1)

        widget = TableWidget(
            headers=headers,
            rows=rows,
            title=title,
            theme=theme,
        )

        output_path = widget.render(
            output_dir=output_dir,
            filename="table",
            format=format,  # type: ignore
        )

        output_json({
            "success": True,
            "output_files": [get_file_info(output_path)],
            "message": "Table rendered successfully",
        })

    except Exception as e:
        output_json({
            "success": False,
            "error": str(e),
        })
        raise typer.Exit(1)


@app.command("gauge")
def gauge_command(
    value: Annotated[float, typer.Option("--value", help="Current value to display")],
    output_dir: Annotated[str, typer.Option("--output-dir", help="Directory for output image")] = ".",
    min_val: Annotated[float, typer.Option("--min", help="Minimum gauge value")] = 0,
    max_val: Annotated[float, typer.Option("--max", help="Maximum gauge value")] = 100,
    label: Annotated[Optional[str], typer.Option("--label", help="Label describing the metric")] = None,
    thresholds: Annotated[Optional[str], typer.Option("--thresholds", help="JSON array of threshold objects")] = None,
    theme: Annotated[str, typer.Option("--theme", help="Visual theme")] = "corporate",
    format: Annotated[str, typer.Option("--format", help="Output format: png, svg, pdf")] = "png",
) -> None:
    """Render a gauge indicator.

    Input: value and range via options.
    Output: gauge image at <output-dir>/gauge.<format>.
    """
    try:
        # Parse thresholds if provided
        threshold_list = None
        if thresholds:
            threshold_list = json.loads(thresholds)

        widget = GaugeWidget(
            value=value,
            min_val=min_val,
            max_val=max_val,
            label=label,
            thresholds=threshold_list,
            theme=theme,
        )

        output_path = widget.render(
            output_dir=output_dir,
            filename="gauge",
            format=format,  # type: ignore
        )

        output_json({
            "success": True,
            "output_files": [get_file_info(output_path)],
            "message": "Gauge rendered successfully",
        })

    except Exception as e:
        output_json({
            "success": False,
            "error": str(e),
        })
        raise typer.Exit(1)


@app.command("dashboard")
def dashboard_command(
    spec_file: Annotated[Optional[str], typer.Argument(help="Path to dashboard spec JSON (reads stdin if omitted)")] = None,
    output_dir: Annotated[str, typer.Option("--output-dir", help="Directory for output image")] = ".",
    theme: Annotated[str, typer.Option("--theme", help="Visual theme for all widgets")] = "corporate",
    resolution: Annotated[str, typer.Option("--resolution", help="Output resolution: 1080p, 4k, or WxH")] = "1080p",
    format: Annotated[str, typer.Option("--format", help="Output format: png, svg, pdf")] = "png",
) -> None:
    """Compose multiple widgets into a single dashboard image.

    Input: JSON specification with layout and widgets.
    Output: dashboard image at <output-dir>/dashboard.<format>.
    """
    try:
        spec = parse_data_input(spec_file)

        composer = DashboardComposer(spec=spec, theme=theme)

        output_path = composer.render(
            output_dir=output_dir,
            filename="dashboard",
            format=format,  # type: ignore
            resolution=resolution,
        )

        width, height = parse_resolution(resolution)

        output_json({
            "success": True,
            "output_files": [{
                **get_file_info(output_path),
                "width": width,
                "height": height,
            }],
            "message": "Dashboard rendered successfully",
        })

    except Exception as e:
        output_json({
            "success": False,
            "error": str(e),
        })
        raise typer.Exit(1)


@app.command("themes", hidden=True)
def themes_command() -> None:
    """List available themes."""
    themes = get_available_themes()
    output_json({
        "themes": themes,
    })


def run() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    run()
