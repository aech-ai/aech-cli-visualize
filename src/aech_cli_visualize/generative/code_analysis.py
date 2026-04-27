"""Agentic Python analysis for large visualization datasets."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from ..model_utils import build_pydantic_ai_model, get_model_settings
from ..observability import observed_llm_role
from .models import VisualizationAnalysis


CODE_ANALYSIS_INSTRUCTIONS = """You are a senior data analyst writing a small Python analysis function.

Return only a typed object containing Python code. The code must define:

def analyze(data: dict) -> dict:
    ...

The function receives the full visualization payload data as a Python dict.
It must return a JSON-serializable dict with exactly these top-level keys:

{
  "analysis_data": { ... compact findings, metrics, annotations, evidence rows ... },
  "prompt_data": { ... tiny visual evidence brief for image generation ... }
}

Use pandas through the provided global name `pd` if helpful. Imports are only
allowed for pandas, json, math, statistics, datetime, time, typing, and collections.
Do not read files, write files, use network, inspect the process, or call external commands.
The sandbox provides safe_float(value, default=0.0) and safe_int(value, default=0).
Use them for every visible numeric value and for DataFrame rows after joins,
groupby, concat, nlargest, or resampling. Never write int(float(value)); it fails
on missing pandas values.
Ground every number in the provided data shape, sample rows, and deterministic profile.
Prefer concise derived series, ranked evidence rows, and annotations over raw row dumps.
Use the full dataset to compute aggregates, rankings, and representative points,
but keep returned data compact enough for one image prompt. Never return one
point per row unless the dataset has fewer than 160 rows.
The prompt_data object is not for re-analysis. It is the final evidence package
for the image model. Include only visible values: 3-5 KPIs, 3-8 chart points,
2-4 callouts, and 2-6 evidence rows. Use short keys and short strings.
If data.template_reference.visual_schema is present, prompt_data must follow
that schema so the saved template image can be regenerated consistently. Keep
the same top-level keys, collection shapes, and semantic field meanings while
updating all values from the current dataset.
When using pandas frequency or resampling aliases, use lowercase strings such
as "2h" instead of deprecated uppercase aliases such as "2H".
"""


@dataclass(frozen=True)
class CodeAnalysisResult:
    """Validated result from generated Python analysis."""

    analysis: VisualizationAnalysis
    prompt_data: dict[str, Any]
    code_path: Path
    sample_result_path: Path
    full_result_path: Path


class GeneratedAnalysisProgram(BaseModel):
    """LLM-authored analysis program."""

    rationale: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)


class CodeAnalysisFailure(RuntimeError):
    """Raised when generated analysis code cannot be used."""


_BLOCKED_NAMES = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "globals",
    "input",
    "locals",
    "open",
    "setattr",
    "delattr",
    "vars",
}

_BLOCKED_ATTRS = {
    "__class__",
    "__dict__",
    "__globals__",
    "__mro__",
    "__subclasses__",
    "__getattribute__",
    "__setattr__",
    "__delattr__",
    "read_clipboard",
    "read_csv",
    "read_excel",
    "read_feather",
    "read_fwf",
    "read_gbq",
    "read_hdf",
    "read_html",
    "read_json",
    "read_orc",
    "read_parquet",
    "read_pickle",
    "read_sas",
    "read_spss",
    "read_sql",
    "read_sql_query",
    "read_sql_table",
    "read_stata",
    "read_table",
    "read_xml",
    "to_clipboard",
    "to_csv",
    "to_excel",
    "to_feather",
    "to_gbq",
    "to_hdf",
    "to_json",
    "to_latex",
    "to_markdown",
    "to_orc",
    "to_parquet",
    "to_pickle",
    "to_sql",
    "to_stata",
    "to_xml",
}

_ALLOWED_IMPORT_ROOTS = {"collections", "datetime", "json", "math", "pandas", "statistics", "time", "typing"}


def analyze_with_generated_code(
    *,
    data: dict[str, Any],
    title: str | None,
    instructions: str | None,
    model: str,
    api_key: str | None,
    output_dir: str | Path,
    filename: str,
    timeout_seconds: int = 20,
    max_prompt_data_chars: int = 2_000,
) -> CodeAnalysisResult:
    """Generate, validate, and execute Python analysis against the full dataset."""
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for code analysis mode.")

    output_directory = Path(output_dir)
    output_directory.mkdir(parents=True, exist_ok=True)
    code_path = output_directory / f"{filename}.analysis_code.py"
    sample_result_path = output_directory / f"{filename}.analysis_sample.json"
    full_result_path = output_directory / f"{filename}.analysis_full.json"

    retry_feedback: str | None = None
    code = ""
    full_raw: dict[str, Any] = {}
    prompt_data: dict[str, Any] = {}
    for attempt in range(3):
        code = _generate_analysis_code(
            data=data,
            title=title,
            instructions=instructions,
            model=model,
            api_key=api_key,
            max_prompt_data_chars=max_prompt_data_chars,
            retry_feedback=retry_feedback,
        )
        code_path.write_text(code, encoding="utf-8")
        try:
            _validate_analysis_code(code)

            sample_data = _sample_value(data)
            sample_raw = _run_analysis_code(
                code=code,
                data=sample_data,
                output_path=sample_result_path,
                timeout_seconds=timeout_seconds,
            )
            _validate_raw_result(sample_raw, sample=True)

            full_raw = _run_analysis_code(
                code=code,
                data=data,
                output_path=full_result_path,
                timeout_seconds=timeout_seconds,
            )
            prompt_data = _validate_raw_result(full_raw, sample=False)
            prompt_data_chars = _serialized_chars(prompt_data)
            if prompt_data_chars <= max_prompt_data_chars:
                break
            raise CodeAnalysisFailure(
                f"Generated prompt_data is too large ({prompt_data_chars} chars > "
                f"{max_prompt_data_chars}). Aggregate more aggressively: keep at most "
                "8 chart points, 4 callouts, 6 evidence rows, short IDs, short "
                "timestamps, and no raw rows."
            )
        except CodeAnalysisFailure as exc:
            if attempt == 2:
                raise
            retry_feedback = (
                f"Previous generated analysis code failed: {str(exc)[:1400]}. "
                "Rewrite the entire analyze(data) function to avoid that failure "
                "while preserving the user's requested analysis."
            )
            continue
        else:
            break
    else:
        raise CodeAnalysisFailure(retry_feedback or "Generated analysis code failed.")

    analysis = _brief_from_code_result(
        raw_result=full_raw,
        title=title,
        instructions=instructions,
        model=model,
        api_key=api_key,
    )
    return CodeAnalysisResult(
        analysis=analysis,
        prompt_data=prompt_data,
        code_path=code_path,
        sample_result_path=sample_result_path,
        full_result_path=full_result_path,
    )


def _generate_analysis_code(
    *,
    data: dict[str, Any],
    title: str | None,
    instructions: str | None,
    model: str,
    api_key: str,
    max_prompt_data_chars: int,
    retry_feedback: str | None,
) -> str:
    profile = _profile_value(data)
    sample = _sample_value(data)
    visual_schema = _template_visual_schema(data)
    agent: Agent[None, GeneratedAnalysisProgram] = Agent(
        build_pydantic_ai_model(model, api_key=api_key),
        output_type=GeneratedAnalysisProgram,
        instructions=CODE_ANALYSIS_INSTRUCTIONS,
        model_settings=get_model_settings(model),
    )
    prompt = "\n".join(
        [
            f"Title: {title or 'Untitled visualization'}",
            f"User question/instructions: {instructions or 'Analyze the dataset for a clear visual.'}",
            f"Hard prompt_data budget: compact JSON serialization must be <= {max_prompt_data_chars} chars.",
            "Return final image evidence only, not chart-ready source data.",
            "Maximums: 5 KPIs, 8 chart points, 4 callouts, 6 evidence rows, and short strings.",
            *(
                [
                    "Template visual schema JSON. The returned prompt_data must conform to this contract:",
                    json.dumps(visual_schema, indent=2, sort_keys=True, default=str),
                ]
                if visual_schema
                else []
            ),
            *(["Correction required:", retry_feedback] if retry_feedback else []),
            "Dataset profile JSON:",
            json.dumps(profile, indent=2, sort_keys=True, default=str),
            "Cheap sample JSON:",
            json.dumps(sample, indent=2, sort_keys=True, default=str),
        ]
    )
    with observed_llm_role("executor"):
        response = agent.run_sync(prompt)
    return response.output.code


def _template_visual_schema(data: dict[str, Any]) -> dict[str, Any] | None:
    template_reference = data.get("template_reference")
    if not isinstance(template_reference, dict):
        return None
    visual_schema = template_reference.get("visual_schema")
    if isinstance(visual_schema, dict) and visual_schema:
        return visual_schema
    analysis_result = template_reference.get("analysis_result")
    if isinstance(analysis_result, dict):
        prompt_data = analysis_result.get("prompt_data")
        if isinstance(prompt_data, dict) and prompt_data:
            return {"prompt_data": _profile_value(prompt_data)}
    return None


def _validate_analysis_code(code: str) -> None:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise CodeAnalysisFailure(f"Generated analysis code has invalid syntax: {exc}") from exc

    analyze_defs = [
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "analyze"
    ]
    if len(analyze_defs) != 1:
        raise CodeAnalysisFailure("Generated analysis code must define exactly one analyze(data) function.")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root not in _ALLOWED_IMPORT_ROOTS:
                    raise CodeAnalysisFailure(f"Generated analysis code imports blocked module: {alias.name}")
        if isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            if root not in _ALLOWED_IMPORT_ROOTS:
                raise CodeAnalysisFailure(f"Generated analysis code imports blocked module: {node.module}")
        if isinstance(node, ast.Name) and node.id in _BLOCKED_NAMES:
            raise CodeAnalysisFailure(f"Generated analysis code uses blocked name: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr in _BLOCKED_ATTRS:
            raise CodeAnalysisFailure(f"Generated analysis code uses blocked attribute: {node.attr}")
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _BLOCKED_NAMES:
                raise CodeAnalysisFailure(f"Generated analysis code calls blocked function: {func.id}")
            if isinstance(func, ast.Attribute) and func.attr in _BLOCKED_ATTRS:
                raise CodeAnalysisFailure(f"Generated analysis code calls blocked attribute: {func.attr}")
            if (
                isinstance(func, ast.Name)
                and func.id == "int"
                and node.args
                and isinstance(node.args[0], ast.Call)
                and isinstance(node.args[0].func, ast.Name)
                and node.args[0].func.id == "float"
            ):
                raise CodeAnalysisFailure(
                    "Generated analysis code uses int(float(...)); use safe_int(value) "
                    "so pandas NaN/NA values are handled explicitly."
                )
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "astype"
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "int"
            ):
                raise CodeAnalysisFailure(
                    "Generated analysis code uses astype(int); use safe_int/safe_float "
                    "after filling missing values explicitly."
                )


def _run_analysis_code(
    *,
    code: str,
    data: dict[str, Any],
    output_path: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    runner = textwrap.dedent(
        """
        import json
        import math
        import statistics
        import sys
        import time
        from collections import Counter, defaultdict
        from datetime import datetime, timezone

        import pandas as pd

        code_path, input_path, output_path = sys.argv[1:4]
        code = open(code_path, "r", encoding="utf-8").read()
        data = json.loads(open(input_path, "r", encoding="utf-8").read())
        def safe_float(value, default=0.0):
            try:
                if value is None:
                    return float(default)
                if pd.isna(value):
                    return float(default)
                return float(value)
            except Exception:
                return float(default)

        def safe_int(value, default=0):
            try:
                number = safe_float(value, default)
                if math.isnan(number) or math.isinf(number):
                    return int(default)
                return int(number)
            except Exception:
                return int(default)

        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            root = name.split(".", 1)[0]
            if root not in {"collections", "datetime", "json", "math", "pandas", "statistics", "time", "typing"}:
                raise ImportError(f"blocked import: {name}")
            return __import__(name, globals, locals, fromlist, level)

        safe_builtins = {
            "__import__": safe_import,
            "ArithmeticError": ArithmeticError,
            "Exception": Exception,
            "KeyError": KeyError,
            "LookupError": LookupError,
            "TypeError": TypeError,
            "ValueError": ValueError,
            "ZeroDivisionError": ZeroDivisionError,
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "callable": callable,
            "dict": dict,
            "enumerate": enumerate,
            "filter": filter,
            "float": float,
            "format": format,
            "hasattr": hasattr,
            "int": int,
            "iter": iter,
            "isinstance": isinstance,
            "issubclass": issubclass,
            "len": len,
            "list": list,
            "map": map,
            "max": max,
            "min": min,
            "next": next,
            "pow": pow,
            "range": range,
            "repr": repr,
            "round": round,
            "set": set,
            "slice": slice,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "type": type,
            "zip": zip,
        }
        namespace = {
            "__builtins__": safe_builtins,
            "Counter": Counter,
            "defaultdict": defaultdict,
            "datetime": datetime,
            "json": json,
            "math": math,
            "pd": pd,
            "safe_float": safe_float,
            "safe_int": safe_int,
            "statistics": statistics,
            "time": time,
            "timezone": timezone,
        }
        exec(compile(code, code_path, "exec"), namespace, namespace)
        result = namespace["analyze"](data)
        open(output_path, "w", encoding="utf-8").write(json.dumps(result, indent=2, sort_keys=True, default=str))
        """
    )
    with tempfile.TemporaryDirectory(prefix="aech-visualize-analysis-") as temp_dir:
        temp_path = Path(temp_dir)
        code_path = temp_path / "analysis.py"
        input_path = temp_path / "input.json"
        runner_path = temp_path / "runner.py"
        code_path.write_text(code, encoding="utf-8")
        input_path.write_text(json.dumps(data, default=str), encoding="utf-8")
        runner_path.write_text(runner, encoding="utf-8")
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONNOUSERSITE": "1",
        }
        process = subprocess.run(
            [sys.executable, str(runner_path), str(code_path), str(input_path), str(output_path)],
            cwd=str(temp_path),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    if process.returncode != 0:
        detail = (process.stderr or process.stdout or "analysis code failed").strip()
        raise CodeAnalysisFailure(f"Generated analysis code failed: {detail[:1200]}")

    try:
        raw = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CodeAnalysisFailure(f"Generated analysis did not write valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise CodeAnalysisFailure("Generated analysis output must be a JSON object.")
    return raw


def _validate_raw_result(raw: dict[str, Any], *, sample: bool) -> dict[str, Any]:
    analysis_data = raw.get("analysis_data", raw.get("analysis"))
    prompt_data = raw.get("prompt_data")
    if not isinstance(analysis_data, dict):
        raise CodeAnalysisFailure("Generated analysis output missing object key: analysis_data")
    if not isinstance(prompt_data, dict):
        raise CodeAnalysisFailure("Generated analysis output missing object key: prompt_data")
    serialized = json.dumps(raw, default=str)
    if len(serialized) > 80_000:
        phase = "sample" if sample else "full"
        raise CodeAnalysisFailure(
            f"Generated {phase} analysis is too large ({len(serialized)} chars > 80000). "
            "Return compact derived data, not raw rows."
        )
    return prompt_data


def _serialized_chars(value: Any) -> int:
    return len(json.dumps(value, separators=(",", ":"), sort_keys=True, default=str))


def _brief_from_code_result(
    *,
    raw_result: dict[str, Any],
    title: str | None,
    instructions: str | None,
    model: str,
    api_key: str,
) -> VisualizationAnalysis:
    analysis_data = raw_result.get("analysis_data", raw_result.get("analysis"))
    prompt_data = raw_result.get("prompt_data")
    compact_result = {
        "analysis_data": analysis_data,
        "prompt_data": prompt_data,
    }
    agent: Agent[None, VisualizationAnalysis] = Agent(
        build_pydantic_ai_model(model, api_key=api_key),
        output_type=VisualizationAnalysis,
        instructions=(
            "You convert compact Python data-analysis output into a typed visualization brief. "
            "Use only the supplied compact analysis result. Do not invent values. "
            "The brief is for one generated analytical image."
        ),
        model_settings=get_model_settings(model),
    )
    prompt = "\n".join(
        [
            f"Title: {title or 'Untitled visualization'}",
            f"User question/instructions: {instructions or 'Analyze the dataset for a clear visual.'}",
            "Compact Python analysis result JSON:",
            json.dumps(compact_result, indent=2, sort_keys=True, default=str),
        ]
    )
    with observed_llm_role("executor"):
        response = agent.run_sync(prompt)
    return response.output


def _sample_value(value: Any, *, max_rows: int = 80, max_keys: int = 24) -> Any:
    if isinstance(value, list):
        if len(value) <= max_rows:
            return [_sample_value(item, max_rows=max_rows, max_keys=max_keys) for item in value]
        head_count = max_rows // 2
        tail_count = max_rows - head_count
        sampled = value[:head_count] + value[-tail_count:]
        return [_sample_value(item, max_rows=max_rows, max_keys=max_keys) for item in sampled]
    if isinstance(value, dict):
        items = list(value.items())[:max_keys]
        return {
            str(key): _sample_value(item_value, max_rows=max_rows, max_keys=max_keys)
            for key, item_value in items
        }
    return value


def _profile_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return {"type": type(value).__name__}
    if isinstance(value, dict):
        return {
            "type": "object",
            "keys": list(value.keys()),
            "fields": {
                str(key): _profile_value(item_value, depth=depth + 1)
                for key, item_value in list(value.items())[:24]
            },
        }
    if isinstance(value, list):
        profile: dict[str, Any] = {"type": "array", "count": len(value)}
        if value:
            profile["item_profile"] = _profile_value(value[0], depth=depth + 1)
        if value and all(isinstance(item, dict) for item in value):
            profile["columns"] = _profile_table(value)
        return profile
    return {"type": type(value).__name__, "example": value}


def _profile_table(rows: list[Any]) -> dict[str, Any]:
    columns: dict[str, list[Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key, value in row.items():
            columns.setdefault(str(key), []).append(value)

    profile: dict[str, Any] = {}
    for key, values in columns.items():
        non_null = [value for value in values if value is not None and value != ""]
        numeric = [float(value) for value in non_null if isinstance(value, (int, float))]
        column_profile: dict[str, Any] = {
            "non_null": len(non_null),
            "null": len(values) - len(non_null),
            "example": non_null[0] if non_null else None,
        }
        if numeric:
            column_profile.update({
                "min": min(numeric),
                "max": max(numeric),
                "sum": sum(numeric),
            })
        else:
            distinct = sorted({str(value) for value in non_null})[:12]
            column_profile["distinct_sample"] = distinct
        profile[key] = column_profile
    return profile
