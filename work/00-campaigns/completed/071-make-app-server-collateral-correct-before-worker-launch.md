# Make App Server collateral correct before worker launch

Status: complete
Type: campaign
Updated: 2026-08-26
Next Action: none
Campaign ID: make-app-server-collateral-correct-before-worker-launch
Campaign Number: 071
Outcome: Move collateral correctness ahead of worker launch while preserving one-command execution and the existing bounded CAMP runner.
Primary Focus Areas: provider-portability
Supporting Focus Areas: campaign-lifecycle, workspace-safety
Depends On: requalify-realistic-low-token-owner-loop
Decision: none
Detour For: none
Return To: none
Completion Gate: G10-PRELAUNCH-COLLATERAL-SAFE passes with focused contract, freshness, feasibility, repair-or-reduction, persistence, and dispatcher evidence.
Completion Evidence: G10 passed: first-pass contract, source binding, prelaunch feasibility, queued stale regeneration, working no-replay, and 20 focused tests; see work/evidence/evidence-app-server-first-pass-prelaunch-collateral.md
Completion Date: 2026-08-26
Completion Order: 65
Disposition: completed
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 3
Milestone: M10-FIRST-PASS-PREPARATION
Unlocks Gate: G10-PRELAUNCH-COLLATERAL-SAFE

## Request

Using normal GUI execution, add a compact App Server preparation contract to campaign creation and roadmap materialization so stable semantic intent is available before dispatch without requiring exact paths too early. At ts: next --app-server, resolve exact paths, context, executables, deterministic verification, and budgets against current campaign and source state. Bind persisted automatic capsules to that state; regenerate stale capsules. Before persistence or worker launch, deterministically reject or repair unavailable executables, protected or broad paths, excessive context, likely oversized verification output, insufficient turn budget, and non-atomic work; reduce work to one bounded executable slice when safe. Never replay after mutation and retain the existing CAMP runner and safety controls. Run focused changed-path tests plus one dispatcher smoke for unsafe and valid preparation. Do not publish, synchronize installed skills, upgrade Core, run the full validator, or deploy anything.

## Completion Check

G10-PRELAUNCH-COLLATERAL-SAFE passes with focused contract, freshness, feasibility, repair-or-reduction, persistence, and dispatcher evidence.
