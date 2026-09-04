# Risk-Adaptive Verification Hooks Work2 Evidence

Status: passed
Date: 2026-09-04
Campaign: `CAMP-0155` (`implement-risk-adaptive-verification-hooks`)
Candidate: `60d78457eb8eb9817cbd34863bfb9031256455a9`

## Outcome

The schema-3 recursive-closure proof contract now records a deterministic, versioned verification
policy decision for every new proof recipe. It preserves the classified profile, effective
profile, policy and decision digests, reason codes, required recipe set, governing floors, and
escalation history through recipe registration, proof-attempt binding, and closure evidence.

Policy revision 1 is intentionally hooks-only. `automatic_lowering_enabled` is false, so a
demonstrably mechanical change is classified as `mechanical` but remains effectively `high-risk`
and requires the complete existing loop. This prevents the new contract from reducing verification
depth before comparative token, elapsed-time, missed-regression, and false-closure qualification.

## Exact Candidate

- Candidate commit: `60d78457eb8eb9817cbd34863bfb9031256455a9`
- Disconnected snapshot SHA-256:
  `c6f32c6be85bdc639a34f50d281a247578e8db85e4f395fd64ab0277b8b84f9b`
- `scripts/verification_policy.py` SHA-256 on source, Linux, and Windows:
  `0b896f4854aa7b277ae00b4bfbca043ea9fc78d13c619a5b4ba4f249d4b484da`
- Policy digest:
  `f49b3bbd1109fcfd59ea27f7b240969741a040dc5974566b754d40a20e10d0a3`
- Mechanical fixture decision digest on Linux and Windows:
  `d0930953ce93c23498b7ca1769bdb547269148347b80eb68e0ea8e7a3b594b62`

The snapshot contains no Git metadata or project `work/` tree. An initial overly narrow archive
omitted the test suite; Linux validation rejected it before full qualification. That inactive copy
is retained as `tool_shed.candidate-60d7845-incomplete`, while the active Linux and Windows
snapshots use the corrected exact archive above.

## Verification Matrix

| Lane | Exact target | Evidence | Result |
| --- | --- | --- | --- |
| Clean local candidate | detached worktree at candidate commit | 16 focused policy/closure tests; full validator | PASS: 567/567 tests; full validation in 32.051 seconds |
| Linux | `sup:/home/jon/dev/ts_linux_test_bed` | strict disconnected-snapshot integrity; focused tests; full validator; installed mechanical classification | PASS: 16/16 focused and 567/567 full tests; full validation in 27.647 seconds |
| Windows | `GOGETTER:E:\dev\ts_windows_test_bed` | staged strict integrity and validation before swap; installed mechanical classification | PASS: 16/16 focused and 567/567 full tests; full validation in 112.166 seconds |
| Hosted development | compose project `tsrookarocom-dev` at `/home/jon/docker/ts.rookaro.com-dev` | exact staged commit, image marker, docs health, dashboard health | PASS: image `tool-shed-dashboard:dev-60d78457eb8e`; development and dashboard HTTP 200 |
| Production observation | compose project `tsrookarocom` | read-only health check | PASS: HTTP 200; no production mutation |

Linux and Windows both produced the same policy and decision digests. Their mechanical fixture
reported `classified_profile=mechanical`, `effective_profile=high-risk`, reason
`automatic-lowering-disabled`, and the required recipes `edit`, `targeted-verification`,
`applicable-tests`, `diff-review`, `recursive-closure`, and `independent-verification`.

## Contract Coverage

- Mechanical, normal, and high-risk classification are deterministic and content-addressed.
- Mixed scope uses the highest applicable profile.
- Parent minimums, production/protected boundaries, unsafe side effects, migrations, controller or
  orchestration work, architecture, recovery, security, credentials, dependency changes, stale or
  failed evidence, unknown scope, and unexpected diffs cannot be lowered.
- A passed proof must repeat the checker, recipe, target, subject, verification-policy, and
  policy-decision digests plus the effective profile and complete recipe set.
- The resulting closure record retains the policy decision and actual evidence references.
- A changed context produces a different decision and recipe digest, so historical proof cannot
  silently satisfy the new policy identity.

## Recovery And Boundary

- Linux rollback: `/home/jon/dev/ts_linux_test_bed/tool_shed.before-idea0019-g7-60d7845`
- Windows rollback: `E:\dev\ts_windows_test_bed\tool_shed.before-idea0019-g7-60d7845`
- Hosted development can roll back by staging its previous exact commit and restoring the previous
  non-secret image-tag field.
- Existing unrelated App Server changes in the canonical worktree were neither committed nor
  included in the candidate snapshot.
- Git push, publication, production migration/deployment, automatic profile lowering, measured
  token-savings claims, Work3 qualification, and Work5 reconciliation remain outside this Work2
  result.
