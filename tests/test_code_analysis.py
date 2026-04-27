"""Tests for generated Python analysis sandbox execution."""

from __future__ import annotations

import json

import pytest

from aech_cli_visualize.generative.code_analysis import (
    CodeAnalysisFailure,
    _run_analysis_code,
    _validate_analysis_code,
)


def test_generated_analysis_sandbox_allows_safe_python_helpers(tmp_path) -> None:
    output_path = tmp_path / "analysis.json"
    code = """
from typing import Any

def analyze(data: dict) -> dict:
    rows: list[dict[str, Any]] = data.get("sessions") or []
    ts = pd.Timestamp(data.get("timestamp"))

    def safe_float(value):
        try:
            if hasattr(pd, "isna") and pd.isna(value):
                return 0.0
            return float(value)
        except Exception:
            return 0.0

    costs = list(map(lambda row: safe_float(row.get("estimated_cost_usd")), rows))
    return {
        "analysis_data": {
            "total": round(sum(costs), 4),
            "row_type": type(rows).__name__,
            "time_label": ts.strftime("%H:%M:%S"),
        },
        "prompt_data": {
            "costs": costs,
            "first": next(iter(costs), 0.0),
        },
    }
"""

    result = _run_analysis_code(
        code=code,
        data={
            "timestamp": "2026-04-26T23:57:00Z",
            "sessions": [{"estimated_cost_usd": "0.125"}, {"estimated_cost_usd": None}],
        },
        output_path=output_path,
        timeout_seconds=5,
    )

    assert result["analysis_data"]["total"] == 0.125
    assert result["analysis_data"]["row_type"] == "list"
    assert result["analysis_data"]["time_label"] == "23:57:00"
    assert result["prompt_data"]["costs"] == [0.125, 0.0]
    assert json.loads(output_path.read_text(encoding="utf-8")) == result


def test_generated_analysis_sandbox_provides_safe_numeric_helpers(tmp_path) -> None:
    output_path = tmp_path / "analysis.json"
    code = """
def analyze(data: dict) -> dict:
    values = data.get("values") or []
    return {
        "analysis_data": {"ints": [safe_int(value) for value in values]},
        "prompt_data": {"nums": [safe_float(value) for value in values]},
    }
"""

    result = _run_analysis_code(
        code=code,
        data={"values": ["1", None, float("nan"), "bad"]},
        output_path=output_path,
        timeout_seconds=5,
    )

    assert result["analysis_data"]["ints"] == [1, 0, 0, 0]
    assert result["prompt_data"]["nums"] == [1.0, 0.0, 0.0, 0.0]


def test_generated_analysis_validation_rejects_unsafe_int_float() -> None:
    code = """
def analyze(data: dict) -> dict:
    return {
        "analysis_data": {},
        "prompt_data": {"value": int(float(data.get("value", 0)))},
    }
"""

    with pytest.raises(CodeAnalysisFailure, match="int\\(float"):
        _validate_analysis_code(code)
