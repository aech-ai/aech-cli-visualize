"""CLI entry point for aech-cli-visualize."""

import json
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated, Optional

import typer

from .delight.visual_modes import normalize_visual_mode
from .dashboard.composer import DashboardComposer
from .themes.loader import get_available_themes
from .utils.data import parse_data_input
from .utils.export import parse_resolution
from .widgets.chart import ChartWidget, ChartType
from .widgets.gauge import GaugeWidget
from .widgets.kpi import KPIWidget
from .widgets.table import TableWidget

app = typer.Typer(
    help="Generate arbitrary visual artifacts with GPT Image from data, records, text, or instructions.",
    no_args_is_help=True,
    add_completion=False,
)


def _package_version() -> str:
    try:
        return version("aech-cli-visualize")
    except PackageNotFoundError:
        return "unknown"


@app.callback(invoke_without_command=True)
def main_callback(
    version_flag: Annotated[
        bool,
        typer.Option("--version", "-V", help="Show the installed aech-cli-visualize version and exit."),
    ] = False,
) -> None:
    if version_flag:
        typer.echo(f"aech-cli-visualize {_package_version()}")
        raise typer.Exit()


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


def unsupported_deterministic_renderer(command: str) -> None:
    output_json({
        "success": False,
        "error": (
            f"The '{command}' renderer is no longer supported. "
            "Use 'aech-cli-visualize image' for all visualization generation."
        ),
        "replacement": "image",
    })
    raise typer.Exit(1)


@app.command("chart", hidden=True)
def chart_command(
    chart_type: Annotated[str, typer.Argument(help="Chart type: bar, line, pie, scatter, area, heatmap")],
    data_file: Annotated[Optional[str], typer.Argument(help="Path to JSON data file (reads stdin if omitted)")] = None,
    output_dir: Annotated[str, typer.Option("--output-dir", help="Directory for output image")] = ".",
    title: Annotated[Optional[str], typer.Option("--title", help="Chart title")] = None,
    theme: Annotated[str, typer.Option("--theme", help="Visual theme")] = "corporate",
    backend: Annotated[str, typer.Option("--backend", help="Rendering backend: delight or legacy")] = "delight",
    visual_mode: Annotated[
        str,
        typer.Option("--visual-mode", help="Delight visual mode: premium_executive, editorial, data_journal"),
    ] = "premium_executive",
    annotations: Annotated[
        bool,
        typer.Option("--annotations/--no-annotations", help="Enable smart chart annotations"),
    ] = True,
    format: Annotated[str, typer.Option("--format", help="Output format: png, svg, pdf")] = "png",
) -> None:
    """Render a chart from data.

    Input: JSON with x/y values or series data.
    Output: chart image at <output-dir>/chart.<format>.
    """
    unsupported_deterministic_renderer("chart")
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

        if backend not in ("delight", "legacy", "plotly"):
            output_json({
                "success": False,
                "error": "Invalid backend. Supported values: delight, legacy",
            })
            raise typer.Exit(1)

        resolved_visual_mode: str | None = None
        if backend == "delight":
            from .delight import render_chart_file

            resolved_visual_mode = normalize_visual_mode(visual_mode)
            output_path = render_chart_file(
                chart_type=chart_type,
                data=data,
                output_dir=output_dir,
                filename="chart",
                format=format,  # type: ignore
                width=1920,
                height=1080,
                theme=theme,
                title=title,
                show_legend=True,
                scale=1.0,
                visual_mode=resolved_visual_mode,
                auto_annotate=annotations,
            )
        else:
            # Legacy Plotly renderer
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
            "backend": "delight" if backend == "delight" else "legacy",
            "visual_mode": resolved_visual_mode if backend == "delight" else None,
            "annotations": annotations if backend == "delight" else None,
            "message": "Chart rendered successfully",
        })

    except Exception as e:
        output_json({
            "success": False,
            "error": str(e),
        })
        raise typer.Exit(1)


@app.command("kpi", hidden=True)
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
    unsupported_deterministic_renderer("kpi")
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


@app.command("table", hidden=True)
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
    unsupported_deterministic_renderer("table")
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


