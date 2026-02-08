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
    is_executive = "executive" in purpose.lower()
    if is_executive:
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
    gauge_suggestions = [w for w in suggested_widgets if w.get("widget_type") == "gauge"]
    include_gauge = bool(gauge_suggestions) and rows == 2

    # Filter by key_metrics if specified
    if key_metrics:
        kpi_suggestions = [
            w for w in kpi_suggestions
            if any(m in w.get("data_fields", []) for m in key_metrics)
        ] or kpi_suggestions[:kpi_count]

    if include_gauge and is_executive:
        kpi_count = min(2, max(1, kpi_count))
        top_row_widget_count = kpi_count + 1
    else:
        top_row_widget_count = max(kpi_count, 1)

    kpi_colspan = 12 // top_row_widget_count
    for i, kpi in enumerate(kpi_suggestions[:kpi_count]):
        field_name = kpi.get("data_fields", ["value"])[0]
        # Find field analysis for this field
        field_info = next((f for f in fields if f.get("name") == field_name), {})
        summary = field_info.get("summary", {})
        lower_name = field_name.lower()

        if "revenue" in lower_name and not any(
            token in lower_name for token in ("growth", "rate", "ratio", "pct", "percent")
        ):
            format_value = "${:,.0f}"
        elif any(token in lower_name for token in ("growth", "rate", "ratio", "pct", "percent", "churn")):
            format_value = "{:.1f}%"
        else:
            format_value = "{:,.0f}"

        widgets.append({
            "type": "kpi",
            "position": {"row": 0, "col": col, "rowspan": 1, "colspan": kpi_colspan},
            "config": {
                "value": summary.get("mean", summary.get("max", 0)),
                "label": _humanize_field_name(field_name),
                "format_value": format_value,
            }
        })
        col += kpi_colspan

    # Add gauge as the last card in the top row when available.
    if include_gauge:
        gauge = gauge_suggestions[0]
        field_name = gauge.get("data_fields", ["value"])[0]
        field_info = next((f for f in fields if f.get("name") == field_name), {})
        summary = field_info.get("summary", {})
        metric_name = _humanize_field_name(field_name)

        # Infer sensible scale for score/rate metrics.
        raw_value = float(summary.get("mean", summary.get("max", 0)))
        gauge_value = raw_value
        gauge_min = float(summary.get("min", 0))
        gauge_max = float(summary.get("max", 100))
        gauge_unit = ""
        lower_name = field_name.lower()
        if any(token in lower_name for token in ("nps", "score", "satisfaction", "utilization")):
            gauge_min = 0
            gauge_max = 100
            gauge_unit = "%"
        elif any(token in lower_name for token in ("rate", "ratio", "pct", "percent", "growth", "churn")):
            gauge_unit = "%"
            observed_max = max(gauge_max, raw_value)
            if observed_max <= 1:
                gauge_value = raw_value * 100
                gauge_min = 0
                gauge_max = 100
            elif observed_max <= 10:
                gauge_min = 0
                gauge_max = 10
            elif observed_max <= 25:
                gauge_min = 0
                gauge_max = 25
            else:
                gauge_min = 0
                gauge_max = 100
        if gauge_max <= gauge_min:
            gauge_max = gauge_min + 100

        if any(token in lower_name for token in ("churn", "error", "latency", "defect", "failure")):
            gauge_target = round(gauge_max * 0.3, 2)
        else:
            gauge_target = round(gauge_max * 0.9, 2)
        widgets.append({
            "type": "gauge",
            "position": {"row": 0, "col": col, "rowspan": 1, "colspan": kpi_colspan},
            "config": {
                "value": gauge_value,
                "min": gauge_min,
                "max": gauge_max,
                "target": gauge_target,
                "label": metric_name,
                "unit": gauge_unit,
            }
        })

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
                    "title": f"{_humanize_field_name(y_fields[0])} Over Time" if y_fields else "Trend",
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
                    "title": f"{_humanize_field_name(y_field)} by {_humanize_field_name(x_field)}",
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
        "style": {
            "preset": "default",
            "show_cards": True,
            "show_legend": False,
            "row_heights": [0.82, 1.22] if rows == 2 else [0.8, 1.0, 1.2],
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


def _humanize_field_name(field_name: str) -> str:
    """Format field names for UI labels/titles."""
    raw_parts = [part.replace("_", " ").strip() for part in field_name.split(".") if part.strip()]
    if raw_parts and raw_parts[0].lower() == "metrics":
        raw_parts = raw_parts[1:]

    if raw_parts:
        time_tokens = {"month", "date", "time", "quarter", "year", "week", "day"}
        tail = raw_parts[-1].lower()
        if len(raw_parts) >= 2 and tail in time_tokens:
            return raw_parts[-1].title()

    words: list[str] = []
    for part in raw_parts:
        for word in part.split():
            if not words or words[-1].lower() != word.lower():
                words.append(word)

    return " ".join(words).title()


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
