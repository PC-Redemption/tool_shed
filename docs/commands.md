# Tool Shed AI Command Reference

Tool Shed commands are prompts for a workspace-capable AI agent. They are not shell commands and
there is no separate Tool Shed server. Put one route at the start of the request; it applies only
to that request.

Use this page for the complete prompt inventory. Use the
[operator guide](operator-guide.md) for workflows and examples, and use `--help` on the underlying
Python scripts for their CLI arguments.

All `ts: help`-family responses read these workspace-local sources and visibly include
`Browse Tool Shed help: https://ts.rookaro.com/`. `ts: commands` and `ts: help all` also include
`Browse the complete command reference: https://ts.rookaro.com/ref/`. These links supplement
offline local help; rendering never performs a request-time availability check.

## Syntax

```text
ts: <request>
```

The `ts:` prefix routes the remainder of the request to the workspace-local Tool Shed. It does not
carry into the next message. A natural-language request may combine planning with an execution
endpoint, for example:

```text
ts: plan the documentation refresh, then work3
```

Routes never bypass repository policy, safety controls, credentials, protected-environment
approvals, or the authority stated in the request.

## Workspace Identity

| Prompt | Usage |
| --- | --- |
| `ts: identity` | Read the stable project ID, project name, resolved root, repository fingerprint, active campaign, and current session binding. Read-only. |
| `ts: use <project-alias-or-path>` | Explicitly verify another workspace, then reload its instructions and Tool Shed skill and obtain fresh target-bound state. The verification itself is read-only. |

Before a session's first mutation, bind it to the exact project ID and resolved root shown by:

```bash
python3 tool_shed/scripts/project_identity.py --workspace . identity \
  --operation campaign-queue --json
```

Pass the returned operation-specific binding as `--project-binding` and use only state tokens read
from that same target. Tokens hash the project ID and resolved root, so foreign-project and
different-clone tokens fail even when work content is identical. An outside-root path produces
`WORKSPACE_MISMATCH`; a path mention or read-only inspection never implies a switch.

## Persistent Autonomy

| Prompt | Usage |
| --- | --- |
| `ts: autonomy <0-5>` | Persist the cumulative autonomy level for the verified current project. |
| `ts: approve <0-5>` | Exact numeric compatibility alias for `ts: autonomy <0-5>`. |
| `ts: autonomy status` | Show the current project, level, covered categories, preference source, and hard boundaries. Read-only. |
| `ts: autonomy reset` | Remove the current project's preference and fail safely to level 0. |
| `ts: autonomy <level> for this run` | Apply a clearly scoped non-persistent override to the current authority envelope. |

The levels are cumulative: `0 Observe`, `1 Plan`, `2 Build`, `3 Checkpoint`, `4 Collaborate`, and
`5 Deliver`. They control interruptions, not task scope or the requested work1-work5 endpoint.
Effective authority is the intersection of outcome and scope, endpoint, known target, autonomy
level, and provider policy.

Covered faithful actions continue automatically, including applicable planning acceptance,
campaign materialization, queue transitions, execution, evidence gates, and completion. Fresh
tokens remain internal concurrency controls. Tool Shed interrupts only for new authority, a
material unresolved decision, an unknown target, broad destructive or irreversible action,
credentials, cross-workspace or account work, financial/legal commitments, or provider-native
protection. Every interrupt explains impact, blast radius, rollback, and recommendation inline.

## Help And Discovery

| Prompt | Usage |
| --- | --- |
| `ts: help` | Return a concise local use-case menu plus the public root help link. Read-only unless the same request explicitly asks for a change. |
| `ts: commands` | Return the complete local command groups and usage plus the public `/ref/` link. Read-only. |
| `ts: help all` | Alias for the complete local command reference, with both public help and `/ref/` links. Read-only. |
| `ts: help <topic-or-command>` | Explain the named workflow locally with examples and retain the public root help link. Read-only. |
| `ts: discuss <topic>` | Explore the outcome, constraints, assumptions, unknowns, and smallest useful next route without modifying workspace artifacts. |
| `ts: brainstorm` | List active Idea Briefs under `work/ideas/` without mutation. |
| `ts: brainstorm <idea>` | Create or resume one durable pre-PRM Idea Brief, updating its current synthesis and useful dated exploration notes. |
| `ts: bs <idea>` | Exact alias for `ts: brainstorm <idea>`. |
| `ts: build focus areas` | Inspect existing workspace sources and produce a project-specific focus-area catalog and active-campaign assignments. Faithful reversible results may apply under planning autonomy; material responsibility choices require a decision. |
| `ts: develop roadmap` | Read project evidence and clarify an opt-in Program Roadmap without mutation. |
| `ts: overview` | Combine maps, approved roadmaps, gates, focus areas, campaign state, and drift. Read-only. |

