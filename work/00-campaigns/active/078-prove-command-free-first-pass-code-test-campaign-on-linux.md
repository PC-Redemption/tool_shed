# Prove command-free first-pass code and test preparation on Linux

Status: queued
Type: campaign
Updated: 2026-08-26
Next Action: execute when selected from the active campaign queue
Campaign ID: prove-command-free-first-pass-code-test-campaign-on-linux
Campaign Number: 078
Outcome: A fresh bounded code-and-test campaign completes from one App Server command through the command-free first-file-change handoff.
Primary Focus Areas: provider-portability
Supporting Focus Areas: campaign-lifecycle, workspace-safety
Depends On: prove-first-pass-documentation-campaign-on-linux, establish-deterministic-app-server-worker-handoff
Decision: none
Detour For: none
Return To: none
Completion Gate: The command-free code/test proof contributes passing evidence to G11 with one file-change handoff, no worker shell, and exactly-once verification.
Completion Evidence: none
Disposition: none
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 5
Milestone: M11-LINUX-FIRST-PASS-PROOF
Unlocks Gate: none

## Request

Select one small useful code-and-focused-test improvement in the maintained Tool Shed workspace. Start it through ts: next --app-server with no manually authored capsule. Automatic preparation must provide complete bounded source context, exact expected paths, and a quiet verifier. The write worker must issue no commandExecution; its first completed fileChange must be interrupted into Tool Shed-owned exactly-once verification without a final model handoff request. Capture source binding, preparation and execution usage, turns, control stop, journal, and verification. Complete only if the first worker verifies within default budgets and changes only declared paths. Do not replay Campaigns 073 or 075, publish, synchronize skills, upgrade clients, or run the full suite.

## App Server Preparation Contract

```json
{
  "campaign_id": "prove-command-free-first-pass-code-test-campaign-on-linux",
  "completion_evidence": "The command-free code/test proof contributes passing evidence to G11 with one file-change handoff, no worker shell, and exactly-once verification.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "A fresh bounded code-and-test campaign completes from one App Server command through the command-free first-file-change handoff.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

The command-free code/test proof contributes passing evidence to G11 with one file-change handoff, no worker shell, and exactly-once verification.
