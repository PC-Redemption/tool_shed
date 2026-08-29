# Evidence: Tool Shed v0.28.0 maintainer skill synchronization

Status: complete
Type: evidence
Updated: 2026-08-25
Next Action: derive the M3 native Linux installed-use campaign; stop before the Bactron Core snapshot consent gate
Campaign: synchronize-maintainer-skill-and-smoke-v0-28-0

## Deployment

- Released source: `/home/jon/docker/tool_shed/skills/tool-shed`
- Installed target: `/home/jon/.codex/skills/tool-shed`
- Previous installed state: valid unmodified release `v0.27.1`
- Rollback backup: `/home/jon/.codex/skills/tool-shed.backup-20260825T192824Z`
- Source, staged copy, installed target, and rollback backup passed `quick_validate.py` where
  applicable.
- Final `diff -qr` between released source and installed target was empty.
- Final installed state: `current`, compatibility `compatible`, tree SHA-256
  `153d85e90bf827b97f6956404ac95c12d88e966b05a8653eb369095017b4f28e`.

## Fresh-session smoke

An ephemeral read-only Codex task using `gpt-5.6-terra` with low reasoning routed
`ts: appserver status` through the released contract and reported:

- execution default: GUI;
- CAMP route: `gpt-5.6-terra` / medium;
- API fallback: disabled;
- executable: `/home/jon/.local/bin/codex`;
- qualification: exact-qualified with blockers.

The smoke completed successfully with 165,397 input tokens, of which 144,640 were cached, plus 788
output tokens and 263 reasoning-output tokens. The high fresh-task context footprint remains an
explicit optimization concern for later roadmap evidence; it does not invalidate routing or skill
parity.

No Tool Shed snapshot, installed skill, or application state in Bactron Core was changed.
