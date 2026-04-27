"""Tests for GPT Image backed visualization prompt generation."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from aech_cli_visualize.generative.image_renderer import (
    _estimate_gpt_image_2_cost_usd,
    _extract_response_image_result,
)
from aech_cli_visualize.generative import (
    VisualizationAnalysis,
    build_image_prompt,
    resolve_visualization_input,
)
from aech_cli_visualize.main import app
from aech_cli_visualize.observability import resolve_session_path


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


def test_extract_response_image_result() -> None:
    output = type("Output", (), {"type": "image_generation_call", "result": "aW1hZ2U="})()
    response = type("Response", (), {"output": [output]})()

    assert _extract_response_image_result(response) == "aW1hZ2U="


def test_estimate_gpt_image_2_cost_usd() -> None:
    cost = _estimate_gpt_image_2_cost_usd(
        "gpt-image-2",
        {"input_tokens": 1000, "cache_read_tokens": 100, "output_tokens": 2000},
    )

    assert cost == 0.064625


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
