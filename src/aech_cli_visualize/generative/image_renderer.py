"""GPT Image backed visualization renderer."""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError
from pydantic_ai import Agent

from ..model_utils import build_pydantic_ai_model, get_model_settings
from ..observability import append_llm_log_entry, observed_llm_role, timed_llm_call
from .code_analysis import analyze_with_generated_code
from .factual_validator import FactualImageValidator
from .models import FactualValidationResult, VisualizationAnalysis, VisualizationPayload
from .prompting import MAX_PROMPT_DATA_CHARS, build_image_prompt


AnalysisMode = Literal["auto", "llm", "precomputed", "code"]
OutputFormat = Literal["png", "jpeg", "webp"]
ImageQuality = Literal["low", "medium", "high", "auto"]
SurfaceMode = Literal["slide", "embedded-card"]


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
    analysis_model: str = "gpt-5.4"
    analysis_mode: AnalysisMode = "auto"
    size: str = "2048x1152"
    quality: ImageQuality = "medium"
    output_format: OutputFormat = "png"
    output_compression: int | None = None
    surface: SurfaceMode = "slide"
    include_header: bool = False
    max_data_chars: int = MAX_PROMPT_DATA_CHARS
    image_timeout_seconds: int = 135
    image_max_attempts: int = 2
    factual_validation: bool = True
    factual_validation_model: str | None = "gpt-5.4"
    factual_validation_max_attempts: int = 2
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
    validation_path: Path | None = None
    validation_review_path: Path | None = None
    factual_validation: FactualValidationResult | None = None
    validation_attempts: int = 0
    factual_validation_status: Literal["not_run", "skipped", "accepted", "warning"] = "not_run"
    factual_validation_disclaimer: str | None = None
    image_unavailable: bool = False
    image_unavailable_reason: str | None = None


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

        analysis, prompt_data = self._resolve_analysis(
            payload=payload,
            options=options,
            output_dir=output_directory,
            filename=filename,
        )
        prompt = build_image_prompt(
            data=prompt_data,
            analysis=analysis,
            title=payload.title,
            instructions=payload.instructions,
            output_format=options.output_format,
            surface=options.surface,
            include_header=options.include_header,
            template_image=str(template_image) if template_image else None,
            max_data_chars=options.max_data_chars,
        )

        prompt_path = output_directory / f"{filename}.prompt.txt"
        analysis_path = output_directory / f"{filename}.analysis.json"
        prompt_path.write_text(prompt, encoding="utf-8")
        analysis_path.write_text(json.dumps(analysis.model_dump(), indent=2), encoding="utf-8")

        if options.dry_run:
            return GenerativeImageRenderResult(
                output_path=None,
                prompt_path=prompt_path,
                analysis_path=analysis_path,
                analysis=analysis,
                prompt=prompt,
                usage=None,
                used_template_image=template_image is not None,
                validation_path=None,
                validation_review_path=None,
                factual_validation=None,
                validation_attempts=0,
                factual_validation_status="not_run",
                factual_validation_disclaimer=None,
                image_unavailable=False,
                image_unavailable_reason=None,
            )

        output_path = output_directory / f"{filename}.{options.output_format}"
        validation_path = output_directory / f"{filename}.factual_validation.json"
        validation_review_path = output_directory / f"{filename}.factual_review.md"
        usage: dict[str, Any] | None = None
        final_validation: FactualValidationResult | None = None
        validation_attempts = 0
        factual_validation_status: Literal["skipped", "accepted", "warning"] = (
            "accepted" if options.factual_validation else "skipped"
        )
        factual_validation_disclaimer: str | None = None
        image_unavailable = False
        image_unavailable_reason: str | None = None
        generation_prompt = prompt
        max_validation_attempts = (
            max(1, int(options.factual_validation_max_attempts))
            if options.factual_validation
            else 1
        )

        for generation_attempt in range(1, max_validation_attempts + 1):
            prompt_path.write_text(generation_prompt, encoding="utf-8")
            try:
                image_bytes, usage = self._generate_image(
                    prompt=generation_prompt,
                    options=options,
                    template_image=template_image,
                )
                output_path.write_bytes(image_bytes)
            except RuntimeError as exc:
                image_unavailable = True
                image_unavailable_reason = str(exc)
                previous_validation = final_validation
                final_validation = _build_image_unavailable_validation(
                    failure_reason=image_unavailable_reason,
                    previous_validation=previous_validation,
                )
                factual_validation_status = "warning"
                factual_validation_disclaimer = _build_image_unavailable_disclaimer(
                    failure_reason=image_unavailable_reason
                )
                validation_path.write_text(
                    json.dumps(final_validation.model_dump(), indent=2),
                    encoding="utf-8",
                )
                validation_review_path.write_text(
                    _build_image_unavailable_review_note(
                        validation=final_validation,
                        disclaimer=factual_validation_disclaimer,
                    ),
                    encoding="utf-8",
                )
                break

            if not options.factual_validation:
                break

            final_validation = self._validate_generated_image(
                image_path=output_path,
                payload=payload,
                analysis=analysis,
                prompt_data=prompt_data,
                options=options,
            )
            validation_attempts = generation_attempt
            validation_path.write_text(
                json.dumps(final_validation.model_dump(), indent=2),
                encoding="utf-8",
            )
            if final_validation.is_acceptable:
                break

            if generation_attempt >= max_validation_attempts:
                factual_validation_status = "warning"
                factual_validation_disclaimer = _build_factual_validation_disclaimer(
                    validation=final_validation,
                    attempts=generation_attempt,
                    max_attempts=max_validation_attempts,
                )
                validation_review_path.write_text(
                    _build_factual_validation_review_note(
                        validation=final_validation,
                        attempts=generation_attempt,
                        max_attempts=max_validation_attempts,
                        disclaimer=factual_validation_disclaimer,
                    ),
                    encoding="utf-8",
                )
                break

            generation_prompt = self._build_regeneration_prompt(
                base_prompt=prompt,
                validation=final_validation,
            )

        return GenerativeImageRenderResult(
            output_path=None if image_unavailable else output_path,
            prompt_path=prompt_path,
            analysis_path=analysis_path,
            analysis=analysis,
            prompt=prompt,
            usage=usage,
            used_template_image=template_image is not None,
            validation_path=(
                validation_path if options.factual_validation or image_unavailable else None
            ),
            validation_review_path=(
                validation_review_path
                if (options.factual_validation or image_unavailable)
                and factual_validation_status == "warning"
                else None
            ),
            factual_validation=final_validation,
            validation_attempts=validation_attempts,
            factual_validation_status=factual_validation_status,
            factual_validation_disclaimer=factual_validation_disclaimer,
            image_unavailable=image_unavailable,
            image_unavailable_reason=image_unavailable_reason,
        )

    def _validate_generated_image(
        self,
        *,
        image_path: Path,
        payload: VisualizationPayload,
        analysis: VisualizationAnalysis,
        prompt_data: dict[str, Any],
        options: ImageGenerationOptions,
    ) -> FactualValidationResult:
        """Use a vision-capable analysis model to reject fabricated image content."""
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for factual image validation.")

        validator = FactualImageValidator(
            model=options.factual_validation_model or "gpt-5.4",
            api_key=self.api_key,
        )
        return validator.evaluate(
            image_path=image_path,
            analysis=analysis,
            prompt_data=prompt_data,
            title=payload.title,
            instructions=payload.instructions,
            max_data_chars=options.max_data_chars,
        )

    def _build_regeneration_prompt(
        self,
        *,
        base_prompt: str,
        validation: FactualValidationResult,
    ) -> str:
        issues = [
            f"- [{issue.severity}] {issue.kind}: {issue.description} Evidence: {issue.evidence}"
            for issue in validation.issues
        ]
        return "\n".join([
            base_prompt,
            "",
            "Previous generated image failed factual validation.",
            validation.summary,
            "Correct these factual issues without adding new visible data:",
            "\n".join(issues) if issues else "- Unspecified factual mismatch.",
            "",
            "Correction instructions:",
            validation.correction_instructions,
            "",
            "Regenerate the image using only the allowed values and visual elements above.",
        ])

    def _resolve_analysis(
        self,
        *,
        payload: VisualizationPayload,
        options: ImageGenerationOptions,
        output_dir: Path,
        filename: str,
    ) -> tuple[VisualizationAnalysis, dict[str, Any]]:
        """Return analysis and compact data for the image prompt."""
        if options.analysis_mode == "precomputed":
            if payload.analysis is None:
                raise ValueError(
                    "analysis_mode=precomputed requires an 'analysis' object in the input JSON."
                )
            return payload.analysis, payload.data

        if options.analysis_mode == "auto" and payload.analysis is not None:
            return payload.analysis, payload.data

        if options.analysis_mode == "code":
            result = analyze_with_generated_code(
                data=payload.data,
                title=payload.title,
                instructions=payload.instructions,
                model=options.analysis_model,
                api_key=self.api_key,
                output_dir=output_dir,
                filename=filename,
                max_prompt_data_chars=options.max_data_chars,
            )
            return result.analysis, result.prompt_data

        if options.analysis_mode == "auto":
            data_text = json.dumps(payload.data, indent=2, sort_keys=True, default=str)
            if len(data_text) > options.max_data_chars:
                result = analyze_with_generated_code(
                    data=payload.data,
                    title=payload.title,
                    instructions=payload.instructions,
                    model=options.analysis_model,
                    api_key=self.api_key,
                    output_dir=output_dir,
                    filename=filename,
                    max_prompt_data_chars=options.max_data_chars,
                )
                return result.analysis, result.prompt_data

        return self._analyze_with_llm(payload=payload, options=options), payload.data

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

        agent: Agent[None, VisualizationAnalysis] = Agent(
            build_pydantic_ai_model(options.analysis_model, api_key=self.api_key),
            output_type=VisualizationAnalysis,
            instructions=ANALYSIS_INSTRUCTIONS,
            model_settings=get_model_settings(options.analysis_model),
        )
        prompt = "\n".join(
            [
                f"Title: {payload.title or 'Untitled visualization'}",
                f"User instructions: {payload.instructions or 'Analyze and visualize the data.'}",
                "Dataset JSON:",
                data_text,
            ]
        )
        with observed_llm_role("executor"):
            result = agent.run_sync(prompt)
        return result.output

    def _generate_image(
        self,
        *,
        prompt: str,
        options: ImageGenerationOptions,
        template_image: str | Path | None,
    ) -> tuple[bytes, dict[str, Any] | None]:
        """Call GPT Image directly and return decoded image bytes."""
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for GPT Image generation.")

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError(
                "The generative image backend requires the 'openai' package."
            ) from exc

        common_kwargs: dict[str, Any] = {
            "model": options.image_model,
            "prompt": prompt,
            "size": options.size,
            "quality": options.quality,
            "output_format": options.output_format,
        }
        if options.output_compression is not None:
            common_kwargs["output_compression"] = options.output_compression

        max_attempts = max(1, int(options.image_max_attempts))
        client = OpenAI(api_key=self.api_key, timeout=max(1, int(options.image_timeout_seconds)))
        response: Any | None = None
        for attempt in range(1, max_attempts + 1):
            with observed_llm_role("executor"), timed_llm_call() as elapsed_ms:
                try:
                    if template_image is not None:
                        template_path = Path(template_image)
                        if not template_path.exists():
                            raise FileNotFoundError(f"Template image not found: {template_path}")
                        with template_path.open("rb") as image_file:
                            response = client.images.edit(
                                image=image_file,
                                timeout=max(1, int(options.image_timeout_seconds)),
                                **common_kwargs,
                            )
                    else:
                        response = client.images.generate(
                            timeout=max(1, int(options.image_timeout_seconds)),
                            **common_kwargs,
                        )
                    break
                except Exception as exc:
                    error_detail = _format_exception_chain(exc)
                    retryable = _is_retryable_image_error(error_detail)
                    will_retry = retryable and attempt < max_attempts
                    append_llm_log_entry({
                        "model": options.image_model,
                        "operation": "image_generation",
                        "tool_name": "image_generation",
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "reasoning_tokens": 0,
                        "cache_read_tokens": 0,
                        "cache_creation_tokens": 0,
                        "duration_ms": elapsed_ms(),
                        "status": "ERROR",
                        "error": error_detail,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "will_retry": will_retry,
                    })
                    if not will_retry:
                        raise RuntimeError(
                            f"Image generation failed after {attempt}/{max_attempts} attempt(s): "
                            f"{error_detail}"
                        ) from exc
            time.sleep(min(8.0, 1.5 * attempt))

        if response is None:
            raise RuntimeError("Image generation failed before receiving a response.")

        image_base64 = _extract_images_api_result(response)
        if not image_base64:
            raise RuntimeError("GPT Image response did not include base64 image data.")

        usage = _normalize_openai_usage(getattr(response, "usage", None))
        cost_usd = _estimate_gpt_image_2_cost_usd(options.image_model, usage)
        append_llm_log_entry({
            "model": options.image_model,
            "operation": "image_generation",
            "tool_name": "image_generation",
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "reasoning_tokens": usage.get("reasoning_tokens", 0),
            "cache_read_tokens": usage.get("cache_read_tokens", 0),
            "cache_creation_tokens": usage.get("cache_creation_tokens", 0),
            "duration_ms": elapsed_ms(),
            "status": "OK",
            "cost_usd": cost_usd if cost_usd is not None else 0.0,
            "request_messages": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            "response_messages": [{
                "type": "image_generation",
                "response_id": getattr(response, "id", None),
            }],
        })

        return base64.b64decode(image_base64), usage