`discussion: <topic>` is also accepted as an informal, read-only discussion signal.

## Brainstorm And Idea Briefs

Brainstorming is Tool Shed's durable pre-PRM Discovery Cycle:

```text
Idea → Brainstorm / Discovery → PRM (Plan → Roadmap → Milestone)
```

`brainstorm` and `bs` are equivalent. Unlike `ts: discuss`, the brainstorm route authorizes
creating or updating exactly one tracked `work/ideas/idea-*.md` Idea Brief. Before creating a new
one, compare active brief titles and current syntheses; resume one clear material match and ask one
concise choice if several match. A bare `ts: brainstorm` only lists active briefs.

Each turn keeps `Current Synthesis` concise and appends only useful dated context to `Exploration
Log`. Capture possibilities, tradeoffs, constraints, non-goals, reminders, assumptions, open
questions, and decisions without requiring every section to be complete. Supported statuses are
`exploring`, `ready-for-prm`, `promoted`, and `parked`. Idea Briefs appear in the work index but are
excluded from campaign reconciliation.

Use `ts: brainstorm idea <idea-id-or-path>` or its `ts: bs` equivalent to explicitly resume one
brief. Use `ts: prm idea <idea-id-or-path>` to carry it forward; keep it ready-for-PRM until
settled project-map direction captures it, then preserve it as promoted provenance with
`Produces:` pointing to that map.

Brainstorming does not authorize a project map, roadmap, campaign, source change, deployment, or
publication. Promotion does not independently expand the authority envelope. Brainstorming is
GUI-native; `--app-server` is not supported for `brainstorm` or `bs`.

## Execution Endpoints

The numbered levels are cumulative stopping points. They do not make a Direct request more
complex or grant authority outside the stated goal.

| Prompt | Stop after |
| --- | --- |
| `ts:work1 <goal>` | Implement, run the quickest meaningful check, and create a scoped local checkpoint commit. Do not deploy. |
| `ts:work2 <goal>` | Perform work1, deploy to the configured work environment, and run focused browser and changed-behavior checks. |
| `ts:work3 [scope]` | Review the accumulated coded work and create, read, update, or delete project documentation as needed so it matches the candidate; then fully validate and build, update the work environment when relevant, and freeze it locally. |
| `ts:work4 [scope]` | Perform work3, then push without intentionally promoting production. |
| `ts:work5 [scope]` | Qualify, push, release or promote production, and verify the production target. |

Readable aliases:

| Alias | Equivalent route |
| --- | --- |
| `ts:work <goal>` | `ts:work2 <goal>` |
| `ts:freeze [scope]` | `ts:work3 [scope]` |
| `ts:push [scope]` | `ts:work4 [scope]` |
| `ts:ship <goal>` | `ts:work5 <goal>` |

`ts: ship changes since last release` scopes work5 to the intended tracked changes after the
highest stable semantic-version tag through one frozen content commit. Tool Shed pushes that
content commit first and waits for the exact-SHA `Validate` push run: the release profile must pass
within 60 seconds on Ubuntu and Windows with Python 3.11 and current 3.x. Only then may it create
and push the provenance-only commit and stable tag. Publication verifies the same CI evidence and
fails closed for a different SHA, pull-request-only run, incomplete matrix, or unsuccessful run.

Validation-only route:

```text
ts:check <spot|focused|full|release>
```

This validates only. It does not implement, commit, push, deploy, or release.

