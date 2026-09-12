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

```bash
python3 scripts/project_projection.py --workspace . 100k
python3 scripts/project_projection.py --workspace . 100k ledger
python3 scripts/project_projection.py --workspace . render-100k
python3 scripts/project_projection.py --workspace . check-100k
```

The first command renders the concise view without writing. The ledger form renders exhaustive
Idea/Map/PRM/Campaign lifecycle, planning, outcome, reconciliation, closure, parent, and produces
state without writing. `render-100k` atomically refreshes the tracked main view and refuses to
overwrite content that lacks the generated marker. `check-100k` compares exact expected bytes and
fails for missing, stale, manually edited, or truncated accounting. Strict Doctor applies the same
freshness gate. Installation, snapshot update, and Work2 release-cohort registration refresh the
projection at their controlled checkpoints.

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
