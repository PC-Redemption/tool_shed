# Tool Shed Operator Guide

Tool Shed helps a human and AI agent preserve project coordination in plain Markdown. The
workspace-local `tool_shed/` directory supplies reusable rules, templates, and scripts; the
project's tracked `work/` directory holds its planning artifacts.

## Getting Help

Type:

```text
ts: help
```

The active agent should read this guide and return a concise menu of relevant use cases with example prompts.
Help is read-only: it must not create or change artifacts unless the same request explicitly asks
for a change.

Every help response also shows this public navigation link while retaining the local response:

> Browse Tool Shed help: https://ts.rookaro.com/

The link is supplemental. Rendering help never checks the network, and the workspace-local guide
remains sufficient when offline.

For the complete prompt inventory rather than a focused menu, type:

```text
ts: commands
ts: help all
```

Both routes read the [AI command reference](commands.md) and may also show:

> Browse the complete command reference: https://ts.rookaro.com/ref/

Use `ts: help <topic-or-command>` for a focused explanation and examples. A focused response may
add a stable public topic URL when one exists, but it always retains the root help link.

Ask for focused help with:

```text
ts: help spikes
ts: help existing projects
ts: help completing work
ts: help install
ts: help update
ts: help version
ts: help providers
```

## Discuss A Campaign Before Planning

Use discussion when an idea is still forming:

```text
discussion: should Tool Shed support another AI provider?
ts: discuss how to reduce campaign token cost
```

`ts: discuss` is the authoritative Tool Shed discovery route. `discussion:` is an informal
read-only entry signal. The agent explores the outcome, motivation, constraints, assumptions,
unknowns, and credible options, then recommends the smallest useful next route. It does not create
or modify an artifact unless the same request explicitly asks to capture or plan.

## Choose The Minimum Coordination Level

- Direct: clear, reversible, single-step work; no artifact.
- Guided: bounded known steps; checklist or ticket.
- Coordinated: dependencies, branching, multi-session work, or handoff; workpackage or map.
- Deep: consequential cross-layer uncertainty or repeated failure; bounded research and controlled
  evidence.

Start at the lowest adequate level, load only the route-specific instructions needed, and escalate
only when evidence shows additional risk or coordination cost.

Direct is the default for a clear, reversible bug fix or enhancement in one repository, including
requests dispatched through `ts:ask`. The agent resolves the named target once, makes the focused
change, and runs focused tests. It does not create planning artifacts, branches, PRs, releases,
deployments, evidence artifacts, or new worktrees unless you requested them, repository policy
requires them, or concrete risk, conflicting evidence, or an observed failure justifies expansion.
Campaign continuity keeps the request moving without upgrading its coordination level.

An optional `Coordination: direct` or `Route: direct` line makes the intended level explicit:

```text
Coordination: direct
In the current Django repository, replace the dashboard's 30-second reload with read-only SSE.
Run the focused dashboard tests.
```

Contrast that with a coordinated qualification campaign:

```text
Qualify and release the firmware update across the supported hardware matrix, preserve evidence,
document rollback, and hand the result to operations.
```

The second request has cross-target sequencing, evidence, release, rollback, and handoff cost, so a
workpackage and staged verification are appropriate.

## Use Another AI Provider

Tool Shed supports native instruction adapters for Codex, Claude Code, Gemini CLI, GitHub Copilot,
and Cursor:

```bash
python3 tool_shed/scripts/install_into_workspace.py . --provider <provider-id>
```

Repeat the option or use `--provider all`. Compatibility is expressed as a provider surface plus
capability level; a static planning adapter does not imply that every surface can deploy or verify.
See [provider adapters](provider-adapters.md).

## Bind The Workspace Before Mutation

Each installed project owns a tracked `work/tool-shed-project.json` UUID and name. At the first
mutation in a provider session, run `ts: identity` or the underlying read-only command for the
intended operation:

```bash
python3 tool_shed/scripts/project_identity.py --workspace . identity \
  --operation campaign-queue --json
```

Surface the project name, ID, resolved root, repository fingerprint, active campaign or operation,
and session binding. Pass the operation-specific binding as `--project-binding`, and obtain state
tokens only from the same target. Tokens incorporate both project ID and resolved root, so another
project—or a clone at another root—cannot reuse them even when its state is byte-identical.

An absolute path outside the bound root is `WORKSPACE_MISMATCH`. Reading or mentioning it does not
switch projects. Use `ts: use <project-alias-or-path>` to verify a switch explicitly, then reload
that target's instructions and Tool Shed skill and obtain fresh target-bound state. Generic editor
and shell operations obey the same boundary.

## Diagnose Workspace Health

Use one read-only command when individual validators may agree with their own source while the
workspace remains contradictory:

```text
ts: doctor
```

The underlying command audits the resolved workspace and Git root, installed snapshot integrity,
repository preflight, branch/HEAD and relevant dirty state, canonical work topology, campaign
lifecycle and queue projections, generated index freshness, stale paths, work-state drift, and
whole-work reconciliation:

```bash
python3 tool_shed/scripts/doctor.py --workspace .
python3 tool_shed/scripts/doctor.py --workspace . --json --strict
```

The verdict is `HEALTHY`, `DEGRADED`, `NEEDS_DECISION`, or `INVALID`. Strict mode exits nonzero
unless the result is fully healthy. The report verifies internal consistency only: external or
runtime claims need a referenced, sanitized durable workspace evidence record and may need fresh
observation when currency matters.

Repair is deliberately narrow. `ts: doctor --repair` can regenerate stale deterministic work
indexes only after campaign source validates and exact doctor state/project-binding tokens are
provided. It never changes campaign lifecycle state, selects semantic truth, rewrites owner
artifacts, fabricates evidence, or applies reconciliation without its separate approved manifest.

To fully upgrade an existing Tool Shed installation with one short command, type:

```text
ts: fulltsupgrade
```

This authorizes the complete current-installation upgrade from the latest verified published
GitHub release: guarded backup/update, provider convergence, attested focused client validation
with fail-closed full-validation fallback, installed Codex skill
synchronization when applicable, exact verification, and rollback. It does not authorize release
publication, history rewriting, unsafe overwrite, deletion of unknown recovery material, or
changes to other workspaces or fleet targets.

## Choose An Execution Endpoint

Use the same five levels in every workspace:

| Route | Stop after |
| --- | --- |
| `ts:work1 <goal>` | A minimally checked local checkpoint commit; no deployment. |
| `ts:work2 <goal>` | Deployment to the configured work environment plus focused browser and changed-behavior checks. |
| `ts:work3 [scope]` | Documentation aligned with the accumulated coded work through scoped create, read, update, or delete operations, followed by full applicable validation/build and a locally frozen candidate. |
| `ts:work4 [scope]` | The frozen source is pushed without intentional production promotion. |
| `ts:work5 [scope]` | Production is released or promoted and verified. |

The levels are cumulative and do not change Direct, Guided, Coordinated, or Deep coordination.
Use `ts:work` as an alias for `work2`, `ts:freeze` for `work3`, `ts:push` for `work4`, and
`ts:ship` for `work5`. Use `ts:check <spot|focused|full|release>` when validation is wanted without
implementation, commits, pushes, deployment, or release.

At Work3, review the accumulated coded work and create, read, update, or delete project
documentation as needed so it matches the candidate. Keep those changes within the requested
scope: preserve unrelated owner documentation and historical records, and delete documentation
only when the coded change makes it obsolete.

The optional tracked file `work/tool-shed.yaml` declares how remote work maps to environments:

```yaml
schema_version: 1
work_model: combined
```

In `combined` mode, development and production share the configured target, so `work2` and
`work3` may change the live site. In `split` mode, those levels deploy only to development and
`work5` promotes the frozen candidate to production. Optional `development_target` and
`production_target` names are needed only when existing project docs and tooling do not already
resolve them.

The file does not hold credentials, create infrastructure, or grant deployment authority. If it
is absent, Tool Shed uses existing workspace evidence and asks one concise target question only
when safe routing is genuinely ambiguous. It rejects invalid schemas or modes. When a normal push
automatically deploys production, `work4` stops before that push unless production release is
explicitly authorized.

An individual workspace may also add actions around one canonical endpoint:

```yaml
schema_version: 1
work_model: split
work_levels:
  work3:
    before:
      - Run the candidate-data refresh script
    run_default: true
    after:
      - Generate the project handoff summary
  work4:
    before:
      - Run the controlled publication flow
    run_default: false
```

Before a numbered route runs, Tool Shed resolves the declaration with
`tool_shed/scripts/work_level_config.py`. It applies the selected canonical level's `before`
actions, the standard cumulative behavior unless explicitly disabled, then its `after` actions.
Aliases share that envelope and lower-level envelopes do not repeat. Actions stop on first failure,
and default suppression is reported before execution. Missing configuration preserves the standard
behavior. See [workspace work-level customization](work-level-customization.md) for the complete
schema, ordering, validation, safety, installation, and upgrade contract.

## Ship End to End

Use the ship route when the intended outcome is a delivered, verified change rather than a plan or
an intermediate implementation:

```text
ts:ship <goal>
```

`ts:ship` means: plan, implement, validate, build, deploy, and verify the requested workspace goal
end-to-end. A delivery-capable agent continues through every applicable stage, uses the project's own delivery
tooling, and verifies the result in the target environment before declaring completion.

A lifecycle stage is applicable only when the requested outcome includes it, repository policy
mandates it, or concrete risk or an observed failure justifies it. Merely mentioning, documenting,
or discussing `ts:ship` is not an end-to-end delivery request. When verification expands beyond
focused tests, the agent states the concrete reason.

The route authorizes the normal workspace changes and deployment actions needed for the stated
goal, but it does not override safety rules, protected-environment controls, required approvals,
or credential and authorization boundaries. The agent explains any inapplicable stage. If it cannot
safely deploy, it completes every safe preceding stage and reports the exact blocker.