In the Tool Shed repository, `scripts/validate_tool_shed.py` implements the reusable profiles.
`focused` owns validator-orchestration regressions, `full` owns every unit behavior plus current
repository contracts, and `release` adds only the disposable cross-command installation smoke.
Independent unit cases run in isolated concurrent processes and all failures are reported in stable
test-ID order. The default CLI profile is `full`; CI and release qualification pass
`--profile release --max-seconds 60` explicitly.

Work3 document changes stay within the requested candidate scope. Preserve unrelated owner
documentation and historical records, and delete documentation only when the coded change makes it
obsolete.

Projects may define `work/tool-shed.yaml` with `work_model: combined` or `work_model: split`.
Combined work and production targets mean work2 or work3 may affect the live site. Split mode
reserves production promotion for work5.

The same optional file may wrap one canonical endpoint with ordered workspace-specific `before`
and `after` actions or set `run_default: false` to replace its standard behavior. Before executing
a numbered route, resolve it with `tool_shed/scripts/work_level_config.py`; aliases use their
canonical level, lower-level envelopes do not repeat, and absent configuration preserves the
standard definitions above. See [workspace work-level customization](work-level-customization.md).

## Nested Cycles And Work Origin

The Tool Shed workflow is the operator path through direction, execution, evidence, and review.
Five nested control cycles govern how that workflow repeats and returns control. Completing an
inner cycle returns control to its owner; it does not imply that the outer outcome is complete.

KISS means **minimum sufficient complexity**. Choose the smallest complete solution that satisfies
the current outcome, safety boundaries, and proven constraints. Reuse existing mechanisms and add
complexity only when a current requirement, concrete risk, or observed failure justifies it. This
guides planning, roadmaps, milestones, implementation, testing, and recovery without adding a new
required field or approval gate.

`PRM` means **Plan → Roadmap → Milestone**, the complete outer Tool Shed coordination lifecycle
after an outcome is understood well enough to pursue. An optional Brainstorm / Discovery Cycle
precedes PRM for durable multi-session exploration. The Plan Cycle settles intent and project-map direction; the Roadmap Cycle owns the Program Roadmap
and is the human-facing name for the Program Cycle; and the Milestone Cycle runs evidence-gated
milestone waves and is the human-facing name for the Milestone Wave Cycle. PRM contains the Queue,
Campaign, and Evidence cycles and preserves their existing machine-facing Cycle State Capsule names.
It completes only when the intended outcome and all applicable gates pass.

| Cycle | Repeating transition | Complete when | Control returns to |
| --- | --- | --- | --- |
| Program Cycle | Settle roadmap → execute milestone waves → review drift/revise | Intended program outcome and all applicable gates pass | Owner/program review |
| Milestone Wave Cycle | Derive exact plan → resolve authority → materialize → run queue → evaluate gate | Milestone campaigns and evidence gate pass | Program Cycle |
| Queue Cycle | Select ready campaign → run campaign cycle → repeat | No ready campaign remains | Milestone Wave Cycle, Program Cycle, or owner |
| Campaign Cycle | Start → execute → verify gate → complete or block | Completion gate passes with evidence and lifecycle record completes | Queue Cycle |
| Evidence Loop | Observe → act → verify → adapt | Actual state matches expected state or a real blocker is proven | Current Campaign Cycle |

Work origin is computed from existing state: no queue record is `direct`; a campaign with
`Roadmap` traceability is `roadmap-derived`; `Detour For` or `Return To` makes it `detour`; any
other queued campaign is `owner-originated`. Do not call origin “standalone”: `Campaign:
standalone` already means a work artifact intentionally outside campaign coverage.

These four dimensions remain independent:

| Dimension | Question | Values |
| --- | --- | --- |
| Work origin | Where did the work come from? | direct, owner-originated, roadmap-derived, detour |
| Coordination | How much structure does it need? | Direct, Guided, Coordinated, Deep |
| Execution endpoint | How far should it run? | work1 through work5 |
| Cycle state | Which loop owns the next transition? | evidence, campaign, queue, milestone wave, program |

A roadmap-derived campaign can still use Direct coordination and stop at work1. `ts: overview`,
`ts: status`, and `ts: next` expose the same JSON and human-readable Cycle State Capsule. When no
campaign is ready, `next` rolls control upward and reports the owning cycle plus one safe command:
Dangler Resolution, exact persisted campaign-plan authority evaluation, incomplete milestone/gate
work, next-milestone derivation, roadmap drift review, completed program, or an owner choice between
direct work and `ts: add`. Covered faithful transitions advance with fresh internal tokens; it
never infers a material decision or expands the active envelope.

