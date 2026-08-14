# Active Campaign Queue

Updated: 2026-08-14

## Owner State

- Last completed: complete-portable-verified-installer — Complete Portable Verified Tool Shed Installer
- Working now: none
- Next: none
- Blocker or decision needed: guarded-fleet-snapshot-update — Guarded Fleet Snapshot Update; file-codex-desktop-robustness-issue — File Codex Desktop Robustness Issue; evaluate-workspace-performance-collector — Evaluate Workspace Performance Collector
- Detour and return point: none

## Ordered Queue

1. [Guarded Fleet Snapshot Update](active/guarded-fleet-snapshot-update.md) — state: blocked — outcome: The first explicitly approved Tool Shed fleet snapshot update is applied to the exact target set with boundary, rollback, and post-update verification. — decision: Awaiting explicit approval of the exact fleet target manifest before any snapshot apply.
2. [File Codex Desktop Robustness Issue](active/file-codex-desktop-robustness-issue.md) — state: blocked — outcome: The contained Codex Desktop crash is reported through an approved external channel with a sanitized, reviewed evidence set. — decision: Awaiting operator approval of the external issue destination and exact sanitized evidence to publish.
3. [Evaluate Workspace Performance Collector](active/evaluate-workspace-performance-collector.md) — state: blocked — outcome: Approved longitudinal or multi-workspace measurements determine whether a separate sanitized performance-report collector is justified. — decision: Awaiting approved longitudinal or multi-workspace measurement targets and separate profiling authorization.
