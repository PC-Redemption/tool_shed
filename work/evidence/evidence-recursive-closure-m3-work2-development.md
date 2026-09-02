# Recursive Closure M3 Work2 Development Evidence

Status: passed
Date: 2026-09-02
Exact candidate: `d6a90f172dca050fc0d7deb08f2230080560704f`
Branch: `dev/idea-0019-work2`

The exact candidate was deployed only to the three configured development lanes.

## Provisional corpus

- Elements: 25,000
- Edges: 100,000
- Maximum depth: 128
- Independent recursive parity: true
- Summary p95: 0.121 ms (budget 20 ms)
- Mutation-through-ancestry p95: 101.509 ms (budget 250 ms)
- Full rebuild: 10,078.354 ms (budget 60,000 ms)
- First-100-blocker query is included in the committed benchmark and remains under its 50 ms
  provisional budget.

## Hosted development

- Compose project: `tsrookarocom-dev`
- Source/image: `d6a90f172dca050fc0d7deb08f2230080560704f` /
  `tool-shed-dashboard:dev-d6a90f172dca`
- LAN and dashboard health: HTTP 200, development environment
- Fake hostname `ts.rookaro.com-dev`: HTTP 200 from `gogetter.local`
- Django migration `0008_recursive_closure_status` applied.
- Both real test-bed instances were accepted at report schema 7.
- Stored snapshots contain the four closure fields, revisions, counts, reasons, and blockers.
- Authenticated Work rendering returned HTTP 200 and displayed the Closure column and
  `closed-loop · current · valid`.
- Production health remained HTTP 200; production Compose state was not changed.

## Linux development lane

- Host/path: `sup` / `/home/jon/dev/ts_linux_test_bed`
- Disconnected snapshot: exact candidate, no nested Git or snapshot-local `work/`
- Full snapshot validation: 522/522 tests passed
- Schema 2→3 backup verified; controlled child recovery blocked the parent; exact restoration
  reopened the path to effective closure; closure audit CLEAN; schema-3 checkpoint written.
- Reporter schema 7 delivered sequence 101 and reached zero pending events.

## Windows development lane

- Host/path: `GOGETTER` / `E:\dev\ts_windows_test_bed`
- Disconnected snapshot: exact candidate, no nested Git or snapshot-local `work/`
- Full native validation: 522/522 tests passed in 103.543 seconds
- Schema 2→3 backup verified; the same controlled recovery/restore behavior passed; closure audit
  CLEAN; schema-3 checkpoint written.
- Reporter schema 7 delivered through sequence 104 and reached zero pending events.

The previous Linux and Windows snapshots remain in named rollback directories. Work3 candidate
freezing, production migration, publication, and Work5 reconciliation remain intentionally open.
