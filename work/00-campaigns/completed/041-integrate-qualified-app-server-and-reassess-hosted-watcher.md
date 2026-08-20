# Integrate qualified App Server work and reassess Campaign 039

Status: complete
Type: campaign
Updated: 2026-08-20
Next Action: none
Campaign ID: integrate-qualified-app-server-and-reassess-hosted-watcher
Campaign Number: 041
Outcome: Reconcile the qualified App Server branch lineage into a clean, merge-ready Tool Shed integration branch while preserving default-off GUI behavior and all safety boundaries, then produce an evidence-backed disposition recommendation for deferred Campaign 039 without silently changing its lifecycle.
Primary Focus Areas: provider-portability
Supporting Focus Areas: workspace-safety, qualification-release, campaign-lifecycle
Depends On: app-server-camp-token-optimization
Decision: none
Detour For: none
Return To: none
Completion Gate: A documented clean integration base and minimal nonduplicated commit set preserve qualified App Server infrastructure, centralized Sol/Terra routing, default-off GUI fallback, compatibility tooling, write safety, and Campaign 040 optimization; full Tool Shed, App Server, GUI-fallback, compatibility, write-safety, and representative CAMP validation passes without disturbing unrelated dirty work; Campaign 039 is reassessed against the integrated architecture with a clear unchanged, revised, reduced, superseded, or obsolete recommendation; merge readiness, known blockers, conflicts, and the next Tool Shed action are documented; nothing is pushed, released, deployed, or globally enabled.
Completion Evidence: Reconciliation branch codex/tool-shed-app-server-reconciliation at commit 93795a4; durable evidence work/evidence/evidence-app-server-integration-and-watcher-reassessment.md in /home/jon/docker/tool_shed-app-server-reconciliation; main base 8966a2e and integrated source tip 9f72e2c; 23 focused and 180 full tests passed; manifest, provider, campaign, roadmap, index, stale-path, strict work-state, reconciliation, disposable install, live compatibility, write-safety, GUI-fallback, ChatGPT-only/no-API-fallback, and trigger-neutral representative CAMP checks passed; App Server remains default-off and qualified-with-blockers; representative rerun 55,665 input, 2 turns, 1 tool, 22 tests, safe journal; Campaign 039 remains deferred and unmodified with reduce-scope recommendation; candidate locally review-ready but dirty main must be preserved/checkpointed before merge; nothing pushed, released, deployed, or enabled.
Completion Date: 2026-08-20
Completion Order: 37
Disposition: completed

## Request

Integrate the qualified App Server work into the normal Tool Shed codebase without changing current
production behavior, then reassess deferred Campaign 039 against the resulting architecture. This
is a reconciliation, integration-validation, and architecture-reassessment campaign. Campaign 040
already demonstrated meaningful execution savings; do not begin another App Server optimization
campaign.

### Proven results to preserve

The qualified routing remains:

```text
planning       -> Sol / high
verification   -> Terra / low
camp_execution -> Terra / medium
```

Campaign 040 reduced the representative CAMP from 241,524 to 61,516 input tokens (74.53%), seven
to two model turns (71.43%), six to one model tools (83.33%), 36.704 to 12.458 seconds (66.06%),
and 67,362.0 to 36,468.4 weighted-usage units (45.86%). Only the declared target changed, 22
focused tests passed, the Git journal was safe, and no retry followed mutation. Additional samples
confirmed the two-turn pattern and compact verification behavior.

Qualified work currently exists across these clean isolated branches:

```text
codex/tool-shed-app-server-integration
codex/tool-shed-app-server-write-qualification
codex/tool-shed-app-server-camp-token-optimization
```

Relevant history includes integration commits `46f412a`, `6d9c275`, `c66a5f1`, `f04d855`,
`c7c3d87`, `8841335`, and `edff851`; write-qualification commits `8b12c6a` and `69a27d8`; and
optimization commits `22082bb`, `6f6c817`, `ce0b05c`, and `9f72e2c`. Do not blindly cherry-pick
this list. Inspect ancestry and actual diffs first because later branches may already contain
earlier work.

### Dirty-work and integration boundary

The original/main checkout contains unrelated dirty work. Inspect and classify that state, but do
not work directly over it. Do not reset, clean, checkout over dirty files, force-merge, overwrite
unrelated work, or stash without an explicit demonstrated need. Create a dedicated clean
reconciliation branch/worktree from the evidence-backed current repository state, using a name
consistent with existing Tool Shed branch conventions.

Before integrating, inspect `main`, the original dirty checkout, Campaign 039, all completed App
Server branches, branch ancestry, overlapping commits, unrelated completion-watcher changes, and
changes made after the branches diverged. Document the chosen integration base and why it is the
correct representation of legitimate current Tool Shed mainline work.

Build the minimal correct integration branch. It must include the qualified App Server
infrastructure, centralized model routing, workspace-writing safety and qualification,
compatibility/version registry, optimized CAMP execution, and qualification documentation, while
excluding unrelated experimental or obsolete changes. Resolve conflicts from actual current truth;
do not duplicate already-inherited commits.

### Required preserved behavior

