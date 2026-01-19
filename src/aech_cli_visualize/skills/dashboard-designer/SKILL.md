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

### Phase 4: Render and QA Loop

**CRITICAL**: You MUST review every rendered dashboard before showing to user. Do not return images without visual QA.

#### Design Principles to Apply

**Visual Hierarchy**: Elements should have size proportional to their importance.

- KPIs and headline metrics should DOMINATE - they're the hero elements
- Charts should fill their allocated space generously
- No widget should appear "lost" in empty space or squeezed into a corner

**Spatial Balance**: Every pixel should feel intentional.

- EMPTY SPACE IS A PROBLEM if it's unintentional (huge gap at top, tiny chart in corner)
- Crowding is also a problem (overlapping text, cramped widgets)
- Good balance: widgets fill ~80-90% of their allocated regions

**Typography Hierarchy**:

- KPI values: LARGE and readable from distance (48-72pt effective size)
- KPI labels: Clear secondary text (18-24pt)
- Chart axis labels: Must be readable (12-16pt minimum)

```
┌─────────────────────────────────────────────────────────────────┐
│                    QUALITY ASSURANCE LOOP                       │
│                                                                 │
│   1. Render ──▶ 2. Review Image ──▶ 3. Check for Issues         │
│                                            │                    │
│                              ┌─────────────┴─────────────┐      │
│                         acceptable?                 issues?     │
│                              │                          │       │
│                       Return to User           Call iterate     │
│                                                     │           │
│                                                     └───────────┘
│                                                    (max 3 times) │
└─────────────────────────────────────────────────────────────────┘
```

**Step 1: Initial Render**
```bash
aech-cli-visualize dashboard spec.json --output-dir ./output --theme corporate
```

**Step 2: Visual Review (REQUIRED)**

You must examine the rendered image and check for:
- [ ] **Visual balance**: No huge empty areas, no cramped widgets
- [ ] **Text readable** at presentation distance (not too small)
- [ ] **No widget overlap** or cramping
- [ ] **Delta indicators visible** on KPIs (e.g., +8.2%)
- [ ] **Chart axis labels readable** (12pt minimum effective)
- [ ] **Adequate spacing** between widgets (not too tight, not too loose)
- [ ] **Widgets fill their space** (not tiny in a large region)
- [ ] **Titles and labels not truncated**

**Step 3: Iterate if Issues Found**

If issues detected, use the iterate command with plain language feedback describing the visual problem:
```bash
aech-cli-visualize iterate spec.json \
  --feedback "KPIs overlapping, fonts too small, need more spacing between charts" \
  --previous-image ./output/dashboard.png \
  --output-dir ./output
```

The iterate command's internal agent handles all parameter calculations automatically.

**Feedback Examples** (plain language):

| Issue | Feedback |
|-------|----------|
| Text too small | "fonts too small to read" |
| Widgets cramped | "widgets overlapping" |
| KPIs overlapping | "KPIs too close together" |
| Gauge too small | "gauge is tiny" |
| Too much space at top | "too much space between title and content" |
| Top row too low | "move top row closer to title" |
| Charts too close | "need more spacing between charts" |
| Poor visual balance | "poor visual balance - huge empty area on the right" |

**IMPORTANT**: Describe VISUAL problems in plain language. The iterate command's internal agent handles all parameter calculations.

**Step 4: Max Iterations**

- Maximum 3 QA iterations
- If still not acceptable after 3, return best result with explanation
- Always tell user what was adjusted

**Example QA conversation with yourself:**

```
Iteration 1: Rendered dashboard.png
Review: KPI numbers overlapping, fonts tiny, no deltas visible
Action: iterate --feedback "KPIs overlapping, fonts too small, deltas missing"

Iteration 2: Rendered dashboard.png
Review: KPIs now separated, deltas showing, but charts still cramped
Action: iterate --feedback "triple the spacing between charts"

Iteration 3: Rendered dashboard.png
Review: All elements readable, proper spacing, deltas visible
Result: APPROVED - return to user
```

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
