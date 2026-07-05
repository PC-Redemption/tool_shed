# Conventions

## Boundaries

`tool_shed/` contains:

- selection rules
- conventions
- templates
- helper scripts
- examples

`work/` contains project-specific generated artifacts:

- project maps
- active and completed workpackages
- tickets
- ADRs
- incidents
- runbooks
- spikes
- checklists
- inventories
- decision records

`docs/` contains settled project truth:

- operator docs
- reference docs
- project/product docs
- current-state docs

## Artifact Headers

Every project artifact should start with a compact status block:

```text
Status: active
Type: workpackage
Updated: 2026-07-05
Next Action: ...
Canonical Truth: docs/...
```

This saves context and lets Codex decide whether to read deeper.

## Naming

Use lowercase kebab-case filenames.

Examples:

- `map-plugin-migration.md`
- `wp-plugin-migration.md`
- `adr-hosted-installer-plugin-bootstrapper.md`
- `incident-duplicate-mcp-table.md`
- `inventory-root-files.md`

## Artifact Composition

Artifacts should work in concert without duplicating each other.

- Use project maps as visual navigation for large projects.
- Use workpackages as delivery containers for larger transformations.
- Use tickets, checklists, spikes, ADRs, runbooks, inventories, and decision matrices as supporting tools when they fit the local problem.
- Link related artifacts with plain Markdown paths.
- Keep the coordinating artifact focused on orientation, dependencies, and next action.
- Keep detailed execution or decision content in the artifact type built for it.

## Existing Project Backfill

When loading `tool_shed` onto an existing project, learn before backfilling.

- Default to Level 2: create a project map, then create an inventory.
- Prefer the lowest useful backfill level.
- Capture observed current state before inferred plans.
- Do not invent historical decisions, completed work, or incidents.
- Mark uncertain or inferred items clearly.
- Use inventories for classification and spikes for unknowns.
- Promote settled current truth into `docs/` or README files.
- Keep coordination and future work under `work/`.

## Discovery Routing

Route discovered project facts by whether they are settled truth or unresolved work.

| Discovery | Route |
| --- | --- |
| Current setup steps | `README.md` or `docs/setup.md` |
| Current architecture or system shape | `docs/architecture.md` |
| Current operational procedure | `docs/` first, or `work/runbooks/` if still being tested |
| Open question | `work/spikes/` |
| Specific bug or enhancement | `work/tickets/` |
| Multi-step change | `work/wp/active/` |
| Known bounded execution steps | `work/checklists/` |
| Durable decision with alternatives | `work/adr/` |
| Classification list | `work/inventories/` |
| Visual coordination across moving parts | `work/maps/` |

Level 2 onboarding produces a project map and inventory only. After review, promote stable observed facts into `docs/` or README files, and create `work/` artifacts only for unresolved work.

## Promotion Rule

Work artifacts are not canonical truth by default.

When an artifact settles a durable fact, copy or summarize that fact into `README.md` or `docs/`.

Completed artifacts are history. Docs are current truth.

## Lessons Rule

Lessons should store routing and memory, not bulky templates.

Good lesson:

> Use `tool_shed/selection.md` before choosing a work artifact.

Bad lesson:

> A full copy of every artifact template.
