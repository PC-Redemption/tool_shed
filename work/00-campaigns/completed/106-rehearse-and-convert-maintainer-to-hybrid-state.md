# Rehearse and convert the maintainer to hybrid state

Status: complete
Type: campaign
Updated: 2026-08-28
Next Action: none
Campaign ID: rehearse-and-convert-maintainer-to-hybrid-state
Campaign Number: 106
Outcome: The disposable rehearsal and canonical live maintainer conversion prove exact no-data-loss migration, recovery, direct-SQL reconciliation, bootstrap closure, and stable hybrid operation while retaining every original file.
Primary Focus Areas: workspace-safety
Supporting Focus Areas: artifact-workflows, snapshot-delivery, qualification-release
Depends On: implement-and-qualify-hpt2-closed-loop-vertical-slice
Decision: none
Detour For: none
Return To: none
Completion Gate: An assigned-ID manifest and external archive cover tracked, ignored, and untracked conversion state; disposable rehearsals are deterministic; the live shadow import, parity, rebuild, backup, reverse export, rollback, no-write window, branch/worktree, interruption, direct-SQL, full-validator, closure, and soak checks pass; G3 evidence is complete.
Completion Evidence: G3-MAINTAINER-CONVERSION-PROVEN satisfied under bootstrap token 840d37699b767de2: exact commit 3aaacdf and external archive 08b8cb0a passed two semantic rehearsals; live maintainer cutover preserved 466 inventoried files and 20 assigned imports; archive rollback, SQLite backup, shadow/hybrid rebuild, interruption, direct-SQL recovery, real-worktree lineage refusal, legacy-writer refusal, no-write window, HPT2 parity, and 5.04-second soak passed; append-only bootstrap sync converged to CLEAN revision 10 with tracked checkpoint 8b025e953ba85287; final full profile passed 342/342 tests and all repository contracts; no updater, publication, push, release, skill sync, or client mutation occurred. Historical claim audit: work/evidence/evidence-historical-campaign-external-claims-backfill.md
Completion Date: 2026-08-28
Completion Order: 90
Disposition: completed
Roadmap: hybrid-sqlite-operational-state
Roadmap Revision: 2
Milestone: M3-MAINTAINER-HYBRID-PROVEN
Unlocks Gate: G3-MAINTAINER-CONVERSION-PROVEN

## Request

Use the dedicated maintainer path: never run the disconnected-snapshot updater against the canonical checkout. Rehearse from the exact source state in a disposable clone, then perform the guarded live maintainer state conversion only after every pre-cutover gate passes. Preserve all files and retain rollback. Requested endpoint: work3 local maintained candidate; no publication, installed-skill synchronization, or downstream client mutation.

## App Server Preparation Contract

```json
{
  "campaign_id": "rehearse-and-convert-maintainer-to-hybrid-state",
  "completion_evidence": "An assigned-ID manifest and external archive cover tracked, ignored, and untracked conversion state; disposable rehearsals are deterministic; the live shadow import, parity, rebuild, backup, reverse export, rollback, no-write window, branch/worktree, interruption, direct-SQL, full-validator, closure, and soak checks pass; G3 evidence is complete.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "The disposable rehearsal and canonical live maintainer conversion prove exact no-data-loss migration, recovery, direct-SQL reconciliation, bootstrap closure, and stable hybrid operation while retaining every original file.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

An assigned-ID manifest and external archive cover tracked, ignored, and untracked conversion state; disposable rehearsals are deterministic; the live shadow import, parity, rebuild, backup, reverse export, rollback, no-write window, branch/worktree, interruption, direct-SQL, full-validator, closure, and soak checks pass; G3 evidence is complete.
