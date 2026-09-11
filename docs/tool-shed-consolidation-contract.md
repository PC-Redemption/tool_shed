# Tool Shed Consolidation Contract

Status: active
Owner: IDEA-0027 / PRM-0047
Baseline commit: `6db6d52b01ae6d242aa90c7d99fa83c7a47acab0`
Baseline date: 2026-09-11

## Purpose

Tool Shed should grow by strengthening a small number of product capabilities, not by adding a new
command, state interpretation, or presentation model for every request. This contract makes the
retained capabilities and their ownership explicit, defines how reduction is measured, and sets the
boundary that IDEA-0028 must honor when it adds the 100k executive view.

## Measured Baseline

The baseline has 86 top-level Python files in `scripts/`, 57,154 physical Python lines in those
files, and 26,700 physical lines in top-level `tests/test_*.py` files. Physical lines are a warning
signal, not the architecture target: narrow guarded entry points can be safer than one large
dispatcher. Every consolidation candidate must also report:

- number of independent implementations of the changed product interpretation;
- size of the largest affected responsibility owner;
- runtime-code and test-code deltas;
- measured latency or repeated reads for the affected operator path;
- compatibility shims added, retained, and removed.

The first Work2 slice moves 351 lines out of `dashboard_reporter.py` into the canonical projection
owner and removes repeated audited document reads plus an N+1 closure-blocker query. Its pre-manifest
working-tree measurement is 87 script files and 57,239 script lines: an explicit +85-line foundation
debt, not a claimed line-count reduction. The debt must be reclaimed or explicitly superseded by a
larger measured removal before IDEA-0028 starts implementation. On the current 291-artifact
workspace, complete projection construction improved from approximately 18.0 seconds to 4.7 seconds.

## Capability Disposition

| Capability family | Canonical owner or boundary | Disposition | Consolidation direction |
| --- | --- | --- | --- |
| Project identity and workspace safety | `project_identity.py`, `workspace_preflight.py`, repository policy | Keep | One identity capsule and fail-closed boundary used by all mutations |
| Authority selection | `authority_resolver.py` | Keep | No command-local database/file heuristics |
| Authoritative document storage | `document_store.py`, schema module | Keep | SQLite/file behavior remains behind the authority contract |
| Artifact authoring and conversion | `new_artifact.py`, conversion and onboarding tools | Merge | Reuse document-store operations; do not add parallel writers |
| Planning readiness and order | `idea_readiness.py`, `planning_order.py` | Keep | One semantic review and one local-order projection |
| Program and campaign lifecycle | program-roadmap and campaign modules | Merge | Converge shared cycle selection and state projection; retain guarded transitions |
| Outcome and recursive closure | outcome, reconciliation, and closure-lineage modules | Keep | One lineage/evidence model; schema helpers remain implementation details |
| Loop findings | `loop_findings.py` | Keep | Findings feed operator projections; they do not become a second task tracker |
| Project-world read model | `project_projection.py` | Replace | Replaces dashboard-local summary and inventory interpretation; future readers consume it |
| Dashboard transport and scheduling | `dashboard_reporter.py` | Move | Reporter owns transport/outbox only; project interpretation belongs to the projection |
| Hosted dashboard presentation | `dashboard/` | Keep | Consumes bounded reports; never becomes local lifecycle authority |
| Codex execution and orchestration | app-server, execution, and orchestration modules | Merge | Share resolution, policy, telemetry, and fallback contracts across roles |
| Provider portability | provider adapters and checks | Keep | Provider differences stay behind declared capabilities |
| Work endpoints and validation | work-level, work-orchestration, validation policy | Merge | One endpoint plan and one evidence vocabulary |
| Install, update, and convergence | snapshot, installer, convergence, Doctor | Merge | One release capability plan composed from guarded domain operations |
| Qualification | lifecycle and platform qualification modules | Move | Scenario/evidence helpers are maintainer tooling, not product state APIs |
| Release cohort and delivery | release cohort/projection/preparation | Keep | Exact commit and owning-chain registration remain separate from publication |
| Historical one-off migration utilities | freeze/migrate/maintainer scripts | Retire | Remove only after release/usage evidence proves no supported recovery depends on them |

