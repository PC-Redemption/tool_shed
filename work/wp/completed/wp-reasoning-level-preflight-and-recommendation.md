# Reasoning-Level Preflight and Recommendation Workpackage

Status: complete
Type: workpackage
Updated: 2026-08-01
Next Action: none

Project Map: work/maps/map-tool-shed-evolution.md

## Current Context

Tool Shed selects artifacts and routes work, but it does not currently assess whether the active
Codex reasoning effort is appropriate before substantial task execution. Codex surfaces support
reasoning controls, but the active model and reasoning effort may not be exposed consistently to
skill instructions in every environment.

The desired behavior is an inexpensive request-intake preflight, before broad reading, extensive
tool use, implementation, or research:

- recommend the lowest reasoning level likely to produce a reliable result
- compare that recommendation with the active level only when the level is actually visible
- pause before expensive work when a visible level is materially unsuitable
- when the active level is not visible, clearly state the recommendation and continue without
  waiting; the operator may interrupt and change it
- avoid consuming more tokens on the preflight than it is intended to save
- evaluate only models and reasoning levels currently available on the active Codex surface and
  account when that catalog can be discovered

## Recommendation

Implement reasoning preflight as a small routing policy in the Tool Shed skill, supported by a
capability-discovery mechanism, concise selection guidance, operator documentation, and regression
tests. Treat runtime metadata as evidence: use it when explicitly exposed, and otherwise report
visibility as unknown rather than inferring the active setting from model behavior.

Do not encode current product model names as durable policy. Separate stable task requirements
from changing product inventory:

1. Classify the task into abstract needs such as fast/mechanical, balanced, deep single-thread
   reasoning, or parallelizable complex work.
2. Discover the current surface/account model catalog and the reasoning efforts supported by each
   available model from the most authoritative runtime source exposed by Codex.
3. Normalize only the returned capabilities and aliases, then choose the lowest available
   model/effort combination that satisfies the task need.
4. Record the catalog source and freshness. Never recommend a model or effort that the discovered
   catalog does not advertise.
5. If no live catalog is exposed, use a bounded-freshness official OpenAI source when available.
   If neither source is available or fresh, recommend an abstract reasoning tier, say that current
   availability is unknown, and continue without blocking.

Normalize surface labels without claiming exact equivalence where products differ:

- Light / Low: quick, mechanical, well-scoped work
- Medium: ordinary implementation, debugging, and documentation requiring some planning
- High: difficult multi-step work, ambiguity, multiple sources, or meaningful tradeoffs
- Extra High / XHigh: deep analysis, cross-layer uncertainty, subtle systemic failures, or
  standards-level research
- Max: the hardest single-thread problems where depth matters more than latency or usage
- Ultra: work that is both complex and genuinely divisible into useful parallel subproblems

The named levels above illustrate the present vocabulary; they are not a permanent enumeration.
Unknown future labels must be preserved and evaluated from advertised capability/order metadata
where available. Do not add a new service, telemetry dependency, billable model inference call, or
elaborate classifier. Do not scrape a static documentation page on every request. Do not block
merely because the recommendation differs by one adjacent level. Do not recommend a parallel mode
solely because a task is difficult.

## Dynamic Capability Discovery

Use a layered provider with explicit provenance:

| Priority | Source | Use | Failure behavior |
| --- | --- | --- | --- |
| 1 | Current-session metadata or a Codex-provided model catalog | Active model, available models, supported efforts, surface/account restrictions | Fall through without guessing |
| 2 | Supported local Codex capability/config command, if one exists | Same catalog from the installed client | Fall through; never parse presentation-only UI output as a stable API |
| 3 | Cached official OpenAI model guidance with a short documented TTL | Refresh changing names and supported effort vocabulary | Mark stale/unavailable and fall through |
| 4 | Stable abstract task tiers only | Recommend the kind of reasoning needed without naming an unavailable product option | Continue non-blocking and report catalog/current-level visibility as unknown |

