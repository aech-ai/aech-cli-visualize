"""Schema fingerprinting for data matching."""

import hashlib
import json
from datetime import datetime
from typing import Any


def infer_field_type(values: list[Any]) -> str:
    """Infer the type of a field from sample values.

    Args:
        values: List of values from the field

    Returns:
        Type string: "numeric", "categorical", "temporal", "text", "boolean", "null", "object", "array"
    """
    if not values:
        return "null"

    # Filter out None values for analysis
    non_null = [v for v in values if v is not None]
    if not non_null:
        return "null"

    # Check for nested objects (dicts)
    if all(isinstance(v, dict) for v in non_null):
        return "object"

    # Check for nested arrays
    if all(isinstance(v, list) for v in non_null):
        return "array"

    # Check for boolean
    if all(isinstance(v, bool) for v in non_null):
        return "boolean"

    # Check for numeric
    numeric_count = sum(1 for v in non_null if isinstance(v, (int, float)) and not isinstance(v, bool))
    if numeric_count == len(non_null):
        return "numeric"

    # Check for temporal (date/datetime strings)
    temporal_count = 0
    date_formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y-%m",
        "%Y",
    ]
    for v in non_null:
        if isinstance(v, str):
            for fmt in date_formats:
                try:
                    datetime.strptime(v, fmt)
                    temporal_count += 1
                    break
                except ValueError:
                    continue

    if temporal_count > len(non_null) * 0.8:  # 80% threshold
        return "temporal"

    # Check for categorical (low cardinality strings)
    if all(isinstance(v, str) for v in non_null):
        unique_ratio = len(set(non_null)) / len(non_null)
        if unique_ratio < 0.5:  # Less than 50% unique = categorical
            return "categorical"
        return "text"

    # Mixed or unknown
    return "text"


def compute_schema_fingerprint(data: dict[str, Any]) -> str:
    """Create a deterministic hash of the data schema for matching.

    The fingerprint is based on field names and their inferred types,
    allowing configs to be matched to new data with similar structure.

    Args:
        data: Dictionary with field names as keys and lists of values

    Returns:
        16-character hexadecimal fingerprint
    """
    schema: dict[str, str] = {}

    for key, values in data.items():
        if isinstance(values, list):
            # Infer type from list values
            schema[key] = infer_field_type(values)
        else:
            # Single value - use Python type
            schema[key] = type(values).__name__

    # Sort keys for deterministic output
    canonical = json.dumps(schema, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _safe_cardinality(values: list[Any]) -> int:
    """Compute cardinality, handling unhashable types like dicts."""
    try:
        return len(set(values))
    except TypeError:
        # Unhashable types (dicts, lists) - use JSON serialization
        seen = set()
        for v in values:
            try:
                key = json.dumps(v, sort_keys=True, default=str)
                seen.add(key)
            except (TypeError, ValueError):
                # Fallback: count as unique
                seen.add(id(v))
        return len(seen)


def analyze_field(name: str, values: list[Any]) -> dict[str, Any]:
    """Analyze a single field and return detailed info.

    Args:
        name: Field name
        values: List of values

    Returns:
        Dictionary with field analysis
    """
    field_type = infer_field_type(values)
    non_null = [v for v in values if v is not None]

    analysis = {
        "name": name,
        "type": field_type,
        "cardinality": _safe_cardinality(non_null) if non_null else 0,
        "sample_values": non_null[:5] if non_null else [],
        "summary": {},
    }

    if field_type == "numeric" and non_null:
        numeric_vals = [float(v) for v in non_null]
        analysis["summary"] = {
            "min": min(numeric_vals),
            "max": max(numeric_vals),
            "mean": sum(numeric_vals) / len(numeric_vals),
        }
    elif field_type == "categorical" and non_null:
        from collections import Counter
        try:
            counts = Counter(non_null)
            analysis["summary"] = {
                "unique_values": list(counts.keys()),
                "value_counts": dict(counts.most_common(10)),
            }
        except TypeError:
            # Unhashable values - skip value counts
            analysis["summary"] = {
                "unique_values": [],
                "value_counts": {},
            }
    elif field_type == "temporal" and non_null:
        analysis["summary"] = {
            "first": min(non_null),
            "last": max(non_null),
            "count": len(non_null),
        }

    return analysis
