# Tool Shed campaign entry, efficiency, and portability Workpackage

Status: active
Type: workpackage
Updated: 2026-08-09
Next Action: finish release qualification, publish the approved release, synchronize the installed Codex client, and verify from a fresh task

Project Map: work/maps/map-tool-shed-evolution.md

## Current Context

The operator frequently begins potential Tool Shed campaigns with open-ended discussion. Tool Shed
currently selects artifacts after a goal takes shape, but it has no explicit conversational route
for exploring whether a campaign exists, clarifying its shape, and choosing the smallest next
Tool Shed action without prematurely creating work artifacts.

The second concern is Tool Shed's token cost. Upfront coordination is worthwhile when it prevents
more expensive rework, failed attempts, missed requirements, or recovery, but a large fixed
instruction and artifact cost can burden simple work. Tool Shed needs to optimize total campaign
cost rather than minimize either planning tokens or execution tokens in isolation.

The two concerns belong together: discussion is the lowest-cost campaign intake, and that intake
can select the minimum sufficient coordination level before Tool Shed loads additional procedures
or creates durable work.

The third concern is product portability. Tool Shed was developed and qualified through Codex, so
its durable artifact model and Python utilities are already broadly portable while its discovery,
instruction, reasoning, approval, installation, and lifecycle language contain Codex assumptions.
Tool Shed should become a generic AI product by defining a vendor-neutral behavior contract and
shipping thin native adapters for major agent-capable services, without reducing every provider to
a lowest-common-denominator prompt.

## Recommendation

Plan a lightweight `ts: discuss <topic>` route as an interaction mode rather than a new artifact
type. It should explore and summarize an emerging campaign, recommend the smallest next route, and
avoid workspace writes until explicitly requested.

Adopt `minimum sufficient coordination` as the efficiency rule: start at the lowest adequate
coordination level and escalate only when evidence shows ambiguity, consequence, irreversibility,
cross-layer uncertainty, repeated failure, coordination, or handoff cost. Specialized instructions
should load progressively rather than making every Tool Shed request pay the complete procedure
cost.

Define Tool Shed as a portable coordination protocol with native platform packaging. Keep artifact
schemas, campaign behavior, authority boundaries, evidence-response rules, deterministic scripts,
and conformance scenarios in a vendor-neutral core. Put instruction discovery, skill/plugin
packaging, command syntax, tool names, permission behavior, model catalogs, hooks, and installation
details in provider adapters. Use the Agent Skills `SKILL.md` baseline where supported, while
testing outcomes rather than assuming identical provider semantics.

Keep files and Git as durable project state and the existing Python utilities as deterministic
operations. Treat MCP as an optional tool surface for providers that support it, not as a required
server or replacement source of truth. Advertise compatibility by capability level rather than a
binary claim that every chat or agent surface supports the full Tool Shed lifecycle.

Avoid implementing source changes, minimizing tokens at the expense of outcome quality, adding a
permanent discussion log, creating a discussion template, assigning false-precision token budgets,
requiring deep-planning ceremony for bounded reversible work, building one universal provider
prompt, or creating a mandatory server during this planning stage.

## Current State

Completed:

- Identified discussion as a recurring campaign-entry behavior.
- Chosen an interaction route—not an artifact type—as the initial design direction.
- Defined a provisional campaign-seed concept and exit routes.
- Captured total campaign efficiency as the second concern.
- Captured cross-provider product portability as the third concern.
- Determined that discussion intake and adaptive coordination belong in one workpackage.
- Defined a provisional four-level coordination model and progressive-loading direction.
- Chosen a provisional portable-core plus native-adapter architecture.
- Finalized `ts: discuss` as the authoritative discovery route and `discussion:` as an informal
  read-only entry signal.
- Implemented minimum sufficient coordination and progressive route loading.
- Implemented the provider-neutral skill contract, provider registry, native instruction adapters,
  static conformance runner, documentation, and tests.
- Qualified Codex at Level 5 locally and the four additional provider packages at honest static
  Level 2 pending runtime availability.

