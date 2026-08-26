# Prove path-state command-free asset revision on Linux

Status: queued
Type: campaign
Updated: 2026-08-26
Next Action: execute when selected from the active campaign queue
Campaign ID: prove-path-state-command-free-first-pass-asset-aware-campaign-on-linux
Campaign Number: 083
Outcome: Documentation asset cache revisions cover every direct site asset deterministically through a command-free worker with explicit expected-path starting states.
Primary Focus Areas: provider-portability
Supporting Focus Areas: workspace-safety, campaign-lifecycle
Depends On: prove-path-state-command-free-first-pass-code-test-campaign-on-linux
Decision: none
Detour For: none
Return To: none
Completion Gate: G11-LINUX-FIRST-PASS-RELIABLE passes across documentation plus path-state command-free code/test and asset-aware task shapes.
Completion Evidence: none
Disposition: none
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 7
Milestone: M11-LINUX-FIRST-PASS-PROOF
Unlocks Gate: G11-LINUX-FIRST-PASS-RELIABLE

## Request

Harden the documentation site's asset_revision behavior so its cache revision is derived deterministically from every regular file directly under site/assets, not only the two currently hard-coded asset names. Hash stable relative filenames as well as bytes so rename-only changes alter the revision; ignore directories and keep output at the existing 12 hexadecimal characters. Add focused tests using a temporary asset directory and the production function to prove stable ordering, content changes, rename-only changes, and directory exclusion. Start through ts: next --app-server with no manually authored capsule. Automatic preparation must use metadata-only inventory for site assets, exclude binary or generated payloads from inline context, supply complete bounded text source/test context, a quiet verifier, and explicit expected-path starting states. The write worker must issue no commandExecution; its first completed fileChange must hand off directly to Tool Shed-owned exactly-once verification. Capture source binding, usage, turns, control stop, path-start state, journal, and verification. Complete only on first-worker verification or correct pre-worker reduction. Do not replay Campaigns 074, 076, 079, or 081, publish, synchronize skills, upgrade clients, or run the full suite.

## App Server Preparation Contract

```json
{
  "campaign_id": "prove-path-state-command-free-first-pass-asset-aware-campaign-on-linux",
  "completion_evidence": "G11-LINUX-FIRST-PASS-RELIABLE passes across documentation plus path-state command-free code/test and asset-aware task shapes.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "Documentation asset cache revisions cover every direct site asset deterministically through a command-free worker with explicit expected-path starting states.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

G11-LINUX-FIRST-PASS-RELIABLE passes across documentation plus path-state command-free code/test and asset-aware task shapes.