def _truncate_text(text: Any, max_chars: int) -> str:
    normalized = " ".join(str(text).split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max(0, max_chars - 3)].rstrip() + "..."


def _build_image_unavailable_validation(
    *,
    failure_reason: str,
    previous_validation: FactualValidationResult | None,
) -> FactualValidationResult:
    prior_summary = (
        f" Previous factual validation summary: {previous_validation.summary}"
        if previous_validation is not None
        else ""
    )
    return FactualValidationResult(
        is_acceptable=False,
        summary=(
            "GPT Image did not return image bytes, so no visualization image is "
            "available for this request."
            f"{prior_summary}"
        ),
        issues=list(previous_validation.issues) if previous_validation is not None else [],
        correction_instructions=(
            "Tell the user the visualization is temporarily unavailable and retry GPT Image "
            "generation later. Do not attach a substitute image. Failure reason: "
            f"{_truncate_text(failure_reason, 240)}"
        ),
    )


def _build_image_unavailable_disclaimer(*, failure_reason: str) -> str:
    return (
        "GPT Image generation failed before producing an image, so the requested "
        "visualization is temporarily unavailable and no image is attached. Failure reason: "
        f"{_truncate_text(failure_reason, 220)}"
    )


def _build_image_unavailable_review_note(
    *,
    validation: FactualValidationResult,
    disclaimer: str,
) -> str:
    lines = [
        "# Image Generation Unavailable",
        "",
        disclaimer,
        "",
        "Generation status: warning; no image artifact was produced.",
        f"Review summary: {validation.summary}",
        "",
        "## Findings",
        "",
    ]
    if validation.issues:
        for index, issue in enumerate(validation.issues, start=1):
            lines.extend([
                f"{index}. [{issue.severity}] {issue.kind}",
                f"   - Finding: {issue.description}",
                f"   - Evidence: {issue.evidence}",
            ])
    else:
        lines.append(
            "- No image fact-check findings were available because GPT Image did not "
            "produce bytes for vision validation."
        )
    lines.extend([
        "",
        "## Suggested Correction",
        "",
        validation.correction_instructions,
        "",
    ])
    return "\n".join(lines)


