# Tool Shed campaign routes

Read this reference for numbered work levels, persistent autonomy, `ts:ship`, campaign execution,
explicit App Server controls, `ts: help`, `ts: commands`, and `ts:ask`.

## Persistent Autonomy Route

Treat `ts: autonomy <0-5>` as the canonical command and an exact numeric `ts: approve <0-5>` as its
compatibility alias. Before the preference mutation, verify project identity for operation
`autonomy-preference`, surface the project capsule, then run:

```bash
python3 <shed>/scripts/autonomy_control.py --workspace <workspace> set <level> --json
```

Use `status` for `ts: autonomy status` and `reset` for `ts: autonomy reset`. The setting persists
per verified project until changed or reset. A clearly stated one-command or current-run override
applies only to that authority envelope and does not rewrite the stored level.

Before prompting for approval during routed work, classify the contemplated action and run
`autonomy_control.py evaluate`. Continue immediately when it returns `outcome: continue`; obtain
and pass any fresh deterministic state tokens internally. When it returns an interrupt, present its
action, reason, impact, blast radius, rollback, and recommendation. Do not replace that explanation
with an artifact link or token challenge.

Autonomy and work endpoints are independent. Level 5 cannot turn work1 into a push or release, and
a work5 request pauses before actions above the active autonomy level. Missing or invalid preference
state fails to level 0. Tool Shed autonomy cannot waive provider-native permissions, protected
environments, credentials, project identity, or the hard boundaries defined in the portable skill.

## Numbered Work Levels

Treat a leading numbered route as the operator's explicit stopping point for the current execution:

| Route | Required endpoint |
| --- | --- |
| `ts:work1 <goal>` | Implement, run the quickest meaningful check, checkpoint only the requested changes in a local commit, leave the worktree clean when unrelated pre-existing changes do not prevent it, and stop without deployment. |
| `ts:work2 <goal>` | Perform `work1`, deploy to the configured work environment, run focused browser and changed-behavior checks, checkpoint, and stop. |
| `ts:work3 [scope]` | Review the accumulated coded work and create, read, update, or delete project documentation as needed so it matches the candidate; then run the repository's full applicable validation and build, update and verify the work environment when relevant, freeze it in a local commit, and stop. |
| `ts:work4 [scope]` | Perform `work3`, then push the frozen source without intentionally releasing or promoting production. |
| `ts:work5 [scope]` | Perform release qualification, push, release or promote production, and verify the production target. This is equivalent to an explicit `ts:ship`. |

The levels are cumulative execution boundaries, not coordination levels. Keep Direct, Guided,
Coordinated, and Deep selection independent. Aliases are `ts:work` for `work2`, `ts:freeze` for
`work3`, `ts:push` for `work4`, and `ts:ship` for `work5`. `ts:check
<spot|focused|full|release>` runs only the corresponding validation and does not implement, commit,
push, deploy, or release.

Work3 documentation alignment is limited to the requested candidate scope. Preserve unrelated
owner documentation and historical records; delete documentation only when the coded change makes
it obsolete and the deletion is within the authorized scope.

Read optional project state from root `work/tool-shed.yaml` when present. The minimal supported
declaration is:

```yaml
schema_version: 1
work_model: combined
```

- `combined`: the work environment and production are the same target. State plainly before
  remote mutation that `work2` or `work3` may change the live site; `work5` formalizes and verifies
  the release but may not be its first production exposure.
- `split`: `work2` and `work3` affect development only; only `work5` promotes production.

Target names may be declared as `development_target` and `production_target` when existing
workspace docs and tooling do not resolve them. The file is tracked agent-readable project state,
not a credential store, deployment framework, or grant of authority. Reuse existing scripts,
hosting configuration, and runbooks. When the declaration is absent, preserve existing workspace
behavior and ask one concise target question only when repository evidence cannot route a requested
remote stage safely. Reject unsupported schema versions or work models rather than guessing.

Before executing a numbered route, resolve the selected route against that file with the
workspace-local deterministic helper:

```bash
python3 tool_shed/scripts/work_level_config.py --workspace . resolve work3 --json
```

When developing the canonical Tool Shed checkout, use `scripts/work_level_config.py` instead. The
resolver returns the project target capsule and operation-specific session binding. Verify that
capsule before running any configured or default write action; generic editing and shell tools may
not bypass it. A different resolved root is `WORKSPACE_MISMATCH` and requires `ts: use` plus fresh
target instructions, skill, binding, and state. The optional `work_levels` mapping can add ordered
actions around one canonical endpoint:

```yaml
schema_version: 1
work_model: split
work_levels:
  work3:
    before:
      - Run the project's candidate-data refresh script
    run_default: true
    after:
      - Generate the project-specific handoff summary
  work4:
    before:
      - Run the controlled publication preflight
    run_default: false
    after:
      - Verify the workspace-specific publication result
```