## Owner Campaign Queue

Durable owner-facing state lives under `work/00-campaigns/`.

All lifecycle mutations use `--project-binding` from `ts: identity` plus the fresh project-bound
state token. Read-only status and validation do not require a mutation binding.

| Prompt | Usage |
| --- | --- |
| `ts: status` | Show and validate the active owner capsule and shared Cycle State Capsule, including any pending or active Dangler Resolution campaign. |
| `ts: queue` | Alias for `ts: status`. |
| `ts: completed` | Summarize recent verified campaign completions. |
| `ts: next` | Resume the working campaign or select the first ready campaign; when none is ready, report the owning higher-level cycle and exact safe transition. |
| `ts: next 1,2` | Execute an ordered batch from mutable queue positions in one fresh snapshot; this compatibility shorthand is equivalent to `que 1,2`. |
| `ts: next que 1,2` | Execute explicit queue positions sequentially after resolving all of them to stable campaign IDs. |
| `ts: next camp <number-or-id,...>` | Execute an ordered batch of exact zero-padded campaign numbers or full Campaign IDs. |
| `ts: next *` | Drain every campaign in the validated active-queue snapshot, excluding campaigns added later. |
| `ts: add <idea>` | Check active, deferred, and completed work for overlap or direction conflicts, then add the approved campaign using the current state token. |
| `ts: unblock <campaign>` | Return blocked work to queued state and clear its recorded decision; starting remains a separate transition. |
| `ts: reconcile campaigns` | Inspect queue and whole-`work/` coverage, automatically creating or refreshing one Dangler Resolution campaign as the first queued work. |
| `ts: defer <campaign>` | Move active work to deferred with a reason and reactivation condition. |
| `ts: abandon <campaign>` | Preserve cancelled or superseded work with a disposition and replacement when applicable. |

Owner-queue shorthand:

| Term | Meaning |
| --- | --- |
| `camp` | Alias for `campaign`. |
| `que N` | Alias for the campaign currently at mutable 1-based queue position N, not its parenthesized campaign number. |

Missing or out-of-range positions, duplicate resolutions, and invalid campaign references stop
before execution. Targeted
batches resume a selected working campaign first and otherwise preserve their requested order.
They run sequentially with at most one working campaign; every campaign must pass its own gate,
then Tool Shed refreshes and validates lifecycle, index, stale-path, work, and dependency state
before advancing. A failure, blocker, decision, stale state, unsatisfied dependency, protected
action, or missing authority stops at a reported resume point with completed and remaining stable
IDs. `*` is a fixed invocation snapshot, and batch selection never authorizes work5, deployment,
release, production promotion, destructive work, credentials, or other consequential actions.

Resolve `que N` from a fresh queue status immediately before acting. Missing or out-of-range
positions are errors and are never guessed. A heading such as `1. (004) Title` shows mutable queue
position 1 and stable campaign number 004. Each rendered card also shows its full stable
`Campaign ID`; use the number or full ID when a reference must survive reordering or completion.
`campaign_queue.py backfill-numbers --expect TOKEN` preserves numeric ID prefixes and assigns
zero-padded numbers to legacy slug-only campaigns in deterministic lifecycle order, atomically
renaming each request to `<number>-<campaign-id>.md` and refreshing queue links. Lifecycle commands
accept either the full Campaign ID or its exact zero-padded campaign number.

Blocked work remains active. Queue mutations reject stale state and do not silently reorder
ambiguous priorities. Campaign completion requires its explicit completion gate and applicable
verification.

Queue entries are readable cards with icon-plus-text readiness states: `WORKING`, `READY`,
`WAITING`, `BLOCKED`, or `COMPLETE`. The state comes from the same dependency/decision calculation
used by `next` and reconciliation. Projects may approve an evidence-backed catalog at
`work/focus-areas.md`; once approved, active campaigns require known `Primary Focus Areas` and may
also declare `Supporting Focus Areas`. The CLI accepts repeatable `--primary-focus-area ID` and
`--supporting-focus-area ID` options on `add`.

