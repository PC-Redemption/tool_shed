# Implement persistent App Server preference and route precedence

Status: complete
Type: campaign
Updated: 2026-08-27
Next Action: none
Campaign ID: implement-persistent-app-server-preference
Campaign Number: 092
Outcome: One user-local preference makes unflagged eligible Tool Shed commands prefer App Server while preserving explicit strict App Server and one-command GUI overrides.
Primary Focus Areas: provider-portability
Supporting Focus Areas: workspace-safety, snapshot-delivery
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: Atomic cross-platform preference tests, selector/control tests, alias and precedence tests, GUI-native route tests, status output, and user-local permission checks pass without repository-local preference state.
Completion Evidence: Implemented protected atomic user-local on/off preference, strict --app-server and --gui precedence, GUI-native bypass, persistent next dispatch, canonical/alias guidance, and installer parity; 77 focused execution tests plus routing/provider documentation contracts passed.
Completion Date: 2026-08-27
Completion Order: 79
Disposition: completed
Roadmap: passive-app-server-dogfooding
Roadmap Revision: 1
Milestone: M1-PASSIVE-CORE
Unlocks Gate: none

## Request

Implement the smallest user-local persistent preference using the existing Codex-home and protected-cache machinery. Add canonical ts: app-server on, off, and status behavior, retain appserver as an alias, and resolve effective routing with precedence --gui, explicit strict --app-server, persisted preference, then committed GUI default. Apply preference only to already-qualified plan, verify, camp run, and executable next routes; preserve discussion, brainstorming, unsupported roles, qualification checks, API fallback policy, permissions, and authority boundaries. Add focused deterministic tests and current operator/install/skill contract updates. Do not implement fallback execution, analytics, circuit breaking, publish, synchronize installed skills, upgrade clients, or run unrelated platform matrices.

## App Server Preparation Contract

```json
{
  "campaign_id": "implement-persistent-app-server-preference",
  "completion_evidence": "Atomic cross-platform preference tests, selector/control tests, alias and precedence tests, GUI-native route tests, status output, and user-local permission checks pass without repository-local preference state.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "One user-local preference makes unflagged eligible Tool Shed commands prefer App Server while preserving explicit strict App Server and one-command GUI overrides.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## Completion Check

Atomic cross-platform preference tests, selector/control tests, alias and precedence tests, GUI-native route tests, status output, and user-local permission checks pass without repository-local preference state.
