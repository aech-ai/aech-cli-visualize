# aech-cli-visualize

Render charts, KPIs, tables, and dashboards to presentation-ready images.

## Installation

```bash
pip install -e .
```

## Usage

### Chart

```bash
# From JSON file
aech-cli-visualize chart bar data.json --output-dir ./outputs --title "Sales"

# From stdin
echo '{"x": ["Q1","Q2","Q3","Q4"], "y": [100,150,130,180]}' | \
  aech-cli-visualize chart bar --output-dir ./outputs
```

### KPI Card

```bash
aech-cli-visualize kpi --value 2847 --label "Active Users" --delta "+12%" --output-dir ./outputs
```

### Table

```bash
echo '{"headers": ["Name","Value"], "rows": [["A","100"],["B","200"]]}' | \
  aech-cli-visualize table --output-dir ./outputs
```

### Gauge

```bash
aech-cli-visualize gauge --value 73 --label "Customer Satisfaction" --output-dir ./outputs
```

### Dashboard

```bash
aech-cli-visualize dashboard spec.json --output-dir ./outputs --theme corporate --resolution 1080p
```

## Themes

- `corporate` - Professional blue/gray, clean lines
- `modern` - Vibrant colors, subtle gradients
- `minimal` - Black/white, high data-ink ratio
- `dark` - Dark background, high contrast
- `light` - Light background, soft colors

## Output

All commands return JSON to stdout:

```json
{
  "success": true,
  "output_files": [
    {
      "path": "./outputs/chart.png",
      "format": "png",
      "size_bytes": 245678
    }
  ],
  "message": "Chart rendered successfully"
}
```