### Build Focus Areas From Existing Sources

```text
ts: build focus areas
```

The agent inspects enduring project evidence across source, documentation, tests, integrations,
runtime and hardware boundaries, qualification, delivery workflows, and durable work history. It
then presents an exact proposed catalog with stable IDs, boundaries, evidence paths, uncertainty,
coverage gaps, and proposed assignments for every active campaign.

This first stage is read-only. The command does not silently create or approve
`work/focus-areas.md`, and an existing approved catalog keeps its stable IDs and accepted
boundaries unless the proposal names evidence for a change. After the owner explicitly approves
the exact catalog and assignment set, the agent writes the approved catalog, applies the active
campaign assignments, refreshes indexes, and validates campaign state, stale paths, and work state.

The deterministic reconciliation utility automatically creates or refreshes one Dangler
Resolution campaign when unclassified unresolved artifacts exist. It places that campaign first
among queued work while preserving any currently working campaign. It also reports complete scan
and exclusion totals; explicit `Campaign: <id>`, `Campaign: standalone`, and `Campaign: excluded`
associations; unresolved artifact clusters; lifecycle mismatches; and queue projection drift:

```bash
python3 tool_shed/scripts/reconcile_campaign_queue.py --workspace . --json
```

Use `--dry-run` to inspect and save the exact proposed manifest without changing the workspace:

```bash
python3 tool_shed/scripts/reconcile_campaign_queue.py --workspace . --dry-run --json \
  | jq '.reconciliation_manifest' > /tmp/campaign-reconciliation.json
```

Automatic mutation always includes creating or refreshing Dangler Resolution. For other
`reconciliation_manifest` operations, save the exact current manifest and pass `--apply --expect
TOKEN --manifest PATH` after authority-envelope evaluation. The token covers the complete scanned
work surface; unambiguous reversible operations may continue automatically when covered.
Generated projection repairs preserve the current valid relative order and never apply the
separately reported execution-order proposal. Authorized manifest operations can create campaigns,
set explicit associations or focus areas, or transition campaigns; terminal transitions preserve
lifecycle history instead of deleting files. `migrate-preview` can suggest exact
`set_focus_areas` operations for fully matched legacy `Focus areas: ...` outcome prose, but it
never rewrites that prose itself. Ambiguous semantic, catalog-approval, or priority choices remain
owner-owned.

```bash
python3 tool_shed/scripts/reconcile_campaign_queue.py --workspace . \
  --apply --expect <whole-work-token> --manifest /tmp/campaign-reconciliation.json --json
```

## Program Roadmaps

Use this optional lifecycle when a project map needs explicit state-token-guarded phases,
milestones, gates, and rolling-wave campaign planning:

| Prompt | Usage |
| --- | --- |
| `ts: prm <outcome>` | Carry an outcome through the full Plan → Roadmap → Milestone lifecycle, continuing every covered transition until applicable gates pass or genuine owner intervention is required. This does not grant release beyond the endpoint or bypass protected-target authority. |
| `ts: prm idea <idea-id-or-path>` | Carry one selected Idea Brief into PRM, preserving visible unknowns and promoting the brief after settled project-map direction captures it. Later actions remain bounded by the same authority envelope. |
| `ts: develop roadmap` | Read and classify project evidence. Greenfield projects establish initial map direction first. No writes. |
| `ts: propose roadmap` | Capture an exact proposed roadmap revision from a fresh source-state token. Creates no campaigns. |
| `ts: approve roadmap <token>` | Manual level-0 compatibility route for one unchanged proposal; covered faithful proposals are accepted automatically with internal tokens. |
| `ts: derive campaigns for milestone <id>` | Preview an exact dependency-aware campaign manifest for one milestone. No writes. |
| `ts: approve campaign plan <token>` | Manual level-0 compatibility route for one exact manifest; at level 3, covered plans materialize automatically and continue into execution when the endpoint authorizes it. |
| `ts: roadmap status` | Compute milestone and gate progress from linked campaign evidence. No writes. |
| `ts: review roadmap` | Report assumptions, source drift, blockers, and revision needs. No writes. |
| `ts: overview` | Show whole-project strategic and execution state together. No writes. |