Apply exactly one customization envelope for the selected canonical endpoint: ordered `before`
actions, the standard cumulative endpoint unless `run_default: false`, then ordered `after`
actions. Aliases resolve first (`work` to `work2`, `freeze` to `work3`, `push` to `work4`, and
`ship` to `work5`); they do not have separate configuration. Lower-level envelopes do not run
again because the selected endpoint's standard behavior is already cumulative.

Report the resolved actions and explicit default suppression before acting. Every action is
required and runs in declaration order; stop on the first failure, do not run later phases, and do
not report the endpoint complete. Invoking a configured route includes its declared in-scope
actions, but the file cannot bypass request scope, credentials, approvals, destructive-action
safeguards, protected environments, or outcome verification. Missing configuration or a missing
level entry preserves the standard behavior. Reject malformed configuration instead of guessing.

Do not force unrelated pre-existing changes into a checkpoint. If they prevent a clean worktree,
preserve them and report the exception. If the only available `work4` push automatically deploys
production, stop before pushing unless production release is explicitly authorized; never report
that coupled endpoint as non-production.

## Ship Route

Treat `ts:ship <goal>` and `ts: ship <goal>` as authorization to plan, implement, validate, build,
deploy, and verify the workspace goal end to end.

Treat `ts: ship changes since last release` as the same work5 route with its candidate scope bound
to every intended tracked change after the highest stable semantic-version tag through one frozen
content commit. Surface the base tag and exact content-commit SHA. Before creating or pushing the
provenance commit or tag:

1. Push the frozen content commit on its branch.
2. Require a successful `push` run of `.github/workflows/validate.yml` whose `head_sha` exactly
   matches that content commit. The workflow must run the release profile on Ubuntu and Windows
   with Python 3.11 and the current Python 3.x, enforcing the 60-second profile budget.
3. Only after that exact run succeeds, create and push the provenance-only manifest commit and
   stable tag. The publication workflow must independently verify the same successful content-SHA
   run before creating the GitHub Release.

A pull-request run, a run for another SHA, a partial matrix, a skipped or failed job, or local-only
evidence does not satisfy this gate. Stop before tagging when the exact push run is absent or not
successful; fix the candidate and repeat from a new frozen content commit rather than waiving the
gate.

- Inspect workspace guidance and active work before choosing the smallest sufficient plan.
- Continue through every applicable lifecycle stage. Tests or a build are intermediate evidence.
- Treat a lifecycle stage as applicable only when the requested outcome includes it, repository
  policy mandates it, or concrete risk or observed failure justifies it. `ts:ship` explicitly
  requests end-to-end delivery; wording that merely appears near or discusses `ts:ship` does not.
- Do not create planning artifacts, branches, PRs, releases, deployments, or broad qualification
  solely because a request uses Tool Shed. State the concrete reason when expanding beyond focused
  verification.
- Use the project's own tooling, environments, runbooks, and protected-environment controls.
- Keep changes scoped and preserve unrelated work.
- Do not ask for repeated confirmation for reversible, in-scope steps already authorized. One
  request may authorize multiple named operations.
- Ask again only when an action materially expands scope, targets a protected environment, is
  destructive or irreversible, uses an unknown deployment target, publishes externally, or
  otherwise requires new authority.
- Before an already-authorized consequential stage, identify at most three credible failure modes
  and add proportionate prevention, detection, verification, or rollback.
- Explain inapplicable lifecycle stages and complete every safe preceding stage if blocked.

## Evidence-Response Loop

For nontrivial work:

1. Keep the desired outcome and current limiting condition visible.
2. Take the smallest material action that advances or tests the outcome.
3. Compare actual evidence with expected state.
4. When they differ, revise assumptions, the plan, and the next action.

Command success alone is not outcome success. Adaptation does not broaden authority. Skip explicit
loop ceremony for simple answers and known single-step reversible work.

## KISS: Minimum Sufficient Complexity

Choose the smallest complete solution that satisfies the current outcome, safety boundaries, and
proven constraints. Reuse existing mechanisms. Do not add artifacts, abstractions, dependencies,
layers, compatibility scope, tests, or future-proofing unless a current requirement, concrete risk,
or observed failure justifies them. When complexity is necessary, add the smallest bounded amount
and reevaluate.

Apply KISS throughout PRM and campaign execution:

- Plan for the smallest valuable outcome and make non-goals explicit.
- Use the fewest roadmap milestones and evidence gates needed to reach and prove that outcome.
- Make each milestone the smallest independently useful, verifiable slice.
- Reuse existing mechanisms before introducing abstractions, subsystems, or dependencies.
- Run the smallest credible checks for the changed behavior; expand only for demonstrated risk,
  failure, or a required release boundary.
- Recover by fixing the observed failure, rerunning the failed check, and then running one focused
  smoke check before broadening the investigation.

