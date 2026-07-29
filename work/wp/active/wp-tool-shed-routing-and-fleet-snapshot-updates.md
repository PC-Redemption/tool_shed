# Tool Shed routing and fleet snapshot updates Workpackage

Status: active
Type: workpackage
Updated: 2026-07-21
Next Action: obtain explicit approval before the first guarded mass update

Project Map: work/maps/map-tool-shed-evolution.md
Canonical Truth: README.md; docs/fleet-snapshot-updates.md; skills/tool-shed/SKILL.md

## Current Context

Tool Shed is installed into projects as disconnected `tool_shed/` snapshots. The canonical checkout
did not define request-prefix routing or provide a fleet inventory. Linux and Windows Marshal setup
installers generate the global Codex `AGENTS.md` block and therefore must carry the same routing.

The user requested steps 1 through 6 only. The first mass update remains separately approval-gated.

## Recommendation

Define one-request-only `ts:`, `mp:`, and `ws:` routing consistently in Tool Shed and both setup
installers. Inventory instruction drift by hashes without writing. Preserve snapshots as non-Git,
one-way copies. Specify a staged, recoverable updater, but do not apply it during this workpackage.

## Current State

Completed:

- Defined the three request prefixes and their lifetime/precedence rules.
- Reconciled the Windows setup branch with its independent remote fix; verified Linux is clean and
  ahead only by its two local feature commits.
- Added routing to the packaged Tool Shed skill, Tool Shed README, and both setup installers.
- Added installer assertions for all prefixes.
- Added a read-only local/SSH instruction-hash inventory and its tests.
- Documented guarded mass-update requirements and approval boundary.

Incomplete:

- None within plan steps 1 through 6.
- Obtain explicit approval before any fleet update.

## Goal

Codex can route each request to Tool Shed, Marshal, or the current workspace consistently, and an
operator can identify stale Tool Shed instruction snapshots across approved hosts before approving
a guarded mass update.

## Why It Matters

Without consistent routing, plans can land in the wrong system. Without fleet inventory, old Tool
Shed instructions remain silently active across projects and hosts.

## Major Outcomes

- One-request-only routing is installed and tested.
- Setup repository histories are reconciled without discarding local work.
- Fleet inventory is read-only, explicit, and evidence-producing.
- The updater design preserves project boundaries and requires separate apply approval.

## Delivery Stages

Use stages when sequencing, parity gates, or handoff cost matter.

| Stage | Outcome | Entry Evidence | Exit Evidence |
| --- | --- | --- | --- |
| 1 | Prefix contract | User-defined routes | Tool Shed and setup installers agree |
| 2 | Setup reconciliation | Clean local branches | Remote work retained with local features |
| 3 | Inventory | Canonical instruction hashes | Local/SSH report classifies every result |
| 4 | Update design | Reviewed inventory model | Guardrails and approval gate documented |
| 5 | Read-only fleet run | Approved SSH aliases/search roots | Update set and unreachable hosts reported |

## Related Artifacts

- Tickets:
- Checklists:
- Spikes:
- ADRs:
- Runbooks:
- Inventories:
- Decision matrices:

## Rough Sequence

1. Define and test routing.
2. Reconcile setup repositories.
3. Build and validate inventory.
4. Document updater safety contract.
5. Run inventory and review evidence.
6. Stop before apply pending explicit approval.

## Milestones

### Milestone 1: Steps 1–6 complete

Completion criteria:

- [x] Prefix contract defined.
- [x] Setup repositories reconciled.
- [x] Routing implemented in all instruction sources.
- [x] Inventory designed and implemented.
- [x] Guarded updater designed and safety constraints documented.
- [x] Read-only fleet inventory run and reviewed.

## Open Questions

- Which unreachable or duplicate SSH aliases should be removed from the approved fleet?
- Should the first apply update every stale snapshot or a canary subset?

## Completion Standard

Steps 1 through 6 are complete when tests pass and the read-only fleet report identifies current,
stale, incomplete, checkout, and unreachable results without modifying any snapshot. The broader
fleet-update work remains incomplete until the separately approved apply and verification finish.

## Closeout Routing

- Current truth promoted to: README.md; docs/fleet-snapshot-updates.md; skills/tool-shed/SKILL.md
- Historical context remains in: this workpackage after completion
- Runtime/status evidence: read-only fleet inventory output
- Cleanup deferred to: approval-gated mass update and optional periodic drift checks
