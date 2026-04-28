"""Tests for GPT Image backed visualization prompt generation."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from typer.testing import CliRunner

from aech_cli_visualize.generative.image_renderer import (
    GenerativeImageRenderer,
    ImageGenerationOptions,
    _estimate_gpt_image_2_cost_usd,
    _extract_images_api_result,
    _is_retryable_image_error,
)
from aech_cli_visualize.generative import (
    VisualizationAnalysis,
    build_image_prompt,
    resolve_visualization_input,
)
from aech_cli_visualize.main import app
from aech_cli_visualize.observability import (
    _missing_observability_dependency_message,
    resolve_session_path,
)


def _analysis_dict() -> dict:
    return {
        "headline": "Spend anomaly detected",
        "narrative": "Agent session spend rose sharply on Wednesday.",
        "key_metrics": [
            {"label": "Peak daily spend", "value": "$1,240", "context": "Wednesday"},
            {"label": "Baseline spend", "value": "$420", "context": "Trailing weekday average"},
        ],
        "insights": [
            {
                "label": "Wednesday spike",
                "explanation": "Spend was 2.95x the weekday baseline.",
                "severity": "critical",
                "evidence": ["Wednesday: $1,240", "Baseline: $420"],
            }
        ],
        "recommended_visuals": [
            {
                "kind": "line_chart",
                "title": "Daily session spend",
                "fields": ["date", "spend_usd"],
                "purpose": "Show the midweek spike against the surrounding days.",
            }
        ],
        "layout_guidance": "Use a single annotated time-series chart with KPI callouts.",
        "warnings": ["Values are sample data."],
    }


def test_resolve_visualization_input_accepts_wrapped_payload() -> None:
    payload = resolve_visualization_input({
        "title": "Agent spend",
        "instructions": "Highlight anomalies.",
        "data": {"date": ["Mon", "Tue"], "spend_usd": [420, 1240]},
        "analysis": _analysis_dict(),
    })

    assert payload.title == "Agent spend"
    assert payload.instructions == "Highlight anomalies."
    assert payload.analysis is not None
    assert payload.analysis.headline == "Spend anomaly detected"


def test_build_image_prompt_includes_data_analysis_and_constraints() -> None:
    analysis = VisualizationAnalysis.model_validate(_analysis_dict())
    prompt = build_image_prompt(
        data={"date": ["Mon", "Tue"], "spend_usd": [420, 1240]},
        analysis=analysis,
        title="Agent spend",
        instructions="Highlight anomalies.",
        output_format="png",
        surface="embedded-card",
        include_header=False,
    )

    assert "Spend anomaly detected" in prompt
    assert "Wednesday spike" in prompt
    assert '"spend_usd"' in prompt
    assert "Use only these values; do not infer new numbers" in prompt
    assert "Quiet in-app analytical card" in prompt
    assert "No large header band" in prompt


def test_build_image_prompt_treats_template_as_composition_contract() -> None:
    analysis = VisualizationAnalysis.model_validate(_analysis_dict())
    prompt = build_image_prompt(
        data={"date": ["Mon", "Tue"], "spend_usd": [420, 1240]},
        analysis=analysis,
        title="Agent spend",
        instructions="Highlight anomalies.",
        output_format="png",
        surface="embedded-card",
        include_header=False,
        template_image="/tmp/template.png",
    )

    assert "primary composition contract" in prompt
    assert "Apply the user's requested changes" in prompt


def test_image_command_dry_run_with_precomputed_analysis(tmp_path) -> None:
    input_path = tmp_path / "payload.json"
    input_path.write_text(json.dumps({
        "title": "Agent spend",
        "instructions": "Highlight anomalies.",
        "data": {"date": ["Mon", "Tue", "Wed"], "spend_usd": [420, 430, 1240]},
        "analysis": _analysis_dict(),
    }))

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "image",
            str(input_path),
            "--output-dir",
            str(tmp_path),
            "--analysis-mode",
            "precomputed",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    output = json.loads(result.output)
    assert output["success"] is True
    assert output["dry_run"] is True
    assert output["backend"] == "gpt-image"
    assert output["surface"] == "slide"
    assert output["size"] == "2048x1152"
    assert output["include_header"] is False
    assert (tmp_path / "generative_visual.prompt.txt").exists()
    assert (tmp_path / "generative_visual.analysis.json").exists()


def test_deterministic_renderer_commands_are_unsupported() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["chart", "bar"])

    assert result.exit_code == 1
    output = json.loads(result.output)
    assert output["success"] is False
    assert output["replacement"] == "image"
    assert "no longer supported" in output["error"]


def test_cli_help_only_advertises_generative_image_command() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "image" in result.output
    assert "chart" not in result.output
    assert "dashboard" not in result.output


def test_image_command_rejects_png_compression(tmp_path) -> None:
    input_path = tmp_path / "payload.json"
    input_path.write_text(json.dumps({
        "data": {"date": ["Mon"], "spend_usd": [420]},
        "analysis": _analysis_dict(),
    }))

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "image",
            str(input_path),
            "--output-dir",
            str(tmp_path),
            "--analysis-mode",
            "precomputed",
            "--dry-run",
            "--format",
            "png",
            "--output-compression",
            "50",
        ],
    )

    assert result.exit_code == 1
    output = json.loads(result.output)
    assert output["success"] is False
    assert "jpeg and webp" in output["error"]


def test_extract_images_api_result() -> None:
    image_data = type("ImageData", (), {"b64_json": "aW1hZ2U="})()
    response = type("Response", (), {"data": [image_data]})()

    assert _extract_images_api_result(response) == "aW1hZ2U="


def test_estimate_gpt_image_2_cost_usd() -> None:
    cost = _estimate_gpt_image_2_cost_usd(
        "gpt-image-2",
        {"input_tokens": 1000, "cache_read_tokens": 100, "output_tokens": 2000},
    )

    assert cost == 0.064625


def test_retryable_image_error_classification() -> None:
    assert _is_retryable_image_error(
        "APIConnectionError: Connection error. | caused by RemoteProtocolError: Server disconnected"
    )
    assert _is_retryable_image_error("APITimeoutError: request timed out")
    assert not _is_retryable_image_error(
        "BadRequestError: Error code: 400 - {'error': {'code': 'model_not_found'}}"
    )


def test_gpt_image_2_template_edit_omits_unsupported_input_fidelity(monkeypatch, tmp_path) -> None:
    template_path = tmp_path / "template.png"
    template_path.write_bytes(b"template")
    image_base64 = base64.b64encode(b"image-bytes").decode("ascii")

    class FakeImages:
        def __init__(self) -> None:
            self.edit_kwargs: dict | None = None

        def edit(self, **kwargs):
            self.edit_kwargs = kwargs
            image_data = type("ImageData", (), {"b64_json": image_base64})()
            return type("Response", (), {"data": [image_data], "usage": None})()

    class FakeOpenAI:
        last_instance: "FakeOpenAI | None" = None

        def __init__(self, **_kwargs) -> None:
            self.images = FakeImages()
            FakeOpenAI.last_instance = self

    import openai

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)

    renderer = GenerativeImageRenderer(api_key="test-key")
    image_bytes, _usage = renderer._generate_image(
        prompt="Use the template and update the data.",
        options=ImageGenerationOptions(image_model="gpt-image-2"),
        template_image=template_path,
    )

    assert image_bytes == b"image-bytes"
    assert FakeOpenAI.last_instance is not None
    edit_kwargs = FakeOpenAI.last_instance.images.edit_kwargs
    assert edit_kwargs is not None
    assert edit_kwargs["model"] == "gpt-image-2"
    assert "input_fidelity" not in edit_kwargs


def test_resolve_session_path_uses_standard_aech_session(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("AECH_SESSION_PATH", raising=False)
    monkeypatch.delenv("LLM_LOG_PATH", raising=False)
    monkeypatch.setenv("AECH_SESSION_ID", "session-123")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert resolve_session_path() == tmp_path / ".aech" / "sessions" / "session-123"


def test_resolve_session_path_prefers_llm_log_path(monkeypatch, tmp_path) -> None:
    session_path = tmp_path / ".aech" / "sessions" / "session-456"
    monkeypatch.delenv("AECH_SESSION_PATH", raising=False)
    monkeypatch.setenv("LLM_LOG_PATH", str(session_path / "llm.jsonl"))
    monkeypatch.setenv("AECH_SESSION_ID", "ignored")

    assert resolve_session_path() == session_path


def test_observability_error_names_missing_transitive_dependency() -> None:
    error = ModuleNotFoundError("No module named 'opentelemetry.sdk'", name="opentelemetry.sdk")

    message = _missing_observability_dependency_message(error)

    assert "opentelemetry.sdk" in message
    assert "aech_llm_observability package" not in message


def test_observability_error_names_missing_runtime_package() -> None:
    error = ModuleNotFoundError(
        "No module named 'aech_llm_observability'",
        name="aech_llm_observability",
    )

    message = _missing_observability_dependency_message(error)

    assert "aech_llm_observability package" in message
