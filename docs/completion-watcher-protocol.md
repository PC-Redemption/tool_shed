# Completion Watcher Protocol v1

Status: accepted design contract with local alpha implementation completed.

Tool Shed completion watchers observe one immutable external target at a one-minute cadence, write
one durable terminal event, and retire without keeping an AI turn open. Local state is
authoritative. Hosted status and email are optional advisory adapters.

This document is normative for protocol version 1. The machine-readable schemas are under
`schemas/completion-watcher/v1/`; the executable oracle and fixtures are in
`tests/test_completion_watcher_contract.py` and `tests/fixtures/completion-watcher-v1/`.
Hosted service behavior is intentionally advisory and bounded to M4; see
`docs/completion-watcher-hosted-api-contract.md` for the outbound terminal-event and status API
shape for the pilot.

## Guarantees and boundaries

Version 1 guarantees:

- one immutable target identity per watch;
- exactly four checker-result states: `WAITING`, `SATISFIED`, `TERMINAL_UNSATISFIED`, and
  `CHECK_ERROR`;
- a fixed default and minimum polling interval of 60 seconds;
- no task failure inferred from elapsed duration, a stale reporter, or a hosted outage;
- durable local terminal enqueue before watcher retirement;
- a deterministic idempotency key for all terminal paths of one watch;
- singleton runner ownership plus recoverable per-watch claims;
- bounded missing-target and checker-error handling;
- explicit cancellation and inconclusive administrative retirement semantics;
- local-only operation when notification is disabled or the hosted service is unavailable.

Version 1 does not guarantee sub-minute notification, automatic restart after reboot without an
authorized recovery hook, uninterrupted operation across filesystem failure, or exactly-once
email receipt. It provides durable, idempotent event processing; a downstream mail provider can
still accept a request and produce an ambiguous delivery result.

The protocol does not authorize remote task control. Hosted components cannot execute, cancel,
restart, approve, or change local work.

## Versioned payloads

Every persisted or exchanged payload is UTF-8 JSON. Writers emit canonical JSON for digest and
idempotency calculations: object keys sorted lexicographically, no insignificant whitespace, and
UTF-8 characters preserved. Readers reject unknown top-level fields in version 1.

### Watch descriptor

`watch-descriptor.schema.json` defines immutable intent. Important fields are:

| Field | Contract |
| --- | --- |
| `watch_id` | Canonical lowercase UUIDv4, generated once and never reused. |
| `workspace` | Safe local ID and human-facing alias; neither is a credential. |
| `target` | Exact `kind`, immutable `id`, and optional immutable `generation`. |
| `checker.argv` | Direct argument vector; never evaluated through a shell. |
| `checker.timeout_seconds` | 1–55 seconds; default for callers is 30. |
| `checker.credential_profile` | Optional local reference; never a secret value. |
| `policy.poll_interval_seconds` | Exactly 60 in v1. |
| `policy.missing_grace_checks` | Default 3; permitted range 1–10. |
| `policy.max_consecutive_check_errors` | Default 5; permitted range 1–20. |
| `policy.claim_lease_seconds` | Default 180; permitted range 60–900. |
| `policy.idle_exit_scans` | Exactly 2 in v1. |
| `notification` | `none`, `project`, or `hosted`, with a local profile for configured adapters. |

The descriptor cannot contain environment-variable values, access tokens, mail credentials,
recipient addresses, arbitrary stdout/stderr, or private evidence. A project adapter may resolve a
named credential profile locally at invocation time. Hosted payloads never receive the checker
command, working directory, or credential profile.

The runner launches the argument vector with no stdin and no shell. The checker must exit zero and
write exactly one checker-result JSON object to stdout, bounded to 64 KiB. Nonzero exit, timeout,
missing output, extra non-whitespace output, invalid UTF-8, malformed JSON, unsupported version, or
schema failure is a synthesized `CHECK_ERROR`. Stderr is bounded for local diagnostics and is
neither persisted in terminal events nor uploaded.

### Runtime watch record

`watch-record.schema.json` wraps the immutable descriptor with mutable counters, due time, claim
metadata, and retirement linkage. `descriptor_sha256` is the SHA-256 digest of the canonical
descriptor. Any digest mismatch is corruption and must fail closed; the runner does not repair or
reinterpret the descriptor.

Runtime lifecycle states are:

- `PENDING`: due or waiting for a future `due_at`;
- `CLAIMED`: owned by one runner instance until completion or recovery;
- `RETIRING`: a terminal event exists durably and the watch record can be removed safely.

`missing_streak`, `error_streak`, and `checker_attempts` are durable counters. A valid
`WAITING`, `SATISFIED`, or `TERMINAL_UNSATISFIED` observation resets both error streaks before any
terminal action. A non-missing `CHECK_ERROR` resets `missing_streak` and increments
`error_streak`. A transient missing target increments both.

### Checker result

`checker-result.schema.json` is the only valid checker stdout shape.

