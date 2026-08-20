# Checklist: Hosted watcher status and email pilot

Status: active
Type: checklist
Updated: 2026-08-19
Next Action: execute the checklist
Campaign: build-hosted-watcher-status-and-email-pilot
Parent: work/roadmaps/roadmap-completion-watcher-program.md
Project Map: work/maps/map-disposable-completion-watchers-and-hosted-notifications.md

## Goal

Deliver the first bounded hosted pilot for completion watchers while preserving local authority, with
advisory status, idempotent event ingestion, and centralized email under explicit authentication and
tenant isolation.

## Checklist

- [x] Publish the bounded hosted API contract:
  - endpoint for terminal event ingestion with versioned schema, deterministic event ID, and duplicate
    rejection,
  - endpoint for advisory status read with redacted / tenant-scoped payloads,
  - endpoint for manual replay/retry requests within bounded limits,
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
- [ ] Implement recovery and resilience checks:
  - outbox retry/replay after service restart,
  - stale reporter behavior (no false local-task conclusions),
  - service outage fallback path that preserves local outbox ownership,
  - rollback plan for backend and static-site deployments that can be executed independently.
- [ ] Recovery and rollout playbook committed to
  `docs/completion-watcher-hosted-recovery-rollout.md` including outage replay, stale-reporter semantics,
  worker restart, and independent backend/site rollback checks.
- [ ] Add security and privacy hardening:
  - credential issuance, rotation, and revocation hooks (manual if needed for pilot),
  - payload redaction controls for sensitive paths / stderr / command text,
  - rate limiting and abuse guardrails for pilot traffic,
  - minimal logging plus audit record retention policy.
- [ ] Run a bounded pilot on the hosted surface:
  - at least one workspace enrollment,
  - terminal events captured and reported without hosted write-back to local state,
  - email path proves exactly once processing is bounded and durable (not exactly-once email delivery claim).
- [ ] Record evidence for each acceptance criterion in a single campaign evidence artifact
  (runtime logs, request IDs, and bounded rollout results).

## Runtime Closeout

- [ ] Service deployment, rollback, and status checks are documented for pilot.
- [ ] Host and static documentation deployments have explicit rollback boundaries.
- [ ] Any temporary local or shared config changes are listed with matching docs or examples.

## Verification

- The checklist is complete when campaign `039` can be moved to complete with evidence pointing to:
  authenticated ingress, idempotent terminal delivery, bounded notification worker behavior, and
  recovery/rollback evidence.
