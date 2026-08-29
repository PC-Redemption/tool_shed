# Windows non-privileged snapshot upgrade qualification

Status: complete
Type: evidence
Updated: 2026-08-09
Next Action: none
Parent: work/tickets/ticket-portable-verified-tool-shed-installer.md

Release: v0.12.1
Issue: release validation failed before mutation when Windows denied test symlink creation with error 1314

## Outcome

Passed. The two symlink-security fixtures now skip when the symlink API is absent or Windows
reports error 1314. Other symlink errors remain failures, and capable Windows or Unix hosts still
execute the real symlink rejection assertions.

## Evidence

- A mocked regression reproduces Windows error 1314 and proves the helper raises `SkipTest`.
- The same regression proves an unrelated Windows-style symlink error is re-raised.
- All 72 local tests and the complete Tool Shed validator passed.
- Qualification-branch GitHub Actions run `31318547083` passed on Ubuntu and Windows with Python
  3.11 and current Python 3.x.
- Published-main GitHub Actions run `31318673229` passed the same four-job matrix, including both
  Windows PowerShell launcher smokes.
- A disposable workspace containing the actual tagged `v0.10.3` snapshot ran its embedded updater
  against GitHub, selected live `v0.12.1`, installed and verified content commit
  `71d590ded78311d1f487ddbcc8908c3fc3d1dee9`, retained the update backup, and preserved root
  `work/` byte-for-byte.

Hosted Windows runners may have symlink privilege, so the mocked error-1314 regression is the
deterministic coverage for the non-privileged path. The real security assertions continue to run
where symlinks can be created.

## Release Provenance

- Content commit: `71d590ded78311d1f487ddbcc8908c3fc3d1dee9`
- Provenance commit and annotated tag target: `10f2235efe86892b3fe570dacb6c49435011927f`
- GitHub release: `https://github.com/PC-Redemption/tool_shed/releases/tag/v0.12.1`
- Live canonical manifest: `0.12.1`, exact local match, verified integrity
