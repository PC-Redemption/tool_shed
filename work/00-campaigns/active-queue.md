# Active Campaign Queue

Updated: 2026-08-15

## Owner State

- Last completed: evaluate-workspace-performance-collector — Evaluate Workspace Performance Collector
- Working now: none
- Next: unify-dependency-aware-campaign-readiness — Unify dependency-aware campaign readiness
- Blocker or decision needed: none
- Detour and return point: none

## Ordered Queue

1. [Unify dependency-aware campaign readiness](active/unify-dependency-aware-campaign-readiness.md) — state: queued — outcome: Owner queue projection, status, and next use one dependency-aware readiness selector while preserving the reconciliation fallback when no queued campaign is ready.
2. [Discover focus areas and render readiness cards](active/discover-focus-areas-and-render-readiness-cards.md) — state: queued — outcome: Tool Shed supports owner-approved, evidence-derived focus-area catalogs and renders deterministic, human-scannable campaign readiness cards using shared dependency-aware semantics. — depends: unify-dependency-aware-campaign-readiness
