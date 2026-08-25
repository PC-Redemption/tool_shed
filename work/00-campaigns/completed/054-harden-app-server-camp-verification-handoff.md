# Harden App Server CAMP verification handoff

Status: complete
Type: campaign
Updated: 2026-08-25
Next Action: none
Campaign ID: harden-app-server-camp-verification-handoff
Campaign Number: 054
Outcome: Make bounded App Server CAMP execution distinguish a safe mutation journal from verified implementation completion, eliminate the reserved-verification outcome deadlock observed in Bactron Core Campaign 013, and reduce oversized focused-context tool output without weakening exact-binary qualification, path allowlists, fail-closed recovery, or default-off policy.
Primary Focus Areas: provider-portability
Supporting Focus Areas: qualification-release, campaign-lifecycle
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: A representative CAMP may report implementation ready without running orchestrator-reserved commands; the orchestrator then runs every declared deterministic verification command exactly once before recommending any lifecycle advance; unknown, invalid, and partial outcomes never skip required reconciliation or trigger retry after mutation; journal state reports safe-unverified, verification-failed, or verified truthfully; focused tests reproduce the Bactron Core completed-turn, safe-journal, unknown-outcome sequence and cover command failure plus no-retry invariants; focused-context behavior prevents unbounded full-file dumps or emits an enforceable bounded finding; documentation distinguishes protocol-level turn completion from verified CAMP completion; focused tests and the full Tool Shed validator pass; no release, client synchronization, Core mutation, global enablement, or deployment occurs.
Completion Evidence: Focused App Server suite: python3 -m unittest tests.test_codex_execution (42 passed). Full Tool Shed validator: python3 scripts/validate_tool_shed.py (260 tests passed; manifest, provider conformance, indexes, stale paths, work state, roadmaps, and disposable workspace smoke passed). No release, client/skill sync, Core mutation, global enablement, or deployment performed.
Completion Date: 2026-08-25
Completion Order: 49
Disposition: completed

## Request

Use the completed Bactron Core Campaign 013 field trial as the regression specimen. The exact
qualified `0.149.0-alpha.4.3` App Server turn completed with a safe four-path Git journal, but the
worker returned `unknown` because it correctly did not run verification reserved for the enclosing
orchestrator. The current orchestrator runs those commands only for `step_complete` or
`camp_complete`, so the declared verification remained required with zero commands run. The journal
also reported `final_state: verified` even though implementation verification had not occurred.

Repair the generic Tool Shed contract rather than adding a Bactron-specific exception:

- define an unambiguous structured handoff for implementation-ready work whose deterministic
  verification is still reserved for the orchestrator;
- run every declared verification command exactly once only after the mutation journal is safe and
  the worker has reached that handoff, then compute the next action from both results;
- distinguish mutation-boundary safety from implementation verification in journal and telemetry
  state, including safe-unverified, verification-failed, and verified outcomes;
- preserve fail-closed handling for malformed, unknown, partial, interrupted, unsafe, or unexpected-
  path outcomes, with no automatic replay after any possible mutation;
- add a regression fixture matching the observed completed-turn, four-expected-path, zero-
  unexpected-path, reserved-verification-not-run sequence;
- bound or clearly flag oversized context/tool output so a focused CAMP cannot silently consume
  hundreds of thousands of input tokens through whole-file dumps when targeted excerpts suffice;
- align operator and maintainer documentation with the implemented semantic boundary.

Retain App Server as exact-binary and explicit opt-in. Do not broaden qualified roles, connect new
approval surfaces, enable network or API fallback, change lifecycle state automatically, release
Tool Shed, synchronize clients, modify Bactron Core, or deploy anything in this campaign.

## Completion Check

A representative CAMP may report implementation ready without running orchestrator-reserved commands; the orchestrator then runs every declared deterministic verification command exactly once before recommending any lifecycle advance; unknown, invalid, and partial outcomes never skip required reconciliation or trigger retry after mutation; journal state reports safe-unverified, verification-failed, or verified truthfully; focused tests reproduce the Bactron Core completed-turn, safe-journal, unknown-outcome sequence and cover command failure plus no-retry invariants; focused-context behavior prevents unbounded full-file dumps or emits an enforceable bounded finding; documentation distinguishes protocol-level turn completion from verified CAMP completion; focused tests and the full Tool Shed validator pass; no release, client synchronization, Core mutation, global enablement, or deployment occurs.
