# Completion Watcher Hosted Recovery and Rollback Plan (Pilot)

Status: active
Type: doc
Updated: 2026-08-19
Next Action: convert these controls into deployment and operator runbooks
Parent: Tool Shed document MAP-0002
Campaign: build-hosted-watcher-status-and-email-pilot

## Scope

Bounded pilot recovery behavior for hosted service outages, local fallback, and independent rollback of the
backend and static site.

## Recovery behavior

1. **Service outage while terminal events are sent**
   - Local runners continue to emit terminal events and retry against `terminal_events` idempotency.
   - Failed HTTP calls are represented as `RETRY_PENDING` with bounded `retry_after`.
   - Local state and outcomes remain authoritative and unchanged.
2. **Service outage after terminal admission**
   - Persisted event remains in datastore by idempotency key.
   - Retry remains bounded by policy until service returns or budget is exhausted.
3. **Worker restart**
   - Worker resumes from `terminal_events` + `notification_attempts`.
   - Claims are re-evaluated for staleness and safe transition only to retriable states.
4. **Local runner stale/outage**
   - Local stale reporter marks `status=stale` only in hosted status; local watchers keep local truth.

## Outbox replay checks

- A restart recovery test must prove:
  - terminal event remains retained and deduplicated after crash,
  - duplicate outbox events are not re-sent as additional attempts,
  - failed attempts can rehydrate and continue according to retry policy.

## Rollback strategy: backend and static documentation

Keep backend and static documentation deployment independently reversible:

- **Backend rollback**
  - Deployments are versioned; rollback target must be the last healthy backend image.
  - Rollback runbook includes:
    - verify database migration compatibility,
    - drain active workers to avoid duplicate claim,
    - clear stale in-memory locks,
    - confirm 401/403 behavior for revoked tokens still works.
- **Static-site rollback**
  - Deploy docs independently.
  - Ensure `docs/completion-watcher-hosted-api-contract.md` and status pages remain consistent with
    active backend schema/version.

## Operational boundaries

- Any rollback must preserve local workspace autonomy.
- No local runner receives new secrets or endpoint credentials from rollback step.
- Evidence from rollback/recovery actions must include:
  - timestamp,
  - operator,
  - before/after health summary,
  - data retention impact (if any),
  - verification checks executed.

## Minimal rollout checks

Before campaign evidence acceptance:

- one workspace enrollment path simulated end-to-end,
- at least one outage simulation (ingest success + retry path),
- one service recycle with in-flight event recovery,
- independent rollback of static/site + backend validated.