The global default must remain:

```text
codex_app_server_enabled = false
```

App Server CAMP execution remains explicit opt-in. Normal GUI behavior stays unchanged, including
`ts: discuss` in the current GUI conversation and the existing GUI execution/fallback path. App
Server failure or incompatibility must not break normal Tool Shed use.

Keep model selection centralized. The intended policy remains conceptually:

```text
planning             -> Sol / high
program_derivation   -> Sol / high
camp_derivation      -> Sol / high
architecture         -> Sol / xhigh when justified
escalation           -> Sol / high

camp_execution       -> Terra / medium
normal_debug         -> Terra / medium
testing              -> Terra / low
verification         -> Terra / low
build                -> Terra / low
```

Only already-qualified roles may be enabled through App Server. Do not enable a role merely because
it exists in policy.

Preserve the Campaign 040 optimization as a regression requirement: compact deterministic
evidence, orchestrator-owned lifecycle state, minimal model-visible evidence, two-turn execution
where applicable, focused context, progressive diagnostic expansion, compact Git/test results, and
avoidance of redundant skill-orientation turns. Use the Campaign 040 representative CAMP as the
regression fixture and investigate material movement toward seven turns, six tools, or 241k input.
Measurements need not be bit-identical.

Preserve every qualified write safeguard:

```text
ChatGPT authentication only
no API fallback
Terra / medium CAMP execution
workspaceWrite
exact writable root
exact path allowlist
network disabled
temporary-directory exclusions
approval policy never
Git required
dirty declared targets refused
unrelated dirty work preserved
no retry after mutation
no permission expansion
no reset, checkout, or clean
no automatic destructive rollback
```

Keep these compatibility commands operational:

```bash
python3 scripts/codex_app_server_compatibility.py status
python3 scripts/codex_app_server_compatibility.py status --json
python3 scripts/codex_app_server_compatibility.py smoke --cwd .
```

Preserve version-specific qualification records. Codex CLI 0.144.6 remains
`qualified_with_blockers`. If the installed version differs, follow the compatibility and
requalification process instead of inheriting qualification.

Do not mark these blockers solved without new evidence: the cancellation/reconciliation protocol
issue, restricted-read mismatch, unavailable supported GUI approval bridge, unqualified workspace
deployment, and App Server's experimental/non-production support status.

### Validation

After reconciliation, run the complete Tool Shed suite and manifest verification, provider
conformance, campaign and roadmap validation, index regeneration, stale-path and work-state checks,
and disposable-workspace smoke. Also verify App Server compatibility, read-only planning,
verification, the write-safety fixture, the optimized representative CAMP fixture, GUI fallback,
`ts: discuss`, and no-API-fallback behavior. Keep durable, sanitized evidence of the integration
base, conflict resolutions, commands, results, and any material token regression.

### Campaign 039 reassessment

Only after the integration branch is assembled and validated, reassess deferred Campaign 039. Do
not reactivate or silently rewrite it. Determine its original problem, which assumptions predated
App Server integration, whether direct App Server execution replaces watcher responsibilities,
and whether a watcher still has a distinct role in completion detection, orchestration, recovery,
or another boundary. Avoid maintaining two orchestration mechanisms for the same capability.

Recommend exactly one disposition for Campaign 039: resume unchanged, revise, reduce scope,
supersede with a new campaign, or close as obsolete. If a material lifecycle or purpose change is
recommended, present the reassessment first and use normal Tool Shed campaign procedures with
preserved history; do not make the change implicitly inside the assessment.

### Merge readiness and authority boundary

Decide from evidence whether the local integration branch is ready to merge into `main` with App
Server default-disabled. A clean reconciliation, preserved dirty work, full validation, unchanged
GUI behavior, explicit opt-in, intact safety controls, preserved optimization, and visible blockers
may support a ready recommendation, but do not merge merely because integration is desirable.

Do not push, release, deploy, or globally enable App Server. Do not mutate Campaign 039 before its
assessment is reviewed. A local reviewed integration branch is sufficient for this campaign's
qualification gate.

### Final report

Report the assigned campaign number; integration branch/worktree; actual base; source branches;
commits merged, cherry-picked, or reimplemented; conflicts and resolutions; preservation of
unrelated dirty work; default state; qualified roles; Sol/Terra routing; CAMP optimization and
write-safety regressions; compatibility smoke; full validation; known blockers; Campaign 039's
original purpose and reassessment; its recommended disposition; integration merge readiness; and
the next Tool Shed action.

## Completion Check

A documented clean integration base and minimal nonduplicated commit set preserve qualified App Server infrastructure, centralized Sol/Terra routing, default-off GUI fallback, compatibility tooling, write safety, and Campaign 040 optimization; full Tool Shed, App Server, GUI-fallback, compatibility, write-safety, and representative CAMP validation passes without disturbing unrelated dirty work; Campaign 039 is reassessed against the integrated architecture with a clear unchanged, revised, reduced, superseded, or obsolete recommendation; merge readiness, known blockers, conflicts, and the next Tool Shed action are documented; nothing is pushed, released, deployed, or globally enabled.
