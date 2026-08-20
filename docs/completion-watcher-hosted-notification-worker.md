# Completion Watcher Hosted Notification Worker (Pilot v1)

Status: active
Type: doc
Updated: 2026-08-19
Next Action: map bounded concurrency/retry implementation to backend runtime
Campaign: build-hosted-watcher-status-and-email-pilot
Parent: work/maps/map-disposable-completion-watchers-and-hosted-notifications.md

## Purpose

Define bounded notification worker behavior for campaign `039`:
reliable delivery attempts from hosted terminal events, deterministic de-duplication, and clearly bounded
failure/poison outcomes without local secret leakage.

## Worker contract

1. Poll/claim loop reads terminal events in `QUEUED`, `ACKED`, or `RETRY_PENDING`.
2. Claiming writes a short `worker_state` record scoped to worker identity.
3. Before sending, worker re-checks `terminal_events.state`:
   - `DELIVERED` or `FAILED_PERMANENT` are terminal and skipped.
   - non-terminal events continue processing.
4. Attempt email send through configured server profile.
5. Persist one `notification_attempts` row per attempt and reconcile terminal state.

## Concurrency model

- `max_concurrent_workers` (pilot default: `2`) and `max_concurrent_sends` (pilot default: `4`) are
  config-gated.
- Polling and claiming are lease-aware; each in-flight event is claimed by at most one worker run.
- At most `max_concurrent_sends` attempts can be active for one worker process.
- If worker count is below concurrency target, no event is processed by more than one worker.

## Deterministic de-duplication

- An event can be sent only once for each `event_id`:
  - if `attempt_number = 1` already exists, `attempt_number` starts at 2.
  - existing attempts do not reset event dedupe state.
- Replay calls are allowed only if event state is `RETRY_PENDING` and policy budget remains.
- `idempotency_key` is immutable for the event and used for all downstream correlation.

## Retry schedule

- Retry states:
  - `ACKED` → immediate queue admission
  - `PROCESSING` → in-flight
  - `RETRY_PENDING` → delayed requeue
  - `DELIVERED` → terminal success
  - `FAILED_PERMANENT` → terminal failure
- Retry backoff function is bounded and deterministic:
  - attempt 1: 15 seconds
  - attempt 2: 60 seconds
  - attempt 3: 5 minutes
  - attempt 4: 15 minutes
  - attempt 5+: 60 minutes cap
- Retries stop at `retry_count >= 20` OR explicit `provider_permanent_failure`.
- Retry budget and next attempt are written to `terminal_events.retry_count` and
  `terminal_events.retry_at`.

## Poison and terminal failure handling

- Transition to `FAILED_PERMANENT` for:
  - provider permanent failure codes (e.g., invalid recipient domain, hard rejection),
  - repeated provider timeout after max retries,
  - repeated malformed payload replays for same event after retries are exhausted.
- `FAILED_PERMANENT` writes:
  - `status=failed_permanent` in `notification_attempts`,
  - `state=FAILED_PERMANENT` in `terminal_events`,
  - bounded error code/detail and operator-visible status fields.

## No local secret ingress

- Worker runtime must never receive or persist:
  - client recipient list,
  - SMTP credentials,
  - local auth tokens.
- Recipient and provider config is server-side only and only injected from worker-local secure config.

## Recovery behavior

- If worker process dies mid-send:
  - claim heartbeat expires after configured TTL,
  - another active worker may claim the event if retry state permits.
- On restart:
  - resume scanning `RETRY_PENDING`, `ACKED`, `PROCESSING` safely,
  - do not send if an attempt already succeeded (`DELIVERED`).
- Startup reconciliation includes stale claim detection and safe resumption of in-flight events.

## Operator visibility

- Worker emits bounded structured events:
  - `worker.started`, `worker.failed`, `worker.recovered_stale_claim`,
  - `send.attempt`, `send.succeeded`, `send.failed`, `send.permanent_failure`,
  - `event.replayed`, `event.skipped_terminal`.
- Every emission includes `request_id`, `event_id`, `workspace_id`, and `retry_count`.

## Minimal implementation sequence (pilot)

1. Add worker state claim+heartbeat loop.
2. Add deterministic bounded claim queue and de-dupe checks.
3. Add retry state machine and backoff function.
4. Add terminal/potentially-poison transitions and audit outputs.
5. Add runbook hooks for scaling and operational visibility.
