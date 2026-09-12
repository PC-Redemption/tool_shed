# 100k Project Executive View

`work/100k.md` is Tool Shed's standard, easy-to-find owner strategic cockpit. It joins one narrowly
authoritative Project Executive Intent with the canonical operational project projection so an
owner returning after time away can understand why the project exists, what done-for-now means,
what changed, what matters, and which next cycles are credible.

The main view shows the North Star, current completion horizon, strategic context, owner priorities,
project landscape, decisions and attention, recommended next cycles, material changes, realized
outcomes, deliberate non-goals, review triggers, and compact accounting integrity. It does not
contain the exhaustive Complete Strategic Ledger. That ledger remains available as an explicit
deterministic drill-down from the exact same projection.

## Authority Boundary

Project Executive Intent owns only owner-authored executive framing:

- North Star;
- Current Completion Horizon;
- Strategic Context;
- Current Priorities;
- Deliberate Non-Goals;
- Decisions Needed; and
- Review Triggers.

Under SQLite authority it is one active managed `decision` document whose metadata role is
`project-executive-intent-v1` and whose preferred path is `work/project-executive-intent.md`. Under
file authority, that exact file declares `Type: decision` and
`Role: project-executive-intent-v1`. The existing managed-document revision or Git history records
changes. Multiple active SQLite intent documents or a malformed file-authority identity fail
closed. Missing or incomplete sections remain visible owner decisions; the renderer never invents
strategy.

Ideas, Project Maps, Program Roadmaps, campaigns, decisions, planning order, relationships,
outcomes, evidence, reconciliation, closure, focus areas, and release cohorts keep their existing
authority. `work/100k.md` remains a deterministic read-only projection. Bare `ts: 100k` never
selects, prioritizes, starts, or completes work. A later explicit owner choice uses the existing
guarded route for the selected source.

## CEO Directives And Subordinate Cycles

`ts: 100k add <directive>` is the explicit write route beside the read-only cockpit;
`ts: directive <directive>` is its concise alias. It preserves the CEO's wording in an existing
Idea Brief marked `Role: project-executive-directive-v1`, opens the normal governed outcome under
Hybrid authority, appends it through canonical Idea planning order, checkpoints the intake, and
stops. This lets the CEO issue several directives before implementation. Reissuing the exact active
directive is the explicit delegation/resume action; it then continues through Roadmap, Milestone,
Campaign, Evidence, and Outcome cycles as the active authority envelope allows.

A new directive issued while a subordinate campaign is working is captured without interrupting
that campaign. An exact-match resume request also waits when a different campaign is working.
Canonical planning order selects what is eligible next, and `ts: order bs move` is the existing
explicit CEO priority control. Priority changes never preempt a working campaign.

The CEO supplies the desired outcome, constraints, priority, and delivery boundary. The subordinate
cycles select internal artifact mechanics. A source-changing directive without delivery language
defaults to a verified Work1 candidate; push, deployment, release, credentials, destructive
recovery, and other authority expansions are never inferred.

100k projects directive state and its current subordinate handoff from existing Idea, relationship,
outcome, reconciliation, and closure authority. Directives do not create another backlog, queue,
table, or lifecycle engine. Bare 100k review and deterministic rendering remain non-mutating.

Connected schema-13 reporters send an active-first bounded structured projection of these same sections to
the hosted project page. The **CEO** tab appears before Overview and shows the newest single-instance
projection without parsing `work/100k.md` or merging independent reporters. Each directive copies
its exact `ts: directive <directive text>` command for the operator to paste into Codex; the browser
cannot execute it. The projection shows canonical planning position, distinguishes queued,
working, and completed state, retains up to 50 directives with all active directives first, and
reports any truncation explicitly. Schema-12 reports remain valid with their original eight-item
directive contract; schema-11 and older reports receive an explicit unavailable state.

```bash
python3 scripts/project_projection.py --workspace . 100k
python3 scripts/project_projection.py --workspace . 100k setup
python3 scripts/project_projection.py --workspace . 100k ledger
python3 scripts/project_projection.py --workspace . render-100k
python3 scripts/project_projection.py --workspace . check-100k
```

The first command renders the concise view without writing. The setup form renders a bounded,
read-only evidence packet and seven-section proposal scaffold. It lists conventional owner
orientation documents and current/recent canonical artifact identities but does not interpret,
accept, or persist strategy. The ledger form renders exhaustive
Idea/Map/PRM/Campaign lifecycle, planning, outcome, reconciliation, closure, parent, and produces
state without writing. `render-100k` atomically refreshes the tracked main view and refuses to
overwrite content that lacks the generated marker. `check-100k` compares exact expected bytes and
fails for missing, stale, manually edited, or truncated accounting. Strict Doctor applies the same
freshness gate. Installation, snapshot update, and Work2 release-cohort registration refresh the
projection at their controlled checkpoints.

## Guided First-Run Setup

When executive intent is missing or incomplete, the main view names `ts: 100k setup` as its next
route. The guided route:

1. runs the deterministic setup projection;
2. inspects the named README/architecture/strategy/vision/goals/roadmap/project sources and the
   relevant canonical artifacts;
3. presents one exact proposal covering all seven executive-intent sections while leaving
   uncertainties visible;
4. asks the owner to accept or revise the proposal; and
5. only after explicit acceptance, persists the proposal through the active authority and refreshes
   `work/100k.md`.

A bare review, installer, or snapshot upgrade never performs step 5. Under file authority, upgrade
discovery recursively recognizes `work/**/*.md` documents with a supported Tool Shed `Type:`. Under
SQLite authority, it reads managed `IDEA`, `MAP`, `PRM`, and `CAMP` documents and their current
operational state. Other project documentation remains evidence, not an implicitly converted
artifact or accepted strategy.

Rendering is deterministic: it contains source timestamps and digests, not the current wall clock.
Under Hybrid authority it reads the active intent decision, database-owned documents, and outcome
state. Under file authority it reads `work/project-executive-intent.md` and the established file
projection while reporting unavailable capabilities honestly. Rendering performs no project-state
mutation beyond replacing its own marked generated output.

## Owner Acceptance

The primary experience test is whether an owner returning after a month can read the main view and
answer, without opening the ledger: why the project exists, what its current horizon is, what
changed, what remains important, which decisions need attention, and what credible next cycles
exist. Machine accounting, deterministic bytes, stale detection, file/SQLite parity, and recovery
remain required but do not substitute for that owner outcome.
