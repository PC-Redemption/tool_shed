# Adopt first-pass App Server preparation in Core

Status: working
Type: campaign
Updated: 2026-08-26
Next Action: execute the campaign completion gate
Campaign ID: adopt-first-pass-app-server-preparation-in-core
Campaign Number: 085
Outcome: A fresh ordinary Core campaign completes on its first automatically prepared Windows App Server attempt.
Primary Focus Areas: provider-portability
Supporting Focus Areas: snapshot-delivery, workspace-safety, campaign-lifecycle
Depends On: publish-and-synchronize-first-pass-app-server-preparation
Decision: none
Detour For: none
Return To: none
Completion Gate: G13-CORE-FIRST-PASS-OWNER-READY passes with exact upgrade, first-attempt execution, exactly-once verification, bounded usage, and no deployment.
Completion Evidence: none
Disposition: none
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 7
Milestone: M13-CORE-FIRST-PASS-ADOPTION
Unlocks Gate: G13-CORE-FIRST-PASS-OWNER-READY

## Request

Under the Core-upgrade and operator-assisted Windows authorization granted on 2026-08-26, upgrade Core's disconnected Tool Shed snapshot and installed skill to the verified first-pass release with bounded backups. The first v0.29.10 upgrade completed exactly; after Campaign 087 publishes and synchronizes the corrective preparation patch, re-upgrade Core to that stable patch without requesting Core authorization again. From the normal logged-in Windows GUI console, run one fresh ordinary non-production Core campaign through ts: next --app-server without manually authoring or repairing its capsule. Capture source binding, preparation and execution usage, turns, tool-result bytes, expected and actual paths, journal, and exactly-once verification. Complete only if the first worker attempt succeeds without replay or preventable reconciliation. Do not replay completed campaigns or deploy Bactron.

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