Incomplete:

- Complete the `0.12.0` release, live canonical-manifest verification, installed Codex client sync,
  and fresh-task smoke.
- Run later runtime scenarios on non-Codex providers before increasing their capability claims.

## Goal

Tool Shed provides a low-ceremony entry point for exploring new campaign ideas. Discussion can
surface the desired outcome, motivation, assumptions, constraints, unknowns, and candidate next
route without creating project state prematurely. Tool Shed then uses the minimum sufficient
coordination and loads only the procedures warranted by the campaign's current uncertainty,
consequence, reversibility, duration, and coordination needs.

The same campaign and work artifacts can move between supported AI services. Each service uses a
native adapter for its instruction, skill, tool, permission, and packaging surfaces while sharing
the Tool Shed core behavior and deterministic workspace operations.

Success means lower expected total campaign cost—orientation, coordination, execution,
verification, rework, and recovery—without more missed requirements, authority errors, failed
attempts, or false completion. Portability success additionally means equivalent frozen campaign
scenarios produce materially equivalent artifacts, authority behavior, and verified outcomes on
multiple independent providers.

## Why It Matters

Without an explicit discovery mode, an agent may solve too quickly, create an artifact before the
goal is understood, or leave a useful discussion without a clear campaign seed. A thin discussion
route can preserve open exploration while still producing a reliable transition into Tool Shed.

Conversely, excessive always-loaded instruction, repeated context summaries, unnecessary
artifacts, and disproportionate validation spend tokens without necessarily reducing risk. A
progressive design should preserve Tool Shed's reliability advantage while reducing its fixed cost
on ordinary work.

Without a portable contract, copying the Codex skill into other products would preserve hidden
Codex assumptions and create divergent forks. A core-and-adapter design can reuse the market's
converging Agent Skills format while isolating the real differences in instruction discovery,
permissions, hooks, tools, session lifecycle, and distribution.

## Major Outcomes

- A defined `ts: discuss <topic>` behavior contract.
- A compact campaign-seed summary shape.
- Explicit non-write and non-artifact defaults.
- Clear exit routing to no action, an answer, spike, decision matrix, ADR, workpackage, project map,
  or `ts:ship`.
- A four-level `Direct`, `Guided`, `Coordinated`, and `Deep` engagement model.
- Evidence-based escalation and de-escalation triggers.
- A thinner always-loaded routing contract with route-specific procedures loaded on demand.
- A risk-proportionate validation ladder.
- A compact campaign-state capsule for efficient continuation.
- An evaluation protocol measuring total campaign efficiency and outcome quality together.
- A vendor-neutral Tool Shed behavior and artifact contract.
- A portable Agent Skills baseline plus thin Codex, Claude Code, Gemini CLI, GitHub Copilot, and
  Cursor adapter specifications.
- Explicit capability levels for discussion, planning, workspace execution, integration, and
  end-to-end delivery.
- An optional MCP facade over deterministic Tool Shed operations, with files and Git remaining
  authoritative.
- A cross-provider conformance suite that evaluates equivalent outcomes rather than prompt text.

## Adaptive Coordination Model

| Level | Typical shape | Default Tool Shed behavior |
| --- | --- | --- |
| Direct | clear, reversible, single-step | no artifact; minimal relevant context; execute and verify directly |
| Guided | bounded work with several known steps | checklist or ticket; targeted validation |
| Coordinated | multi-session, branching, dependency, or handoff cost | workpackage or project map; staged verification |
| Deep | consequential, difficult to reverse, highly uncertain, cross-layer, or repeatedly failing | research spike, prospective failure analysis, controlled evidence, and broader qualification |

Start at the lowest adequate level. Escalate when evidence—not importance language alone—shows the
need. De-escalate once the uncertainty or coordination burden has been resolved.

## Cross-Provider Product Model

