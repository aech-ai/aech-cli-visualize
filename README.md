# aech-cli-visualize

Render charts, KPIs, tables, and dashboards to presentation-ready images for Agent Aech.

## Purpose

This CLI capability enables Agent Aech to generate visual reports without traditional dashboards. The agent queries data from capabilities (e.g., `aech-cli-analytics`, `aech-cli-bms`) and pipes it to `aech-cli-visualize` to produce presentation-ready images.

**Key principle:** Data always flows through `aech-cli-*` capabilities. This CLI is the visualization layer, not a data source.

## Installation

```bash
# Development
uv venv && source .venv/bin/activate
uv pip install -e .

# Build wheel for deployment
uv build
```

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

**Environment Variables:**

| Variable | Description | Default |
| -------- | ----------- | ------- |
| `AECH_LLM_WORKER_MODEL` | Model for iterate command and data analyzer | `anthropic:claude-sonnet-4-20250514` |
| `AECH_VLM_MODEL` | Model for VLM validation (must support vision) | `anthropic:claude-sonnet-4-20250514` |
| `ANTHROPIC_API_KEY` | API key for Anthropic models | - |
| `OPENAI_API_KEY` | API key for OpenAI models | - |

Model format is `provider:model` (e.g., `anthropic:claude-sonnet-4-20250514`, `openai:gpt-4o`).

## CLI Commands

| Command | Description |
|---------|-------------|
| `chart` | Bar, line, pie, scatter, area, heatmap charts |
| `kpi` | Metric cards with value, delta, sparkline |
| `table` | Styled data tables as images |
| `gauge` | Progress/status indicators with thresholds |
| `dashboard` | Multi-widget composition in grid layout |

## Usage Examples

### Chart

```bash
# Bar chart from stdin
echo '{"x": ["Q1","Q2","Q3","Q4"], "y": [100,150,130,180]}' | \
  aech-cli-visualize chart bar --output-dir ./out --title "Quarterly Sales"

# Line chart with multiple series
echo '{"x": ["Jan","Feb","Mar"], "series": [{"name": "2024", "values": [100,120,140]}, {"name": "2023", "values": [90,100,110]}]}' | \
  aech-cli-visualize chart line --output-dir ./out
```

### KPI Card

```bash
aech-cli-visualize kpi --value 2847 --label "Active Users" --delta "+12%" --output-dir ./out

# With currency formatting
aech-cli-visualize kpi --value 2500000 --label "Revenue" --format-value '${:,.0f}' --delta "+15%" --output-dir ./out
```

### Table

```bash
echo '{"headers": ["Product","Units","Revenue"], "rows": [["Widget A","1234","$45,678"],["Widget B","987","$32,100"]]}' | \
  aech-cli-visualize table --output-dir ./out --title "Product Sales"
```

### Gauge

```bash
aech-cli-visualize gauge --value 73 --label "Customer Satisfaction" --min 0 --max 100 --output-dir ./out

# With threshold zones
aech-cli-visualize gauge --value 45 --label "CPU Usage" --thresholds '[{"value":50,"color":"green"},{"value":80,"color":"yellow"},{"value":100,"color":"red"}]' --output-dir ./out
```

### Dashboard

```bash
cat << 'EOF' | aech-cli-visualize dashboard --output-dir ./out --theme corporate
{
  "title": "Q4 Executive Summary",
  "layout": {"columns": 12, "rows": 2},
  "widgets": [
    {"type": "kpi", "position": {"row": 0, "col": 0, "colspan": 4}, "config": {"value": 2500000, "label": "Revenue", "format_value": "${:,.0f}"}},
    {"type": "kpi", "position": {"row": 0, "col": 4, "colspan": 4}, "config": {"value": 847, "label": "Customers", "delta": "+23"}},
    {"type": "kpi", "position": {"row": 0, "col": 8, "colspan": 4}, "config": {"value": 94.2, "label": "NPS"}},
    {"type": "chart", "position": {"row": 1, "col": 0, "colspan": 12}, "config": {"chart_type": "bar", "data": {"x": ["North","South","East","West"], "y": [150000,120000,180000,95000]}, "title": "Revenue by Region"}}
  ]
}
EOF
```

