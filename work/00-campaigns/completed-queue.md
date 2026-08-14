# Completed Campaign Queue

Updated: 2026-08-14

Newest completion first.

- 2026-08-14 — [Converge upgrades to current work structure](completed/converge-upgrades-to-current-work-structure.md) — Make Tool Shed upgrades from older releases migrate preserved owner work into the complete latest canonical work tree instead of leaving a hybrid installation — evidence: GitHub #25; commit 2450401; protocol-3 Windows-path convergence and rollback tests; full validator 102/102
- 2026-08-14 — [Reconcile campaign queue state and execution order](completed/reconcile-campaign-queue-state-and-order.md) — Provide a deterministic utility that finds orphaned or stalled campaigns, safely repairs mechanically resolvable queue drift, and evaluates the active queue execution order without overriding owner decisions — evidence: GitHub #23; commit 2450401; dry-run, stale-token, projection-repair, rollback, and order tests; full validator 102/102
- 2026-08-14 — [Restore blocked campaign lifecycle](completed/restore-blocked-campaign-lifecycle.md) — Provide a deterministic supported transition that returns blocked campaigns to schedulable execution without weakening start invariants — evidence: GitHub #24; commit 2450401; unblock and same-day lifecycle tests; full validator 102/102; installed skill exact with backup tool-shed.backup-20260814T151412Z
- 2026-08-14 — [Owner-facing campaign queues](completed/owner-facing-campaign-queues.md) — Deliver the approved first-sorted durable campaign lifecycle and synchronize the installed Codex skill — evidence: commit 5c1f402; repository validator 97/97; installed skill exact diff; backup tool-shed.backup-20260814T124356Z
