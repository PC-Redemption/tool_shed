# Hybrid SQLite HPT2 Closed-Loop Parity Evidence

Status: passed
Evidence ID: EVID-G2-HPT2-PARITY
Gate: G2-SUBSTRATE-LOOP-PROVEN
Campaign: implement-and-qualify-hpt2-closed-loop-vertical-slice
Target: disposable shadow workspaces and local work3 candidate
Date: 2026-08-28

## Exact Historical Disposition

The frozen G1 inventory is confirmed: this repository has no retained artifact whose title or
stable ID is HPT2 and no exact original HPT2 request, development-change ledger, campaign/milestone
history, product commit, or qualification bundle. The vertical slice does not infer any of them.

The resulting dimensions are intentionally independent:

```text
lifecycle: terminal
outcome verdict: partial
reconciliation: reconciled
```

The comparison is complete, its four missing surfaces are named residual work, and those unknowns
block a `satisfied` HPT2 verdict. This is a closed loop with a partial outcome, not a false claim of
delivery.

## Parity Result

`scripts/outcome_reconciliation.py` imports the current independent bootstrap closure projection
and tracked UUIDv4 assignments into a new shadow database. Requirements, material changes, evidence
results, and verdicts reconstruct exactly from SQLite. HPT2 then records its available operator
origin, two owner-authorized development changes, three current product-truth references, missing
history, partial verdict, and reconciled comparison.

The file-first and hybrid results are byte-identical after canonical serialization for all eight
operations: orientation, status, next, overview, dependency/gate lookup, history, reconciliation,
and one bounded mutation. The mutation adds one typed `reported-by` relationship under its own
managed revision and leaves checkpoint policy pending as expected.

Five focused tests passed with resource warnings treated as errors:

```text
PYTHONPATH=scripts:. python3 -W error::ResourceWarning -m unittest -v \
  tests.test_outcome_reconciliation
```

The tests prove:

- exact bootstrap projection and eight-operation parity;
- explicit unknown-history preservation and a correct partial/reconciled HPT2 result;
- UUIDv4 assigned-ID reuse and foreign-project refusal;
- unchanged product/source bytes;
- one-revision import and bounded-mutation accounting;
- deterministic checkpoint and fresh rebuild semantic parity; and
- an independent fresh-workspace import with identical projection and operation digests.

Every database used by this evidence was inside a disposable Git workspace. The canonical
maintainer has no live `.tool-shed/state.sqlite3`, and no file authority, campaign/roadmap authority,
deployment, release, installed skill, or client was changed.
