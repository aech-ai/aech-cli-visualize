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
    try:
        spec = parse_data_input(spec_file)
        width, height = parse_resolution(resolution)

        if vlm_validate:
            # Use validated composer with VLM feedback loop
            from .dashboard.validated_composer import ValidatedDashboardComposer

            composer = ValidatedDashboardComposer(
                spec=spec,
                theme=theme,
                enable_vlm_validation=True,
                max_iterations=vlm_max_iterations,
                vlm_model=vlm_model,
            )

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
                "message": "Dashboard rendered successfully",
            })

    except Exception as e:
        output_json({
            "success": False,
            "error": str(e),
        })
        raise typer.Exit(1)


@app.command("analyze")
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

        data = parse_data_input(data_file)
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


# Config subcommand group
config_app = typer.Typer(help="Manage saved dashboard configurations.")
app.add_typer(config_app, name="config")


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


@app.command("iterate")
def iterate_command(
    spec_file: Annotated[Optional[str], typer.Argument(help="Path to spec JSON (reads stdin if omitted)")] = None,
    feedback: Annotated[str, typer.Option("--feedback", "-f", help="User feedback to apply")] = "",
    previous_image: Annotated[Optional[str], typer.Option("--previous-image", help="Path to previous render for visual context")] = None,
    output_dir: Annotated[str, typer.Option("--output-dir", help="Directory for output")] = ".",
    theme: Annotated[str, typer.Option("--theme", help="Visual theme")] = "corporate",
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
    try:
        from .iterate import SpecModifier
        from .dashboard.composer import DashboardComposer

        if not feedback:
            output_json({
                "success": False,
                "error": "Feedback is required. Use --feedback 'your feedback here'",
            })
            raise typer.Exit(1)

        # Parse input spec
        spec = parse_data_input(spec_file)

        # Initialize modifier
        modifier = SpecModifier()

        # Get previous image path if provided
        image_path = Path(previous_image) if previous_image else None

        # Interpret feedback and generate modifications
        modifications = modifier.interpret_feedback(
            feedback=feedback,
            current_spec=spec,
            image_path=image_path,
        )

        # Apply modifications
        new_spec = modifier.apply_modifications(spec, modifications)

        # Render with new spec
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