| Layer | Portable responsibility | Provider-specific responsibility |
| --- | --- | --- |
| Core protocol | artifact schemas, campaign lifecycle, routing semantics, authority boundaries, evidence-response behavior | none |
| Skill | progressive workflow guidance and bundled references using the common `SKILL.md` baseline | discovery locations, invocation syntax, and supported extensions |
| Workspace runtime | deterministic Python scripts, files, indexes, validation, and Git-compatible state | shell/file tool names, sandbox behavior, and approval mapping |
| Integration | optional structured operations suitable for an MCP facade | MCP configuration, authentication, hooks, and native tool registration |
| Distribution | canonical versioned core and adapter manifests | Codex plugin/skill, Claude plugin, Gemini extension, Copilot customization, or Cursor package/rules |
| Qualification | frozen campaign fixtures and outcome assertions | provider harness, telemetry availability, and declared capability level |

Initial capability levels:

1. `Discussion`: analyze and recommend without durable workspace mutation.
2. `Planning`: read and create portable Tool Shed artifacts.
3. `Workspace`: edit files, run deterministic utilities, and validate results.
4. `Integrated`: use MCP, hooks, policies, permissions, or structured provider tools.
5. `Delivery`: plan, implement, build, deploy, and verify an outcome end to end.

Compatibility should be declared for a specific product surface and level. A web chat, IDE agent,
CLI agent, cloud agent, and API-built agent from the same provider may support different levels.

## Efficiency Evaluation

Evaluate current Tool Shed against the progressive design on frozen scenarios at all four levels.
Run a representative subset through each provider adapter and compare equivalent outcomes rather
than exact responses or tool-call sequences.
Measure, when available:

- input and output tokens by campaign stage;
- instruction bytes and files loaded as transparent proxies when tokens are unavailable;
- first-pass outcome success and requirement coverage;
- failed or repeated attempts;
- human corrections and plan revisions;
- tool calls, turns, artifacts, and validation steps;
- recovery work and authority or safety errors;
- artifact interchangeability and provider-switch recovery;
- provider-specific instruction overhead and adapter-induced failure;
- capability claims versus observed execution and verification behavior.

An efficiency improvement is acceptable only when it reduces total coordination cost without a
critical regression or material increase in missed requirements, rework, recovery, or false
completion.

## Delivery Stages

Use stages when sequencing, parity gates, or handoff cost matter.

| Stage | Outcome | Entry Evidence | Exit Evidence |
| --- | --- | --- | --- |
| 1 | Complete product-improvement scope | discussion, token-efficiency, and portability concerns | concerns are bounded and composed as adaptive, portable campaign coordination |
| 2 | Finalize behavior and portability design | agreed scope | route, coordination levels, progressive loading, validation ladder, portable core, capability tiers, adapters, and exits are testable |
| 3 | Plan implementation | finalized behavior plus frozen efficiency and conformance scenarios | exact core, adapter, documentation, test, release, and deployment surfaces are named |
| 4 | Implement and ship later | explicit implementation authorization | target behavior is validated and deployed |

## Related Artifacts

- Tickets:
- Checklists:
- Spikes:
- ADRs:
- Runbooks:
- Inventories:
- Decision matrices:

## Rough Sequence

1. Resolve the discussion route's syntax and behavioral contract.
2. Define minimum sufficient coordination, the four levels, and escalation/de-escalation triggers.
3. Design a thin core skill plus progressively loaded route references without weakening portable
   workspace guidance.
4. Define the campaign-state capsule and risk-proportionate validation ladder.
5. Freeze quality, rework, safety, and token-efficiency scenarios and adoption gates.
6. Inventory Codex-specific assumptions and define the vendor-neutral core contract.
7. Define capability levels, the optional MCP boundary, and native adapter contracts for Codex,
   Claude Code, Gemini CLI, GitHub Copilot, and Cursor.
8. Freeze cross-provider conformance scenarios, starting with Codex plus one independent provider
   and requiring a second distinct adapter before making a broad generic-product claim.
9. Identify implementation, documentation, compatibility, release, deployment, and rollback surfaces.
10. Stop at the implementation-ready plan until implementation is explicitly requested.

## Milestones

### Milestone 1: Scope complete

