# Spike: Workspace Performance Profiling and Fleet Measurement

Status: complete
Type: spike
Updated: 2026-08-14
Next Action: none
Parent: work/maps/map-tool-shed-evolution.md
Disposition: documented
Produces: work/tickets/ticket-implement-privacy-safe-workspace-performance-profiler.md
Campaign: evaluate-workspace-performance-collector

## Question

What minimum, privacy-safe measurements will distinguish Tool Shed work-history growth from Git
state, generated evidence, and general repository scale as causes of slower Codex workspace work?
How can those measurements be collected across approved Tool Shed workspaces without coupling
profiling permission to report transfer or snapshot updates?

## Timebox

One design session. Define the report contract, privacy boundary, repeatable benchmark protocol,
and staged fleet rollout. Do not implement the profiler, update snapshots, contact remote hosts,
or collect live fleet data in this spike.

## Scope And Constraints

- Diagnose correlation and likely bottlenecks; do not claim to observe undocumented Codex internal
  hashing or indexing.
- Extend the concepts in `scripts/workspace_preflight.py` instead of creating a competing evidence
  inventory.
- Reuse the disconnected-snapshot discovery and explicit target boundaries documented in
  `docs/fleet-snapshot-updates.md`.
- Keep profile, collect, and update as three independently authorized operations.
- Make local profiling read-only. It must not refresh indexes, change Git state, flush operating
  system caches, install software, or write inside the measured repository unless an operator
  explicitly supplies a report destination.
- Prefer aggregate counts and timings. Do not hash every workspace file merely to diagnose a
  suspected hashing cost.

## Findings

### Existing coverage and the measurement gap

`workspace_preflight.py` already reports tracked and untracked counts and bytes, dirty entries,
evidence scale, large files, and diff size. `review_work_state.py` detects lifecycle drift, and
`inventory_tool_shed_fleet.py` discovers and classifies disconnected Tool Shed snapshots.

Those tools identify risky repository composition but do not time representative operations,
summarize the age and lifecycle distribution of `work/`, or create a sanitized longitudinal
record. Consequently they cannot distinguish these plausible causes:

1. many tracked or untracked filesystem entries;
2. total bytes or unusually large files;
3. generated evidence and binary payloads;
4. dirty Git state or a large tracked diff;
5. growth in active, completed, or superseded Tool Shed artifacts;
6. Tool Shed's own full-tree artifact parsing; or
7. Codex behavior that cannot be directly observed through a supported interface.

The profiler can establish correlations and controlled before/after evidence. It cannot prove what
Codex internally hashes or indexes unless a supported Codex diagnostic surface is added later.

### Report schema

Use a versioned JSON document. The human-readable output is rendered from the same in-memory
payload so JSON and text cannot disagree. Proposed version 1 shape:

