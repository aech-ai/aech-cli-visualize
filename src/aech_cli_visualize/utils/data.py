"""Data parsing utilities for JSON and CSV input."""

import json
import sys
from pathlib import Path
from typing import Any


def parse_json_data(content: str) -> dict[str, Any]:
    """Parse JSON string into dictionary."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
    if not isinstance(data, dict):
        raise ValueError("JSON input must be an object.")
    return data


def parse_jsonl_data(content: str) -> dict[str, Any]:
    """Parse newline-delimited JSON records into a rows payload."""
    rows: list[Any] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            rows.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL on line {line_number}: {exc}") from exc
    if not rows:
        raise ValueError("JSONL input did not contain any records.")
    return {"rows": rows}


def parse_data_input(
    file_path: str | None = None,
    stdin: bool = True,
) -> dict[str, Any]:
    """Parse data from file path or stdin.

    Args:
        file_path: Optional path to JSON file
        stdin: Whether to read from stdin if no file_path

    Returns:
        Parsed data dictionary
    """
    content: str

    if file_path:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {file_path}")
        content = path.read_text()
        if path.suffix.lower() == ".jsonl":
            return parse_jsonl_data(content)
    elif stdin and not sys.stdin.isatty():
        content = sys.stdin.read()
    else:
        raise ValueError("No data input provided. Provide a file path or pipe data to stdin.")

    return parse_json_data(content)
