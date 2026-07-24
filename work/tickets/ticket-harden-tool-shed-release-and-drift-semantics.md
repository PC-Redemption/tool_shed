# Ticket: Harden Tool Shed release and drift semantics

Status: complete
Type: ticket
Updated: 2026-07-24
Next Action: none
Parent: work/wp/completed/wp-work-artifact-reconciliation.md
Canonical Truth: scripts/check_shed_version.py; scripts/update_shed_manifest.py; scripts/review_work_state.py

## Problem

Equal version strings can hide different canonical manifests, release hashes can be rewritten
without an intentional bump, provenance is absent, and plan drift treats historical links as
active dependencies.

## Expected Behavior

Version and reconciliation checks distinguish release mistakes from legitimate history, while
release manifests preserve verifiable provenance.

## Acceptance Criteria

- [x] Equal versions with different content report `release-mismatch`.
- [x] Writes require a valid greater semantic version unless explicitly rebuilding unpublished work.
- [x] Manifest schema includes release tag, content commit, and release timestamp.
- [x] Version status reports local and canonical provenance.
- [x] Plan drift only inspects planning-bearing fields and sections.
- [x] Focused and full validation cover the new behavior.

## Verification

Run the version, manifest, and reconciliation unit tests plus `python3 scripts/validate_tool_shed.py`.