At a transition, ask: Does this directly advance the current outcome? What can be removed or
deferred without sacrificing completeness or safety? What evidence justifies each additional
layer, artifact, or check? KISS does not waive correctness, safety, verification, or authority, and
it does not add a required field, form, checklist, or approval gate.

## Workspace Doctor Route

Treat `ts: doctor` as a request to run the workspace-local `scripts/doctor.py --workspace .`.
The default command is read-only and composes workspace/Git boundaries, snapshot integrity,
repository preflight, Git checkpoint state, canonical work topology, campaign validation and
status, generated-index freshness, stale paths, work-state drift, and whole-work reconciliation.
It reports one `HEALTHY`, `DEGRADED`, `NEEDS_DECISION`, or `INVALID` verdict plus compact finding
counts and exact next actions. `--json` is schema-stable; `--strict` exits nonzero unless the
workspace is fully healthy.

The doctor verifies internal workspace consistency, not current external or runtime truth. A
completed campaign that makes a runtime or external claim without referencing a durable,
sanitized `work/evidence/`, incident, runbook, or spike record is
`external-evidence-required`; the doctor never fabricates or re-observes that evidence.

`ts: doctor --repair` may regenerate only stale deterministic `work/index.md` and
`work/index.json`, and only after campaign source validates, the operator supplies the exact
current doctor state token, and the session supplies the `doctor-repair` project binding. It does
not change lifecycle state, choose semantic truth, rewrite owner-authored artifacts, fabricate
evidence, or apply campaign reconciliation. Queue repairs continue only from an exact current
manifest, fresh reconciliation token, and resolved authority envelope.

## Campaign Continuity

The requested outcome is the campaign. Plans, artifacts, tests, builds, and deployments are stages,
not the campaign itself.

- Keep working while the next action is reversible, in scope, and already authorized.
- Preserve the selected coordination level while continuing. Campaign continuity does not upgrade
  Direct work to Guided, Coordinated, or Deep and does not make inapplicable lifecycle stages apply.
- A progress summary, artifact update, phase boundary, useful review point, fresh token, or evidence
  gate is not a human approval gate by itself.
- Pause only for requested review, a material unresolved decision, contradictory evidence, new
  authority, or a protected, destructive, irreversible, or not-yet-authorized external action.
- When review is required, identify the exact file or result and section, the precise decision or
  approval, and what follows.

## Owner Campaign Queue

Durable owner-facing campaign state lives under first-sorted `work/00-campaigns/`:

Use one shared Cycle State Capsule calculation for `overview`, `status`, and `next`. The nested
cycles are Program → Milestone Wave → Queue → Campaign → Evidence. Evidence returns to Campaign,
Campaign to Queue, Queue to the owning Milestone Wave/Program/owner, and Milestone Wave to Program;
Program completes only when its intended outcome and applicable gates complete. Compute work
origin without a new required header: no queue record is `direct`, Roadmap traceability is
`roadmap-derived`, Detour For/Return To is `detour`, and other queued work is
`owner-originated`. Keep origin independent from coordination, work1–work5 endpoint, and cycle
state; do not reuse `Campaign: standalone` as an origin.

When bare `next` has no ready campaign, report the owning cycle and exact safe transition in this
order: pending Dangler Resolution; an exact current campaign-plan manifest awaiting authority
evaluation; an
incomplete materialized milestone or evidence gate; a derivable next milestone; roadmap drift
requiring review; fully completed roadmap; or no higher-level driver. Never turn the capsule into
implicit approval, materialization, lifecycle mutation, roadmap revision, protected action, or
release authority.

- `active-queue.md`: canonical ordered queue plus last completed, working now, next, blockers,
  decisions, and detour/return state;
- `completed-queue.md`: newest-first verified completion history;
- `active/`, `completed/`, `deferred/`, and `abandoned/`: detailed campaign requests by lifecycle.

Queue entries are accessible cards with icon-plus-text `WORKING`, `READY`, `WAITING`, `BLOCKED`, or
`COMPLETE` states. Use the shared dependency-and-decision readiness calculation for status, `next`,
rendering, and reconciliation. If `work/focus-areas.md` has `Status: approved`, display catalog names and
require every ordinary active campaign to have a known primary ID; supporting IDs are optional.
Never hard-code a focus taxonomy or silently resolve a material taxonomy decision.

Keep `work/01-q&a/ask.txt` as transient intake. Accepting an inbox request may create a durable
campaign, but never moves, clears, or rewrites the inbox without explicit operator authorization.

Use `python3 <shed>/scripts/campaign_queue.py --workspace <workspace>` for deterministic reads and
mutations:

Before any mutation, run `project_identity.py identity --operation campaign-queue`, surface the
target capsule, and pass its `--project-binding` together with the fresh project-bound state token.

