# Evidence: Tool Shed v0.29.1 release and installed-skill synchronization

Status: complete
Type: evidence
Updated: 2026-08-25
Next Action: return to Campaign 059 for the authorized Bactron Core Windows proof
Campaign: publish-and-synchronize-direct-app-server-dispatch-v0-29-1

## Release recovery

- The first immutable tag, `v0.29.0`, reached GitHub but its release workflow failed before
  creating a GitHub Release. Clean Python 3.14 test discovery exposed a test-only import that had
  depended on the maintainer shell's `PYTHONPATH`.
- The tag was preserved and not moved or reused. Campaign 061 was abandoned as an incomplete
  release attempt and replaced by Campaign 062.
- The focused dispatcher test passed after adding an explicit repository scripts path: 3 tests in
  0.041 seconds without a custom `PYTHONPATH`.

## Verified v0.29.1 publication

- Version: `0.29.1`.
- Content commit: `e321711830a3b36ccab995d8e61280713583d8c3`.
- Provenance commit: `92b0fcfc649f03f41f0da0655f2443db49830a42`.
- Annotated tag: `v0.29.1`.
- Released at: `2026-08-25T21:02:58Z`.
- GitHub Release: `https://github.com/PC-Redemption/tool_shed/releases/tag/v0.29.1`.
- Release workflow: `https://github.com/PC-Redemption/tool_shed/actions/runs/32898989930`, passed
  release integrity, metadata preparation, publication, and published-release verification.
- Local and canonical version checks both reported `0.29.1`, verified, and current.
- Both the pre-content and post-provenance full validators passed without a custom `PYTHONPATH`:
  264 tests plus provider conformance, work-state checks, roadmap validation, and disposable smoke.

## Installed Codex skill

- Canonical and staged skills passed the system skill validator before replacement.
- Rollback backup:
  `/home/jon/.codex/skills/tool-shed.backup-20260825T210650Z`.
- Installed target: `/home/jon/.codex/skills/tool-shed`.
- The installed target passed the system validator and `diff -qr` against the canonical
  `skills/tool-shed` source was empty.
- A fresh ephemeral read-only Codex task activated the Tool Shed version route and reported
  `0.29.1` with verified integrity. The smoke used `gpt-5.6-luna` / low, changed no files, and
  consumed 77,754 input tokens (63,488 cached), 366 output tokens, and 95 reasoning-output tokens.
  This one-time client-load smoke did not wrap App Server campaign execution.

## Result

The direct App Server dispatcher is now a verified stable release and the maintained host's
installed Codex skill is exactly synchronized with it. The preserved `v0.29.0` tag is explicitly
not a completed release; `v0.29.1` is the current supported version for installation and the
Windows proof.
