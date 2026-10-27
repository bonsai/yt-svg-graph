# ADR-0001: Flexible comic layout selection

- **Status:** Proposed
- **Date:** 2026-10-27
- **Scope:** `bonsai/yt-svg-graph` comic/storyboard image-generation planning

## Context

The pipeline may need 4-panel comics, 8-panel comics, 9-cell sheets, dedicated thumbnails, or a thumbnail plus 8 story panels. These formats have different generation costs, crop risks, aspect-ratio needs, prompt complexity, and revision costs. A single fixed layout would make the workflow unnecessarily rigid.

## Options considered

1. **Always generate a 3×3 / 9-cell sheet.** Convenient for uniform crops, but the ninth cell may be unused and a thumbnail is not automatically equivalent to a story panel.
2. **Always generate 8 panels.** Aligns with eight story beats but does not solve dedicated thumbnail composition or short 4-beat stories.
3. **Generate a separate thumbnail plus 8 story panels.** Gives thumbnail composition and panel revisions more freedom, but can require extra generation calls or assets.
4. **Choose layout per task using a reusable skill.** Supports all formats and compares costs and quality risks before committing.

## Decision

**Propose option 4:** use the `comic-layout-planner` skill to choose a layout from story beats, thumbnail requirements, target aspect ratio, crop reliability, generation/retry cost, prompt complexity, and downstream use.

The skill must distinguish:
- a 9-cell sheet with one unused cell;
- a 3×3 sheet with a thumbnail assigned to one cell; and
- a separate thumbnail asset plus 8 story panels.

No single layout is the mandatory default. A recommendation must state its assumptions and allow the user to override it.

## Consequences

### Positive
- 4-panel and 8-panel stories remain first-class options.
- Thumbnail composition can use a different aspect ratio from story panels.
- Cost estimates include retries and whole-sheet regeneration risk, not only initial generation calls.
- Crop accuracy is explicitly validated before the assets enter video production.

### Trade-offs
- The planning step has more decision factors than a fixed template.
- Exact monetary cost cannot be asserted unless model/provider pricing, dimensions, and generation settings are known.
- Grid borders and gutters can be inconsistent in generated images, so a 3×3 sheet requires crop validation.

## Validation requirements

- Record intended panel count, reading order, aspect ratio, thumbnail role, and output contract.
- Check panel count, file existence, crop dimensions, clipped content, and adjacent-panel bleed.
- Use `pass`, `review`, and `fail` with reasons for panel validation.
- Keep visual crop validation separate from semantic matching of panels to narration.
- A successful GitHub Actions run means the workflow completed; it does not by itself prove crop accuracy.

## Revisit this decision when

- Actual generation measurements show a consistently better cost/quality trade-off.
- The selected image model gains reliable structured multi-panel output.
- The pipeline adds a formal panel schema or changes its asset-generation contract.
- User testing shows that one format should become a default for a specific class of jobs.