@app.command("gauge", hidden=True)
def gauge_command(
    value: Annotated[float, typer.Option("--value", help="Current value to display")],
    output_dir: Annotated[str, typer.Option("--output-dir", help="Directory for output image")] = ".",
    min_val: Annotated[float, typer.Option("--min", help="Minimum gauge value")] = 0,
    max_val: Annotated[float, typer.Option("--max", help="Maximum gauge value")] = 100,
    label: Annotated[Optional[str], typer.Option("--label", help="Label describing the metric")] = None,
    target: Annotated[Optional[float], typer.Option("--target", help="Optional target marker value")] = None,
    thresholds: Annotated[Optional[str], typer.Option("--thresholds", help="JSON array of threshold objects")] = None,
    theme: Annotated[str, typer.Option("--theme", help="Visual theme")] = "corporate",
    format: Annotated[str, typer.Option("--format", help="Output format: png, svg, pdf")] = "png",
) -> None:
    """Render a gauge indicator.

    Input: value and range via options.
    Output: gauge image at <output-dir>/gauge.<format>.
    """
    unsupported_deterministic_renderer("gauge")
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
            target=target,
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


@app.command("dashboard", hidden=True)
def dashboard_command(
    spec_file: Annotated[Optional[str], typer.Argument(help="Path to dashboard spec JSON (reads stdin if omitted)")] = None,
    output_dir: Annotated[str, typer.Option("--output-dir", help="Directory for output image")] = ".",
    theme: Annotated[str, typer.Option("--theme", help="Visual theme for all widgets")] = "corporate",
    backend: Annotated[str, typer.Option("--backend", help="Rendering backend: delight or legacy")] = "delight",
    visual_mode: Annotated[
        str,
        typer.Option("--visual-mode", help="Delight visual mode: premium_executive, editorial, data_journal"),
    ] = "premium_executive",
    annotations: Annotated[
        bool,
        typer.Option("--annotations/--no-annotations", help="Enable smart chart annotations"),
    ] = True,
    resolution: Annotated[str, typer.Option("--resolution", help="Output resolution: 1080p, 4k, or WxH")] = "1080p",
    format: Annotated[str, typer.Option("--format", help="Output format: png, svg, pdf")] = "png",
    vlm_validate: Annotated[bool, typer.Option("--vlm-validate/--no-vlm-validate", help="Enable VLM validation loop")] = False,
    vlm_max_iterations: Annotated[int, typer.Option("--vlm-max-iterations", help="Max VLM correction iterations")] = 3,
    vlm_model: Annotated[Optional[str], typer.Option("--vlm-model", help="VLM model (e.g., openai:gpt-4o)")] = None,
) -> None:
    """Compose multiple widgets into a single dashboard image.

    Input: JSON specification with layout and widgets.
    Output: dashboard image at <output-dir>/dashboard.<format>.

    Use --vlm-validate to enable VLM-based validation that checks the rendered
    output for visual issues and automatically applies corrections.
    """
    unsupported_deterministic_renderer("dashboard")
    try:
        spec = parse_data_input(spec_file)
        width, height = parse_resolution(resolution)

        if backend not in ("delight", "legacy", "plotly"):
            output_json({
                "success": False,
                "error": "Invalid backend. Supported values: delight, legacy",
            })
            raise typer.Exit(1)

        use_delight_backend = backend == "delight" and not vlm_validate and format != "svg"

        resolved_visual_mode: str | None = None
        if use_delight_backend:
            from .delight import DelightDashboardComposer

            resolved_visual_mode = normalize_visual_mode(visual_mode)
            composer = DelightDashboardComposer(
                spec=spec,
                theme=theme,
                visual_mode=resolved_visual_mode,
                auto_annotate_charts=annotations,
            )
            output_path = composer.render(
                output_dir=output_dir,
                filename="dashboard",
                format=format,  # type: ignore
                resolution=resolution,
                scale=1.0,
            )

            output_json({
                "success": True,
                "output_files": [{
                    **get_file_info(output_path),
                    "width": width,
                    "height": height,
                }],
                "backend": "delight",
                "visual_mode": resolved_visual_mode,
                "annotations": annotations,
                "message": "Dashboard rendered successfully",
            })
            return

        # Legacy path (explicit or automatic fallback).
        if vlm_validate:
            # Use validated composer with VLM feedback loop
            from .dashboard.validated_composer import ValidatedDashboardComposer
            from .observability import llm_observability_session

            composer = ValidatedDashboardComposer(
                spec=spec,
                theme=theme,
                enable_vlm_validation=True,
                max_iterations=vlm_max_iterations,
                vlm_model=vlm_model,
            )

            with llm_observability_session():
                result = composer.render(
                    output_dir=output_dir,
                    filename="dashboard",
                    format=format,  # type: ignore
                    resolution=resolution,
                )

            # Build validation metadata for output
            validation_info = {
                "enabled": True,
                "iterations": result.iterations,
                "final_status": "approved" if (
                    result.validation_history
                    and result.validation_history[-1].is_acceptable
                ) else "issues_remaining",
                "corrections_applied": len(result.corrections_applied),
            }

            if result.validation_history:
                # Summarize resolved issues
                all_issues = []
                for vr in result.validation_history[:-1]:
                    for issue in vr.issues:
                        all_issues.append({
                            "type": issue.issue_type,
                            "widgets": issue.affected_widgets,
                        })
                validation_info["issues_resolved"] = all_issues

                # Remaining issues from last validation
                if result.validation_history[-1].issues:
                    validation_info["remaining_issues"] = [
                        {"type": i.issue_type, "severity": i.severity}
                        for i in result.validation_history[-1].issues
                    ]

            output_data = {
                "success": True,
                "output_files": [{
                    **get_file_info(result.path),
                    "width": width,
                    "height": height,
                }],
                "backend": "legacy",
                "validation": validation_info,
                "message": f"Dashboard rendered after {result.iterations} iteration(s)",
            }

            if result.warning:
                output_data["warning"] = result.warning
            if result.vlm_error:
                output_data["vlm_error"] = result.vlm_error

            output_json(output_data)

        else:
            # Standard render without VLM validation
            composer = DashboardComposer(spec=spec, theme=theme)

            output_path = composer.render(
                output_dir=output_dir,
                filename="dashboard",
                format=format,  # type: ignore
                resolution=resolution,
            )

            output_json({
                "success": True,
                "output_files": [{
                    **get_file_info(output_path),
                    "width": width,
                    "height": height,
                }],
                "backend": "legacy",
                "message": "Dashboard rendered successfully",
            })

    except Exception as e:
        output_json({
            "success": False,
            "error": str(e),
        })
        raise typer.Exit(1)


