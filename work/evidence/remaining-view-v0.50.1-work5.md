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

### Development lanes

- Web: exact candidate `689b81132a48f5f28c84846ca7a03b961cf53d80` built as
  `tool-shed-dashboard:dev-689b81132a48` with image digest
  `sha256:6176c7617322966ba95bf46689c212dd92527cf9d8fb322edfe623ca040d6dd6`.
  The development stack and HTTP health endpoint were healthy. An in-container production-shape
  probe returned `False` for completed, superseded, abandoned, and deferred legacy rows with
  unknown lifecycle fields, and `True` for the same row carrying an explicit open disposition.
- Linux: the clean candidate archive (SHA-256
  `a7a0cde0d590a20d8777bc534d14ba7262acb50040d3ddb72c5282aea7d28c83`) was installed in the
  authorized `sup:/home/jon/dev/ts_linux_test_bed` test bed. The 54 focused tests passed under
  Python 3.13, strict snapshot integrity was verified, strict Doctor was healthy, and the parent
  repository remained clean.
- Windows: the same archive was installed in the authorized
  `GOGETTER:E:\dev\ts_windows_test_bed` test bed. The 54 focused tests passed under Windows using
  the maintained qualification environment (Django 5.2.17), strict snapshot integrity was
  verified, strict Doctor was healthy, and the parent repository remained clean.

Exact-SHA CI, publication, production promotion, clean unfiltered dashboard verification,
automatic reporter convergence, and direct-outcome reconciliation remain required.
