# IDEA-0020 M1 Lifecycle Qualification Evidence

Status: passed
Date: 2026-09-02
Candidate: `e7b2b28516d5fbe68df452510c73d6155b80171f`
Version: `0.43.0` (unpublished development candidate)
Campaign: `CAMP-0150`
Roadmap: `PRM-0038` / `M1-CONTRACT-AND-FOUNDATION`

## Result

The versioned scenario, sealed manifest, explicit checkpoint selector, append-only hash-chained
journal, content-derived run ID, compact result, truth-vector, verdict, and replay contracts are
executable. The independent oracle derives closure from authority tables without importing the
product closure evaluator or reading ancestor, blocker, or rollup projections before comparison.

The exact candidate passed the clean release profile with 535 of 535 tests. The same snapshot was
installed in the Linux and Windows disposable fixtures, and the same commit was deployed to the
isolated development web service. No source was pushed, no release was published, and production
was not deployed or mutated.

## Qualification matrix

| Scenario / target | Run / checkpoint | Result |
| --- | --- | --- |
| QH-001 hosted development | `tsqh-d7c10323cf72d679023a05a0` / `hosted-inventory` | PASS: exact visible project set is only `ts_linux_test_bed` and `ts_windows_test_bed`; no seed project is operational; two unique projects and two unique instances |
| QH-002 Linux | `tsqh-d6b37ef933c4448ecd73061a` / `terminal-clean-tail` | PASS: 10 local/hosted checks |
| QH-002 Windows | `tsqh-74130b1c052a739e5885516b` / `terminal-clean-tail` | PASS: 10 local/hosted checks |
| Rendered project work pages | exact final QH-002 artifact UUIDs | HTTP 200; all four Linux and all four Windows visible IDs rendered; closed/completed labels present |

Both QH-002 runs created exactly one Idea, project map, Program Roadmap, and campaign; completed
all four documents; made all four outcomes terminal/satisfied/reconciled; created the three exact
parent and propagated-result edges; left zero run-owned active residue; enrolled every run cycle in
the closure graph; independently matched every stored rollup; and matched the hosted project,
instance, artifact identity, lifecycle, outcome, reconciliation, and effective-closure fields.

Reporter queues drained to zero before the hosted snapshot. Development dashboard health and the
development site were healthy on the exact candidate. The separately observed production health
endpoint remained healthy throughout.

## Defect found and closed

The first Linux run, `tsqh-c2d21e53766558a2f372e571`, passed document and outcome propagation but
failed `QH002-CLOSURE-PROJECTION-PARITY`: all four new document cycles were missing from schema-3
closure authority. This proved that migration had populated the graph but later managed lifecycle
writes did not enroll new elements.

Candidate `df019af29a7d8adaf2b1e1398ec63abcb9d5c3d6` added same-transaction authority
synchronization. New or changed cycles, requirements, and active outcome-parent edges now refresh
recoverable envelopes and append-only assertions; exact terminal/reconciled outcomes record
closed-loop closure. A later managed write rediscovered and repaired every missing element from the
failed run. Its recovered truth vector passes all seven local QH-002 checks without deleting or
rewriting the retained lifecycle history.

## Persistence and integrity

- Linux checkpoint/rebuild: schema 3, revision 91, live and rebuilt domain digest
  `7bc058b24d0c53efadaa8f5f82f044151988f23b1d1c345967007c719dc469f4`, CLEAN.
- Windows checkpoint/rebuild: schema 3, revision 66, live and rebuilt domain digest
  `c0558c392c6f4f6300ea40c5074ea6990ab0eeed61f54396b60ddd6f7f9c32e8`, CLEAN.
- Installed snapshot manifests match all 257 tracked snapshot files on both platforms.
- Fixture Doctor reports no errors after generated Python bytecode was removed. It remains
  DEGRADED only for expected disposable-test-bed residue: retained prior snapshot backups,
  generated qualification/checkpoint files, and uncommitted synthetic `work/` history.

## Retained generated evidence

Raw evidence is ignored below `work/evidence/generated/idea0020-m1/`; these hashes bind the selected
records without promoting generated captures into operational authority.

| Record | SHA-256 |
| --- | --- |
| QH-001 final manifest | `df69ab85ee28cda4e4cc06cf753481cdf7c8d2e142123d4bc718b558be31b704` |
| QH-001 final result | `de002af5380d55c556c03dad6228b65d18e4bb9c8619afd2755f6f68edb3f2a8` |
| QH-002 Linux manifest | `1413ebda67fdc1610d02e2d47db6cd763ad0074bc7d82c916399825e83f8183f` |
| QH-002 Linux truth | `d92a75feb6763e786476b7c48686174e1b5afdd6e984835b33991a5b5d09905e` |
| QH-002 Linux result | `790e60256a8c8ccdc1be0232a8ae4405fe22e190d1ed743bdb423abda41d31e8` |
| QH-002 Windows manifest | `8cf48c0a8dd6b243e5027d0f0fb92e0a62987f16db423d3cd9cacf35cae0c0ca` |
| QH-002 Windows truth | `70184d0ef380fba28bc58e13ab255c1003d0272c6d4062dd5853cb17b9a8ebf6` |
| QH-002 Windows result | `e7827b9ea572cde803332d1519686b8577aae7b9d115a0206785596c24c6988b` |
| Final hosted snapshot | `aae09515b0b3ca09ed34c06c1ca83e01754709f9f4b1cbc1613c2c212cae5502` |
| Final rendered check | `a94a40c2b61dacca68b8308a77894ac833afbc83bdef5b24f45114be3d60ba44` |
| Final development-site status | `3c60d5ac78f5b5f3c4f88505708b028de6e4bdc75799db16b07c0023b89b2a3c` |
| First product-failure drive | `ea17757c30f65f0516ab1554bad2ad6bd94a931dd0afff58f0fc3bdc01059197` |
| Recovered failed-run truth | `6effdd412a050d58d5cd7fee4fd518294160a29f5582c243a628227dfc60c542` |

## Boundary and next step

M1 satisfies `G1-RUN-CONTRACT-AND-INDEPENDENT-ORACLE`, the foundation portion of
`G2-LOCAL-LIFECYCLE-CORPUS`, and the baseline portion of
`G3-REPORTER-HOSTED-AND-UI-TRUTH`. M2 through M7 remain open. In particular, this is not a Work3
candidate freeze and does not authorize Work5 publication or production promotion.
