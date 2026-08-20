# App Server Write Qualification and CAMP Execution

Status: complete
Type: campaign
Updated: 2026-08-20
Next Action: none
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
Completion Evidence: Codex 0.144.6 disposable workspace-write boundary harness passed; hardened temp exclusions, ChatGPT-only auth, exact-root sandbox, denial, interrupt/partial-write reconciliation, dirty-work protection, and Git mutation journal qualified; minimal Terra write and one real journaled CAMP step passed 20 focused tests; representative CAMP token savings were not demonstrated, so only explicit camp_execution is enabled while global default, broader writing, build, deployment, permission expansion, and API fallback remain disabled; full Tool Shed validation passed 177 tests.
Completion Date: 2026-08-20
Completion Order: 34
Disposition: completed

## Request

Qualify the installed Codex 0.144.6 App Server workspace-write boundary before enabling any CAMP
execution. Preserve Campaign 035 as the completed read-only baseline. If disposable qualification
passes, add explicit opt-in `camp_execution` routing to Terra/medium with Git mutation journaling,
structured outcomes, deterministic lifecycle control, and bounded escalation. Keep the global
default, testing/build/deployment roles, network, permission expansion, API fallback, and automatic
lifecycle transitions disabled.

## Qualification Progress

Promotion decision: qualify workspace writing only for explicit journaled `camp_execution` on
Codex 0.144.6; retain global default-off and the existing GUI fallback because representative CAMP
token savings were not demonstrated and broader blockers remain.

- Deterministic workspace read/create/modify/delete/directory/test commands passed.
- Sibling writes/deletion, privileged writes, and network access failed closed.
- Schema-default workspace-write allowed `/tmp`; the qualified policy explicitly excludes both
  `/tmp` and the process temp directory.
- A minimal Terra/medium edit and focused test passed with a clean Git mutation journal.
- Command approval denial was emitted to the client, declined, and respected.
- Cancellation left an expected partial write; post-state reconciliation found it and did not
  classify the CAMP complete.
- Read-only resume preserved the reduced permission boundary and reported user intervention.
- The first real Terra/medium `camp-run` changed only its declared test file, returned
  `step_complete`, passed all 20 focused tests, and produced a safe journal with no unexpected paths.
- That real CAMP used 241,524 input tokens and crossed the 50,000 warning threshold. The GUI exposes
  no matching token telemetry, so savings are not established and broader promotion is rejected.
- Structured outcomes and deterministic control allow one clean Terra retry, read-only Sol
  escalation only after clean failure, and reconciliation before any action after mutation.
- Raw disposable evidence is stored under ignored `work/evidence/generated/`; the durable results,
  policy, comparison limit, rollback boundary, and promotion decision are recorded in
  `docs/codex-app-server-write-qualification-2026-08-20.md`.

## Completion Check

Disposable write qualification proves or rejects the authorized-workspace boundary, command policy, denial, cancellation and partial-write reconciliation, dirty-worktree protection, mutation journaling, authentication, fallback, and telemetry; if critical safety criteria pass, minimal Terra writing and representative CAMP execution are qualified with structured outcomes, bounded escalation, cost comparison, documentation, and full validation while global default and deployment remain disabled; otherwise implementation stops with durable blocker evidence.
