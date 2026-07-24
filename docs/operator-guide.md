# Tool Shed Operator Guide

Tool Shed helps a human and Codex preserve project coordination in plain Markdown. The
workspace-local `tool_shed/` directory supplies reusable rules, templates, and scripts; the
project's tracked `work/` directory holds its planning artifacts.

## Getting Help

Type:

```text
ts: help
```

Codex should read this guide and return a concise menu of relevant use cases with example prompts.
Help is read-only: it must not create or change artifacts unless the same request explicitly asks
for a change.

Ask for focused help with:

```text
ts: help spikes
ts: help existing projects
ts: help completing work
ts: help install
ts: help update
ts: help version
```

## Common Use Cases

### Orient in a project

Use this when returning to a project or deciding what deserves attention next.

```text
ts: orient me
ts: show active work and the next concrete actions
```

Codex reads project docs, `work/index.md`, active maps and artifacts, then runs the read-only
work-state review.

### Capture a small known task

Use a checklist when the steps are known and forgetting one is the main risk.

```text
ts: create the smallest artifact for validating the release
ts: make a checklist for cleaning up the root documentation
```

### Record a bug or enhancement

Use a ticket when expected behavior and acceptance criteria are clear.

```text
ts: create a ticket for the broken retry behavior
```

### Coordinate a larger change

Use a workpackage for a multi-step transformation and a project map when several workstreams or
artifacts must stay aligned.

```text
ts: plan the authentication migration
ts: map the active workstreams and show the current ground task
```

### Investigate uncertainty

Use a spike when the deliverable is learning rather than production code.

```text
ts: create a time-boxed spike to compare deployment options
```

When a spike finishes, record `Disposition:` as `planned`, `documented`, `no-action`, or
`superseded`. A planned spike names its follow-up artifact in `Produces:`.

### Preserve a decision or operation

Use an ADR for a durable decision, a decision matrix to compare options, and a runbook for a
repeatable operation.

```text
ts: record the database choice as an ADR
ts: compare these hosting options in a decision matrix
ts: create a rollback runbook
```

### Onboard an existing project

Use Level 2 onboarding to create a project map and inventory before backfilling detailed work.

```text
ts: onboard this existing project
```

Codex observes the repository before creating inferred history. Stable facts go to project docs;
unresolved work stays under `work/`.

### Review planning drift

Use reconciliation when artifacts may have fallen out of sync with plans.

```text
ts: review work state
ts: find orphaned, stale, or undisposed work
```

The underlying command is:

```bash
python3 tool_shed/scripts/review_work_state.py --workspace .
```

It is advisory by default. `--json` supports automation and `--strict` makes findings fail the
command.

### Complete or supersede work

```text
ts: complete work/wp/active/wp-example.md
ts: supersede this decision and preserve the history
```

Completed artifacts remain history. Promote settled current truth to project `docs/` or README
files.

### Install or update Tool Shed

```text
ts: help install
ts: help update
```

The canonical source is [PC-Redemption/tool_shed](https://github.com/PC-Redemption/tool_shed).
Installations are disconnected snapshots: ignore `/tool_shed/`, remove its `.git/`, and track
project-specific `/work/` by default. An update replaces only Tool Shed machinery and must preserve
`work/`, project docs, and code.

After installation or update, run:

```bash
python3 tool_shed/scripts/install_into_workspace.py .
python3 tool_shed/scripts/review_work_state.py --workspace .
```

Both commands detect a root `work/` ignore. An existing rule is not automatically repository
policy. Without a valid repository-root `.tool-shed-policy.json` exception, the output identifies
the exact ignore source and matching rule and previews the count and size of ignored files. Remove
only that root `/work/` rule. Do not delete, replace, relocate, or rewrite any `work/` evidence.

An intentional exception uses:

```json
{
  "schema_version": 1,
  "work_git_policy": {
    "ignore": true,
    "reason": "Repository-specific reason for excluding project work artifacts."
  }
}
```

### Check version and update status

```text
ts: version
ts: check for updates
ts: update status
```

`ts: version` verifies the local snapshot against its own `SHED_VERSION.json` without using the
network. An update-status request also reads the canonical manifest from GitHub and distinguishes:

- `current`: local and canonical versions match and local tracked files are intact
- `older`: canonical has a newer semantic version
- `newer`: local declares a version ahead of canonical
- `modified`: local tracked content differs from its version manifest
- `release-mismatch`: equal local/canonical versions contain different release manifests
- `check-failed`: canonical status could not be retrieved or parsed

The check is read-only and never authorizes or applies an update.

## Artifact Menu

| Need | Artifact |
| --- | --- |
| Known bounded steps | Checklist |
| Clear bug or enhancement | Ticket |
| Multiple workstreams and navigation | Project map |
| Multi-step transformation | Workpackage |
| Durable decision | ADR |
| Repeatable operation | Runbook |
| Break/fix learning | Incident |
| Time-boxed uncertainty | Spike |
| Classify or route a collection | Inventory |
| Compare plausible options | Decision matrix |

When unsure, ask:

```text
ts: choose the smallest artifact for this: <describe the need>
```

Tool Shed should not become a server, database, general task tracker, or replacement for canonical
project documentation.
