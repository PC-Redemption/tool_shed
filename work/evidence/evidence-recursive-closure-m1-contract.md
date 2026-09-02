# Evidence: Recursive Closure M1 Observed Contract

Status: passed
Date: 2026-09-02
Campaign: CAMP-0146
Roadmap: PRM-0037
Milestone: M1-OBSERVED-CONTRACT
Gates: G1-LEGACY-INVENTORY-AND-SCHEMA; G2-PROOF-RUNNER-SAFETY (contract portion)

## Sources inspected

- Canonical Hybrid schema and writers in `scripts/hybrid_state_schema.py`,
  `scripts/hybrid_state.py`, `scripts/document_store.py`, `scripts/outcome_loop.py`,
  `scripts/outcome_reconciliation.py`, and `scripts/release_cohort.py`.
- Local and hosted status readers in `scripts/dashboard_reporter.py` and `dashboard/fleet/`.
- Open `PC-Redemption/tool_shed` issues #57 and #58 through the authenticated `gh` client.
- The read-only `local-hybrid-dashboard` patch v1.0.2 at `/home/jon/dev/ts_patches`, commit
  `d1829d3`, including its manifest, renderer, install/rollback behavior, and tests.
- The live Hybrid schema-2 database at revision 1040. This was a read-only inventory; no semantic
  history was inferred from filenames, prose, lifecycle, or timestamps.

## Observed inventory

The live database contained 464 artifacts, 342 database-owned documents, 136 outcome cycles
(8 nonterminal), 246 requirements, 440 active relationships, 230 evidence references, and 221
verification results. Active relationship counts were: 112 `evidenced-by`, 111 `outcome-parent`,
99 `outcome-result-propagated`, 67 `produces`, 46 `release-candidate-member`, and one each of
`implemented-by`, `release-extension-of`, and `reported-by`.

The core schema already provides immutable artifact/cycle/requirement identities, append-only
events and structural-change accounting, current typed relationships with retirement revisions,
requirements, material changes, evidence, verification results, verdicts, reconciliation,
migration/export/checkpoint ledgers, guarded revisions, and deterministic logical checkpoints.
Schema 2 adds versioned SQLite-owned documents and path/conversion provenance.

The exact missing surfaces are:

- no canonical versioned lineage envelope for every closure-bearing element;
- no requirement-bound lineage claim (the current relationship key stops at artifact-to-artifact);
- no explicit governing/optional/informational requirement classification and requirement digest;
- no obligation-scoped local closure or authorized manual-closure record;
- no graph revision, current-edge/ancestor-path projection, rollup, blocker, or recovery finding;
- no registered declarative proof recipe, attempt lease, retry/cooldown, or supersession record;
- no orphan/reparent/retirement tombstone operation;
- no schema-enforced relationship registry; and
- no typed closure status in the reporter or hosted dashboard.

Current reporting confirms issues #57 and #58: it exposes document lifecycle, outcome lifecycle,
outcome disposition, reconciliation, and planning-queue readiness, but not recursive closure,
subject/evaluator revision, evidence health, graph health, blocker counts, or nearest blockers.
The v1.0.2 local patch is explicitly read-only and correctly treats generated Markdown as a
projection. It improves operator wording but reads the same flattened lifecycle/outcome tables and
therefore cannot supply the missing recursive authority by itself.

No existing writer implements `closed-manual`; manual closure is therefore a new protected
operation, not a legacy state to backfill. Existing terminal cycles and accepted requirements are
historical inputs, but none are automatically reclassified as locally or effectively closed.

## Frozen role classification

- `cycle`: independently actionable durable outcome; owns local closure and may own requirements.
- `obligation`: requirement, milestone, gate, phase, step, checklist item, or acceptance condition;
  owns obligation-scoped closure without requiring an outer cycle.
- `record`: evidence, verdict, decision result, inventory, runbook, checkpoint, assertion, or
  tombstone; has no closure state.
- `projection`: edge/path index, rollup, blocker row, dashboard row, or generated view; has no
  closure state and cannot authorize closure.

Legacy prose containing a promise, next action, gate, or unresolved acceptance condition is
reported as `UNCLASSIFIED_COMMITMENT` until an authorized migration binds it to an obligation or
child cycle. It is never guessed from wording.

## Minimum schema-3 delta

Reuse all existing artifact, document, cycle, requirement, relationship, evidence, verdict,
reconciliation, event, revision, and checkpoint primitives. Add only these closure-domain tables:

1. `closure_element` — one current versioned envelope per closure-bearing cycle or obligation,
   including role, kind, subject revision/digest, schema version, and envelope digest.