The deterministic CLI is:

```bash
python3 tool_shed/scripts/program_roadmap.py --workspace . develop --roadmap-id <id> --json
python3 tool_shed/scripts/program_roadmap.py --workspace . propose --manifest proposal.json --expect <source-token>
python3 tool_shed/scripts/program_roadmap.py --workspace . approve <id> --revision <n> --expect <source-token> --proposal-token <token>
python3 tool_shed/scripts/program_roadmap.py --workspace . derive <id> --milestone M1 --json
python3 tool_shed/scripts/program_roadmap.py --workspace . apply-campaign-plan --manifest campaign-plan.json --expect <manifest-token>
python3 tool_shed/scripts/program_roadmap.py --workspace . overview --json
```

Roadmap and campaign-plan mutations retain separate exact tokens, but those are state-consistency
controls rather than universal human approval gates. Every mutation rejects stale source, roadmap,
or queue state. Existing standalone maps and queues remain supported. When an
operator explicitly persists an exact derived plan under `work/roadmaps/campaign-plans/*.json`,
the shared Cycle State Capsule recognizes it only while its roadmap, queue, and manifest token
remain current; otherwise it reports derivation rather than inventing pending authority.

## Q&A Inbox

```text
ts:ask
```

Read actionable content from canonical `work/01-q&a/ask.txt`, using legacy
`work/q&a/ask.txt` only as a pre-migration fallback. The agent does not merge conflicting inboxes
or move, clear, rewrite, or delete inbox content without explicit authorization. Inbox transport
does not change the request's natural coordination level.

## Version And Update Status

| Prompt | Usage |
| --- | --- |
| `ts: doctor` | Audit the complete supported workspace surface read-only and return one health verdict with exact next actions. Use `--json` for stable automation output or `--strict` to fail unless fully healthy. |
| `ts: doctor --repair` | Regenerate stale deterministic work indexes only after campaign source validates and exact current doctor state and project-binding tokens are supplied. It never chooses semantic truth or changes campaign lifecycle state. |
| `ts: fulltsupgrade` | Upgrade the current existing Tool Shed installation end-to-end from the latest verified published GitHub release, including guarded backup/update, provider convergence, attested focused client validation with fail-closed full-validation fallback, installed Codex skill synchronization when applicable, exact verification, and rollback. |
| `ts: upgrade report [latest\|<transaction-id>]` | Render one protected local snapshot-upgrade transaction as sanitized maintainer-ready Markdown without publishing it. Use `--json` for structured output. |
| `ts: version` | Verify the local Tool Shed snapshot and report its version without network access. |
| `ts: check for updates` | Verify locally, compare with the canonical manifest, and report the version relation. Read-only. |
| `ts: update status` | Alias for `ts: check for updates`. Read-only. |

An update-status check does not authorize replacement. Ask explicitly to install or update Tool
Shed when mutation is intended.

The equivalent shell command is:

```bash
python3 tool_shed/scripts/doctor.py --workspace .
python3 tool_shed/scripts/doctor.py --workspace . --json --strict
```

`doctor` distinguishes internal consistency from external/runtime truth. Findings use `error`,
`warning`, `owner-decision-required`, and `external-evidence-required`; compact counts and samples
avoid raw generated-evidence diffs. A repair requires the report's exact `state_token` and the
binding returned by `project_identity.py identity --operation doctor-repair`.

`ts: fulltsupgrade` is the concise full-authorization exception for the current installation. It
does not authorize publishing a release, rewriting history, forcing over modified or unmanaged
state, deleting unknown recovery material, or updating other workspaces or fleet targets.

`ts: upgrade report` reads the protected user-local transaction registry created by the snapshot
updater. It accepts `latest` or one exact transaction ID, validates that the record belongs to the
current platform and matches its stable `TSU-*` issue code, and emits only allowlisted release,
updater, stage-duration, validation/cache, error-class, and rollback fields. It never files an
issue. Review the draft before separately authorizing `gh issue create`.

## Codex Reasoning Maintenance

These optional routes apply only to Codex:

| Prompt | Usage |
| --- | --- |
| `ts: refresh reasoning catalog` | Refresh the account-aware local model/effort catalog. |
| `ts: reasoning status` | Inspect the local catalog without network access. |
| `ts: recommend reasoning <task>` | Refresh the catalog and recommend a concrete advertised model/effort pair for the task. |

