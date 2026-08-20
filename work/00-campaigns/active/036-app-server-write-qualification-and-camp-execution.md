# App Server Write Qualification and CAMP Execution

Status: working
Type: campaign
Updated: 2026-08-20
Next Action: qualify the journaled camp-run path on one bounded real branch change
Campaign ID: app-server-write-qualification-and-camp-execution
Campaign Number: 036
Outcome: Qualify a safely bounded, ChatGPT-authenticated App Server workspace-write path and, only if the safety gate passes, add explicit opt-in Terra CAMP execution with structured outcomes, mutation recovery, bounded Sol escalation, and measured token savings.
Primary Focus Areas: provider-portability
Supporting Focus Areas: workspace-safety, qualification-release
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: Disposable write qualification proves or rejects the authorized-workspace boundary, command policy, denial, cancellation and partial-write reconciliation, dirty-worktree protection, mutation journaling, authentication, fallback, and telemetry; if critical safety criteria pass, minimal Terra writing and representative CAMP execution are qualified with structured outcomes, bounded escalation, cost comparison, documentation, and full validation while global default and deployment remain disabled; otherwise implementation stops with durable blocker evidence.
Completion Evidence: none
Disposition: none

## Request

Qualify the installed Codex 0.144.6 App Server workspace-write boundary before enabling any CAMP
execution. Preserve Campaign 035 as the completed read-only baseline. If disposable qualification
passes, add explicit opt-in `camp_execution` routing to Terra/medium with Git mutation journaling,
structured outcomes, deterministic lifecycle control, and bounded escalation. Keep the global
default, testing/build/deployment roles, network, permission expansion, API fallback, and automatic
lifecycle transitions disabled.

## Qualification Progress

- Deterministic workspace read/create/modify/delete/directory/test commands passed.
- Sibling writes/deletion, privileged writes, and network access failed closed.
- Schema-default workspace-write allowed `/tmp`; the qualified policy explicitly excludes both
  `/tmp` and the process temp directory.
- A minimal Terra/medium edit and focused test passed with a clean Git mutation journal.
- Command approval denial was emitted to the client, declined, and respected.
- Cancellation left an expected partial write; post-state reconciliation found it and did not
  classify the CAMP complete.
- Read-only resume preserved the reduced permission boundary and reported user intervention.
- Raw disposable evidence is stored under ignored `work/evidence/generated/`; a concise durable
  qualification record remains required before campaign completion.

## Completion Check

Disposable write qualification proves or rejects the authorized-workspace boundary, command policy, denial, cancellation and partial-write reconciliation, dirty-worktree protection, mutation journaling, authentication, fallback, and telemetry; if critical safety criteria pass, minimal Terra writing and representative CAMP execution are qualified with structured outcomes, bounded escalation, cost comparison, documentation, and full validation while global default and deployment remain disabled; otherwise implementation stops with durable blocker evidence.