The agent does not request repeated confirmation for reversible, in-scope steps that the operator
has already clearly authorized. One request may authorize multiple named operations. It asks
again only when an action materially expands scope, targets a protected environment, is destructive
or irreversible, uses an unknown deployment target, publishes externally, or otherwise requires
new authority.

For nontrivial work, the agent keeps the requested outcome and current limiting condition visible. It
compares the actual result with the expected state after material actions and updates the next
action when evidence changes the situation. A command completing successfully is not enough if the
target state is still wrong. This loop preserves the original authority boundary and is skipped as
explicit ceremony for simple answers and known single-step reversible work.

Before an already-authorized consequential stage, the agent checks at most three credible failure
modes and adds proportionate prevention, detection, verification, or rollback. Routine reversible
work does not receive a generic failure-analysis ritual.

## Campaign Status And Continuity

Tool Shed treats the requested outcome in the current chat as the campaign. A plan, checklist,
workpackage, test, build, or deployment may be part of that campaign, but finishing one does not
necessarily finish the requested outcome.

The agent keeps going when the next action is reversible, in scope, and already authorized. Progress
updates and useful inspection points do not become approval gates merely because the operator
might want to review them. Review pauses are reserved for explicitly requested review, material
unresolved decisions, evidence that contradicts the plan, new authority, or protected,
destructive, irreversible, or not-yet-authorized external actions.

Continuity preserves the selected coordination level. It does not upgrade Direct work to Guided,
Coordinated, or Deep or make an otherwise inapplicable lifecycle stage apply.

Every final response for a Tool Shed campaign ends with one explicit verdict:

- `Campaign status: COMPLETE` means the whole requested outcome and applicable verification are
  finished.
- `Campaign status: CONTINUE` means work remains, no operator decision is needed, and the response
  names the next concrete action. The agent does not use this verdict to stop when it can safely perform
  that action in the current turn.
- `Campaign status: BLOCKED` identifies the exact decision, dependency, permission, credential,
  external-state change, or required review preventing progress and the precise operator action.

When review is genuinely required, the agent points to the exact file or result and relevant section,
states the exact question or approval, and explains what resumes afterward. A vague request to
"review this" or "let me know" is not a valid handoff.

## Follow The Nested Cycles

The Tool Shed workflow is the operator path from intent through direction, execution, evidence,
and review. Tool Shed uses five nested control cycles underneath that workflow to decide what
repeats, what counts as complete, and where control returns:

```text
Program Cycle
└─ Milestone Wave Cycle
   └─ Queue Cycle
      └─ Campaign Cycle
         └─ Evidence Loop
```

- The Evidence Loop observes, acts, verifies, and adapts until reality matches expectation or a
  real blocker is proven; control returns to the current campaign.
- The Campaign Cycle starts, executes, verifies its completion gate, and completes or blocks;
  control returns to the queue.
- The Queue Cycle selects and runs ready campaigns until none remains; an empty queue returns
  control upward and never proves the milestone or program complete.
- The Milestone Wave Cycle derives a plan, obtains exact approval, materializes campaigns, runs
  the queue, and evaluates its gate; control returns to the Program Cycle.
- The Program Cycle executes approved milestone waves, reviews drift, and revises only through
  exact proposal/approval; it ends when the intended outcome and every applicable gate complete.

Work origin is separate: `direct` has no queue record, `owner-originated` was deliberately added,
`roadmap-derived` carries Roadmap/Revision/Milestone/Gate traceability, and `detour` carries
`Detour For` or `Return To`. Origin does not choose coordination or execution: roadmap-derived
work may remain Direct and stop at work1. Likewise Direct, Guided, Coordinated, or Deep describes
structure; work1–work5 describes the endpoint; cycle state says which loop owns the next move.

`ts: overview`, `ts: status`, and `ts: next` render one shared Cycle State Capsule in human and
JSON output. With no ready campaign, it checks Dangler Resolution, a persisted exact campaign plan
awaiting approval, incomplete milestone/gate state, a derivable milestone, roadmap drift, completed
program state, then the absence of any higher-level driver. The reported transition is guidance,
not authority: plan approval, materialization, lifecycle, protected-environment, and release
boundaries stay unchanged.

## Owner Campaign Queue

Tool Shed places durable owner-facing execution state in the first-sorted
`work/00-campaigns/` folder. This is separate from the transient Q&A inbox.

| Route | Result |
| --- | --- |
| `ts: status` or `ts: queue` | Show last completed, working now, next, blockers, detours, lifecycle findings, and pending Dangler Resolution work. |
| `ts: next` | Resume or execute one campaign using the existing safe readiness behavior. |
| `ts: next 1,2` or `ts: next que 1,2` | Resolve selected queue positions once, then execute that stable ordered batch sequentially. |
| `ts: next camp <number-or-id,...>` | Execute exact stable campaign references in the requested order. |
| `ts: next *` | Drain the validated active-queue snapshot without including campaigns added later. |
| `ts: add <idea>` | Check overlap, dependencies, and direction conflicts before inserting an approved campaign. |
| `ts: unblock <campaign>` | Return blocked work to queued state and clear the blocker decision without starting it. |
| `ts: reconcile campaigns` | Inspect queue and whole-`work/` coverage, automatically creating or refreshing Dangler Resolution as the first queued work. |
| `ts: defer <campaign>` | Move an active campaign with a reason and reactivation condition. |
| `ts: abandon <campaign>` | Preserve a cancelled or superseded campaign with its disposition. |
| `ts: completed` | Show recent verified outcomes newest-first. |

