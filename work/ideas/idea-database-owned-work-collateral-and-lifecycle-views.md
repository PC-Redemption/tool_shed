# Idea Brief: Database-Owned Work Collateral and Lifecycle Views

Status: exploring
Type: idea-brief
Updated: 2026-08-28
Next Action: continue brainstorming or promote this brief with `ts: prm idea <idea-id-or-path>`
Produces:

## Current Synthesis

### Idea

Move Tool Shed-generated work collateral from path-bound Markdown files into the existing embedded
SQLite authority. Idea Briefs, project maps, Program Roadmaps and revisions, campaigns and queues,
tickets, checklists, spikes, ADRs, decisions, inventories, runbooks, workpackages, lifecycle state,
relationships, revisions, and generated projections should become database-owned records with
immutable visible IDs.

The filesystem should stop being the canonical storage layout for generated work. Instead, it
should expose disposable, lifecycle-organized views such as active, completed, parked, deferred,
abandoned, and superseded. Those views exist so an operator can understand the project directly in
the VS Code tree and so Codex can receive file-shaped bounded context. Moving an artifact between
lifecycle views must not change its identity, invalidate relationships, or require mass edits.

This is a follow-on to the completed Hybrid SQLite foundation. The earlier design deliberately kept
files as the primary interface for much collateral; sustained use has shown that this boundary
still leaves the operator with a noisy tree, intermingled current and historical work, path-coupled
links, and excessive agent orientation. This idea intentionally moves the authority boundary
farther into SQLite rather than stopping after generating better views over file-owned documents.

### Why It Matters

The current `work/` tree cannot answer basic operator questions without opening files or consulting
separate indexes. Active, completed, promoted, parked, and superseded artifacts appear together;
multiple roadmap revisions sort by descriptive filenames; and current work is visually buried in
historical collateral. Adding lifecycle folders would improve the view but physically moving
canonical Markdown would break inbound links or cause a large automatic rewrite diff.

The same file-first layout costs Codex context and precision. It must discover, parse, and filter
many unrelated documents before acting, while relationships are duplicated as path strings and
historical revisions compete with current truth. These costs recur and grow with every Tool Shed
cycle.

The existing Hybrid database already provides stable identities, guarded transactions,
relationships, revisions, reconciliation, checkpointing, unmanaged-write detection, and recovery.
Using it as the document authority extends machinery that has already been implemented and
qualified instead of adding a separate server database.

### Desired Outcome

All Tool Shed-generated work documents are addressed by immutable human-visible IDs and stored as
versioned SQLite documents. Lifecycle, outcome, reconciliation, relationships, body content, and
history can change without changing identity or creating path-maintenance commits.

The operator sees a concise generated tree organized by lifecycle, with active work immediately
visible and completed or superseded history collapsible. Codex can list, search, show, traverse,
edit, compare, and history-query one artifact through deterministic commands that return compact
Markdown or JSON. For editing, Tool Shed presents a temporary file-shaped projection, validates an
exact patch against the artifact ID and database revision, and applies it transactionally.

Imported owner files, source code, tests, canonical product documentation, provider instructions,
selected external evidence, compact Codex-efficient context, and portable recovery/checkpoint
artifacts remain files under an explicit authority contract. The live database remains untracked;
snapshot tooling creates deterministic, reviewable Git artifacts only at governed checkpoints.
Production installs work without GitHub or a database server and can rebuild exact state from
portable tracked checkpoints.

## Constraints And Non-Goals

- Use the existing embedded SQLite substrate; do not introduce MongoDB, another database server,
  authentication service, background daemon, or hosted dependency.
- The completed Hybrid and Universal Closed-Loop contracts remain the starting foundation. This
  idea extends their authority boundary and must preserve their qualified behavior.
- Generated lifecycle views are projections, not canonical documents and not an acceptable final
  authority boundary.
- Codex must not need direct SQL or schema knowledge for ordinary reads or writes. Deterministic
  file-like commands are a non-negotiable product interface.
- Preserve plain Markdown and JSON rendering for operator inspection, provider portability,
  debugging, export, and recovery.
- Preserve all existing bytes, identities where assigned, relationships, status, history, owner
  notes, evidence references, and development changes through conversion.
- Do not delete original file-owned collateral until exact import, rendering, semantic parity,
  backup, rollback, rebuild, and upgrade qualification have passed and the retention gate permits
  retirement.
- Do not make GitHub a production-install requirement. Git integration is optional durability and
  collaboration, not runtime authority.
- Avoid checkpoint or snapshot commits on every database access. Snapshot policy must distinguish
  reads, routine managed writes, meaningful checkpoints, releases, and recovery boundaries.
- Source code, canonical product documentation, imported owner material, large/raw evidence, and
  provider instruction files are not moved merely to make storage uniform.

## Possibilities And Tradeoffs

