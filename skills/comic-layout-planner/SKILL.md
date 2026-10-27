---
name: comic-layout-planner
description: Choose and specify flexible comic/storyboard layouts (4-panel, 8-panel, 9-panel, separate thumbnail, or thumbnail plus 8 panels) by balancing generation cost, crop reliability, aspect ratio, and prompt simplicity. Use when planning comic image generation, storyboard panels, thumbnails, or image-to-video assets.
---

# Comic Layout Planner

## Purpose

Help the user choose a layout for the current job rather than forcing every comic into one fixed format. Produce a short recommendation, a trade-off summary, and a reusable image-generation prompt. Treat layout choice as a configurable decision.

## Supported layout patterns

- **4-panel comic**: compact story, low generation and review burden; less room for detailed progression.
- **8-panel comic**: richer sequence while keeping a manageable panel count; good default candidate when narration has around eight beats.
- **9-panel sheet**: a regular 3×3 source grid; convenient for contact sheets and bulk cropping, but the story may use only eight panels and leave one unused.
- **Thumbnail only**: generate a dedicated cover/thumbnail with its own composition and aspect ratio.
- **Thumbnail + 8 panels (separate assets)**: one dedicated thumbnail plus an 8-panel comic sheet or eight independent panels. Prefer when thumbnail composition must be strong and must not be constrained by story-panel geometry.
- **Thumbnail + 8 panels (single 3×3 sheet)**: reserve one cell for the thumbnail and eight for story panels only if the generator can keep the cell roles and boundaries reliably distinct. Validate the crop result before using it.

Do not treat “9-panel sheet with one unused panel” and “thumbnail + 8 panels” as equivalent. State which cell is used for what.

## Decision factors

For each request, evaluate these factors without assuming that one layout always wins:

1. **Story beats**: number of distinct moments that must be communicated (4, 8, 9, or another count).
2. **Thumbnail role**: none, separate asset, or one cell in a sheet.
3. **Aspect ratio**: target platform and placement. Examples to consider, not mandatory defaults: vertical 9:16, portrait 4:5, square 1:1, landscape 16:9.
4. **Generation cost**: number of image-generation calls, image dimensions/pixel area, likely retries, and whether a failed panel forces regeneration of a whole sheet. Do not invent currency costs; use relative estimates unless actual provider pricing and settings are supplied.
5. **Crop reliability**: visible gutters, consistent grid, no panel bleed, no text crossing boundaries, sufficient safe margins, and whether each crop remains readable.
6. **Prompt simplicity**: how easily the prompt can describe panel order, characters, continuity, composition, and per-panel content without contradictory constraints.
7. **Revision granularity**: whether one bad panel can be regenerated independently or requires rerendering the whole sheet.
8. **Downstream use**: video sequence, social thumbnail, HTML viewer, SVG overlay, or manual editing.
9. **Quality risk**: lettering, character consistency, hands/faces, small details, and model tendency to ignore strict grid instructions.

## Flexible selection rules

- Ask at most one clarifying question if a missing requirement changes the recommendation; otherwise state reasonable assumptions and proceed.
- Compare at least the most relevant alternatives, usually 4-panel, 8-panel, 9-panel sheet, and separate thumbnail + 8 panels.
- Recommend the simplest format that meets the story and output requirements, not automatically the largest or cheapest.
- Prefer independent assets when crop accuracy or panel-level revision matters more than minimizing generation calls.
- Consider a 3×3 sheet when uniform grid extraction is valuable, but do not assume that generated borders align perfectly.
- Consider a dedicated thumbnail when the thumbnail needs a different focal point, text-safe area, or aspect ratio from story panels.
- For vertical publishing, choose the final canvas ratio based on the target placement. A vertical video canvas does not require every source panel to be vertical; define panel ratio and final composition separately.
- If costs cannot be calculated from supplied provider/model settings, report a relative cost tier and list the assumptions.
- Keep creative prompt text separate from technical output instructions and validation requirements.

## Suggested comparison format

| Option | Best for | Generation/retry cost | Cropping | Prompt complexity | Thumbnail fit |
|---|---|---|---|---|---|
| 4 panels | Short/simple story | Relative estimate | Low to medium | Low | Separate or absent |
| 8 panels | Narrative with 8 beats | Relative estimate | Medium | Medium | Separate recommended |
| 3×3 / 9 panels | Contact sheet and regular crops | Relative estimate | Medium to high risk until validated | Medium to high | One cell only if explicitly assigned |
| Thumbnail + 8 panels, separate | Strong thumbnail and reliable revisions | More calls/assets; potentially less rework | Low if assets are independent | Medium | High |

This table is a starting point, not a universal ranking. Adapt it to the generator, target platform, and actual results.

## Prompt-building template

Fill in only known requirements; leave optional choices configurable.

**Creative brief**
- Purpose / audience: `{purpose}`
- Story beats: `{4 | 8 | 9 | custom}`
- Main character(s) and continuity rules: `{characters}`
- Visual style: `{style}`
- Per-panel content: `{ordered beats}`

**Layout contract**
- Pattern: `{4-panel | 8-panel | 3×3 | thumbnail + 8 separate | custom}`
- Reading order: `{explicit order}`
- Thumbnail role: `{none | separate | named cell}`
- Target platform and final aspect ratio: `{platform, ratio}`
- Source canvas and panel ratio: `{ratio or flexible}`
- Panel gutters/borders: `{requirements}`
- Keep all essential content inside each panel; no artwork, speech balloons, captions, or borders crossing panel boundaries.
- Maintain character identity, costume, palette, and spatial continuity across panels.
- Do not add extra panels or duplicate a beat. If a 9-cell grid uses only eight story beats, explicitly mark the unused cell as blank or assign it to the thumbnail.

**Output contract**
- Required outputs: `{sheet, separate panels, thumbnail, metadata}`
- File naming / panel IDs: `{scheme}`
- Crop validation: `{dimensions, boundaries, bleed, missing panels}`
- Text policy: `{no text | exact text | text added downstream}`

## Crop validation checklist

Before approving a sheet for downstream video or editing:

- Confirm expected panel count and reading order.
- Confirm all panel files exist and have non-zero dimensions.
- Inspect the original sheet and every crop together.
- Check for missing edges, adjacent-panel bleed, clipped faces/hands/text, uneven gutters, and inconsistent crop dimensions.
- Mark each panel `pass`, `review`, or `fail`, with a reason.
- Keep crop accuracy validation separate from semantic matching of panels to narration.
- Do not claim that a successful build means the crops are visually correct; that requires a separate inspection or vision-model check.

## Decision record (ADR) guidance

When a layout choice affects the reusable pipeline, record an ADR with:
- Context and intended use.
- Considered options.
- Decision and reasons.
- Cost assumptions and uncertainty.
- Aspect-ratio and crop-validation strategy.
- Consequences, rejected alternatives, and conditions that would trigger reconsideration.

A one-off creative choice does not require a formal ADR. Record an ADR when the choice changes defaults, asset schemas, build steps, or downstream contracts.

## Response contract

Return:
1. Recommended layout and why.
2. Short comparison of alternatives and trade-offs.
3. A ready-to-use prompt with configurable fields.
4. Output/crop validation requirements.
5. Whether an ADR is warranted and which decision remains open.

Never hard-code one layout as the only valid answer. The user may choose a different layout after seeing the trade-offs.
