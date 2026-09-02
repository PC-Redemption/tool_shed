# Three-Lane Release Closure

Status: approved
Type: runbook
Updated: 2026-09-02
Next Action: use the corrected Work3 route to bind and verify all development lanes

This project keeps Tool Shed's portable Work1–Work5 definitions unchanged. The tracked
`work/tool-shed.yaml` applies this runbook only to this repository's selected Work3 and Work5
endpoints.

Database-owned owner: `IDEA-0018`, through `MAP-0025` and `PRM-0036`.

The release has one canonical source candidate and three required delivery lanes:

| Lane | Development target | Production target |
| --- | --- | --- |
| Web | `tsrookarocom-dev@sup.local:/home/jon/docker/ts.rookaro.com-dev` | `tsrookarocom@sup.local:/home/jon/docker/ts.rookaro.com` |
| Windows | `PC-Redemption/ts_windows_test_bed@GOGETTER:E:\dev\ts_windows_test_bed` | `github-release:tool-shed-windows-install-client` |
| Linux | `PC-Redemption/ts_linux_test_bed@sup.local:/home/jon/dev/ts_linux_test_bed` | `github-release:tool-shed-linux-install-client` |

The canonical status record is one tracked JSON manifest under
`work/evidence/release-lanes/<release-id>.json`. `work/runbooks/release_lanes.py` owns changes to that
record. It reports both directions from one structure: the release reports its required child
lanes, and each lane record identifies its release, stage, target, source commit, artifact, actor,
and evidence. Do not keep a second mutable lane-status list.

An open child keeps the selected phase open. A child becomes terminal only through `verified` or
`manual-closed`. Manual closure is not a silent waiver: it requires evidence, an actor, an explicit
authorization reference, and a reason. A stale manifest digest, foreign project binding, wrong
target, different candidate, missing evidence, or mismatched source commit fails closed.

## Guarded command pattern

Obtain the project binding once for the active session and refresh the manifest digest before each
mutation:

```bash
python3 scripts/project_identity.py --workspace . identity --operation release-lanes --json
python3 work/runbooks/release_lanes.py --workspace . status --release-id <release-id> --json
```

Pass the returned `session_binding` as `--project-binding` and the current `manifest_digest` as
`--expect`. Initialize exactly one record when the release does not already have one:

```bash
python3 work/runbooks/release_lanes.py --workspace . init \
  --release-id <release-id> \
  --project-binding <session-binding> \
  --json
```

Initialization always requires all three lanes. A future scope change must revise this project
contract; an individual release cannot omit a failed or inconvenient target.

## Work3 development closure

Run the normal cumulative Work3 endpoint first. After its final documentation, validation, build,
development updates, and local freeze commit are complete, bind that exact commit:

```bash
python3 work/runbooks/release_lanes.py --workspace . bind \
  --release-id <release-id> \
  --commit <full-candidate-sha> \
  --expect <manifest-digest> \
  --project-binding <session-binding> \
  --json
```

For each required lane, deploy or synchronize that candidate to the declared development target,
run the lane's focused checks, preserve durable evidence, and record the exact artifact. Example:

```bash
python3 work/runbooks/release_lanes.py --workspace . record \
  --release-id <release-id> \
  --lane windows \
  --stage development \
  --status verified \
  --source-commit <full-candidate-sha> \
  --artifact <version-or-artifact-digest> \
  --evidence <durable-reference> \
  --actor <actor> \
  --expect <fresh-manifest-digest> \
  --project-binding <session-binding> \
  --json
```

After web, Windows, and Linux are recorded, require:

```bash
python3 work/runbooks/release_lanes.py --workspace . verify \
  --release-id <release-id> \
  --phase work3 \
  --json
```

Commit the manifest with the Work3 evidence checkpoint. Do not report Work3 closed while this
command reports a blocker.

## Work5 replacement

`work/tool-shed.yaml` sets `work5.run_default: false` because checking production lanes only after
the portable Work5 route would be too late: the standard route may already have reconciled and
finalized the parent release cohort. This replacement preserves every standard Work5 obligation
and moves the three-lane gate before reconciliation:

1. Resolve the complete active release cohort and refuse a narrower scope that strands a registered
   candidate. Run release qualification and obtain a clean frozen content commit.
2. Run `verify --phase work5-preflight --release-commit <frozen-sha>`. The bound Work3 candidate
   must be an ancestor of the frozen commit and every development lane must remain terminal.
3. Guardedly freeze the release cohort to that exact SHA. Push it, require the exact-SHA full
   validation workflow, then create the provenance-only `SHED_VERSION.json` commit, stable tag,
   and GitHub Release by the normal release contract.
4. Promote and verify the web, Windows, and Linux production targets that are explicitly authorized
   for this run. Record each production artifact and its durable evidence with `record --stage
   production --source-commit <frozen-sha>`. Stop at the first unapproved, failed, stale, or missing
   lane; do not infer production authority from this runbook.
5. Require `verify --phase work5-complete --release-commit <frozen-sha>`. Every required production
   lane must be terminal and must name the exact release content commit.
6. Only after that gate passes, record the release against the cohort, reconcile registered owning
   cycles from the innermost result through the originating Idea, finalize the cohort, checkpoint
   Hybrid state, and commit the lane manifest plus the exact checkpoint objects.
7. Run the configured after-action GitHub issue review against the released behavior.

A manual lane closure uses the same `record` command with `--status manual-closed` plus
`--authorization-ref` and `--reason`. It is a visible terminal disposition, not proof that an
unobserved deployment succeeded.

## Boundary

This manifest is the fast project-level release gate for IDEA-0018. It deliberately does not add a
portable database schema or recursively close arbitrary Tool Shed artifacts. General element
lineage, descendant discovery, proof attempts, and parent rollup remain the separate IDEA-0019
design; until that is implemented, the Work5 replacement enforces this manifest before calling the
existing outcome reconciliation machinery.
