# Ticket: Prepare Tool Shed 0.2.0 release

Status: complete
Type: ticket
Updated: 2026-07-24
Next Action: none
Parent: work/maps/map-tool-shed-evolution.md
Canonical Truth: docs/releasing.md; scripts/check_shed_version.py; scripts/update_shed_manifest.py

## Problem

The initial `0.2.0` publication needs future-proof tests, an unambiguous provenance workflow,
secure and structured version-check failures, and warning-free release validation.

## Expected Behavior

The release can be committed and pushed with reproducible provenance and clean validation output.

## Acceptance Criteria

- [x] Tests derive the current version instead of hard-coding `0.2.0`.
- [x] A two-commit release runbook defines content commit and final tag semantics.
- [x] Version checks reject HTTP, validate schemas/timestamps, and report local failures cleanly.
- [x] Validation smoke tests finish with strict reconciliation and no advisory warnings.
- [x] Full validation passes before content and provenance commits.

## Verification

Run `python3 scripts/validate_tool_shed.py`, strict local version and work-state checks, and
`git diff --check`.
