# Evidence: Tool Shed 0.11.0 release and client synchronization

Status: active
Type: evidence
Updated: 2026-08-09
Next Action: run `ts: version` in a fresh Codex task
Parent: work/wp/active/wp-evidence-responsive-tool-shed-execution.md

## Release Identity

- Version: `0.11.0`
- Content commit: `3bd4d003c4df07a2ff6a683e8b7e3c71848453c8`
- Provenance commit: `4390b367df419615105eb194b6cc4a9fd61306aa`
- Annotated tag object: `bf09d58c914210f5589257b7e2add9c2551f4543`
- Tag: `v0.11.0`
- Released at: `2026-08-09T13:01:40Z`

## Publication Verification

- Remote `main` immediately after release publication:
  `016aa8203c76200ed762466569d154313c0a924d`; later work-state commits may advance `main` without
  changing the tagged release identity.
- Remote annotated tag resolves to provenance commit `4390b367df419615105eb194b6cc4a9fd61306aa`.
- Canonical version check: `0.11.0`, relation `current`.
- Local release manifest: verified.

## Client Synchronization

- Canonical source: `/home/jon/docker/tool_shed/skills/tool-shed`
- Installed target: `/home/jon/.codex/skills/tool-shed`
- Backup: `/home/jon/.codex/skills/tool-shed.backup-20260809T130521Z`
- Pre-deployment drift: `SKILL.md` differed.
- Canonical validation: passed.
- Staged validation: passed.
- Installed-target validation after replacement: passed twice.
- Final `diff -qr` canonical versus installed: empty.
- Removed material: the replaced temporary client copy was removed only after the backup existed,
  installed validation passed, and exact parity was confirmed. Recovery remains available from the
  backup above.

## Remaining Verification

The current task loaded skill instructions before deployment. Start a fresh Codex task in
`/home/jon/docker/tool_shed` and run `ts: version`. Close the parent workpackage after it reports
Tool Shed 0.11.0 and the new client loads without error.
