# Prove command-free first-pass asset-aware preparation on Linux

Status: queued
Type: campaign
Updated: 2026-08-26
Next Action: execute when selected from the active campaign queue
Campaign ID: prove-command-free-first-pass-asset-aware-campaign-on-linux
Campaign Number: 079
Outcome: A fresh asset-aware campaign completes or is reduced before worker launch using metadata-only asset context and the command-free first-file-change handoff.
Primary Focus Areas: provider-portability
Supporting Focus Areas: workspace-safety, campaign-lifecycle
Depends On: prove-command-free-first-pass-code-test-campaign-on-linux
Decision: none
Detour For: none
Return To: none
Completion Gate: G11-LINUX-FIRST-PASS-RELIABLE passes across documentation plus command-free code/test and asset-aware task shapes.
Completion Evidence: none
Disposition: none
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 5
Milestone: M11-LINUX-FIRST-PASS-PROOF
Unlocks Gate: G11-LINUX-FIRST-PASS-RELIABLE

## Request

Select a bounded useful Tool Shed task whose context includes binary or generated assets but whose authorized mutation is a small exact path set. Start it through ts: next --app-server with no manually authored capsule. Preparation must exclude binary payloads and generated evidence from inline context, provide complete bounded text context, retain asset metadata only, and choose a quiet verifier. The write worker must issue no commandExecution; its first completed fileChange must hand off directly to Tool Shed-owned exactly-once verification. Capture source binding, usage, turns, control stop, journal, and verification. Complete only on first-worker verification or correct pre-worker reduction. Do not replay Campaigns 074 or 076, publish, synchronize skills, upgrade clients, or run the full suite.

## App Server Preparation Contract

```json
{
  "campaign_id": "prove-command-free-first-pass-asset-aware-campaign-on-linux",
  "completion_evidence": "G11-LINUX-FIRST-PASS-RELIABLE passes across documentation plus command-free code/test and asset-aware task shapes.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "A fresh asset-aware campaign completes or is reduced before worker launch using metadata-only asset context and the command-free first-file-change handoff.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

G11-LINUX-FIRST-PASS-RELIABLE passes across documentation plus command-free code/test and asset-aware task shapes.
