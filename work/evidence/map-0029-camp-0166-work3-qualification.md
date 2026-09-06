# MAP-0029 CAMP-0166 Work3 Qualification

Status: passed
Recorded: 2026-09-06
Campaign: `CAMP-0166` (`enforce-and-qualify-app-server-dispatch-closure`)
Candidate commit: `c4dfe36f871b05dcf192375588cafe18a4f8bd05`
Candidate version: `0.48.0` (unpublished development candidate)
Environment: development only

## Result

The exact candidate passed strict disconnected-snapshot validation, full repository validation on
Linux and Windows, fresh installation on both supported client platforms, and live dispatch-debt
detection and recovery. The development dashboard image was rebuilt from the candidate and both
development health endpoints returned HTTP 200; the production health endpoint was observed as
HTTP 200 without mutation.

Qualification found and corrected one pre-mutation recovery defect before this candidate was
bound: a controlled `selected -> gui_fallback` recovery without an execution attempt remained
classified as dispatch debt. The final candidate recognizes only the explicit
`process_loss_pre_mutation` terminal as the no-attempt exception. A regression test and live Linux
and Windows proofs verify that pending debt blocks strict Doctor and controlled recovery returns
the debt count to zero.

## Exact Development Targets

| Lane | Target and artifact | Result |
| --- | --- | --- |
| Web | `tsrookarocom-dev` on `sup.local`; `tool-shed-dashboard:dev-c4dfe36f871b`; image `sha256:f7ab56d9cbf0b950f6205ea69567ca25b512f824d2d103307f83a0ee96f0a4af` | Development site and dashboard health HTTP 200; production regression health HTTP 200 |
| Linux | `sup:/home/jon/dev/ts_linux_test_bed`; archive `sha256:e78d6374c7cac3cfcf07c402d24d57a19b55e7787f13fe7b19a75ea1d36fc872` | 597/597 tests; fresh Doctor HEALTHY; debt block and recovery PASS |
| Windows | `GOGETTER:E:\dev\ts_windows_test_bed`; same archive | 597/597 tests; fresh Doctor HEALTHY; debt block and recovery PASS |

The archive contains no Git metadata or project `work/` tree. Strict manifest verification passed
before replacement on both platforms. Existing test-bed snapshots were preserved as
`tool_shed.before-map29-09cdde7` on Linux and `tool_shed.before-map29-c4dfe36` on Windows. The
failed pre-fix Linux candidate is retained separately as `tool_shed.failed-map29-09cdde7`.

## Fresh And Upgrade Coverage

- Linux fresh project: `8deacb5c-5e67-42da-a3e4-27b421de6d43`.
- Windows fresh project: `d1088b93-24d3-4718-bc29-534f5f67517b`.
- Both retained existing project identity while converging their upgraded workspaces.
- Both fresh projects produced a HEALTHY strict Doctor result with zero dispatch debt.
- Both synthetic current-schema pending lifecycles produced `APP_SERVER_DISPATCH_DEBT` and a
  nonzero strict Doctor result.
- Both `pre-mutation` recovery operations wrote one `gui_fallback` terminal and reduced the report
  to zero debt without replay.

## Boundary

No production deployment, Git push, tag, GitHub Release, or installed user-level skill
synchronization occurred during Work3 qualification. The published client remains authoritative
until the v0.48.0 release is fully verified.
