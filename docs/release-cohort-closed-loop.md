# Persistent Work2-to-Work5 Release Cohorts

Tool Shed uses the existing Hybrid outcome tables to preserve which Work2 results are waiting for
production release. This lets a maintainer dogfood unpublished work immediately, batch compatible
changes, and pay the Work5 qualification cost once without losing Idea-to-production traceability.

## State model

One mutable `release-cohort` cycle owns zero or more candidate requirements. Each Work2 requirement
records the exact product commit, the owning outcome cycle, its origin artifact, and a passed Work2
checkpoint verification. `release-candidate-member` relationships connect every registered owner
to the cohort. Registration follows active `outcome-parent` relationships, so a PRM or campaign
entry retains its open Map and Idea ownership. Direct work creates one explicit open outcome rather
than becoming unowned release scope.

The lifecycle is:

```text
working -> frozen -> released-pending-reconciliation -> terminal/reconciled
```

- `working`: candidates may be registered and used in the configured work environment.
- `frozen`: the cohort is bound to the exact clean Work5 content commit; registration stops.
- `released-pending-reconciliation`: production publication evidence is attached to every owner.
  This state does not prevent a later Work2 result from starting a fresh working cohort while an
  intentionally continuing parent outcome remains open.
- `terminal`: every registered owner is terminal, reconciled, and has an accepted terminal verdict.

The live SQLite database remains the operational authority. Normal Hybrid checkpoints preserve the
cohort in tracked state and rebuild it exactly. The freeze mutation may occur after the final
content commit to avoid a commit-SHA self-reference; post-release reconciliation is checkpointed.

## Guarded interface

Read current state and retain its project-bound token:

```bash
python3 scripts/release_cohort.py --workspace . --json status
```

After a Work2 product commit, register its nearest open owner. The command expands the full open
parent chain:

```bash
python3 scripts/release_cohort.py --workspace . register \
  --expect <state-token> --project-binding <hybrid-state-binding> \
  --commit <work2-commit> --origin-cycle <cycle-uuid>
```

For direct work without an existing owner, replace `--origin-cycle` with `--accepted-outcome` and
`--summary`. Exact repeated registration does not advance the database revision.

When a pre-cohort Work2 result was already given a terminal local verdict, registration does not
reopen or rewrite it. The guarded command creates one open direct release extension related by
`release-extension-of`, preserves the original verdict as history, and makes only the missing
production-release obligation a cohort candidate. Repeating that backfill reuses the extension.

At Work5, freeze the clean combined candidate, publish it through the repository's ordinary
release route, and record the verified durable publication reference:

```bash
python3 scripts/release_cohort.py --workspace . freeze \
  --expect <state-token> --project-binding <hybrid-state-binding> \
  --content-commit <sha>
python3 scripts/release_cohort.py --workspace . record-release \
  --expect <fresh-token> --project-binding <hybrid-state-binding> \
  --tag <vMAJOR.MINOR.PATCH> --evidence <durable-reference>
```

If exact-SHA CI rejects a frozen content commit, correct the candidate and run `freeze` again with
the new clean `HEAD` plus `--failure-evidence <failed-run-url>`. The guarded retry preserves the
rejected commit and failed-run reference, refuses a silent rebind, and keeps publication blocked
until the replacement content commit passes the ordinary exact-SHA gate.

Reconcile the registered outcome chains from their innermost result to their Idea roots using the
ordinary outcome-transition interface. Finalization fails closed while any registered owner is
open, failed, partial without approval, unreconciled, unpropagated, backed by a nonterminal managed
document, or not recursively closed at its cycle-role closure element. Direct non-document owners
retain the legacy outcome-only gate, and pre-closure schemas retain their compatibility behavior.
When multiple released
cohorts await parent reconciliation, select the exact cohort:

```bash
python3 scripts/release_cohort.py --workspace . finalize \
  --expect <fresh-token> --project-binding <hybrid-state-binding> \
  --authorization <reference> [--cohort-id <cycle-uuid>]
```

The mechanism never treats all open Ideas as release scope. An intentionally excluded candidate
must be resolved before freeze rather than silently stranded.
