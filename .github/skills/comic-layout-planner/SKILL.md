---
name: comic-layout-planner
description: Select a flexible storyboard/comic layout for image generation and downstream video production. Use when choosing 4-panel, 8-panel, 9-cell, thumbnail-plus-8-panel, portrait, or other panel arrangements.
---

# Comic Layout Planner

Choose a layout per task. Never assume a fixed panel count or that a 3×3 sheet must leave one cell unused.

## Inputs to collect
- Story purpose and number of narrative beats.
- Destination: short video, comic page, thumbnail, social post, or storyboard.
- Target aspect ratio and whether portrait/vertical output is required.
- Image-generation constraints: cost per generation, prompt complexity, consistency, and revision cost.
- Cropping constraints: visible gutters, predictable panel bounds, risk of bleed/cut-off, and whether panels can be generated separately.
- Whether the thumbnail is a separate deliverable or part of the same generated sheet.

If a critical input is unknown, state the assumption and offer the smallest useful alternative rather than blocking progress.

## Layout candidates

| Layout | Good default when | Trade-offs |
|---|---|---|
| 4 panels (2×2 or vertical 1×4) | A simple story, low generation cost, easy manual QA | Less room for setup and payoff |
| 8 panels | Eight distinct beats; a compact story or vertical sequence | Unequal panel geometry may complicate cropping |
| 9 panels (3×3) | A regular grid is valuable and all nine cells have a purpose | More generations/details; tiny panels on portrait canvases |
| Thumbnail + 8 panels | Thumbnail must be visually distinct from the eight narrative beats | A separate thumbnail costs another generation but avoids confusing it with a story panel |
| Separate panel images | Precise crop bounds, independent revisions, or high reliability matters most | More generation calls and assembly work |

These are options, not mandatory templates. Use 3×3 with eight used cells only when one cell is intentionally spare or repurposed; otherwise prefer a true eight-panel composition or separate assets.

## Decision method
1. Eliminate layouts that cannot meet the target aspect ratio or readable panel size.
2. Score remaining candidates from 1–5 for:
   - generation cost (lower cost scores higher),
   - portrait/vertical fit,
   - cropability and gutter clarity,
   - prompt simplicity,
   - consistency across panels,
   - ease of revising one panel,
   - thumbnail separation.
3. Weight crop reliability and target-format fit above aesthetic symmetry when the output will be automatically sliced.
4. Choose the simplest layout that satisfies the story and production constraints. Explain the main trade-off in one short paragraph.
5. Keep thumbnail generation separate from panel generation when the thumbnail has different text, framing, or visual emphasis.

## Output contract
Return:
- chosen layout and reason;
- canvas orientation/aspect ratio recommendation;
- panel count and reading order;
- thumbnail strategy;
- crop/gutter strategy;
- generation/revision cost notes;
- risks and a QA checklist;
- a machine-readable JSON summary when the pipeline consumes the decision.

## Machine-readable example
```json
{
  "layout": "8-panel",
  "grid": {"columns": 2, "rows": 4},
  "orientation": "portrait",
  "thumbnail": {"mode": "separate"},
  "reading_order": "left-to-right, top-to-bottom",
  "crop_strategy": "visible gutters and per-panel bounds",
  "qa": ["panel count", "reading order", "bleed", "cut-off", "aspect ratio"]
}
```
