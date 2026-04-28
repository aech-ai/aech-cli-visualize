"""Tests for post-generation factual image validation."""

from __future__ import annotations

from aech_cli_visualize.generative.factual_validator import FactualImageValidator
from aech_cli_visualize.generative import FactualValidationResult, VisualizationAnalysis


def _analysis_dict() -> dict:
    return {
        "headline": "Spend anomaly detected",
        "narrative": "Agent session spend rose sharply on Wednesday.",
        "key_metrics": [
            {"label": "Peak daily spend", "value": "$1,240", "context": "Wednesday"},
        ],
        "insights": [],
        "recommended_visuals": [
            {
                "kind": "line_chart",
                "title": "Daily session spend",
                "fields": ["date", "spend_usd"],
                "purpose": "Show the midweek spike.",
            }
        ],
        "layout_guidance": "Use one annotated time-series chart.",
        "warnings": [],
    }


def test_factual_validator_sends_image_and_allowed_evidence(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "render.png"
    image_path.write_bytes(b"fake-png")
    captured = {}

    class FakeAgent:
        def __init__(self, *args, **kwargs) -> None:
            captured["agent_kwargs"] = kwargs

        def run_sync(self, content):
            captured["content"] = content
            return type(
                "Result",
                (),
                {
                    "output": FactualValidationResult(
                        is_acceptable=True,
                        summary="All facts are grounded.",
                        issues=[],
                        correction_instructions="No correction needed.",
                    )
                },
            )()

    monkeypatch.setattr("aech_cli_visualize.generative.factual_validator.Agent", FakeAgent)
    monkeypatch.setattr(
        "aech_cli_visualize.generative.factual_validator.build_pydantic_ai_model",
        lambda model, api_key=None: model,
    )

    validator = FactualImageValidator(model="gpt-5.4", api_key="test-key")
    result = validator.evaluate(
        image_path=image_path,
        analysis=VisualizationAnalysis.model_validate(_analysis_dict()),
        prompt_data={"spend_usd": [420, 1240]},
        title="Agent spend",
        instructions="Highlight anomalies.",
    )

    assert result.is_acceptable is True
    assert captured["agent_kwargs"]["output_type"] is FactualValidationResult
    assert "surfaces a raw evidence value in a KPI" in captured["agent_kwargs"]["instructions"]
    prompt, image = captured["content"]
    assert "Allowed typed analysis JSON" in prompt
    assert '"spend_usd":[420,1240]' in prompt
    assert getattr(image, "data", None) or getattr(image, "content", None)
