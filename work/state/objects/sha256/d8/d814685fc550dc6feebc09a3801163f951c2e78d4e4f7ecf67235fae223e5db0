# Ticket: Add Tool Shed operator help

Status: complete
Type: ticket
Updated: 2026-07-24
Next Action: none
Parent: work/maps/map-tool-shed-evolution.md
Canonical Truth: docs/operator-guide.md; skills/tool-shed/SKILL.md; README.md

## Problem

Tool Shed has operator material spread across several files, but no dedicated use-case guide and no
defined behavior for `ts: help`.

## Expected Behavior

`ts: help` returns a concise, read-only menu of Tool Shed use cases and example prompts.
`ts: help <topic>` focuses that help without creating artifacts.

## Acceptance Criteria

- [x] A snapshot-local operator guide covers common use cases and artifact choices.
- [x] The repo-packaged skill defines `ts: help` and focused help behavior.
- [x] README makes operator help discoverable.
- [x] A regression test verifies the guide and routing remain packaged.

## Verification

Run `python3 scripts/validate_tool_shed.py` and inspect the guide against the skill routing rule.
