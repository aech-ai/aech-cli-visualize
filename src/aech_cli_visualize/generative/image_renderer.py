"""GPT Image backed visualization renderer."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from .models import VisualizationAnalysis, VisualizationPayload
from .prompting import MAX_PROMPT_DATA_CHARS, build_image_prompt


AnalysisMode = Literal["auto", "llm", "precomputed"]
OutputFormat = Literal["png", "jpeg", "webp"]
ImageQuality = Literal["low", "medium", "high", "auto"]


ANALYSIS_INSTRUCTIONS = """You are an expert analytical visualization agent.

Analyze the user's dataset and visualization instructions, then return a typed
brief for a single generated image. The brief must be grounded in the provided
data only. Do not invent numbers, dimensions, categories, or conclusions.

Choose a compact visual story that can fit into one polished image: key metrics,
the clearest chart forms, and short insight annotations. Prefer anomaly,
trend, comparison, and operational risk findings over decorative summaries.
"""


@dataclass(frozen=True)
class ImageGenerationOptions:
    """Generation settings for GPT Image."""

    image_model: str = "gpt-image-2"
    analysis_model: str = "gpt-5.5"
    analysis_mode: AnalysisMode = "auto"
    size: str = "1536x1024"
    quality: ImageQuality = "medium"
    output_format: OutputFormat = "png"
    output_compression: int | None = None
    max_data_chars: int = MAX_PROMPT_DATA_CHARS
    dry_run: bool = False


@dataclass(frozen=True)
class GenerativeImageRenderResult:
    """Result returned by the generative renderer."""

    output_path: Path | None
    prompt_path: Path
    analysis_path: Path
    analysis: VisualizationAnalysis
    prompt: str
    usage: dict[str, Any] | None
    used_template_image: bool


def resolve_visualization_input(
    payload: dict[str, Any],
    *,
    title: str | None = None,
    instructions: str | None = None,
) -> VisualizationPayload:
    """Normalize accepted CLI JSON shapes into a visualization payload."""
    if "data" in payload:
        candidate = {
            "data": payload["data"],
            "title": title if title is not None else payload.get("title"),
            "instructions": instructions if instructions is not None else payload.get("instructions"),
            "analysis": payload.get("analysis"),
        }
    else:
        candidate = {
            "data": payload,
            "title": title,
            "instructions": instructions,
            "analysis": None,
        }

    try:
        return VisualizationPayload.model_validate(candidate)
    except ValidationError as exc:
        raise ValueError(f"Invalid generative visualization payload: {exc}") from exc


class GenerativeImageRenderer:
    """Render an analysis-rich data image with GPT Image."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")

    def render(
        self,
        *,
        payload: VisualizationPayload,
        output_dir: str | Path,
        filename: str,
        options: ImageGenerationOptions,
        template_image: str | Path | None = None,
    ) -> GenerativeImageRenderResult:
        """Analyze data, build a prompt, and optionally generate an image."""
        output_directory = Path(output_dir)
        output_directory.mkdir(parents=True, exist_ok=True)

        analysis = self._resolve_analysis(payload=payload, options=options)
        prompt = build_image_prompt(
            data=payload.data,
            analysis=analysis,
            title=payload.title,
            instructions=payload.instructions,
            output_format=options.output_format,
            template_image=str(template_image) if template_image else None,
            max_data_chars=options.max_data_chars,
        )

        prompt_path = output_directory / f"{filename}.prompt.txt"
        analysis_path = output_directory / f"{filename}.analysis.json"
        prompt_path.write_text(prompt)
        analysis_path.write_text(json.dumps(analysis.model_dump(), indent=2))

        if options.dry_run:
            return GenerativeImageRenderResult(
                output_path=None,
                prompt_path=prompt_path,
                analysis_path=analysis_path,
                analysis=analysis,
                prompt=prompt,
                usage=None,
                used_template_image=template_image is not None,
            )

        image_bytes, usage = self._generate_image(
            prompt=prompt,
            options=options,
            template_image=template_image,
        )

        output_path = output_directory / f"{filename}.{options.output_format}"
        output_path.write_bytes(image_bytes)

        return GenerativeImageRenderResult(
            output_path=output_path,
            prompt_path=prompt_path,
            analysis_path=analysis_path,
            analysis=analysis,
            prompt=prompt,
            usage=usage,
            used_template_image=template_image is not None,
        )

    def _resolve_analysis(
        self,
        *,
        payload: VisualizationPayload,
        options: ImageGenerationOptions,
    ) -> VisualizationAnalysis:
        """Return precomputed analysis or call the analysis model."""
        if options.analysis_mode == "precomputed":
            if payload.analysis is None:
                raise ValueError(
                    "analysis_mode=precomputed requires an 'analysis' object in the input JSON."
                )
            return payload.analysis

        if options.analysis_mode == "auto" and payload.analysis is not None:
            return payload.analysis

        return self._analyze_with_llm(payload=payload, options=options)

    def _analyze_with_llm(
        self,
        *,
        payload: VisualizationPayload,
        options: ImageGenerationOptions,
    ) -> VisualizationAnalysis:
        """Use OpenAI typed outputs for the reasoning step."""
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required for LLM analysis. Provide a typed "
                "'analysis' object and use analysis_mode=precomputed, or set OPENAI_API_KEY."
            )

        data_text = json.dumps(payload.data, indent=2, sort_keys=True, default=str)
        if len(data_text) > options.max_data_chars:
            raise ValueError(
                "Data is too large for LLM analysis "
                f"({len(data_text)} chars > {options.max_data_chars}). "
                "Pre-aggregate the dataset before calling the generative image backend."
            )

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError(
                "The generative image backend requires the 'openai' package."
            ) from exc

        client = OpenAI(api_key=self.api_key)
        response = client.responses.parse(
            model=options.analysis_model,
            instructions=ANALYSIS_INSTRUCTIONS,
            input="\n".join([
                f"Title: {payload.title or 'Untitled visualization'}",
                f"User instructions: {payload.instructions or 'Analyze and visualize the data.'}",
                "Dataset JSON:",
                data_text,
            ]),
            text_format=VisualizationAnalysis,
        )
        if response.output_parsed is None:
            raise RuntimeError("Analysis model returned no parsed VisualizationAnalysis output.")
        return response.output_parsed

    def _generate_image(
        self,
        *,
        prompt: str,
        options: ImageGenerationOptions,
        template_image: str | Path | None,
    ) -> tuple[bytes, dict[str, Any] | None]:
        """Call GPT Image and return decoded image bytes."""
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for GPT Image generation.")

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError(
                "The generative image backend requires the 'openai' package."
            ) from exc

        client = OpenAI(api_key=self.api_key)
        common_kwargs: dict[str, Any] = {
            "model": options.image_model,
            "prompt": prompt,
            "size": options.size,
            "quality": options.quality,
            "output_format": options.output_format,
        }
        if options.output_compression is not None:
            common_kwargs["output_compression"] = options.output_compression

        if template_image is not None:
            template_path = Path(template_image)
            if not template_path.exists():
                raise FileNotFoundError(f"Template image not found: {template_path}")
            with template_path.open("rb") as image_file:
                response = client.images.edit(image=image_file, **common_kwargs)
        else:
            response = client.images.generate(**common_kwargs)

        if not response.data or not response.data[0].b64_json:
            raise RuntimeError("GPT Image response did not include base64 image data.")

        usage = None
        if getattr(response, "usage", None) is not None:
            usage_obj = response.usage
            usage = usage_obj.model_dump() if hasattr(usage_obj, "model_dump") else dict(usage_obj)

        return base64.b64decode(response.data[0].b64_json), usage