## Input Schemas

### Chart Data

```json
// Single series
{"x": ["Q1", "Q2", "Q3"], "y": [100, 150, 130]}

// Multiple series
{"x": ["Q1", "Q2", "Q3"], "series": [
  {"name": "2024", "values": [100, 150, 130]},
  {"name": "2023", "values": [90, 120, 110]}
]}

// Heatmap
{"x": ["Mon", "Tue", "Wed"], "y": ["Morning", "Afternoon"], "z": [[1, 2, 3], [4, 5, 6]]}
```

### Table Data

```json
{"headers": ["Column 1", "Column 2"], "rows": [["A", "100"], ["B", "200"]]}
```

### Dashboard Specification

```json
{
  "title": "Dashboard Title",
  "layout": {
    "columns": 12,    // Grid columns (default: 12)
    "rows": 2,        // Grid rows
    "aspect_ratio": "16:9"
  },
  "widgets": [
    {
      "type": "kpi|chart|table|gauge",
      "position": {
        "row": 0,       // 0-indexed
        "col": 0,       // 0-indexed
        "colspan": 4,   // Columns to span
        "rowspan": 1    // Rows to span
      },
      "config": { }     // Widget-specific config
    }
  ]
}
```

## Output Format

All commands return JSON to stdout:

```json
{
  "success": true,
  "output_files": [
    {"path": "./out/chart.png", "format": "png", "size_bytes": 245678}
  ],
  "message": "Chart rendered successfully"
}
```

## Themes

| Theme | Description |
|-------|-------------|
| `corporate` | Professional blue/gray, clean lines (default) |
| `modern` | Vibrant colors, subtle gradients |
| `minimal` | Black/white, high data-ink ratio |
| `dark` | Dark background, high contrast |
| `light` | Light background, soft colors |

Theme definitions are in `src/aech_cli_visualize/themes/loader.py`.

## Architecture

```
src/aech_cli_visualize/
├── main.py              # Typer CLI entry point
├── manifest.json        # v4 capability manifest for Agent Aech
├── widgets/
│   ├── base.py          # Abstract base widget
│   ├── chart.py         # Bar, line, pie, scatter, area, heatmap
│   ├── kpi.py           # KPI cards with delta/sparkline
│   ├── table.py         # Styled data tables
│   └── gauge.py         # Gauge indicators
├── dashboard/
│   └── composer.py      # Grid layout engine
├── themes/
│   └── loader.py        # Theme definitions and loading
└── utils/
    ├── data.py          # JSON/stdin parsing
    └── export.py        # Kaleido image export
```

### Key Components

**BaseWidget** (`widgets/base.py`): Abstract base class. All widgets implement `create_figure() -> go.Figure`.

**DashboardComposer** (`dashboard/composer.py`): Uses domain-based positioning to compose multiple widgets. Each widget gets a calculated `[x0, x1], [y0, y1]` domain based on its grid position.

**Theme System** (`themes/loader.py`): Themes are dictionaries with `colors`, `fonts`, and `chart` settings. Applied via `apply_theme_to_figure()`.

## Adding a New Widget

1. Create `widgets/new_widget.py`:
```python
from .base import BaseWidget
import plotly.graph_objects as go

class NewWidget(BaseWidget):
    def __init__(self, config_param: str, theme: str = "corporate"):
        super().__init__({"config_param": config_param}, theme)

    def create_figure(self) -> go.Figure:
        fig = go.Figure()
        # Add traces...
        return fig
```

2. Export from `widgets/__init__.py`

3. Add to `dashboard/composer.py` `_create_widget_figure()`

4. Add CLI command in `main.py`

5. Add to `manifest.json` actions

## Adding a New Theme

Add to `BUILTIN_THEMES` in `themes/loader.py`:

```python
"new_theme": {
    "name": "new_theme",
    "colors": {
        "primary": "#...",
        "secondary": "#...",
        "background": "#...",
        # ... etc
    },
    "fonts": {"title": "Arial", "body": "Arial", "mono": "Consolas"},
    "chart": {"palette": ["#...", "#..."], "gridlines": True}
}
```