Completion criteria:

- [x] Discussion-route opportunity is captured.
- [x] Token-efficiency concern is captured.
- [x] Cross-provider product-portability concern is captured.
- [x] The concerns are composed as adaptive, efficient, and portable campaign coordination.

### Milestone 2: Design ready

Completion criteria:

- [x] Route syntax and aliases are decided.
- [x] Discussion behavior and campaign-seed fields are explicit.
- [x] Write boundaries, exit conditions, and anti-ceremony rules are explicit.
- [x] Coordination levels and escalation/de-escalation triggers are explicit.
- [x] Thin-core and progressive-loading boundaries are explicit.
- [x] Campaign-state capsule and validation ladder are explicit.
- [x] Acceptance scenarios cover productive exploration, no-action outcomes, and transition into
  existing Tool Shed routes.
- [x] Efficiency scenarios cover all four levels and protect outcome quality, authority, and safety.
- [x] Vendor-neutral core behavior and artifact boundaries are explicit.
- [x] Capability levels and honest surface-specific compatibility claims are explicit.
- [x] Provider-owned instruction, permission, packaging, hook, and tool concerns are isolated behind
  adapter contracts.
- [x] The Agent Skills baseline, optional MCP role, and durable file/Git state boundaries are explicit.

### Milestone 3: Delivery plan ready

Completion criteria:

- [x] Exact files, route references, and tests are named.
- [x] Core and adapter source layout, generation strategy, and manifests are named.
- [x] Codex, Claude Code, Gemini CLI, GitHub Copilot, and Cursor adapter order and qualification
  surfaces are planned.
- [x] Cross-provider conformance fixtures and outcome-parity gates are planned.
- [x] Compatibility, rollout, release, installed-client sync, and rollback are planned.
- [x] Measurement sources and honest proxy behavior are defined for environments without token telemetry.
- [x] Implementation began only after the explicit `ts:ship` request.

## Open Questions

- Should `discussion:` remain an informal conversational label, should only `ts: discuss` be
  authoritative, or should both be recognized with different routing semantics?
- What minimum campaign-seed fields are useful without turning discussion into a form?
- Should a discussion remain entirely transient unless the operator explicitly requests capture?
- Which rules must remain in the always-loaded skill or generated `AGENTS.md`, and which can safely
  move into route-specific references?
- Which observable signals distinguish `Guided` from `Coordinated` without adding another form?
- When actual token telemetry is unavailable, which combination of instruction bytes, loaded files,
  turns, tool calls, attempts, and rework best approximates total campaign cost?
- Which current rules are truly Tool Shed core behavior, and which encode Codex discovery,
  permissions, reasoning, session, or packaging assumptions?
- Should generated provider packages share `.agents/skills` where supported, or should every
  provider receive only its native discovery path from an installer?
- What is the minimum conformance threshold for claiming provider support at each capability level?
- Which independent provider should be the first portability proof, and which second adapter is
  sufficiently different to justify the broader generic-product claim?
- Which deterministic operations justify an optional MCP facade, and which should remain direct
  file or CLI operations?
- How should Tool Shed record provider and surface capability without making fast-changing model
  names part of the durable core contract?

## Completion Standard

This planning workpackage is ready for implementation when the discussion route, adaptive
coordination levels, progressive loading, campaign-state capsule, validation ladder, measurement
protocol, portable core, provider-adapter contracts, capability levels, cross-provider conformance
gates, acceptance gates, and delivery surfaces are explicit. Product implementation remains
separately authorized.

## Closeout Routing

- Current truth promoted to: pending final design; likely README.md, docs/operator-guide.md, a vendor-neutral core specification, skills/tool-shed/SKILL.md, and provider adapter documentation
- Historical context remains in: this workpackage and any later decision record
- Runtime/status evidence: future route, progressive-loading, installer, quality, efficiency, and cross-provider conformance tests
- Qualification evidence: work/evidence/evidence-tool-shed-provider-portability.md
- Cleanup deferred to: discussion transcript capture unless explicitly requested
