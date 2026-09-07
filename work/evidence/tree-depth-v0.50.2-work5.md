# Tree Depth Controls v0.50.2 Work5 Evidence

Status: in-progress
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
- Web production: pending.
- Linux released-client qualification: pending.
- Windows released-client qualification: pending.

## Release And Reconciliation

- Frozen content commit and exact-SHA CI: pending.
- GitHub Release and production promotion: pending.
- Owning outcome and release cohort reconciliation: pending.
