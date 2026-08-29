# Implement mutation-aware GUI fallback and sanitized events

Status: complete
Type: campaign
Updated: 2026-08-27
Next Action: none
Campaign ID: implement-safe-app-server-gui-fallback
Campaign Number: 093
Outcome: Persisted prefer-App-Server mode continues recoverable work in GUI in the same action and records bounded privacy-safe success/failure events without replaying possible mutation.
Primary Focus Areas: provider-portability
Supporting Focus Areas: workspace-safety, campaign-lifecycle
Depends On: implement-persistent-app-server-preference
Decision: none
Detour For: none
Return To: none
Completion Gate: Focused tests cover selection/start/read-only failure, pre-mutation CAMP failure, known or unknown post-mutation reconciliation, no replay, diagnostic-write failure, redaction, bounded event fields, and concise fallback banners.
Completion Evidence: Implemented automatic same-action GUI fallback for persisted mode across selection and next dispatch; pre-mutation failures continue immediately, possible mutation requires journal/Git reconciliation with no replay, explicit App Server remains strict, and sanitized best-effort user-local JSONL events exclude request content. 89 focused tests and 21 routing/docs/provider checks passed.
Completion Date: 2026-08-27
Completion Order: 80
Disposition: completed
Roadmap: passive-app-server-dogfooding
Roadmap Revision: 1
Milestone: M1-PASSIVE-CORE
Unlocks Gate: none

## Request

Extend only persisted prefer-App-Server mode with automatic same-action GUI fallback. Reuse current error categories, App Server controller/dispatcher results, mutation journal, and Git boundary. Continue directly in GUI for safe selection, authentication, qualification, startup, network, model, read-only, and pre-mutation failures. After known or possible mutation, hand control to GUI reconciliation of the existing journal and Git state before continuing; never blindly replay. Append minimal sanitized success/failure events under the user-local Codex home using bounded fields and best-effort atomic writes; exclude prompts, raw model output, credentials, secrets, and broad environment capture. A logging failure must not block fallback. Preserve explicit strict --app-server fail-closed behavior. Add focused tests and concise operator documentation. Do not add reports, dashboards, circuit breakers, automatic repairs, publication, synchronization, or downstream project mutation.

## App Server Preparation Contract

```json
{
  "campaign_id": "implement-safe-app-server-gui-fallback",
  "completion_evidence": "Focused tests cover selection/start/read-only failure, pre-mutation CAMP failure, known or unknown post-mutation reconciliation, no replay, diagnostic-write failure, redaction, bounded event fields, and concise fallback banners.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "Persisted prefer-App-Server mode continues recoverable work in GUI in the same action and records bounded privacy-safe success/failure events without replaying possible mutation.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

Focused tests cover selection/start/read-only failure, pre-mutation CAMP failure, known or unknown post-mutation reconciliation, no replay, diagnostic-write failure, redaction, bounded event fields, and concise fallback banners.
