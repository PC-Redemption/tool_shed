# Tool Shed campaign routes

Read this reference for numbered work levels, `ts:ship`, campaign execution, `ts: help`,
`ts: commands`, and `ts:ask`.

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

Do not force unrelated pre-existing changes into a checkpoint. If they prevent a clean worktree,
preserve them and report the exception. If the only available `work4` push automatically deploys
production, stop before pushing unless production release is explicitly authorized; never report
that coupled endpoint as non-production.

## Ship Route

Treat `ts:ship <goal>` and `ts: ship <goal>` as authorization to plan, implement, validate, build,
deploy, and verify the workspace goal end to end.

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

## Campaign Continuity

The requested outcome is the campaign. Plans, artifacts, tests, builds, and deployments are stages,
not the campaign itself.

- Keep working while the next action is reversible, in scope, and already authorized.
- Preserve the selected coordination level while continuing. Campaign continuity does not upgrade
  Direct work to Guided, Coordinated, or Deep and does not make inapplicable lifecycle stages apply.
- A progress summary, artifact update, phase boundary, or useful review point is not an approval gate.
- Pause only for requested review, a material unresolved decision, contradictory evidence, new
  authority, or a protected, destructive, irreversible, or not-yet-authorized external action.
- When review is required, identify the exact file or result and section, the precise decision or
  approval, and what follows.

## Owner Campaign Queue

Durable owner-facing campaign state lives under first-sorted `work/00-campaigns/`:

- `active-queue.md`: canonical ordered queue plus last completed, working now, next, blockers,
  decisions, and detour/return state;
- `completed-queue.md`: newest-first verified completion history;
- `active/`, `completed/`, `deferred/`, and `abandoned/`: detailed campaign requests by lifecycle.

Queue entries are accessible cards with icon-plus-text `WORKING`, `READY`, `WAITING`, `BLOCKED`, or
`COMPLETE` states. Use the shared dependency-and-decision readiness calculation for status, `next`,
rendering, and reconciliation. If `work/focus-areas.md` is owner-approved, display catalog names and
require every ordinary active campaign to have a known primary ID; supporting IDs are optional.
Never hard-code or silently approve a focus taxonomy.

Keep `work/01-q&a/ask.txt` as transient intake. Accepting an inbox request may create a durable
campaign, but never moves, clears, or rewrites the inbox without explicit operator authorization.

Use `python3 <shed>/scripts/campaign_queue.py --workspace <workspace>` for deterministic reads and
mutations:

- `ts: queue` and `ts: status`: run `status`, report the compact owner capsule, findings, and any
  pending or active Dangler Resolution campaign for unclassified unresolved work.
- `ts: completed`: run `completed` and summarize recent verified outcomes.
- `ts: next`: run `next`, surface pending Dangler Resolution work, then execute only a selected
  active ready campaign under its natural coordination and requested work level. Run reconciliation
  to add pending Dangler Resolution work to the active queue.
- `ts: add <idea>`: compare with active, deferred, and completed IDs and content; report material
  overlap or direction conflicts; after resolving placement, run `add` with the current state token.
- `ts: unblock <campaign>`: run `unblock` with the current state token; return blocked work to
  queued state, clear its decision, and leave `start` as a separate invariant-checked transition.
- `ts: reconcile campaigns`: run `reconcile_campaign_queue.py` in its default mode.
  Report queue consistency plus whole-`work/` coverage, exclusions, explicit campaign,
  `standalone`, and `excluded` associations, unresolved clusters, and the proposed execution
  order. When unclassified unresolved artifacts exist, automatically create or refresh exactly one
  Dangler Resolution campaign as the first queued work while preserving any working campaign.
  `--dry-run` never writes. Apply any other operation only from an exact approved JSON manifest
  with `--apply --expect TOKEN --manifest PATH`; the token covers the complete scanned work
  surface. Never apply proposed order or ambiguous lifecycle decisions implicitly. Manifest delete
  semantics transition campaigns to completed, deferred, or abandoned history instead of removing
  them.
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

Every mutation requires `--expect TOKEN` obtained immediately beforehand from `status`. Reject a
stale token rather than overwriting newer state. Lifecycle operations use a recovery journal and
validate queue/folder invariants before committing. Do not silently reorder a campaign when
priority or direction is ambiguous. Blocked campaigns stay active; deferral is an intentional
priority decision; abandonment preserves disposition history.

## Program Roadmap Route

Program Roadmaps are an opt-in layer from project-map strategy to bounded campaigns. Use
`python3 <shed>/scripts/program_roadmap.py --workspace <workspace>` for deterministic operations.

- `ts: develop roadmap`: run `develop`; inspect canonical docs, maps, focus areas, queues, and all
  supported `work/**/*.md` evidence. Classify existing work as completed, active, remaining,
  superseded, excluded, or uncertain. This is read-only. Greenfield projects must establish and
  exactly approve their initial project map first.
- `ts: propose roadmap`: capture an exact `tool-shed-roadmap-proposal` manifest and run `propose`
  with its fresh source-state token. This may create only a `proposed` roadmap revision. It does
  not approve the roadmap or create campaigns.
- `ts: approve roadmap <token>`: run `approve` only for the exact proposal token and unchanged
  source-state token. Preserve the preceding approved revision as `superseded`.
- `ts: derive campaigns for milestone <id>`: run `derive`. Return the exact read-only campaign
  manifest with roadmap and queue tokens; do not modify the queue.
- `ts: approve campaign plan <token>`: run `apply-campaign-plan` for the exact current manifest.
  Preserve a working campaign, reject stale inputs and dependency cycles, and materialize only the
  approved milestone candidates. Creation does not authorize campaign execution.
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
It never writes. Campaign or focus-area conversion requires a separate exact approved manifest and
is not implied by preview, installation, update, or `ts:ask`.

## Focus Area Discovery Route

Treat `ts: build focus areas` as a two-stage, project-specific discovery and approval route:

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
4. Request explicit owner approval for that exact catalog and assignment set. Identify the precise
   proposal under review and state that approval will write the catalog, apply assignments, refresh
   indexes, and validate the work state. A request to discover, build, or refresh areas is not by
   itself approval of the proposal.
5. After explicit approval, write `work/focus-areas.md` as `Status: approved`, apply the approved
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

## Help Route

For `ts: commands` or `ts: help all`, read `docs/commands.md` and return the complete command groups
and usage. For `ts: help`, read `docs/operator-guide.md` and return a concise use-case menu. For
`ts: help <topic-or-command>`, read the relevant section of `docs/commands.md` and
`docs/operator-guide.md`, then return focused usage and examples. Do not create or modify
artifacts for a help-only request.

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
