# Qualify universal reconciliation backfill and recovery

Status: working
Type: campaign
Updated: 2026-08-28
Next Action: execute the campaign completion gate
Campaign ID: qualify-universal-reconciliation-backfill-and-recovery
Campaign Number: 112
Outcome: The universal loop survives historical ambiguity, migration, direct writes, backup, rollback, deterministic rebuild, scale, and cross-platform release qualification without data loss.
Primary Focus Areas: workspace-safety
Supporting Focus Areas: artifact-workflows, campaign-lifecycle, qualification-release, snapshot-delivery
Depends On: integrate-closed-loop-owning-state-across-tool-shed
Decision: none
Detour For: none
Return To: none
Completion Gate: Disposable and maintainer qualification, exact backup/rebuild/rollback, ambiguity refusal, direct-SQL reconciliation, context-efficiency, soak, full local validation, and the exact push CI matrix pass; G4 passes.
Completion Evidence: none
Disposition: none
Roadmap: universal-closed-loop-outcome-reconciliation
Roadmap Revision: 1
Milestone: M4-RECOVERY-BACKFILL-PROVEN
Unlocks Gate: G4-RECOVERY-BACKFILL-PROVEN

## Request

Run the bounded migration, backfill, recovery, efficiency, and cross-platform qualification suite; repair observed defects and reconcile every material change. Requested endpoint: work4 frozen and pushed candidate; do not publish yet.

## App Server Preparation Contract

```json
{
  "campaign_id": "qualify-universal-reconciliation-backfill-and-recovery",
  "completion_evidence": "Disposable and maintainer qualification, exact backup/rebuild/rollback, ambiguity refusal, direct-SQL reconciliation, context-efficiency, soak, full local validation, and the exact push CI matrix pass; G4 passes.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "The universal loop survives historical ambiguity, migration, direct writes, backup, rollback, deterministic rebuild, scale, and cross-platform release qualification without data loss.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

Disposable and maintainer qualification, exact backup/rebuild/rollback, ambiguity refusal, direct-SQL reconciliation, context-efficiency, soak, full local validation, and the exact push CI matrix pass; G4 passes.
