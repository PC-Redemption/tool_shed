# Mainline App Server integration and hosted-watcher reduction evidence

Status: complete
Type: evidence
Updated: 2026-08-20
Next Action: none
Campaign: reconcile-main-integrate-app-server-and-reduce-hosted-watcher
Related: work/00-campaigns/deferred/039-build-hosted-watcher-status-and-email-pilot.md

## Outcome

Campaign 042 reconciled the previously dirty canonical `main`, merged the complete qualified App
Server lineage through `93795a4`, validated the actual merged mainline, and explicitly reduced
Campaign 039 to hosted advisory status and notification delivery for external or non-App-Server
work. App Server remains globally disabled and ordinary GUI execution remains the fallback.

## Original dirty-main inventory

| Classification | Paths or body | Resolution |
| --- | --- | --- |
| tracked intentional work | `README.md`, `adapters/codex-skill-releases.json`, `scripts/update_shed_manifest.py` | committed with the completed local watcher |
| completed but uncommitted work | local watcher protocol, schemas, runtime, tests, Campaigns 036–038, spike, and evidence | checkpointed on main at `d949f55` |
| Campaign 039-related work | hosted contracts and schemas, deferred Campaigns 035/039, ADR, checklist, Project Map, and Program Roadmap | checkpointed on main at `1328454` |
| completed but uncommitted App Server history | Campaigns 040 and 041 | checkpointed on main at `ed8b3ee` |
| superseded App Server proof of concept | model policy, early execution docs and adapters, tests, and reasoning-catalog refactor | preserved on `checkpoint/pre-mainline-app-server-poc-20260820` at `04ddb97`; removed from the working tree before merge because `93795a4` supersedes it |
| generated/transient | `SHED_VERSION.json`, active/completed queue projections, `work/index.json`, and `work/index.md` | regenerated from reconciled sources; Campaign 042 lifecycle projection was checkpointed at `f046280`, watcher manifest candidate at `5a504e4` |
| other unrelated work | none | none required |
| unknown | none | inventory was complete before merge |

No reset, clean, forced checkout, stash, automatic rollback, or destructive recovery was used.

## Integration method

`main` advanced from `8966a2e` through five coherent checkpoint commits. The reviewed integration
branch was then merged with a non-fast-forward merge and retained as the second parent of
`aa1e1ca`. A merge-tree preview showed only `SHED_VERSION.json`, queue projections, and work indexes
changed on both sides. Current-main versions were retained as the intermediate conflict policy and
all five generated files were then regenerated from the combined source tree.

The integration lineage also contained historical App Server campaign files numbered 035 and 036.
Those numbers belong to the watcher registry on real main. The duplicate App Server files were
omitted from the final tree while remaining visible in the merge ancestry; canonical App Server
history is recorded by Campaigns 040 and 041. No implementation conflict was resolved by selecting
one code side.

## Mainline validation

- Focused combined App Server and watcher tests: 31 passed.
- Full Tool Shed validator: 188 tests passed in 45.804 seconds.
- Manifest: matched 132 tracked files.
- Provider conformance, campaign/roadmap validation, regenerated indexes, stale-path checks,
  strict work-state review, and disposable-workspace smoke: passed.
- Codex CLI: 0.144.6, matching the qualified version.
- Compatibility status and live smoke: `qualified_with_blockers`.
- Live smoke passed App Server startup, ChatGPT authentication, no API-key fallback, default GUI
  fallback, GUI-native `ts: discuss`, Sol/high planning, Terra/low verification, new-thread
  behavior, and fail-closed approvals.
- The cancellation reconciliation race and restricted-read mismatch remained blocked. The absent
  supported GUI approval bridge, unqualified deployment, material tiny-operation harness cost,
  and experimental/unsupported-production status remain visible.

## Representative CAMP regression

The disposable post-merge fixture branch
`qualification/post-merge-camp-regression-042` prepared the fixture at `b98deb6` and recorded the
successful result at `a28ec42`. The model changed only `tests/test_codex_execution.py`; the Git
journal was safe, preserved pre-existing work, and reported no unexpected paths.

| Metric | Campaign 041 | Merged main |
| --- | ---: | ---: |
| Input tokens | 55,665 | 56,969 |
| Cached input | 27,392 | 27,392 |
| Uncached input | 28,273 | 29,577 |
| Output tokens | 512 | 420 |
| Reasoning output | 149 | 85 |
| Model turns | 2 | 2 |
| Model tools | 1 | 1 |
| Elapsed | 13.716 s | 13.651 s |
| Weighted usage | 34,084.2 | 34,836.2 |
| Focused tests | 22 | 23 |

Input increased 2.34% and weighted usage increased 2.21%; this is not a material regression and the
two-turn/one-tool optimized shape remains intact.

## Workspace-write safety

The live disposable write qualification passed in 68.556 seconds. Authentication was ChatGPT-only
with no API fallback. The exact writable root allowed intended read/create/modify/delete,
directory, harmless-command, and focused-test operations while blocking sibling writes and
destructive deletion, privileged writes, network access, and hardened `/tmp` writes. Approval
denial created no target. Interrupted partial work produced a safe journal, did not perform the
after-sleep write, and resumed read-only without writing or replaying mutation. The minimal
Terra/medium write changed only `sample.py`, passed its focused test, recorded 75,008 input tokens,
four turns and three tools, and had no unexpected paths. The global default did not change.

## Campaign 039 decision

The remaining independent need is limited to workloads Tool Shed/App Server cannot observe
directly, such as external CI, hardware or firmware qualification, provider-native jobs, remote
systems, or long-running work launched outside the App Server-controlled path. A hosted companion
could add multi-host advisory status, sender-staleness visibility, and centralized email or another
notification when the GUI and originating machine are unattended.

That responsibility is distinct only if the hosted service accepts sanitized terminal events from
the authoritative local watcher and never controls execution. Campaign 039 therefore removes
duplicate execution orchestration, App Server CAMP completion detection, App Server monitoring,
recovery orchestration, agent lifecycle, remote retry, and workspace write-back.

Email or notification delivery can still be useful, but no concrete current workload, accountable
service owner, or recipient justifies the security, tenancy, retention, deployment, and operational
maintenance cost. Campaign 039 remains deferred. Reactivation requires a named external or
non-App-Server workload and recipient plus a bounded hosting/authentication plan.

## Authority boundary

Nothing was pushed, released, deployed, published, or globally enabled. The installed Tool Shed
client was not synchronized because this campaign is not a release or explicit client-update route.