## Deployment to Agent Aech

1. Build wheel: `uv build`
2. Copy to aech-main: `cp dist/*.whl /path/to/aech-main/capabilities/clis/`
3. Regenerate manifest: `python capabilities/installer.py`

The installer reads `manifest.json` from inside the wheel and aggregates it into `capabilities/manifest.json`.

## Manifest (v4 Spec)

The `manifest.json` follows CLI_MANIFEST_SPEC_v4.md. Key requirements:
- `spec_version: 4`
- Every action has description with: what/input/output/when
- Every parameter has description with format and valid values
- No implementation details in descriptions

## Dependencies

- **plotly**: Chart generation
- **kaleido**: Static image export (no browser needed)
- **typer**: CLI framework
- **pydantic**: Config validation
- **pandas**: Data manipulation

## Testing

```bash
# Run all tests
pytest

# Test a specific widget
echo '{"x": ["A","B"], "y": [1,2]}' | aech-cli-visualize chart bar --output-dir ./test_out
```

## Style Settings

Dashboard specs support a `style` section for fine-tuning layout and fonts:

```json
{
  "style": {
    "preset": "presentation",
    "font_scale": 1.4,
    "h_spacing": 0.08,
    "v_spacing": 0.10,
    "title_size": 32
  }
}
```

| Setting | Description | Range |
|---------|-------------|-------|
| `preset` | Base preset: compact, default, presentation, spacious | - |
| `font_scale` | Multiplier for all fonts | 0.6 - 2.0 |
| `h_spacing` | Horizontal gap between widgets | 0.01 - 0.15 |
| `v_spacing` | Vertical gap between widgets | 0.01 - 0.15 |
| `title_size` | Dashboard title font size in pixels | 16 - 48 |

**Preset defaults:**

| Preset | font_scale | h_spacing | v_spacing |
|--------|------------|-----------|-----------|
| compact | 0.8 | 0.015 | 0.03 |
| default | 1.0 | 0.02 | 0.04 |
| presentation | 1.4 | 0.035 | 0.06 |
| spacious | 1.2 | 0.04 | 0.07 |

## Iterate Command

Refine dashboards based on natural language feedback:

```bash
aech-cli-visualize iterate spec.json \
  --feedback "fonts too small, charts too crowded" \
  --previous-image ./out/dashboard.png \
  --output-dir ./out
```

The LLM interprets feedback and modifies style settings automatically.

## Agent Usage Patterns

### Worker Agent (Ad-hoc)
```bash
# Query data via capability, pipe to visualize
aech-cli-analytics query sales --group-by region | \
  aech-cli-visualize chart bar --output-dir ./outputs
```

### Skill Builder (Reusable)
Skills compose capabilities via Python scripts:
```python
# scripts/generate_report.py
data = subprocess.run(["aech-cli-analytics", "query", "..."], capture_output=True)
spec = transform_to_dashboard_spec(json.loads(data.stdout))
subprocess.run(["aech-cli-visualize", "dashboard", "--output-dir", "./outputs"], input=json.dumps(spec))
```

### Quality-Assured Dashboard Generation
```python
# Agent Aech pattern for high-quality dashboards
import subprocess
import json

def generate_dashboard_with_qa(spec, output_dir, max_iterations=3):
    """Generate dashboard with iterative QA."""
    for i in range(max_iterations):
        # Render
        result = subprocess.run(
            ["aech-cli-visualize", "dashboard", "--output-dir", output_dir],
            input=json.dumps(spec).encode(),
            capture_output=True
        )
        output = json.loads(result.stdout)
        image_path = output["output_files"][0]["path"]

        # Agent reviews image (VLM call)
        issues = review_dashboard_image(image_path)

        if not issues:
            return output  # Acceptable

        # Iterate with feedback
        feedback = "; ".join(issues)
        result = subprocess.run(
            ["aech-cli-visualize", "iterate", "--feedback", feedback,
             "--previous-image", image_path, "--output-dir", output_dir],
            input=json.dumps(spec).encode(),
            capture_output=True
        )
        spec = json.loads(open(f"{output_dir}/dashboard_spec.json").read())

    return output  # Return best effort after max iterations
```
