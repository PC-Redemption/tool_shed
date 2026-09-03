# Evidence: IDEA-0020 M2 Local Lifecycle and Recovery Corpus

Status: passed
Recorded: 2026-09-02
Campaign: CAMP-0151
Program Roadmap: PRM-0038, M2-LOCAL-LIFECYCLE-CORPUS
Candidate commit: `dd0081438454a16f9ec539350f47fa68fdf74540`
Candidate version: `0.43.0` (unpublished development cohort)
Environment: development only

## Candidate Validation

The exact candidate was validated from a clean detached worktree with the repository's Python
environment:

```text
python scripts/validate_tool_shed.py --profile release
SHED_VERSION.json matches 265 tracked files.
537 of 537 tests passed with 8 workers.
Provider adapter, database view, stale-path, work-state, Program Roadmap, bootstrap-closure,
temporary-workspace, template, and example checks passed.
tool_shed release validation passed.
```

Focused Hybrid, document-store, closure-lineage, and lifecycle qualification validation also
passed 38 of 38 tests before the candidate was frozen.

## Exact Development Targets

| Target | Identity | Installed/served candidate | Result |
| --- | --- | --- | --- |
| Linux fixture | `sup:/home/jon/dev/ts_linux_test_bed`; project `4e6c7752-8ce6-44d1-bf76-dffb18cd8137`; instance `71fa633f-d6e6-4e44-b904-dd52a748bb70` | disconnected snapshot `dd0081438454` | PASS |
| Windows fixture | `GOGETTER:E:\dev\ts_windows_test_bed`; project `10066c9b-e5e3-419f-9ee8-bb47fc029e9c`; instance `4906bbc9-36c3-486a-a247-bb442ea15dba` | disconnected snapshot `dd0081438454` | PASS |
| Development web | `tsrookarocom-dev` on `sup.local` | image tag `dev-dd0081438454`; image ID `sha256:b0e43634975119c0704f8292e18d1c0f5b798c86d057dd435060640f1b47a0cd` | healthy |

The dashboard and `requirements-dashboard.txt` trees have zero changed paths between the M1
candidate `e7b2b28516d5fbe68df452510c73d6155b80171f` and this candidate. The existing verified image
was therefore retagged to the new exact candidate identity rather than rebuilt from a dirty source
workspace. `http://192.168.7.5:8443/dashboard/healthz` with Host `ts.rookaro.com-dev` returned the
development health payload successfully.

Rollback snapshots remain at `tool_shed.before-idea0020-dd00814` inside each disposable fixture.
The installed personal Codex skill and every production target were left unchanged.

## Local Corpus Results

Each OS used a platform-specific sealed manifest bound to the candidate, fixture project and
instance, source baseline digest, scenario digest, deterministic seed, and declared checkpoint.
Each drive result was then sealed into a compact PASS result and replayed once with the same run
identity. Replay returned the retained result without advancing database state.

| Scenario | Linux result digest | Windows result digest | Checks per platform |
| --- | --- | --- | ---: |
| QH-003 branched closure ordering | `6f0d988c4159691d2f68eae923dcb639189f94e8419af6bd6369a575d68400a1` | `7a1f4be93be0db55fc68eaa1041600d4a62a61b4879d21c37dd885ee8b5732f0` | 5 |
| QH-004 deep/shared lineage | `de76c846abf02972de16b69b6cbfcc292f4e771c98e49142f6802d9bfa2c5f47` | `3fcfb733b48bd0fab716b24571e02d825ead0abc4cf3a530d7f4ba54e97755a5` | 5 |
| QH-005 revision-invalidated proof | `4ab17632109665b21eb66a1c4a7d1ef5e66cc6dffc5df8b38ad3d44a0d7fd575` | `ecb9cbd9e71fd0386adac50a8f2e5813745b04ee6b2c7149dcf6806a73497420` | 4 |
| QH-006 interrupted reconciliation/replay | `9b934b3a786cdac1f2e0e6539b0a60d08fd86f61fd7e68e8029ac1fccb6d9c0c` | `c83b221148e3328a40c44603b259199e4cf1ccf5b3000a8ab04241e92cb76465` | 6 |
| QH-008 checkpoint/rebuild parity | `07f64f5e05df8333fcbf7cb95d8410936562ce4e75bcb84c851990ebec066a91` | `93e8e31b0f8c499a352a981d96eeced5d992207d7028109f0faf920cc8bbf70b` | 4 |
| QH-009 isolated malformed graphs | `016d8b0e8f4df0a108ad27b428819c7f1034820245d815ef6357ec0a11838641` | `a589e469e4db7fa6e83e1bdfb5eddc1c766fcd0decc8dd9434ab17903dbbab4c` | 6 |
| QH-010 local existing-instance intake | `22ae2f91dcbaa6273c23a140c9674e4655ab8790dc9f04295b665fc76e2c483b` | `82be358718bdfee6049e8b2d30c4ce7d2d573ba44d0251e680847289567e9d2b` | 7 |

Linux retained summary SHA-256:
`9ec91d022eef714c6043c6af234c014259c694268805713e78dca0ec523777ea`.

Windows retained summary SHA-256:
`85230c5cdc88d25140e3b154ecda568e26aea8d205a90f25a4755a0907546b90`.

The complete ignored replay material remains below
`.tool-shed/qualification/idea0020-m2-dd00814/` in each fixture. Malformed databases and sanitized
pre-upgrade snapshots remain further isolated below each sealed run directory and never entered
the operational fixture database or shared hosted database.

## Qualified Claims

- A parent that is locally closed remains effectively open until all governing descendants close;
  a non-governing child does not block it.
- Shared descendants retain two indexed ancestry paths, propagate blockers through both branches,
  deduplicate identical blocker rows, and close the root only after the shared leaf closes.
- Revising an authoritative requirement supersedes its current proof, holds it open, retains the
  old proof record, and accepts a new subject-bound proof as an appended record.
- A terminal child committed before its parent survives interruption. Resume produces exactly one
  terminal parent verdict, reconciliation, and result-propagation edge; replay produces none.
- Schema-3 checkpoints rebuild to a clean database with exact domain-digest, independent-oracle,
  and stored-projection parity on both operating systems.
- Missing parents, conflicting lineage digests, and cycles are explicit in isolated malformed
  copies. Findings stay within the affected ancestry, while the healthy source and unrelated
  control remain closed and unchanged.
- Sanitized file-owned and Hybrid snapshots upgrade in place with stable artifact IDs, retained
  history, reconstructed recoverable claims, explicit unresolved ancestry, idempotent replay, and
  zero invisible orphan claims.

## Scope Boundary

This evidence completes the local M2 portion of G2. Reporter transport, hosted ingestion of the
existing-instance corpus, hosted projections, and browser truth remain M3. Shared-host destructive
fault injection remains prohibited until the M4 qualification namespace passes. Work3 candidate
freeze and Work5 production promotion remain separate future routes.
