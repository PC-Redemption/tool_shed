# Completion Watcher Hosted Datastore Model (Pilot)

Status: active
Type: doc
Updated: 2026-08-19
Next Action: implement API + worker behavior over this data model
Parent: work/maps/map-disposable-completion-watchers-and-hosted-notifications.md
Campaign: build-hosted-watcher-status-and-email-pilot

## Scope

This is the bounded hosted data model for campaign `039` during the hosted pilot stage.
The local watcher remains authoritative for terminal conclusions; the hosted datastore only stores
sanitized advisory projections and delivery state derived from terminal events.

## Data entities

Pilot implementations should provide three durable collections (SQL tables or equivalent):

- `terminal_events` (durable event intake + dedupe source of truth)
- `notification_attempts` (bounded retry history and worker ownership)
- `worker_state` (ephemeral/short-lived worker status with durable heartbeat and concurrency caps)

All collections include:

- `schema_version` fixed to `1`
- `created_at`, `updated_at`, and UTC RFC3339 timestamps
- `tenant_boundary`/`workspace_id` (must match the token scope on writes and reads)
- `request_id` for cross-system traceability

### `terminal_events`

Purpose: single durable representation of each terminal event payload and its notification lifecycle.

Required fields:

- `idempotency_key` (unique): must be exactly `watch-terminal-v1:<event_id>`
- `event_id` (unique): computed terminal-event hash from local contract
- `workspace_id`, `watch_id`
- `terminal_class`, `reason_code`, `state` (`INGESTING`, `QUEUED`, `ACKED`, `PROCESSING`,
  `RETRY_PENDING`, `DELIVERED`, `FAILED_PERMANENT`)
- `retry_count` (0..20)
- `retry_at` and `retry_available_after`
- `redacted_summary`
- `display_name`
- `tenant_boundary`

Constraints:

- `(idempotency_key)` is a hard uniqueness key.
- `terminal_events.state` transitions are monotonic and bounded by deterministic worker logic.
- Duplicate ingest for the same `idempotency_key` must return the first stored snapshot and must
  reject schema-matching but payload-conflicting requests with conflict response.

### `notification_attempts`

Purpose: auditable retry and failure history for each attempted send.

Required fields:

- `attempt_id` (unique)
- `event_id` (foreign key to `terminal_events`)
- `workspace_id`
- `provider` (`smtp`, `mailer`, `test`)
- `attempt_number` (1-indexed)
- `scheduled_at`, `attempted_at`
- `status` (`queued`, `in_progress`, `sent`, `failed`, `poison`, `permanent_failure`)
- `error_code`, `error_detail`
- `message_id` (if available from provider)

Constraints:

- `(event_id, attempt_number)` should be unique to prevent accidental duplicate retry rows.
- `attempt_number` MUST increase sequentially per event for audit completeness.
- Keep attempts for `DELIVERED` and `FAILED_PERMANENT` until terminal event cleanup allows removal.

### `worker_state`

Purpose: bounded visibility into worker lifecycle, concurrency, and recovery behavior.

Required fields:

- `worker_id` (unique)
- `hostname`
- `version`
- `started_at`, `last_heartbeat_at`
- `inflight_limit`
- `inflight_count`
- `status` (`starting`, `running`, `draining`, `degraded`, `stopped`)
- `last_checkpoint` (last reconciled cursor or equivalent marker)

Constraints:

- Heartbeat is required at least once every `retry_backoff_max`.
- A failed heartbeat for `heartbeat_ttl` marks worker stale; unclaimed queued events remain available to
  another active worker only when configured for >1 active workers.

## Retention and deletion policy

This bounded pilot keeps an auditable trail without becoming permanent data hoarding:

- `terminal_events`: keep for **30 days** after `state` becomes terminal (`DELIVERED` or
  `FAILED_PERMANENT`), unless extended manually for pilot incident review.
- `notification_attempts`: keep for **30 days**; failures are kept no longer than `terminal_events`.
- `worker_state`: keep for **48 hours**, then compact to current status only.
- `audit_log` (append-only service log, if persisted separately): keep for **30 days**.

Deletion policy:

- Deletions are TTL-style, batched, and idempotent.
- A deletion sweep must emit an audit row with:
  - policy version
  - cutoff timestamps
  - affected row count by collection
  - requester id and confirmation timestamp
- Deletion never removes unresolved terminal events or active `notification_attempts`.

## Privacy and minimization

- No checker argv, repository path, raw stdout/stderr, private secrets, or recipient lists are
  stored.
- `redacted_summary` is capped to 512 chars and should avoid PII markers.
- Any schema-valid but non-compliant payload must be redacted to policy before persistence.

## Cross-link

- API contract: `docs/completion-watcher-hosted-api-contract.md`
- Local protocol: `docs/completion-watcher-protocol.md`
- Relevant schemas:
  - `schemas/completion-watcher-hosted/v1/terminal-event-snapshot.schema.json`
  - `schemas/completion-watcher-hosted/v1/watch-status.schema.json`
