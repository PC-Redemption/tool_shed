# App Server integration and Campaign 039 reassessment evidence

Status: complete
Type: evidence
Updated: 2026-08-20
Campaign: standalone
Campaign Reason: branch-local reconciliation evidence; Campaign 041 lifecycle remains in the preserved main worktree until merge review
Disposition: documented

## Integration decision

Campaign 041 reconciled the qualified App Server lineage on the clean local branch
`codex/tool-shed-app-server-reconciliation` in worktree
`/home/jon/docker/tool_shed-app-server-reconciliation`.

The actual mainline base is `8966a2e` (`Complete GitHub Actions dependency campaign`). `main` and
`origin/main` both point to that commit and have no later commits. The integration branch was
created directly from `9f72e2c` (`Complete App Server CAMP token optimization`). Git ancestry proves
that the three source branches are linear:

```text
main 8966a2e
  -> codex/tool-shed-app-server-integration edff851
  -> codex/tool-shed-app-server-write-qualification 69a27d8
  -> codex/tool-shed-app-server-camp-token-optimization 9f72e2c
  -> codex/tool-shed-app-server-reconciliation
```

The integrated history is the 15-commit range `8966a2e..9f72e2c`:

```text
46f412a Add Codex App Server execution proof of concept
6d9c275 Add feature-flagged Codex App Server orchestration
f9c7ced Reconcile completed campaign index
b1f9d8b Add real-campaign App Server qualification telemetry
c66a5f1 Harden App Server qualification controls
f04d855 Record App Server real-campaign qualification
c7c3d87 Harden App Server compatibility and cancellation
8841335 Document App Server hardening baseline and gates
edff851 Close App Server integration campaign
8b12c6a Qualify App Server workspace writing
69a27d8 Complete App Server CAMP qualification
22082bb Document App Server CAMP token baseline
6f6c817 Optimize bounded App Server CAMP execution
ce0b05c Avoid redundant CAMP skill activation in worker capsule
9f72e2c Complete App Server CAMP token optimization
```

No commits were merged, cherry-picked, or reimplemented during reconciliation because the latest
source branch already contains the complete earlier lineage and `main` is its direct ancestor.
There were no content or ancestry conflicts. Starting from the qualified tip is the minimal
nonduplicated integration.

The original `main` worktree was not modified for source integration. Its unrelated uncommitted
App Server copies, completion-watcher implementation, hosted-pilot material, campaign records, and
generated queue/index projections remain in place. No reset, checkout, clean, stash, forced merge,
or overwrite was used.

## Preserved operating boundary

Codex CLI `0.144.6` is installed and its version-specific record remains
`qualified_with_blockers`. The global configuration remains
`codex_app_server_enabled = false`; App Server use requires an invocation-scoped opt-in. Normal GUI
execution and `ts: discuss` remain on the existing GUI path.

Only these App Server roles are qualified and enabled:

| Role | Model | Reasoning | Sandbox |
| --- | --- | --- | --- |
| planning | `gpt-5.6-sol` | high | read-only |
| verification | `gpt-5.6-terra` | low | read-only |
| camp execution | `gpt-5.6-terra` | medium | workspace-write through `camp-run` only |

The centralized policy also defines the intended Sol/Terra routes for program and campaign
derivation, architecture, escalation, implementation, debugging, testing, build, and deployment,
but those unqualified App Server roles remain disabled.

The live and deterministic checks preserve ChatGPT authentication with no API-key fallback,
approval `never`, one exact writable root, exact declared paths, network disabled, both temporary
directory exclusions, Git-required journaling, dirty-target refusal, unrelated-dirty preservation,
no retry after mutation, no permission expansion, and no automatic destructive rollback or
lifecycle transition.

## Validation evidence

The following checks ran from the clean reconciliation worktree:

| Check | Result |
| --- | --- |
| `python3 -m unittest tests.test_codex_execution -v` | 23 tests passed |
| `python3 scripts/update_shed_manifest.py --check` | manifest matched 116 tracked files |
| campaign validation | valid, no findings |
| Program Roadmap validation | valid, no findings |
| `python3 scripts/codex_app_server_compatibility.py status` and `status --json` | opt-in, default disabled, CLI 0.144.6 qualified with blockers |
| `python3 scripts/codex_app_server_compatibility.py smoke --cwd .` | qualified capabilities passed; recorded blockers retained |
| `python3 scripts/codex_app_server_write_qualification.py --base-dir /home/jon/docker ...` | qualified; all disposable write-safety checks passed in 45.106 seconds |
| `python3 scripts/validate_tool_shed.py` | 180 tests passed in 45.927 seconds; provider, index, stale-path, work-state, roadmap, and disposable-install checks passed |

