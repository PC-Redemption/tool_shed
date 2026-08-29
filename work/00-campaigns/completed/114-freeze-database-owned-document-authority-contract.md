# Freeze the database-owned document authority and conversion contract

Status: complete
Type: campaign
Updated: 2026-08-28
Next Action: none
Campaign ID: freeze-database-owned-document-authority-contract
Campaign Number: 114
Outcome: Settle and validate every document class, identity, schema, command, projection, checkpoint, compatibility, migration, rollback, retirement, and closed-loop boundary.
Primary Focus Areas: artifact-workflows
Supporting Focus Areas: workspace-safety, snapshot-delivery
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: G1-CONTRACT-DESIGN-FROZEN pass criteria are evidenced and the outcome loop records any approved scope changes.
Completion Evidence: work/evidence/evidence-database-owned-collateral-g1-contract.md
Completion Date: 2026-08-28
Completion Order: 98
Disposition: completed
Roadmap: database-owned-work-collateral-and-lifecycle-views
Roadmap Revision: 2
Milestone: M1-CONTRACT-DESIGN-FROZEN
Unlocks Gate: G1-CONTRACT-DESIGN-FROZEN

## Request

Write the versioned authority/conversion contract, decision records, schemas, fixtures, and validators; preserve all unresolved choices explicitly and do not implement broad corpus conversion.

## App Server Preparation Contract

```json
{
  "campaign_id": "freeze-database-owned-document-authority-contract",
  "completion_evidence": "G1-CONTRACT-DESIGN-FROZEN pass criteria are evidenced and the outcome loop records any approved scope changes.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "Settle and validate every document class, identity, schema, command, projection, checkpoint, compatibility, migration, rollback, retirement, and closed-loop boundary.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

G1-CONTRACT-DESIGN-FROZEN pass criteria are evidenced and the outcome loop records any approved scope changes.
