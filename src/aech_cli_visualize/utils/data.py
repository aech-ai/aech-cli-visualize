"""Data parsing utilities for JSON and CSV input."""

import json
import sys
from pathlib import Path
from typing import Any


def parse_json_data(content: str) -> dict[str, Any]:
    """Parse JSON string into dictionary."""
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


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
    elif stdin and not sys.stdin.isatty():
        content = sys.stdin.read()
    else:
        raise ValueError("No data input provided. Provide a file path or pipe data to stdin.")

    return parse_json_data(content)
