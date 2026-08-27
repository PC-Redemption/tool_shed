# Idea Brief: Persistent Autonomy Levels

Status: promoted
Type: idea-brief
Updated: 2026-08-27
Next Action: use the approved revised project-map direction to propose Program Roadmap revision 2
Produces: work/maps/map-persistent-autonomy-levels.md

## Current Synthesis

### Idea

Add persistent, cumulative autonomy levels so the owner can select a level such as `0` through `5`
once and Tool Shed will stop requesting repetitive confirmation for action categories already
covered by that level. The level participates in one authority envelope formed from the requested
outcome and scope, selected work1-work5 endpoint, known target, persistent autonomy level, and
provider policy. A direct `go` or `continue` should bind that envelope and allow the complete
applicable lifecycle to continue until the requested outcome is verified or a genuine new-authority
boundary is reached.

The lifecycle covered by that continuation includes discovery promotion, project-map and roadmap
state transitions, milestone campaign derivation and materialization, queue transitions, campaign
execution, implementation, verification, evidence gates, completion, and—when the requested
endpoint and autonomy level cover them—remote collaboration and delivery. Artifact types, phase
boundaries, state tokens, and ordinary progress checkpoints are not approval gates by themselves.

### Why It Matters

Tool Shed already intends to continue reversible, in-scope work after clear authorization, but the
owner still experiences repeated approval requests after saying to proceed. In the first PRM use of
this idea, the owner was offered separate project-map, roadmap, and campaign-plan approvals even
though all were derived from the same request, changed only reversible workspace metadata, and
presented no material risk. The prompts required ceremony without giving the owner a useful
self-contained decision or reason to inspect the referenced files. Those pauses add interaction
cost, break concentration, and undermine end-to-end campaign continuity.

### Desired Outcome

The owner can persist an easily understood autonomy preference, see exactly which action categories
it covers, and complete normal work with zero additional Tool Shed approvals after `go` whenever
the active authority envelope covers the remaining actions. Higher levels progressively cover
planning, local execution, checkpoints and campaign lifecycle, remote collaboration, and
known-target delivery. Tool Shed interrupts only for a material unresolved decision, new authority,
or a safety boundary that the envelope cannot cover.

## Constraints And Non-Goals

- Tool Shed preferences guide agent behavior but cannot bypass provider-native permission, sandbox,
  protected-environment, or account controls.
- Effective authority must remain bounded by the intersection of the requested task scope, selected
  work1-work5 endpoint, known target, persistent autonomy level, and provider policy. Autonomy does
  not invent work, expand scope, or raise the requested endpoint.
- Faithful project maps, roadmap proposals, campaign plans, campaign materialization, queue and
  completion transitions, and evidence-gate advancement should proceed automatically when derived
  from and contained by the active envelope. Their state tokens remain internal stale-write and
  concurrency protections rather than text the owner must reproduce.
- A prompt is justified only when an action is not already entailed by the envelope, a meaningful
  alternative could materially change the result or risk, and the choice cannot safely be inferred
  or cheaply reversed.
- Unknown targets, material scope expansion, credentials or authentication changes, cross-workspace
  operations, purchases or legal commitments, and broad destructive or irreversible actions remain
  explicit boundaries at every level. Known production delivery may proceed only when both the
  requested endpoint and autonomy level explicitly cover it.
- Persistent state should be protected user-local data, bound to a verified project identity, and
  never committed to a repository or copied into an installed snapshot.
- The initial feature should not add a server, database, dashboard, background worker, or general
  policy engine.

## Possibilities And Tradeoffs

| Possibility | Benefits | Costs / Risks | Evidence / Status |
| --- | --- | --- | --- |
| Persistent autonomy level `0`-`5` | Simple mental model; one setting progressively removes pauses | Category boundaries must be precise and cumulative | Owner-requested direction |
| Treat levels as literal blanket approval | Shortest explanation | Conflates pause policy with task authority and could silently expand scope | Not recommended |
| Treat levels as one dimension of an authority envelope | Removes ceremony throughout PRM, campaign materialization, execution, and delivery without inventing work | Requires an action classifier, explicit endpoints and targets, and a clear hard-stop set | Recommended direction |
| Canonical `ts: autonomy <level>` with `ts: approve <level>` alias | Avoids collision with `approve roadmap` and `approve campaign plan` while supporting the owner's preferred shorthand | Adds one documented alias | Recommended |
| Project-bound user-local preference | Prevents one project's trust setting from silently applying to another | Requires stable identity binding and per-project entries | Recommended default |
| One global user preference | Lowest setup friction across projects | Trust and deployment boundaries differ by workspace | Possible explicit override, not default |
| One-command or campaign override | Makes it easy to tighten or temporarily raise autonomy without changing the durable default | Adds precedence rules | Recommended companion feature |

Candidate cumulative matrix:

| Level | Actions that normally continue without another Tool Shed confirmation |
| --- | --- |
| `0` Observe | Read, inspect, diagnose, and non-mutating checks; ask before durable writes |
| `1` Plan | Create and update ideas, maps, roadmaps, manifests, indexes, and other reversible planning state |
| `2` Build | Scoped source edits, ordinary project-local dependency operations, tests, builds, and generated outputs |
| `3` Checkpoint | Materialize campaigns, transition queues, create local commits, record evidence, and complete lifecycle stages |
| `4` Collaborate | Pushes, PR or issue updates, and known non-production deployments |
| `5` Deliver | Requested merge, release, publication, and known production deployment endpoints when the work endpoint includes them |

