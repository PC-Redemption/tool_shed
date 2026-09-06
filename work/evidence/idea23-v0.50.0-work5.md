# IDEA-0023 v0.50.0 Work5 Evidence

Status: in progress
Recorded: 2026-09-06
Release lane: `idea23-v0.50.0`
Work2 implementation: `f304e230881a9ad23342aa0338d4b2967df8b2fe`
Development candidate: `92cf9167848f7f3459690e76ccdb1c6c050d11c3`

## Development Qualification

- Canonical release profile: 620/620 isolated tests passed with eight workers; provider adapter,
  database-owned view, stale-path, work-state, roadmap, bootstrap-closure, fresh-install, template,
  and example checks all passed in 36.999 seconds.
- Web: exact candidate image `tool-shed-dashboard:dev-92cf9167848f`, image digest
  `sha256:9cbec160d0af1bb1ebf40a3b2820fde8ef7973bed9e7687ce1e1247792c932b3`.
  Development docs and dashboard health returned HTTP 200, an authenticated render exercised the
  new Work controls, and the production regression health endpoint remained HTTP 200.
- Linux: the disconnected candidate archive has SHA-256
  `cd4939586fdbbc73794e8b7da5ae0875bb94d04a8744ebd99eb7d91f4dd7a2a1`; 83 targeted tests,
  strict snapshot integrity, and strict Doctor passed in `/home/jon/dev/ts_linux_test_bed`.
- Windows: the identical archive passed the same 83 targeted tests, strict snapshot integrity, and
  strict Doctor under Python 3.14 in `E:\\dev\\ts_windows_test_bed` on `GOGETTER`.
- Both disposable parent repositories remained clean. Recoverable prior snapshots are retained as
  ignored `tool_shed.backup-idea23-92cf916.tar` directories.

## Remaining Work5 Proof

Freeze the final content descendant, pass exact-SHA CI, publish v0.50.0, deploy the production web
lane, verify stable Linux and Windows client installation behavior, force a fresh production
report, prove immediate dashboard hierarchy convergence, review GitHub issues, and reconcile the
registered outcome chain.