Ordinary Tool Shed requests do not refresh or require this catalog.

## Codex App Server Persistent Preference

The repository default remains GUI. Turn on a protected user-local preference once to make eligible
unflagged commands prefer App Server, use `--gui` for one GUI action, or use `--app-server` for a
strict one-command App Server request:

| Prompt | Selected execution |
| --- | --- |
| `ts: plan <request> --app-server` | App Server planning with `gpt-5.6-sol` / `high` |
| `ts: verify <request> --app-server` | App Server verification with `gpt-5.6-terra` / `low` |
| `ts: camp run <camp> --app-server` | Existing bounded App Server CAMP path with `gpt-5.6-terra` / `medium` |
| `ts: next --app-server` | Invoke one deterministic dispatcher that reuses normal `next` selection, preflights CAMP before planning, automatically prepares an unprepared ready campaign with at most 64,000 bytes of inline context through read-only App Server planning, and continues to the existing Terra/medium CAMP path; never launch a nested Codex agent. |
| `ts: app-server on` | Persistently prefer App Server for eligible commands. `appserver` is an alias. |
| `ts: app-server off` | Restore the normal GUI default. |
| `ts: app-server status` | Read-only preference, compatibility, and qualified-role status. |

With the preference off, unflagged `ts: plan`, `ts: verify`, `ts: camp run`, and executable `ts:
next` use the GUI and report `Execution: GUI`. With it on, those routes prefer App Server; `--gui`
overrides it once without changing stored state. For planning and verification, the selector accepts exact reviewed records or an
unseen Codex version whose numeric release core is at least `0.146.0`. An unseen eligible executable
runs the bounded dirty read qualification in the same invocation; a passing result continues the
original request without updating the repository registry. A sanitized user-local cache reuses a
result only when the executable hash, Codex version, protocol fingerprint, qualification policy,
model policy, and platform still match. Successes expire normally; reviewed unsafe denials persist
until a relevant fingerprint changes or `--requalify` is supplied on the explicit App Server
request. Transient authentication, network, service, and model-catalog failures are not cached.
Prereleases use their numeric release core, and there is no upper cutoff. Versions below the floor
and fatal or unknown qualification results are blocked with a clear GUI fallback. CAMP execution still requires an exact reviewed
workspace-write record and separate write harness. There is no API fallback.

`next` is not a new App Server role. The flagged and unflagged forms select the same next action.
When execution resolves to App Server, the GUI immediately runs
`python3 <shed>/scripts/app_server_dispatch.py --workspace . next --json` once, adding
`--app-server` only for an explicit strict request; it does
not wrap that command in `codex exec` or another agent. Executable CAMP work uses a strict
campaign-local JSON execution capsule with the matching campaign/CAMP IDs, prompt, relative path
allowlists, focused context, and shell-free verification argv. If that capsule is absent, the same
invocation assembles a deterministic focused snapshot from the campaign, project instructions, Git
state, relevant file inventory, and bounded source excerpts. Read-only App Server planning receives
only that isolated snapshot, without tools, and returns strict structured preparation. The
dispatcher preflights CAMP before the planning turn, validates the returned context against the
smaller of 64,000 bytes and the configured inline limit, and persists it through the
guarded campaign transaction before continuing to the existing `camp-run` safety path. Unsafe,
ambiguous, invalid, or over-budget preparation stops before mutation. Existing valid capsules skip
planning. Discussion, decisions, blocked work, external gates, and unsupported roles remain on
their ordinary route. Explicit `--app-server` remains strict. A persisted selection that cannot
qualify reports a compact category and continues the same action immediately in GUI. Pre-mutation
failures switch directly; possible mutations require GUI reconciliation from the existing journal
and Git state, never replay.

The CAMP worker reports `step_ready_for_verification` or `camp_ready_for_verification` after bounded
implementation. App Server `turn/completed` is only a terminal protocol event. The controller runs
each reserved deterministic command exactly once, then records `safe_unverified`,
`verification_failed`, or `verified` from the Git boundary and check results. Unknown or invalid
outcomes remain fail-closed, with no retry after mutation; focused-context budget findings prevent
lifecycle advance.

