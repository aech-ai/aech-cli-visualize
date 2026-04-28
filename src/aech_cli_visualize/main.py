"""CLI entry point for aech-cli-visualize."""

import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated, Optional

import typer

from .utils.data import parse_data_input

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
    ] = "gpt-5.4",
    image_model: Annotated[
        str,
        typer.Option("--image-model", help="GPT Image model for raster generation"),
    ] = "gpt-image-2",
    response_model: Annotated[
        str,
        typer.Option("--response-model", help="Deprecated compatibility option; image generation uses the Images API directly"),
    ] = "gpt-5.4",
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
    factual_validate: Annotated[
        bool,
        typer.Option("--factual-validate/--no-factual-validate", help="Validate the generated image against the analysis/data evidence"),
    ] = True,
    factual_validation_model: Annotated[
        Optional[str],
        typer.Option("--factual-validation-model", help="Vision-capable model for post-generation factual validation; defaults to analysis model"),
    ] = None,
    factual_validation_max_attempts: Annotated[
        int,
        typer.Option("--factual-validation-max-attempts", help="Maximum generate/validate attempts before failing"),
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

        if factual_validation_max_attempts < 1:
            raise ValueError("factual-validation-max-attempts must be at least 1")

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
            factual_validation=factual_validate,
            factual_validation_model=factual_validation_model,
            factual_validation_max_attempts=factual_validation_max_attempts,
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
        if result.validation_path is not None:
            output_files.append(get_file_info(result.validation_path))
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
            "factual_validation": factual_validate,
            "factual_validation_model": factual_validation_model or analysis_model,
            "factual_validation_max_attempts": factual_validation_max_attempts,
            "validation_attempts": result.validation_attempts,
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


def run() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    run()