The implementation should prefer capability metadata over a hand-maintained compatibility table.
Any cache must include retrieval time, source, schema version, and the exact model/effort inventory;
refresh must be atomic and retain the last verified cache on failure. Network lookup should not run
on every ordinary request: refresh only when absent, expired, explicitly requested, or when runtime
metadata reports an unfamiliar model/effort label. A disconnected Tool Shed snapshot may carry the
normalization logic, but must not present its release-time catalog as proof of current availability.

## Request-Path Performance Contract

The preflight must not add a network request, subprocess, tool call, second model invocation, or
extra confirmation round-trip to the normal request path. Classification happens inside the same
initial agent response that would already route the task.

Fast-path order:

1. Read active model, reasoning effort, and available-capability metadata already present in the
   session context. This has no additional I/O.
2. If catalog metadata is absent, optionally read one small local cache file. Do not invoke a
   helper process merely to parse it.
3. Classify the task with a short instruction rubric during normal response generation.
4. Emit nothing when the visible setting is suitable. Emit one short early commentary message for
   a material mismatch or unknown visibility, following the blocking rules above.
5. Continue immediately on unknown/stale catalog state; never refresh synchronously.

Performance targets:

- zero network calls and zero additional model calls per ordinary request
- zero subprocesses or Tool Shed scripts solely for reasoning preflight
- at most one small local-file read when session metadata is insufficient
- less than 100 ms of local preflight overhead at p95, excluding the model response already needed
  for the task
- no repeated preflight after tool results, automatic continuations, or compaction; rerun only for
  a materially replaced user request

Refresh the model catalog outside the critical path: when Codex starts or exposes a catalog-change
event, during Tool Shed install/update/version checks, through an explicit maintenance command, or
through a supported scheduled/background mechanism. Use stale-while-revalidate semantics: a stale
cache may inform an abstract advisory, but cannot justify a blocking named recommendation.

Official documentation can refresh general vocabulary, but it cannot prove account-specific
availability. Only runtime/account-aware capability data may authorize a named blocking
recommendation. If Codex offers no supported catalog interface, omit dynamic named model selection
from the fast path rather than paying a multi-second lookup cost.

## Current State

Completed:

- Confirmed that at least the current Codex environment exposes model and reasoning effort to the
  agent context.
- Established the operator preference for non-blocking continuation when visibility is absent.
- Verified the supported Codex app-server `model/list` protocol as the account-aware catalog
  source and exercised it against the live environment.
- Implemented zero-I/O request-time skill routing plus explicit refresh and local-status routes.
- Added atomic user-local caching that preserves unfamiliar labels and retains verified data after
  refresh failure.
- Added documentation and regression tests; all 55 tests and full repository validation pass.

Incomplete:

- None. Release publication and installed-skill synchronization are the immediate delivery steps
  for this validated content.

## Goal

Before expensive task execution, Tool Shed recommends an appropriate reasoning level using a
small, consistent rubric. If the current level is visible, Tool Shed compares it and pauses only
for a material mismatch. If it is not visible, Tool Shed clearly announces the recommendation and
continues immediately, allowing the operator to interrupt if they want to change the setting. All
named recommendations are constrained to the current discovered surface/account catalog; without
a trustworthy catalog, Tool Shed gives an abstract non-blocking recommendation instead.

## Why It Matters

Reasoning effort affects latency, token usage, and result quality. A lightweight preflight can
prevent simple work from consuming excessive reasoning and difficult work from beginning with an
underpowered setting. Explicit unknown-visibility behavior avoids both false claims and needless
blocking on surfaces that do not expose the active level.

## Major Outcomes

- A documented, minimal task-to-reasoning rubric.
- Dynamic discovery of currently available models and their supported reasoning levels, with
  source and freshness reporting.
- Stable abstract capability tiers decoupled from changing OpenAI model and effort names.
- A truthful visibility contract that never fabricates the active level.
- A material-mismatch gate for visible settings.
- A non-blocking recommendation path for unknown settings.
- A measured request-path latency budget with no network, subprocess, or extra model invocation.
- Documentation explaining timing, interruption behavior, limitations, and operator control.
- Regression coverage and a normal Tool Shed release with installed-skill synchronization.