In owner-queue requests, `camp` is an alias for `campaign`, and `que N` identifies the campaign at
the current mutable 1-based queue position. A card heading such as `1. (004) Title` distinguishes
queue position 1 from stable campaign number 004; the card also displays its full stable
`Campaign ID`. Use the campaign number or full ID for durable references across insertions,
reordering, or completion. Tool Shed resolves `que N` from a fresh status read immediately before
acting and rejects missing or out-of-range positions rather than guessing. Numeric prefixes in
existing IDs remain authoritative; every request filename uses `<number>-<campaign-id>.md`, and
guarded `backfill-numbers` atomically renames legacy slug-only histories and refreshes projections.
Lifecycle commands accept the full Campaign ID or exact zero-padded campaign number.

Targeted `next` batches resolve every target before starting, resume a selected working campaign
first, and keep at most one campaign working. Each target retains its own completion gate,
coordination, and work level. After a successful transition, Tool Shed refreshes and validates the
queue, indexes, stale paths, work state, and dependency readiness. It stops at the first failure,
blocker, decision, stale state, dependency, protected action, or missing authority and reports the
completed IDs, remaining IDs, and exact resume point. Selecting a batch never grants deployment,
release, production, destructive, credential, or other consequential authority.
Snapshot upgrades perform the same guarded convergence automatically after reporting the detected
mismatch. The selected release backs up the complete campaign tree as a declared mutation surface;
owner extensions are preserved, indexes are regenerated, and any later failure restores the
pre-upgrade tree.

The active queue is the canonical execution order. Detailed requests live in lifecycle folders:

```text
work/00-campaigns/
├── active-queue.md
├── completed-queue.md
├── active/
├── completed/
├── deferred/
└── abandoned/
```

Every mutation uses the current operation-specific project binding and state token returned by that
same target's `status`; stale, foreign-project, and root-mismatched tokens are rejected.
Completion requires the request's explicit completion gate and applicable verification, then moves
the request and updates both queue views through a recoverable operation. Blocked work stays
active. Deferral and abandonment require explicit lifecycle reasons.

Active queue entries render as cards with icon-plus-text readiness states: `WORKING`, `READY`,
`WAITING`, `BLOCKED`, or `COMPLETE`. `next`, status, queue rendering, and reconciliation all use the
same dependency-and-decision calculation, so the visual state cannot silently disagree with
selection. Dependency rows show each prerequisite's current state.

Projects can keep an evidence-backed focus catalog at `work/focus-areas.md`. Existing repositories
remain valid without one. Onboarding creates a proposed catalog, and owner approval changes it to
`Status: approved`; Tool Shed never invents or approves a generic taxonomy. Once approved, every
ordinary active campaign must name at least one known `Primary Focus Areas` ID and may name
`Supporting Focus Areas`. Queue cards display the catalog names.

To derive or refresh the catalog from the project that actually exists, run:

```text
ts: build focus areas
```

The agent inspects source modules and build targets, architecture and README documentation, tests
and fixtures, integrations, runtime/service/hardware boundaries, qualification and delivery
workflows, and durable work history. It avoids raw generated evidence, dependencies, caches, and
build output unless a concise versioned summary is the only durable evidence.

The first response is an exact, read-only proposal: stable IDs, names, purpose, inclusions,
exclusions, evidence paths, uncertainty, coverage gaps, and primary/supporting assignments for all
active campaigns. Review that proposal explicitly. The discovery request alone does not authorize
a write. After approval, the agent writes the approved catalog and assignments, refreshes indexes,
and validates campaign state, stale paths, and work state. Existing stable IDs and accepted
boundaries remain unchanged unless the proposal cites evidence and names the change.

Refresh the catalog when an enduring responsibility boundary changes: a new or retired product,
service, repository, external application, hardware/runtime boundary, qualification regime,
release/regulatory/supply workflow, or a repeated campaign that does not fit the approved areas.
Return edits to `Status: proposed`, record new evidence and uncertainty, and require owner approval
before the revised catalog governs assignments.

`reconcile_campaign_queue.py` automatically creates or refreshes one Dangler Resolution campaign
for unclassified unresolved artifacts and places it first among queued work without interrupting a
working campaign. `--dry-run` preserves read-only inspection. The report separates mechanically
repairable projection drift from whole-`work/` coverage findings, stalled lifecycle decisions, and
a proposed execution order. Unresolved artifacts declare `Campaign: <id>`, `Campaign: standalone`,
or `Campaign: excluded`; the latter two require `Campaign Reason`. All other writes require an
exact approved JSON manifest plus `--apply --expect TOKEN --manifest PATH`. Reprioritization and
ambiguous semantic decisions remain owner-controlled, and terminal manifest operations preserve
completed, deferred, or abandoned history.

