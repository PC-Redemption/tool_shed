# Tree Depth Controls v0.50.2 Work5 Evidence

Status: passed
Recorded: 2026-09-07
Release lane: `tree-depth-v0.50.2`

## Product Contract

The Work tree presents an instant hierarchy-depth control above the table. Level `1` shows root
parents only, `2` adds their children, `3` adds grandchildren, and `All` shows the full reported
hierarchy. The control changes presentation only: it does not alter the Remaining scope, planning
order, root-chain pagination, or authoritative Tool Shed state. Individual row chevrons remain
available for custom expansion after a preset is applied.

## Focused Verification

- `tests.test_dashboard_app` and `tests.test_work_projection` passed 54 tests, including hierarchy
  depth metadata, all four accessible presets, the default `All` selection, and absence of the
  controls from List view.
- `node --check dashboard/fleet/static/fleet/dashboard.js` passed.
- The local release profile passed 624/624 isolated tests plus manifest, provider-adapter, Hybrid
  view, stale-path, work-state, roadmap, bootstrap-closure, fresh-install, template, and example
  checks in 37.052 seconds.
- A real Chrome browser on `GOGETTER` authenticated to the isolated development dashboard and
  exercised a four-level reported hierarchy. `All` showed 5 rows at depths 0–3; `1` showed 2 root
  rows; `2` showed 3 rows at depths 0–1; and `3` showed 4 rows at depths 0–2. Every preset exposed
  the correct single pressed state. A subsequent row-chevron collapse cleared the global preset
  and reported `aria-expanded=false`.

## Three-Lane Qualification

- Web development: exact candidate `3a3389d60c792564c6f47644745202d09fd0cde7` is healthy as
  `tool-shed-dashboard:dev-3a3389d60c79` at image digest
  `sha256:211195346e5727e171a18c441db3cf8bf7acc2982a12163073adb284985232f2`.
  Production health remained HTTP 200 and its Compose project was not changed.
- Linux development: the disconnected candidate archive
  `sha256:37bb6c5b5e918f558cb359b552fdb10dce5d44c8f704c0136d57b75be63c5af1`
  passed 54 focused tests, strict snapshot integrity, and a healthy Doctor in
  `/home/jon/dev/ts_linux_test_bed`; the parent repository remained clean.
- Windows development: the same archive passed 54 focused tests, strict snapshot integrity, and a
  healthy Doctor in `GOGETTER:E:\dev\ts_windows_test_bed`; the parent repository remained clean.
- The three-lane Work3 development gate passed for the exact candidate.
- Web production: the validated encrypted PostgreSQL backup
  `dashboard-daily-20260907T115201Z.dump.age` and filesystem rollback bundle
  `release-backups/pre-v0.50.2-20260907T1152Z` preceded promotion. Production is healthy on
  `tool-shed-dashboard:v0.50.2` at image digest
  `sha256:211195346e5727e171a18c441db3cf8bf7acc2982a12163073adb284985232f2`;
  the public dashboard and documentation health endpoints returned HTTP 200. An authenticated
  production render contained all four controls and eight depth-annotated rows for the selected
  hierarchy, while List view contained no depth controls.
- Linux released-client qualification: the official stable updater selected `v0.50.2`, verified
  provenance for frozen content commit `0cd14bb0b509a31ddae54918718c4a94caac64a3`, preserved the
  existing work and Hybrid state, retained rollback archive
  `tool_shed.backup-20260907T115545Z.tar`, and passed the attested client smoke plus all 54 focused
  tests. Doctor accepted the installed snapshot with only the expected generated index-date
  refresh warning.
- Windows released-client qualification: the official stable updater selected `v0.50.2`, verified
  the same frozen content commit, preserved existing work and Hybrid state, retained rollback
  archive `tool_shed.backup-20260907T115804Z.tar`, and passed the attested client smoke plus all 54
  focused tests. Doctor reported the same non-semantic generated index-date refresh warning.

## Release And Reconciliation

- Frozen content commit `0cd14bb0b509a31ddae54918718c4a94caac64a3` passed the exact-SHA
  GitHub Validate matrix with all 33 jobs successful.
- Provenance commit `1372f7dd7e0ea61d78243ce4ec0d0fa24d7a081c` is tagged `v0.50.2`;
  the non-draft GitHub Release was published by the successful release workflow. All three
  production lanes are qualified.
- Automatic dashboard event sequence `11391` delivered in 1.983011 seconds with zero attempts;
  no manual worker or safety pass was used, and the local queue returned to zero. Production
  accepted client `0.50.2` with the complete 267-row inventory and now reports zero working,
  queued, open, unreconciled, or closure-debt items.
- Production qualification cycle `65b85548-cb27-4094-9862-9c03d7a79ff7` is satisfied and
  reconciled. Direct origin cycle `a45137bf-709d-4acd-909a-fa4cf8e1adb6` and release cohort
  `bbc90fe7-7022-4741-8daf-7bf5d2025e61` are terminal, recursively closed, satisfied, and
  reconciled against `v0.50.2`.
- GitHub issue #57 was reviewed and updated with the delivered hierarchy-navigation subset; it
  remains open for its broader semantic-fidelity scope.
