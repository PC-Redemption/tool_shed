# Build the hosted watcher status and email pilot

Status: deferred
Type: campaign
Updated: 2026-08-20
Next Action: reactivate when After Campaign 040 completes, reassess Campaign 039 against the App Server results and explicitly reactivate it only if the watcher work remains relevant.
Campaign ID: build-hosted-watcher-status-and-email-pilot
Campaign Number: 039
Outcome: Deliver a bounded authenticated pilot at the Tool Shed public service boundary for sanitized advisory status and centralized email delivery.
Primary Focus Areas: provider-portability
Supporting Focus Areas: workspace-safety, qualification-release
Depends On: qualify-and-release-local-completion-watchers
Decision: none
Detour For: none
Return To: none
Completion Gate: The selected hosted architecture, authenticated UI, scoped credentials, durable event store, idempotent API/outbox acknowledgement, notification worker, retention policy, tenant isolation, stale-reporter behavior, offline replay, service-outage recovery, and independent static documentation/backend deployment and rollback pass focused security, privacy, and operational tests in an explicitly bounded pilot.
Completion Evidence: none
Disposition: Prioritize Campaign 040 App Server CAMP token optimization because its results may obsolete or materially reshape the hosted watcher pilot.
Reactivate When: After Campaign 040 completes, reassess Campaign 039 against the App Server results and explicitly reactivate it only if the watcher work remains relevant.
Roadmap: completion-watcher-program
Roadmap Revision: 1
Milestone: M4-HOSTED-PILOT
Unlocks Gate: G4-HOSTED-PILOT-PROVEN

## Request

Resolve the remaining hosted technology and operations decisions, then build the smallest production-shaped pilot consistent with the accepted hosted-email ADR. Keep local state authoritative, accept outbound-only sanitized events, configure recipients and mail credentials only on the server, and exclude remote-control endpoints.

## Completion Check

The selected hosted architecture, authenticated UI, scoped credentials, durable event store, idempotent API/outbox acknowledgement, notification worker, retention policy, tenant isolation, stale-reporter behavior, offline replay, service-outage recovery, and independent static documentation/backend deployment and rollback pass focused security, privacy, and operational tests in an explicitly bounded pilot.