Use `python3 tool_shed/scripts/campaign_queue.py --workspace . migrate-preview --json` to inspect
Markdown requests under `work/01-q&a/` or legacy `work/q&a/`, actionable inbox lines, and legacy
campaign outcome clauses such as `Focus areas: Firmware, Qualification`. Preview never writes.
When every legacy name matches an approved catalog, it returns a suggested exact manifest using
`set_focus_areas`; unresolved or ambiguous names remain owner decisions. Installation never
converts requests, rewrites campaign prose, or clears the canonical inbox. Applying a campaign or
focus-area migration requires a separately approved exact manifest. The filesystem migration of
legacy Q&A folders is a distinct installer operation described below.

## Turn A Project Map Into A Program Roadmap

Use a Program Roadmap only when the project spans multiple dependent milestones or evidence gates.
It is an opt-in layer; standalone maps and campaign queues remain valid.

1. Run `ts: develop roadmap`. The read-only report classifies populated work as completed, active,
   remaining, superseded, excluded, or uncertain. For a greenfield project, approve the initial
   project map with its exact map token first.
2. Run `ts: propose roadmap` to capture an exact revision under `work/roadmaps/`. Confirm its
   phases, stable milestone/gate IDs, decisions, dependencies, authority boundaries, and candidate
   campaigns. This does not create campaigns.
3. Run `ts: approve roadmap <token>` only for the exact unchanged proposal and source state.
4. Run `ts: derive campaigns for milestone M1` to preview one rolling-wave campaign manifest.
5. Run `ts: approve campaign plan <token>` to materialize exactly that manifest. The campaigns are
   queued with roadmap traceability but are not started.
6. Use `ts: roadmap status`, `ts: review roadmap`, and `ts: overview` for computed evidence rollup
   and drift. Contradictory evidence leads to a proposed revision; approved intent is never silently
   rewritten.

Installation and upgrade preserve every owner-authored artifact and create only the empty roadmap
topology. They do not perform roadmap ingestion or approval.

## Q&A Inbox

The installer creates a workspace-local scratch inbox at `work/01-q&a/ask.txt`. Put a question or
direction there while the agent is busy, then type:

```text
ts:ask
```

The agent inspects the canonical file and `work/q&a/ask.txt`, which is supported only as a
pre-migration misplaced fallback. Blank lines and lines beginning with `#` are ignored in both
files. If only the canonical file is actionable, the agent uses it. If only the fallback is
actionable, the agent may process it but clearly identifies the noncanonical path. If both are
actionable, the agent does not merge or run either request; it reports the conflict and asks which
one to use. If neither is actionable, the agent reports that the inbox is empty.

The selected content keeps its natural coordination level. A small bug fix remains Direct; the
inbox transport does not create planning or delivery ceremony by itself.

Both files are preserved during read-only inspection. The installer separately migrates all files
from legacy `work/q&a/` and root `q&a/` into `work/01-q&a/`, verifies copied bytes, preserves
collisions under source-specific filenames, and removes the old folders. The canonical inbox is
ignored by Git because it is transient operator input, not project documentation or durable work
state.

## Common Use Cases

### Explicitly test the qualified App Server path

Normal Tool Shed work stays in the current Codex GUI. For deliberate real-world qualification,
opt into one qualified operation at a time:

```text
ts: plan <request> --app-server
ts: verify <request> --app-server
ts: camp run <camp> --app-server
ts: next --app-server
ts: appserver status
```

The execution banner identifies App Server, role, model, reasoning, and explicit opt-in. Planning
uses Sol/high, verification uses Terra/low, and CAMP execution reuses the optimized bounded
Terra/medium `camp-run` path. The same commands without the option show `Execution: GUI` and remain
in the normal GUI path.

For an App Server CAMP, `turn/completed` confirms only that the protocol turn ended. The worker
returns `step_ready_for_verification` or `camp_ready_for_verification` after its bounded edits, then
the controller runs every declared deterministic command once and verifies the Git boundary. A
safe path journal is `safe_unverified` until that handoff and verification succeed; failures become
`verification_failed`, and only the combined success becomes `verified`. Unknown, malformed,
partial, interrupted, or unexpected-path results do not advance or retry after mutation. Context
token warnings and oversized tool results likewise stop lifecycle advance with a compact finding.

`ts: next --app-server` keeps normal navigation authoritative through one deterministic command:

```text
python3 <shed>/scripts/app_server_dispatch.py --workspace . next --app-server --json
```

The GUI must run that command directly, never through `codex exec` or another agent. The dispatcher
selects exactly what unflagged `ts: next` would select and requires a strict campaign execution
capsule declaring the matching IDs, prompt, relative allowed paths, focused context, and shell-free
verification argv. It preflights Codex state, ChatGPT authentication, network/model access, and
qualification before mutation, then uses the existing Terra/medium runner. Discussion, owner
decisions, blocked work, invalid or missing capsules, external gates, and unsupported actions are
surfaced without being forced through CAMP execution. The preference applies only to that
invocation; `next` does not become an App Server role.