| State | Required evidence | Runner action |
| --- | --- | --- |
| `WAITING` | Exact identity confirmed, target exists, authoritative source says nonterminal. | Reset error streaks and schedule no earlier than 60 seconds after this attempt began. |
| `SATISFIED` | Exact identity confirmed and the desired condition is authoritative. | Durably enqueue `SATISFIED`, then retire. |
| `TERMINAL_UNSATISFIED` | Exact identity confirmed and failure, cancellation, preemption, or supersession is authoritative. | Durably enqueue the matching diagnostic terminal event, then retire. |
| `CHECK_ERROR` | No authoritative task conclusion. | Apply bounded missing/error policy. |

The complete v1 checker reason taxonomy is:

- `WAITING`: `TARGET_NONTERMINAL`;
- `SATISFIED`: `TARGET_SUCCEEDED`, `CONDITION_MET`;
- `TERMINAL_UNSATISFIED`: `TARGET_FAILED`, `TARGET_CANCELLED`, `TARGET_PREEMPTED`,
  `TARGET_SUPERSEDED`;
- `CHECK_ERROR`: `TARGET_MISSING_TRANSIENT`, `SOURCE_UNAVAILABLE`, `CHECKER_INTERNAL`.

The returned `target` must equal the descriptor target byte-for-byte after JSON decoding. A
mismatch is a runner-synthesized check error and cannot make the watch follow a replacement target.

`WAITING` is invalid unless all three evidence booleans are true. A checker cannot use `WAITING`
for a missing record, an unverified alias such as “current run,” a stale cached state, or a source
outage.

### Terminal event

`terminal-event.schema.json` is the durable local outbox payload. Its safe fields are copied from
the descriptor and checker result; command lines, local paths, credential profiles, and raw output
are excluded.

For watch ID `W`:

```text
event_id = hex(sha256(UTF8("tool-shed-watch-terminal-v1\0" + W)))
idempotency_key = "watch-terminal-v1:" + event_id
```

Every terminal route for the same watch uses this one key. A conflicting second event for that key
is corruption, not a new delivery.

Terminal classes and reasons are:

| Terminal class | Valid reason codes |
| --- | --- |
| `SATISFIED` | `TARGET_SUCCEEDED`, `CONDITION_MET` |
| `TERMINAL_UNSATISFIED` | `TARGET_FAILED`, `TARGET_CANCELLED`, `TARGET_PREEMPTED`, `TARGET_SUPERSEDED`, `TARGET_MISSING_AFTER_GRACE` |
| `CHECK_ERROR_EXHAUSTED` | `CONSECUTIVE_CHECK_ERRORS_EXHAUSTED` |
| `WATCH_CANCELLED` | `OPERATOR_CANCELLED_WATCH` |
| `RETIRED_WITHOUT_CONCLUSION` | `ADMINISTRATIVE_RETIREMENT` |

`CHECK_ERROR_EXHAUSTED`, `WATCH_CANCELLED`, and `RETIRED_WITHOUT_CONCLUSION` describe the watcher,
not an authoritative failure of the target.

## Failure policy

The default missing-target grace is three consecutive due checks. Checks occur no earlier than 60
seconds apart, so a default missing target is not retired until the third separate observation.
Any valid observation of the exact target resets the missing streak. After grace is exhausted, the
runner emits `TERMINAL_UNSATISFIED / TARGET_MISSING_AFTER_GRACE`; the detail must say that the target
could not be found after grace, not that it failed.

The default checker-error budget is five consecutive errors. Timeout, abnormal exit, malformed
output, unsupported schema, identity mismatch, local invocation failure, and checker-reported
`CHECK_ERROR` all consume this budget. A valid authoritative result resets it. On exhaustion, the
runner emits `CHECK_ERROR_EXHAUSTED / CONSECUTIVE_CHECK_ERRORS_EXHAUSTED` and retires without a task
conclusion.

Missing-target exhaustion is evaluated before general error exhaustion when the same observation
reaches both thresholds.

`review_after` is advisory housekeeping. Crossing it may surface status but never changes the
checker result or infers failure. `administrative_retire_after` only makes retirement eligible; an
operator or explicit policy action must request retirement, which emits
`RETIRED_WITHOUT_CONCLUSION`. There is no task-duration hard expiration.

## Durable filesystem layout

The default per-user state roots are:

- Linux: `$XDG_STATE_HOME/tool-shed/watchers/v1`, falling back to
  `$HOME/.local/state/tool-shed/watchers/v1`;
- Windows: `%LOCALAPPDATA%\ToolShed\watchers\v1`.

An override must be an absolute local path and pass the same ownership, link, and permission
checks. Network shares are unsupported in v1 because lock and atomic-replace guarantees vary.

```text
v1/
  format.json
  runner/
    singleton.lock
    heartbeat.json
  watches/
    pending/<watch_id>.json
    claimed/<watch_id>.json
  cancel/<watch_id>.json
  outbox/
    pending/<event_id>.json
    claimed/<event_id>.json
    receipts/<event_id>.json
  history/<watch_id>.json
  tmp/
```

All new files are written to a unique file under `tmp/`, flushed, and atomically replaced into
their destination on the same filesystem. POSIX implementations also flush the containing
directory where supported. The implementation must not claim power-loss durability when the host
filesystem or platform cannot provide it.

