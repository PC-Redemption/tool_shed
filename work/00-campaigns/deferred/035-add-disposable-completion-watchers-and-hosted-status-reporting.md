# Add disposable completion watchers and hosted status reporting

Status: deferred
Type: campaign
Updated: 2026-08-18
Next Action: reactivate when The completion-watcher Program Roadmap is explicitly rejected or abandoned and the owner chooses to return to a single umbrella campaign.
Campaign ID: add-disposable-completion-watchers-and-hosted-status-reporting
Campaign Number: 035
Outcome: Resolve GitHub issue #42 by delivering a reusable, provider-neutral completion watcher with an on-demand singleton runner, one-minute polling, four-state terminal handling, durable idempotent notifications, crash recovery, and an optional outbound-only advisory status plane at ts.rookaro.com. Source: https://github.com/PC-Redemption/tool_shed/issues/42
Primary Focus Areas: provider-portability
Supporting Focus Areas: qualification-release, snapshot-delivery
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: GitHub issue #42 acceptance criteria pass: watches arm atomically and share exactly one disposable runner; legitimate long-running targets remain waiting without elapsed-time failure; successful, unsuccessful, missing, preempted, cancelled, checker-error, crash, and reporting-outage paths produce the specified idempotent lifecycle; the runner exits when idle and can recover through the optional heartbeat hook; hosted reporting is outbound-only, sanitized, secure, advisory, and distinguishes reporter staleness from task failure; operator documentation, focused cross-platform tests, full Tool Shed validation, and normal release/install/update distribution evidence are complete.
Completion Evidence: none
Disposition: Replaced as the executable entrypoint by a full Program Roadmap proposal with staged milestones, evidence gates, and separately approved roadmap-derived campaigns.
Reactivate When: The completion-watcher Program Roadmap is explicitly rejected or abandoned and the owner chooses to return to a single umbrella campaign.

## Request

Add detailed execution context here.

## Completion Check

GitHub issue #42 acceptance criteria pass: watches arm atomically and share exactly one disposable runner; legitimate long-running targets remain waiting without elapsed-time failure; successful, unsuccessful, missing, preempted, cancelled, checker-error, crash, and reporting-outage paths produce the specified idempotent lifecycle; the runner exits when idle and can recover through the optional heartbeat hook; hosted reporting is outbound-only, sanitized, secure, advisory, and distinguishes reporter staleness from task failure; operator documentation, focused cross-platform tests, full Tool Shed validation, and normal release/install/update distribution evidence are complete.
