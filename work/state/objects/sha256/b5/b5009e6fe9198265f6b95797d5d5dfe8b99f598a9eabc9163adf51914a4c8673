# Consolidate validation profiles and contracts

Status: complete
Type: campaign
Updated: 2026-08-27
Next Action: none
Campaign ID: consolidate-validation-profiles-and-contracts
Campaign Number: 099
Outcome: Tool Shed has non-redundant focused, full, and release validation profiles with measured performance and preserved safety isolation.
Primary Focus Areas: qualification-release
Supporting Focus Areas: none
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: Focused profile passes; full is under 45 seconds; release is under 60 seconds; preserved scenarios and safety contracts pass; CLI and operator documentation describe profile ownership.
Completion Evidence: Focused profile passed in 0.617s; full passed all 314 discovered cases plus manifest, provider, roadmap, stale-path, and work-state contracts in 11.369s; release passed the same cases plus the unique disposable installed-workspace smoke in 12.093s. Failures are isolated per case and reported in stable test-ID order. Historical claim audit: work/evidence/evidence-historical-campaign-external-claims-backfill.md
Completion Date: 2026-08-27
Completion Order: 83
Disposition: completed
Roadmap: validation-consolidation
Roadmap Revision: 2
Milestone: M1-CONSOLIDATED-QUALIFICATION
Unlocks Gate: G1-VALIDATION-EFFICIENT

## Request

Consolidate Tool Shed validation so each behavior and contract is checked once at the lowest useful layer, focused/full/release profiles avoid repeated work, and safety coverage and failure isolation are preserved. Target full validation under 45 seconds and release qualification under 60 seconds; use test count only as a secondary metric. Execute through work1 only—local commit, no push or release.

## App Server Preparation Contract

```json
{
  "campaign_id": "consolidate-validation-profiles-and-contracts",
  "completion_evidence": "Focused profile passes; full is under 45 seconds; release is under 60 seconds; preserved scenarios and safety contracts pass; CLI and operator documentation describe profile ownership.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "Tool Shed has non-redundant focused, full, and release validation profiles with measured performance and preserved safety isolation.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

Focused profile passes; full is under 45 seconds; release is under 60 seconds; preserved scenarios and safety contracts pass; CLI and operator documentation describe profile ownership.
