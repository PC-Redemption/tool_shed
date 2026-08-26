# Establish deterministic App Server worker handoff

Status: complete
Type: campaign
Updated: 2026-08-26
Next Action: none
Campaign ID: establish-deterministic-app-server-worker-handoff
Campaign Number: 077
Outcome: Replace prompt-only mutation-first behavior with a deterministic command-free worker and first-file-change verification handoff.
Primary Focus Areas: provider-portability
Supporting Focus Areas: campaign-lifecycle, workspace-safety
Depends On: make-app-server-collateral-correct-before-worker-launch
Decision: none
Detour For: none
Return To: none
Completion Gate: G10B-DETERMINISTIC-WORKER-HANDOFF passes with official-contract research, client-enforced control, focused tests, and durable evidence.
Completion Evidence: G10B passed: official App Server and installed-client contracts expose interruption but no per-turn built-in-tool allowlist; client-enforced command-free workers now stop on any commandExecution and hand off at the first completed fileChange; 66 focused tests passed; see work/evidence/evidence-app-server-deterministic-worker-handoff.md
Completion Date: 2026-08-26
Completion Order: 67
Disposition: completed
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 5
Milestone: M10B-DETERMINISTIC-WORKER
Unlocks Gate: G10B-DETERMINISTIC-WORKER-HANDOFF

## Request

Use official Codex App Server documentation and the installed client schema to determine whether built-in tools can be restricted per turn. Implement the narrowest supported deterministic protocol: read-only preparation supplies complete context; a write worker may not use commandExecution; the first completed fileChange is the handoff to Tool Shed-owned journaling and exactly-once verification without another model request. Interrupt fail-closed on a worker shell attempt, retain truthful recovery for any race-observed mutation, add focused protocol and dispatcher tests, and record compact evidence. Do not run a real worker proof, publish, synchronize skills, upgrade Core, run the full validator, or deploy anything.

## App Server Preparation Contract

```json
{
  "campaign_id": "establish-deterministic-app-server-worker-handoff",
  "completion_evidence": "G10B-DETERMINISTIC-WORKER-HANDOFF passes with official-contract research, client-enforced control, focused tests, and durable evidence.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "Replace prompt-only mutation-first behavior with a deterministic command-free worker and first-file-change verification handoff.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

G10B-DETERMINISTIC-WORKER-HANDOFF passes with official-contract research, client-enforced control, focused tests, and durable evidence.
