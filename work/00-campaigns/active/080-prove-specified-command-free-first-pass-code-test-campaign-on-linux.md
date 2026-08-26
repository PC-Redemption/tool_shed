# Prove specified command-free provider path validation on Linux

Status: queued
Type: campaign
Updated: 2026-08-26
Next Action: execute when selected from the active campaign queue
Campaign ID: prove-specified-command-free-first-pass-code-test-campaign-on-linux
Campaign Number: 080
Outcome: Provider adapter instruction paths are validated identically on Linux and Windows, and the fix completes through the command-free first-file-change handoff.
Primary Focus Areas: provider-portability
Supporting Focus Areas: campaign-lifecycle, workspace-safety
Depends On: prove-first-pass-documentation-campaign-on-linux, establish-deterministic-app-server-worker-handoff
Decision: none
Detour For: none
Return To: none
Completion Gate: The specified code/test proof contributes passing evidence to G11 with one file-change handoff, no worker shell, and exactly-once verification.
Completion Evidence: none
Disposition: none
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 6
Milestone: M11-LINUX-FIRST-PASS-PROOF
Unlocks Gate: none

## Request

Harden the existing provider adapter safe-relative-path validation so manifest instruction paths remain repository-relative on both Linux and Windows. The current helper uses host Path semantics and can accept root-like dot paths or Windows-style backslash traversal when running on Linux. Preserve valid POSIX repository-relative paths, reject empty or dot/root paths, reject parent traversal with either slash style, reject POSIX absolute paths, Windows drive-absolute paths, UNC paths, and backslash-containing manifest paths, and add focused standard-library unittest coverage that calls the production validation behavior. Start through ts: next --app-server with no manually authored capsule. Automatic preparation must resolve exact paths, complete bounded context, and a quiet verifier. The write worker must issue no commandExecution; its first completed fileChange must hand off directly to Tool Shed-owned exactly-once verification. Capture source binding, usage, turns, control stop, journal, and verification. Complete only if the first worker verifies within default budgets and changes only declared paths. Do not replay Campaigns 073, 075, or 078, publish, synchronize skills, upgrade clients, or run the full suite.

## App Server Preparation Contract

```json
{
  "campaign_id": "prove-specified-command-free-first-pass-code-test-campaign-on-linux",
  "completion_evidence": "The specified code/test proof contributes passing evidence to G11 with one file-change handoff, no worker shell, and exactly-once verification.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "Provider adapter instruction paths are validated identically on Linux and Windows, and the fix completes through the command-free first-file-change handoff.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

The specified code/test proof contributes passing evidence to G11 with one file-change handoff, no worker shell, and exactly-once verification.