- `ts: queue` and `ts: status`: run `status`, report the compact owner capsule, findings, and any
  pending or active Dangler Resolution campaign for unclassified unresolved work.
- `ts: completed`: run `completed` and summarize recent verified outcomes.
- `ts: next`: run bare `next`, surface pending Dangler Resolution work, then preserve the existing
  single-campaign behavior: resume the working campaign or execute the first ready campaign under
  its natural coordination and requested work level. Run reconciliation to add pending Dangler
  Resolution work to the active queue.
- `ts: next 1,2`, `ts: next que 1,2`, `ts: next camp 025,example-id`, and `ts: next *`: pass the
  selection to `next` (`*` must be quoted when invoking it through a shell). Queue positions are a
  compatibility shorthand; `que` makes them explicit, `camp` selects exact zero-padded campaign
  numbers or full IDs, and `*` snapshots every currently active campaign. Reject an invalid queue
  projection, duplicate, missing, ambiguous, or out-of-range target. Retain the resolved stable IDs
  and snapshot token so later queue movement or newly added campaigns cannot change the batch.
  Resume a selected working campaign first, then run targets sequentially with at most one working
  campaign. After every completion gate passes, use guarded completion, refresh indexes, validate
  campaign and work state, check stale paths, and recompute dependency readiness. Stop at the first
  failure, blocker, decision, stale state, unsatisfied dependency, protected action, or missing
  authority; report completed and remaining stable IDs plus the exact resume point. Selection never
  grants work5, deployment, release, production promotion, destructive, credential, or other
  consequential authority.
- `ts: add <idea>`: compare with active, deferred, and completed IDs and content; report material
  overlap or direction conflicts; after resolving placement, run `add` with the current state token.
- `ts: unblock <campaign>`: run `unblock` with the current state token; return blocked work to
  queued state, clear its decision, and leave `start` as a separate invariant-checked transition.
- `ts: reconcile campaigns`: run `reconcile_campaign_queue.py` in its default mode.
  Report queue consistency plus whole-`work/` coverage, exclusions, explicit campaign,
  `standalone`, and `excluded` associations, unresolved clusters, and the proposed execution
  order. When unclassified unresolved artifacts exist, automatically create or refresh exactly one
  Dangler Resolution campaign as the first queued work while preserving any working campaign.
  `--dry-run` never writes. Apply any other operation only from an exact current JSON manifest with
  `--apply --expect TOKEN --manifest PATH`; the token covers the complete scanned work surface.
  Apply an unambiguous, reversible, in-envelope manifest automatically at the required autonomy
  level. Never apply ambiguous priority, ownership, or lifecycle decisions implicitly. Manifest
  delete semantics transition campaigns to completed, deferred, or abandoned history instead of
  removing them.
- `ts: defer <campaign>`: require a reason and reactivation condition, then run `defer` with the
  current state token.
- `ts: abandon <campaign>`: require a disposition and replacement when applicable, then run
  `abandon` with the current state token.
- Campaign completion: require the request's explicit completion gate and applicable verification,
  then run `complete --gate-passed --evidence ...` with the current state token.

In owner-queue requests, `camp` is shorthand for `campaign`. `que N` means the campaign at the
mutable 1-based position N in the current ordered queue. A heading such as `1. (004) Title`
distinguishes queue position 1 from stable campaign number 004; every card separately shows its
full stable `Campaign ID`. Resolve `que N` from a fresh `status` read immediately before acting,
and reject a missing or out-of-range position instead of guessing. Preserve a campaign number
from an existing numeric ID prefix; guarded `backfill-numbers --expect TOKEN` assigns durable
zero-padded numbers to legacy slug-only histories, atomically renames request files to
`<number>-<campaign-id>.md`, and refreshes queue links before ordinary lifecycle mutations continue.
Lifecycle commands accept either the exact zero-padded number or the full Campaign ID.

Every mutation requires the operation-specific `--project-binding` and `--expect TOKEN` obtained
immediately beforehand from the same target's `status`. Reject stale, foreign-project, or
root-mismatched tokens rather than overwriting newer state. Lifecycle operations use a recovery journal and
validate queue/folder invariants before committing. Do not silently reorder a campaign when
priority or direction is ambiguous. Blocked campaigns stay active; deferral is an intentional
priority decision; abandonment preserves disposition history.

## Program Roadmap Route

Program Roadmaps are an opt-in layer from project-map strategy to bounded campaigns. Use
`python3 <shed>/scripts/program_roadmap.py --workspace <workspace>` for deterministic operations.

### PRM: the full outer lifecycle

`PRM` means **Plan → Roadmap → Milestone**. It names Tool Shed's complete outer coordination
lifecycle from understood intent to evidence-gated delivery. An optional Brainstorm / Discovery
Cycle may precede it when an idea needs durable multi-session exploration:

`Idea → Brainstorm / Discovery → PRM (Plan → Roadmap → Milestone)`

- The **Plan Cycle** explores intent, constraints, and current evidence until the desired outcome
  and project direction are clear enough to settle in a project map.
- The **Roadmap Cycle** develops, proposes, approves, executes, reviews, and when evidence requires
  it revises the Program Roadmap. This is the human-facing name for the existing Program Cycle.
- The **Milestone Cycle** derives one milestone's exact campaign plan, validates its fresh tokens,
  materializes and runs its queue under the active authority envelope, evaluates its evidence gate,
  and returns control to the roadmap. Human input occurs only for a genuine decision or authority
  boundary. This is the human-facing name for the existing Milestone Wave Cycle.

Treat `ts: prm <outcome>` as an explicit request to carry that outcome through the full PRM
lifecycle and continue through every safe, already-authorized transition until the intended
outcome and applicable gates pass or genuine owner intervention is required. PRM contains the
existing Queue, Campaign, and Evidence cycles; it does not replace them. Preserve the stable
machine-facing `program` and `milestone_wave` Cycle State Capsule names for compatibility.

Treat `ts: prm idea <idea-id-or-path>` as the same PRM route with one selected
`work/ideas/idea-*.md` Idea Brief as its durable discovery source. Read its current synthesis,
constraints, tradeoffs, open questions, decisions, and exploration history. Preserve unknowns
rather than fabricating certainty. Keep the brief `ready-for-prm` during the Plan Cycle; after an
approved project map captures its direction, set it to `promoted`, name that map in `Produces:`,
and preserve the brief as provenance. That status update does not independently expand the active
authority envelope.

PRM is coordination, not blanket authority. It automatically accepts faithful derived maps,
roadmaps, campaign plans, materialization, and lifecycle transitions only when the active authority
envelope covers them. It does not publish or deploy beyond the requested endpoint, cross a
protected boundary, or authorize credentials, destructive recovery, or an unknown external target.
A full PRM is complete only when the intended outcome and every applicable evidence gate pass—not
when a plan, roadmap, milestone, campaign, or empty queue merely exists.

- `ts: develop roadmap`: run `develop`; inspect canonical docs, maps, focus areas, queues, and all
  supported `work/**/*.md` evidence. Classify existing work as completed, active, remaining,
  superseded, excluded, or uncertain. This is read-only. Greenfield projects must establish their
  initial project map first; accept it automatically at level 1 or higher when it is a faithful,
  reversible expression of the stated direction.
- `ts: propose roadmap`: capture an exact `tool-shed-roadmap-proposal` manifest and run `propose`
  with its fresh source-state token. This creates a `proposed` roadmap revision. When the proposal
  is a faithful in-envelope derivation and level 1 or higher covers planning state, immediately run
  `approve` with its fresh internal tokens; otherwise present the material decision or manual route.
- `ts: approve roadmap <token>`: preserve this explicit level-0 compatibility route. Run `approve`
  only for the exact proposal token and unchanged source-state token, and preserve the preceding
  approved revision as `superseded`.
- `ts: derive campaigns for milestone <id>`: run `derive`. Return the exact read-only campaign
  manifest with roadmap and queue tokens; do not modify the queue.
- `ts: approve campaign plan <token>`: preserve this explicit level-0 compatibility route. Run
  `apply-campaign-plan` for the exact current manifest. At level 3 or higher, automatically apply an
  unambiguous in-envelope plan with its fresh internal token, preserve a working campaign, reject
  stale inputs and dependency cycles, and materialize only its milestone candidates. When the same
  outcome and requested endpoint already authorize execution, continue into the ready campaign
  without inventing a separate start approval.
- `ts: roadmap status` and `ts: review roadmap`: report computed milestone and gate progress,
  completion evidence, source drift, and revision state without changing approved intent.
- `ts: overview`: run `overview` and combine project maps, current approved roadmaps, milestone and
  gate state, focus areas, campaign readiness, strategic/execution recommendations, and drift.

Roadmap milestones, gates, and revisions use stable IDs. Campaign requests derived from a roadmap
must carry `Roadmap`, `Roadmap Revision`, `Milestone`, and `Unlocks Gate`. Installation or upgrade
may create `work/roadmaps/` but never ingests existing work, proposes or approves a roadmap, or
materializes campaigns implicitly. Standalone project maps and queues remain valid.

Use `migrate-preview` to inspect Markdown requests and actionable inbox lines in canonical
`work/01-q&a/` or pre-installer legacy `work/q&a/`. It also previews legacy outcome focus phrases;
only fully matched values from an approved catalog produce suggested `set_focus_areas` operations.
It never writes. Campaign or focus-area conversion requires a separate exact current manifest and
authority-envelope evaluation; it is not implied by preview, installation, update, or `ts:ask`.

