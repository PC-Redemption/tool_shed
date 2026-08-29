# Harden campaign-number convergence during snapshot upgrades

Status: complete
Type: campaign
Updated: 2026-08-18
Next Action: none
Campaign ID: harden-upgrade-campaign-number-convergence
Campaign Number: 025
Outcome: Resolve GitHub issue #35 by making protocol-3 upgrades accept valid v0.20 empty campaign queues, converge inbound owner-artifact references when campaign files gain numbers, and preserve exact snapshot plus owner-work rollback across failures or interruption.
Primary Focus Areas: snapshot-delivery
Supporting Focus Areas: campaign-lifecycle, qualification-release
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: A representative v0.20-to-current upgrade with zero active campaigns completes in one transaction; numbered campaign renames update every deterministic inbound work-artifact path without altering unrelated owner content; injected failures after each convergence stage restore the exact pre-upgrade snapshot and declared owner-work mutation surface; compact transaction diagnostics identify the failed stage; focused upgrade tests and the full Tool Shed validator pass; and GitHub issue #35 is updated with verified evidence.
Completion Evidence: Implemented legacy empty-queue acceptance, read-only campaign backfill planning, exact inbound Parent/Markdown-link convergence, dynamically scoped verified backups, and transaction-stage diagnostics; 6 focused updater tests passed; full validate_tool_shed.py qualification passed 146 tests plus manifest, provider, index, stale-path, work-state, roadmap, and disposable-workspace checks; GitHub issue #35 updated at https://github.com/PC-Redemption/tool_shed/issues/35#issuecomment-5328178527. Historical claim audit: work/evidence/evidence-historical-campaign-external-claims-backfill.md
Completion Date: 2026-08-18
Completion Order: 23
Disposition: completed

## Request

Address [GitHub issue #35](https://github.com/PC-Redemption/tool_shed/issues/35), which was
reproduced on Windows while upgrading a released v0.20.0 snapshot to v0.21.0 with updater protocol
3. Rollback worked, but two compatibility defects forced retries:

- the legacy validator rejected the valid v0.20 empty-queue projection because it lacked the newer
  queue-position guidance line;
- `backfill-numbers` renamed completed campaign files without converging inbound `Parent:` paths in
  other owner artifacts, so post-install stale-path validation failed.

Fix both defects transactionally. Preserve unknown owner content, include every changed owner path
in the declared mutation and rollback surface, and retain compact stage-level diagnostics so a
failed or interrupted upgrade can be understood without raw logs. Extend protocol-3 integration
coverage for empty active queues, inbound references to completed campaigns, successful one-pass
convergence, and rollback after each post-install failure point.

## Completion Check

A representative v0.20-to-current upgrade with zero active campaigns completes in one transaction; numbered campaign renames update every deterministic inbound work-artifact path without altering unrelated owner content; injected failures after each convergence stage restore the exact pre-upgrade snapshot and declared owner-work mutation surface; compact transaction diagnostics identify the failed stage; focused upgrade tests and the full Tool Shed validator pass; and GitHub issue #35 is updated with verified evidence.