The live compatibility smoke confirmed GUI fallback, GUI-native discussion, approval fail-closed,
ChatGPT authentication, no API fallback, App Server startup, Sol/high planning, Terra/low
verification, and fresh read-only threads. Planning used 18,255 input tokens and verification used
18,254, consistent with the recorded fixed harness baseline.

The write-safety rerun allowed only the intended disposable-root read/create/modify/delete,
directory, harmless command, and test operations. It blocked sibling writes and deletion,
privileged writes, network access, and hardened `/tmp` writes. Approval denial created no target.
Interrupted partial work was journaled, the after-sleep write did not occur, read-only resume could
not write, and no replay followed mutation. The minimal Terra/medium write changed only
`sample.py`, passed its focused test, and recorded 75,008 input tokens, four model turns, three
tools, a safe journal, and no unexpected paths.

### Campaign 040 representative regression

The final trigger-neutral fixture commit is `b3e90f2`, followed historically by the qualified
result at `9e9f28a`. Rerunning that exact controller edit changed only
`tests/test_codex_execution.py`, added the two requested retry/unsafe-journal assertions, passed all
22 focused tests, and produced `step_complete` with a safe Git journal.

| Metric | Campaign 040 qualification | Campaign 041 rerun |
| --- | ---: | ---: |
| Input tokens | 61,516 | 55,665 |
| Cached input | 30,464 | 27,392 |
| Uncached input | 31,052 | 28,273 |
| Output tokens | 395 | 512 |
| Reasoning output | 41 | 149 |
| Model turns | 2 | 2 |
| Model tools | 1 | 1 |
| Elapsed | 12.458 seconds | 13.716 seconds |
| Weighted usage | 36,468.4 | 34,084.2 |

Input fell 9.51% and weighted usage fell 6.54% relative to the qualified result. Elapsed increased
10.10%, while the two-turn/one-tool shape, exact-path behavior, correctness, and safety remained
stable. This is not material movement toward the seven-turn, six-tool, 241,524-input reference.

An initial diagnostic rerun used historical fixture `7b7a8bd`, which predates trigger-neutral
commit `ce0b05c`. It caused one installed-skill read and measured 87,403 input tokens, three turns,
and two tools. That result identified the fixture error rather than an integrated-code regression;
the correct post-fix fixture removed the redundant read.

## Known blockers

No blocker was reclassified as solved. The cancellation smoke again returned `no active turn` and
then reconciled `inProgress` to `completed`. Restricted-read behavior was not retested because the
CLI version is unchanged and its recorded mismatch remains applicable. The supported GUI approval
bridge remains unavailable, workspace deployment remains unqualified, fixed harness cost remains
material for tiny operations, and App Server remains experimental and unsupported for production
workloads.

## Campaign 039 reassessment

Campaign 039 originally proposed an authenticated hosted pilot for sanitized advisory status and
centralized email delivery. Its scope includes tenant-scoped credentials, durable terminal-event
ingestion, idempotent API/outbox acknowledgement, notification-worker retries, retention and
redaction, stale-reporter and outage behavior, offline replay, and independent backend/static-site
deployment and rollback. Its local watcher remains authoritative for local state; the hosted
surface is advisory.

App Server now directly owns bounded execution and terminal reconciliation for explicitly opted-in
App Server planning, verification, and CAMP execution. A hosted watcher must not duplicate that
execution controller, infer App Server lifecycle state independently, or become a second recovery
mechanism for the same turn.

App Server does not replace notification delivery or cross-workspace/cross-device visibility for
long-running work outside App Server. It provides no hosted email service, tenant status surface,
durable notification outbox, offline replay endpoint, or independent hosted retention and rollout
boundary. Those responsibilities remain distinct when there is a demonstrated operator need.

Recommended disposition: **reduce scope**. Keep Campaign 039 deferred and unchanged until this
assessment is reviewed. If reactivated through the normal guarded lifecycle, revise its execution
contract to a notification/status companion for non-App-Server external work and explicitly
exclude App Server completion detection, CAMP orchestration, turn cancellation/recovery, and any
hosted write-back to local or App Server lifecycle state. Revalidate demand for email and remote
status before building hosted infrastructure; do not maintain two orchestration mechanisms.

## Merge readiness

The reconciliation candidate is locally validated and source-ready for review with App Server
default-disabled. Because `main` is an ancestor, the committed source lineage has no Git merge
conflict. The current `main` checkout is nevertheless dirty on overlapping App Server and work
projection paths, so merging there is not presently safe. Preserve or checkpoint that owner work
and review the Campaign 039 scope recommendation before attempting the merge. No push, release,
deployment, production promotion, global enablement, or Campaign 039 lifecycle mutation is part of
this evidence.
