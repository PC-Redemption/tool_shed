# Outcome Loop Findings

Tool Shed schemas 4 and 5 provide a bounded, local discovery index for outcome loops that need operator
attention. Hybrid SQLite remains authoritative. The hosted dashboard receives a read-only
projection and cannot run a command or mutate a workspace.

Schema 4 retains the initial promoted-Idea lifecycle check. Schema 5 also discovers current:

- blocked outcomes and nonterminal outcomes with no activity for 30 days;
- terminal but unreconciled outcomes and reconciled outcomes with an open disposition;
- terminal reconciled child results that were not propagated to their parent;
- invalid or recovery-required recursive closure lineage; and
- missing, stale, or checker-error closure evidence.

Current clients additionally apply the same semantic check to every managed Idea, Map, PRM, and
campaign. A terminal, reconciled outcome is classified against its cycle-role recursive closure:

- an active document whose recursive closure is closed is a safe lifecycle repair candidate;
- an active document whose descendants remain open is retained open and reported as closure debt;
- a completed document whose recursive closure remains open stays completed but is reported as
  closure debt; and
- terminal database lifecycle with a nonterminal body `Status:` is a body-only repair candidate.

These checks never write closure projection tables. `closure_element` and `closure_rollup` remain
derived authority refreshed by normal managed transactions.

Healthy progressing open outcomes remain visible work, not attention findings.

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

Migration advances one guarded step from schema 3 to 4 or schema 4 to 5. It copies a verified
backup, upgrades a shadow copy, seeds current findings, audits it, and atomically promotes it.
`audit` and `resolve` are read-only.
`resolve` re-reads local authority and reports the controlled mitigation class; the Tool Shed chat
route `ts: resolve loop <finding-id>` performs the actual supervised local correction after checking
the subject’s current revision and outcome state.

## Hosted projection

Report schema 9 carries at most 50 active and 50 recently resolved findings and separates queued
campaigns, working campaigns, and recursive closure debt in the project summary. The server accepts
only controlled categories, reasons, state fields, timestamps, counts, subject IDs, and the exact
command `ts: resolve loop <finding-id>`. Overview and Needs Attention copy exact built-in status
routes; Work and Outcome Reconciliation copy reporter-provided finding routes; Health copies exact
diagnostic routes only when its current state is actionable. History-only rows do not gain an
action. The service does not expose a hosted action channel, writeback, or remote execution.

Historical recovery remains supervised. Current-state discovery does not claim that every legacy
manifest can be inferred safely and does not force-close past work. A later history-review manifest
can preserve zero unexplained—not necessarily zero open—loops as the acceptance rule.

## Supervised historical review

`audit --history` includes active and resolved finding history and accepts repeatable bounded
`--source` selectors for an exact finding ID, subject ID, category, reason, or state. A review then
binds explicit operator decisions to the current Hybrid revision, domain digest, finding rows, and
managed-document revisions:

```bash
python3 scripts/loop_findings.py --workspace . audit --history --source IDEA-0001
python3 scripts/loop_findings.py --workspace . history-plan \
  --decision LOOP-ABC123DEF456=apply-expected-state \
  --rationale "The terminal reconciled outcome proves the promoted Idea is complete." \
  --complete-cluster
python3 scripts/loop_findings.py --workspace . history-validate \
  --manifest <review-manifest.json>
python3 scripts/loop_findings.py --workspace . history-apply \
  --manifest <review-manifest.json> --expect <manifest-token> \
  --project-binding <hybrid-state-binding> --authorization <review-evidence>
```

Every selected item requires one controlled decision: `apply-expected-state`, `retain-open`, or
`requires-evidence`. `--complete-cluster` refuses a manifest that omits another active finding in
the same outcome-parent lineage. Apply records review evidence for every decision; only the
safe recursively closed lifecycle correction or body-only status correction mutates product state.
Open-descendant and completed-but-open closure debt is retained for descendant reconciliation.
Any intervening database,
finding, document-revision, project, digest, or cluster change makes the manifest stale. The normal
managed-write refresh then re-audits findings, propagation/lineage authority, and checkpoint need.
