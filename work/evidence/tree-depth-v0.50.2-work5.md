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
- Pending real-browser interaction proof against the isolated development dashboard.

## Three-Lane Qualification

- Web development: pending.
- Linux development: pending.
- Windows development: pending.
- Web production: pending.
- Linux released-client qualification: pending.
- Windows released-client qualification: pending.

## Release And Reconciliation

- Frozen content commit and exact-SHA CI: pending.
- GitHub Release and production promotion: pending.
- Owning outcome and release cohort reconciliation: pending.
