# Outcome Loop Findings

Tool Shed schema 4 adds a bounded, local discovery index for outcome loops that need operator
attention. Hybrid SQLite remains authoritative. The hosted dashboard receives a read-only
projection and cannot run a command or mutate a workspace.

The first implemented finding class is deliberately narrow:

- category: `semantic-lifecycle-drift`;
- reason: `PROMOTED_IDEA_LIFECYCLE_STALE`;
- condition: a promoted Idea document is still `active` after its owning outcome cycle is
  terminal and its latest satisfied or superseded verdict is reconciled;
- expected correction: `completed`, or `superseded` when the verdict disposition is superseded.

Findings use a stable `LOOP-…` identifier derived from the semantic condition and subject. Every
managed Hybrid write refreshes this index. A repeated observation updates the same row; a corrected
condition resolves it; a later recurrence reopens the same ID and increments its recurrence count.

## Local operations

Obtain a fresh Hybrid project binding before the one-time schema migration:

```bash
python3 scripts/project_identity.py --workspace . identity --operation hybrid-state --json
python3 scripts/loop_findings.py --workspace . migrate --project-binding <binding>
python3 scripts/loop_findings.py --workspace . audit
python3 scripts/loop_findings.py --workspace . resolve LOOP-17A1B2C3D4E5
```

Migration requires a valid schema-3 database, copies a verified backup, upgrades a shadow copy,
seeds current findings, audits it, and atomically promotes it. `audit` and `resolve` are read-only.
`resolve` re-reads local authority and reports the controlled mitigation class; the Tool Shed chat
route `ts: resolve loop <finding-id>` performs the actual supervised local correction after checking
the subject’s current revision and outcome state.

## Hosted projection

Report schema 8 carries at most 50 active and 50 recently resolved findings. The server accepts
only controlled categories, reasons, state fields, timestamps, counts, subject IDs, and the exact
command `ts: resolve loop <finding-id>`. The Outcome Reconciliation screen renders active findings
per reporting instance and offers **Copy Tool Shed command**. It does not expose a hosted action
channel, writeback, or remote execution.

Historical recovery remains supervised. This first slice does not claim exhaustive discovery of
all legacy loop classes and does not force-close past work. Later milestones can add separately
tested classes and a deterministic history-review manifest while preserving zero unexplained—not
necessarily zero open—loops as the acceptance rule.