def _extract_images_api_result(response: Any) -> str | None:
    """Extract base64 image data from an OpenAI Images API response."""
    data = getattr(response, "data", None) or []
    if not data:
        return None
    first = data[0]
    result = getattr(first, "b64_json", None)
    if result:
        return str(result)
    return None


def _build_factual_validation_disclaimer(
    *,
    validation: FactualValidationResult,
    attempts: int,
    max_attempts: int,
) -> str:
    issue_count = len(validation.issues)
    issue_label = "issue" if issue_count == 1 else "issues"
    return (
        "Disclaimer: this generated visual was delivered with fact-checker review "
        f"findings after {attempts}/{max_attempts} validation attempt(s). Treat "
        f"the flagged visual elements as potentially inaccurate until reviewed "
        f"against the source data. The validator reported {issue_count} {issue_label}."
    )


def _build_factual_validation_review_note(
    *,
    validation: FactualValidationResult,
    attempts: int,
    max_attempts: int,
    disclaimer: str,
) -> str:
    lines = [
        "# Factual Validation Review",
        "",
        disclaimer,
        "",
        f"Validation status: warning after {attempts}/{max_attempts} attempt(s).",
        f"Validator summary: {validation.summary}",
        "",
        "## Findings",
        "",
    ]
    if not validation.issues:
        lines.append("- No structured issue was returned, but the validator did not accept the image.")
    else:
        for index, issue in enumerate(validation.issues, start=1):
            lines.extend([
                f"{index}. [{issue.severity}] {issue.kind}",
                f"   - Finding: {issue.description}",
                f"   - Evidence: {issue.evidence}",
            ])
    lines.extend([
        "",
        "## Suggested Correction",
        "",
        validation.correction_instructions,
        "",
    ])
    return "\n".join(lines)


