# Checklist: Hosted watcher status and email pilot

Status: deferred
Type: checklist
Updated: 2026-08-19
Next Action: wait for a named external or non-App-Server workload, service owner, and notification recipient before resuming
Campaign: build-hosted-watcher-status-and-email-pilot
Parent: work/roadmaps/roadmap-completion-watcher-program.md
Project Map: work/maps/map-disposable-completion-watchers-and-hosted-notifications.md

## Goal

Deliver a bounded hosted notification companion only for work outside the App Server-controlled
path. Preserve local watcher authority while providing tenant-scoped advisory status, idempotent
terminal-event ingestion, and centralized notification delivery.

The hosted service must not orchestrate execution, detect completion for App Server CAMPs, monitor
App Server turns, retry or recover originating work, manage agent lifecycle, or write back to the
originating workspace.

## Checklist

- [x] Publish the bounded hosted API contract:
  - endpoint for terminal event ingestion with versioned schema, deterministic event ID, and duplicate
    rejection,
  - endpoint for advisory status read with redacted / tenant-scoped payloads,
  - idempotent acknowledgement so the sender-owned local outbox can replay safely,
  - clear authentication error behavior and 401/403/404 semantics.
- [x] Add a minimal, auditable datastore path for hosted pilot:
  - durable terminal-event table/collection with idempotency key constraints,
  - delivery attempts and worker state,
  - retention and deletion policy that preserves a bounded audit window.
- [x] Datastore design committed to
  `docs/completion-watcher-hosted-datastore.md` with terminal-event dedupe, retry attempts, worker
  state heartbeat, and bounded TTL retention rules.
- [ ] Implement notification worker behavior:
  - bounded concurrent send loop,
  - deterministic de-duplication by event key,
  - bounded retry schedule with terminal state and poison-case handling,
  - no local secrets or recipient lists passed from the runner.
- [ ] Worker behavior contract committed to
  `docs/completion-watcher-hosted-notification-worker.md` with concurrency, de-duplication, retry
  backoff, failure transitions, and recovery sequence.
- [ ] Implement authenticated status surface:
  - scoped API keys or token exchange model,
  - per-workspace tenancy boundaries on reads and writes,
  - advisory status values aligned to `WATCH`, `SENT`, `RETRYING`, and stale/outage states.
- [ ] Status-surface contract committed to
  `docs/completion-watcher-hosted-status-surface.md` with tenant checks, stale/reporting mapping, and
  advisory status semantics.
- [ ] Implement hosted-delivery resilience checks:
  - outbox retry/replay after service restart,
  - stale reporter behavior (no false local-task conclusions),
  - service outage behavior that preserves local outbox ownership and performs no remote recovery,
  - rollback plan for backend and static-site deployments that can be executed independently.
- [ ] Recovery and rollout playbook committed to
  `docs/completion-watcher-hosted-recovery-rollout.md` including outage replay, stale-reporter semantics,
  worker restart, and independent backend/site rollback checks.
- [ ] Add security and privacy hardening:
  - credential issuance, rotation, and revocation hooks (manual if needed for pilot),
  - payload redaction controls for sensitive paths / stderr / command text,
  - rate limiting and abuse guardrails for pilot traffic,
  - minimal logging plus audit record retention policy.
- [ ] Run a bounded pilot on the hosted surface only after reactivation:
  - at least one named external or non-App-Server workload enrollment,
  - terminal events captured and reported without hosted write-back to local state,
  - email or selected notification path proves bounded durable processing (not exactly-once delivery),
  - no execution, recovery, lifecycle, or workspace-control endpoint exists.
- [ ] Record evidence for each acceptance criterion in a single campaign evidence artifact
  (runtime logs, request IDs, and bounded rollout results).

## Runtime Closeout

- [ ] Service deployment, rollback, and status checks are documented for pilot.
- [ ] Host and static documentation deployments have explicit rollback boundaries.
- [ ] Any temporary local or shared config changes are listed with matching docs or examples.

## Verification

- The checklist is complete when reduced campaign `039` can be moved to complete with evidence from
  a real external/non-App-Server workload covering authenticated ingress, idempotent terminal
  delivery, advisory status, bounded notification behavior, sender-owned replay, and hosted
  rollback. App Server execution evidence does not satisfy this gate.
