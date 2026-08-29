# Universal Closed-Loop Outcome Reconciliation Contract

Status: approved design contract
Schema version: 1
Initiative: universal-closed-loop-outcome-reconciliation

This contract defines Tool Shed's universal outcome loop. It separates finishing work from proving
what that work achieved. It applies to every durable entry point while preserving the approved
hybrid SQLite/file authority boundary.

## Core Invariant

A durable Tool Shed outcome is complete only when all of the following are explicit:

1. the stable origin and accepted outcome;
2. accepted requirements and revisions;
3. every material development change and its authorization;
4. current product truth and endpoint-appropriate evidence;
5. the outcome verdict and residual work;
6. reconciliation state; and
7. propagation of the local result to every owning loop through the initiative root.

Terminal children and empty queues never imply that their parent outcome is satisfied. A loop may
close with a non-success disposition when the comparison is complete and the result is explicit.

## Independent Dimensions

Every loop reports three independent dimensions:

| Dimension | Values | Meaning |
| --- | --- | --- |
| Lifecycle | proposed, queued, working, blocked, terminal | Whether the bounded activity is still running |
| Outcome verdict | open, satisfied, satisfied-with-approved-change, partial, failed, rejected, superseded, parked, not-applicable | What the accepted outcome comparison concluded |
| Reconciliation | open, reconciliation-required, reconciled | Whether intent, changes, truth, evidence, residuals, and propagation were compared and dispositioned |

`reconciled` does not mean `satisfied`. `terminal` does not mean `reconciled`. An empty campaign
queue is only queue state.

## Supported Origins

The contract is entry-point neutral. A loop may originate from:

- an Idea Brief or brainstorm promoted into PRM;
- a project map;
- a Program Roadmap or milestone;
- a campaign;
- a workpackage, ticket, checklist, spike, ADR, inventory, decision matrix, or runbook;
- a durable direct-work closure capsule; or
- an imported historical outcome overlay.

Every durable origin receives or inherits an immutable UUIDv4 identity. Paths, filenames, display
numbers, titles, and queue positions remain mutable metadata and never become identity.

## Minimum Closure Record

One logical loop contains:

- `cycle_id`, `kind`, `origin_artifact_id`, and optional `parent_cycle_id` relationship;
- the accepted outcome, origin revision, and lifecycle state;
- requirements with accepted revision, disposition, milestone, and evidence gate;
- material changes tied to requirements or decisions, authorization, supersession, and evidence to
  rerun;
- evidence references, target identity, hashes when applicable, and verification results;
- current product-truth references appropriate to the requested endpoint;
- one outcome verdict for each governed scope;
- reconciliation state, comparison revision/time, and residual work; and
- explicit propagation from child result to the owning cycle.

The schema-version-1 hybrid tables already provide the minimum cycle, artifact, relationship,
requirement, material-change, evidence, verification, verdict, reconciliation, event, and ledger
primitives. The universal feature must use those primitives before proposing a schema expansion.

## Material Changes

A material change affects the accepted outcome, requirement, scope, product-facing behavior,
supported boundary, target, acceptance, authority, or safety posture. Refactoring and ordinary
implementation details that preserve the accepted result are not material changes.

Every material change records:

- a stable change ID;
- affected requirement or decision IDs;
- summary and rationale;
- authorization reference;
- any superseded change;
- evidence that must be rerun; and
- the managed revision and source commit.

A change cannot be appended with no affected state or no evidence rerun. A final verdict remains
open or becomes partial when a material difference lacks an explicit disposition.

## Evidence And Product Truth

Evidence is endpoint appropriate:

- source changes require code and focused/full validation evidence;
- a build requires build output identity;
- a release requires exact content commit, CI, provenance, tag, and publication evidence;
- deployment requires target identity and current observation;
- qualification requires the declared target, procedure, and result; and
- manual acceptance requires an explicit authorization reference.

A commit does not prove deployment. A test does not prove target qualification. Completed work
artifacts are historical evidence, not current product truth by themselves.

When implementation stops at Work2, `release_cohort.py` persists the exact commit and every open
owning cycle as an awaiting-release requirement. Work5 publication evidence is attached to those
registered owners, and the cohort cannot reconcile until their outcome chains are terminal and
reconciled. This preserves batching and local dogfooding without guessing release scope from all
open Ideas.

## Propagation Rules

Each terminal child propagates its outcome verdict, reconciliation state, residuals, and evidence
references—not merely its lifecycle state—to its parent.

- A parent remains open when any required child is missing, open, or unreconciled.
- A failed, partial, rejected, parked, or superseded child cannot silently satisfy a parent.
- A parent may be `satisfied-with-approved-change` only when the governing change and authorization
  are explicit and all affected evidence was rerun.