The selector uses exact reviewed qualification for known versions. For an unseen planning or
verification executable at or above `0.146.0`, including prereleases and versions beyond `0.150.0`,
it runs a bounded dirty read qualification and continues the same explicit request only if that
qualification passes. The dirty harness proves ChatGPT authentication, required models and
reasoning, isolated read-only turns, fail-closed approvals, unchanged disposable workspace state,
and active-turn cancellation. It negotiates the named `:read-only` permission profile when the
runtime exposes it and otherwise validates the legacy read-only sandbox. Fatal and unknown outcomes
remain blocked; safe non-fatal blockers are reported separately. Passing summaries and reviewed
unsafe denials are cached in `$CODEX_HOME/tool-shed/dirty-read-qualifications.json` (or the
equivalent `~/.codex` path), never inside canonical or installed Tool Shed trees. The cache contains
hashes and sanitized check names, not prompts, responses, credentials, secrets, or telemetry. Its
identity binds the exact binary, version, generated protocol schema or runtime-probe fingerprint,
Tool Shed qualification policy, model policy, and platform. Successes expire after the configured
TTL. Reviewed unsafe denials persist until that identity changes; add `--requalify` to the explicit
request to deliberately rerun them. Transient authentication, network, service, and model-catalog
failures are never cached, so the next explicit request retries. Status reports whether its decision
came from live evidence or the cache and explains misses and invalidation. CAMP writing never
inherits this result and still requires an exact reviewed write record. Rerun without `--app-server`
to use GUI fallback. `ts: discuss` always remains GUI-native, and `ts: discuss ... --app-server` is rejected
with an explanation.

Session-scoped `ts: appserver on|off` is not implemented: the current Codex skill surface has no
reliable skill-owned per-session state store. Those commands explain the limitation and do not
change user or repository configuration. Use the explicit option on each test command. The global
App Server default and API fallback remain off.

App Server commands use one centralized Codex resolver. A supported explicit override remains
authoritative. Without one, it inventories `PATH`, bounded trusted platform locations, and OpenAI
VS Code extension bundles, then selects the highest semantically eligible version at or above
`0.146.0`; source priority breaks only equal-version ties. It reports every candidate and the
selected path, source, App Server availability, qualification state, and actually usable roles.
Status and selection distinguish `exact-qualified`, `dirty-qualifying`, `dirty-qualified`,
`transient-fallback`, `unsafe-blocked`, `below-minimum`, and `write-not-qualified`; discovery alone
is not qualification. The same resolver serves status, selection, smoke, startup, version
detection, qualification, reasoning refresh, and install/upgrade readiness. It does not install or
copy Codex, alter permanent `PATH`, search arbitrary disk locations, persist user paths, or enable
an API fallback. If Codex is unavailable, only explicit App Server work is unavailable; normal GUI
Tool Shed work continues.

On Linux, trusted bundle discovery checks the user's `.vscode`, `.vscode-insiders`,
`.vscode-server`, and `.vscode-server-insiders` extension roots for x86_64, aarch64, and arm64
Codex payloads. This supports ordinary desktop and remote GUI launches where `codex` is absent
from the inherited `PATH`.

Automated Windows and Linux regression coverage verifies these rules but does not pass the Windows
GUI release gate. That still requires field evidence from a fresh normally launched Codex GUI with
`Get-Command codex` not found and no `PATH` preparation: `ts: appserver status` must discover the
trusted VS Code bundle, and GUI-triggered App Server execution, smoke, startup, version detection,
and qualification must identify the same executable. Treat the gate as pending until that evidence
is recorded.

### Check reasoning before substantial work

Tool Shed performs a one-time, zero-I/O reasoning preflight before substantial routed work. It uses
only the request and current-session metadata. When a usable picker pair is known, it recommends
the lowest adequate choice on its own line in this form:

### **Reasoning: <model> / <effort>**

It does not use abstract labels, claim to observe the active picker, or pause work for a reasoning
choice. If the available picker options are unknown, it continues silently instead of guessing.

The request path never refreshes catalogs. Refresh the optional account-aware diagnostic cache
after a Codex login/account change, client update, visible model-picker change, or cache expiry:

```bash
python3 tool_shed/scripts/reasoning_catalog.py refresh
python3 tool_shed/scripts/reasoning_catalog.py status
```

Equivalent requests are `ts: refresh reasoning catalog` and `ts: reasoning status`.
Use `ts: recommend reasoning <task>` when you want an explicit catalog refresh followed by a
concrete picker recommendation.

Refresh uses Codex app-server `model/list`; status is local-only. The cache preserves future model
and effort labels without treating release-time names as permanent policy. It cannot establish the
active thread setting, and stale data never blocks ordinary work.

### Orient in a project

Use this when returning to a project or deciding what deserves attention next.

```text
ts: orient me
ts: show active work and the next concrete actions
```

The agent reads project docs, `work/index.md`, active maps and artifacts, then runs the read-only
work-state review.

### Capture a small known task

Use a checklist when the steps are known and forgetting one is the main risk.

```text
ts: create the smallest artifact for validating the release
ts: make a checklist for cleaning up the root documentation
```

