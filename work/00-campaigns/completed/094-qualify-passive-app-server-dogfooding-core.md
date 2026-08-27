# Qualify passive App Server dogfooding core

Status: complete
Type: campaign
Updated: 2026-08-27
Next Action: none
Campaign ID: qualify-passive-app-server-dogfooding-core
Campaign Number: 094
Outcome: The complete M1 behavior is proven in disposable workspaces and documented as a release-ready but unpublished Tool Shed candidate.
Primary Focus Areas: qualification-release
Supporting Focus Areas: provider-portability, snapshot-delivery, workspace-safety
Depends On: implement-safe-app-server-gui-fallback
Decision: none
Detour For: none
Return To: none
Completion Gate: G1-PASSIVE-CORE-QUALIFIED passes with focused Linux behavior, disposable installed-workspace smoke, privacy assertions, snapshot/install parity checks, and one unchanged full validator result only when release-candidate qualification requires it.
Completion Evidence: G1-PASSIVE-CORE-QUALIFIED passed; durable evidence: work/evidence/evidence-passive-app-server-dogfooding-core.md. Unpublished 0.30.0 manifest matches 143 shipped files; 105 focused tests/checks and the single final full validator with 310 tests, provider conformance, roadmap/work validation, and disposable all-provider install smoke passed. No publish, tag, push, skill sync, downstream upgrade, or deployment performed.
Completion Date: 2026-08-27
Completion Order: 81
Disposition: completed
Roadmap: passive-app-server-dogfooding
Roadmap Revision: 1
Milestone: M1-PASSIVE-CORE
Unlocks Gate: G1-PASSIVE-CORE-QUALIFIED

## Request

Qualify the integrated M1 candidate without adding features. Exercise on, off, status, alias, --gui precedence, strict explicit --app-server, unchanged GUI-native routes, successful eligible selection, safe automatic GUI fallback, mutation-aware reconciliation, no replay, best-effort diagnostic failure, and sanitized event fields in disposable workspaces. Verify installer and generated provider instructions match the canonical contract. Run focused suites first and the complete Tool Shed validator at most once on unchanged qualification inputs if required for release readiness. Record compact durable evidence. Do not publish, tag, push, synchronize installed skills, upgrade downstream snapshots, mutate product projects, add analytics or circuit breakers, or deploy anything.

## App Server Preparation Contract

```json
{
  "campaign_id": "qualify-passive-app-server-dogfooding-core",
  "completion_evidence": "G1-PASSIVE-CORE-QUALIFIED passes with focused Linux behavior, disposable installed-workspace smoke, privacy assertions, snapshot/install parity checks, and one unchanged full validator result only when release-candidate qualification requires it.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "The complete M1 behavior is proven in disposable workspaces and documented as a release-ready but unpublished Tool Shed candidate.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

G1-PASSIVE-CORE-QUALIFIED passes with focused Linux behavior, disposable installed-workspace smoke, privacy assertions, snapshot/install parity checks, and one unchanged full validator result only when release-candidate qualification requires it.
