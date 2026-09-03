# Evidence: IDEA-0020 M3 Reporter, Hosted, and Browser Truth

Status: passed
Recorded: 2026-09-03
Campaign: CAMP-0152
Program Roadmap: PRM-0038, M3-REPORTER-HOSTED-UI-TRUTH
Candidate commit: `8af4a0c91112fc935b2d6cd1275bb585e8e09f47`
Candidate version: `0.43.0` (unpublished development cohort)
Environment: development only

## Result

The exact candidate passed QH-001 against the shared development dashboard and passed QH-007,
hosted QH-008, and hosted QH-010 from both disposable operating-system fixtures against fresh,
dedicated ephemeral development databases. The evidence covers reporter persistence and ordering,
hosted base rows and projections, and a real Chrome browser's inventory, detail, closure/blocker,
freshness, and link observations.

No source was pushed, no release was published, and no production service, database, fixture, or
installed client was changed.

## Exact Development Targets

| Target | Identity | Installed/served candidate | Result |
| --- | --- | --- | --- |
| Linux fixture | `sup:/home/jon/dev/ts_linux_test_bed`; project `4e6c7752-8ce6-44d1-bf76-dffb18cd8137`; instance `71fa633f-d6e6-4e44-b904-dd52a748bb70` | snapshot `8af4a0c91112`; 268-file manifest | PASS |
| Windows fixture | `GOGETTER:E:\dev\ts_windows_test_bed`; project `10066c9b-e5e3-419f-9ee8-bb47fc029e9c`; instance `4906bbc9-36c3-486a-a247-bb442ea15dba` | snapshot `8af4a0c91112`; 268-file manifest | PASS |
| Development web | compose project `tsrookarocom-dev` on `sup.local` | image `tool-shed-dashboard:dev-8af4a0c`; image ID `sha256:8ef2e7a81d3ea918932edb55ff1ebfd2d794acbc4224235a58d101fa38bd67b9` | healthy |

Rollback snapshots remain at `tool_shed.before-idea0020-8af4a0c` in both disposable fixtures. The
installed personal Codex skill was not synchronized because this Work2 route owns only project
development lanes.

## Qualification Matrix

| Scenario / target | Sealed run | Checks | Result record SHA-256 |
| --- | --- | ---: | --- |
| QH-001 shared hosted development | `tsqh-f7757bdb18d7d6e5f4e0dc4c` | 5 | `85dca4d2b166b3f35858f5d68afada667d4d6bd390aa9b6e5000fe8ba0d6a065` |
| QH-007 Linux | `tsqh-af51214e2ab2379236dc6e2d` | 11 | `a2195e1279a192f73a1247ad74e8ea890198a032e6883127f8f4217c38e18785` |
| QH-007 Windows | `tsqh-6051087e7af825ca63727438` | 11 | `c51a4c49bcf2abeed069cbd1410bc9d25efca1c2ca3add254ee7ced6fa609a2a` |
| QH-008 Linux, local plus hosted | `tsqh-c41d4c2a37968df055249cf7` | 11 | `c91a8ee87360a502567910f6a6bcf6f34d0befa1d9b11cf132c89499be2b84a1` |
| QH-008 Windows, local plus hosted | `tsqh-6efd4ddd217930bd68b960f4` | 11 | `d33a6bfef4d65a9c612a8c8f5fef901e8c350c7b52326f0a1579eff8255799d1` |
| QH-010 Linux, local plus hosted | `tsqh-e7986bae82624a6fca431c1a` | 14 | `258e04d8193fcae8c0a1a02ff8c2d9f59d1191cd8ea77f917f094c067128d93e` |
| QH-010 Windows, local plus hosted | `tsqh-5770662cc735a7b62121fa1a` | 14 | `591274f1d82ce75d81dc054e99bc63311d087f323b7a4d9eb0ad35700fc56eb1` |

The generated manifests, local observations, reporter transport records, hosted exports, browser
captures, and compact results remain below `work/evidence/generated/idea0020-m3/`. The records are
ignored operational data; the hashes above bind the selected PASS evidence.

## Qualified Claims

- QH-001's raw export and authenticated real-browser observation both contain exactly
  `ts_linux_test_bed` and `ts_windows_test_bed`, exactly one unique instance per project, and no
  visible seed or phantom project. The temporary shared-dashboard qualification user was deleted
  after capture.
- Both QH-007 runs retained two monotonically ordered pending reports while transport was
  unavailable. The browser displayed the hosted baseline as stale. Resume accepted the newest
  report, classified its replay as duplicate and the older report as stale, drained the outbox to
  zero, and presented the final report as fresh.
- Hosted exports contain exactly the current reporter artifact set, all compared lifecycle,
  parent/producer, reconciliation, closure, blocker, inventory sequence, digest, count, and receipt
  fields agree, and the browser contains no missing or fabricated work row.
- QH-008 rebuilt checkpoints retain clean domain-digest, independent closure truth, and projection
  parity locally, then reproduce their exact empty operational work inventory and current sequence
  through hosted storage and browser presentation on both platforms.
- QH-010 preserves stable identities and history for sanitized file-owned and Hybrid instances,
  rebuilds recoverable lineage, retains explicit `MISSING_PARENT` ancestry, has zero invisible
  orphans, and presents the exact two file-owned artifacts and their open/blocker state through the
  hosted browser surface on both platforms.
- Each destructive hosted scenario used a freshly created ephemeral PostgreSQL volume. The
  compose project and volume were removed after capture; no qualification identity entered the
  shared operational development inventory.

## Defect Found and Closed

Early local hosted drives inherited the root fixture's global dashboard connection. That allowed
run-owned workspaces to start long-lived reporter workers with the fixture project identity, which
could overwrite the shared project's displayed name and recreate the apparent phantom-project
symptom. The candidate now temporarily rebinds `TOOL_SHED_STATE_ROOT` to a run-owned temporary
directory while driving the local corpus. Final QH-008 and QH-010 local drives created no reporter
outbox and left no nested reporter worker on either operating system. Existing leaked Linux workers
were terminated before the final matrix; the root Linux and Windows reporters remain connected,
credentialed, and drained.

The hosted timestamp comparison also exposed representational drift between equivalent UTC values,
and Windows browser probing exposed an unreliable temporary-profile cleanup. The candidate
canonicalizes hosted closure timestamps and uses bounded, platform-safe browser cleanup. Both
fixes are covered by the final passing matrix.

## Candidate Validation

The frozen candidate was validated from a clean detached worktree:

```text
python scripts/validate_tool_shed.py --profile release
SHED_VERSION.json matches 268 tracked files.
539 of 539 tests passed in 23.733s with 8 workers.
Provider adapter, database view, stale-path, work-state, Program Roadmap, bootstrap-closure,
temporary-workspace, template, and example checks passed.
tool_shed release validation passed in 31.365s.
```

The shared development health endpoint returned the expected healthy development payload after the
final image deployment. The source workspace's unrelated pre-existing edits were excluded from the
detached candidate and are not part of this evidence.

## Boundary and Next Step

This completes `G3-REPORTER-HOSTED-AND-UI-TRUTH` and makes
`M4-DEVELOPMENT-FAULT-NAMESPACE` ready. M4 must add the protected shared-host qualification
namespace before fault injection is allowed in the shared development database. Work3 candidate
freeze, pushing, publication, and Work5 production promotion remain separate explicit routes.
