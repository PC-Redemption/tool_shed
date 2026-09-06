# Remaining View v0.50.1 Work5 Evidence

Status: passed
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

### Release and production lanes

- Frozen content commit `c39480b492070270ba9835a67cae6672d8690a56` passed the full GitHub
  Validate matrix: 33/33 jobs completed successfully with zero failures
  ([run 34064368612](https://github.com/PC-Redemption/tool_shed/actions/runs/34064368612)).
- Provenance commit `9b41ed0bf135a11b39024ec95eb87ce6587d084a` is tagged `v0.50.1`; the
  GitHub Release was published by
  [run 34064662674](https://github.com/PC-Redemption/tool_shed/actions/runs/34064662674).
- Web: a validated encrypted PostgreSQL backup
  `dashboard-daily-20260906T224050Z.dump.age` and filesystem rollback copy
  `release-backups/pre-v0.50.1-20260906T2239Z` preceded promotion. Production is healthy on
  `tool-shed-dashboard:v0.50.1` at image digest
  `sha256:6176c7617322966ba95bf46689c212dd92527cf9d8fb322edfe623ca040d6dd6`; public dashboard and
  documentation health returned HTTP 200.
- The production `tool_shed` inventory contains 267 rows. A direct, unfiltered production render
  selected Remaining/Tree and returned 0 matching items and 0 roots. Representative legacy rows
  `MAP-0002`, `MAP-0004`, `MAP-0006`, and `MAP-0008` occurred zero times in that default response
  and remained present in the All/List response.
- Linux and Windows test beds both completed the official stable updater to `v0.50.1`, with the
  installed provenance bound to frozen content commit `c39480b492070270ba9835a67cae6672d8690a56`.
  Strict snapshot verification and the 54 focused regressions passed on each platform; both parent
  repositories remained clean.

### Final reconciliation

- Automatic dashboard event sequence `10759` delivered in 1.832296 seconds with zero attempts;
  no manual worker or safety pass was used, the local queue returned to zero, and production
  observed client v0.50.1 with the complete 267-row inventory.
- Direct origin cycle `9644e45a-e9e6-42bb-9f77-b5c722a81b9c` is satisfied, terminal, recursively
  closed, and reconciled using production qualification cycle
  `3c84e2a8-9433-4dae-aa73-8ec6722fd0e1`.
- Release cohort `0cac74ca-9a38-4931-a84a-ecc25b6fb849` recorded `v0.50.1` against frozen content
  commit `c39480b492070270ba9835a67cae6672d8690a56` and finalized with its candidate in
  `released-reconciled` disposition.
- GitHub issue #57 was reviewed and updated with the delivered Remaining-view subset; it remains
  open for its broader semantic-fidelity scope.
