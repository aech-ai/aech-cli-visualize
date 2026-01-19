#!/usr/bin/env python3
"""Generate dashboard specification from analysis and user answers.

Usage:
    python generate_recommendations.py --analysis analysis.json --answers '{"purpose": "executive"}' --output spec.json
    python generate_recommendations.py --analysis analysis.json --answers answers.json --output spec.json
"""

import argparse
import json
import sys
from pathlib import Path


def load_json(path_or_string: str) -> dict:
    """Load JSON from file path or inline string."""
    if path_or_string.startswith("{"):
        return json.loads(path_or_string)
    with open(path_or_string) as f:
        return json.load(f)


def generate_spec(analysis: dict, answers: dict) -> dict:
    """Generate dashboard specification from analysis and user answers.

    Args:
        analysis: Output from `aech-cli-visualize analyze`
        answers: User answers to clarifying questions

    Returns:
        Dashboard specification dictionary
    """
    purpose = answers.get("purpose", "executive")
    key_metrics = answers.get("key_metrics", [])

    # Extract analysis data
    fields = analysis.get("analysis", {}).get("fields", [])
    patterns = analysis.get("analysis", {}).get("patterns", [])
    suggested_widgets = analysis.get("analysis", {}).get("suggested_widgets", [])

    # Determine layout based on purpose
    if "executive" in purpose.lower():
        # Executive: KPIs prominent, one main chart
        rows = 2
        kpi_count = min(3, len([w for w in suggested_widgets if w.get("widget_type") == "kpi"]))
    elif "operational" in purpose.lower():
        # Operational: More charts, detailed view
        rows = 3
        kpi_count = min(4, len([w for w in suggested_widgets if w.get("widget_type") == "kpi"]))
    else:
        # Analysis: Balanced
        rows = 2
        kpi_count = min(2, len([w for w in suggested_widgets if w.get("widget_type") == "kpi"]))

    # Build widgets
    widgets = []
    col = 0
    row = 0

    # Add KPI widgets
    kpi_suggestions = [w for w in suggested_widgets if w.get("widget_type") == "kpi"]

    # Filter by key_metrics if specified
    if key_metrics:
        kpi_suggestions = [
            w for w in kpi_suggestions
            if any(m in w.get("data_fields", []) for m in key_metrics)
        ] or kpi_suggestions[:kpi_count]

    kpi_colspan = 12 // max(kpi_count, 1)
    for i, kpi in enumerate(kpi_suggestions[:kpi_count]):
        field_name = kpi.get("data_fields", ["value"])[0]
        # Find field analysis for this field
        field_info = next((f for f in fields if f.get("name") == field_name), {})
        summary = field_info.get("summary", {})

        widgets.append({
            "type": "kpi",
            "position": {"row": 0, "col": col, "rowspan": 1, "colspan": kpi_colspan},
            "config": {
                "value": summary.get("mean", summary.get("max", 0)),
                "label": field_name.replace("_", " ").title(),
                "format_value": "${:,.0f}" if "revenue" in field_name.lower() else "{:,.0f}",
            }
        })
        col += kpi_colspan

    # Add chart widgets based on patterns
    chart_row = 1
    chart_col = 0

    for pattern in patterns:
        if chart_row >= rows:
            break

        pattern_type = pattern.get("pattern_type")
        involved_fields = pattern.get("involved_fields", [])

        if pattern_type == "time_series" and len(involved_fields) >= 2:
            # Line chart for time series
            x_field = involved_fields[0]
            y_fields = involved_fields[1:]

            # Find actual data
            x_data = _extract_field_data(fields, x_field)
            y_data = _extract_field_data(fields, y_fields[0] if y_fields else x_field)

            widgets.append({
                "type": "chart",
                "position": {"row": chart_row, "col": chart_col, "rowspan": 1, "colspan": 6},
                "config": {
                    "chart_type": "line",
                    "title": f"{y_fields[0].replace('_', ' ').title()} Over Time" if y_fields else "Trend",
                    "data": {
                        "x": x_data.get("sample_values", []),
                        "y": y_data.get("sample_values", []),
                    }
                }
            })
            chart_col += 6

        elif pattern_type == "comparison" and len(involved_fields) >= 2:
            # Bar chart for comparison
            x_field = involved_fields[0]
            y_field = involved_fields[1] if len(involved_fields) > 1 else involved_fields[0]

            x_data = _extract_field_data(fields, x_field)
            y_data = _extract_field_data(fields, y_field)

            widgets.append({
                "type": "chart",
                "position": {"row": chart_row, "col": chart_col, "rowspan": 1, "colspan": 6},
                "config": {
                    "chart_type": "bar",
                    "title": f"{y_field.replace('_', ' ').title()} by {x_field.replace('_', ' ').title()}",
                    "data": {
                        "x": x_data.get("sample_values", []),
                        "y": y_data.get("sample_values", []),
                    }
                }
            })
            chart_col += 6

        if chart_col >= 12:
            chart_col = 0
            chart_row += 1

    # Build final spec
    spec = {
        "title": _generate_title(answers, fields),
        "layout": {
            "columns": 12,
            "rows": rows,
            "aspect_ratio": "16:9",
        },
        "widgets": widgets,
    }

    return spec


def _extract_field_data(fields: list, field_name: str) -> dict:
    """Extract field data by name."""
    for field in fields:
        if field.get("name") == field_name:
            return field
    return {}


def _generate_title(answers: dict, fields: list) -> str:
    """Generate a dashboard title based on answers and data."""
    purpose = answers.get("purpose", "").lower()
    key_metrics = answers.get("key_metrics", [])

    if "executive" in purpose:
        prefix = "Executive Dashboard"
    elif "operational" in purpose:
        prefix = "Operations Dashboard"
    else:
        prefix = "Dashboard"

    # Add metric focus if specified
    if key_metrics:
        metric_str = " & ".join(m.replace("_", " ").title() for m in key_metrics[:2])
        return f"{prefix} - {metric_str}"

    return prefix


def main():
    parser = argparse.ArgumentParser(
        description="Generate dashboard spec from analysis and answers"
    )
    parser.add_argument(
        "--analysis",
        required=True,
        help="Path to analysis JSON or inline JSON string",
    )
    parser.add_argument(
        "--answers",
        required=True,
        help="Path to answers JSON or inline JSON string",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for generated spec",
    )

    args = parser.parse_args()

    try:
        analysis = load_json(args.analysis)
        answers = load_json(args.answers)

        spec = generate_spec(analysis, answers)

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(spec, f, indent=2)

        print(json.dumps({
            "success": True,
            "output": str(output_path),
            "widgets": len(spec.get("widgets", [])),
            "message": f"Generated spec with {len(spec.get('widgets', []))} widgets",
        }))

    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": str(e),
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
