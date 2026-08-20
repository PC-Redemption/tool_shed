---
name: tool-shed
description: Route requests that explicitly begin with ts:, explicitly name Tool Shed, or explicitly ask to create or manage Tool Shed artifacts or campaign state. Do not activate from directory presence alone or for unrelated planning, coding, or conversation.
---

# Tool Shed

Use this skill as the portable routing layer for a workspace-local Tool Shed. The shed's files and
scripts—not this skill—are the source of templates, conventions, and project state.

## Portable Contract

Tool Shed behavior is provider-neutral. Use the current AI product's native instruction, file,
shell, permission, hook, and tool surfaces without pretending unsupported capabilities exist.

Capability levels are cumulative:

1. `Discussion`: analyze and recommend without durable workspace mutation.
2. `Planning`: read and create Tool Shed artifacts.
3. `Workspace`: edit files, run deterministic utilities, and validate results.
4. `Integrated`: use MCP, hooks, policies, permissions, or structured provider tools.
5. `Delivery`: plan, implement, build, deploy, and verify end to end.

State the supported product surface and level when compatibility matters. Files and Git remain
durable state. MCP is an optional integration surface, not a required Tool Shed server.

## Request Routing

Treat a leading `ts:` as authoritative Tool Shed routing for the current request only. Do not carry
the prefix forward. If a workspace also defines account or owner-work routes, obey those boundaries
and ask one concise routing question only when an unprefixed write could materially target either
destination.

Load only the route reference needed for the request:

| Request shape | Required reference |
| --- | --- |
| `ts: identity` or `ts: use <project-alias-or-path>` | this file only |
| discussion or campaign discovery | this file only |
| artifact selection, creation, completion, onboarding, or reconciliation | `references/artifact-workflows.md` |
| `ts:work1` through `ts:work5`, aliases, `ts:check`, `ts:ship`, `ts: doctor`, campaign execution, owner campaign queues, Program Roadmaps, `ts: overview`, `ts: build focus areas`, explicit App Server controls, `ts: help`, `ts: commands`, or `ts:ask` | `references/campaign-routes.md` |
| `ts: fulltsupgrade`, version, update, snapshot, or provider-specific reasoning maintenance | `references/maintenance-routes.md` |

Read a referenced file completely when its route applies. Do not load unrelated route references.

## Workspace Identity Boundary

Every installed workspace owns `work/tool-shed-project.json`, outside the reusable snapshot. Before
the first mutation in a session, run the workspace-local `project_identity.py identity` command for
the intended operation, surface its target capsule, and bind the session to that exact project ID
and resolved root. Pass its operation-specific `--project-binding` and only fresh state tokens from
the same target to mutation commands.

Treat missing, malformed, duplicate, conflicting, foreign-project, or root-mismatched identity as
a hard failure with no write. An absolute path outside the bound root is `WORKSPACE_MISMATCH`; path
mention or read-only inspection does not authorize switching. `ts: use <project-alias-or-path>` is
the explicit read-only switch route: verify the target identity, reload that target's instructions
and Tool Shed skill, and obtain fresh target-bound state. Generic edit and shell tools must not
bypass the same fence.

## Discussion Route

Treat `ts: discuss <topic>` as the authoritative Tool Shed discovery route. Treat a leading
`discussion:` as an informal read-only campaign-entry signal.

During discussion:

- Explore the desired outcome, motivation, constraints, assumptions, unknowns, and credible options.
- Do not create or modify artifacts unless the operator explicitly asks to capture or plan.
- Avoid forcing a form; include only campaign-seed fields that clarify the topic.
- End with the smallest useful next route: no action, answer, continued discussion, spike, decision
  matrix, ADR, checklist, ticket, workpackage, project map, or `ts:ship`.

A compact campaign seed may contain: outcome, why it matters, known constraints, assumptions,
unknowns, decisions already made, and next route.

## Minimum Sufficient Coordination

Start at the lowest adequate level and escalate only from evidence:

| Level | Typical shape | Default behavior |
| --- | --- | --- |
| Direct | clear, reversible, single-step | no artifact; execute and verify directly |
| Guided | bounded work with several known steps | checklist or ticket; targeted validation |
| Coordinated | multi-session, branching, dependency, or handoff cost | workpackage or project map; staged verification |
| Deep | consequential, difficult to reverse, highly uncertain, cross-layer, or repeatedly failing | research spike, controlled evidence, prospective failure checks, broader qualification |

Direct is the default for a clear, reversible bug fix or enhancement contained in one repository,
including when the request arrives through `ts:ask`. An explicit `Coordination: direct` or
`Route: direct` marker confirms that choice unless it conflicts with a higher-priority safety or
repository rule.

For Direct work:

1. Resolve the named repository and target once.
2. Implement the focused change.
3. Run focused, proportionate verification.
4. Expand orientation, artifacts, validation, or delivery only when the operator requested it,
   repository policy mandates it, or concrete risk, conflicting evidence, or an observed failure
   justifies it.

Do not create a ticket, checklist, workpackage, map, ADR, evidence artifact, branch, PR, release, or
new worktree merely because Tool Shed routed the request. Do not infer full-suite validation,
deployment, publication, or historical-worktree review from a bounded implementation request.
Campaign continuity keeps Direct work moving; it does not upgrade its coordination level.

Escalate for material ambiguity, consequence, irreversibility, repeated failure, coordination, or
handoff cost. De-escalate when the limiting uncertainty or coordination burden is resolved. Do not
select ceremony merely because a task sounds important.

For continuation, preserve only a compact state capsule: desired outcome, current limiting
condition, relevant decisions, latest evidence, authority boundary, and next action.

## Reasoning Preflight

Before substantial routed implementation, debugging, research, planning, or validation, perform
one zero-I/O reasoning preflight using only model and effort metadata already exposed by the
current provider and session. Do not run a command, read a cache, access the network, invoke another
model, or add a separate turn.

When a usable provider-specific model and effort pair is established, recommend the lowest adequate
pair in this exact format:

### **Reasoning: <model> / <effort>**

Do not guess names, claim to observe an active picker, pause merely for a change, or use abstract
tiers. Provider-specific selection and maintenance behavior belongs in
`references/maintenance-routes.md`; the optional Codex catalog is not portable core behavior.

Skip the preflight for conversation, help, version/status checks, and explicit continuations.

## Locate The Shed

1. If `tool_shed/selection.md` exists, use `tool_shed/` as the shed directory.
2. Else if `selection.md`, `conventions.md`, `templates/`, and `scripts/` exist at the workspace
   root, treat that root as the canonical development shed.
3. Else explain that Tool Shed must be installed before it can create artifacts or run workspace
   operations.

Always read `selection.md` and `conventions.md` before artifact work. Read `README.md` for install,
repository-boundary, or product questions; `existing-projects.md` for onboarding; and
`work/index.md` when existing work artifacts need orientation.

## Core Rules

- Choose the smallest artifact that fits the immediate work.
- Keep project artifacts under root `work/`, never inside the workspace-local shed.
- Keep owner-facing campaign lifecycle state under first-sorted `work/00-campaigns/`; keep `work/01-q&a/ask.txt` as transient intake.
- Keep opt-in strategic sequencing under `work/roadmaps/`; roadmap approval and campaign-plan approval are separate exact-token boundaries.
- Keep settled current truth in project docs or README files.
- Treat completed work artifacts as history, not canonical truth.
- Keep the workspace-local shed a disconnected, one-way snapshot; never develop inside it or push
  changes from it to the canonical repository.
- Track root `work/` by default. Ignore it only through the documented repository policy exception.
- Prefer deterministic shed scripts for artifact creation, indexing, completion, reconciliation,
  preflight, and version checks.
- Do not create a server, database, or tracker until plain files and scripts have demonstrated a
  concrete limitation.
- Preserve operator scope, authority, safety rules, credentials, protected environments, and
  unrelated work. A discovered action does not authorize itself.
- Use provider-native approvals and permissions as enforcement boundaries; instructions guide
  behavior but do not replace enforcement.

## Completion

After artifact lifecycle changes, refresh `work/index.md` and `work/index.json`, check stale paths,
and run the read-only work-state review. After source changes, run proportionate focused tests and
the repository's full validator. Do not claim delivery until the result is verified in its target
environment.
