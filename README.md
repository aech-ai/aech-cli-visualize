# aech-cli-visualize

Generate arbitrary visual artifacts for Agent Aech with GPT Image.

`visualize` is not limited to charts, dashboards, or numeric datasets. It is the agent's general visual composition capability: anything the agent can understand and express as JSON, JSONL, or a wrapped payload can become an explanatory image.

## Purpose

Agent Aech uses this CLI to turn structured records, prose, status, workflows, concepts, and analysis into presentation-ready raster images. Good outputs include dashboards, diagrams, timelines, process maps, account summaries, annotated comparisons, risk maps, incident explanations, and decision briefs.

**Key principle:** data and source material flow through `aech-cli-*` capabilities or the agent's own reasoning. This CLI is the visualization layer, not a data source.

## Installation

```bash
uv venv && source .venv/bin/activate
uv pip install -e .
```

## Configuration

The generative path uses OpenAI:

```bash
export OPENAI_API_KEY=...
```

## Command

Use `image` for all visualization generation:

```bash
aech-cli-visualize image [data_file] --output-dir ./out [options]
```

Supported input:
- JSON object files or stdin
- `.jsonl` files, wrapped as `{"rows": [...]}`
- Wrapped payloads with `data`, `instructions`, `title`, and optional precomputed `analysis`
- Narrative or arbitrary source material wrapped in JSON, usually under `data.source_text`

There are no deterministic renderer commands or compatibility stubs. The installed CLI exposes only `image` plus the `--version` option.

## Examples

### Visualize Records

```bash
aech-cli-visualize image work/crm/data/opportunities.jsonl \
  --output-dir ./out \
  --title "Pipeline Action Map" \
  --instructions "Create a board-style visual that groups opportunities by stage, calls out blocked deals, and highlights next actions. Numeric charts are optional." \
  --analysis-mode auto \
  --generate
```

### Visualize Prose

```bash
cat > renewal-brief.json <<'JSON'
{
  "title": "Renewal Risk Brief",
  "instructions": "Create a slide visual showing the renewal situation as a timeline plus three risk callouts and owner actions. This is a narrative visual, not a chart.",
  "data": {
    "source_text": "The customer is enthusiastic about expansion but blocked on security review. Procurement needs final pricing by Friday. The champion asked for a CISO-facing summary."
  }
}
JSON

aech-cli-visualize image renewal-brief.json \
  --output-dir ./out \
  --analysis-mode auto \
  --generate
```

### Use Precomputed Analysis

```bash
aech-cli-visualize image examples/generative/agent-spend-anomaly.json \
  --output-dir ./out \
  --analysis-mode precomputed \
  --quality high \
  --size 2048x1152 \
  --generate
```

### Dry Run

```bash
aech-cli-visualize image payload.json \
  --output-dir ./out \
  --analysis-mode auto \
  --dry-run
```

`--dry-run` writes the prompt and analysis artifacts without calling GPT Image.

## Useful Options

| Option | Purpose |
| --- | --- |
| `--instructions` | Add or override the visual brief. Use this to specify a non-chart form such as timeline, diagram, map, or comparison. |
| `--title` | Set the output title. |
| `--surface slide` | Generate a presentation-friendly landscape image. |
| `--surface embedded-card` | Generate a quieter image for an app surface. |
| `--template-image` | Use an existing screenshot or visual as a composition/style reference. |
| `--analysis-mode auto` | Default mode. Uses direct LLM analysis when compact enough and generated-code analysis for larger payloads. |
| `--analysis-mode code` | Force generated-code analysis for larger structured datasets. |
| `--analysis-mode precomputed` | Use an `analysis` object already supplied in the payload. |
| `--max-data-chars` | Serialized data size allowed in direct model prompts. Default: `20000`. |
| `--factual-validate / --no-factual-validate` | Validate generated image facts against the analysis/evidence. Default: enabled for generated images. |
| `--factual-validation-model` | Vision-capable model for post-generation factual QA. Default: `gpt-5.4`. |
| `--factual-validation-max-attempts` | Maximum generate/validate attempts before delivering with review warnings. Default: `2`. |

## Outputs

The command writes a structured JSON result to stdout and files under `--output-dir`:

```json
{
  "success": true,
  "output_files": [
    {"path": "./out/generative_visual.png", "format": "png", "size_bytes": 123456},
    {"path": "./out/generative_visual.prompt.txt", "format": "txt", "size_bytes": 3200},
    {"path": "./out/generative_visual.analysis.json", "format": "json", "size_bytes": 1800},
    {"path": "./out/generative_visual.factual_validation.json", "format": "json", "size_bytes": 900},
    {"path": "./out/generative_visual.factual_review.md", "format": "md", "size_bytes": 600}
  ],
  "backend": "gpt-image",
  "image_model": "gpt-image-2",
  "analysis_mode": "auto",
  "factual_validation": true,
  "factual_validation_status": "warning",
  "factual_validation_disclaimer": "Disclaimer: this generated visual was delivered with fact-checker review findings..."
}
```

For `--analysis-mode code`, the CLI may also write `*.analysis_code.py`, `*.analysis_sample.json`, and `*.analysis_full.json`.

Generated images are fact-checked by default. The validator looks at the image and flags visible numbers, labels, charts, callouts, or conclusions that are false, contradictory, or not grounded in the condensed evidence JSON. Extra visible data is allowed when it is present in or mechanically derivable from the evidence; layout guidance is not treated as an exclusion list. Rejected images are regenerated with explicit correction instructions; if validation still fails, the command still returns the generated image but marks `factual_validation_status` as `warning`, includes `factual_validation_disclaimer` and `factual_validation_issues` in stdout, and writes a `*.factual_review.md` companion note.

## Development

```bash
.venv/bin/python -m pytest
```

Package data includes the CLI manifest and bundled agent skill under `src/aech_cli_visualize`.
