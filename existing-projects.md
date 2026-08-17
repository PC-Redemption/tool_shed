# Existing Project Level 2 Onboarding

Use this runbook when loading `tool_shed` onto an existing project.

Default to Level 2: create a project map, then create an inventory of existing docs/code/work surfaces. Use those two artifacts before deciding whether to backfill workpackages, tickets, ADRs, runbooks, or checklists.

## Preconditions

- Read `selection.md` and `conventions.md`.
- Work from the project root.
- Treat the existing project as evidence. Do not invent history.
- Confirm the local `tool_shed/` is a disconnected snapshot: it has no `.git/`, is not a submodule, and the parent codebase repository ignores `/tool_shed/`.
- Confirm root `work/` is trackable. If installation reports that it is ignored, do not assume the
  rule is intentional: remove only the reported root `/work/` rule, unless repository-root
  `.tool-shed-policy.json` explicitly documents the exception.

## Procedure

1. Install the work tree:

```bash
python3 tool_shed/scripts/install_into_workspace.py .
```

The installer preserves every existing owner-authored `work/` file's content. It may relocate
legacy Tool Shed paths into the canonical work tree and regenerate Tool Shed-owned indexes or queue
projections. When a stale legacy ignore is present, it reports the exact source and rule, previews
the number and size of files that will become trackable, and exits nonzero until the rule is removed
or a valid exception is documented.
It preserves existing `.gitignore` and provider-native instruction content while appending or
refreshing marked Tool Shed generated-output and routing guidance. Use `--provider <provider-id>`;
the backward-compatible default is `codex`.

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

5. Refresh the work indexes:

```bash
python3 tool_shed/scripts/update_work_index.py --workspace .
```

Review workspace-preflight warnings before continuing. Existing raw evidence does not need to
move: add its exact path to `.git/info/exclude`, direct future raw output to
`work/evidence/generated/`, and keep small summaries and manifests versioned in `work/evidence/`.

6. Fill the project map with:

- the 30,000 ft outcome
- major workstreams or code areas
- known dependencies
- active unknowns
- the current ground-level next action

7. Discover the project's enduring focus areas in `work/focus-areas.md`:

- inspect docs and architecture, source and build targets, external apps and repositories,
  runtime/service/hardware boundaries, tests and fixtures, qualification infrastructure,
  deployment/release/regulatory/supply workflows, and active/deferred/completed work
- prefer stable owner responsibilities over temporary initiatives or an assumed generic taxonomy
- record evidence, inclusions, exclusions, overlaps, gaps, and uncertainties for every proposed area
- keep `Status: proposed` until the owner approves the complete catalog
- when approving, assign every active campaign a known primary area in the same exact
  reconciliation manifest

8. Fill the inventory with observed surfaces:

- docs and README files
- code entry points and major modules
- tests and validation commands
- build/deploy/runtime files
- existing work/planning artifacts
- risks, unknowns, and stale-looking areas

9. Decide whether to backfill more:

- Route stable current facts to `docs/` or README files.
- Route unresolved work, uncertainty, risks, and coordination needs to `work/`.
- Use a workpackage for multi-step transformations.
- Use tickets for clear behavior changes.
- Use checklists for known bounded execution.
- Use spikes for uncertainty.
- Use ADRs only for decisions supported by evidence.
- Use runbooks for repeatable operations.

10. Promote settled current truth to `docs/` or README files. Keep coordination under `work/`.
11. Refresh `work/index.md` and `work/index.json` after filling, moving, completing, or superseding artifacts.
12. Complete active workpackages with `python3 tool_shed/scripts/complete_workpackage.py work/wp/active/wp-example.md --workspace .`.
13. Fix stale-link warnings from the completion helper, or run `python3 tool_shed/scripts/check_stale_paths.py --workspace .` after manual moves.

## Routing Table

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
| Approved multi-milestone sequencing and evidence gates | `work/roadmaps/` |

## Verification

- `work/maps/` contains one project map.
- `work/inventories/` contains one existing-project inventory.
- `work/index.md` and `work/index.json` list the generated artifacts.
- The map points to the inventory.
- The inventory separates observed facts from inferred follow-up.
- `work/focus-areas.md` contains an evidence-backed proposed catalog or a deliberately approved one.
- An approved catalog maps every active campaign to at least one known primary focus area.
- No historical decisions, incidents, or completed work were invented.
- Roadmap ingestion, when requested, previews completed, active, remaining, superseded, excluded,
  and uncertain classifications without changing existing work.
- The stale-path check passes after any artifact moves.

## Recovery

- If the project is smaller than expected, keep only the map or remove generated artifacts before committing.
- If discovery shows many unknowns, create a spike instead of backfilling workpackages.
- If generated artifacts are noisy, trim them to the current project shape before using them as coordination surfaces.
