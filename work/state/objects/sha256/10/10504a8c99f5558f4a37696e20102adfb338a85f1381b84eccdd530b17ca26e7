# Checklist: Refresh README and AI command reference

Status: complete
Type: checklist
Updated: 2026-08-14
Next Action: none
Parent: work/maps/map-tool-shed-evolution.md

## Goal

Give operators one complete, canonical Markdown reference for Tool Shed prompts used with an AI
agent, make the help route expose it, and correct documentation that drifted after the owner
campaign queue and ordered Q&A inbox shipped.

## Checklist

- [x] Add `docs/commands.md` with every defined `ts:` route, aliases, usage, and authority boundary.
- [x] Route `ts: commands`, `ts: help all`, and command-specific help to the reference.
- [x] Update the README project tree, active-state boundary, Quick Start, and documentation links.
- [x] Resolve the operator-guide ambiguity between preview-only campaign conversion and installer
      filesystem migration.
- [x] Add focused tests that require the command reference to stay packaged and routed.
- [x] Refresh the version manifest and run the full repository validator.

## Runtime Closeout

Not applicable: this checklist changes documentation, the portable skill, and release metadata; it
does not change a service or scheduler. The requested work5 release and client synchronization are
execution stages tracked by the active Tool Shed plan rather than checklist deliverables.

## Verification

- Focused operator-help packaging test passes.
- `python3 scripts/validate_tool_shed.py` passes for the complete content candidate.