Arming writes a complete `PENDING` record before publishing it to `watches/pending/`. Claiming is
an atomic rename to `watches/claimed/`, followed by an atomic record update containing the runner
UUID and lease. A claimed file without valid claim metadata is recoverable corruption, never a
reason to discard the watch.

For a terminal observation, ordering is mandatory:

1. Construct the deterministic terminal event.
2. If `outbox/pending`, `outbox/claimed`, or `outbox/receipts` already contains the same event ID,
   verify identical content; never create a second event.
3. Persist and flush the event under `outbox/pending/`.
4. Persist the watch as `RETIRING` with `terminal_event_id`.
5. Remove the claimed watch and write bounded local history.
6. Deliver through the selected adapter independently.

A crash at any point replays these steps idempotently. In particular, a crash after step 3 and
before step 5 cannot trigger a second event or email job.

Receipts are compact adapter acknowledgements and may be retention-bounded. They do not replace
the adapter's durable audit. Local history must not retain raw checker output.

## Singleton runner, claims, and reboot

The singleton lock is an operating-system advisory lock held for the lifetime of the runner:
`flock` on Linux and `LockFileEx` on Windows. A PID file or heartbeat alone is never proof of
ownership. `ensure-runner` behaves as follows:

- held lock: do not start another runner, even when heartbeat is stale;
- free lock and no pending/claimed/outbox work: do nothing;
- free lock with work: acquire it and start one runner.

The runner publishes a bounded heartbeat for diagnostics. Once a new runner owns the singleton
lock, claims naming another runner instance are recoverable immediately; it need not trust a
wall-clock lease left across a crash or reboot. While the owning runner is alive, a claim becomes
recoverable after `lease_until`. Recovery first checks the deterministic outbox key, so an already
enqueued terminal event proceeds to retirement rather than running the checker again.

The runner scans due work once per minute and does not run a watch before its `due_at`. Processing
many watches or slow checkers may delay a check; the 60-second cadence is a lower bound, not a
real-time deadline. The runner exits after two consecutive scans find no pending watches, claimed
watches, cancellation requests, or undelivered outbox events.

A detached process does not survive reboot or an unexpected kill. Durable files survive, but
automatic recovery requires an existing authorized heartbeat or another Tool Shed invocation to
call `ensure-runner`. Workspaces without that hook must report reboot recovery as unavailable, not
as automatic.

## Cancellation and races

`cancel <watch_id>` atomically publishes `cancel/<watch_id>.json`; it never directly deletes a
watch. The runner resolves races using durable linearization points:

- if a terminal event was durably enqueued first, that terminal outcome wins and cancellation
  reports “already terminal”;
- if the cancellation request was published first, the checker result is ignored and the runner
  enqueues `WATCH_CANCELLED / OPERATOR_CANCELLED_WATCH`;
- cancellation of the watch does not cancel the external target and must not be described as
  target cancellation.

`TARGET_CANCELLED` is reserved for authoritative evidence that the external target itself ended in
a cancelled state.

## Permissions and security

On POSIX systems, the state root and directories must be owned by the current user and mode `0700`;
files must be `0600`. The runner refuses group/world-writable roots, ownership mismatch, symlinks,
or link traversal. On Windows, the default root must inherit a current-user-only profile ACL; the
platform adapter must verify the effective ACL and reject reparse points before processing state.
If ownership or ACL verification is unavailable, arming fails closed rather than weakening the
contract.

The runner does not execute a descriptor owned by another user, follow links, invoke a shell, pass
mail credentials to a checker, or send raw local data to a hosted adapter. Hosted reporting is
outbound HTTPS, opt-in, authenticated with a separately stored per-workspace credential, bounded,
sanitized, idempotent, and advisory.

## Upgrade and downgrade behavior

`v1/format.json` declares the state format before any watch is armed. A runner that sees an unknown
major format, unknown record version, unknown schema version, or unknown field fails closed and
leaves all state untouched. It may report the incompatibility but may not delete, rewrite, or
deliver an event from data it cannot interpret.

Future migrations must stage a verified copy, transform atomically, and retain rollback material.
An older Tool Shed release that predates watchers simply leaves the per-user state directory
untouched. Downgrading while v1 watches or outbox events remain pending is unsupported until they
are drained or a compatible v1 runner is restored; it must never be represented as data loss-free
automatic downgrade.

## Implementation gate

Milestone M2 may implement the local alpha only if it conforms to this contract and keeps the
machine-readable fixtures passing. The implementation must add failure-injection coverage for
atomic arming, duplicate runner attempts, concurrent watches, every checker state, missing grace,
error exhaustion, cancellation races, crash after outbox enqueue, claim recovery, idle exit,
outbox replay, Linux permissions and locks, Windows ACLs and locks, and degraded reboot recovery.

Hosted API shape, tenancy, storage, UI authentication, retention, mail provider, deployment, and
production operations remain later roadmap decisions. M1 fixes only the local-to-adapter event
boundary needed to prevent those choices from changing local watcher correctness.
