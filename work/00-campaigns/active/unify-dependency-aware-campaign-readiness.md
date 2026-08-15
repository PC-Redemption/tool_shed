# Unify dependency-aware campaign readiness

Status: queued
Type: campaign
Updated: 2026-08-15
Next Action: execute when selected from the active campaign queue
Campaign ID: unify-dependency-aware-campaign-readiness
Outcome: Owner queue projection, status, and next use one dependency-aware readiness selector while preserving the reconciliation fallback when no queued campaign is ready.
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: Regression tests prove active-queue Markdown, status --json, and next --json agree for dependency-blocked and independently ready queues; stale projections fail validation; focused and full Tool Shed validation pass.
Completion Evidence: none
Disposition: none

## Request

Resolve [GitHub issue #29](https://github.com/PC-Redemption/tool_shed/issues/29).

- Extract one ordered, dependency-aware ready-campaign selector.
- Use it for the active queue Markdown projection, `status --json`, and `next --json`.
- Preserve working-campaign precedence and the reconciliation fallback when no queued campaign is ready.
- Reject stale queue projections whose `Next` value disagrees with dependency-aware readiness.
- Cover both dependency-blocked queues and independent ready campaigns behind blocked work.

## Completion Check

Regression tests prove active-queue Markdown, status --json, and next --json agree for dependency-blocked and independently ready queues; stale projections fail validation; focused and full Tool Shed validation pass.
