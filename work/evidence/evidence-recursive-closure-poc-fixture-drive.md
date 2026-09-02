# IDEA-0019 Recursive Closure Proof-of-Concept Fixture Drive

Date: 2026-09-02  
Route: `ts:work2 IDEA-0019`  
Campaign: `CAMP-0149` (`drive-recursive-closure-proof-of-concept-fixtures`)  
Candidate: `aaab4807f63a2f43af572d13feec61b95241f20e`

## Outcome

The exact repaired candidate passed the recursive-closure proof-of-concept across the isolated
hosted-development site, the disposable Linux fixture, and the disposable Windows fixture.
Production was neither deployed nor mutated. The candidate is registered for later Work3 freeze
and Work5 release through release cohort `9902c070-34c6-4885-9f93-115fa6f59402`.

## Defect Found and Repaired

The original Work2 candidate correctly made an active `MISSING_PARENT` recovery case hold the
child and every governing ancestor open, but the recovery reason was not included in the child's
public `reason_codes` or the ancestors' indexed blocker lists. The root therefore reported only a
generic open descendant instead of the exact recovery cause.

Candidate `aaab4807f63a2f43af572d13feec61b95241f20e` makes active recovery reason codes participate in
both the independent recursive evaluator and the incremental projection. Resolution recomputes
static findings when required, so a historical recovery reason disappears without concealing a
real structural finding that happens to use the same code. Regression coverage proves the child
and root expose `MISSING_PARENT`, resolution clears it, effective closure returns, and incremental
and recursive results agree.

## Exact Candidate Qualification

- Clean isolated source: `/home/jon/dev/tool_shed_idea0019_work2`
- Candidate script SHA-256:
  `86c03f91f4d505ddfe17878d4138c09f784d70f16fd0a89a81544477fc3ae7fb`
- Disconnected snapshot: `/tmp/tool-shed-aaab4807f63a.tar`
- Snapshot SHA-256:
  `76ae27e1f8a8d4b0a12af451de1921386c9664bf0fa44de806b319dcd8a4a2bb`
- Snapshot contents: 353 entries with root `work/` excluded.
- Focused closure suite: 10 tests passed.
- Full clean candidate validation: 522 of 522 tests plus manifest, provider adapter, template,
  and snapshot checks passed.
- Linux installed snapshot validation: 522 of 522 tests; full validation passed in 23.812 seconds.
- Windows installed snapshot validation: 522 of 522 tests; full validation passed in 100.910
  seconds.

The 25,000-element, 100,000-edge, depth-128 benchmark retained recursive parity and passed every
provisional budget: first-100-blocker p95 0.031333 ms, full rebuild 10,105.881 ms, mutation p95
97.538152 ms, and summary p95 0.046373 ms.

## Fixture Matrix

| Lane | Exact target | Installed candidate | Blocked-state proof | Restored-state proof |
| --- | --- | --- | --- | --- |
| Hosted development | `tsrookarocom-dev` on `sup` | image `tool-shed-dashboard:dev-aaab4807f63a`, healthy | both authenticated Work pages returned 200 and rendered `MISSING_PARENT` | both pages returned 200 and no longer rendered `MISSING_PARENT` |
| Linux | `/home/jon/dev/ts_linux_test_bed` on `sup` | script digest matched | child `CAMP-0001` was `recovery-required`; root `IDEA-0001` remained open and named the child as a depth-2 `MISSING_PARENT` blocker | exact recovery restored the root; manual closure remained distinct; fabricated proof was blocked; recursive parity passed; final root closed |
| Windows | `E:\dev\ts_windows_test_bed` on `GOGETTER` | script digest matched | same typed recovery and depth-2 blocker result | same recovery, manual-closure, proof-safety, parity, and final-closure result |

Linux raw fixture evidence is retained at:

- `/home/jon/dev/ts_linux_test_bed/.tool-shed/idea0019-poc/blocked-before-repair.json`
- `/home/jon/dev/ts_linux_test_bed/.tool-shed/idea0019-poc/blocked-after-repair.json`
- `/home/jon/dev/ts_linux_test_bed/.tool-shed/idea0019-poc/resolved.json`

Windows raw fixture evidence is retained at:

- `E:\dev\ts_windows_test_bed\.tool-shed\idea0019-poc\blocked-before-repair.json`
- `E:\dev\ts_windows_test_bed\.tool-shed\idea0019-poc\blocked-after-repair.json`
- `E:\dev\ts_windows_test_bed\.tool-shed\idea0019-poc\resolved.json`

Both reporters delivered schema-7 blocked snapshots and later restored snapshots with zero pending
events. Hosted blocked snapshots showed `effective_closed=false`, child
`graph_health=recovery-required`, root `reason_codes=[DESCENDANT_OPEN]`, and the exact
`MISSING_PARENT` blocker for Linux sequence 190 and Windows sequence 115. Restored snapshots at
Linux sequence 198 and Windows sequence 121 showed both child and root effectively closed with
empty reasons and blockers.

The Windows fake-domain route also passed directly from `gogetter.local`:
`http://ts.rookaro.com-dev:8443/dashboard/healthz` returned the development health document.

## Safety and Boundary Evidence

- Recovery retries were bounded: the second retry escalated and the attempted third retry was
  refused.
- A local manual close remained labeled `closed-manual` and did not recursively manufacture
  descendant closure.
- A fabricated passed proof without immutable checker, recipe, subject, and authority bindings was
  stored as `blocked` and could not change closure.
- Recovery resolution removed the active reason, restored the tree, and preserved audit history.
- Development health and dashboard health returned HTTP 200 after deployment.
- Production health remained HTTP 200 at `http://127.0.0.1:8087/healthz`; the production compose
  project and v0.42.0 image were not changed.

The standard Work orchestration prepare route was attempted first. It stopped because unrelated,
pre-existing App Server edits in the canonical working tree make the current `SHED_VERSION.json`
stale. Those owner changes were preserved untouched. Candidate qualification therefore used an
isolated clean worktree and exact disconnected snapshots, while Tool Shed state mutations remained
guarded and revision-accounted in the canonical database.

## Work-Level Boundary

This evidence completes only the requested Work2 proof-of-concept fixture drive. It does not freeze
a Work3 candidate, push Git, publish a tag, deploy production, or reconcile the open PRM, project
map, or Idea. The next route remains an explicit `ts:work3 IDEA-0019` after the owner is ready to
freeze and qualify the registered candidate.