def _format_exception_chain(exc: BaseException) -> str:
    parts = [f"{type(exc).__name__}: {exc}"]
    cause = exc.__cause__
    while cause is not None and len(parts) < 8:
        parts.append(f"{type(cause).__name__}: {cause}")
        cause = cause.__cause__
    return " | caused by ".join(parts)


def _is_retryable_image_error(error_detail: str) -> bool:
    retry_markers = (
        "APIConnectionError",
        "APITimeoutError",
        "RemoteProtocolError",
        "Connection error",
        "Server disconnected",
        "timeout",
        "temporarily unavailable",
        "rate limit",
        "status_code: 408",
        "status_code: 409",
        "status_code: 429",
        "status_code: 500",
        "status_code: 502",
        "status_code: 503",
        "status_code: 504",
    )
    non_retry_markers = (
        "invalid_request_error",
        "model_not_found",
        "status_code: 400",
        "status_code: 401",
        "status_code: 403",
        "status_code: 404",
    )
    normalized = error_detail.lower()
    if any(marker.lower() in normalized for marker in non_retry_markers):
        return False
    return any(marker.lower() in normalized for marker in retry_markers)


def _normalize_openai_usage(usage: Any) -> dict[str, int]:
    if usage is None:
        return {
            "requests": 1,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "reasoning_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
        }
    payload = usage.model_dump() if hasattr(usage, "model_dump") else dict(usage)
    input_tokens = int(payload.get("input_tokens") or payload.get("prompt_tokens") or 0)
    output_tokens = int(payload.get("output_tokens") or payload.get("completion_tokens") or 0)
    details = payload.get("input_tokens_details") or {}
    output_details = payload.get("output_tokens_details") or {}
    cache_read_tokens = int(details.get("cached_tokens") or details.get("cache_read_tokens") or 0)
    reasoning_tokens = int(output_details.get("reasoning_tokens") or payload.get("reasoning_tokens") or 0)
    total_tokens = int(payload.get("total_tokens") or input_tokens + output_tokens)
    return {
        "requests": 1,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_creation_tokens": 0,
    }


def _estimate_gpt_image_2_cost_usd(model: str, usage: dict[str, int]) -> float | None:
    """Estimate GPT Image 2 cost from token usage using current standard pricing."""
    if model.split(":", 1)[-1] != "gpt-image-2":
        return None

    input_tokens = max(0, usage.get("input_tokens", 0) - usage.get("cache_read_tokens", 0))
    cached_tokens = usage.get("cache_read_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cost = (input_tokens * 5.00 + cached_tokens * 1.25 + output_tokens * 30.00) / 1_000_000
    return round(cost, 8)
