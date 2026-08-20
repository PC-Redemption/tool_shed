# Completion Watcher v1 Contract Evidence

Status: complete
Type: evidence
Updated: 2026-08-18
Next Action: none
Parent: work/maps/map-disposable-completion-watchers-and-hosted-notifications.md
Campaign: define-completion-watcher-protocol-and-failure-model

## Scope

Evidence for roadmap milestone `M1-CONTRACT` and gate `G1-CONTRACT-ACCEPTED`. This evidence covers
the versioned design contract and executable oracle only. It does not claim a production runner,
native Windows execution, release, deployment, hosted service, or client synchronization.

Target project:

- Project ID: `817b6358-b2f5-48fd-bb66-bd80f936faca`
- Repository: `/home/jon/docker/tool_shed`
- Campaign: `036-define-completion-watcher-protocol-and-failure-model`
- Completed validation observation: `2026-08-19T01:19:35Z`

## Contract coverage

The accepted contract and oracle cover:

- immutable target identity and identity-mismatch failure;
- `WAITING`, `SATISFIED`, `TERMINAL_UNSATISFIED`, and `CHECK_ERROR`;
- authoritative evidence required for `WAITING`;
- fixed 60-second cadence and no elapsed-time task failure;
- three-check missing grace and five-error default checker exhaustion;
- direct no-shell invocation, timeout, malformed output, abnormal exit, and bounded output;
- singleton OS locks, diagnostic heartbeats, claim leases, prior-runner recovery, and idle exit;
- durable terminal outbox ordering, deterministic idempotency, replay, and receipt boundaries;
- target cancellation, operator watch cancellation, and administrative retirement distinctions;
- POSIX ownership/mode/link rules and Windows current-user ACL/`LockFileEx`/reparse-point rules;
- degraded reboot recovery without an existing `ensure-runner` hook;
- unknown-version and pending-state downgrade behavior;
- sanitized optional adapter events with local state remaining authoritative.

## Commands and outcomes

```text
python3 -m unittest tests.test_completion_watcher_contract -v
5 tests passed

python3 scripts/validate_tool_shed.py
162 tests passed; provider conformance, manifest, indexes, stale paths, work state,
roadmaps, disposable installation, templates, and examples passed

python3 scripts/workspace_preflight.py --workspace . --json
No findings
```

The focused suite includes valid and invalid payload checks, transition-table execution, durable
outbox replay, cancellation precedence, missing/error exhaustion, claim recovery, stale-heartbeat
lock behavior, and explicit Linux/Windows platform obligations.

## Versioned artifact hashes

| Artifact | SHA-256 |
| --- | --- |
| `docs/completion-watcher-protocol.md` | `840f5581570c3ce4e93788483b6c49e48fdd21de991ded0a716c5c18b016d0d8` |
| `schemas/completion-watcher/v1/checker-result.schema.json` | `58d00042f132cb7ee656b1190a39ae6f60c26d86a22361cd511bccfcbcb75922` |
| `schemas/completion-watcher/v1/terminal-event.schema.json` | `ea1dc7ba12f788d11f8d74c9a28cea7e01e209d04486a98d82c4f765fc5afbb2` |
| `schemas/completion-watcher/v1/watch-descriptor.schema.json` | `e6b54939fb06111b7a9f687ceb9be281a9e8dc389bdc28a72d9ee3078eb5fe4f` |
| `schemas/completion-watcher/v1/watch-record.schema.json` | `7455db4c2e7a271ec8efbd7b0828143a141dcd1daa55d25540132ab0b53a5b1d` |
| `tests/fixtures/completion-watcher-v1/contract-cases.json` | `630df68e6c49b768037e120ae7772214afb3c6baf85d53c37181feccccfac97d` |
| `tests/test_completion_watcher_contract.py` | `d78f24b6890cbf719ff23e99fe04dfa6dbbf5824d5fbf43c48b18202f58fda2a` |

## Deferred proof

- Native Linux and Windows process lifecycle qualification belongs to M3 after an M2 implementation
  exists; this milestone provides the cross-platform oracle, not runtime proof.
- Detached-process adapters, live filesystem crash injection, and actual reboot recovery belong to
  M2/M3.
- Hosted API, authentication, status UI, email delivery, retention, and deployment belong to M4/M5.
- Tool Shed `0.24.0` is an unreleased development manifest. No tag, push, release, deployment, or
  installed-client synchronization occurred.
