# tool_shed

[![Validate](https://github.com/PC-Redemption/tool_shed/actions/workflows/validate.yml/badge.svg)](https://github.com/PC-Redemption/tool_shed/actions/workflows/validate.yml)

`tool_shed` is a reusable collaboration toolkit for structured work with Codex.

It is not the project. It is the workbench copied into or referenced from a project workspace so human and assistant can choose the right artifact, use the same shapes consistently, and keep project code/documentation uncluttered.

Core boundary:

```text
tool_shed/ = tools, templates, rules
work/      = project-specific work artifacts
docs/      = settled project documentation
code/      = product implementation
```

Short version:

**tool_shed creates. work contains. docs canonize. code implements.**

## What This Is For

Use `tool_shed` when a project benefits from consistent structure for:

- checklists
- tickets
- project maps
- workpackages
- ADRs
- runbooks
- incidents
- spikes
- inventories
- decision matrices

Lessons should remember how to route to `tool_shed`, but `tool_shed` keeps the larger templates and conventions inspectable as local files.

## What This Is Not

`tool_shed` is not:

- a server
- a database
- a task tracker
- a place for active project state
- a place for app code
- a replacement for project docs

No server should be required. Start with plain files, Python scripts, and Git.

## Recommended Project Layout

When installed into a project workspace:

```text
project/
  tool_shed/
  work/
    README.md
    index.md
    index.json
    maps/
    wp/
      active/
      completed/
    tickets/
    adr/
    incidents/
    runbooks/
    spikes/
    checklists/
    inventories/
    decisions/
  docs/
  ...
```

Project-specific artifacts should go under `work/`, not inside `tool_shed/`.

## Quick Start

Create the project work tree:

```bash
python3 tool_shed/scripts/install_into_workspace.py .
```

Create a new artifact:

```bash
python3 tool_shed/scripts/new_artifact.py checklist "Root docs cleanup" --workspace .
python3 tool_shed/scripts/new_artifact.py project-map "Plugin migration" --workspace .
python3 tool_shed/scripts/new_artifact.py wp "Plugin migration" --workspace .
python3 tool_shed/scripts/new_artifact.py adr "Hosted installer uses plugin bootstrapper" --workspace .
```

Complete an active workpackage:

```bash
python3 tool_shed/scripts/complete_workpackage.py work/wp/active/wp-plugin-migration.md --workspace .
```

Refresh the work index:

```bash
python3 tool_shed/scripts/update_work_index.py --workspace .
```

Read `work/index.md` after README/docs to find active artifacts quickly. Use `work/index.json` when automation needs the same navigation data. Both files are generated from artifact headers; current truth still belongs in docs or README files.

Check for stale work artifact links after moving or completing artifacts:

```bash
python3 tool_shed/scripts/check_stale_paths.py --workspace .
```

Run the full repository validation:

```bash
python3 scripts/validate_tool_shed.py
```

GitHub Actions runs the same validation on push and pull requests.

Before choosing an artifact, read:

- [selection.md](./selection.md)
- [conventions.md](./conventions.md)
- [existing-projects.md](./existing-projects.md) when loading `tool_shed` into an existing project

## Codex Start Prompts

Use short prompts and let Codex operate the scripts:

```text
use tool_shed and orient me
```

```text
use tool_shed and create the smallest artifact for this
```

```text
use tool_shed and complete work/wp/active/wp-example.md
```

Codex should read README/docs first, then `work/index.md`, then active artifacts. It should use `work/index.json` only when automation needs machine-readable navigation.

## Existing Projects

For an existing project, install the work tree first, then learn before backfilling:

```bash
python3 tool_shed/scripts/install_into_workspace.py .
```

Recommended flow:

1. Inspect the project layout, docs, code surfaces, tests, and existing planning material.
2. Default to Level 2 backfill: create a project map, then create an inventory of existing docs/code/work surfaces.
3. Use the map and inventory before deciding whether to backfill workpackages, tickets, ADRs, runbooks, or checklists.
4. Backfill only useful current-state artifacts.
5. Keep observed current truth in `docs/` or README files; keep work coordination in `work/`.
6. Regenerate `work/index.md` and `work/index.json` after artifacts are created, moved, completed, or superseded.
7. Use `complete_workpackage.py` for active workpackage closeout, then fix stale links if the command reports warnings.

Level 2 artifact commands:

```bash
python3 tool_shed/scripts/onboard_existing_project.py "Project name" --workspace .
```

Manual equivalent:

```bash
python3 tool_shed/scripts/new_artifact.py project-map "Project name" --workspace .
python3 tool_shed/scripts/new_artifact.py existing-project-inventory "Project name surfaces" --workspace .
```

## Repository Governance

Canonical repository: `PC-Redemption/tool_shed`.

The repository should be public for visibility, but direct changes should be limited to owners/admins of the `PC-Redemption` organization. Public readers may fork or propose changes through normal GitHub flows, but maintainers should avoid granting broad write access.

## Codex Skill

`tool_shed` includes a thin Codex skill package at `skills/tool-shed`.

The skill is also installed locally at `${CODEX_HOME:-~/.codex}/skills/tool-shed` for auto-discovery in this environment. It is an adoption/routing layer only: it teaches Codex to find and use workspace-local `tool_shed` files and scripts instead of duplicating templates.

Initial skill packaging is local plus repo-packaged. Plugin packaging is intentionally deferred until real use shows it is needed.

## Lessons Integration

Recommended durable lesson:

> If a workspace has `tool_shed/`, read `tool_shed/selection.md` before choosing a planning or documentation artifact. Do not default to workpackages. Use the smallest artifact that fits the task. Project-specific artifacts live under `work/`; `tool_shed/` contains only templates, rules, and helper scripts.
