# Active Campaign Queue

Updated: 2026-08-14

## Owner State

- Last completed: owner-facing-campaign-queues — Owner-facing campaign queues
- Working now: restore-blocked-campaign-lifecycle — Restore blocked campaign lifecycle
- Next: reconcile-campaign-queue-state-and-order — Reconcile campaign queue state and execution order
- Blocker or decision needed: none
- Detour and return point: none

## Ordered Queue

1. [Restore blocked campaign lifecycle](active/restore-blocked-campaign-lifecycle.md) — state: working — outcome: Provide a deterministic supported transition that returns blocked campaigns to schedulable execution without weakening start invariants
2. [Reconcile campaign queue state and execution order](active/reconcile-campaign-queue-state-and-order.md) — state: queued — outcome: Provide a deterministic utility that finds orphaned or stalled campaigns, safely repairs mechanically resolvable queue drift, and evaluates the active queue execution order without overriding owner decisions
3. [Converge upgrades to current work structure](active/converge-upgrades-to-current-work-structure.md) — state: queued — outcome: Make Tool Shed upgrades from older releases migrate preserved owner work into the complete latest canonical work tree instead of leaving a hybrid installation
