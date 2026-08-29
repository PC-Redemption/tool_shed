# Completion Watcher v1 Local Release Evidence

Status: complete
Type: evidence
Updated: 2026-08-19
Next Action: none
Parent: work/00-campaigns/completed/038-qualify-and-release-local-completion-watchers.md
Campaign: qualify-and-release-local-completion-watchers

## Scope

Evidence for roadmap milestone `M3-LOCAL-RELEASE` and gate `G3-LOCAL-RELEASE-PROVEN`.

Target project:

- Project ID: `817b6358-b2f5-48fd-bb66-bd80f936faca`
- Repository: `/home/jon/docker/tool_shed`
- Completed validation observation: `2026-08-19`

## Command evidence

```text
python3 scripts/validate_tool_shed.py
# Result: OK, 165 tests passed, provider conformance, indexes regenerated, stale-paths clean,
# work-state reconciled, roadmap validation passed, provider docs smoke passed.

python3 scripts/build_docs_site.py
# Built 23 pages and 61 commands at build/ts.rookaro.com

python3 scripts/check_shed_version.py --shed .
# Local Tool Shed: 0.24.0 (verified)
# Canonical Tool Shed: 0.23.0
# Version relation: newer
# Local release: tag=v0.24.0, minimum_updater_protocol=3

python3 scripts/update_shed_manifest.py --check
# SHED_VERSION.json matches tracked file set

python3 -m unittest \
  tests.test_scripts.ScriptTests.test_snapshot_updater_rejects_invalid_release_before_mutation \
  tests.test_scripts.ScriptTests.test_snapshot_updater_rejects_release_validation_failure_before_mutation \
  tests.test_scripts.ScriptTests.test_snapshot_updater_requires_matching_project_binding_before_mutation \
  tests.test_scripts.ScriptTests.test_snapshot_campaign_convergence_rolls_back_after_injected_failure
# 4 passed
```

### Bounded local pilot (Linux)

```text
temp state root: /tmp/cw_pilot_local_release/state

arm:
{"state": "armed", "state_root": "/tmp/cw_pilot_local_release/state", "watch_id": "11111111-1111-4111-8111-111111111111"}

status (initial): pending includes watch id

ensure-runner: completed, terminal event emitted locally and delivered through `local-alpha-noop` adapter

status (final): pending empty, outbox receipts=1, claimed/pending/retired queues clean
outbox receipt: 7e85f32b48a0d90d9b6ecdd9163a6104626eb526c77bbd8dcf9275111e6f6fb1.json
```

## Release and downgrade posture

- `SHED_VERSION.json` currently declares version `0.24.0`, release tag `v0.24.0`, and release-provenance placeholders (`release_commit`, `released_at`) pending publication:
  - `release_commit: null`
  - `released_at: null`
- Release tooling and manifest checks are in place and pass; explicit publish to GitHub Release is still pending an explicit release route/tag step.
- `minimum_updater_protocol: 3` is recorded, so downgrade behavior stays governed by snapshot/protocol checks in the existing updater path.
- Campaign completion evidence includes the tested updater-rollback/validation scripts above.
