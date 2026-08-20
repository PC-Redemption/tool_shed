# Build the hosted watcher status and email pilot

Status: deferred
Type: campaign
Updated: 2026-08-20
Next Action: reactivate only when a named external or non-App-Server workload and notification recipient justify a bounded hosted pilot.
Campaign ID: build-hosted-watcher-status-and-email-pilot
Campaign Number: 039
Outcome: Prove a bounded hosted companion for external or non-App-Server work that accepts outbound-only sanitized terminal events from the local watcher, exposes tenant-scoped advisory status, and delivers centralized email or notifications without executing, controlling, recovering, or managing the originating work.
Primary Focus Areas: provider-portability
Supporting Focus Areas: workspace-safety, qualification-release
Depends On: qualify-and-release-local-completion-watchers
Decision: none
Detour For: none
Return To: none
Completion Gate: One named external or non-App-Server workload completes a bounded pilot in which authenticated tenant-isolated ingestion, sanitized payloads, durable idempotency, advisory status, centralized notification delivery, retention, reporter-staleness semantics, sender-owned offline replay, service-outage tolerance, and independent backend/static-site rollback pass focused security, privacy, and operational tests; the hosted service has no execution, lifecycle, recovery-control, or local write authority.
Completion Evidence: none
Disposition: Scope revised after Campaigns 041 and 042 integrated the qualified App Server architecture. App Server and Tool Shed now own in-path execution, CAMP completion, compatibility monitoring, bounded recovery decisions, and agent lifecycle. Campaign 039 retains only hosted advisory status and notification delivery for external or non-App-Server work. It remains deferred because no current real workload and recipient demonstrate enough independent value to justify hosted maintenance.
Reactivate When: A named external or non-App-Server workload, accountable service owner, intended recipient, and bounded hosting/authentication plan demonstrate that delayed terminal notification has material value beyond Tool Shed and App Server status.
Roadmap: completion-watcher-program
Roadmap Revision: 1
Milestone: M4-HOSTED-PILOT
Unlocks Gate: G4-HOSTED-PILOT-PROVEN

## Request

For a named workload that runs outside the App Server-controlled path, build the smallest
production-shaped hosted notification pilot consistent with the accepted hosted-email ADR. Keep
the local watcher authoritative, accept only outbound sanitized terminal events, expose advisory
tenant-scoped status, configure recipients and mail credentials only on the server, and exclude
remote-control endpoints.

## Scope Revision — 2026-08-20

Campaigns 041 and 042 showed that qualified App Server execution already supplies in-path
orchestration, CAMP completion observation, compatibility monitoring, bounded recovery decisions,
and agent lifecycle. Maintaining a second hosted controller for the same work would duplicate
authority and create conflicting recovery semantics.

Removed or superseded responsibilities:

- execution orchestration;
- CAMP completion detection for App Server-controlled work;
- App Server execution monitoring;
- recovery orchestration or remote retry;
- agent or turn lifecycle management;
- any hosted write-back or control endpoint.

Independent remaining responsibility:

- receive sanitized terminal events emitted by the local watcher for work outside App Server;
- retain a bounded tenant-scoped advisory status record;
- deliver centralized email or another explicitly selected notification;
- report sender staleness and tolerate offline replay without inferring task failure.

The original hosted architecture work remains historical context. This revision narrows what may
be implemented; it does not claim that the pilot has been executed.

## Completion Check

One named external or non-App-Server workload completes a bounded pilot in which authenticated tenant-isolated ingestion, sanitized payloads, durable idempotency, advisory status, centralized notification delivery, retention, reporter-staleness semantics, sender-owned offline replay, service-outage tolerance, and independent backend/static-site rollback pass focused security, privacy, and operational tests; the hosted service has no execution, lifecycle, recovery-control, or local write authority.