| Possibility | Benefits | Costs / Risks | Evidence / Status |
| --- | --- | --- | --- |
| SQLite owns all Tool Shed-generated work collateral | Removes path identity, enables exact lifecycle queries, compact Codex context, transactions, and history | Requires document editing, rendering, migration, checkpoint, and upgrade tooling | Owner-selected direction |
| Generate lifecycle views while files remain canonical | Improves the visible tree quickly | Retains path coupling, broad scans, duplicated state, and link-maintenance pressure | Useful migration aid; rejected as the final state |
| Automatically rewrite every Markdown link after moves | Preserves clickable path links | Still produces maintenance storms and broad commits; historical paths remain fragile | Compatibility tool only, not the operating model |
| Add MongoDB or another document server | Native document terminology and rich queries | Adds installation, service, credentials, backup, upgrade, and disconnected-use burdens | Rejected; SQLite is sufficient |
| Store everything including source and canonical docs in SQLite | Uniform storage | Damages normal coding, Git review, interoperability, and owner editing | Rejected |
| Temporary Markdown editing projections | Preserves Codex patch workflow and human-readable review | Requires strict import, revision fencing, cleanup, and conflict handling | Recommended interface |
| Generated lifecycle tree organized by status | Active work is immediately visible and history is collapsible | Views must never become a second authority or durable link target | Required operator interface |
| Stable IDs in database and every rendered title | Relationships and history survive title, status, and view changes | Requires numbering, import, and collision policy | Required |

## Open Questions

- Which exact file classes are Tool Shed-generated and therefore mandatory database candidates,
  and which evidence or operator-authored variants remain file-owned?
- What visible ID namespaces and numbering rules should apply to ideas, maps, roadmaps, campaigns,
  tickets, workpackages, decisions, evidence, and direct-work capsules?
- Should lifecycle views be ignored Markdown pointer files, symlinks where supported, a generated
  directory tree, or a combination with a single portable default?
- What commands provide the minimum complete Codex/operator interface: list, show, search, context,
  related, history, edit/export, apply/import, diff, and render?
- How should temporary Markdown editing projections represent structured fields and body content
  without losing comments, ordering, or owner formatting?
- What snapshot representation produces useful Git review without a monolithic checkpoint diff or
  commit on every managed write?
- How should full-text search, historical `--as-of` queries, and bounded context budgets work across
  database-owned documents and retained file-owned truth?
- What exact conversion sequence proves byte retention, semantic parity, stable relationships,
  interruption recovery, rollback, and deterministic rebuild before file retirement?
- How will the canonical maintainer perform the first upgrade when its existing special
  install/update path differs from normal production installations?
- How will an older Tool Shed refuse or safely hand off a database/checkpoint created by this newer
  document-authority schema?

## Decisions

- Proceed toward SQLite authority for Tool Shed-generated work documents; do not stop at generated
  lifecycle views over file-owned collateral.
- Use the existing embedded Hybrid SQLite substrate rather than MongoDB or another server.
- Separate canonical storage from operator presentation: database records are authoritative and
  lifecycle-organized files are generated views.
- Use immutable visible artifact IDs so title, lifecycle, and view changes do not change identity.
- Keep source, canonical product docs, imported owner files, selected evidence/recovery artifacts,
  and deliberately Codex-efficient files outside the database under an explicit authority contract.
- Preserve Codex's file-patch strengths through deterministic temporary Markdown projections and
  guarded revision-bound import.
- Convert incrementally and reversibly, but treat full generated-collateral conversion—not the view
  layer—as the intended endpoint.

## Don't Forget

- The operator must be able to look at the tree and immediately distinguish active work from
  completed, parked, abandoned, deferred, and superseded history.
- A generated view path must never become artifact identity or a durable relationship target.
- A database transaction proves storage consistency, not outcome correctness; closed-loop product
  truth, evidence, verdict, residual work, and propagation still apply.
- Direct SQL must remain detectable and recoverable, while normal Codex work uses managed tools.
- The live database is not tracked. Governed snapshots and portable checkpoints provide Git
  durability without commit spam.
- Production installations may have neither GitHub nor an initialized Git repository.
- Conversion must retain every original file until no-loss, rollback, upgrade, and rebuild gates
  pass; cleanup is a separate authorized retention decision.
- The database should reduce context, not hide necessary context. Codex must be able to expand from
  a bounded capsule to related records intentionally.

## Exploration Log

### 2026-08-28

- Idea Brief created from the operator's observation that the current `work/` tree is visually
  dominated by unordered current and historical collateral.
- Discussion distinguished two problems: lifecycle organization makes the tree understandable,
  while stable database identities eliminate link-maintenance storms caused by physical moves.
- Generated lifecycle views were considered as an initial relief mechanism, then explicitly
  rejected as a deliberate stopping point. The owner directed that Tool Shed-generated documents
  move to database authority.
- MongoDB-style document storage was considered. The direction is to use SQLite as an embedded
  document store because the Hybrid foundation already supplies identities, relationships,
  transactions, checkpoints, and recovery without adding a server.
- Codex impact was made an acceptance boundary: compact queries should reduce orientation tokens,
  but deterministic Markdown/JSON rendering and temporary patchable projections must preserve its
  normal read, edit, diff, and verification workflow.

Keep the synthesis current and append only useful dated exploration notes. Use `Status: ready-for-prm`
when the owner chooses to promote it, `promoted` after approved project-map direction captures it,
or `parked` when it is intentionally set aside. A promoted brief names its output in `Produces:`.
