---
name: visualize
description: Visualize what the agent wants to communicate with aech-cli-visualize. Use when data, records, text, status, workflows, ideas, or plans would be clearer as an image. Not limited to charts, dashboards, or numeric data.
allowed-tools: Read, Bash, Write, Grep, Glob
---

# Visualize

Use `aech-cli-visualize image` to turn agent-understood material into a polished image. The input does not need to be numeric. Anything the agent can clearly express as JSON, JSONL, or a wrapped payload with instructions can be visualized.

Good uses include:
- Executive dashboards and metric summaries
- Arbitrary image generation for ideas the agent needs to communicate visually
- Concept diagrams, process maps, system flows, and timelines
- CRM/account summaries, deal boards, risk maps, and action plans
- Annotated comparisons, status narratives, incident explanations, and decision briefs
- Visual summaries of prose, notes, transcripts, records, or mixed source material

## Input Pattern

Prefer a wrapped JSON payload so the image model has explicit intent:

```json
{
  "title": "Customer Renewal Map",
  "instructions": "Create a slide visual that groups accounts by renewal risk, shows blockers as callouts, and highlights next actions. This is not a numeric dashboard.",
  "data": {
    "source_text": "Optional prose, notes, or conversation summary.",
    "records": [
      {"account": "Acme", "status": "blocked", "blocker": "security review", "next_action": "schedule CISO call"}
    ]
  }
}
```

For JSONL inputs, pass the `.jsonl` file directly. The CLI wraps records under `rows`.

## Command

```bash
aech-cli-visualize image payload.json \
  --output-dir ./out \
  --analysis-mode auto \
  --surface slide \
  --generate
```

Useful options:
- `--instructions`: add or override the visual brief.
- `--title`: set the image title.
- `--surface embedded-card`: generate a quieter in-app visual instead of a slide.
- `--template-image`: use an existing screenshot or visual as a layout/style reference.
- `--analysis-mode precomputed`: use when you already supplied a trusted `analysis` object.
- `--analysis-mode code`: force generated-code analysis for larger structured payloads.
- `--factual-validate`: enabled by default; regenerates images with unsupported visible facts, then delivers with review warnings if findings remain.

## Working Rules

- Do not assume visualize means charting. Numeric fields are optional.
- For prose or arbitrary material, wrap it in JSON under `data.source_text`, `data.records`, or domain-specific keys and provide concrete `instructions`.
- Keep only evidence the image should actually show. Use concise strings, short IDs, and high-signal fields.
- Treat factual validation warnings as user-visible caveats. Show the generated image only with the disclaimer and review findings from the CLI output/artifacts.
- Always inspect the generated image before showing it to the user.
- Use `--dry-run` when you need to audit the prompt and analysis without spending an image call.
- The CLI exposes only `image`; there are no deterministic renderer commands or compatibility stubs.

## Output

The command writes:
- `<output-dir>/generative_visual.<format>`
- `<output-dir>/generative_visual.prompt.txt`
- `<output-dir>/generative_visual.analysis.json`
- `<output-dir>/generative_visual.factual_validation.json` when generation runs with factual validation
- `<output-dir>/generative_visual.factual_review.md` when validation findings remain after retry attempts

For `--analysis-mode code`, it may also write generated-code audit artifacts beside the image.
