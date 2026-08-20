# Restore trustworthy overview and close out stale evolution-map state

Status: working
Type: campaign
Updated: 2026-08-20
Next Action: execute the campaign completion gate
Campaign ID: restore-trustworthy-overview-and-close-out-stale-evolution-map-state
Campaign Number: 043
Outcome: Make Tool Shed's overview, index-drift reporting, stale-path detection, and active evolution-map state agree with the real tracked workspace after completion-watcher roadmap closeout.
Primary Focus Areas: artifact-workflows
Supporting Focus Areas: campaign-lifecycle, workspace-safety
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: The roadmap-aware overview no longer reports tracked roadmap files as missing; regression tests cover the corrected index-drift comparison; stale planning references in the Tool Shed evolution map are reconciled to existing lifecycle paths and truthful statuses; the map is completed or intentionally deferred based on remaining work; focused tests, the full Tool Shed validator, overview, campaign validation, stale-path checks, strict work-state review, and generated-index verification pass; no fleet snapshot update, App Server promotion, hosted-watcher reactivation, release, deployment, or push occurs.
Completion Evidence: none
Disposition: none

## Request

Restore agreement among Tool Shed's strategic navigation and integrity surfaces after the
completion-watcher roadmap closeout:

- reproduce and fix the `ts: overview` false index-drift report that classifies tracked
  `work/roadmaps/` files as missing even though roadmap discovery intentionally handles them
  separately;
- add focused regression coverage that keeps roadmap lifecycle artifacts visible without making
  existing-project artifact mapping ingest them as ordinary source work;
- inspect why the stale-path checker passes while the active Tool Shed evolution map names missing
  `work/wp/active/` paths, then make the checker and its tests honor the documented planning-path
  contract;
- reconcile `work/maps/map-tool-shed-evolution.md` to existing artifact paths, current lifecycle
  statuses, and the completed completion-watcher program;
- mark that map complete or intentionally deferred according to the remaining evidenced work,
  without reviving the abandoned fleet-update campaign; and
- regenerate deterministic indexes and verify that overview, campaign status, roadmap validation,
  stale-path checking, strict work-state review, focused tests, and the full validator report one
  coherent state.

Keep this campaign local and maintenance-scoped. Do not perform a fleet snapshot update, enable or
promote App Server, reactivate hosted-watcher work, publish a release, deploy, push, create
credentials, or mutate any other workspace.

## Completion Check

The roadmap-aware overview no longer reports tracked roadmap files as missing; regression tests cover the corrected index-drift comparison; stale planning references in the Tool Shed evolution map are reconciled to existing lifecycle paths and truthful statuses; the map is completed or intentionally deferred based on remaining work; focused tests, the full Tool Shed validator, overview, campaign validation, stale-path checks, strict work-state review, and generated-index verification pass; no fleet snapshot update, App Server promotion, hosted-watcher reactivation, release, deployment, or push occurs.