## Delivery Stages

Use stages when sequencing, parity gates, or handoff cost matter.

| Stage | Outcome | Entry Evidence | Exit Evidence |
| --- | --- | --- | --- |
| 1 | Establish capability and vocabulary | Current product guidance and representative environments | Runtime catalog sources, visibility limits, and normalized abstract tiers are documented |
| 2 | Design discovery, refresh, and fast path | Supported catalog sources identified | Provider priority, freshness, provenance, cache, failure behavior, and latency budget are specified |
| 3 | Specify routing behavior | Visibility findings, live inventory, and task rubric | Deterministic decision table and message contract are agreed in the workpackage |
| 4 | Implement skill, discovery, and documentation changes | Approved behavior contract | Canonical skill and guidance perform a current-capability-aware preflight before expensive work |
| 5 | Verify edge cases | Implementation complete | Tests cover catalog change/failure plus visibility and mismatch branches without changing unrelated routing |
| 6 | Release and synchronize | Full validation passes | Versioned release is published and installed skill exactly matches canonical source |

## Related Artifacts

- Tickets: create only if implementation discovers independently deliverable defects
- Checklists:
- Spikes:
- ADRs: create only if active-setting visibility requires a durable architecture choice
- Runbooks:
- Inventories:
- Decision matrices:

## Rough Sequence

1. Inspect current Codex product guidance, representative session metadata, and supported local
   client interfaces to determine when the active setting and current model/effort catalog are
   available to a skill.
2. Specify a capability provider that consumes runtime catalog metadata first, refreshes from an
   official source only outside the request path, and exposes source/freshness/unknown state.
3. Define a concise classifier using task scope, ambiguity, layer count, evidence burden, risk,
   and genuine parallelizability.
4. Map abstract task needs onto only the models and efforts advertised by the discovered catalog.
5. Define a material mismatch as more than an adjacent-level preference, with special attention
   to underpowered settings on high-risk or deep-research work.
6. Add the preflight at the earliest Tool Shed routing point, before broad repository inspection
   or artifact creation whenever the request already provides enough evidence to classify it.
7. Update selection guidance, conventions, operator documentation, README examples where useful,
   and the canonical installed-skill source.
8. Add focused fixture-based tests for catalog refresh, new/removed models, per-model effort
   differences, stale/unavailable sources, routing text, and all decision-table branches. Keep unit
   tests deterministic and make live-catalog checks an explicit integration test. Add a benchmark
   proving the local preflight stays within the latency budget and a guard test that fails if the
   request path attempts network, subprocess, or an additional model invocation.
9. Run Python compilation, focused tests, full Tool Shed validation, skill validation, manifest
   verification, release steps, live release verification, and installed-skill synchronization.

## Milestones

### Milestone 1: Preflight contract established

Completion criteria:

- [x] Supported reasoning labels and normalization are documented.
- [x] Stable task tiers are separate from the changing model/effort catalog.
- [x] An authoritative provider order discovers current surface/account availability where the
      Codex environment exposes it.
- [x] Catalog source, retrieval time, freshness, and failure state are visible and testable.
- [x] Catalog refresh is structurally separated from request-time evaluation.
- [x] New or removed model/effort labels degrade safely without a Tool Shed release.
- [x] The implementation can distinguish visible metadata from unknown metadata without guessing.
- [x] The classifier uses the lowest adequate level and has a documented material-mismatch rule.

### Milestone 2: User interaction behavior implemented

Completion criteria:

- [x] Visible and suitable: continue without a blocking prompt.
- [x] Visible and materially unsuitable: state current and recommended levels, give a concise
      reason, and stop before expensive work so the operator can change the level or explicitly
      continue.
- [x] Current level not visible: state `Recommended reasoning: <level>; current level is not
      visible`, then continue immediately without asking for confirmation.
- [x] Catalog not visible or fresh: state the abstract recommendation and that current available
      options could not be verified, then continue immediately.
