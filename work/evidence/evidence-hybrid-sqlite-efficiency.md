# Hybrid SQLite Context-Efficiency Evidence

Status: passed
Evidence ID: EVID-G2-EFFICIENCY
Gate: G2-SUBSTRATE-LOOP-PROVEN
Campaign: 105-implement-and-qualify-hpt2-closed-loop-vertical-slice
Date: 2026-08-28

## Measurement Contract

`scripts/outcome_reconciliation.py --workspace . benchmark` runs the same expected semantics for
eight operations across the frozen fixtures:

- `small`: 25 deterministic records, 66,088 file-first context bytes;
- `maintainer`: exact tracked inventory at the candidate worktree, 415 files and 5,024,965 bytes;
  and
- `large`: 2,500 deterministic records, 2,574,888 file-first context bytes.

The local product surface does not expose provider-reported usage. Estimated tokens therefore use
the documented UTF-8-bytes-divided-by-four fallback and are labeled estimates. Hybrid measurement
is the actual purpose-built result capsule plus a fixed 384-byte query envelope. Each of the 24
rows records file and capsule bytes, estimated tokens, files/queries/rows read, projection bytes,
round trips, duration, fallback, and semantic/evidence parity. The tool also records the source
commit and current source-tree digest on every run.

## Result

```text
operations: 24
median context reduction: 99.975%
full-tree fallback: 0.0%
semantic parity: passed
evidence parity: passed
```

The least favorable operation was the small-fixture full reconciliation capsule at 97.93%
reduction. Maintainer operations ranged from 99.97% to 99.99%; large operations ranged from 99.95%
to 99.98%. All exceed the required 70% median reduction and no run approaches the maximum 5%
explained fallback limit.

The suite does not claim to measure hidden prompts, provider indexing, caching, or undocumented
tokenization. Migration, corruption, backup, and recovery are covered by separate substrate tests
and are not included in the steady-state denominator.