```json
{
  "schema_version": 1,
  "profile_id": "operator-assigned-or-random-uuid",
  "collected_at": "RFC3339 UTC timestamp",
  "collector": {
    "tool_shed_version": "semantic version",
    "profiler_version": 1
  },
  "environment": {
    "os_family": "linux|macos|windows|other",
    "python": "major.minor",
    "filesystem_family": "local|network|container-overlay|unknown",
    "git_version": "major.minor"
  },
  "repository": {
    "tracked": {"files": 0, "bytes": 0},
    "untracked": {"files": 0, "bytes": 0},
    "ignored": {"files": 0, "bytes": 0, "sampled": false},
    "dirty_entries": 0,
    "diff_bytes": 0,
    "directory_count": 0,
    "maximum_depth": 0,
    "size_buckets": {"under_4k": 0, "4k_to_1m": 0, "1m_to_10m": 0, "over_10m": 0},
    "content_classes": {"text": 0, "binary": 0, "archive": 0, "unknown": 0}
  },
  "tool_shed_work": {
    "files": 0,
    "bytes": 0,
    "by_lifecycle": {"active": 0, "finished": 0, "superseded": 0, "other": 0},
    "by_kind": {},
    "age_buckets_days": {"0_to_30": 0, "31_to_90": 0, "91_to_365": 0, "over_365": 0, "unknown": 0},
    "generated_evidence": {"tracked_files": 0, "tracked_bytes": 0, "untracked_files": 0, "untracked_bytes": 0}
  },
  "benchmarks": {
    "git_tracked_inventory": {"first_observed_ms": 0, "samples_ms": [], "median_ms": 0, "p95_ms": 0, "status": "ok"},
    "git_status_tracked_only": {"first_observed_ms": 0, "samples_ms": [], "median_ms": 0, "p95_ms": 0, "status": "ok"},
    "git_status_with_untracked": {"first_observed_ms": 0, "samples_ms": [], "median_ms": 0, "p95_ms": 0, "status": "ok"},
    "filesystem_inventory": {"first_observed_ms": 0, "samples_ms": [], "median_ms": 0, "p95_ms": 0, "status": "ok"},
    "work_artifact_parse": {"first_observed_ms": 0, "samples_ms": [], "median_ms": 0, "p95_ms": 0, "status": "ok"},
    "stale_path_review": {"first_observed_ms": 0, "samples_ms": [], "median_ms": 0, "p95_ms": 0, "status": "ok"},
    "work_state_review": {"first_observed_ms": 0, "samples_ms": [], "median_ms": 0, "p95_ms": 0, "status": "ok"}
  },
  "limits": {"rounds": 5, "per_probe_timeout_seconds": 30, "random_seed": 0},
  "warnings": []
}
```

Schema rules:

- Counts and bytes are exact when inexpensive; `sampled: true` and the sampling rule are mandatory
  when an ignored tree or inaccessible path makes exact traversal disproportionate.
- `by_kind` uses Tool Shed's known artifact types; unknown values aggregate under `other` rather
  than being copied verbatim.
- Benchmark status is `ok`, `timeout`, `unsupported`, or `error`. Errors use stable codes, not raw
  stderr.
- Durations use monotonic time. Retain individual samples plus median and nearest-rank p95; do not
  imply more precision than the clock provides.
- Optional operator observations, such as perceived Codex task-start latency, belong in a separate
  explicitly entered annotation file and never masquerade as collector measurements.

### Privacy boundary

Allowed by default:

- aggregate counts, byte totals, fixed size/age/content buckets, lifecycle counts, durations;
- coarse OS, filesystem, Python, Git, and Tool Shed versions needed to interpret results;
- a random UUID or an operator-supplied non-sensitive label; and
- stable finding/error codes.

Forbidden by default:

- file contents, excerpts, file names, relative or absolute paths, repository names, usernames,
  hostnames, branch names, remotes, commit identifiers, environment variables, command stdout or
  stderr, credentials, and per-file hashes;
- free-form policy reasons, artifact titles, next actions, or Git status entries; and
- automatic network transmission.

The local human-readable report may display the measured workspace path on screen for operator
orientation, but that value must not enter saved JSON. A later `collect` operation must parse and
validate the schema, reject unknown top-level fields by default, re-sanitize before copying, and
write an aggregation manifest listing report hashes and consent metadata. Hashing the small final
report is acceptable; hashing the workspace tree is not.

Profile identifiers are not anonymous when an external mapping is retained. Fleet aggregation
must describe them as pseudonymous and keep any host/path mapping outside the reports. Reports stay
local unless the operator separately approves exact source reports and a destination.

### Benchmark protocol

1. Run preflight first and record warnings; do not abort merely because the workspace is large.
2. Require the repository root as the measurement boundary. Do not follow symlinks or cross
   filesystem boundaries.
3. Run each probe once as an observed first run, then five additional times by default. Report
   first-run, median, p95, timeout, and exit status. Randomize the repeated probe order with a
   recorded seed to reduce systematic ordering bias.
4. Use `time.perf_counter_ns()` around subprocesses or internal scans. Suppress subprocess payloads
   after counting bytes; never store raw Git or review output.
5. Benchmark both `git status --untracked-files=no --porcelain=v1` and a normal porcelain status so
   untracked discovery cost is visible.
6. Benchmark Tool Shed artifact discovery/parsing directly. Do not call
   `update_work_index.py`, because writing generated indexes would contaminate a read-only run.
