# Replace CAMP version gate with operator-runtime trust

Status: complete
Type: campaign
Updated: 2026-08-27
Next Action: none
Campaign ID: replace-camp-version-gate-with-operator-runtime-trust
Campaign Number: 100
Outcome: Fresh schema-v2 App Server consent and a separated trust/readiness/safety/certification model allow an otherwise unknown Codex CLI to reach bounded CAMP admission without an exact registry record.
Primary Focus Areas: provider-portability
Supporting Focus Areas: workspace-safety, qualification-release
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: Preference migration, policy precedence, selector and status tests prove legacy on does not silently broaden writes, fresh on enables operator-runtime policy, normal admission ignores missing exact identity certification, and explicit repository strict mode retains certification requirements.
Completion Evidence: Schema-v2 consent migration, operator-runtime selector/status separation, legacy non-broadening, strict repository certification, registry/hash telemetry behavior, and 95 focused App Server tests passed. Historical claim audit: work/evidence/evidence-historical-campaign-external-claims-backfill.md
Completion Date: 2026-08-27
Completion Order: 84
Disposition: completed
Roadmap: operator-trust-camp-runtime-enforcement
Roadmap Revision: 1
Milestone: M1-OPERATOR-TRUST-CAMP
Unlocks Gate: none

## Request

Implement the smallest preference, policy, compatibility, selector, and status refactor needed to separate operator trust, current runtime readiness, observed safety, and optional certification. Keep default-off, --gui precedence, strict explicit --app-server behavior, GUI-native routes, disabled API fallback, and sanitized events. Extend repository policy only as needed for strict-certified mode. Treat version, path, hash, protocol fingerprint, registry, and cache results as diagnostic or strict-mode evidence in normal operator-runtime selection. Add focused migration and reporting tests. Requested endpoint: work3 local candidate; do not push, publish, release, deploy, synchronize skills, or mutate downstream workspaces.

## App Server Preparation Contract

```json
{
  "campaign_id": "replace-camp-version-gate-with-operator-runtime-trust",
  "completion_evidence": "Preference migration, policy precedence, selector and status tests prove legacy on does not silently broaden writes, fresh on enables operator-runtime policy, normal admission ignores missing exact identity certification, and explicit repository strict mode retains certification requirements.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "Fresh schema-v2 App Server consent and a separated trust/readiness/safety/certification model allow an otherwise unknown Codex CLI to reach bounded CAMP admission without an exact registry record.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

Preference migration, policy precedence, selector and status tests prove legacy on does not silently broaden writes, fresh on enables operator-runtime policy, normal admission ignores missing exact identity certification, and explicit repository strict mode retains certification requirements.
