# Workspace Work-Level Customization

Tool Shed keeps one portable definition for `work1` through `work5`, while allowing an individual
project to add its own required actions. The optional tracked `work/tool-shed.yaml` file can wrap a
single selected endpoint with ordered workspace-specific actions or explicitly replace its standard
behavior.

No configuration is the default. Existing workspaces without this file, or without a matching
level entry, retain the standard Tool Shed behavior exactly.

## Configuration

The configuration uses schema version 1 and the existing workspace environment model:

```yaml
schema_version: 1
work_model: split
development_target: staging
production_target: production
work_levels:
  work2:
    before:
      - Run scripts/prepare-staging.sh
    run_default: true
    after:
      - Verify the project-specific staging health page
  work3:
    after:
      - Generate the customer handoff summary
  work4:
    before:
      - Run scripts/controlled-publish.sh --preflight
    run_default: false
    after:
      - Verify the controlled publication result
  work5:
    after:
      - Record the required operations acceptance evidence
```

Supported root keys are:

- `schema_version`: required and currently `1`;
- `work_model`: optional `combined` or `split` environment model;
- `development_target` and `production_target`: optional agent-readable target names;
- `work_levels`: optional mapping of canonical `work1` through `work5` entries.

Each level accepts `before`, `run_default`, and `after`. Actions are non-empty strings in block
lists. They may describe an agent-performed step or name an existing workspace command or script.
Tool Shed does not create a separate shell-hook runtime, store credentials, or invent deployment
infrastructure from this file.

## Resolution And Ordering

Resolve the route before execution:

```bash
python3 tool_shed/scripts/work_level_config.py --workspace . resolve work3 --json
```

Use `scripts/work_level_config.py` in the canonical Tool Shed development checkout. The helper also
provides a validation-only command:

```bash
python3 tool_shed/scripts/work_level_config.py --workspace . validate --json
```

Resolution applies one envelope to the selected canonical endpoint:

1. run `before` actions in declaration order;
2. run the standard cumulative work-level behavior unless `run_default: false`;
3. run `after` actions in declaration order.

`ts:work`, `ts:freeze`, `ts:push`, and `ts:ship` resolve to `work2`, `work3`, `work4`, and `work5`
before configuration is selected. Aliases have no separate entries. Lower-level customization
envelopes do not run again: the standard behavior of the selected endpoint is already cumulative,
and applying every lower envelope could repeat builds, deployments, commits, or publication.

Every declared action is required. On the first failure, stop; do not execute the remaining
actions or later phases, and do not report the endpoint complete. The resolved plan and any
`run_default: false` suppression must be surfaced before actions begin.

## Default Suppression

Use `run_default: false` only when workspace actions replace the selected endpoint's normal
behavior. A level that suppresses its default must declare at least one before or after action;
an empty replacement is invalid. Suppression applies to work-level actions, not to Tool Shed's
safety, campaign-continuity, evidence-comparison, or outcome-verification rules.

Removing the level entry restores the standard behavior. Removing the entire file restores all
standard behavior, subject to the same environment-routing discovery used before customization.

## Authority And Safety

Invoking a configured work level includes its declared actions as part of that endpoint for the
current goal, so operators do not need to repeat project-specific steps in every prompt. The
configuration still cannot:

- broaden the current goal beyond the named workspace outcome;
- bypass credentials, protected-environment approvals, or repository policy;
- waive destructive or irreversible action safeguards;
- turn a non-production endpoint into silent production publication; or
- make a failed or unverified result complete.

Keep credentials out of the file. Apply the normal prospective failure check before consequential
configured actions, preserve unrelated work, and use the project's existing tooling and runbooks.

## Validation Rules

The deterministic parser intentionally supports a small YAML subset so disconnected snapshots
need no third-party YAML dependency. Use spaces, block mappings, and block lists. Full-line comments
are supported. Inline mappings and lists are rejected except for the empty list `[]`.

Validation rejects unsupported schema versions, unknown root or level keys, aliases inside
`work_levels`, duplicate declarations, invalid booleans, malformed indentation, empty actions,
oversized files or actions, symlinked configuration, and empty default replacements.

Installation validates an existing declaration before mutating the workspace and never creates or
overwrites the file. Snapshot upgrades preserve its bytes as owner-authored work; a malformed file
causes post-install convergence to fail and roll back rather than partially applying guidance or
workspace changes.
