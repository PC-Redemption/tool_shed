# Adopt first-pass App Server preparation in Core

Status: complete
Type: campaign
Updated: 2026-08-26
Next Action: none
Campaign ID: adopt-first-pass-app-server-preparation-in-core
Campaign Number: 085
Outcome: A fresh ordinary Core campaign completes on its first automatically prepared Windows App Server attempt.
Primary Focus Areas: provider-portability
Supporting Focus Areas: snapshot-delivery, workspace-safety, campaign-lifecycle
Depends On: publish-and-synchronize-case-normalized-verification
Decision: none
Detour For: none
Return To: none
Completion Gate: G13-CORE-FIRST-PASS-OWNER-READY passes with exact upgrade, first-attempt execution, exactly-once verification, bounded usage, and no deployment.
Completion Evidence: work/evidence/evidence-core-v0-29-13-first-pass-owner-ready.md
Completion Date: 2026-08-26
Completion Order: 77
Disposition: completed
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 7
Milestone: M13-CORE-FIRST-PASS-ADOPTION
Unlocks Gate: G13-CORE-FIRST-PASS-OWNER-READY

## Request

Under the Core-upgrade and operator-assisted Windows authorization granted on 2026-08-26, upgrade
Core's disconnected Tool Shed snapshot and installed skill to the verified first-pass release with
bounded backups. The v0.29.11 and v0.29.12 upgrades completed exactly. Core Campaign 022 exposed a
same-boundary file-change handoff defect and whitespace-fragile verification; Core Campaign 023 then
proved the v0.29.12 handoff in one worker turn but exposed case-sensitive semantic verification.
After Campaign 091 publishes and synchronizes the locally proven Campaign 090 correction, re-upgrade
Core to that stable patch without requesting Core authorization again. From the normal logged-in
Windows GUI console, create and run one fresh ordinary non-production Core campaign through
`ts: next --app-server` without manually authoring or repairing its capsule. Capture source binding,
preparation and execution usage, turns, tool-result bytes, expected and actual paths, journal, and
exactly-once verification. Complete only if the first worker attempt succeeds without replay or
preventable reconciliation. Do not replay completed campaigns or deploy Bactron.

## App Server Preparation Contract

```json
{
  "campaign_id": "adopt-first-pass-app-server-preparation-in-core",
  "completion_evidence": "G13-CORE-FIRST-PASS-OWNER-READY passes with exact upgrade, first-attempt execution, exactly-once verification, bounded usage, and no deployment.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "A fresh ordinary Core campaign completes on its first automatically prepared Windows App Server attempt.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

G13-CORE-FIRST-PASS-OWNER-READY passes with exact upgrade, first-attempt execution, exactly-once verification, bounded usage, and no deployment.
