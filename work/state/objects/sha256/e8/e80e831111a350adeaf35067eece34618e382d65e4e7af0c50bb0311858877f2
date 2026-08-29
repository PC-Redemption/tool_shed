# Ticket: Add Tool Shed version status

Status: complete
Type: ticket
Updated: 2026-07-24
Next Action: none
Parent: work/maps/map-tool-shed-evolution.md
Canonical Truth: SHED_VERSION.json; scripts/check_shed_version.py; conventions.md

## Problem

Tool Shed declares a version but does not keep it synchronized, verify snapshot integrity, or let a
disconnected installation determine whether canonical GitHub has a newer version.

## Expected Behavior

The manifest is authoritative and validated. Operators can run a read-only local integrity check or
canonical update check, with Codex routes for both.

## Acceptance Criteria

- [x] Manifest contains semantic version, canonical URL, and shipped-content hashes.
- [x] Local checks distinguish verified from modified or incomplete snapshots.
- [x] Canonical checks distinguish current, older, newer, modified, and check failure.
- [x] `ts: version`, `ts: check for updates`, and `ts: update status` are documented routes.
- [x] Repository validation fails when the manifest is stale.
- [x] Unit tests cover older and modified snapshots without network access.

## Verification

Run `python3 scripts/validate_tool_shed.py` and the focused version-check tests.
