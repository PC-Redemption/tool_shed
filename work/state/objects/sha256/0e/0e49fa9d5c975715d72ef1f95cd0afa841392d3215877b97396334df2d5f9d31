# Qualify a disconnected hybrid production canary

Status: complete
Type: campaign
Updated: 2026-08-28
Next Action: none
Campaign ID: qualify-disconnected-hybrid-production-canary
Campaign Number: 108
Outcome: One production-shaped disconnected Tool Shed client with local Git but no project GitHub remote or authenticated gh proves install/upgrade, checkpoint, backup, restore, reconciliation, safe downgrade behavior, and rollback before broad rollout.
Primary Focus Areas: snapshot-delivery
Supporting Focus Areas: qualification-release, workspace-safety, artifact-workflows
Depends On: publish-hybrid-state-release-and-sync-maintainer-skill
Decision: none
Detour For: none
Return To: none
Completion Gate: The released external updater backs up and migrates the declared file/database/skill surface, validates reconstruction and closed-loop state, handles old-updater refusal, operates without gh authentication or a project remote, restores from external backup, downgrades through verified reverse export or refuses safely, and completes the required soak with no unresolved finding; G4 passes.
Completion Evidence: EVID-G4-CANARY passed under bootstrap closure token 3c9c7b90b911c4bd: published v0.34.2 upgraded the zero-remote unauthenticated synthetic hybrid client through protocol 4; live, backup, checkpoint, and rebuild parity matched; rollback restored; downgrade refused without mutation; isolated skill synchronization matched; strict snapshot integrity stayed bytecode-free; and three soak rounds ended HEALTHY with zero findings.
Completion Date: 2026-08-28
Completion Order: 92
Disposition: completed
Roadmap: hybrid-sqlite-operational-state
Roadmap Revision: 3
Milestone: M4-RELEASE-CANARY-PROVEN
Unlocks Gate: G4-RELEASE-CANARY-PROVEN

## Request

After the release and only under separate explicit client-mutation authority, upgrade one disposable or low-risk disconnected client through the normal released updater. Verify no-GitHub project operation, DB/checkpoint lineage, closure, context efficiency, backup/restore, rollback, and downgrade behavior. Record compact durable evidence and stop before broad fleet rollout.

## Approved Canary Boundary

Use one disposable synthetic client created from Tool Shed-owned fixture content in a secure
temporary directory. The client must have local Git, no project remote, and isolated unauthenticated
GitHub CLI state. Do not inspect, copy, or mutate another project workspace. Retain only compact
sanitized evidence in this repository after qualification.

## App Server Preparation Contract

```json
{
  "campaign_id": "qualify-disconnected-hybrid-production-canary",
  "completion_evidence": "The released external updater backs up and migrates the declared file/database/skill surface, validates reconstruction and closed-loop state, handles old-updater refusal, operates without gh authentication or a project remote, restores from external backup, downgrades through verified reverse export or refuses safely, and completes the required soak with no unresolved finding; G4 passes.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "One production-shaped disconnected Tool Shed client with local Git but no project GitHub remote or authenticated gh proves install/upgrade, checkpoint, backup, restore, reconciliation, safe downgrade behavior, and rollback before broad rollout.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

The released external updater backs up and migrates the declared file/database/skill surface, validates reconstruction and closed-loop state, handles old-updater refusal, operates without gh authentication or a project remote, restores from external backup, downgrades through verified reverse export or refuses safely, and completes the required soak with no unresolved finding; G4 passes.
