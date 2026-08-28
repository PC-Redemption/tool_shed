# Implement the minimum SQLite operational substrate

Status: complete
Type: campaign
Updated: 2026-08-28
Next Action: none
Campaign ID: implement-minimum-sqlite-operational-substrate
Campaign Number: 104
Outcome: Tool Shed has immutable public IDs, import provenance, typed relationships, revisions/events, evidence references, migration/export/checkpoint ledgers, guarded transactions, DB-enforced dirty accounting, entrance audits, and deterministic portable rebuild without moving excluded domains.
Primary Focus Areas: artifact-workflows
Supporting Focus Areas: workspace-safety, snapshot-delivery, qualification-release
Depends On: establish-hybrid-bootstrap-closure-and-design-contract
Decision: none
Detour For: none
Return To: none
Completion Gate: Focused and full tests prove schema creation and migration, foreign keys, revision/trigger accounting, managed and unmanaged writes, project/worktree lineage, deterministic checkpoint/export, fresh rebuild, corruption detection, backup, interruption recovery, and legacy writer refusal while campaigns, roadmaps, general bodies, and legacy retirement remain file-owned.
Completion Evidence: EVID-G2-SUBSTRATE passed under bootstrap closure token f0f0f772d0c3866b: seven disposable-repository substrate scenarios and installer/docs focus passed 21/21; Tool Shed full profile passed 333/333 tests and all repository, provider, roadmap, and closure contracts; CHG-HYBRID-003 reconciles exact checkpoint/export ledger recovery; the 23-page/73-command site build passed; no live database, authority conversion, deployment, release, skill synchronization, or client mutation occurred. Historical claim audit: work/evidence/evidence-historical-campaign-external-claims-backfill.md
Completion Date: 2026-08-28
Completion Order: 88
Disposition: completed
Roadmap: hybrid-sqlite-operational-state
Roadmap Revision: 1
Milestone: M2-SUBSTRATE-HPT2-PROVEN
Unlocks Gate: none

## Request

Implement only the approved phase-one embedded SQLite substrate and shared managed access layer. Keep the live DB ignored and per-worktree, use standard-library sqlite3, preserve source files, and provide shadow import plus deterministic rebuild. Add focused cross-platform tests and docs. Requested endpoint: work3 local candidate; no live maintainer conversion, release, skill sync, or client upgrade.

## App Server Preparation Contract

```json
{
  "campaign_id": "implement-minimum-sqlite-operational-substrate",
  "completion_evidence": "Focused and full tests prove schema creation and migration, foreign keys, revision/trigger accounting, managed and unmanaged writes, project/worktree lineage, deterministic checkpoint/export, fresh rebuild, corruption detection, backup, interruption recovery, and legacy writer refusal while campaigns, roadmaps, general bodies, and legacy retirement remain file-owned.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "Tool Shed has immutable public IDs, import provenance, typed relationships, revisions/events, evidence references, migration/export/checkpoint ledgers, guarded transactions, DB-enforced dirty accounting, entrance audits, and deterministic portable rebuild without moving excluded domains.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

Focused and full tests prove schema creation and migration, foreign keys, revision/trigger accounting, managed and unmanaged writes, project/worktree lineage, deterministic checkpoint/export, fresh rebuild, corruption detection, backup, interruption recovery, and legacy writer refusal while campaigns, roadmaps, general bodies, and legacy retirement remain file-owned.
