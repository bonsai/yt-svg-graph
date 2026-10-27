# ADR-0001: Flexible comic layout and repository boundaries

- Status: Proposed
- Date: 2026-10-27

## Context

The repository supports short-form video production from storyboard PNG and HTML/SVG sources. The current project lives at `01-mixue/`; its pipeline code, configuration, inputs, web assets, docs, legacy route, and generated build outputs are grouped under that project. This project-specific layout is workable, but the repository-level boundaries and naming need to scale to future projects and reusable comic-layout guidance.

The recent build-path flattening also means documentation and workflows must be kept in sync with the current `build/` output contract.

## Decision

1. Keep project-specific runtime code, config, input assets, web sources, docs, and generated outputs within each project boundary.
2. Keep generated artifacts out of Git and publish them through GitHub Actions artifacts/releases.
3. Put reusable workflow guidance under `.github/skills/` and architecture decisions under `docs/adr/`.
4. Select comic layout per task rather than hard-coding 3×3: support 4-panel, 8-panel, 9-cell, thumbnail + 8-panel, and separate-panel strategies.
5. Prefer a path-only migration first. Do not change TTS, panel order, crop algorithms, QA verdict semantics, or rendered output while moving files.
6. Before moving the project directory itself, inventory every path reference in scripts, workflow files, docs, ignore rules, and artifact/release definitions. Move the project as one coordinated change and validate every path.

## Layout selection criteria

Compare generation cost, portrait aspect-ratio fit, panel cropability, prompt simplicity, visual consistency, revision granularity, and whether the thumbnail is independent from the narrative panels. Crop reliability and destination constraints take priority over a symmetric grid.

## Consequences

- Layout choice becomes a reusable decision rather than a project-specific assumption.
- Directory moves must update all path consumers in the same change.
- A 3×3 sheet is not automatically interpreted as eight panels plus one unused cell.
- Existing paths remain canonical until the migration commit updates all consumers; do not partially rename folders.

## Validation

- Search for stale path references before and after the move.
- Verify workflow dependency cache, working directories, QA input paths, artifact globs, diagram output, and release file paths.
- Run the documented pipeline smoke test and compare output/QA summaries.
