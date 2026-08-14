# Workspace Performance Profiling

Tool Shed's workspace profiler measures repository scale and representative read-only operation
latency so operators can test whether slower Codex work correlates with `work/` history, Git state,
generated evidence, or general filesystem growth.

It cannot observe or prove undocumented Codex hashing, indexing, or workspace-hydration behavior.
Use controlled before/after measurements to test likely causes.

## Run A Local Profile

From a project repository root with an installed Tool Shed snapshot:

```bash
python3 tool_shed/scripts/profile_workspace_performance.py --workspace .
```

The default runs one first observation and five repeated samples for each probe. Use JSON for a
sanitized machine-readable report:

```bash
python3 tool_shed/scripts/profile_workspace_performance.py \
  --workspace . \
  --json
```

Saving a report requires an explicit destination. Existing files are not overwritten unless
`--force` is also supplied:

```bash
python3 tool_shed/scripts/profile_workspace_performance.py \
  --workspace . \
  --output /approved/report-directory/workspace-profile.json
```

`--rounds`, `--timeout`, and `--seed` make repeated campaigns comparable. Supply the same UUID with
`--profile-id` only when an approved longitudinal study needs pseudonymous correlation. The first
observation is reported as `first_observed_ms`; it is not described as a cold-cache result because
the profiler does not flush operating-system caches.

## Measurements

The version 1 report contains:

- tracked, untracked, and ignored file counts and bytes;
- dirty-entry and serialized-diff size;
- directory depth, fixed size buckets, and suffix-based content classes;
- Tool Shed artifact counts and bytes by known lifecycle, type, and age bucket;
- tracked and untracked evidence aggregates from the existing workspace preflight profile; and
- timings for tracked inventory, tracked-only Git status, normal Git status, filesystem inventory,
  Tool Shed artifact parsing, stale-path review, and work-state review.

The filesystem walk excludes `.git`, does not follow symlinks, and does not cross filesystem-device
boundaries. Every timed probe has a timeout and a stable `ok`, `timeout`, `unsupported`, or `error`
status. Repeated probe order is randomized with the seed recorded in the report. Git subprocesses
run with optional locks disabled so profiling does not refresh or rewrite the Git index.

## Privacy Boundary

Saved JSON uses a strict allowlist. It contains aggregate counts, timings, coarse platform and
version fields, stable warning codes, and a UUID. It does not contain:

- file contents, names, or paths;
- repository, user, or host names;
- branches, remotes, commits, or Git status entries;
- environment variables or command output;
- artifact titles, next actions, or other prose; or
- per-file hashes.

The human console view may show the local workspace path for orientation. The saved JSON never
does. A UUID is pseudonymous, not anonymous, when someone retains an external workspace mapping.

Reports remain local by default. Permission to profile does not authorize copying a report,
updating a Tool Shed snapshot, cleaning a workspace, archiving evidence, deleting files, or
rewriting Git history. Each is a separate operation requiring its own scope and approval.

## Comparison Protocol

Compare the same workspace before and after one controlled change. Do not combine evidence
relocation, untracked-file cleanup, and work-history experiments in one comparison. For causal
tests, use disposable fixtures that independently vary:

- completed Tool Shed artifacts while source and evidence remain constant; and
- untracked or generated evidence while artifact count remains constant.

The test suite exercises completed-artifact fixtures at 0, 100, 1,000, and 5,000 files plus a
separate evidence-count matrix. Production data must not be deleted or archived merely to create a
benchmark.

## Fleet Boundary

The profiler contains no network, collection, installation, or update capability. Distribute a
released profiler through the existing verified snapshot updater, first to explicitly approved
canaries. Profile exact approved targets, review reports locally, and authorize report collection
separately. Stop rollout on schema, sanitizer, repository-boundary, mutation, or snapshot-validation
failure.

A separate sanitized report collector is not currently implemented or justified. Reviewed local
canaries completed without profiler warnings or a material measurement bottleneck, and no concrete
multi-workspace comparison requires the added privacy and transfer surface. Reconsider a collector
only when a new campaign names exact workspaces, reports, destination, and consent boundaries.
