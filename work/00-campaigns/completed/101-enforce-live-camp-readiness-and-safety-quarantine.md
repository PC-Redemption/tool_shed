# Prove live CAMP readiness through the existing runtime path

Status: complete
Type: campaign
Updated: 2026-08-27
Next Action: none
Campaign ID: enforce-live-camp-readiness-and-safety-quarantine
Campaign Number: 101
Outcome: An unknown Codex version completes bounded CAMP through the existing runtime and containment path, while only an evidence-backed exact `unqualified` registry record denies a version.
Primary Focus Areas: workspace-safety
Supporting Focus Areas: provider-portability, campaign-lifecycle
Depends On: replace-camp-version-gate-with-operator-runtime-trust
Decision: none
Detour For: none
Return To: none
Completion Gate: A focused end-to-end test proves fresh operator trust lets an unknown version perform and verify one bounded CAMP mutation through the existing runner; existing startup, authentication, model, sandbox, Git, path, journal, budget, verification, reconciliation, and no-replay behavior remains passing; an evidence-backed exact `unqualified` record denies only its recorded version and a new version runs normally.
Completion Evidence: 96 focused tests pass, including an unknown-version bounded CAMP mutation through the existing runner and exact evidence-backed unqualified denial with fixed-version recovery; no parallel preflight, journal, quarantine, or state store remains.
Completion Date: 2026-08-27
Completion Order: 85
Disposition: completed
Roadmap: operator-trust-camp-runtime-enforcement
Roadmap Revision: 1
Milestone: M1-OPERATOR-TRUST-CAMP
Unlocks Gate: none

## Request

Use the existing selector, dispatcher, App Server client, bounded CAMP runner, Git mutation journal, path enforcement, budgets, deterministic verification, and recovery semantics without adding another preflight, journal, policy engine, or protected state store. The actual operation is the runtime capability handshake. Reuse exact `unqualified` records in the existing reviewed qualification registry as the narrow version denylist, requiring an evidence reference. Add one focused end-to-end unknown-version CAMP test and one exact-denial/fixed-version recovery test. Requested endpoint: work3 local candidate; do not perform external writes or protected operations.

## App Server Preparation Contract

```json
{
  "campaign_id": "enforce-live-camp-readiness-and-safety-quarantine",
  "completion_evidence": "An end-to-end unknown-version CAMP test passes through the existing runner, existing containment and recovery tests remain green, and an evidence-backed exact unqualified record denies only the recorded version.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "Prove unknown-version CAMP works through the existing runtime path and add only a minimal evidence-backed exact-version denial.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

An end-to-end unknown-version CAMP test passes through the existing runner, existing containment and recovery tests remain green, and an evidence-backed exact `unqualified` record denies only the recorded version.
