# Ticket: Portable Verified Tool Shed Installer

Status: complete
Type: ticket
Updated: 2026-08-14
Next Action: none
Parent: work/maps/map-tool-shed-evolution.md
Campaign: complete-portable-verified-installer

## Problem

Superseded GitHub PR #3 proposed a cross-platform installer, PowerShell and POSIX
launchers, rollback tests, and a Windows/Linux CI matrix. Those capabilities are
useful, but the proposed installer clones `main` rather than selecting a stable
semantic-version tag and verifying Tool Shed's two-commit release provenance.
Merging it as written would weaken the guarded installation model now documented
in `docs/install-or-update-snapshot.md`.

## Expected Behavior

Provide a supported cross-platform installer and CI coverage that preserve the
canonical stable-tag selection, provenance verification, disconnected-snapshot
boundary, project `work/`, repository policy, and recoverable update behavior.

## Acceptance Criteria

- [x] Add Linux and Windows validation jobs without weakening existing checks.
- [x] Provide POSIX and PowerShell launchers that select an available Python 3
  runtime without changing Tool Shed's Python-version requirements.
- [x] Select the highest stable `vMAJOR.MINOR.PATCH` tag rather than cloning
  `main`.
- [x] Verify the tag's two-commit provenance and snapshot content before any
  workspace mutation.
- [x] Preserve project `work/`, source, docs, `.gitignore`, `AGENTS.md`, and
  unrelated dirty changes.
- [x] Keep update backups until the operator explicitly removes them.
- [x] Roll back a failed replacement and report any installer-created residue.
- [x] Test fresh install, existing update, invalid release, validation failure, and rollback.
- [x] Test Windows and Linux validation, Windows paths, spaces, and both native launcher smokes.
- [x] Exercise launcher runtime fallback—not only `--help`—against disposable Windows and Linux
  workspaces.
- [x] Reconcile implementation and documentation with
  `docs/install-or-update-snapshot.md`.

## Verification

Run the complete validator on Linux and Windows, then exercise both launchers
against disposable new-install and existing-update workspaces.

The v0.12.1 qualification passed GitHub Actions on Windows and Ubuntu with Python 3.11 and current
Python 3.x, and a real v0.10.3 embedded updater upgraded a disposable workspace to live v0.12.1.
See `work/evidence/evidence-windows-nonprivileged-snapshot-upgrade.md`.

On 2026-08-14, the new native-launcher fallback test passed locally on Linux for both a disposable
new installation and an existing update with `python3` removed from `PATH`. The complete Linux
validator passed all 107 tests. The same test selects the PowerShell launcher and removes `py` from
`PATH` on Windows; its native Windows result remains pending an authorized push and GitHub Actions
run. Draft PR #27 then passed all eight push and pull-request matrix jobs at commit `8c6d373`,
including native Windows 3.11 and current Python fallback execution in both installation modes.

Source context: GitHub PR #3, `agent/improve-tool-shed-install`. Do not copy its
obsolete `0.1.1` version metadata or main-branch installation behavior.