## Focus Area Discovery Route

Treat `ts: build focus areas` as a project-specific discovery and authority-envelope route:

1. Inspect existing project evidence: README and architecture documentation, source modules and
   build targets, tests and fixtures, integrations, runtime/service/hardware boundaries,
   qualification, deployment/release/regulatory/supply workflows, and durable work history. Avoid
   raw generated evidence, vendored dependencies, caches, and build output unless a concise
   versioned summary is the only evidence for an enduring responsibility.
2. Read any existing `work/focus-areas.md`. Preserve stable IDs and accepted boundaries unless
   project evidence justifies a named addition, retirement, split, merge, or boundary change.
3. Present an exact proposed catalog with stable lowercase kebab-case IDs, names, purpose,
   inclusions, exclusions, cited workspace paths, uncertainty, coverage gaps, and proposed primary
   and supporting assignments for every active campaign. Do not create, refresh, approve, or assign
   anything yet.
4. Classify whether the exact catalog and assignment set are faithful, reversible consequences of
   settled project evidence or contain a material ownership, responsibility, split, merge, or
   priority decision. Apply the former automatically when level 1 covers planning state; present
   the latter as a self-contained decision with alternatives and consequences.
5. After authority resolution, write `work/focus-areas.md` as `Status: approved`, apply the exact
   active-campaign assignments, refresh `work/index.md` and `work/index.json`, then run campaign
   validation, stale-path checks, and the read-only work-state review. Preserve unrelated work and
   reject stale state or a catalog/assignment mismatch instead of partially accepting it.

If evidence is insufficient or material boundaries remain ambiguous, keep the route read-only and
name the evidence or owner decision needed. Never invent a universal taxonomy, silently approve a
catalog, overwrite an accepted boundary without explanation, or leave active campaigns unmapped by
an approved catalog.

End every Tool Shed campaign response with exactly one verdict:

- `Campaign status: COMPLETE` only when the whole outcome and applicable verification are finished.
- `Campaign status: CONTINUE` when work remains but the turn must end without operator input; name
  the next action. Do not stop if that action can safely run now.
- `Campaign status: BLOCKED` when progress requires a named decision, dependency, permission,
  credential, external-state change, or required review; state the precise operator action.

## App Server Preference and Explicit Route

The committed repository default remains off. A protected user-local preference may make eligible
unflagged commands prefer App Server. Resolve execution in this order: standalone `--gui`, strict
standalone `--app-server`, persisted preference, then the committed GUI default. Do not interpret
examples, quoted text, or a mere mention as a control request.

| Prompt | Supported role | Model / reasoning | Orchestrator path |
| --- | --- | --- | --- |
| `ts: plan <request> --app-server` | planning | `gpt-5.6-sol` / `high` | read-only `run` |
| `ts: verify <request> --app-server` | verification | `gpt-5.6-terra` / `low` | read-only `run` |
| `ts: camp run <camp> --app-server` | CAMP execution | `gpt-5.6-terra` / `medium` | bounded `camp-run` |
| `ts: next --app-server` | selected qualified role only | selected role policy | one deterministic dispatch to normal `next`, then its existing runner |

The same unflagged routes use App Server only while the preference is on. `--gui` is a one-command
override and never changes the preference. Remove either standalone execution option from the
request passed to the worker. Discussion, brainstorming, qualification gates, unsupported roles,
and other GUI-native routes remain GUI-native regardless of the preference.

Before every explicit operation, run the deterministic selector from the workspace-local shed:

```bash
python3 <shed>/scripts/app_server_control.py select <plan|verify|camp-run> --json
```

Add `--app-server` for a strict request or `--gui` for the one-command override. Surface its concise
execution banner. Continue to App Server only when `allowed` is true. An explicit App Server request
fails closed; a persisted request that cannot select App Server records a sanitized event, reports
the reason, and continues the same action immediately in the current GUI without asking or stopping.
Fresh schema-v2 `ts: app-server on` consent selects `operator-runtime` trust for every supported
local role, including CAMP. In that mode, version and executable hash are telemetry, and missing
positive qualification or dirty-read evidence never blocks admission. The actual App Server
operation supplies the runtime handshake through startup, ChatGPT authentication, live model
selection, requested sandbox, and the existing role-specific path. Do not add a second preflight.

An exact qualification-registry record with `status: unqualified` and a non-empty reviewed evidence
reference is the only normal-mode version denial. It blocks only that exact version; a different
fixed or newer version runs normally. The dirty-read cache and disposable harness remain advisory
diagnostic, reproduction, release-qualification, or optional strict-mode tools. They never grant or
deny operator-runtime access. A repository `.tool-shed-policy.json` may explicitly select
`app_server.certification_mode: strict-certified` with a reason; only that optional mode requires
matching certification evidence.