@app.command("analyze", hidden=True)
def analyze_command(
    data_file: Annotated[Optional[str], typer.Argument(help="Path to JSON data file (reads stdin if omitted)")] = None,
    questions: Annotated[bool, typer.Option("--questions/--no-questions", help="Include clarifying questions")] = True,
    use_llm: Annotated[bool, typer.Option("--llm/--no-llm", help="Use LLM for enhanced analysis")] = True,
) -> None:
    """Analyze data to suggest visualizations and generate dashboard recommendations.

    Input: JSON data with field names as keys and value arrays.
    Output: Field analysis, detected patterns, widget suggestions, and optional questions.
    """
    try:
        from .config import DataAnalyzer
        from .observability import llm_observability_session

        data = parse_data_input(data_file)
        with llm_observability_session():
            analyzer = DataAnalyzer(use_llm=use_llm)
            result = analyzer.analyze(data, include_questions=questions)

        output_json({
            "success": True,
            "analysis": {
                "fields": [f.model_dump() for f in result.fields],
                "patterns": [p.model_dump() for p in result.patterns],
                "suggested_widgets": [w.model_dump() for w in result.suggested_widgets],
            },
            "questions": [q.model_dump() for q in result.questions] if questions else [],
            "schema_fingerprint": result.schema_fingerprint,
            "matching_configs": result.matching_configs,
            "message": f"Analyzed {len(result.fields)} fields, detected {len(result.patterns)} patterns",
        })

    except Exception as e:
        output_json({
            "success": False,
            "error": str(e),
        })
        raise typer.Exit(1)


