# Ticket: Portable Verified Tool Shed Installer

Status: active
Type: ticket
Updated: 2026-07-25
Next Action: redesign the useful parts of superseded PR #3 around stable-tag verification
Parent: work/maps/map-tool-shed-evolution.md

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

- [ ] Add Linux and Windows validation jobs without weakening existing checks.
- [ ] Provide POSIX and PowerShell launchers that select an available Python 3
  runtime without changing Tool Shed's Python-version requirements.
- [ ] Select the highest stable `vMAJOR.MINOR.PATCH` tag rather than cloning
  `main`.
- [ ] Verify the tag's two-commit provenance and snapshot content before any
  workspace mutation.
- [ ] Preserve project `work/`, source, docs, `.gitignore`, `AGENTS.md`, and
  unrelated dirty changes.
- [ ] Keep update backups until the operator explicitly removes them.
- [ ] Roll back a failed replacement and report any installer-created residue.
- [ ] Test fresh install, existing update, invalid release, validation failure,
  rollback, Windows paths, spaces, and launcher fallback.
- [ ] Reconcile implementation and documentation with
  `docs/install-or-update-snapshot.md`.

## Verification

Run the complete validator on Linux and Windows, then exercise both launchers
against disposable new-install and existing-update workspaces.

Source context: GitHub PR #3, `agent/improve-tool-shed-install`. Do not copy its
obsolete `0.1.1` version metadata or main-branch installation behavior.
