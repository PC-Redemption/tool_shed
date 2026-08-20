# Spike: Completion watcher protocol and failure model

Status: complete
Type: spike
Updated: 2026-08-18
Next Action: none
Parent: work/maps/map-disposable-completion-watchers-and-hosted-notifications.md
Campaign: define-completion-watcher-protocol-and-failure-model
Disposition: documented
Produces: docs/completion-watcher-protocol.md

## Question

What exact portable contract lets a disposable watcher distinguish legitimate waiting from target
completion, unsuccessful terminal outcomes, checker faults, missing targets, cancellation, and
crash recovery without making hosted infrastructure authoritative?

## Timebox

One roadmap campaign. Produce the v1 schemas, lifecycle and storage decisions, platform oracle,
and focused executable fixtures. Do not implement the runner, detached-process adapters, or hosted
service.

## Findings

- A watch binds once to a canonical UUIDv4 and an immutable target `kind`, `id`, and optional
  `generation`; a checker result with another identity is a bounded check error.
- `WAITING` is valid only when the exact target exists and an authoritative source confirms it is
  nonterminal. Elapsed duration and reporter staleness never prove failure.
- Version 1 fixes a 60-second minimum cadence, three-check missing grace, five-error default
  checker budget, 180-second claim lease, and two empty scans before runner exit.
- Checker stdout is one bounded versioned JSON object. Shell invocation, stdin, arbitrary output,
  secrets in descriptors, and raw output in hosted payloads are excluded.
- Terminal enqueue precedes retirement. One deterministic key covers every terminal route for a
  watch, so replay after a crash cannot create a second event or notification job.
- OS advisory locking is authoritative; heartbeat is diagnostic. A new singleton owner can recover
  claims from a prior runner immediately and safely check the outbox before reevaluation.
- Operator watch cancellation and authoritative target cancellation are distinct terminal reasons.
  Administrative retirement is explicitly inconclusive.
- Linux uses an owner-only XDG state directory, `0700` directories, `0600` files, and `flock`.
  Windows uses current-user `%LOCALAPPDATA%`, verified user ACLs, link rejection, and `LockFileEx`.
- No reboot recovery is promised unless an existing authorized hook or Tool Shed invocation calls
  `ensure-runner`.
- Unknown format, record, or schema versions fail closed. Downgrade with pending watcher state is
  unsupported until drained or a compatible v1 runner is restored.

## Recommendation

Treat `docs/completion-watcher-protocol.md` and
`schemas/completion-watcher/v1/` as the M2 implementation contract. Keep the test fixtures as the
oracle and add production failure-injection tests without weakening the stated semantics.

## Follow-Up

- [x] Publish settled current truth in `docs/completion-watcher-protocol.md`.
- [x] Add descriptor, runtime record, checker-result, and terminal-event schemas.
- [x] Add valid/invalid fixtures and transition tests for Linux and Windows obligations.
- [x] Leave production runner and hosted implementation to later roadmap milestones.