@app.command("image")
def image_command(
    data_file: Annotated[Optional[str], typer.Argument(help="Path to JSON payload/data file (reads stdin if omitted)")] = None,
    output_dir: Annotated[str, typer.Option("--output-dir", help="Directory for output image and prompt artifacts")] = ".",
    title: Annotated[Optional[str], typer.Option("--title", help="Visualization title override")] = None,
    instructions: Annotated[
        Optional[str],
        typer.Option("--instructions", help="Analysis and visualization instructions for the model"),
    ] = None,
    template_image: Annotated[
        Optional[str],
        typer.Option("--template-image", help="Optional reference image for visual consistency"),
    ] = None,
    filename: Annotated[str, typer.Option("--filename", help="Output filename without extension")] = "generative_visual",
    analysis_mode: Annotated[
        str,
        typer.Option("--analysis-mode", help="Analysis mode: auto, llm, precomputed, code"),
    ] = "auto",
    analysis_model: Annotated[
        str,
        typer.Option("--analysis-model", help="OpenAI model for typed data analysis"),
    ] = "gpt-5.5",
    image_model: Annotated[
        str,
        typer.Option("--image-model", help="GPT Image model for raster generation"),
    ] = "gpt-image-2",
    response_model: Annotated[
        str,
        typer.Option("--response-model", help="Deprecated compatibility option; image generation uses the Images API directly"),
    ] = "gpt-5.5",
    surface: Annotated[
        str,
        typer.Option("--surface", help="Target surface: slide or embedded-card"),
    ] = "slide",
    size: Annotated[
        Optional[str],
        typer.Option("--size", help="Image size, e.g. 2048x1152 for 16:9 slide, 1536x1024, auto"),
    ] = None,
    include_header: Annotated[
        bool,
        typer.Option("--header/--no-header", help="Allow a compact title/header in the generated visual"),
    ] = False,
    quality: Annotated[
        str,
        typer.Option("--quality", help="Image quality: low, medium, high, auto"),
    ] = "medium",
    format: Annotated[
        str,
        typer.Option("--format", help="Output format: png, jpeg, webp"),
    ] = "png",
    output_compression: Annotated[
        Optional[int],
        typer.Option("--output-compression", help="JPEG/WebP compression level 0-100"),
    ] = None,
    max_data_chars: Annotated[
        int,
        typer.Option("--max-data-chars", help="Maximum serialized data chars allowed in model prompts"),
    ] = 20_000,
    image_timeout_seconds: Annotated[
        int,
        typer.Option("--image-timeout-seconds", help="Per-attempt timeout for GPT Image generation"),
    ] = 135,
    image_max_attempts: Annotated[
        int,
        typer.Option("--image-max-attempts", help="Maximum GPT Image generation attempts for transient transport errors"),
    ] = 2,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run/--generate", help="Write prompt/analysis artifacts without calling GPT Image"),
    ] = False,
) -> None:
    """Generate an arbitrary visualization image with GPT Image.

    Input can be raw JSON, JSONL records, narrative source material wrapped in
    JSON, or a payload:
    {"data": {...}, "title": "...", "instructions": "...", "analysis": {...}}.
    Numeric data is optional: use this for diagrams, timelines, annotated
    summaries, process maps, comparisons, dashboards, and any other visual
    explanation. If analysis is omitted, an OpenAI typed-output analysis call is
    made before image generation. No deterministic chart fallback is used.
    """
    try:
        from .generative import (
            GenerativeImageRenderer,
            ImageGenerationOptions,
            resolve_visualization_input,
        )
        from .observability import llm_observability_session

        valid_analysis_modes = {"auto", "llm", "precomputed", "code"}
        valid_formats = {"png", "jpeg", "webp"}
        valid_qualities = {"low", "medium", "high", "auto"}
        valid_surfaces = {"slide", "embedded-card"}

        if analysis_mode not in valid_analysis_modes:
            raise ValueError(
                f"Invalid analysis mode: {analysis_mode}. Valid values: auto, llm, precomputed, code"
            )

        if format not in valid_formats:
            raise ValueError(f"Invalid format: {format}. Valid values: png, jpeg, webp")

        if quality not in valid_qualities:
            raise ValueError(f"Invalid quality: {quality}. Valid values: low, medium, high, auto")

        if surface not in valid_surfaces:
            raise ValueError(f"Invalid surface: {surface}. Valid values: slide, embedded-card")

        if output_compression is not None and not 0 <= output_compression <= 100:
            raise ValueError("output-compression must be between 0 and 100")

        if output_compression is not None and format == "png":
            raise ValueError("output-compression is only supported for jpeg and webp outputs")

        if image_timeout_seconds < 1:
            raise ValueError("image-timeout-seconds must be at least 1")

        if image_max_attempts < 1:
            raise ValueError("image-max-attempts must be at least 1")

        raw_payload = parse_data_input(data_file)
        payload = resolve_visualization_input(
            raw_payload,
            title=title,
            instructions=instructions,
        )
        options = ImageGenerationOptions(
            image_model=image_model,
            response_model=response_model,
            analysis_model=analysis_model,
            analysis_mode=analysis_mode,  # type: ignore[arg-type]
            size=size or ("2048x1152" if surface == "slide" else "1536x1024"),
            quality=quality,  # type: ignore[arg-type]
            output_format=format,  # type: ignore[arg-type]
            output_compression=output_compression,
            surface=surface,  # type: ignore[arg-type]
            include_header=include_header,
            max_data_chars=max_data_chars,
            image_timeout_seconds=image_timeout_seconds,
            image_max_attempts=image_max_attempts,
            dry_run=dry_run,
        )

        with llm_observability_session():
            renderer = GenerativeImageRenderer()
            result = renderer.render(
                payload=payload,
                output_dir=output_dir,
                filename=filename,
                options=options,
                template_image=template_image,
            )

        output_files = [
            get_file_info(result.prompt_path),
            get_file_info(result.analysis_path),
        ]
        if result.output_path is not None:
            output_files.insert(0, get_file_info(result.output_path))

        output_json({
            "success": True,
            "output_files": output_files,
            "backend": "gpt-image",
            "image_api": "images",
            "image_model": image_model,
            "response_model": None,
            "analysis_model": analysis_model,
            "analysis_mode": analysis_mode,
            "surface": surface,
            "size": options.size,
            "include_header": include_header,
            "image_timeout_seconds": image_timeout_seconds,
            "image_max_attempts": image_max_attempts,
            "dry_run": dry_run,
            "used_template_image": result.used_template_image,
            "usage": result.usage,
            "message": (
                "Generative visualization prompt prepared"
                if dry_run
                else "Generative visualization image rendered successfully"
            ),
        })

    except Exception as e:
        output_json({
            "success": False,
            "error": str(e),
        })
        raise typer.Exit(1)


