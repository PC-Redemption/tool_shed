# Ticket: Implement Privacy-Safe Workspace Performance Profiler

Status: complete
Type: ticket
Updated: 2026-08-03
Next Action: none
Parent: work/maps/map-tool-shed-evolution.md
Canonical Truth: docs/workspace-performance-profiling.md

## Problem

Tool Shed can identify risky repository composition, generated evidence, and planning drift, but it
cannot measure which repository operations slow as `work/` history matures. There is no sanitized,
repeatable report suitable for comparing approved workspaces or controlled fixtures.

## Expected Behavior

A read-only local profiler reuses existing preflight concepts, aggregates Tool Shed work lifecycle
data, and times representative filesystem, Git, and Tool Shed operations. It emits the version 1
schema and enforces the privacy and benchmark protocol defined in
`work/spikes/spike-workspace-performance-profiling-and-fleet-measurement.md`.

Profiling, saved-report collection, and snapshot updating remain separate commands and separate
authorizations. The first implementation contains no network or fleet-update capability.

## Acceptance Criteria

- [x] JSON and human output derive from one versioned in-memory report model.
- [x] Saved JSON contains no file names, paths, repository or host identifiers, branch/remotes,
  commit IDs, environment variables, command output, artifact prose, or per-file hashes.
- [x] An allowlist serializer rejects unknown fields and tests use sensitive-looking fixture names
  to prove they do not leak.
- [x] Existing workspace-preflight metrics are reused or shared rather than independently
  reimplemented with divergent definitions.
- [x] Work artifacts are aggregated by known lifecycle, kind, age bucket, count, and bytes without
  retaining titles or paths.
- [x] Timed probes cover tracked inventory, tracked-only status, status with untracked discovery,
  filesystem inventory, artifact parsing, stale-path review, and work-state review.
- [x] Probes use monotonic timing, a configurable round count and timeout, randomized repeated
  order with a recorded seed, and stable `ok`, `timeout`, `unsupported`, or `error` statuses.
- [x] The tool labels its first observation accurately and does not flush operating-system caches.
- [x] Profiling follows neither symlinks nor filesystem mount boundaries.
- [x] Tests prove the profiler leaves fixture contents, Git index/status, and file metadata
  unchanged.
- [x] Disposable scaling fixtures independently vary completed-artifact count and generated or
  untracked evidence count without committing bulk evidence to this repository.
- [x] Documentation explains that correlation cannot prove undocumented Codex hashing/indexing and
  that profile, collect, update, and cleanup require separate authorization.
- [x] A local canary report is reviewed before any fleet collection or snapshot rollout is proposed.

## Verification

- Focused unit tests cover schema validation, privacy redaction, timeout/error handling,
  percentile calculation, lifecycle aggregation, mount/symlink boundaries, and read-only behavior.
- Scaling tests exercise at least 0, 100, 1,000, and 5,000 completed-artifact fixtures while
  keeping other variables constant, plus a separate evidence-count matrix.
- `python3 scripts/validate_tool_shed.py` passes.
- `python3 scripts/check_stale_paths.py --workspace .` passes.
- `python3 scripts/review_work_state.py --workspace .` reports no finding introduced by this ticket.

## Delivery Evidence

- Implementation: `scripts/profile_workspace_performance.py`
- Focused tests: `tests/test_workspace_performance.py`
- Operator contract: `docs/workspace-performance-profiling.md`
- Full unit suite: 61 tests passed on 2026-08-03.
- Local canary: five repeated rounds, all seven probes `ok`, no warning codes, and no saved
  workspace-path leakage. The report was written outside the repository and is not versioned.
- Fleet collection and snapshot rollout remain unimplemented and separately approval-gated.