Approval handling should be event-driven rather than phase-driven. Ordinary discrepancies such as a
test failure should cause diagnosis, a bounded fix, and proportionate revalidation without an owner
prompt. A recovery that would reset data, broaden scope, change the intended outcome, or cross an
unknown target should pause because it requires new authority. When a pause is legitimate, the
prompt must state the action, why the current envelope does not cover it, impact, blast radius,
rollback, and a recommendation so the owner does not have to open planning files to understand the
decision.

## Open Questions

- Should the canonical command be `ts: autonomy <level>`, with `ts: approve <level>` as an alias,
  or should the shorter but overloaded `approve` form be canonical?
- Are the proposed boundaries between levels correct, especially commit at `3`, push/development at
  `4`, and production delivery at `5`?
- Should the default preference be project-bound only, with a separate explicit command for a global
  default, or should the owner's chosen level apply to all Tool Shed workspaces?
- Should every level persist indefinitely, or should levels `4` and `5` support or default to a
  campaign/expiration boundary?
- Which recoverable deletions, dependency changes, external messages, merges, and publications need
  narrower categories rather than sharing a broad level?
- What endpoint should a bare `ts: prm <outcome>` imply, or should PRM always name `through workN`
  when execution is intended?
- Should `go` create a durable campaign authorization capsule or bind the current outcome and
  endpoint through the existing project-local campaign state?
- How should faithful automatic acceptance distinguish an implementation detail from a material
  product, architecture, sequencing, or target decision that requires the owner?
- When exactly one legitimate decision is pending, should a plain `approve` accept it while tokens
  remain entirely internal?

## Decisions

- The owner wants a persistent numeric approval preference, approximately levels `0` through `5`.
- Higher numbers must cumulatively reduce approval requests using a specific documented case list.
- The primary problem is repetitive confirmation after the owner has already said `go`.
- The intended scope is the whole Tool Shed cycle, including PRM transitions, campaign derivation
  and materialization, queue execution, implementation, evidence gates, and applicable delivery.
- One authorization envelope should replace phase-by-phase and artifact-by-artifact approvals.
- A faithful derived artifact or reversible lifecycle mutation is not a semantic approval boundary
  merely because Tool Shed represents it as a separate file or state transition.
- The practical success criterion is zero additional Tool Shed approvals after `go` while all
  remaining actions stay inside the active envelope.
- The owner chose to carry this synthesis into the full PRM lifecycle.

## Don't Forget

- Existing work1-work5 routes define lifecycle endpoints; autonomy levels should control pauses
  within authorized work rather than replace endpoint selection.
- `ts: approve 5` cannot turn a work1 request into a push or release; conversely, a requested work5
  endpoint pauses at any action not covered by the selected autonomy level.
- Status and reset commands are needed, along with a one-command way to tighten behavior.
- Every legitimate interrupt must present its risk and decision inline; links are supporting detail,
  not a prerequisite for informed consent.
- Malformed, stale, foreign-project, or root-mismatched preference state must fail safely to the
  current default rather than broadening authority.
- Sanitized diagnostics may record only level, action category, and decision outcome—not prompts,
  repository content, credentials, or raw tool output.

## Exploration Log

### 2026-08-27

- Idea Brief created from the owner's request for persistent `0`-to-`5` approval levels that reduce
  repetitive prompts after `go`.
- Initial exploration separated persistent autonomy/confirmation behavior from task scope, work
  endpoints, exact semantic approvals, and provider-native enforcement.
- A candidate cumulative matrix was recorded: observe, edit, build, checkpoint, collaborate, and
  deliver. Boundaries and persistence scope remain open for owner refinement.
- The owner selected PRM promotion. The brief is now `ready-for-prm` and remains unpromoted until
  an exact approved project map captures its direction.
- The owner approved project-map token `2f1bebd0d263bb5c`; the brief is promoted and preserved as
  provenance for `work/maps/map-persistent-autonomy-levels.md`.
- The owner clarified that the intended idea is larger than suppressing routine confirmations while
  preserving separate exact semantic gates. Persistent autonomy should remove ceremonial approvals
  across the entire PRM, campaign-materialization, execution, evidence, and delivery lifecycle when
  those actions remain inside one explicit authority envelope. The existing approved project map
  and roadmap reflect the earlier narrower interpretation and need revision before implementation.
- The brief returned to `ready-for-prm` while the corrected project-map direction is proposed. The
  earlier approved map and roadmap remain history but no longer represent the current synthesis.
- The owner approved the corrected authority-envelope project-map direction. The brief is promoted
  again and roadmap revision 1 remains drifted pending a faithful revision 2 proposal.

Keep the synthesis current and append only useful dated exploration notes. Use `Status: ready-for-prm`
when the owner chooses to promote it, `promoted` after approved project-map direction captures it,
or `parked` when it is intentionally set aside. A promoted brief names its output in `Produces:`.
