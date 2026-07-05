# Existing project onboarding and backfill Workpackage

Status: active
Type: workpackage
Updated: 2026-07-05
Next Action: decide whether Level 2 onboarding needs helper automation

Project Map: work/maps/map-tool-shed-foundation.md

## Current Context

`tool_shed` can be installed into a workspace and create structured artifacts under `work/`.

Current support:

- `scripts/install_into_workspace.py` creates the standard `work/` tree.
- `scripts/new_artifact.py` creates individual artifacts from templates.
- `selection.md` helps choose the right artifact.
- `conventions.md` defines artifact boundaries and composition.
- `templates/project-map.md` supports visual project navigation.

Missing support:

- A repeatable way to load `tool_shed` onto an existing project.
- A discovery workflow for learning the project before creating artifacts.
- A backfill strategy that creates useful maps/workpackages/tickets/docs references without inventing history or flooding the workspace with noise.

## Recommendation

Build this as a staged onboarding/backfill workflow:

1. Discover: inspect project layout, docs, code surfaces, tests, and existing planning material.
2. Orient: create or update a project map when the project meets the map trigger rule.
3. Inventory: capture existing docs, code areas, active work hints, and uncertainty.
4. Backfill: create only the artifacts that help future work continue.
5. Canonize: move settled current truth into `docs/` or README files, not into work artifacts.

Avoid trying to fully reconstruct past project management. Backfill should describe observed current state, active risks, known decisions, and next useful work.

## Current State

Completed:

- Project maps exist as a first-class artifact type.
- Artifact composition links exist in templates.
- A decision matrix exists for when to create a project map.
- Level 2 is the default existing-project backfill level.
- Existing-project inventory template exists.
- Level 2 onboarding runbook exists.
- Level 2 onboarding was tested against a temporary clone of `/home/jon/docker/getshows`.

Incomplete:

- Add helper script or runbook support if the manual workflow becomes repetitive.
- Decide which discovered facts become `work/` artifacts versus settled `docs/` updates.

## Goal

An existing project can adopt `tool_shed`, be learned by Codex, and receive a right-sized set of backfilled artifacts that make the project visible and navigable without creating misleading or excessive process artifacts.

## Why It Matters

Large existing projects often already contain implicit structure: code areas, docs, conventions, abandoned plans, active problems, partial decisions, and hidden dependencies. A visual thinker can get lost if `tool_shed` only starts from new work. The shed should help reveal the project shape that already exists.

## Major Outcomes

- Existing-project onboarding runbook or checklist.
- Backfill level definitions.
- Project map trigger rule integrated into selection guidance.
- Example of a backfilled project map and supporting artifacts.
- Optional script support for initializing discovery artifacts.

## Backfill Levels

Use the lowest level that makes the existing project navigable.

Level 0: install only

- Create the `work/` tree.
- Do not create project artifacts.
- Use when the project is small, paused, or the human only wants the structure available.

Level 1: orientation map

- Create one project map.
- Capture major areas, dependencies, active questions, and next ground action.
- Use when the project has moving parts but backfilling detailed work would be premature.

Level 2: map plus inventory

- Create one project map.
- Create one inventory for docs/code/work surfaces that need classification.
- Use when Codex needs to learn an existing project before making changes.

Level 3: active work backfill

- Create a project map.
- Create workpackages, tickets, checklists, spikes, ADRs, or runbooks only for observed current work.
- Use when the project has multiple active efforts or known decisions/procedures that need durable coordination.

Level 4: deep reconstruction

- Reconstruct historical decisions, completed work, and prior incidents only from explicit project evidence.
- Use rarely, when history affects current operation or migration risk.

Default to Level 2 for existing projects: create a project map, then create an inventory of existing docs/code/work surfaces before deciding whether to backfill detailed work artifacts. Do not invent history. Mark inferred items as inferred, and prefer inventories/spikes when the project state is uncertain.

## Related Artifacts

- Tickets: `work/tickets/ticket-add-codex-skill-after-foundation-stabilizes.md`
- Checklists:
- Spikes:
- ADRs:
- Runbooks:
- Inventories:
- Decision matrices: `work/decisions/decision-project-map-creation-trigger.md`

## Rough Sequence

1. Define backfill levels so Codex can choose how much structure to create.
2. Add an onboarding checklist or runbook for existing projects.
3. Update `selection.md` with map trigger guidance.
4. Add examples showing light, medium, and deep backfill.
5. Consider script support only after the manual workflow is clear.

## Milestones

### Milestone 1: Backfill Model

Completion criteria:

- [x] Backfill levels are documented.
- [x] The default level is safe for existing projects.
- [x] The model distinguishes observed facts from inferred plans.

### Milestone 2: Onboarding Workflow

Completion criteria:

- [x] A checklist or runbook exists for loading `tool_shed` onto an existing project.
- [x] The workflow starts with discovery before artifact creation.
- [x] The workflow includes verification and stale-artifact avoidance.

### Milestone 3: Foundation Integration

Completion criteria:

- [x] `selection.md` includes map trigger guidance.
- [x] `conventions.md` explains safe backfill boundaries.
- [x] Examples demonstrate a backfilled project map and supporting artifacts.

## Test Notes

2026-07-05: Tested Level 2 onboarding against a temporary clone of `/home/jon/docker/getshows`.

Result:

- `install_into_workspace.py` created the standard `work/` tree.
- `new_artifact.py project-map "getshows"` created `work/maps/map-getshows.md`.
- `new_artifact.py existing-project-inventory "getshows surfaces"` created `work/inventories/inventory-getshows-surfaces.md`.
- Discovery identified a Docker/Traefik/Nginx configuration repo with README, Compose, Traefik, portal, env, host-shim, and NPM/AdGuard planning surfaces.
- The map and inventory were enough to identify the next ground action without creating premature workpackages or tickets.
- `docker compose config` passed in the clone, with expected warnings for missing environment variables because no `.env` was copied.

## Open Questions

- Should the default onboarding artifact be a checklist, runbook, or both?
- Should `install_into_workspace.py` optionally create an initial project map?
- Should there be a script that scans and drafts an inventory, or should discovery remain Codex-guided at first?
- What is the smallest useful backfill level for a large project that already has docs and code but no `work/` tree?

## Completion Standard

This workpackage is complete when a fresh existing project can install `tool_shed`, run a documented discovery/backfill workflow, and end with a navigable project map plus only the supporting artifacts that match observed project needs.
