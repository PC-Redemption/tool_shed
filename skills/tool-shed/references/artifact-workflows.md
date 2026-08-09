# Tool Shed artifact workflows

Read this reference for artifact selection, creation, onboarding, completion, or reconciliation.

## Select

Use `<shed>/selection.md` as authority:

- checklist: bounded known steps;
- ticket: specific behavior change with compact acceptance criteria;
- project map: visual coordination across moving parts;
- workpackage: multi-step transformation with sequencing or handoff cost;
- ADR: durable decision with alternatives and consequences;
- runbook: repeatable operation with ordered recovery guidance;
- incident: break/fix learning;
- spike: bounded uncertainty whose deliverable is learning;
- deep-research spike: cross-layer uncertainty driving churn or risky assumptions;
- inventory: classification, ownership, routing, or disposition;
- decision matrix: visible tradeoffs among two to five plausible options.

## Create And Maintain

Prefer the shed scripts:

```bash
python3 <shed>/scripts/install_into_workspace.py <workspace> --provider <provider-id>
python3 <shed>/scripts/new_artifact.py <kind> "Title" --workspace <workspace>
python3 <shed>/scripts/complete_workpackage.py work/wp/active/wp-example.md --workspace <workspace>
python3 <shed>/scripts/update_work_index.py --workspace <workspace>
python3 <shed>/scripts/check_stale_paths.py --workspace <workspace>
python3 <shed>/scripts/review_work_state.py --workspace <workspace>
```

Use templates only when a required script is absent. Preserve naming and locations from
`conventions.md`. Every active non-map artifact needs a concrete parent or project map.

## Existing Projects

Default to Level 2 onboarding:

1. Create a project map.
2. Create an existing-project inventory.
3. Discover front-door docs, code, tests, build/runtime, planning, and CI surfaces.
4. Record observed evidence without inventing history.
5. Refresh the indexes.
6. Create deeper artifacts only when evidence justifies them.

Use `python3 <shed>/scripts/onboard_existing_project.py "Project name" --workspace <workspace>` when
available. Stable facts go to project docs; unresolved work, risks, and uncertainty go to `work/`.

## Evidence And Verification

Before long validation, run `workspace_preflight.py`. Keep raw generated evidence in the configured
ignored generated path and small versioned manifests outside it. Never apply evidence migration
without an exact approved manifest and verified archive.

After artifact lifecycle changes, confirm paths, regenerate indexes, check stale references, and
run the work-state review. Use `--strict` when reconciliation findings should fail automation.
