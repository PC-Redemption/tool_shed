# Conventions

## Boundaries

The workspace-local `tool_shed/` is a disconnected snapshot. It must not contain `.git/`, be registered as a submodule, or be tracked by the parent codebase repository. The parent repository should ignore `/tool_shed/`. Workspace use must not push changes back to the canonical Tool Shed repository.

This exclusion applies only to the tooling snapshot. Root `work/` is repository-tracked by default.
An existing ignore rule is not an intentional exception. Ignoring `work/` requires both a matching
Git ignore rule and a valid repository-root `.tool-shed-policy.json` with
`schema_version: 1`, `work_git_policy.ignore: true`, and a non-empty
`work_git_policy.reason`.

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

## Work Index

`work/index.md` and `work/index.json` are generated orientation surfaces.

- Regenerate them with `python3 tool_shed/scripts/update_work_index.py --workspace .` after creating, moving, completing, or superseding artifacts.
- Read project README/docs first for current truth, then `work/index.md`, then the active artifacts it points to.
- Use `work/index.json` for automation that needs the same artifact list.
- Do not treat the indexes as canonical truth. They are navigation aids built from artifact headers.
- Completed artifacts remain useful history, but docs and README files hold current operating truth.

## Work-State Reconciliation

Git history makes work artifacts visible, but it does not keep them aligned. Track `work/` by
default and keep the workspace-local `/tool_shed/` snapshot ignored. A project may ignore
`work/` only through the explicit documented exception above.

Run `python3 tool_shed/scripts/review_work_state.py --workspace .`:

- when Codex or a human orients in the project
- after creating, completing, cancelling, or superseding an artifact
- during the repository validation workflow
- weekly as a backstop for quiet projects

The review is read-only. It reports orphaned active work, stale next actions, broken parent/output
links, completed spikes without a disposition, active plans that still point at finished work, and
repositories that ignore `work/`. Use `--json` for automation and `--strict` when any finding
should fail CI.

For an undocumented ignore, the review reports the exact ignore source, line, and matching rule,
plus the count and size of currently ignored files. Remove only the reported root `/work/` rule.
Never delete, replace, relocate, or rewrite existing evidence as part of this migration.

Every active non-map artifact should name a concrete `Parent:` or `Project Map:`. Every completed
spike must set `Disposition:` to `planned`, `documented`, `no-action`, or `superseded`. A planned
spike must identify its follow-up artifact in `Produces:`.

## Tool Shed Versioning

`SHED_VERSION.json` is the authoritative snapshot manifest. It records a semantic `shed_version`,
the artifact model version, canonical manifest URL, and hashes for shipped rules, docs, scripts,
skill files, and templates.

Use `scripts/check_shed_version.py --local-only` to verify local integrity without a network call.
Use it without `--local-only` to compare with canonical GitHub state. A version check is read-only
and must distinguish older, newer, current, locally modified, equal-version release mismatch, and
failed canonical checks.

Before releasing changed Tool Shed machinery, intentionally bump `MAJOR.MINOR.PATCH` and run
`scripts/update_shed_manifest.py --write`. A manifest write requires a greater version unless
`--allow-same-version` explicitly rebuilds an unpublished release. Released manifests record their
content commit, matching `v<version>` tag, and release timestamp. Repository validation fails when
manifest hashes or provenance are invalid.

Plan-drift checks inspect planning-bearing locations: `Next Action`, parent/project-map/dependency
fields, active workstream rows, unchecked tasks, and `Do next:` content. Historical, closeout, and
related-artifact links are valid references and do not become drift merely because their targets
are finished.

## Stale Path Check

Run `python3 tool_shed/scripts/check_stale_paths.py --workspace .` after moving, completing, or renaming artifacts.

The check is especially important after moving a workpackage from `work/wp/active/` to `work/wp/completed/`. It flags stale active-path references and missing `work/*.md` links.

## Workpackage Completion

Prefer the completion helper over a manual move:

```bash
python3 tool_shed/scripts/complete_workpackage.py work/wp/active/wp-example.md --workspace .
```

The helper moves the file to `work/wp/completed/`, marks `Status: complete`, updates `Updated:`, sets `Next Action: none` by default, regenerates `work/index.md` and `work/index.json`, and reports stale-link findings.

Use `--strict-stale-check` when automation should fail if old `work/wp/active/` links remain.

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

## Runtime And Local Config Rule

For operations, Docker, scheduler, or host-local work:

- Track examples and policy docs.
- Keep host-specific config, generated state, logs, and status payloads ignored unless the project explicitly decides otherwise.
- Record ignored local config paths in runbooks or closeout checklists when they materially affect behavior.
- Prove both sides of a migration closeout: the new runtime surface is healthy and the old runtime surface is disabled, inactive, or intentionally retained.

## Scheduler Rule

When a project introduces a scheduler or background worker, capture:

- cadence
- timeout
- action modes
- stale thresholds
- conflict or overlap rules
- cooldowns, retry limits, and restart guardrails
- runtime evidence showing whether jobs block or run concurrently

Use a runbook for repeatable operations, a checklist for bounded validation, and an ADR for durable policy changes.

## ADR Supersession Rule

Do not delete or rewrite old decisions to make history look tidy.

- Add `Supersedes:` to the new ADR when it replaces an older decision.
- Add `Superseded By:` to the old ADR.
- Promote the current operating policy to docs or README files.
- Keep the old ADR as historical context.

## Lessons Rule

Lessons should store routing and memory, not bulky templates.

Good lesson:

> Use `tool_shed/selection.md` before choosing a work artifact.

Bad lesson:

> A full copy of every artifact template.
