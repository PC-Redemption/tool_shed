# ADR: Centralize watcher email delivery at ts.rookaro.com

Status: accepted
Type: adr
Updated: 2026-08-18
Next Action: implement the accepted local outbox contract in M2; keep the hosted adapter for M4
Parent: work/maps/map-disposable-completion-watchers-and-hosted-notifications.md
Supersedes: none
Superseded By: none

## Context

GitHub issue #42 and campaign 035 introduce disposable local watchers for long-running work plus an
optional advisory status plane at `ts.rookaro.com`. Terminal outcomes should notify an operator,
but sending mail directly from every workspace would distribute provider credentials, recipient
configuration, retry behavior, and delivery auditing across installations.

The existing `ts.rookaro.com` deployment is a generated, read-only documentation site served by
nginx. A hosted notification path therefore requires a separate stateful backend boundary; it must
not silently turn the static documentation container into the authority for local task state or
make ordinary Tool Shed use depend on a server.

The design must continue to work through temporary network or hosted-service outages. It must also
avoid overstating email guarantees: local and hosted components can durably deduplicate events and
send attempts, but absolute exactly-once receipt cannot be claimed unless the downstream mail
provider supplies an equivalent guarantee.

## Decision

Use an optional authenticated backend at `ts.rookaro.com` as the preferred email-notification
adapter for disposable watchers.

The responsibility boundary is:

- The local watcher runner remains authoritative for immutable target identity, task observation,
  terminal classification, and local watch lifecycle.
- A terminal outcome is first written to a durable local outbox with a stable idempotency key.
- The local reporter sends only a versioned, bounded, sanitized event through outbound HTTPS using
  a per-workspace scoped credential.
- The hosted API acknowledges the event only after durable ingestion and idempotent enqueue into
  its notification pipeline.
- The local reporter retains and retries an unacknowledged event with bounded backoff. Hosted
  unavailability does not change the task outcome and does not resume terminal-state polling.
- Email recipients, mail-provider credentials, delivery preferences, and provider-specific retry
  configuration remain on the hosted service. Watch scripts never receive them.
- The hosted service deduplicates terminal events and notification work by idempotency key. Product
  language may promise durable, idempotent notification processing, but not unconditional
  exactly-once recipient delivery.
- Hosted status is an advisory projection. It may report active watches, terminal outcomes,
  checker errors, and stale reporters, but it cannot execute, cancel, restart, approve, or alter
  local work.
- The hosted adapter is opt-in. Project-native adapters and a no-notification mode remain valid;
  Tool Shed's local watcher capability must not require a hosted account.
- The existing static documentation deployment and the new backend remain independently
  deployable and reversible, even if they share the public hostname through routing.

Phase 1 establishes the local outbox and adapter contract without depending on the hosted service.
Phase 2 adds the hosted API, authenticated status view, notification worker, retention controls,
and operational evidence before broader enablement.

## Consequences

Positive:

- Mail credentials and recipient policy are centralized instead of copied into workspaces.
- Delivery retries, deduplication, audit records, and preference changes have one operational
  owner.
- Local runners stay provider-neutral and carry only scoped reporting credentials.
- A single hosted view can present sanitized status across explicitly enrolled workspaces.
- Network outages degrade to delayed reporting because the local durable outbox remains intact.

Negative:

- Tool Shed gains an optional stateful companion service with authentication, storage, retention,
  backup, monitoring, abuse protection, and key-rotation responsibilities.
- Hosted notification depends on network availability and may be delayed while events remain in a
  local outbox.
- Sanitization, tenancy isolation, authenticated UI access, and deletion policy become security
  and privacy requirements.
- The local and hosted protocol must remain version-compatible across independently upgraded
  installations.
- The public hostname needs routing that preserves independent rollback of the documentation site
  and backend.

## Alternatives Considered

- **Send mail directly from every workspace.** Rejected as the primary path because it distributes
  secrets and duplicates recipient configuration, retries, and audit behavior.
- **Use only project-native notification adapters.** Retained as an extension point, but rejected
  as the sole design because it provides no consistent default or consolidated status.
- **Host status centrally but keep email local.** Rejected because it keeps the most sensitive and
  operationally inconsistent part of notification in every workspace while already requiring a
  hosted event path.
- **Make the hosted service authoritative for watcher state.** Rejected because local task evidence
  must remain authoritative and workspaces must tolerate hosted outages.

## Supersession Notes

This ADR does not supersede an earlier decision. When implementation settles the protocol and
deployment boundary, promote the current operating contract into product and operator
documentation while retaining this ADR as decision history.
