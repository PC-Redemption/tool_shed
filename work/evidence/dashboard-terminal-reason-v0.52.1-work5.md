# Dashboard Terminal-Reason Compatibility v0.52.1 Work5 Evidence

Status: development-qualified
Recorded: 2026-09-08
Bound candidate: `b850efb600c3188aecfbaa55dee367265636d0da`
Planned release: `v0.52.1`

## Observed Failure

The enrolled `tool_shed` reporter remained connected but became stale after schema 11 began
projecting terminal campaign reasons. Its protected local outbox reached 69 pending events. The
production endpoint accepted schema 11 after the v0.52.0 web promotion, but rejected ordinary work
artifacts whose reporter payload supplied an empty `terminal_reason`; the contract accepted only
`null` or a non-empty bounded reason. The pre-upgrade persistent worker reached 18 retries and was
stopped after its exact process root and command were verified.

## Fix And Regression Coverage

- The reporter now emits `null` when an artifact has no terminal reconciliation reason.
- The hosted contract normalizes the already-shipped empty-string representation to `null`, so
  queued schema-11 events can drain without direct outbox rewriting.
- A reporter regression test proves an unreconciled artifact projects `null`.
- A hosted-contract regression test proves an empty legacy value normalizes to `null`, while the
  existing non-empty terminal-reason ingestion and rendering check remains intact.
- Focused dashboard, reporter, and campaign-execution suites passed.
- The canonical release profile passed 646/646 tests through the scripted Work2 preparation gate.

## Development Qualification

- Web: exact commit `b850efb600c3188aecfbaa55dee367265636d0da` was staged and deployed
  to isolated compose project `tsrookarocom-dev` as
  `tool-shed-dashboard:dev-b850efb600c3`. Dashboard readiness passed, development docs and
  dashboard health returned HTTP 200, and production health remained unchanged. Image ID:
  `sha256:3d90212f905fe4e92ceda083b517c71d3a013183c60dd14d061e9186968c1760`.
- Linux: the sanitized disconnected snapshot verified as exact unpublished v0.52.1 and passed the
  complete 646-test release profile in 32.035 seconds.
- Windows: the same snapshot verified as exact unpublished v0.52.1 under Python 3.14.6 and Django
  5.2.17, then passed the complete 646-test release profile in 134.585 seconds. The advisory
  60-second threshold was recorded; the run remained within the enforced 300-second ceiling.
- Sanitized snapshot SHA-256:
  `b40dd2553ba9642670a5103476e2fc20e75e8d64c41068fe67a1e002e04170bd`.

## Remaining Work5 Gates

Bind and verify all development lanes, freeze the final tracked content commit, pass the exact-SHA
GitHub validation matrix, publish v0.52.1, promote all production lanes, verify the dashboard
outbox drains and the hosted instance is current, then reconcile and finalize the owning release
outcome.
