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

## Workspace Installation Boundary

Install `tool_shed/` into a project as a local, one-way snapshot of the blank templates, instructions, and helper scripts. The workspace copy is not a checkout for developing the canonical Tool Shed repository.

Canonical source: [https://github.com/PC-Redemption/tool_shed](https://github.com/PC-Redemption/tool_shed)

- Do not leave `tool_shed/.git/` in the project workspace.
- Do not configure the workspace copy as a Git submodule.
- Do not run `git pull`, `git push`, or otherwise return workspace changes to `PC-Redemption/tool_shed`.
- Add `/tool_shed/` to the project repository's root `.gitignore` so Tool Shed stays outside the codebase history.
- Keep project-specific artifacts in `work/` and track that directory with the project by default. Ignore it only through an explicit repository policy, such as for sensitive owner planning.

One-time snapshot installation with GitHub CLI:

```bash
gh repo clone PC-Redemption/tool_shed tool_shed
rm -rf tool_shed/.git
printf '\n/tool_shed/\n' >> .gitignore
```

Run the removal only with the explicit workspace path shown above, after confirming the clone succeeded. Updates are deliberate snapshot replacements, not pulls: obtain a fresh copy elsewhere, review the differences, and replace only the intended tooling files without copying Git metadata.

## Quick Start

Operator help and use cases:

```text
ts: help
ts: help spikes
ts: help existing projects
```

See the [Tool Shed operator guide](docs/operator-guide.md) for the full use-case menu.

Check the installed snapshot without using the network, or compare it with the canonical manifest:

```bash
python3 tool_shed/scripts/check_shed_version.py --shed tool_shed --local-only
python3 tool_shed/scripts/check_shed_version.py --shed tool_shed
```

Equivalent Codex requests are `ts: version`, `ts: check for updates`, and `ts: update status`.
Checks are read-only and do not authorize snapshot replacement.

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

Review whether work artifacts and planning are still aligned:

```bash
python3 tool_shed/scripts/review_work_state.py --workspace .
python3 tool_shed/scripts/review_work_state.py --workspace . --json
```

Run this during orientation, after artifact lifecycle changes, in validation, and weekly as a
backstop. Add `--strict` when findings should fail CI.

Run the full repository validation:

```bash
python3 scripts/validate_tool_shed.py
```

GitHub Actions runs the same validation on push and pull requests.

Before releasing a changed snapshot, intentionally bump the semantic version and refresh its
content hashes:

```bash
python3 scripts/update_shed_manifest.py --write --version MAJOR.MINOR.PATCH --notes "Release summary"
python3 scripts/update_shed_manifest.py --check
```

For a published release, also pass `--release-commit`, `--release-tag vMAJOR.MINOR.PATCH`, and
`--released-at`. Use `--allow-same-version` only to rebuild an unpublished manifest. Equal version
numbers with different canonical content are reported as `release-mismatch`.

Follow [docs/releasing.md](docs/releasing.md) for the two-commit provenance workflow, annotated tag,
and post-push verification.

Before choosing an artifact, read:

- [selection.md](./selection.md)
- [conventions.md](./conventions.md)
- [existing-projects.md](./existing-projects.md) when loading `tool_shed` into an existing project

## Codex Start Prompts

Use short prompts and let Codex operate the scripts:

Request prefixes are authoritative for one request only:

- `ts:` uses the workspace-local Tool Shed rules and tooling for the remainder of the request.
- `mp:` targets projects, tasks, and owner work in private Marshal.
- `ws:` targets files, code, tests, Tool Shed plans, and runtime work in the current workspace.

Never carry a prefix into a later request. A request uses at most one leading route prefix.

```text
use tool_shed and orient me
```

```text
use tool_shed and create the smallest artifact for this
```

```text
use tool_shed and complete work/wp/active/wp-example.md
```

Codex should read README/docs first, then `work/index.md`, then active artifacts. It should use `work/index.json` only when automation needs machine-readable navigation. Codex should then run the read-only work-state review and surface findings before choosing the next action.

### Codex install and update prompts

For a new installation:

```text
Install Tool Shed into this workspace as a disconnected snapshot. Read tool_shed/README.md,
selection.md, conventions.md, and existing-projects.md. Ignore /tool_shed/ but track /work/ by
default, initialize the work tree, run the work-state review, and report validation results.
```

For an existing installation:

```text
Update this workspace's disconnected tool_shed snapshot from
https://github.com/PC-Redemption/tool_shed.
Preserve work/, docs/, project code, and local repository policy. Review the snapshot diff before
replacement, never copy .git metadata, run install_into_workspace.py to add missing work
directories without overwriting artifacts, then refresh the index, review work state, check stale
paths, and report validation results.
```

An update replaces only the ignored `tool_shed/` machinery. It must never replace or delete the
project's tracked `work/` artifacts.

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

Canonical repository: [PC-Redemption/tool_shed](https://github.com/PC-Redemption/tool_shed).

The repository should be public for visibility, but direct changes should be limited to owners/admins of the `PC-Redemption` organization. Public readers may fork or propose changes through normal GitHub flows, but maintainers should avoid granting broad write access.

This governance applies to intentional development checkouts of the canonical repository. A `tool_shed/` directory installed inside another project is a disconnected snapshot and must not be used to contribute changes upstream.

## Codex Skill

`tool_shed` includes a thin Codex skill package at `skills/tool-shed`.

The skill is also installed locally at `${CODEX_HOME:-~/.codex}/skills/tool-shed` for auto-discovery in this environment. It is an adoption/routing layer only: it teaches Codex to find and use workspace-local `tool_shed` files and scripts instead of duplicating templates.

Initial skill packaging is local plus repo-packaged. Plugin packaging is intentionally deferred until real use shows it is needed.

## Lessons Integration

Recommended durable lesson:

> If a workspace has `tool_shed/`, read `tool_shed/selection.md` before choosing a planning or documentation artifact. Do not default to workpackages. Use the smallest artifact that fits the task. Project-specific artifacts live under `work/`; `tool_shed/` contains only templates, rules, and helper scripts.