# Config subcommand group
config_app = typer.Typer(help="Manage saved dashboard configurations.")
app.add_typer(config_app, name="config", hidden=True)


@config_app.command("save")
def config_save_command(
    name: Annotated[str, typer.Option("--name", help="Unique name for the config")],
    spec_file: Annotated[Optional[str], typer.Argument(help="Path to spec JSON (reads stdin if omitted)")] = None,
    tags: Annotated[Optional[str], typer.Option("--tags", help="Comma-separated tags")] = None,
    description: Annotated[Optional[str], typer.Option("--description", help="Description of the dashboard")] = None,
) -> None:
    """Save a dashboard specification to the config repository."""
    try:
        from .config import ConfigRepository

        spec = parse_data_input(spec_file)
        repo = ConfigRepository()

        tag_list = [t.strip() for t in tags.split(",")] if tags else []

        metadata = repo.save(
            spec=spec,
            name=name,
            tags=tag_list,
            description=description,
        )

        output_json({
            "success": True,
            "config": {
                "id": metadata.id,
                "name": metadata.name,
                "tags": metadata.tags,
                "created_at": metadata.created_at.isoformat(),
            },
            "message": f"Config '{name}' saved successfully",
        })

    except Exception as e:
        output_json({
            "success": False,
            "error": str(e),
        })
        raise typer.Exit(1)


