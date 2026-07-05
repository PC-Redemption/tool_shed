# Existing Project Level 2 Onboarding

Use this runbook when loading `tool_shed` onto an existing project.

Default to Level 2: create a project map, then create an inventory of existing docs/code/work surfaces. Use those two artifacts before deciding whether to backfill workpackages, tickets, ADRs, runbooks, or checklists.

## Preconditions

- Read `selection.md` and `conventions.md`.
- Work from the project root.
- Treat the existing project as evidence. Do not invent history.

## Procedure

1. Install the work tree:

```bash
python3 tool_shed/scripts/install_into_workspace.py .
```

2. Discover the project shape:

```bash
find . -maxdepth 2 -type f -not -path './.git/*' | sort
find . -maxdepth 3 -type d -not -path './.git/*' | sort
```

3. Read the front-door files first:

- `README*`
- `docs/`
- package/build/test files
- existing planning files
- CI/workflow files

4. Create the Level 2 artifacts:

```bash
python3 tool_shed/scripts/onboard_existing_project.py "Project name" --workspace .
```

Manual equivalent:

```bash
python3 tool_shed/scripts/new_artifact.py project-map "Project name" --workspace .
python3 tool_shed/scripts/new_artifact.py existing-project-inventory "Project name surfaces" --workspace .
```

5. Fill the project map with:

- the 30,000 ft outcome
- major workstreams or code areas
- known dependencies
- active unknowns
- the current ground-level next action

6. Fill the inventory with observed surfaces:

- docs and README files
- code entry points and major modules
- tests and validation commands
- build/deploy/runtime files
- existing work/planning artifacts
- risks, unknowns, and stale-looking areas

7. Decide whether to backfill more:

- Use a workpackage for multi-step transformations.
- Use tickets for clear behavior changes.
- Use checklists for known bounded execution.
- Use spikes for uncertainty.
- Use ADRs only for decisions supported by evidence.
- Use runbooks for repeatable operations.

8. Promote settled current truth to `docs/` or README files. Keep coordination under `work/`.

## Verification

- `work/maps/` contains one project map.
- `work/inventories/` contains one existing-project inventory.
- The map points to the inventory.
- The inventory separates observed facts from inferred follow-up.
- No historical decisions, incidents, or completed work were invented.

## Recovery

- If the project is smaller than expected, keep only the map or remove generated artifacts before committing.
- If discovery shows many unknowns, create a spike instead of backfilling workpackages.
- If generated artifacts are noisy, trim them to the current project shape before using them as coordination surfaces.
