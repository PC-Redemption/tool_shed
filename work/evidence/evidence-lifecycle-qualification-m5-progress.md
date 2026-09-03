# Checkpoint: IDEA-0020 M5 Evidence Scale and Route Smoke

Status: in-progress
Recorded: 2026-09-03
Campaign: CAMP-0154
Program Roadmap: PRM-0038, M5-EVIDENCE-SCALE-AND-ROUTE-SMOKE
Candidate commit: `78a78f4d4df8f3a2e7a1cc33d09c33158516591c`
Candidate version: `0.43.0` (unpublished development candidate)
Candidate manifest SHA-256: `4a8620098a632f97f765391934cb26a0fe848c92979d76447e92680fa0dcffbc`
Environment: development only

## Durable Progress

- The clean detached release profile passed 562 of 562 tests.
- The exact candidate is installed in the development web, Linux, and Windows lanes. Development
  web health passed; production was checked read-only and was not changed.
- Candidate-bound low-reasoning lifecycle smoke passed all 11 structural checks on Linux and
  Windows: exact candidate identity, cardinality, current readiness, provenance, gate transfer,
  bidirectional lineage, terminal reconciliation, recursive closure parity, clean tail, revision
  accounting, and idempotent replay.
- The exact-candidate 25,000-element, 100,000-edge, depth-128 closure benchmark retained parity and
  passed every provisional budget. Full rebuild was 10.472 seconds; mutation p95 was 117.583 ms.
- Evidence sealing redacts credentials, bodies, and uncontrolled paths before hashing. The final
  candidate's PASS bundle is reclaimable only after retention and a newer accepted candidate;
  PRODUCT-FAIL evidence remains protected. Oversized intake fails explicitly as `INFRA-BLOCKED`.
- Signature-preserving isolated minimization is stable: 11 attempts reduced the replay to
  `setup` plus `trigger`, with three reproductions required.
- Hosted development currently contains exactly the two enrolled operational fixture projects and
  one stable instance for each; the prior phantom seed projects are absent.

## Running Accumulation Jobs

The following exact-candidate jobs were active when this checkpoint was recorded. Their generated
state is ignored operational evidence and is intentionally resumable. Do not start a second run
with the same inputs while the original process is active.

| Platform | Exact fixture | Serial range | Recorded progress | Pending run |
| --- | --- | --- | ---: | --- |
| Linux | `/home/jon/dev/ts_linux_test_bed` | 830000-830099 | 40/100; last complete 830039 | `tsqh-567564dd52188a1f686b61e8` |
| Windows | `GOGETTER:E:\dev\ts_windows_test_bed` | 930000-930099 | 23/100; last complete 930022 | `tsqh-fe0c6f25840ad64977f6126a` |

State files:

- Linux: `.tool-shed/qualification/scale/idea0020-m5-100-linux-78a78f4-state.json`
- Windows: `.tool-shed\qualification\scale\idea0020-m5-100-windows-78a78f4-state.json`

If either process is no longer active, reissue the same `lifecycle_scale_qualification.py` command
with candidate `78a78f4d4df8f3a2e7a1cc33d09c33158516591c`, version `0.43.0`, its platform and instance ID,
the same serial start, lifecycle count 100, minimum history delta 100000, mutation samples 25, and
the same output path. The state file resolves a pending mutation before advancing and preserves
completed run identities.

## Generated Evidence Bindings

| Evidence | SHA-256 |
| --- | --- |
| Linux route result | `b178f7d9795f4cf9c157fbab7920e69a038f7f1dfb5eafd6f1bfbe03c2cbdcc9` |
| Windows route result | `e3d3fe80a49ced78144f349d90b01b979328ecd1d789c8552a8ff0277f3b68eb` |
| Closure benchmark | `d0496113dce1bbe967bdbf6960514dae90d1430073edc3862833b3bdeafb74eb` |
| Minimization result | `0af4a106b34d893fc07459f5b23b5b8275b5f705d5e81fc897e96e3ad8fe196e` |
| PASS retention bundle | `9bcff6c38aa3178242267d95a9b149a63f0cf89b2dfa96c003a9bad280f11ef5` |
| PRODUCT-FAIL retention bundle | `c261d4fc089ef2e710db8955da4c081f05e78eb6bc1a7334b8752b72d5a6e9d6` |

Generated evidence remains below `work/evidence/generated/idea0020-m5/` and in the two fixture
state paths above. These hashes bind the selected records without versioning raw database output.

## Remaining Work

M5 is not complete. Wait for both 100-lifecycle runs, seal their final PASS results, verify at least
100,000 append-only rows per platform, final reporter drain, exact two-project hosted inventory,
and final dashboard/browser truth. Then record the canonical M5 evidence, complete and reconcile
CAMP-0154, update PRM-0038 so M6 is next, register the Work2 candidate and owner chain, checkpoint
Hybrid state, and run strict validation. M6 remains a separate explicit `ts:work3 IDEA-0020` route;
production remains a separate Work5 route.

Next route: `continue IDEA-0020`.