@config_app.command("list")
def config_list_command(
    tags: Annotated[Optional[str], typer.Option("--tags", help="Filter by tags (comma-separated)")] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum configs to return")] = 20,
) -> None:
    """List saved dashboard configurations."""
    try:
        from .config import ConfigRepository

        repo = ConfigRepository()
        tag_list = [t.strip() for t in tags.split(",")] if tags else None
        configs = repo.list_configs(tags=tag_list, limit=limit)

        output_json({
            "success": True,
            "configs": [
                {
                    "id": c.id,
                    "name": c.name,
                    "description": c.description,
                    "tags": c.tags,
                    "created_at": c.created_at.isoformat(),
                    "last_used_at": c.last_used_at.isoformat() if c.last_used_at else None,
                    "usage_count": c.usage_count,
                }
                for c in configs
            ],
            "count": len(configs),
            "message": f"Found {len(configs)} config(s)",
        })

    except Exception as e:
        output_json({
            "success": False,
            "error": str(e),
        })
        raise typer.Exit(1)


@config_app.command("get")
def config_get_command(
    name_or_id: Annotated[str, typer.Argument(help="Config name or UUID")],
) -> None:
    """Retrieve a saved dashboard configuration by name or ID."""
    try:
        from .config import ConfigRepository

        repo = ConfigRepository()
        result = repo.get(name_or_id)

        if not result:
            output_json({
                "success": False,
                "error": f"Config '{name_or_id}' not found",
            })
            raise typer.Exit(1)

        metadata, spec = result

        output_json({
            "success": True,
            "config": {
                "id": metadata.id,
                "name": metadata.name,
                "description": metadata.description,
                "tags": metadata.tags,
                "created_at": metadata.created_at.isoformat(),
                "last_used_at": metadata.last_used_at.isoformat() if metadata.last_used_at else None,
                "usage_count": metadata.usage_count,
                "schema_fingerprint": metadata.schema_fingerprint,
            },
            "spec": spec,
            "message": f"Retrieved config '{metadata.name}'",
        })

    except Exception as e:
        output_json({
            "success": False,
            "error": str(e),
        })
        raise typer.Exit(1)


@config_app.command("match")
def config_match_command(
    data_file: Annotated[Optional[str], typer.Argument(help="Path to JSON data (reads stdin if omitted)")] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum matches to return")] = 5,
) -> None:
    """Find saved configs that match a data schema."""
    try:
        from .config import ConfigRepository

        data = parse_data_input(data_file)
        repo = ConfigRepository()
        matches = repo.find_by_data(data, limit=limit)

        output_json({
            "success": True,
            "matches": [
                {
                    "id": c.id,
                    "name": c.name,
                    "description": c.description,
                    "tags": c.tags,
                    "usage_count": c.usage_count,
                }
                for c in matches
            ],
            "count": len(matches),
            "message": f"Found {len(matches)} matching config(s)" if matches else "No matching configs found",
        })

    except Exception as e:
        output_json({
            "success": False,
            "error": str(e),
        })
        raise typer.Exit(1)


@config_app.command("delete")
def config_delete_command(
    name_or_id: Annotated[str, typer.Argument(help="Config name or UUID to delete")],
) -> None:
    """Delete a saved configuration from the repository."""
    try:
        from .config import ConfigRepository

        repo = ConfigRepository()
        deleted = repo.delete(name_or_id)

        if deleted:
            output_json({
                "success": True,
                "message": f"Config '{name_or_id}' deleted successfully",
            })
        else:
            output_json({
                "success": False,
                "error": f"Config '{name_or_id}' not found",
            })
            raise typer.Exit(1)

    except Exception as e:
        output_json({
            "success": False,
            "error": str(e),
        })
        raise typer.Exit(1)


