# Reconcile campaign queue state and execution order

Status: complete
Type: campaign
Updated: 2026-08-14
Next Action: none
Campaign ID: reconcile-campaign-queue-state-and-order
Outcome: Provide a deterministic utility that finds orphaned or stalled campaigns, safely repairs mechanically resolvable queue drift, and evaluates the active queue execution order without overriding owner decisions
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: GitHub feature request 23 remains linked; dry-run and JSON reports identify orphaned, inconsistent, stalled, blocked, and ready campaigns; token-protected apply safely repairs eligible drift with rollback; active execution-order recommendations are stable and explainable; ambiguous lifecycle or priority decisions remain owner-controlled; focused cross-platform tests, documentation, and full validation pass
Completion Evidence: GitHub #23; commit 2450401; dry-run, stale-token, projection-repair, rollback, and order tests; full validator 102/102
Completion Date: 2026-08-14
Completion Order: 2
Disposition: completed

## Request

GitHub feature request: https://github.com/PC-Redemption/tool_shed/issues/23

Build a deterministic campaign-reconciliation utility that inspects
`work/00-campaigns/active-queue.md` together with the `active/`, `completed/`, `deferred/`, and
`abandoned/` lifecycle folders. It must find campaign requests that are absent from the correct
queue or lifecycle view, inconsistent queue entries, and campaigns that meet explicit documented
stall criteria.

The utility should:

- default to read-only inspection and provide structured JSON output;
- classify orphaned, inconsistent, stalled, blocked, ready, and dependency-constrained work;
- distinguish mechanically repairable projection drift from lifecycle decisions requiring owner
  intent;
- propose a stable, explainable active execution order using readiness, dependencies, blockers,
  decisions, detours, and return points;
- use the current state token, recovery journal, and invariant validation for approved updates;
- never silently abandon, defer, complete, unblock, or reprioritize ambiguous work;
- refresh queue and index projections and verify stale paths and work state after applying repairs;
- include cross-platform fixtures and operator documentation for inspect, propose, approve, and
  apply workflows.

Reference GitHub issue #23 in completion evidence.

## Completion Check

GitHub feature request #23 remains linked. Dry-run and JSON reports identify orphaned,
inconsistent, stalled, blocked, ready, and dependency-constrained campaigns. Token-protected apply
safely repairs eligible drift with rollback. Active execution-order recommendations are stable and
explainable; ambiguous lifecycle or priority decisions remain owner-controlled. Focused
cross-platform tests, documentation, and full validation pass.