- A roadmap or initiative is satisfied only when its accepted outcome and every applicable gate
  are satisfied and reconciled.
- `next`, `overview`, and status surfaces reveal the nearest open owning loop after local work or a
  queue ends.

## Direct Work

Clear bounded direct work must not acquire mandatory project maps, roadmaps, or campaigns. When a
durable result exists without a normal artifact, Tool Shed may store a compact closure capsule with
origin summary, accepted outcome, changed paths or product references, verification, verdict,
reconciliation state, and optional parent cycle. Conversational work without a durable project
effect opens no durable loop.

## Authority Boundary

One field has one editable authority.

| Surface | Editable authority | Database role |
| --- | --- | --- |
| Campaign, queue, roadmap, milestone, and gate lifecycle | Existing files and scripts | Read/query relationships and closure projections only |
| Idea Brief and general Markdown bodies | Files | Identity, hash, relationship, and imported provenance only |
| Stable closure identities and typed relationships | SQLite after guarded cutover | Editable authority |
| Requirements, material changes, evidence references, verification results, verdicts, and reconciliation | SQLite after guarded cutover | Editable authority |
| Revisions, managed operations, events, migration/export/checkpoint ledgers | SQLite | Editable authority |
| Tracked logical checkpoint | Generated file | Read-only portable projection used for rebuild |

Integrations must not introduce dual writes. A legacy file writer must refuse SQLite-owned fields.
Owner-authored narratives remain byte-preserved and may be imported by hash without normalization.

## Generic Tool Contract

`scripts/outcome_reconciliation.py` provides one project-bound engine:

- `audit`: read-only discovery of open, terminal-unreconciled, invalid, or unpropagated loops;
- `prepare`: create an exact non-mutating proposal from explicit origins, relationships, changes,
  evidence, product truth, and desired disposition;
- `validate`: verify schema, identities, graph, authority, evidence, coverage, propagation, and
  current tokens;
- `apply`: perform only the exact prepared manifest in one guarded managed transaction;
- `report`: render compact human or JSON status, history, orientation, and reconciliation views;
- `backfill-plan`: propose historical overlays without rewriting source artifacts;
- `backfill-apply`: apply only exact, unambiguous, approved overlays; and
- `campaign-result-plan` and `direct-plan`: prepare compact terminal local-result manifests without
  moving file lifecycle authority or requiring planning artifacts for bounded direct work;
- `transition-plan` and `transition-apply`: close an owning loop only from exact propagated child
  cycles, an explicit disposition, reconciliation state, and authorization; and
- compatibility commands for the preserved HPT2 slice.

Semantic dispositions, authorizations, missing relationships, and historical facts cannot be
invented. `prepare` and `backfill-plan` retain unknowns. `apply` refuses ambiguity, stale state,
foreign projects, authority conflicts, graph cycles, missing evidence, or unexpected writes before
semantic mutation.

## Historical And As-Of Reporting

Historical backfill uses overlays. Original artifacts remain unchanged. An overlay records when
the later knowledge was learned and never implies it existed at the historical time.

An `--as-of` report uses only revisions and events available at that boundary and labels later
overlays separately. Missing origins, changes, commits, target evidence, or acceptance records are
explicit residuals. Plausible inference is not fact.

## Recovery And Portability

- The live SQLite database is ignored and mutable.
- Managed writes are locked, revision-accounted, expected-write checked, and evented.
- Direct SQL is detected and requires explicit reconciliation before another managed write.
- A deterministic tracked checkpoint contains complete logical state and ledger identities.
- Rebuild into a new database must reproduce the domain digest and semantic reports.
- Updaters protect the database, storage marker, checkpoint, assigned IDs, source files, and skill
  synchronization under protocol 4 or later.
- Backup, rollback, downgrade/refusal, branch/worktree lineage, and interrupted-write tests remain
  release requirements.

## Context Contract

Normal status, next, overview, history, gate lookup, and reconciliation queries use compact
database-backed capsules. The median measured context reduction across representative fixtures
must remain at least 70 percent, explained full-scan fallback no more than 5 percent, and semantic
and evidence parity 100 percent. No provider-internal token claim is inferred when unavailable.

## Completion And Release Gates

The initiative cannot use its own new universal reconciliation result as the only authority for
completion. The independent bootstrap closure ledger remains authoritative until all gates pass:

1. contract and bootstrap frozen;
2. generic engine proven;
3. lifecycle integration proven;
4. migration, recovery, efficiency, and cross-platform qualification proven; and
5. published release and disconnected-client canary proven.

Publication may occur only after gates 1 through 4 and their milestones pass. Gate 5 and the final
initiative verdict remain open until the released client demonstrates a new origin-to-product
satisfied loop, current target evidence, upward propagation, rebuild/rollback, and a zero-finding
soak. Fleet rollout and retained-source retirement are separate outcomes.
