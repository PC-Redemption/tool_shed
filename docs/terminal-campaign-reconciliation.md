# Terminal Campaign Reconciliation

Tool Shed Hybrid schema 6 adds an execution ledger for campaigns that can outlive their actual
work. It keeps the campaign lifecycle, observed execution result, outcome verdict, and scheduler
assignment reconciliation independent.

Normal completion remains the route for an accepted, evidence-backed outcome. Terminal
reconciliation is only for a campaign whose runs and operations are all terminal while pending or
leased assignments are provably stale. It never turns terminal execution into outcome success.

## State and disposition

`administratively-reconciled` means execution ended and stale control-plane assignments were
retired, without judging the accepted outcome satisfied. `not-satisfied` records an explicit
negative outcome. `superseded` requires a replacement outcome reference. These remain distinct
from `satisfied`, from a deferred or abandoned campaign, and from `blocked`, which still means
runnable work cannot currently proceed.

Runs and operations are terminal only in `completed`, `failed`, `cancelled`, or `superseded`. A
pending or leased assignment is retirable only when it is explicitly non-runnable, has a documented
stale reason, and every referenced run or operation is terminal. Supported stale reasons are
`terminal-owner`, `expired-lease`, `orphaned-owner`, and `superseded-owner`.

## Guarded route

Migrate schema 5 once, preserving the verified backup:

```text
python3 scripts/campaign_execution.py --workspace . --json migrate \
  --project-binding <hybrid-state-binding>
```

An execution adapter records an exact current snapshot using the state token reported by
`status`:

```text
python3 scripts/campaign_execution.py --workspace . --json status CAMP-0123
python3 scripts/campaign_execution.py --workspace . --json record-snapshot CAMP-0123 \
  --snapshot execution.json --expect <state-token> \
  --project-binding <hybrid-state-binding> --actor <adapter>
```

Planning is read-only. It classifies every pending assignment and returns an applicable manifest
only when there are no runnable assignments and no nonterminal runs or operations:

```text
python3 scripts/campaign_execution.py --workspace . --json plan CAMP-0123 \
  --disposition administratively-reconciled \
  --reason <reason> --actor <actor> --authorization <authorization-reference> \
  --handoff-evidence <optional-reference> > terminal-reconciliation.json
```

For `superseded`, pass `--superseding-outcome <reference>`. Apply requires the exact project
binding and unchanged manifest. It rechecks document, cycle, execution, run, operation, and
assignment state after acquiring the transaction; changed or newly runnable work fails closed.

```text
python3 scripts/campaign_execution.py --workspace . --json apply \
  --manifest terminal-reconciliation.json \
  --project-binding <hybrid-state-binding>
```

One atomic commit retires only manifest-classified assignments, closes the execution and outcome
cycle, writes the explicit non-success verdict and reconciliation, updates the campaign projection,
propagates the terminal child result, and appends an immutable audit record. The audit preserves
prior state, counts, individual assignment dispositions, execution result, reason, actor,
authorization reference, and optional handoff or superseding references. Reapplying the same
manifest is a read-only idempotent success.

Checkpoint/rebuild includes the execution ledger, immutable source snapshots, and reconciliation
audit. Local status, queue eligibility, reporter inventory, hosted API, and dashboard consume the
same terminal lifecycle and disposition; a reconciled campaign is never offered for dispatch.

## Choosing the lifecycle route

| Condition | Route |
| --- | --- |
| Completion gate passed and accepted outcome is evidenced | Complete normally with `satisfied` or `satisfied-with-approved-change`. |
| All execution terminal; only proven stale assignments remain | Reconcile with `administratively-reconciled`, `not-satisfied`, or `superseded`. |
| Runnable work exists but cannot proceed | Keep active and mark `blocked`. |
| Work is intentionally postponed | Defer with a reactivation condition. |
| Work is intentionally ended without replacement | Abandon while preserving history. |
| Remaining intent moved to another outcome | Reconcile or abandon as `superseded` and name the replacement. |