`ts: discuss` is always GUI-native. `ts: discuss ... --app-server` is rejected instead of silently
changing execution surfaces.

`ts: app-server on|off` stores only a schema-versioned mode and timestamp in
`$CODEX_HOME/tool-shed/app-server-preference.json` (or the equivalent `~/.codex` path), outside
repositories and installed Tool Shed snapshots. Writes are locked, atomic, and private where the
platform supports modes. Missing or invalid state fails safely to off. The committed global setting
remains `codex_app_server_enabled = false`.

Passive attempts, successes, fallbacks, and reconciliation handoffs append sanitized operational
events to `$CODEX_HOME/tool-shed/app-server-events.jsonl`. Events exclude prompts, responses, raw
tool output, credentials, secrets, exception text, and repository content. Logging is best-effort
and never delays or blocks GUI fallback.

Every App Server path uses one bounded Codex resolver. A supported explicit override is
authoritative. Otherwise it inventories `PATH`, trusted platform locations, and OpenAI VS Code
extension bundles, then selects the highest semantically eligible version at or above `0.146.0`;
source priority resolves only equal-version ties. Status reports the full inventory and only roles
usable by the selected executable. Status and selection distinguish `exact-qualified`,
`dirty-qualifying`, `dirty-qualified`, `transient-fallback`, `unsafe-blocked`, `below-minimum`, and
`write-not-qualified`. Status, selection,
smoke, startup, version detection, qualification, reasoning refresh, and install/upgrade readiness
share that result. Discovery alone does not qualify a version; eligible unseen read-only requests
must pass the live dirty harness. Tool Shed never installs Codex, changes
permanent `PATH`, searches arbitrary locations, persists a user path, or falls back to an API.
When Codex is unavailable, normal unflagged GUI use remains available.

Linux bundle discovery is limited to the user's desktop, Insiders, remote-server, and
remote-server Insiders VS Code extension roots and the x86_64, aarch64, and arm64 payloads.

Automated regression coverage does not satisfy the Windows GUI release gate. Required external
evidence is a fresh normally launched Codex GUI session with `Get-Command codex` still not found
and no `PATH` preparation, where status discovers the trusted VS Code bundle and GUI-triggered
App Server execution, smoke, startup, version detection, and qualification use the same path.

## Artifact And Workspace Requests

Artifact operations use natural language after `ts:` rather than a rigid subcommand parser. Common
request forms are:

```text
ts: orient me
ts: choose the smallest artifact for this: <need>
ts: create a checklist for <goal>
ts: create a ticket for <behavior change>
ts: plan <multi-step outcome>
ts: map the active workstreams
ts: create a time-boxed spike for <unknown>
ts: record <decision> as an ADR
ts: create a rollback runbook
ts: review work state
ts: complete work/wp/active/<workpackage>.md
ts: onboard this existing project
ts: install Tool Shed in this workspace
ts: update Tool Shed in this workspace
```

The agent chooses the smallest sufficient artifact: checklist for bounded known steps, ticket for
a specific behavior change, project map for multiple workstreams, workpackage for a multi-step
transformation, ADR for a durable decision, runbook for a repeatable operation, incident for
break/fix learning, spike for bounded uncertainty, inventory for classification, and decision
matrix for visible tradeoffs.

## Related Shell Utilities

The AI routes normally operate these deterministic scripts from the workspace-local Tool Shed:

```text
scripts/campaign_queue.py
scripts/app_server_control.py
scripts/app_server_dispatch.py
scripts/check_work_tree.py
scripts/doctor.py
scripts/check_shed_version.py
scripts/check_stale_paths.py
scripts/complete_workpackage.py
scripts/install_into_workspace.py
scripts/new_artifact.py
scripts/project_identity.py
scripts/program_roadmap.py
scripts/read_ask_inbox.py
scripts/reconcile_campaign_queue.py
scripts/review_work_state.py
scripts/update_snapshot.py
scripts/update_work_index.py
scripts/workspace_preflight.py
```

Run `python3 <script> --help` for the exact shell interface. The scripts are the automation layer;
the `ts:` prompts are the operator-facing AI interface.