7. Run stale-path and work-state review in read-only JSON mode and discard their detailed output
   after recording exit status and byte count.
8. Do not flush OS caches or claim a true cold-cache measurement. Cache flushing is intrusive,
   platform-specific, and usually privileged. Label the first observation accurately.
9. Record concurrent-load caveats and flag a sample when probe duration exceeds its timeout. Avoid
   benchmarks while another Tool Shed migration or repository-wide build is running.
10. Repeat on the same workspace before and after one controlled change at a time. Useful changes
    include relocating generated evidence, reducing untracked files, or testing a disposable copy
    with completed artifacts excluded from traversal. Never delete or archive source data merely
    to obtain a benchmark.

For causal experiments, build compact disposable fixtures at increasing work-history sizes—for
example 0, 100, 1,000, and 5,000 completed artifacts—with constant source/evidence scale. Build a
second matrix that holds artifact count constant while varying raw evidence and untracked counts.
This separates Tool Shed history growth from general repository hydration cost without using a
production workspace as the experiment.

### Fleet rollout plan

| Stage | Scope | Authorization | Exit evidence |
| --- | --- | --- | --- |
| 0. Implement and test | Canonical checkout and disposable fixtures | This follow-up ticket | Schema/privacy tests, deterministic fixtures, read-only proof |
| 1. Local canary | This canonical workspace | Explicit profile invocation | Reviewed local report; no unexpected fields or mutations |
| 2. Approved snapshot canaries | One or two named, reachable workspaces | Explicit targets plus permission to update/profile | Snapshot update verified; reports remain local and reviewed |
| 3. Broader profiler distribution | Reviewed inventory subset | Separate guarded update approval | Each snapshot update passes existing boundary and rollback checks |
| 4. Fleet profile | Exact approved target manifest | Separate profiling approval | Per-workspace reports produced locally; failures isolated |
| 5. Collect and aggregate | Exact reviewed report manifest and destination | Separate collection approval | Sanitizer passes; aggregate contains no forbidden fields |
| 6. Decide optimization | Aggregated evidence and controlled fixtures | No workspace mutation | Correlations, limitations, and proposed intervention documented |
| 7. Optimize canary | Disposable fixture, then named canaries | New implementation/update approval | Before/after measurements show benefit without data loss |

Rollout must stop on the first sanitizer, schema, boundary, mutation, or snapshot-validation
failure. Profiling failures should be isolated and reported; they must not trigger cleanup. No
stage authorizes archiving, deletion, Git-history rewriting, or changing a workspace's `work/`.

## Recommendation

Implement one read-only local profiler that imports or reuses the current preflight/profile logic,
adds lifecycle aggregates and timed probes, and emits the schema above. Prove privacy with an
allowlist serializer and tests containing deliberately sensitive fixture names. Prove read-only
behavior by fingerprinting fixture Git state and file metadata before and after profiling.

Do not build fleet collection into the first implementation. After local canary evidence is
reviewed, add a separate collector only if multi-workspace comparison is still needed. Continue to
use the verified snapshot updater for distribution rather than teaching the profiler to install or
update itself.

## Collector Decision

Do not implement a separate sanitized performance-report collector. The original local canary and
an approved fresh canonical-workspace profile on 2026-08-14 both completed without warning codes.
All seven probes reported `ok`; the fresh profile's highest p95 was 114.670 ms. This evidence does
not show a collection bottleneck or a concrete multi-workspace comparison need that would justify
the additional privacy, consent, storage, and transfer surface.

Local reports remain sufficient. Reconsider collection only through a new explicitly scoped
campaign that names the target workspaces, exact reports, aggregation destination, and consent
boundary.

## Follow-Up

- [x] Create `work/tickets/ticket-implement-privacy-safe-workspace-performance-profiler.md`.
- [x] Implement and validate the local profiler against disposable scaling fixtures.
- [x] Review a local canary report before authorizing any snapshot update or fleet profiling.
- [x] Decide whether a separate sanitized collector is justified by the canary results: no
  collector is currently justified.
