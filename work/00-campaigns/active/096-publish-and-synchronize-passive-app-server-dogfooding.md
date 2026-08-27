# Publish and synchronize passive App Server dogfooding

Status: blocked
Type: campaign
Updated: 2026-08-27
Next Action: resolve blocker or decision: fresh Codex task must load synchronized v0.30.0 skill and run ts: app-server status
Campaign ID: publish-and-synchronize-passive-app-server-dogfooding
Campaign Number: 096
Outcome: A traceable Tool Shed release and synchronized maintainer/client skill make the M1 behavior available for real work.
Primary Focus Areas: qualification-release
Supporting Focus Areas: snapshot-delivery, provider-portability
Depends On: qualify-passive-app-server-dogfooding-core
Decision: fresh Codex task must load synchronized v0.30.0 skill and run ts: app-server status
Detour For: none
Return To: none
Completion Gate: Release provenance, tag, manifest, public artifact, exact installed-skill parity, and fresh-session status evidence pass under separate authorization.
Completion Evidence: none
Disposition: none
Roadmap: passive-app-server-dogfooding
Roadmap Revision: 1
Milestone: M2-FIELD-ADOPTION
Unlocks Gate: none

## Request

Only after separate owner release and synchronization authorization, use the existing release and dual-role workspace procedures to version, validate, publish, verify provenance, synchronize the installed maintainer skill, and smoke the fresh-session command contract. Do not mutate product project source or start field analytics in this campaign.

## App Server Preparation Contract

```json
{
  "campaign_id": "publish-and-synchronize-passive-app-server-dogfooding",
  "completion_evidence": "Release provenance, tag, manifest, public artifact, exact installed-skill parity, and fresh-session status evidence pass under separate authorization.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "A traceable Tool Shed release and synchronized maintainer/client skill make the M1 behavior available for real work.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

Release provenance, tag, manifest, public artifact, exact installed-skill parity, and fresh-session status evidence pass under separate authorization.