2. `lineage_claim` — current immediate requirement-bound claims plus retirement revision; this is
   the envelope's normalized current projection and is regenerated from the stored envelope.
3. `closure_record` — append-only local closed-loop/manual records bound to element, obligation,
   subject, method, authorization, and evidence.
4. `closure_graph_meta` — singleton graph/evaluator version and authoritative source digest.
5. `closure_ancestor_path` — derived ancestor/descendant/depth/path-count projection.
6. `closure_rollup` and `closure_blocker` — revision-bound four-field status, reasons, counts, and
   obligation-scoped blockers.
7. `proof_recipe` and `proof_attempt` — immutable recipe identity/current revocation plus leased,
   idempotent append-only executions.
8. `recovery_case` — one bounded current case per detected lineage defect, with owner, aging,
   retry/cooldown/escalation, and exact terminal disposition.
9. `lineage_tombstone` — append-only authorized reparent/retire/abandon history.

Relationship assertions and proof/recovery events use the existing append-only `event` ledger;
evidence and verification results reuse existing tables. All new authoritative tables enter the
domain digest and logical checkpoint. Projection tables enter checkpoints only as explicitly
rebuildable state and must match a fresh recursive rebuild before certification.

Schema 3 is required rather than silently changing schema 2. Schema-2 clients must refuse before
mutation and name the updater. The migration is exact-manifest, backup-first, interruption-safe,
and shadow-rebuilt. It imports only explicit current relationships and requirements; ambiguous or
missing bindings become visible recovery/unclassified findings and keep affected roots open.

## Frozen closure contract

For each element and exact subject revision:

```text
effective_closed = locally_closed
                   AND evidence_health in {not-required, current}
                   AND graph_health == valid
                   AND every governing obligation and child is effectively closed
```

The four stored/reportable facts are:

- `local_closure`: `open`, `closed-loop`, `closed-manual`;
- `evidence_health`: `not-required`, `current`, `missing`, `stale`, `checker-error`;
- `graph_health`: `valid`, `recovery-required`, `invalid`;
- `effective_closed`: Boolean.

Reasons are `LOCAL_OPEN`, `DESCENDANT_OPEN`, `UNPROVEN`, `STALE_EVIDENCE`, `CHECKER_ERROR`,
`MISSING_PARENT`, `MISSING_REQUIREMENT`, `UNFULFILLED_REQUIREMENT`, `CYCLE`,
`CONFLICTING_LINEAGE`, `UNCLASSIFIED_COMMITMENT`, or `STALE_ROLLUP`. Manual closure is local,
revision-bound, authorization-required, and prohibited for production/release/security/compliance
gates unless their owning policy explicitly permits it. It never closes descendants.

## Frozen proof and recovery safety

Automatic proof is disabled unless an immutable checker and versioned recipe were registered
before the attempt. The recipe binds exact obligation, subject revision/digest, target identity,
checker/recipe digest, freshness, read/write/network/credential/production/cost classes, allowed
workspace and target, timeout/resources, retry/cooldown, output schema/redaction, and pass/fail
semantics. Free-form generated shell is never a recipe.

Only read-only, local, nonprotected recipes may run automatically inside the active authority
envelope. Mutating, credentialed, external-cost, cross-workspace, or production recipes require
explicit current authority. Attempts are idempotent on element, obligation, subject, recipe digest,
and target; one lease prevents duplicates. Blocked, timed-out, malformed, checker-error, or
superseded attempts do not prove failure or completion.

Every orphan produces one `RECOVERY_REQUIRED` case scoped to its affected ancestry. Retry and
cooldown are bounded; unresolved age escalates visibly; release cohorts containing an affected
root fail closed. The only terminal exits are exact parent restoration, explicitly authorized
reparent, or explicitly authorized retirement/abandonment with a tombstone. A normal clean
checkpoint requires zero unresolved governing orphans, cycles, conflicting lineage, or
unclassified commitments.

## Frozen Work2 and later budgets

The corpus and provisional budgets remain unchanged: 25,000 elements, 100,000 edges, maximum depth
128; 20 ms summary, 50 ms first 100 blockers, 250 ms mutation through 128 ancestors, 60 seconds
full rebuild, and 250 ms hosted API excluding network. Work2 must measure and report them. Work3
binds final qualification to one exact commit/schema/evaluator/fixture/target set. Work5 remains the
only production promotion route.

## Result

`G1-LEGACY-INVENTORY-AND-SCHEMA` is satisfied for planning and implementation: the observed gaps
justify schema 3 and the minimum table family above. The contract portion of
`G2-PROOF-RUNNER-SAFETY` is satisfied. Implementation, migration/recovery proof, performance parity,
development deployment, Work3 qualification, and Work5 release remain open in PRM-0037.