### Record a bug or enhancement

Use a ticket when expected behavior and acceptance criteria are clear.

```text
ts: create a ticket for the broken retry behavior
```

### Coordinate a larger change

Use a workpackage for a multi-step transformation and a project map when several workstreams or
artifacts must stay aligned.

```text
ts: plan the authentication migration
ts: map the active workstreams and show the current ground task
```

### Investigate uncertainty

Use a spike when the deliverable is learning rather than production code.

```text
ts: create a time-boxed spike to compare deployment options
ts: create a deep-research spike for the cross-layer compatibility contract
```

Choose deep research when unresolved uncertainty spans technical layers, compliant specimens
diverge, a second mitigation failed, or a proposed fix depends on narrow vendor/model heuristics.
Start it before a third mitigation when compatibility, reliability, safety, or data integrity is
broadly affected. Importance or elapsed time alone is not a trigger. Create it with:

```bash
python3 tool_shed/scripts/new_artifact.py deep-research "Compatibility contract" --workspace .
```

Tool Shed structures the evidence; it does not search for it. Use the resulting research to focus
target tests, then promote settled conclusions to project docs. Bound the effort, allow urgent
reversible containment when necessary, and pause speculative production heuristics until
mandatory, optional, and implementation-specific behavior are separated.

When a spike finishes, record `Disposition:` as `planned`, `documented`, `no-action`, or
`superseded`. A planned spike names its follow-up artifact in `Produces:`.

### Preserve a decision or operation

Use an ADR for a durable decision, a decision matrix to compare options, and a runbook for a
repeatable operation.

```text
ts: record the database choice as an ADR
ts: compare these hosting options in a decision matrix
ts: create a rollback runbook
```

### Onboard an existing project

Use Level 2 onboarding to create a project map and inventory before backfilling detailed work.

```text
ts: onboard this existing project
```

The agent observes the repository before creating inferred history. Stable facts go to project docs;
unresolved work stays under `work/`.

### Review planning drift

Use reconciliation when artifacts may have fallen out of sync with plans.

```text
ts: review work state
ts: find orphaned, stale, or undisposed work
```

The underlying command is:

```bash
python3 tool_shed/scripts/review_work_state.py --workspace .
```

It is advisory by default. `--json` supports automation and `--strict` makes findings fail the
command.

### Complete or supersede work

```text
ts: complete work/wp/active/wp-example.md
ts: supersede this decision and preserve the history
```

Completed artifacts remain history. Promote settled current truth to project `docs/` or README
files.

### Install or update Tool Shed

```text
ts: help install
ts: help update
```

