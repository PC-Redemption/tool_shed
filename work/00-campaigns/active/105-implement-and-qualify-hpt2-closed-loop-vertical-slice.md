# Implement and qualify the HPT2 closed-loop vertical slice

Status: working
Type: campaign
Updated: 2026-08-28
Next Action: execute the campaign completion gate
Campaign ID: implement-and-qualify-hpt2-closed-loop-vertical-slice
Campaign Number: 105
Outcome: HPT2 is imported without invented history and produces a complete idea-to-product reconciliation whose requirement, material-change, evidence, exception, and verdict results match the independent bootstrap record.
Primary Focus Areas: campaign-lifecycle
Supporting Focus Areas: artifact-workflows, workspace-safety, qualification-release
Depends On: implement-minimum-sqlite-operational-substrate
Decision: none
Detour For: none
Return To: none
Completion Gate: HPT2 source accounting, outcome contract, material changes, product evidence, exceptions, and final verdict reconcile end to end; database import reproduces the bootstrap result in a fresh clone; byte and semantic parity, query/capsule correctness, 70% median context reduction, and 5% fallback limits pass; G2 evidence is complete.
Completion Evidence: none
Disposition: none
Roadmap: hybrid-sqlite-operational-state
Roadmap Revision: 1
Milestone: M2-SUBSTRATE-HPT2-PROVEN
Unlocks Gate: G2-SUBSTRATE-LOOP-PROVEN

## Request

Implement the minimum universal closed-loop records and reports on the approved substrate, using HPT2 as the qualification case. Preserve ambiguous history explicitly. Build identical file-first and hybrid fixtures for status, next, overview, dependency/gate lookup, history, reconciliation, and one bounded mutation. Requested endpoint: work3 local candidate; do not broaden database ownership, convert the live maintainer, or release.

## App Server Preparation Contract

```json
{
  "campaign_id": "implement-and-qualify-hpt2-closed-loop-vertical-slice",
  "completion_evidence": "HPT2 source accounting, outcome contract, material changes, product evidence, exceptions, and final verdict reconcile end to end; database import reproduces the bootstrap result in a fresh clone; byte and semantic parity, query/capsule correctness, 70% median context reduction, and 5% fallback limits pass; G2 evidence is complete.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "HPT2 is imported without invented history and produces a complete idea-to-product reconciliation whose requirement, material-change, evidence, exception, and verdict results match the independent bootstrap record.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

HPT2 source accounting, outcome contract, material changes, product evidence, exceptions, and final verdict reconcile end to end; database import reproduces the bootstrap result in a fresh clone; byte and semantic parity, query/capsule correctness, 70% median context reduction, and 5% fallback limits pass; G2 evidence is complete.
