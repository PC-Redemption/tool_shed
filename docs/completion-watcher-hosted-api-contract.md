# Completion Watcher Hosted API Contract (Pilot v1)

Status: draft
Type: doc
Updated: 2026-08-19
Next Action: align local runner reporter with this bounded API contract

This document defines the minimum hosted API surface for the M4 hosted pilot.

## Service Boundary

- Local watcher runners remain authoritative for terminal decisions.
- The hosted API is advisory and receives only outbound terminal events.
- The service stores and serves advisory state for enrolled workspaces and sends centralized email.
- This contract is production-shaped but bounded to the pilot scope.

## Shared Versioning

All payloads use `schema_version: 1`.

## Authentication

- `Authorization: Bearer <token>` is required for all hosted endpoints.
- Bearer tokens are workspace-scoped and capability-scoped:
  - `watch:read`
  - `event:ingest`
  - `event:replay`
- Response codes:
  - `401` missing/invalid token
  - `403` token without required capability
  - `404` unknown tenant / workspace / watch

### Scope Invariant

- A token must match the `workspace_id` on every request.
- A token may never create, update, or delete local watcher state.

## Endpoints

Base path: `/api/v1`

### 1) Ingest terminal event

`POST /api/v1/terminal-events`

- Headers:
  - `Authorization: Bearer <token>`
  - `Idempotency-Key: watch-terminal-v1:<event_id>`
  - `Content-Type: application/json`
- Body: `schemas/completion-watcher-hosted/v1/hosted-terminal-event-ingest.schema.json`
- Behavior:
  - If the idempotency key exists, return current stored state with identical payload required.
  - If conflict, return `409` with a bounded conflict payload.
  - On success:
    - persist event snapshot,
    - enqueue delivery job,
    - return advisory status for the terminal event.
- Response:
  - `201 Created` on first acceptance
  - `200 OK` on replay of same idempotency key
  - Body:
    - `{
        "schema_version":1,
        "event_id":"...64 hex...",
        "status":"accepted|dup",
        "notification_state":"pending|queued",
        "retry_after": "2026-08-19T...",
        "retry_count": 0,
        "links": [...]
      }`

### 2) Read advisory watch status

`GET /api/v1/workspaces/{workspace_id}/watches/{watch_id}`

- Token capability required: `watch:read`
- Response body must follow:
  - `schemas/completion-watcher-hosted/v1/watch-status.schema.json`
- Includes:
  - redacted/tenant-safe status metadata,
  - notification delivery state,
  - retry and stale indicators when applicable.
- Status semantics and status-to-business mapping are defined in
  `docs/completion-watcher-hosted-status-surface.md`.

### 3) Manual replay

`POST /api/v1/workspaces/{workspace_id}/watches/{watch_id}/replay`

- Token capability required: `event:replay`
- Body: `schemas/completion-watcher-hosted/v1/replay-request.schema.json`
- Limits:
  - bounded and scoped retries only,
  - bounded replay rate per workspace,
  - rejected when retry budget is exhausted with `409`.

### 4) Health and readiness

`GET /api/v1/health`

- Returns basic readiness and dependency checks (`ok`, `degraded`).
- Failure indicates non-empty bounded diagnostics but never affects local truth.

## Error Envelope

All errors return:

```json
{
  "schema_version": 1,
  "error_code": "VALIDATION|AUTH|NOT_FOUND|CONFLICT|RATE_LIMIT|DEPENDENCY",
  "message": "brief reason",
  "request_id": "uuid",
  "retry_after": "2026-08-19T..."
}
```

`request_id` is logged at every layer for support correlation.

## Security and Privacy Rules

- No local file paths, checker argv, or secrets are ingested.
- No recipient list, SMTP credentials, or provider secrets are accepted from clients.
- Outbound payload fields may not exceed:
  - `display_name`: 120 chars
  - `redacted_summary`: 512 chars
- Sensitive payloads are sanitized before persistence.
- `tenant_boundary` must match token scope.

## Retry and Outbox Behavior

- Outbox updates are durable and idempotent by idempotency key.
- Retry policy is bounded, stateful, and visible in status.
- `INGESTING -> QUEUED -> PROCESSING -> DELIVERED` is the normal happy path.
- Permanent failure path records `FAILED_PERMANENT` and returns bounded error details.
- Worker behavior, bounded concurrency, retry backoff, and poison-case transitions are defined in
  `docs/completion-watcher-hosted-notification-worker.md`.

## Datastore and Retention Path

- Hosted state is persisted in a bounded pilot datastore with these logical entities:
  - `terminal_events`
  - `notification_attempts`
  - `worker_state`
- The canonical pilot shape is defined in:
  - `docs/completion-watcher-hosted-datastore.md`
- Retention is bounded:
  - `terminal_events` and `notification_attempts`: 30 days from terminal state.
  - `worker_state`: 48 hours.
- Deletions are TTL-batched and auditable with policy version and affected-row counts.

## Stale Reporter Semantics

- A watch or notification worker that stops reporting can be marked stale.
- Staleness does not mark the underlying local task as failed.

## Boundaries

- No remote control, no task cancellation, no local runner restart commands.
- No authoritative claim over local watch lifecycle; this API never changes local outcomes.

## Related artifacts

- ADR: `work/adr/adr-centralize-watcher-email-delivery-at-ts-rookaro-com.md`
- Local contract: `docs/completion-watcher-protocol.md`
- Campaign: `work/00-campaigns/active/039-build-hosted-watcher-status-and-email-pilot.md`
- Workspace schemas: `schemas/completion-watcher-hosted/v1/*.json`
