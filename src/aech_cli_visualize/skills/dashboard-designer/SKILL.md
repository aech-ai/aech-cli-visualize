---
name: dashboard-designer
description: Interactive dashboard design workflow. Analyzes data, asks clarifying questions, generates visualizations, and saves reusable configs. Use when user has raw data and wants a dashboard created collaboratively.
allowed-tools: Read, Bash, Write, Grep, Glob
---

# Dashboard Designer

An interactive skill for designing dashboards from raw data through collaborative conversation.

## When to Use

Use this skill when:
- User has raw data (JSON) and wants a dashboard
- User wants to create a reusable dashboard template
- User asks to "visualize this data" or "make a dashboard"

## Workflow

### Phase 1: Data Ingestion

When user provides data (JSON file or inline):

1. Save inline data to a temporary file if needed
2. Run analysis:
```bash
aech-cli-visualize analyze data.json --questions
```
3. Review the analysis output for field types, patterns, and suggestions

### Phase 2: Question & Answer

Present the generated questions to the user. Key questions typically include:

- **Purpose**: "What is the primary purpose of this dashboard?"
  - Executive summary (high-level KPIs)
  - Operational monitoring (real-time status)
  - Detailed analysis (exploration)

- **Key metrics**: "Which metrics should be most prominent?"
  - Present suggestions from analysis

- **Timeframe**: If temporal data, "What time range should be displayed?"

- **Comparison**: "Do you want to compare across categories/time periods?"

Also check for matching configs:
- If `matching_configs` is non-empty: "Found saved config '{name}' that matches this data structure. Would you like to use it as a starting point?"

### Phase 3: Generate Recommendations

Based on analysis and user answers, generate a dashboard specification:

```bash
python scripts/generate_recommendations.py \
  --analysis analysis.json \
  --answers answers.json \
  --output spec.json
```

Present the recommendation to the user:
- Describe the proposed layout (e.g., "3 KPIs at top, line chart below")
- Explain widget choices (e.g., "Line chart for revenue trend since data is temporal")
- Offer alternatives (e.g., "Would you prefer a bar chart instead?")

### Phase 4: Render Dashboard

Once user approves (or after refinements):

```bash
aech-cli-visualize dashboard spec.json --output-dir ./output --theme corporate
```

For validated rendering with VLM feedback:
```bash
aech-cli-visualize dashboard spec.json --output-dir ./output --theme corporate --vlm-validate
```

Show the user the output path and offer to open/preview.

### Phase 5: Save Configuration

Ask user if they want to save for future use:

```bash
aech-cli-visualize config save \
  --name "user-provided-name" \
  --tags tag1,tag2 \
  --description "Dashboard description" \
  spec.json
```

## CLI Commands Reference

### Analyze Data
```bash
aech-cli-visualize analyze [data_file] [--questions] [--llm/--no-llm]
```
- `data_file`: Path to JSON data (or stdin)
- `--questions`: Include clarifying questions (default: yes)
- `--llm`: Use LLM for enhanced analysis (default: yes)

Returns:
- `analysis.fields`: List of field types and summaries
- `analysis.patterns`: Detected patterns (time_series, comparison, etc.)
- `analysis.suggested_widgets`: Recommended visualizations
- `questions`: Clarifying questions for user
- `schema_fingerprint`: Hash for config matching
- `matching_configs`: Names of configs matching this schema

### Config Management

```bash
# Save a config
aech-cli-visualize config save --name <name> [--tags <tags>] [--description <desc>] [spec_file]

# List configs
aech-cli-visualize config list [--tags <filter>] [--limit N]

# Get config by name
aech-cli-visualize config get <name_or_id>

# Find matching configs for data
aech-cli-visualize config match [data_file] [--limit N]

# Delete config
aech-cli-visualize config delete <name_or_id>
```

### Render Dashboard
```bash
aech-cli-visualize dashboard [spec_file] --output-dir <dir> [--theme <theme>] [--vlm-validate]
```

## Scripts

### scripts/generate_recommendations.py

Generates a dashboard spec from analysis results and user answers:

```bash
python scripts/generate_recommendations.py \
  --analysis analysis.json \
  --answers '{"purpose": "executive", "key_metrics": ["revenue", "users"]}' \
  --output spec.json
```

## Example Interaction

**User**: "I have this sales data, can you make a dashboard?"
```json
{
  "date": ["2025-01", "2025-02", "2025-03", "2025-04"],
  "revenue": [120000, 135000, 142000, 158000],
  "customers": [450, 478, 502, 531],
  "region": ["North", "South", "East", "West"],
  "region_revenue": [45000, 32000, 48000, 33000]
}
```

**Skill** (runs `aech-cli-visualize analyze --questions`):

"I've analyzed your data. Here's what I found:
- **Temporal data**: Monthly dates from Jan-Apr 2025
- **Numeric metrics**: Revenue (trending up 32%) and customers (trending up 18%)
- **Regional breakdown**: 4 regions with revenue distribution

I have a few questions:
1. What is the primary purpose of this dashboard?
   - Executive summary (high-level KPIs)
   - Operational monitoring (detailed trends)
   - Sales team review (regional focus)

2. Which metrics should be most prominent?
   - Revenue
   - Customer count
   - Both equally

Also, I found a saved config 'quarterly-sales-dashboard' that matches this data structure. Would you like to use it?"

**User**: "Executive summary, focus on revenue. Don't use the saved one."

**Skill** (runs `scripts/generate_recommendations.py`):

"Based on your input, here's my recommendation:

**Layout**: 2 rows, 12-column grid
- Row 1: 3 KPI cards (Revenue total, Revenue growth %, Customer count)
- Row 2: Line chart showing revenue trend over time

Should I render this dashboard?"

**User**: "Yes, and use the modern theme"

**Skill** (runs `aech-cli-visualize dashboard spec.json --output-dir ./out --theme modern`):

"Dashboard rendered successfully!
- Output: ./out/dashboard.png (1920x1080)

Would you like to save this configuration for future use?"

**User**: "Yes, call it 'monthly-revenue-exec'"

**Skill** (runs `aech-cli-visualize config save --name monthly-revenue-exec --tags revenue,executive,monthly`):

"Configuration saved!
- Name: monthly-revenue-exec
- Tags: revenue, executive, monthly
- You can reuse this with: `aech-cli-visualize config get monthly-revenue-exec`"

## Reusing Saved Configs

When user provides new data, always check for matching configs first:

```bash
aech-cli-visualize config match data.json
```

If matches found, offer to use them:
- "Found 'monthly-revenue-exec' which matches this data structure. Use it?"
- User can accept (retrieve and render), modify (retrieve and edit), or start fresh
