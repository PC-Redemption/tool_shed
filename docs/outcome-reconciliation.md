# Outcome Reconciliation Vertical Slice

Status: qualified HPT2 compatibility slice
Schema version: 1

`scripts/outcome_reconciliation.py` began as Tool Shed's first database-backed closed-loop
consumer. Its HPT2 routes remain the qualified compatibility slice described here; the generic
manifest interface and authority rules are defined by
[`universal-closed-loop-outcome-reconciliation.md`](universal-closed-loop-outcome-reconciliation.md).
Neither interface moves campaign, roadmap, milestone, general Markdown, or product-document
authority.

## HPT2 Disposition

The preserved repository contains the operator report that HPT2 lacked visible idea-to-product
closure, but it contains no exact original HPT2 Idea Brief, requirement/change ledger, campaign or
milestone history, product commit, or target qualification bundle. The tool never reconstructs
those facts from plausible later history.

The HPT2 loop is therefore explicit and terminal in three independent dimensions:

```text
lifecycle: terminal
outcome verdict: partial
reconciliation: reconciled
```

`reconciled` means the comparison was completed and its differences were dispositioned. It does
not mean the outcome was satisfied. The four missing historical surfaces remain named residual
work and block a `satisfied` HPT2 verdict.

## Independent Bootstrap Parity

The importer reads the current guarded bootstrap closure manifest and the tracked UUIDv4 assigned-ID
manifest. In one managed SQLite revision it records the exact requirement, material-change,
evidence, and verdict projections; current product-truth hashes; the missing-origin exception; the
partial HPT2 verdict; and both reconciliation results. Imported product/source files remain
byte-authoritative and unchanged.

The parity report reconstructs the bootstrap projection from SQLite and compares it with the file
authority. It also compares identical file-first and hybrid results for:

- orientation and status;
- next action and overview;
- dependency/milestone/gate lookup;
- material-change history;
- complete reconciliation; and
- one bounded, revision-accounted relationship mutation.

Qualification repeats the import in a fresh disposable Git workspace and rebuilds the database
from the tracked logical checkpoint. This proves assigned-ID, source-byte, projection, operation,
semantic, event/ledger, and recovery parity without creating a database in the canonical maintainer.

## Commands

Obtain a fresh `hybrid-state` project binding before each mutation. The following commands are for
a disposable shadow workspace until the maintainer conversion campaign separately authorizes live
use:

```text
python3 scripts/outcome_reconciliation.py --workspace . apply \
  --project-binding <hybrid-state-binding>
python3 scripts/outcome_reconciliation.py --workspace . mutate \
  --project-binding <hybrid-state-binding>
python3 scripts/outcome_reconciliation.py --workspace . report \
  --backend file --operation reconciliation
python3 scripts/outcome_reconciliation.py --workspace . report \
  --backend hybrid --operation reconciliation
python3 scripts/outcome_reconciliation.py --workspace . qualify
python3 scripts/outcome_reconciliation.py --workspace . benchmark
```

After a later bootstrap evidence or verdict transition, reconcile the retained manifest into the
existing hybrid database through the guarded sync route instead of issuing direct SQL:

```bash
python3 scripts/outcome_reconciliation.py --workspace . sync \
  --project-binding <hybrid-state-binding>
python3 scripts/outcome_reconciliation.py --workspace . qualify
python3 scripts/hybrid_state.py --workspace . checkpoint \
  --project-binding <hybrid-state-binding>
```

`sync` reimports the changed bootstrap source bytes, preserves its assigned artifact identity,
updates the existing requirements, evidence results, verdicts, and reconciliation projection in
one managed revision, and inserts only newly assigned material changes. The parity check must pass
before the new projection is checkpointed.

`apply` and `mutate` are guarded writes. `report`, `qualify`, and `benchmark` are read-only.
`qualify` exits nonzero on any bootstrap or operation mismatch. `benchmark` exits nonzero below the
frozen 70% median context-reduction threshold, above the 5% explained-fallback ceiling, or when
semantic/evidence parity fails.

## Efficiency Measurement

The benchmark runs the eight state-heavy operations against the frozen `small` (25 records), exact
maintainer inventory, and deterministic `large` (2,500 records) fixtures. File-first context is the
actual fixture or tracked-worktree byte inventory. Hybrid context is the purpose-built capsule plus
query envelope; it does not count hidden provider behavior. Provider usage is unavailable in this
local surface, so estimated input tokens use the documented four-UTF-8-bytes-per-token fallback.

Every row reports context bytes, estimated tokens, files/queries/rows read, round trips, fallback,
and semantic/evidence parity. Migration, corruption, and recovery are qualified separately and do
not dilute the steady-state denominator.