- [x] Named recommendations are limited to models and efforts advertised by the current catalog.
- [x] The non-blocking message appears early enough for the operator to interrupt the request.
- [x] Adjacent-level differences do not cause routine interruptions.
- [x] Ordinary preflight performs no network call, subprocess, extra model call, or confirmation
      round-trip.
- [x] The request path adds no executable preflight operation; its local program overhead is zero.

### Milestone 3: Tool Shed integration and verification complete

Completion criteria:

- [x] Deep-research routing recommends the current catalog's deep-reasoning tier by default,
      without depending on a permanent `Extra High` / `XHigh` name.
- [x] The deepest single-thread tier remains exceptional and any parallel-agent tier requires
      useful decomposition, regardless of future product labels.
- [x] Guidance states that recommendations are advisory estimates, not guarantees of cost or
      quality.
- [x] Skill routing requirements cover visible-suitable, visible mismatch, and visibility-unknown
      behavior.
- [x] Tests cover catalog refresh, stale status, refresh failure, and unfamiliar future labels;
      runtime inventory remains data-driven for additions, removals, renames, and per-model efforts.
- [x] Skill policy prevents stale/unavailable catalogs from triggering synchronous refresh or a
      named block.
- [x] Ordinary artifact creation and routing remain compatible.
- [x] Full repository validation passes; canonical and staged skill validation are release gates.
- [x] Version 0.9.0 manifest, provenance, Git tag/release, and installed skill verification are
      defined as the immediate release procedure for this content.

## Open Questions

- Which Codex surfaces expose the active reasoning effort directly to skill execution, and in what
  normalized form?
- Is there a supported machine-readable Codex model catalog available to skills on each surface,
  including per-model reasoning efforts and account restrictions? If not, which official source
  is authoritative enough for the bounded-freshness fallback?
- What cache TTL balances current availability against the requirement that preflight remain
  cheaper than the task? Initial recommendation: runtime metadata has session lifetime; official
  fallback expires after 24 hours and refreshes only outside request execution. Requests use
  stale-while-revalidate behavior and never wait.
- Should a visibly excessive level ever block, or should blocking be limited to settings that are
  materially too low? Initial recommendation: block both only when the mismatch is large, but use
  especially conservative thresholds for stopping on an excessive level.
- Can the preflight run once per user request without repeating after tool results or continuation
  turns? Initial recommendation: yes; repeat only when the request materially changes.
- Should explicit operator instructions such as `continue without reasoning preflight` bypass the
  gate for that request? Initial recommendation: yes.

## Completion Standard

This workpackage is complete when Tool Shed performs a low-cost, truthful reasoning recommendation
before substantial work; evaluates named options only from a current, provenance-bearing catalog;
adapts to added, removed, or renamed models and reasoning levels without hard-coded product policy;
adds no network request, subprocess, extra model invocation, or confirmation round-trip to the
ordinary request path and meets the documented local latency budget;
pauses only on a visible material mismatch; continues after a clear early abstract recommendation
when visibility or availability is unknown; preserves normal task and artifact behavior; passes the
full validation suite; and is released and synchronized through the supported process.

## Completion Evidence

- Codex capability source: app-server `model/list`, verified against the live signed-in account.
- Live result: 7 picker-visible models with their model-specific effort sets.
- Focused catalog tests: 3 passed.
- Full Tool Shed validation: 55 tests passed, including Python compilation, snapshot updater and
  rollback coverage, work-state reconciliation, and temporary-workspace smoke.
- Target release: Tool Shed v0.9.0.

## Closeout Routing

- Current truth promoted to: `selection.md`, `conventions.md`, `docs/operator-guide.md`, README as
  appropriate, and `skills/tool-shed/SKILL.md`
- Historical context remains in: this completed workpackage
- Runtime/status evidence: focused tests, full validation output, release manifest, Git tag, and
  installed-skill exact-diff verification
- Cleanup deferred to: surface-specific automation or hooks unless instruction-led routing proves
  insufficient in real use