The canonical source is [PC-Redemption/tool_shed](https://github.com/PC-Redemption/tool_shed).
Installations are disconnected snapshots: ignore `/tool_shed/`, remove its `.git/`, and track
project-specific `/work/` by default. An update replaces Tool Shed machinery, may transactionally
converge documented Tool Shed-owned work topology and projections, and must preserve owner-authored
work content, project docs, and code.

Use the supported updater from a current released Tool Shed checkout:

```bash
python /path/to/current/tool_shed/scripts/update_snapshot.py --workspace . \
  --project-binding <update-snapshot-binding>
```

If the installed snapshot predates the updater, obtain the current released checkout outside the
project and run it from there. The Python updater is authoritative on Windows and Linux; thin
PowerShell and POSIX launchers are also included. It selects and verifies the highest stable tag
with Git line-ending conversion disabled, creates a recoverable backup for updates, preserves
owner-authored project `work/` while converging released Tool Shed structure, and automatically
restores the previous snapshot and affected workspace state after failed post-install verification.
See [install-or-update-snapshot.md](install-or-update-snapshot.md) for the complete guarded contract.

The rollback archive contains the declared mutation surface, not all project work. Its embedded
manifest lists included/absent paths, explicit generated-output exclusions and hashes, versions,
protocol, timestamp, and transaction ID. After complete success the updater retains the newest two
verified updater-owned workspace and optional user-skill backups by default and irreversibly prunes
older verified archives. It preserves and reports every unknown or unverifiable candidate.

Preview or override retention with:

```bash
python /path/to/current/tool_shed/scripts/update_snapshot.py --workspace . --prune-preview --json
python /path/to/current/tool_shed/scripts/update_snapshot.py --workspace . --backup-retention 4 \
  --project-binding <update-snapshot-binding>
python /path/to/current/tool_shed/scripts/update_snapshot.py --workspace . --no-prune-backups \
  --project-binding <update-snapshot-binding>
```

`--prune-preview` performs no update or deletion. A tracked `.tool-shed-policy.json` may declare
`{"schema_version": 1, "backup_policy": {"retention": 4}}`; the command-line value takes
precedence. Retention is the total verified archive count including the protected immediate
rollback archive and cannot be below one.

Every completed attempt has a stable `TSU-*` issue code in its protected user-local transaction
record. Generate a maintainer-ready draft for the newest or one exact transaction without exposing
raw output or publishing anything:

```text
ts: upgrade report latest
ts: upgrade report <transaction-id> --json
```

The reporter rejects malformed, symlinked, permission-exposed, foreign-platform, unknown-field, or
identity-mismatched records. Its Markdown and JSON contain only bounded release/updater identity,
platform, stage durations, validation/cache mode, issue code, error class, and rollback outcome.
Review the draft before separately authorizing a GitHub issue; report generation never authorizes
or performs `gh issue create`.

After installation or update, run:

```bash
python3 tool_shed/scripts/install_into_workspace.py .
python3 tool_shed/scripts/review_work_state.py --workspace .
```

Both commands detect a root `work/` ignore. An existing rule is not automatically repository
policy. Without a valid repository-root `.tool-shed-policy.json` exception, the output identifies
the exact ignore source and matching rule and previews the count and size of ignored files. Remove
only that root `/work/` rule. Do not delete, replace, relocate, or rewrite any `work/` evidence.

The first install or a legacy upgrade atomically creates the project identity and needs no prior
binding. Re-running the installer on an identified workspace preserves the identity exactly and
requires a `workspace-install` binding. Snapshot backups include the identity path, so injected or
real post-install failure restores the exact prior identity state.

`work/evidence/` is the standard validation-evidence repository. Keep Markdown summaries and
small manifests versioned there, and write raw captures, dumps, images, large logs, and test
payloads under ignored `work/evidence/generated/`. Run
`python3 tool_shed/scripts/workspace_preflight.py --workspace .` before large campaigns.
Use `.git/info/exclude` for additional machine-local evidence paths.

Preflight adapts to the repository it inspects. Its JSON output includes the discovered workspace
profile, effective risk budget, policy source for each threshold, finding severity, and suggested
mitigation. Repository-root `.tool-shed-policy.json` can declare a reasoned generated path and
threshold adjustments; hard safety limits remain in force and invalid or reason-free policy is
reported.

To measure whether repository and `work/` growth correlate with slower operations, run:

```bash
python3 tool_shed/scripts/profile_workspace_performance.py --workspace .
python3 tool_shed/scripts/profile_workspace_performance.py --workspace . --json
```

The profiler is read-only, local, and privacy-allowlisted. It times representative Git,
filesystem, and Tool Shed operations but cannot prove undocumented Codex hashing or indexing.
Profiling does not authorize report collection, snapshot updates, cleanup, or archival. See
`docs/workspace-performance-profiling.md` for the report and comparison protocol.

For raw evidence that is already tracked, prepare a reversible migration:

```bash
python3 tool_shed/scripts/migrate_generated_evidence.py prepare \
  --workspace . \
  --output /safe/outside/path/evidence-migration
```

Preparation is read-only with respect to the repository. It classifies candidates as `keep`,
`migrate`, or `review`, records hashes and reasons, and creates an archive outside the repository.
Apply is a separate human-gated step: approve the manifest and individual migrate candidates, then
run `migrate_generated_evidence.py apply`. The helper revalidates the archive and source hashes,
requires an ignored destination, changes only approved files, and never rewrites history.

Rollback remains deliberate: inspect and extract `evidence-backup.tar` into a separate recovery
directory, verify restored hashes against `evidence-migration.json`, and copy only selected files
back to their recorded original paths. Never extract an unreviewed archive directly over the
repository.

An intentional exception uses:

```json
{
  "schema_version": 1,
  "work_git_policy": {
    "ignore": true,
    "reason": "Repository-specific reason for excluding project work artifacts."
  }
}
```

Evidence-specific adaptation can coexist in the same policy file:

```json
{
  "schema_version": 1,
  "evidence_policy": {
    "reason": "UI validation produces many screenshots and recordings.",
    "generated_path": "test-results/generated",
    "evidence_paths": ["test-results", "playwright-report"],
    "thresholds": {
      "untracked_count": 150,
      "untracked_bytes": 209715200
    }
  }
}
```

### Check version and update status

```text
ts: version
ts: check for updates
ts: update status
```

`ts: version` verifies the local snapshot against its own `SHED_VERSION.json` without using the
network. An update-status request also reads the canonical manifest from GitHub and distinguishes:

- `current`: local and canonical versions match and local tracked files are intact
- `older`: canonical has a newer semantic version
- `newer`: local declares a version ahead of canonical
- `modified`: local tracked content differs from its version manifest
- `release-mismatch`: equal local/canonical versions contain different release manifests
- `check-failed`: canonical status could not be retrieved or parsed

The check is read-only and never authorizes or applies an update.

## Artifact Menu

| Need | Artifact |
| --- | --- |
| Known bounded steps | Checklist |
| Clear bug or enhancement | Ticket |
| Multiple workstreams and navigation | Project map |
| Multi-step transformation | Workpackage |
| Durable decision | ADR |
| Repeatable operation | Runbook |
| Break/fix learning | Incident |
| Time-boxed uncertainty | Spike |
| Classify or route a collection | Inventory |
| Compare plausible options | Decision matrix |

When unsure, ask:

```text
ts: choose the smallest artifact for this: <describe the need>
```

Tool Shed should not become a server, database, general task tracker, or replacement for canonical
project documentation.