For allowed planning and verification, call the existing `codex_orchestration.py
--enable-app-server run` path with the selected role, a focused read-only prompt, the workspace,
and only relevant explicit context files. App Server planning returns advisory planning output;
any later artifact or source mutation remains owned by the GUI workflow and its ordinary authority
boundaries.

For allowed CAMP execution, resolve the exact campaign/CAMP step, writable repository root,
expected path allowlist, focused context, and shell-free deterministic verification commands, then
call the existing `codex_orchestration.py --enable-app-server camp-run` path. Never create a second
CAMP implementation or weaken its Git journal, dirty-target refusal, approval policy, network,
retry, lifecycle, or path restrictions.

Treat App Server `turn/completed` only as protocol turn completion. The CAMP worker must return
`step_ready_for_verification` or `camp_ready_for_verification` when its bounded implementation is
ready; it must not run reserved deterministic commands itself. The compatibility outcomes
`step_complete` and `camp_complete` have the same verification-pending meaning. Only those handoff
outcomes authorize the orchestrator to run every declared deterministic command exactly once.
Record a path-safe result as `safe_unverified` until that succeeds, `verification_failed` when any
declared command fails, and `verified` only for the combined safe boundary and successful checks.
Malformed, partial, `unknown`, interrupted, unsafe, and unexpected-path results fail closed. Do not
retry after mutation. A focused-context token warning or oversized tool result must emit a compact
enforceable finding and block lifecycle advance; do not retain raw tool output in the journal.
During CAMP execution, enforce the configured live ceiling before another model request can expand
the turn: four observed model requests, 180,000 cumulative input tokens, 64 KiB cumulative
serialized tool results, and 16 KiB for one result by default. On a reached ceiling, request
`turn/interrupt`, retain only counts/limits and acknowledgement state, skip reserved verification,
and preserve the Git journal. Return `resume_bounded_camp` when no mutation occurred or
`reconcile_workspace_then_resume_bounded_camp` when it did; never replay the mutated step.

For eligible `ts: next`, including the explicit form, immediately invoke the deterministic
dispatcher once when selection chooses App Server:

```bash
python3 <shed>/scripts/app_server_dispatch.py --workspace . next --json
```

Do not launch `codex exec`, another Codex conversation, or an agent wrapper around this command.
The dispatcher reuses ordinary `next` selection unchanged; `next` remains an invocation-scoped
forwarding preference, not an App Server role. Reuse a selected CAMP's single valid
`## App Server Execution Capsule` section when present. New campaign creation and roadmap
materialization record one compact `## App Server Preparation Contract` containing stable semantic
intent while reserving exact paths, commands, executables, and budgets for dispatch-time
resolution. When a ready campaign has no capsule, or when an automatically persisted capsule is
stale, assemble a deterministic focused snapshot from the campaign, project instructions, Git state,
relevant file inventory, and bounded source excerpts. Give only that isolated snapshot to the
existing qualified read-only App Server planning role, with no tool access, to return a strict
structured schema-version-1 capsule with matching campaign/CAMP IDs, prompt, repository-relative
expected paths and context files, and shell-free deterministic verification argv arrays. Validate
the CAMP role and host before spending planning tokens. Include actual file byte sizes and the
automatic context budget in the planning snapshot; the combined context_files size must not exceed
the smaller of 64,000 bytes and the configured inline limit. Validate the planning result, context
budget, protected-path exclusions, selected executables, writable Codex state, managed ChatGPT
authentication, network/model catalog access, and both role qualifications before any workspace or
lifecycle mutation. Persist valid preparation through the
guarded campaign transaction, reload and revalidate it, then continue in the same invocation: start
the queued campaign when needed and call the existing bounded `camp-run` path once. Existing valid
capsules skip planning. Automatically persisted capsules must bind campaign intent and their exact
path, context, and verification boundary to current source state; stale automatic capsules are
replaced through the guarded campaign transaction before execution. Before persistence or worker
launch, require an atomic or independently verifiable bounded slice, available platform-local
executables, quiet scoped verification, no more than eight expected paths and four verification
commands, at most three estimated worker turns, and at most 12,288 bytes for the estimated largest
tool result. Unsafe or oversized work must be reduced before acceptance. Unsafe, indeterminate,
invalid, or over-budget preparation fails closed
before mutation. The CAMP path retains `gpt-5.6-terra` with `medium` reasoning; preparation uses the
centralized planning policy. Emit compact separate preparation and execution usage, journal,
verification, and recovery fields. The deterministic dispatcher uses zero model tokens and reports
GUI token usage as unavailable when the provider does not expose it.
Do not create a `next` role selector, a second CAMP runner, or duplicate executable, version, role,
authentication, model, or reasoning policy.

