# Converge upgrades to current work structure

Status: complete
Type: campaign
Updated: 2026-08-14
Next Action: none
Campaign ID: converge-upgrades-to-current-work-structure
Outcome: Make Tool Shed upgrades from older releases migrate preserved owner work into the complete latest canonical work tree instead of leaving a hybrid installation
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: Upgrade fixtures from 0.13.0 and other supported older structures converge to the latest canonical work topology; owner content and indexes are preserved; legacy paths are migrated without collisions or silent loss; provider guidance and snapshot integrity remain valid; rollback is verified; focused cross-platform tests and full validation pass
Completion Evidence: GitHub #25; commit 2450401; protocol-3 Windows-path convergence and rollback tests; full validator 102/102
Completion Date: 2026-08-14
Completion Order: 3
Disposition: completed

## Request

An upgrade of the Windows workspace `E:\\dev\\bactron-core` reported success from Tool Shed 0.13.0
to 0.14.1, verified release tag `v0.14.1`, provenance, snapshot integrity, preserved `work/` and
indexes, refreshed `AGENTS.md`, and reconciled work state. Despite those successful checks, the
workspace retained a hybrid old/new `work/` layout instead of fully conforming to the latest Tool
Shed structure.

The upgrade also produced a verified rollback archive and left a safe-to-remove temporary release
checkout after the safety layer refused automatic deletion. Treat that cleanup message as observed
upgrade evidence, but keep the campaign focused on structural convergence and preservation.

Implement a full upgrade migration that:

- derives the required target topology from the installed release rather than the source
  workspace's older layout;
- migrates supported legacy `work/` paths into the current canonical structure without overwriting
  collisions or losing owner-authored content;
- regenerates and validates queue, Markdown index, and JSON index projections after migration;
- distinguishes preserved owner content from obsolete generated structure;
- remains transactional and recoverable through the verified rollback archive;
- verifies Windows path handling and cross-platform behavior using older-release fixtures;
- reports structural convergence explicitly instead of declaring success from snapshot integrity
  and stale-path checks alone.

Document the defect and acceptance criteria in the GitHub repository, and reference the resulting
issue in the campaign completion evidence.

## Completion Check

Upgrade fixtures from 0.13.0 and other supported older structures converge to the latest canonical
`work/` topology. Owner content and indexes are preserved; legacy paths migrate without collisions
or silent loss; provider guidance and snapshot integrity remain valid; rollback is verified;
focused Windows and cross-platform tests and full validation pass; completion evidence references
the GitHub issue documenting the defect.
