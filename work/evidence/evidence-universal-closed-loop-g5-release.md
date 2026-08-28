# Universal Closed-Loop G5 Release Evidence

Status: passed
Evidence ID: EVID-CLOSED-G5-RELEASE
Gate: G5-RELEASE-CANARY-PROVEN
Campaign: release-and-canary-universal-closed-loop-reconciliation
Date: 2026-08-28

## Published Release

- Version: `0.35.0`.
- Content commit: `e486943e56310321205fdd940db2b15fa54a97ca`.
- Provenance commit and annotated-tag target: `8c50284f83073991bbd5022f537792ecd14e1c18`.
- Annotated tag: `v0.35.0`.
- Released at: `2026-08-28T21:52:17Z`.
- Exact content push matrix: GitHub run `33214245752`; all Ubuntu/Windows and Python 3.11/3.x
  jobs passed under the unchanged release budget.
- Publication workflow: GitHub run `33214419388`; release integrity, exact-content qualification,
  publication, and published-surface verification passed.
- GitHub Release: `https://github.com/PC-Redemption/tool_shed/releases/tag/v0.35.0`; non-draft,
  non-prerelease, published at `2026-08-28T21:52:53Z`.
- Local and canonical manifest verification both reported current version `0.35.0`, populated
  provenance, verified integrity, and minimum updater protocol 4.

## Maintainer First Upgrade

The canonical source, unique staged skill, and final installed skill all passed `quick_validate.py`.
Pre-deployment review found only the two expected 0.35.0 instruction changes. The exact prior
installed skill is recoverable at
`/home/jon/.codex/skills/tool-shed.backup-20260828T215325Z`. Replacement moved the old target to
that backup and installed the validated stage without merging. Final `diff -qr` was empty.

A fresh read-only Codex task ran `ts: version` after deployment. It reported verified Tool Shed
0.35.0 integrity, exact source/installed skill parity, no `TOOL_SHED_SKILL_MISMATCH`, no file
changes, and `Campaign status: COMPLETE`.

## Verdict

The exact qualified candidate is published on both required surfaces and the canonical maintainer's
first upgrade is validated, recoverable, and exact. `UPG-CLOSED-MAINTAINER` passes.
