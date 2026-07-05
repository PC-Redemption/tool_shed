---
name: tool-shed
description: Structured work artifacts and workspace coordination with a local tool_shed. Use when Codex needs to choose, create, or maintain planning/documentation artifacts such as checklists, tickets, project maps, workpackages, ADRs, runbooks, incidents, spikes, inventories, or decision matrices; when loading tool_shed into an existing project; when a user asks for visual project coordination, 30,000 ft to ground navigation, or Level 2 onboarding/backfill; or when a workspace contains tool_shed/ or the tool_shed repository files.
---

# Tool Shed

Use this skill as a thin adoption layer for a workspace-local `tool_shed`. Do not treat the skill as the source of templates or project state.

## Locate The Shed

Before choosing or creating work artifacts, locate the shed:

1. If `tool_shed/selection.md` exists, use `tool_shed/` as the shed directory.
2. Else if `selection.md`, `conventions.md`, `templates/`, and `scripts/` exist in the workspace root, treat the workspace root as the shed directory.
3. Else if no shed exists, explain that `tool_shed` must be installed or copied into the project before this skill can create shed artifacts.

Read these files from the shed before acting:

- `selection.md`
- `conventions.md`
- `existing-projects.md` when loading the shed into an existing project

Read `README.md` when installing, explaining, or verifying repository boundaries.

When orienting in a workspace that already has work artifacts, read `work/index.md` if it exists after reading README/docs. Use `work/index.json` for automation if needed. Treat both as generated navigation aids, not canonical truth.

## Core Rules

- Choose the smallest artifact that fits the immediate work.
- Keep project-specific artifacts under `work/`, not inside `tool_shed/`.
- Keep settled current truth in `docs/` or README files.
- Treat completed work artifacts as history, not canonical truth.
- Use `work/index.md` to find active artifacts quickly when it exists.
- Use `work/index.json` only as machine-readable navigation data.
- Link related artifacts with plain Markdown paths.
- Do not create a server, database, or tracker unless plain files and scripts have failed.
- Do not duplicate bulky templates or shed docs inside the skill.

## Artifact Selection

Use the shed's `selection.md` as the authority.

Fast defaults:

- Checklist: bounded known steps.
- Ticket: specific bug or enhancement with clear acceptance criteria.
- Project map: visual coordination across moving parts.
- Workpackage: multi-step transformation with sequencing or handoff cost.
- ADR: durable decision with alternatives and consequences.
- Runbook: repeatable operation where commands, order, and recovery matter.
- Incident: break/fix learning.
- Spike: uncertainty where the deliverable is learning.
- Inventory: classify, keep, move, delete, own, or route.
- Decision matrix: compare two to five plausible options.

Use a project map when the user needs to see the whole project, when work spans multiple workstreams/artifact types, when sequencing matters, or when loading `tool_shed` into an existing project.

## Create Artifacts

Prefer shed scripts when available.

Install the work tree:

```bash
python3 <shed>/scripts/install_into_workspace.py <workspace>
```

Create an artifact:

```bash
python3 <shed>/scripts/new_artifact.py <kind> "Title" --workspace <workspace>
```

Complete an active workpackage:

```bash
python3 <shed>/scripts/complete_workpackage.py work/wp/active/wp-example.md --workspace <workspace>
```

Refresh the work index:

```bash
python3 <shed>/scripts/update_work_index.py --workspace <workspace>
```

Check stale work paths:

```bash
python3 <shed>/scripts/check_stale_paths.py --workspace <workspace>
```

Run Level 2 existing-project onboarding:

```bash
python3 <shed>/scripts/onboard_existing_project.py "Project name" --workspace <workspace>
```

If scripts are missing, create files from the shed templates and preserve the naming/location conventions in `conventions.md`.

## Existing Projects

Default to Level 2 onboarding:

1. Create a project map.
2. Create an existing-project inventory.
3. Discover by reading front-door files, docs, code surfaces, tests, build/runtime files, existing planning files, and CI/workflow files.
4. Fill the map and inventory from observed evidence.
5. Refresh `work/index.md` and `work/index.json`.
6. Create deeper work artifacts only after review justifies them.

Do not invent history. Mark inferred or uncertain items clearly.

Routing rule:

- Stable current facts go to `docs/` or README files.
- Unresolved work, uncertainty, risks, and coordination needs go to `work/`.

## Verify

After creating or moving artifacts:

- Confirm files landed under `work/`.
- Refresh `work/index.md` and `work/index.json` when the script exists.
- Prefer `complete_workpackage.py` when moving active workpackages to completed.
- Check parent/map links when relevant.
- Scan for stale paths after moving completed workpackages.
- Run relevant script syntax checks, such as `python3 -m py_compile`, when scripts changed.
- Keep git changes scoped to the shed/work artifacts involved.
