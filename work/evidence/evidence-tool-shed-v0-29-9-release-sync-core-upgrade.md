# Evidence: Tool Shed v0.29.9 release, maintainer sync, and Core upgrade

Status: complete
Type: evidence
Updated: 2026-08-26
Next Action: use the released one-command App Server path for the next appropriate Core campaign
Campaign: publish-synchronize-and-upgrade-app-server-repair

## Release identity

- Version: `0.29.9`.
- Content commit: `5d00db4141d116162b78eb5316114ee145289922`.
- Provenance commit: `82cd238b47190bf11b6668a4e4ae12f080f5ac2d`.
- Annotated tag: `v0.29.9`.
- Released at: `2026-08-26T11:03:41Z`.
- GitHub Release: `https://github.com/PC-Redemption/tool_shed/releases/tag/v0.29.9`, published as
  a non-draft, non-prerelease release.
- Release workflow: `https://github.com/PC-Redemption/tool_shed/actions/runs/32961537596`, completed
  successfully against the provenance commit.
- The local and live canonical manifests both reported verified version `0.29.9`, content commit
  `5d00db4141d116162b78eb5316114ee145289922`, and version relation `current`.

## Qualification

- The frozen unpublished candidate passed the complete validator: 276 tests plus manifest,
  provider-conformance, index, stale-path, work-state, roadmap, disposable-workspace, template,
  and example checks.
- The provenance-populated candidate passed the same complete validator again: 276 tests and all
  accompanying checks.
- Publication followed the documented two-commit model. The tag points to the provenance-only
  commit, whose parent is the declared content commit.
- The separate general Validate workflow exposed one test-fixture-only portability defect after
  publication: the automatic-preparation size assertion hard-coded the LF byte count while Windows
  checked out the fixture with CRLF. The closeout change derives the expected size from the fixture
  bytes. The failure did not exercise or invalidate the released dispatcher, Core upgrade, or real
  Windows verifier proof.

## Maintainer Linux skill

- Canonical, staged, and installed skill trees passed the system `quick_validate.py` check.
- Rollback backup:
  `/home/jon/.codex/skills/tool-shed.backup-20260826T110744Z`.
- Installed target: `/home/jon/.codex/skills/tool-shed`.
- `diff -qr` between the canonical and installed skill trees was empty after replacement.
- The skill payload was unchanged from v0.29.8, so no nested Codex smoke was used merely to reload
  identical instructions; the next fresh Codex task will load the synchronized tree normally.

## Core Windows snapshot upgrade

- Workspace: `E:\dev\bactron-core`.
- Source and target versions: `0.29.8` to `0.29.9`.
- Released updater mode: `attested-focused-smoke`, selected from the exact official attestation.
- Transaction: `bfa8c8cd4de07d696f5f6e63`.
- Verified rollback archive:
  `E:\dev\bactron-core\tool_shed.backup-20260826T110939Z.tar`.
- Backup pruning was disabled. No verified or unknown workspace or skill backups were removed.
- The updater installed eight changed Tool Shed paths, preserved excluded paths and owner work,
  required no campaign convergence, and reported `work_changed: false`, `git_status_changed:
  false`, and `work_preserved: true`.
- The Windows installed skill was already current and safe, so synchronization made no replacement;
  its tree SHA-256 remained the release-catalog identity
  `e91b452355f48a6fbdc34c0382bbc2f5ae0cd8abc31e73d2cd3325216333635e`.
- Post-upgrade checks reported verified local and canonical `0.29.9`, a valid empty campaign queue,
  a valid program roadmap, no stale paths, reconciled work state, and a clean Core worktree at
  `8db9cda83f898dff28add5b6fa21ca239ceebed3`.
- Doctor reported zero errors and verified internal consistency. Its `DEGRADED` verdict consists
  only of the pre-existing binary-evidence warning and four historical external-evidence notices;
  neither finding was introduced by this upgrade.
- The exact temporary v0.29.9 staging checkout was removed after verification. An unintended
  disposable clone created by an initial PowerShell quoting error was also identified by its exact
  release commit and removed before the real update. Core was not touched by that failed staging
  command.

## Boundaries honored

Campaign 013 was not replayed. No Bactron application, production system, hardware, PID behavior,
or API fallback was changed or deployed.
