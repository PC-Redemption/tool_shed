# Evidence: Tool Shed v0.34.0 release and maintainer-skill synchronization

Status: complete
Type: evidence
Updated: 2026-08-28
Campaign: publish-hybrid-state-release-and-sync-maintainer-skill

## Verified release

- Version: `0.34.0`.
- Content commit: `eb283ef7884e85d42a1539725b90bb60986038e5`.
- Provenance commit and annotated tag target: `7924ba0c74764189d8cedd63e223cbc0e4530551`.
- Annotated tag: `v0.34.0`.
- Released at: `2026-08-28T19:00:32Z`.
- Exact candidate CI: `https://github.com/PC-Redemption/tool_shed/actions/runs/33201776422`;
  all 28 Ubuntu and Windows jobs passed on Python 3.11 and current Python.
- Publication workflow: `https://github.com/PC-Redemption/tool_shed/actions/runs/33201934694`;
  the publish job passed.
- GitHub Release: `https://github.com/PC-Redemption/tool_shed/releases/tag/v0.34.0`;
  non-draft and non-prerelease.
- Local and canonical version verification reported current Tool Shed `0.34.0`, populated release
  provenance, and minimum updater protocol 4.

## Candidate corrections retained in the closed loop

Three failed exact-candidate runs were preserved as release evidence rather than waived. Their
findings were reconciled as `CHG-HYBRID-009` through `CHG-HYBRID-011`: checkout-portable bootstrap
tokens, Windows-safe SQLite durability and containment, canonicalized hybrid API roots, stable
terminal-event idempotency, and Windows-safe fixture cleanup. The final local release profile
passed 351/351 tests, the bootstrap staged-release gate was ready, Hybrid SQLite state was CLEAN,
and file/SQLite reconciliation parity was exact before the successful candidate push.

## Installed maintainer skill

- Canonical source: `/home/jon/docker/tool_shed/skills/tool-shed`.
- Installed target: `/home/jon/.codex/skills/tool-shed`.
- Rollback backup: `/home/jon/.codex/skills/tool-shed.backup-20260828T190205Z`.
- Canonical source, staged copy, and installed target passed `quick_validate.py`.
- Reviewed pre-deployment drift and final `diff -qr` were empty.
- Replacement used a unique validated stage and moved the exact prior installed directory to the
  rollback backup; no merge could retain removed canonical files.

## Fresh-session smoke

A fresh ephemeral Codex task ran read-only `ts: version`. It reported Tool Shed `0.34.0`, verified
integrity, updater protocol 4 compatibility, exact installed-skill parity, no
`TOOL_SHED_SKILL_MISMATCH`, and `Campaign status: COMPLETE`. It made no file, campaign, publication,
synchronization, or client-upgrade mutation.

## Result

The release and maintainer-skill portion of `G4-RELEASE-CANARY-PROVEN` passes. The separately
scoped disconnected-client canary remains pending and is not claimed by this evidence.
