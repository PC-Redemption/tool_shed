# CAMP-0175 Release Identity Work2 Evidence

Status: passed
Recorded: 2026-09-08
Candidate: `43224a84263752407a35cb0d62d38fe781271a7e`
Candidate version: `0.52.0` (unpublished)

## Result

The candidate makes release identity a bounded project policy while keeping strict SemVer as the
no-configuration default. A configured fixed-width policy preserved `v00.05.00` exactly without
modifying the installed snapshot. Finalized-cohort continuity, topology fallback, candidate
reachability, selected-commit ambiguity, malformed policy, and rejection diagnostics passed the
focused suite.

## Verification

- Canonical: 31 focused release-cohort and Work-orchestration tests passed. The release profile
  passed 640/640 tests plus provider, Hybrid-state, roadmap, bootstrap-closure, and temporary
  workspace checks in 38.340 seconds.
- Web development: exact commit `43224a84263752407a35cb0d62d38fe781271a7e` was staged as
  `tool-shed-dashboard:dev-43224a842637` at image
  `sha256:f3262c2e5f47e8dbc03708f571341a76458e310c0f5739d2e7a5e7fe82f37a2e`.
  Every `tsrookarocom-dev` container was healthy; development docs and dashboard health returned
  HTTP 200; production health remained HTTP 200 and no production Compose identity was changed.
- Linux development: the disconnected snapshot at
  `/home/jon/dev/ts_linux_test_bed/tool_shed` verified as exact unpublished `0.52.0`; all 13
  release-cohort tests passed. A project-root fixed-width policy selected and preserved
  `v00.05.00` with zero findings while the snapshot remained integrity-verified.
- Windows development: the same archive was installed at
  `GOGETTER:E:\dev\ts_windows_test_bed\tool_shed`, verified as exact unpublished `0.52.0`, and
  passed all 13 focused tests under Python 3.14.6. The same project policy selected `v00.05.00`
  with zero findings and without changing snapshot bytes.
- Cross-platform snapshot archive:
  `sha256:b135aacd1566298fee371c3d02c94639dade2c77260d9e4a5a7833bb1685c82b`.

The temporary fixed-width policies and synthetic tags were removed from both test-bed project
roots after observation. The exact candidate snapshots and uniquely named rollback directories
remain available. No source push, stable tag, GitHub Release, production deployment, or installed
user-level skill synchronization occurred.

## Boundary

This evidence satisfies the M1 Work2 development gate only. M2 remains independently scoped, and
M3 owns combined release qualification, exact-SHA CI, publication, production verification,
portable-skill alignment, and recursive outcome closure.
