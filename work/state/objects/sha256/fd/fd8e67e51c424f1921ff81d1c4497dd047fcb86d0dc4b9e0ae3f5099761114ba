# Completion Watcher v1 Alpha Evidence

Status: complete
Type: evidence
Updated: 2026-08-19
Next Action: none
Parent: work/maps/map-disposable-completion-watchers-and-hosted-notifications.md
Campaign: implement-portable-local-completion-watcher-alpha

## Scope

Evidence for roadmap milestone `M2-LOCAL-ALPHA` and gate `G2-LOCAL-ALPHA-PROVEN`. This evidence covers the portable local alpha implementation, runner semantics, durable outbox behavior, and local-only operation.

Target project:

- Project ID: `817b6358-b2f5-48fd-bb66-bd80f936faca`
- Repository: `/home/jon/docker/tool_shed`
- Campaign: `implement-portable-local-completion-watcher-alpha`
- Completed validation observation: `2026-08-19T10:17:52Z`

## Commands and outcomes

```text
python3 scripts/validate_tool_shed.py
165 tests passed; Python compile, manifest check, unit tests, provider adapter conformance,
work-tree indexes, stale-path checks, work-state review, roadmap validation, and temp workspace smoke passed.

python3 -m unittest tests.test_completion_watcher_contract -v
5 tests passed

python3 -m unittest tests.test_completion_watcher_runtime -v
3 tests passed

python3 -m unittest tests.test_completion_watcher_contract tests.test_completion_watcher_runtime -v
8 tests passed

python3 scripts/review_work_state.py --workspace . --json
{ "findings": [], "summary": {"total": 0, "errors": 0, "warnings": 0} }

python3 scripts/update_shed_manifest.py --write --version 0.24.0 --allow-same-version
Updated manifest with completion watcher scripts and tests included.
```

Observed behavior includes:

- one-shot `arm`, `status`, `cancel`, `retire`, and `ensure-runner` command execution paths;
- atomic spool and outbox idempotency;
- singleton runner lock behavior, claims, recovery and stale lease handling;
- cancellation precedence before checker result;
- missing-target and checker-error policy boundaries from contract fixtures;
- local-only safe permission checks and downgrade-resilient behavior.

## Versioned artifact hashes

| Artifact | SHA-256 |
| --- | --- |
| `scripts/completion_watcher.py` | `e7a48f1f90a6ea83a7c840dc06b0e98e60a5528130b773e1b84a563aef7c6589` |
| `tests/test_completion_watcher_runtime.py` | `e8b408dc0e9c1d2b689439cdd7d2e2db165adbd303946f9ed50649337659bbbc` |
| `docs/completion-watcher-protocol.md` | `840f5581570c3ce4e93788483b6c49e48fdd21de991ded0a716c5c18b016d0d8` |