`Keep` means one justified owner remains. `Merge` means multiple current modules may remain while
their duplicated interpretation is moved behind one contract. `Move` separates runtime behavior
from integration or maintainer tooling. `Replace` identifies an active strangler seam. `Retire`
requires evidence and a separately reviewed removal; it is never inferred from filename age.

## Target Layers

1. **Kernel:** identity, authority, authoritative state, relationships, outcomes, closure, and
   guarded mutations.
2. **Project projection:** one read-only, bounded, privacy-safe view of the entire project world.
3. **Workflow policy:** readiness, planning order, campaign selection, work endpoints, and release
   gates consume kernel state and the projection.
4. **Integrations:** dashboard transport, Codex execution, providers, schedulers, and hosted UI do
   not reinterpret project truth.
5. **Maintainer delivery:** conversion, qualification, installer, release, and migration utilities
   remain outside routine operator workflows.

Dependencies point downward. A presentation or integration may request a guarded operation, but it
cannot own identity, authority, lifecycle, outcome, or closure truth.

## Change Budget

For every net-new feature or major extension:

1. Name the existing capability family and canonical owner.
2. State which surface is consumed, merged, replaced, or retired.
3. Report runtime and test deltas against this baseline and the latest accepted candidate.
4. Reject a parallel state model, second authority, second lifecycle, or second project-world
   projection.
5. Require parity tests before deleting a compatibility path.
6. Keep a compatibility shim only when it delegates without interpretation; name its retirement
   condition.
7. If runtime code grows, record the debt and the concrete later removal that repays it. Hidden
   growth or calling moved lines a reduction fails the gate.

## Protected Invariants

Consolidation must preserve project identity, authority selection, immutable artifact identity,
managed-write accounting, stale-token refusal, lifecycle transitions, planning order, typed
relationships, outcome verdicts, reconciliation, recursive closure, bounded evidence, checkpoint
and rebuild parity, rollback, privacy, provider portability, and Linux/Windows behavior. A reduction
that weakens one of these is not a simplification.

## Canonical Project Projection

`project_projection.build(workspace)` resolves authority once and returns one envelope containing:

- the authority state and bounded feature limits;
- `state`, the concise executive counts used by the dashboard;
- `work_inventory`, the exhaustive bounded lifecycle ledger used for navigation, events, closure,
  planning, and release-chain presentation.

The projection is read-only. It does not choose work, mutate lifecycle, manufacture outcomes, or
store presentation state. `dashboard_reporter.py` retains private compatibility wrappers, but they
delegate without interpretation. Normal report construction builds the projection once and reuses
both layers.

## 100k Handoff

IDEA-0028 remains downstream of IDEA-0027. Its implementation must consume the canonical project
projection and must absorb or replace operator overlap in these surfaces:

- dashboard executive counts and lifecycle navigation;
- Program Roadmap overview/cycle-state summaries;
- campaign queue status and next-action presentation;
- Idea and Program Roadmap planning-order views;
- active loop findings and unresolved closure blockers.

100k may add synthesis, direction, completion horizon, and operator decisions. It may not add a
second artifact ledger, lifecycle model, queue, authority resolver, or hidden source of project
truth. Existing machine APIs can remain for automation, but duplicate operator-facing summaries
must either become projections of 100k or have an explicit retirement plan.

## Checkpoint Checklist

- [x] Baseline script count and physical runtime/test lines recorded.
- [x] Capability families classified as keep, merge, move, replace, or retire.
- [x] Runtime, integration, and maintainer-delivery layers separated.
- [x] Protected invariants named.
- [x] One canonical project-projection contract implemented.
- [x] Dashboard summary and ledger routed through that contract.
- [x] Repeated audited reads and closure-blocker N+1 query removed from the operator path.
- [ ] Exact local, web-development, Linux-development, and Windows-development evidence attached.
- [ ] Exact candidate registered in the release cohort and Hybrid state checkpointed.
- [ ] The +85-line foundation debt reclaimed or explicitly superseded before IDEA-0028 coding.
- [x] 100k consumption and replacement boundary recorded.
