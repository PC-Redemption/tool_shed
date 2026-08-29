# Deliver the managed document interface and lifecycle views

Status: complete
Type: campaign
Updated: 2026-08-28
Next Action: none
Campaign ID: deliver-managed-document-interface-and-lifecycle-views
Campaign Number: 116
Outcome: Provide the full bounded Codex/operator command surface plus portable disposable active/history projections with concurrency and context-efficiency protection.
Primary Focus Areas: artifact-workflows
Supporting Focus Areas: provider-portability, workspace-safety
Depends On: prove-database-owned-document-thin-slice
Decision: none
Detour For: none
Return To: none
Completion Gate: G3-INTERFACE-VIEWS-PROVEN pass criteria and provider-portable command/view qualification pass.
Completion Evidence: work/evidence/evidence-database-owned-collateral-g3-interface-views.md
Completion Date: 2026-08-28
Completion Order: 100
Disposition: completed
Roadmap: database-owned-work-collateral-and-lifecycle-views
Roadmap Revision: 2
Milestone: M3-INTERFACE-VIEWS-PROVEN
Unlocks Gate: G3-INTERFACE-VIEWS-PROVEN

## Request

Extend the proven thin slice across required commands and lifecycle views; prove stale-edit rejection, deterministic rendering, view rebuild, and bounded context without introducing dual authority.

## App Server Preparation Contract

```json
{
  "campaign_id": "deliver-managed-document-interface-and-lifecycle-views",
  "completion_evidence": "G3-INTERFACE-VIEWS-PROVEN pass criteria and provider-portable command/view qualification pass.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "Provide the full bounded Codex/operator command surface plus portable disposable active/history projections with concurrency and context-efficiency protection.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

G3-INTERFACE-VIEWS-PROVEN pass criteria and provider-portable command/view qualification pass.
