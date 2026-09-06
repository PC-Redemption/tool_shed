# Remaining View v0.50.1 Work5 Evidence

Status: in progress
Recorded: 2026-09-06
Release lane: `remaining-view-v0.50.1`

## Product Contract

The default Work view includes only explicitly reported unfinished obligations. Legacy completed,
superseded, abandoned, and deferred rows whose outcome and closure fields are merely unknown remain
available in All/List but do not count as remaining work. A completed ancestor is retained as
subdued tree context when it owns a genuinely remaining descendant.

## Focused Verification

- `tests.test_work_projection` and `tests.test_dashboard_app` passed 54 tests.
- Exact legacy production shapes using `CLOSURE_NOT_AVAILABLE`, one unknown descendant, and no open
  or invalid closure counts are covered without applying a Status filter.
- The release profile passed 624/624 isolated tests plus manifest, provider-adapter, Hybrid view,
  stale-path, work-state, roadmap, bootstrap-closure, fresh-install, template, and example checks
  in 37.584 seconds.

## Remaining Work5 Proof

Full release validation, development web/Linux/Windows qualification, exact-SHA CI, publication,
production promotion, clean unfiltered dashboard verification, automatic reporter convergence,
and direct-outcome reconciliation remain required.