@app.command("iterate", hidden=True)
def iterate_command(
    spec_file: Annotated[Optional[str], typer.Argument(help="Path to spec JSON (reads stdin if omitted)")] = None,
    feedback: Annotated[str, typer.Option("--feedback", "-f", help="User feedback to apply")] = "",
    previous_image: Annotated[Optional[str], typer.Option("--previous-image", help="Path to previous render for visual context")] = None,
    output_dir: Annotated[str, typer.Option("--output-dir", help="Directory for output")] = ".",
    theme: Annotated[str, typer.Option("--theme", help="Visual theme")] = "corporate",
    backend: Annotated[str, typer.Option("--backend", help="Rendering backend: delight or legacy")] = "delight",
    visual_mode: Annotated[
        str,
        typer.Option("--visual-mode", help="Delight visual mode: premium_executive, editorial, data_journal"),
    ] = "premium_executive",
    annotations: Annotated[
        bool,
        typer.Option("--annotations/--no-annotations", help="Enable smart chart annotations"),
    ] = True,
    format: Annotated[str, typer.Option("--format", help="Output format: png, svg, pdf")] = "png",
    resolution: Annotated[str, typer.Option("--resolution", help="Output resolution")] = "1080p",
    save_spec: Annotated[bool, typer.Option("--save-spec/--no-save-spec", help="Save modified spec to output dir")] = True,
) -> None:
    """Iterate on a dashboard based on user feedback.

    Takes a dashboard spec and user feedback, uses LLM to interpret the feedback
    and modify the spec, then re-renders the dashboard.

    Example:
        aech-cli-visualize iterate spec.json --feedback "fonts too small, too crowded"
    """
    unsupported_deterministic_renderer("iterate")
    try:
        from .iterate import SpecModifier
        from .dashboard.composer import DashboardComposer
        from .observability import llm_observability_session

        if not feedback:
            output_json({
                "success": False,
                "error": "Feedback is required. Use --feedback 'your feedback here'",
            })
            raise typer.Exit(1)

        if backend not in ("delight", "legacy", "plotly"):
            output_json({
                "success": False,
                "error": "Invalid backend. Supported values: delight, legacy",
            })
            raise typer.Exit(1)

        # Parse input spec
        spec = parse_data_input(spec_file)

        # Initialize modifier
        modifier = SpecModifier()

        # Get previous image path if provided
        image_path = Path(previous_image) if previous_image else None

        # Interpret feedback and generate modifications
        with llm_observability_session():
            modifications = modifier.interpret_feedback(
                feedback=feedback,
                current_spec=spec,
                image_path=image_path,
            )

        # Apply modifications
        new_spec = modifier.apply_modifications(spec, modifications)

        # Render with new spec
        resolved_visual_mode: str | None = None
        if backend == "delight" and format != "svg":
            from .delight import DelightDashboardComposer

            resolved_visual_mode = normalize_visual_mode(visual_mode)
            composer = DelightDashboardComposer(
                new_spec,
                theme=theme,
                visual_mode=resolved_visual_mode,
                auto_annotate_charts=annotations,
            )
            output_path = composer.render(
                output_dir=output_dir,
                filename="dashboard",
                format=format,  # type: ignore
                resolution=resolution,
                scale=1.0,
            )
        else:
            composer = DashboardComposer(new_spec, theme=theme)
            output_path = composer.render(
                output_dir=output_dir,
                filename="dashboard",
                format=format,  # type: ignore
                resolution=resolution,
            )

        # Add image dimensions
        width, height = parse_resolution(resolution)
        file_info = get_file_info(output_path)
        file_info["width"] = width
        file_info["height"] = height

        # Save modified spec if requested
        spec_path = None
        if save_spec:
            spec_path = Path(output_dir) / "dashboard_spec.json"
            with open(spec_path, "w") as f:
                json.dump(new_spec, f, indent=2)

        output_json({
            "success": True,
            "output_files": [file_info],
            "spec_file": str(spec_path) if spec_path else None,
            "backend": "delight" if backend == "delight" and format != "svg" else "legacy",
            "visual_mode": resolved_visual_mode if backend == "delight" and format != "svg" else None,
            "annotations": annotations if backend == "delight" and format != "svg" else None,
            "modifications": {
                "reasoning": modifications.reasoning,
                "style_changes": modifications.style.model_dump(exclude_none=True) if modifications.style else {},
                "widget_count": len(modifications.widget_modifications),
                "layout_changes": modifications.layout_changes,
            },
            "message": f"Dashboard iterated successfully based on feedback",
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
