# Implement the generic outcome-reconciliation engine

Status: complete
Type: campaign
Updated: 2026-08-28
Next Action: none
Campaign ID: implement-generic-outcome-reconciliation-engine
Campaign Number: 110
Outcome: One guarded entry-point-neutral engine manages exact reconciliation manifests and reports for all durable Tool Shed origin classes while preserving HPT2 compatibility.
Primary Focus Areas: artifact-workflows
Supporting Focus Areas: campaign-lifecycle, workspace-safety
Depends On: freeze-universal-closed-loop-contract-and-bootstrap
Decision: none
Detour For: none
Return To: none
Completion Gate: Generic audit, prepare, validate, apply, report, as-of, backfill-plan, and guarded backfill-apply pass entry-class, ambiguity, concurrency, identity, graph, evidence, compatibility, and checkpoint-rebuild tests; G2 passes.
Completion Evidence: G2 satisfied at bootstrap token 859df913fa6d0036; 25/25 focused and 362/362 full tests passed; all 15 origin classes, exact CLI routes, stale/token/identity/graph/evidence/ambiguity refusals, as-of reporting, historical overlay, checkpoint rebuild, zero-finding live audit, HPT2 parity, and efficiency qualification passed. Evidence: work/evidence/evidence-universal-closed-loop-g2-engine.md.
Completion Date: 2026-08-28
Completion Order: 94
Disposition: completed
Roadmap: universal-closed-loop-outcome-reconciliation
Roadmap Revision: 1
Milestone: M2-GENERIC-ENGINE-PROVEN
Unlocks Gate: G2-GENERIC-ENGINE-PROVEN

## Request

Generalize the existing HPT2 consumer using schema-version-1 hybrid state. Add the smallest complete generic command surface and deterministic tests; do not yet change campaign or roadmap lifecycle semantics. Requested endpoint: work3 local candidate.

## App Server Preparation Contract

```json
{
  "campaign_id": "implement-generic-outcome-reconciliation-engine",
  "completion_evidence": "Generic audit, prepare, validate, apply, report, as-of, backfill-plan, and guarded backfill-apply pass entry-class, ambiguity, concurrency, identity, graph, evidence, compatibility, and checkpoint-rebuild tests; G2 passes.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "One guarded entry-point-neutral engine manages exact reconciliation manifests and reports for all durable Tool Shed origin classes while preserving HPT2 compatibility.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

Generic audit, prepare, validate, apply, report, as-of, backfill-plan, and guarded backfill-apply pass entry-class, ambiguity, concurrency, identity, graph, evidence, compatibility, and checkpoint-rebuild tests; G2 passes.
