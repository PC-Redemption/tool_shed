# Adaptive Generated-Evidence Safeguards Validation

Status: complete
Type: evidence
Updated: 2026-07-25
Next Action: none
Parent: work/wp/completed/wp-generated-evidence-safety-and-migration.md

## Scope

Validation for workspace-adaptive evidence profiling, explainable risk budgets,
and guarded reversible migration derived from the
`7520553_SMI_FW` incident.

## Implemented Surfaces

- `scripts/workspace_preflight.py`
- `scripts/migrate_generated_evidence.py`
- `scripts/install_into_workspace.py`
- `scripts/work_tree.py`
- `conventions.md`
- `README.md`
- `docs/operator-guide.md`
- `docs/install-or-update-snapshot.md`
- `skills/tool-shed/SKILL.md`
- `tests/test_scripts.py`

## Profile Coverage

| Profile | Evidence Shape | Result |
| --- | --- | --- |
| Firmware | 2,065 tracked evidence paths, 124 untracked campaign paths, mixed-case `.SLG` and `.bin` | Adaptive count warning and tracked-binary finding detected |
| Application | Test traces under a custom evidence root | Custom evidence root included in profile |
| Data | Model output under a custom artifact root and policy-derived threshold | Workspace policy source reported |
| Media | Validation video beneath a custom capture root | Custom evidence composition reported |
| Documentation | Human-readable Markdown evidence | Durable evidence remains visible without a binary finding |

## Safety Claims

- Preflight is read-only and emits profile schema version 1 inside response schema
  version 2.
- Effective thresholds disclose whether they came from workspace policy or the
  adaptive baseline.
- Invalid, unreasoned, absolute, or escaping policy paths are actionable
  findings.
- Policy-adjusted thresholds are capped by non-overridable hard limits.
- Migration preparation writes its manifest and archive outside the repository.
- Apply requires top-level and per-candidate approval, a matching workspace,
  unchanged source hashes, a matching archive hash, archived membership, and an
  ignored generated destination.
- Apply changes only approved candidates, attempts rollback on move failure, and
  never stages, commits, deletes the archive, or rewrites Git history.
- Focused migration validation preserved unrelated dirty source and retained
  durable evidence byte-for-byte.

## Commands and Outcomes

```text
python3 -m unittest tests.test_scripts
35 tests passed

python3 scripts/update_shed_manifest.py --write --version 0.4.0 \
  --notes "Adds workspace-adaptive evidence profiling, explainable risk budgets, and guarded reversible evidence migration."
37 release files recorded

python3 scripts/validate_tool_shed.py
tool_shed validation passed
```

The full validator covered Python compilation, manifest integrity, all unit
tests, index regeneration, stale-path review, work-state reconciliation,
disposable-workspace smoke tests, and template/example sanity.

## Deferred Boundaries

- Git-history rewriting remains outside Tool Shed migration.
- The independent Codex Desktop renderer robustness defect remains external.
- Migration apply remains a separate explicitly approved workspace operation; it
  is never part of installation or snapshot update.
