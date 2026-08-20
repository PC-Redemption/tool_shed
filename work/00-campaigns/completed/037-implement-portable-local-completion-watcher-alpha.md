# Implement the portable local completion-watcher alpha

Status: complete
Type: campaign
Updated: 2026-08-19
Next Action: none
Campaign ID: implement-portable-local-completion-watcher-alpha
Campaign Number: 037
Outcome: Deliver the opt-in local watcher CLI, atomic spool, singleton on-demand runner, four-state evaluation, durable terminal outbox, and lease/crash recovery without hosted dependencies.
Primary Focus Areas: provider-portability
Supporting Focus Areas: workspace-safety, qualification-release
Depends On: define-completion-watcher-protocol-and-failure-model
Decision: none
Detour For: none
Return To: none
Completion Gate: The local alpha passes deterministic tests for atomic arming, singleton/concurrent operation, 60-second default cadence, immutable-target evaluation, every terminal and checker-error path, cancellation, lease recovery, dispatcher crash, outbox replay, idle exit, optional ensure-runner recovery, safe permissions, and local-only operation.
Completion Evidence: work/evidence/evidence-completion-watcher-v1-alpha.md
Completion Date: 2026-08-19
Completion Order: 34
Disposition: completed
Roadmap: completion-watcher-program
Roadmap Revision: 1
Milestone: M2-LOCAL-ALPHA
Unlocks Gate: G2-LOCAL-ALPHA-PROVEN

## Request

Implement the approved protocol as a provider-neutral local Tool Shed capability with status, cancel, and ensure-runner commands. Keep hosted reporting behind the adapter boundary and disabled. Document machine-local state, security, limitations, and recovery behavior.

## Completion Check

The local alpha passes deterministic tests for atomic arming, singleton/concurrent operation, 60-second default cadence, immutable-target evaluation, every terminal and checker-error path, cancellation, lease recovery, dispatcher crash, outbox replay, idle exit, optional ensure-runner recovery, safe permissions, and local-only operation.