When `next` selects discussion, user interaction or decision work, blocked work, a qualification
gate, external work, GUI-native work, an invalid existing capsule, preparation that cannot safely
establish exact execution boundaries, or any unqualified or unsupported role, report the selected
action and its ordinary next route without starting CAMP execution. Discussion remains GUI-native.
If selection, Codex discovery, authentication, qualification, startup, network, model lookup,
read-only preparation, or another pre-mutation step fails, explicit App Server remains fail-closed.
For a persisted request, report the compact category and continue the same action in GUI immediately.
If App Server may have mutated the workspace, reconcile the existing mutation journal and Git state
in GUI before continuing; never replay the App Server step. This forwarding never changes the
repository default or enables API fallback.

`ts: discuss`, `ts: brainstorm`, and `ts: bs` are always GUI-native. Reject their use with
`--app-server` using `discussion_is_gui_native` or `brainstorm_is_gui_native` as applicable; do not start App Server. Explicit App Server
selection for any unqualified role is likewise rejected. Program/CAMP derivation, architecture,
implementation, testing, build, deployment, deterministic execution, escalation, and other write
roles do not become qualified through the option.

Treat `ts: app-server status` as the canonical read-only status route; `ts: appserver status` is an
exact compatibility alias:

```bash
python3 <shed>/scripts/app_server_control.py status
```

It reports the repository default, persistent preference and path, trust policy/source, startup
readiness, observed safety, optional certification state, the complete bounded candidate inventory,
selected executable and source, supported roles, current GUI default, GUI-native discussion, and
disabled API fallback. Version and executable hash are diagnostic evidence in normal mode. A
supplied override is authoritative; otherwise the highest semantically eligible candidate at or
above `0.146.0` wins, with source priority used only for equal-version ties.

For `ts: app-server on|off` (or the exact `appserver` alias), run
`app_server_control.py preference on|off`. Store only the schema-versioned mode and timestamp at
`$CODEX_HOME/tool-shed/app-server-preference.json` (or `~/.codex/tool-shed/...`), never in a
canonical workspace or installed snapshot. Writes must be atomic, inter-process safe, and mode
`0600` under a mode-`0700` parent where supported. Missing, malformed, unsupported, or unreadable
state fails safely to off and is surfaced by status. A new `on` writes schema v2 with
`trust_policy: operator-runtime` and a consent timestamp. Legacy schema-v1 `on` stays enabled for
read roles but does not authorize CAMP until the operator runs `on` again. This route never changes
`codex_app_server_enabled`, enables API-key fallback, expands permissions, or grants release,
deployment, push, credential, or external-mutation authority.

Record passive App Server attempts, completions, fallbacks, and reconciliation handoffs as compact
JSON Lines at `$CODEX_HOME/tool-shed/app-server-events.jsonl` (or `~/.codex/tool-shed/...`). Events
may contain only timestamp, route, outcome, controlled category, mutation state, backend,
preference mode, and strict-request flag—never prompts, responses, raw tool output, credentials,
secrets, arbitrary exception messages, or repository content. Use a private parent and mode `0600`
where supported. Event logging is best-effort: a logging failure must never block GUI fallback or
the current action.

## Help Route

For `ts: commands` or `ts: help all`, read `docs/commands.md` and return the complete command groups
and usage. For `ts: help`, read `docs/operator-guide.md` and return a concise use-case menu. For
`ts: help <topic-or-command>`, read the relevant section of `docs/commands.md` and
`docs/operator-guide.md`, then return focused usage and examples. Every response in the `ts: help`
family must visibly include `Browse Tool Shed help: https://ts.rookaro.com/`. A `ts: commands` or
`ts: help all` response must also include
`Browse the complete command reference: https://ts.rookaro.com/ref/`. Focused help may include a
stable topic URL only when the public site defines it, and it must still retain the root help link.
The public links supplement the required workspace-local reads: do not replace local help, perform
a request-time network or availability check, or make offline help depend on the site. Do not
create or modify artifacts for a help-only request.

## Q&A Inbox Route

For `ts:ask` or `ts: ask`, run:

```bash
python3 <shed>/scripts/read_ask_inbox.py --workspace <workspace> --json
```

The canonical inbox is `work/01-q&a/ask.txt`; `work/q&a/ask.txt` is a pre-migration legacy fallback. Ignore blank and
comment lines. Use the only actionable inbox. If both are actionable, do not merge or act; report
the conflict and ask which to use. Never move, clear, rewrite, or delete either file without
explicit authorization. Dispatch the selected content under its natural coordination level;
`ts:ask` does not turn a bounded Direct request into a heavyweight campaign. Summarize what was
selected and done.

During workspace installation or upgrade, copy and byte-verify all contents from legacy
`work/q&a/` and root `q&a/` into `work/01-q&a/`, preserve collisions under source-specific names,
then remove the old folders. This filesystem migration does not convert inbox content into durable
campaigns and does not clear the canonical inbox.
