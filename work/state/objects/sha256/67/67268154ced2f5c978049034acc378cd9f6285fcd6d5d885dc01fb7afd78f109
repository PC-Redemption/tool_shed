# Owner-facing campaign queues and lifecycle management Workpackage

Status: complete
Type: workpackage
Updated: 2026-08-14
Next Action: none
Project Map: work/maps/map-tool-shed-evolution.md
Issue: https://github.com/PC-Redemption/tool_shed/issues/22

## Current Context

Tool Shed stores durable planning artifacts under `work/`, while `work/q&a/ask.txt` is a transient,
ignored operator inbox. The inbox is sometimes used as an ordered campaign list because Tool Shed
does not yet provide a compact owner-facing view of finished, current, next, blocked, deferred, or
abandoned work.

The original feature request proposed placing campaign state below `work/q&a/`. The owner instead
approved a first-sorted top-level folder named `work/00-campaigns/`. `ask.txt` remains at
`work/q&a/ask.txt`; accepting an inbox request may create a durable campaign, but lifecycle state
does not live in the inbox.

## Recommendation

Add a provider-neutral, file-based campaign lifecycle with:

- `work/00-campaigns/active-queue.md` as the canonical ordered execution view;
- `work/00-campaigns/completed-queue.md` as newest-first completion history;
- `active/`, `completed/`, `deferred/`, and `abandoned/` request folders;
- a deterministic helper for add, reorder, start, block, defer, abandon, complete, validate,
  status, and preview-only legacy migration;
- explicit stale-write protection for every mutation;
- routing and operator documentation for the owner-facing commands; and
- installer and index support that preserves existing project work and inbox contents.

Do not create a server, database, hosted tracker, cross-workspace portfolio, or automatic
multi-campaign executor. Do not silently reorder campaigns or migrate inbox contents.

## Current State

Completed:

- Issue #22 records the feature request and acceptance criteria.
- The owner approved `work/00-campaigns/` as the lifecycle root.
- The owner confirmed `work/q&a/ask.txt` remains the transient inbox.

Incomplete:

- None.

## Goal

Give owners a stable, first-sorted campaign control surface that separates concise execution order
from detailed requests and preserves evidence-backed lifecycle history.

## Why It Matters

Detailed work artifacts remain useful to agents but do not provide a fast owner re-entry view.
Without a separate lifecycle model, the transient inbox becomes an accidental queue and campaign
closure, detours, dependencies, and priority changes become fragile manual state.

## Major Outcomes

- Owners can read last completed, working now, next, blockers, and detour/return state quickly.
- Every active request appears exactly once in the active queue.
- Terminal requests move atomically to the correct lifecycle folder.
- New ideas are checked for duplicate IDs, dependencies, conflicts, and stale concurrent edits.
- Existing workspaces receive missing campaign scaffolding without overwriting project state.
- Legacy inbox or linked-request migration is preview-only until explicitly applied by an operator.

## Delivery Stages

| Stage | Outcome | Entry Evidence | Exit Evidence |
| --- | --- | --- | --- |
| 1 | Contract and plan | approved folder and inbox boundary | workpackage and documented file/schema contract |
| 2 | Deterministic lifecycle | existing artifact/index helpers | helper operations preserve queue/folder invariants |
| 3 | Portable integration | lifecycle helper passes focused tests | installer, index, validation, and provider routes agree |
| 4 | Work2 checkpoint | focused repository verification passes | committed source plus host-local installed-skill parity |

## Related Artifacts

- Project map: `work/maps/map-tool-shed-evolution.md`
- GitHub issue: `https://github.com/PC-Redemption/tool_shed/issues/22`
- Inbox contract: `work/q&a/ask.txt`

## Rough Sequence

1. Define campaign request and queue formats with recoverable mutation semantics.
2. Implement scaffolding and deterministic lifecycle operations.
3. Integrate routing, installation, indexing, stale-path checks, and validation.
4. Test normal progression, blocking, detours, reordering, duplication, terminal transitions,
   migration preview, and stale writes.
5. Validate, complete this workpackage, commit the scoped changes, and synchronize the installed
   Codex skill as the configured host-local work environment.

## Milestones

### Milestone 1: File and command contract

Completion criteria:

- [x] Templates and conventions define `work/00-campaigns/` and its lifecycle folders.
- [x] `ask.txt` remains a separate transient inbox.
- [x] Provider-neutral routes define queue, status, next, add, defer, abandon, and completed reads.

### Milestone 2: Lifecycle implementation

Completion criteria:

- [x] A deterministic helper can create, reorder, start, block, defer, abandon, complete, and
      validate campaigns.
- [x] Mutations are recoverable and reject stale expected-state tokens.
- [x] Completion gates must be explicitly satisfied before a request can complete.
- [x] Dependencies are present, acyclic, and compatible with queue readiness.

### Milestone 3: Migration and integration

Completion criteria:

- [x] Installer updates add missing scaffolding without replacing queues, requests, or inbox data.
- [x] Indexing recognizes campaign request folders without treating queue summaries as artifacts.
- [x] Migration from prior `work/q&a/` request layouts or queued inbox content is previewable and
      never applies without explicit approval.
- [x] Documentation provides a compact owner-oriented example.

### Milestone 4: Verification and work2 deployment

Completion criteria:

- [x] Focused lifecycle and integration tests pass.
- [x] Repository validation passes in proportion to the changed shared machinery.
- [x] Requested changes are committed locally without unrelated work.
- [x] Canonical `skills/tool-shed/` is validated, backed up, synchronized to the installed client,
      revalidated, and exactly matches the source.

## Open Questions

- None blocking. The first implementation will use explicit campaign IDs and file hashes as stale
  mutation tokens, and will keep all migration apply behavior out of scope until a separate exact
  approved manifest exists.

## Completion Standard

This workpackage is complete when the approved first-sorted campaign lifecycle works through its
documented helper, its invariants and migration preview are tested, Tool Shed installation and
routing expose it without altering `ask.txt`, focused repository validation passes, the scoped
changes are committed, and the installed Codex skill exactly matches the canonical source.

## Closeout Routing

- Current truth promoted to: `README.md`, `conventions.md`, and `docs/operator-guide.md`
- Historical context remains in: this completed workpackage and GitHub Issue #22
- Runtime/status evidence: focused test output and installed-skill exact-diff verification
- Cleanup deferred to: any future cross-workspace portfolio aggregation
