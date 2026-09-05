# PRM-0040 Work3 Qualification Evidence

Status: passed
Recorded: 2026-09-05
Campaign: CAMP-0163
Candidate commit: `6347383f4aee355fb8aa73f72873f0c990b14ede`
Candidate version: `0.47.0` (unpublished development candidate)
Environment: development only

## Result

The exact candidate passed release-profile validation, ran as the isolated development web image,
and passed fresh-install, full lifecycle/hosted convergence, interruption/replay, and structurally
faithful historical-upgrade qualification on the authorized disposable Linux and Windows test
beds. No production target was changed.

## Exact Development Targets

| Lane | Target and artifact | Result |
| --- | --- | --- |
| Web | `tsrookarocom-dev` on `sup.local`; `tool-shed-dashboard:dev-6347383f4aee` | Health and dashboard health HTTP 200; production regression health remained HTTP 200 |
| Linux | `sup:/home/jon/dev/ts_linux_test_bed`; disconnected archive SHA-256 `7d44b0a32bd6d4fd9da2bd7457c8c638ef095ca9c49d217d53f7580279a9aed3` | PASS |
| Windows | `GOGETTER:E:\dev\ts_windows_test_bed`; same disconnected archive | PASS |

Rollback snapshots are retained as `tool_shed.before-prm40-6347383` on both test beds.

## Qualification Matrix

| Scenario | Linux result | Windows result | Checks per platform |
| --- | --- | --- | ---: |
| QH-002 lifecycle and hosted projection | `b312fdeb52610f0bd87ee39a80d8f18b887b08c6616da15bf8f2d0b1bf7259ef` | `6b2f4087a9f0696a08d1c89ce6bdd44288f2f230699b90b79594cf4fba63bebe` | 10 |
| QH-006 interrupted completion and replay | `5f2260f2ea59a669acee3f1651e2969a4eefcea6ba4c848d581d72658357e7b6` | `c325df043ff8068923703e2fb9dc5e9aa67f03af9c9ad6af50a34998738c1af2` | 6 |
| QH-010 historical file/Hybrid upgrade | `d3a091115b6b3d6a7c978c32d157f0072fa941454a29c1ee880744f75104f22f` | `0924a4a800c1319b4459ae788c1bd526484c8aa1813d45a5558b7d32eff2f9db` | 7 |

Each platform also received a new disconnected snapshot in an empty nested Git workspace, ran the
normal installer, checkpointed its generated project state, and returned a `HEALTHY` strict
workspace Doctor result. The fresh Linux project ID was
`9d08b893-d6c0-4b85-8444-5dc9c22d27e9`; the fresh Windows project ID was
`98484656-2eb0-4359-8367-26cc53abbc7f`.

## Recovery Observation

The retained Windows dashboard instance was at report sequence 541 while its disposable local
outbox had been rebuilt at sequence 103. The server correctly rejected stale reports, and a rapid
replay correctly activated HTTP 429 backoff. The fixture outbox was backed up, the exact already
rejected range through sequence 541 was marked historical-stale, and sequence 542 then delivered.
The hosted snapshot contained exactly the four QH-002 artifacts and the independent oracle passed
all hosted identity and terminal-closure checks. This is test-bed reporter history, not a canonical
database defect.

## Candidate Validation

`python scripts/validate_tool_shed.py --profile release` passed in 34.365 seconds: the version
manifest matched 281 tracked content files, all 581 tests passed with eight workers, provider
adapters conformed, database-owned views were current, no stale work paths remained, both bootstrap
closures passed, and the temporary-workspace fresh-install smoke passed.

The 19 reviewed legacy recursive-closure findings in the canonical workspace remain explicitly
retained closure debt. There are zero unexplained document lifecycle/body mismatches.
