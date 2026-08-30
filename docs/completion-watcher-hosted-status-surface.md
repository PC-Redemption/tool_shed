# Completion Watcher Hosted Status Surface (Pilot v1)

Status: active
Type: doc
Updated: 2026-08-19
Next Action: bind status payload to API read path implementation
Parent: Tool Shed document MAP-0002
Campaign: build-hosted-watcher-status-and-email-pilot

## Purpose

Define the authenticated, tenant-scoped advisory status contract used by `GET
/api/v1/workspaces/{workspace_id}/watches/{watch_id}` and campaign readiness checks.

## API semantics

- Read endpoint requires capability `watch:read`.
- Auth token must match `workspace_id` at both path and token scope.
- Missing tokens or mismatched scope return:
  - `401` for missing/invalid token,
  - `403` for capability/scope mismatch,
  - `404` for unknown workspace/watch.
- The endpoint is advisory only and never mutates local watch state.

## Status mapping

The service status is presented in two parallel fields:

- `status` (human/state label):
  - `active`, `terminal`, `stale`, `failed`, `retrying`, `not-found`
- `status_code` (stable machine token):
  - `WATCH_ACTIVE`, `WATCH_TERMINAL`, `WATCH_STALE`, `WATCH_FAILED`, `REPORTING_RETRY`, `WATCH_NOT_FOUND`

Pilot display vocabulary:

- `WATCH` is represented by `status=active` / `status_code=WATCH_ACTIVE`.
- `SENT` maps to terminal successful delivery when `notification_state=delivered`.
- `RETRYING` maps to `status=retrying` / `status_code=REPORTING_RETRY`.
- Stale reporter is represented by `status=stale` / `status_code=WATCH_STALE`.
- Outage fallback is represented by `notification_state` retaining a retry state with bounded
  `error_code`/`error_detail` and request-id trace.

## Output contract fields

Required response fields:

- `schema_version`
- `watch_id`
- `workspace_id`
- `status`
- `status_code`
- `notification_state`
- `updated_at`

Optional fields:

- `display_name`
- `seen_at`
- `retry_count`
- `error_code`, `error_detail`
- `retry_after`

## Notification-state lifecycle

- `pending`: accepted, not yet queued for sending
- `queued`: ready for claim/send
- `acked`: accepted and readying local delivery side effects
- `delivering`: active attempt in progress
- `delivered`: provider accepted and boundedly acknowledged
- `failed_permanent`: no further retry scheduled (explicit poison or budget exhaustion)

The status endpoint should include the latest worker-visible state from `terminal_events` plus latest
`notification_attempts` row so operators can reason about outage vs. definitive failures.

## Tenant and privacy constraints

- Responses must redact workspace identifiers to tenant-scoped form and never include local file paths,
  raw stdout/stderr, checker commands, recipient addresses, or secret metadata.
- A 404 must be indistinguishable from forbidden tenant mismatch to avoid tenant enumeration.
