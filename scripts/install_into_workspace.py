from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from codex_cli_resolver import CodexCliResolver, CodexReadiness
from codex_skill_sync import inspect_codex_skill, load_release_skill_digests
from provider_adapters import provider_config, provider_ids
from project_identity import (
    IDENTITY_RELATIVE_PATH,
    LEGACY_IDENTITY_PATHS,
    ProjectIdentityError,
    ensure_project_identity,
    load_project_identity,
    require_project_binding,
)
from repository_policy import POLICY_FILE, format_bytes, inspect_snapshot_ignore, inspect_work_ignore
from work_level_config import WorkLevelConfigError, validate_workspace_config
from work_tree import ensure_work_tree
from workspace_preflight import inspect


IGNORE_ENTRIES = (
    "/.tool-shed/",
    "/tool_shed/",
    "/tool_shed.backup-*.tar",
    "/work/01-q&a/ask.txt",
    "/work/01-q&a/*.legacy-*",
    "/work/q&a/ask.txt",
    "/work/evidence/generated/",
)

GUIDANCE_START = "<!-- BEGIN TOOL SHED GENERATED EVIDENCE GUIDANCE -->"
GUIDANCE_END = "<!-- END TOOL SHED GENERATED EVIDENCE GUIDANCE -->"
GUIDANCE = f"""{GUIDANCE_START}
## Tool Shed generated evidence

- Never request or render per-file Git diffs for raw generated evidence.
- Use `git status --untracked-files=no` for routine source review when generated evidence is present.
- Summarize evidence through small versioned manifests instead of returning raw output.
- Avoid passing hundreds of literal paths to `git diff --no-index`.
- Before long automated campaigns, verify generated-output directories are ignored.
- Run Tool Shed workspace preflight and use its profile-specific mitigation before bulk output.
- Never run migration apply without an exact approved manifest and verified archive.
- Commit or checkpoint meaningful source and planning changes before large test runs.
- Start or fork a fresh agent session after exceptionally large qualification campaigns.
{GUIDANCE_END}
"""

ROUTING_GUIDANCE_START = "<!-- BEGIN TOOL SHED ROUTING GUIDANCE -->"
ROUTING_GUIDANCE_END = "<!-- END TOOL SHED ROUTING GUIDANCE -->"
ROUTING_GUIDANCE = f"""{ROUTING_GUIDANCE_START}
## Tool Shed request routing

- Activate Tool Shed only when the request begins with `ts:`, explicitly names Tool Shed, or explicitly asks to create or manage Tool Shed artifacts or campaign state.
- Do not activate Tool Shed merely because `tool_shed/`, `work/`, or canonical Tool Shed repository files exist in the workspace.
- For an activated request, locate the workspace-local shed, then read its `skills/tool-shed/SKILL.md` before acting; load only the route reference that skill selects.
- If a separately installed or already-loaded Tool Shed skill differs from the workspace-local copy, report `TOOL_SHED_SKILL_MISMATCH`, use the workspace-local contract for this workspace, and recommend the documented update or synchronization route instead of combining both contracts.
- Keep project state in root `work/`; the workspace-local shed contains reusable machinery.
- Use only the provider capabilities actually available in the current product surface.
{ROUTING_GUIDANCE_END}
"""

DOCTOR_GUIDANCE_START = "<!-- BEGIN TOOL SHED DOCTOR GUIDANCE -->"
DOCTOR_GUIDANCE_END = "<!-- END TOOL SHED DOCTOR GUIDANCE -->"
DOCTOR_GUIDANCE = f"""{DOCTOR_GUIDANCE_START}
## Tool Shed workspace doctor

- Treat `ts: doctor` as a request to run the workspace-local `scripts/doctor.py --workspace .` read-only health audit.
- Report its single `HEALTHY`, `DEGRADED`, `NEEDS_DECISION`, or `INVALID` verdict, compact finding classes and counts, and exact next actions. Distinguish internally verified structure from external or runtime truth that was not observed.
- `--strict` fails unless fully healthy. `ts: doctor --repair` may regenerate deterministic work indexes only after source validation and exact current `doctor-repair` project-binding and state tokens; it never changes lifecycle state, chooses semantic truth, fabricates evidence, or applies reconciliation.
{DOCTOR_GUIDANCE_END}
"""

IDENTITY_GUIDANCE_START = "<!-- BEGIN TOOL SHED WORKSPACE IDENTITY GUIDANCE -->"
IDENTITY_GUIDANCE_END = "<!-- END TOOL SHED WORKSPACE IDENTITY GUIDANCE -->"
IDENTITY_GUIDANCE = f"""{IDENTITY_GUIDANCE_START}
## Tool Shed workspace identity boundary

- Before the first workspace mutation in a session, run the workspace-local `project_identity.py identity` command with the intended operation and surface its project name, stable project ID, resolved root, repository fingerprint, active campaign or operation, and session binding.
- Bind the session to that exact project ID and resolved root. Pass the returned operation-specific project binding and fresh project-bound state token to deterministic mutation commands.
- Treat any missing, malformed, duplicate, conflicting, foreign-project, or root-mismatched identity or token as a hard failure with no partial write.
- If a referenced absolute path resolves outside the bound root, output `WORKSPACE_MISMATCH` and stop. A path mention or read-only inspection is evidence, not authorization to switch workspaces.
- Treat `ts: use <project-alias-or-path>` as the only explicit workspace-switch route. Verify the target identity, reload that target's instructions and Tool Shed skill, and obtain fresh target-bound state before acting.
- Apply the same fence to generic file-editing and shell tools; they may not bypass the identity checks enforced by lifecycle scripts. Read-only cross-project inspection never changes the active binding.
{IDENTITY_GUIDANCE_END}
"""

AUTONOMY_GUIDANCE_START = "<!-- BEGIN TOOL SHED AUTONOMY GUIDANCE -->"
AUTONOMY_GUIDANCE_END = "<!-- END TOOL SHED AUTONOMY GUIDANCE -->"
AUTONOMY_GUIDANCE = f"""{AUTONOMY_GUIDANCE_START}
## Tool Shed persistent autonomy and authority envelope

- Treat `ts: autonomy <0-5>` as the canonical persistent project-bound setting and exact numeric `ts: approve <0-5>` as its compatibility alias. Resolve `status`, `set`, `reset`, and action evaluation with the workspace-local `scripts/autonomy_control.py`.
- Effective authority is the intersection of explicit outcome and scope, requested work1-work5 endpoint, known target, autonomy level, and provider policy. Autonomy controls interruptions; it never invents work, broadens scope, raises the endpoint, resolves an unknown target, or waives provider controls.
- Continue automatically when a faithful, reversible action is covered. Project-map and roadmap acceptance, campaign-plan materialization, queue transitions, execution, evidence gates, and completion are not human approval gates merely because they use separate artifacts, phases, or tokens.
- Keep fresh identity, proposal, manifest, state, and project-binding tokens as internal concurrency controls. The agent obtains and passes them; do not require the operator to copy a token for a covered transition. Preserve explicit token commands for manual level-0 operation and compatibility.
- Interrupt only for material scope expansion, unresolved meaningful decisions, unknown or mismatched targets, credentials or authentication changes, cross-workspace or account actions, purchases or legal commitments, broad destructive or irreversible operations, or provider-native protected boundaries.
- Every legitimate interrupt states the action, why the envelope does not cover it, impact, blast radius, rollback, and recommendation inline. Missing, malformed, stale, or foreign preference state fails safely to level 0.
{AUTONOMY_GUIDANCE_END}
"""

DISCUSSION_GUIDANCE_START = "<!-- BEGIN TOOL SHED DISCUSSION GUIDANCE -->"
DISCUSSION_GUIDANCE_END = "<!-- END TOOL SHED DISCUSSION GUIDANCE -->"
DISCUSSION_GUIDANCE = f"""{DISCUSSION_GUIDANCE_START}
## Tool Shed discussion route

- Treat `ts: discuss <topic>` as the authoritative Tool Shed discovery route.
- Treat a leading `discussion:` as an informal, read-only campaign-entry signal.
- Explore the outcome, motivation, constraints, assumptions, unknowns, and smallest useful next route.
- Do not create or modify workspace artifacts unless the operator explicitly asks to capture or plan.
{DISCUSSION_GUIDANCE_END}
"""

BRAINSTORM_GUIDANCE_START = "<!-- BEGIN TOOL SHED BRAINSTORM GUIDANCE -->"
BRAINSTORM_GUIDANCE_END = "<!-- END TOOL SHED BRAINSTORM GUIDANCE -->"
BRAINSTORM_GUIDANCE = f"""{BRAINSTORM_GUIDANCE_START}
## Tool Shed Brainstorm / Idea Brief route

- Treat `ts: brainstorm <idea>` as the durable pre-PRM Discovery Cycle and `ts: bs <idea>` as its exact alias. A bare form lists active Idea Briefs without mutation.
- The route authorizes creating or updating one tracked `work/ideas/idea-*.md` Idea Brief, not a project map, roadmap, campaign, product change, deployment, or publication.
- Before creating, compare existing Idea Brief titles and current syntheses. Resume one clear material match, create with `python3 <shed>/scripts/new_artifact.py idea \"Title\" --workspace <workspace>` when none matches, and ask one concise choice if multiple briefs plausibly match.
- Keep a concise current synthesis above useful dated exploration notes. Preserve possibilities, tradeoffs, constraints, non-goals, reminders, assumptions, open questions, owner notes, and decisions without requiring every section to be complete.
- Use `exploring`, `ready-for-prm`, `promoted`, or `parked` status. Idea Briefs are indexed but excluded from campaign reconciliation.
- Semantic readiness review has exactly two triggers: explicit `ts: bs review <idea-id-or-path>`, and `ts: prm idea <idea-id-or-path>` when no current ready result exists. Ordinary brainstorming, listing, status, rendering, startup, and background work may compare freshness metadata but never perform semantic review.
- For either trigger, the agent makes the provider-neutral semantic judgment and uses `<shed>/scripts/idea_readiness.py` to prepare, validate, and apply the revision-bound result. `NOT-READY` engages the operator on material blockers; `REVIEW-ERROR` and `REVIEW-UNAVAILABLE` fail promotion closed. Resume interrupted dialogue against the prior result digest without repeating settled questions.
- Treat `ts: prm idea <idea-id-or-path>` as PRM sourced from that brief. Reuse only a `CURRENT-READY` result. Before accepting derived map or roadmap state, copy its digest, reviewed Idea identity/revision/hash, and complete sorted gate IDs into metadata and require `idea_readiness.py transfer-check` to pass with zero missing, extra, renamed, or dropped gates. Keep the brief `ready-for-prm` until settled project-map direction captures it, then set `promoted` and name that map in `Produces:`. Promotion preserves provenance and does not independently expand the active authority envelope.
- Brainstorming is GUI-native even when the persistent App Server preference is on; reject explicit `--app-server` rather than switching execution backends.
{BRAINSTORM_GUIDANCE_END}
"""

HELP_GUIDANCE_START = "<!-- BEGIN TOOL SHED HELP GUIDANCE -->"
HELP_GUIDANCE_END = "<!-- END TOOL SHED HELP GUIDANCE -->"
HELP_GUIDANCE = f"""{HELP_GUIDANCE_START}
## Tool Shed help route

- For `ts: help`, read the workspace-local operator guide and return a concise use-case menu. For `ts: commands` or `ts: help all`, read the local command reference and return its complete groups and usage. For `ts: help <topic-or-command>`, read the relevant local command and operator-guide sections and return focused usage and examples.
- Every `ts: help`-family response must visibly include `Browse Tool Shed help: https://ts.rookaro.com/`.
- `ts: commands` and `ts: help all` responses must also include `Browse the complete command reference: https://ts.rookaro.com/ref/`.
- A focused response may add a defined stable topic URL, but it must retain the root help link.
- Public links supplement local offline help. Never replace the local reads, perform a request-time network check, or make rendering depend on site availability.
{HELP_GUIDANCE_END}
"""

COORDINATION_GUIDANCE_START = "<!-- BEGIN TOOL SHED COORDINATION GUIDANCE -->"
COORDINATION_GUIDANCE_END = "<!-- END TOOL SHED COORDINATION GUIDANCE -->"
COORDINATION_GUIDANCE = f"""{COORDINATION_GUIDANCE_START}
## Tool Shed minimum sufficient coordination

- Apply KISS as minimum sufficient complexity: choose the smallest complete solution that satisfies the current outcome, safety boundaries, and proven constraints.
- Reuse existing mechanisms. Add artifacts, abstractions, dependencies, layers, compatibility scope, tests, or future-proofing only when a current requirement, concrete risk, or observed failure justifies them; then add the smallest bounded amount and reevaluate.
- KISS does not waive correctness, safety, credible verification, or authority, and it does not create a required field, checklist, or approval gate.
- Start at the lowest adequate level: Direct, Guided, Coordinated, or Deep.
- Default a clear, reversible, single-repository bug fix or enhancement to Direct, including when it arrives through `ts:ask`.
- For Direct work, orient to the named target once, implement the focused change, and run focused, proportionate verification.
- Do not create artifacts, branches, PRs, releases, deployments, broad qualification, or new worktrees for Direct work unless explicitly requested, mandated by repository policy, or justified by concrete risk, conflicting evidence, or observed failure.
- Escalate only when evidence shows ambiguity, consequence, irreversibility, repeated failure, coordination, or handoff cost.
- Load route-specific instructions and references only when the route needs them.
- Preserve a compact campaign state: outcome, current constraint, decisions, evidence, and next action.
{COORDINATION_GUIDANCE_END}
"""

WORK_LEVEL_GUIDANCE_START = "<!-- BEGIN TOOL SHED WORK LEVEL GUIDANCE -->"
WORK_LEVEL_GUIDANCE_END = "<!-- END TOOL SHED WORK LEVEL GUIDANCE -->"
WORK_LEVEL_GUIDANCE = f"""{WORK_LEVEL_GUIDANCE_START}
## Tool Shed numbered work levels

- Treat `ts:work1` through `ts:work5` as cumulative execution endpoints, independent of Direct, Guided, Coordinated, or Deep coordination.
- `work1`: implement, run the quickest meaningful check, checkpoint only requested changes in a local commit, leave the worktree clean when unrelated prior changes permit, and stop without deployment.
- `work2`: perform `work1`, deploy to the configured work environment, run focused browser and changed-behavior checks, checkpoint, and stop.
- `work3`: review the accumulated coded work and create, read, update, or delete project documentation as needed so it matches the candidate; then fully validate and build, update and verify the work environment when relevant, freeze it locally, and stop.
- `work4`: perform `work3`, then push without intentionally releasing or promoting production.
- `work5`: qualify, push, release or promote production, and verify the production target; this is equivalent to explicit `ts:ship`.
- Aliases are `ts:work` = `work2`, `ts:freeze` = `work3`, `ts:push` = `work4`, and `ts:ship` = `work5`. `ts:check <spot|focused|full|release>` validates only and does not mutate source, Git, or environments.
- Before executing a work-level route, resolve its optional tracked workspace customization with `python3 tool_shed/scripts/work_level_config.py --workspace . resolve <route> --json` (use the canonical checkout's `scripts/` path when developing Tool Shed itself). Apply the selected canonical level's ordered `before` actions, its standard behavior unless `run_default: false`, then its ordered `after` actions. Aliases use the canonical level's single envelope; lower-level envelopes do not run separately.
- Read optional tracked project state from `work/tool-shed.yaml`. `work_model: combined` means work and production share a target, so state that `work2` or `work3` may change the live site. `work_model: split` keeps `work2` and `work3` on development and reserves production promotion for `work5`. Missing customization preserves standard behavior; invalid configuration stops the route.
- Report configured actions and explicit default suppression before acting. Run actions in declaration order and stop on the first failure. Invoking the route includes its declared in-scope actions, but configuration cannot bypass scope, credentials, the active authority envelope, destructive-action safeguards, or protected-environment controls.
- Reuse existing workspace tooling. The config is not a credential store, deployment framework, or authority grant. If absent, preserve existing behavior and ask one concise target question only when safe routing cannot be derived. Reject invalid schemas or modes rather than guessing.
- Preserve unrelated pre-existing changes. If they prevent a clean checkpoint, report it. If a `work4` push automatically deploys production, stop before pushing unless production release is explicitly authorized.
{WORK_LEVEL_GUIDANCE_END}
"""

SHIP_GUIDANCE_START = "<!-- BEGIN TOOL SHED SHIP GUIDANCE -->"
SHIP_GUIDANCE_END = "<!-- END TOOL SHED SHIP GUIDANCE -->"
SHIP_GUIDANCE = f"""{SHIP_GUIDANCE_START}
## Tool Shed ship route

- Treat `ts:ship <goal>` and `ts: ship <goal>` as authorization to plan, implement, validate, build, deploy, and verify the workspace goal end-to-end.
- Treat `ts: fulltsupgrade` and `ts:fulltsupgrade` as authorization to upgrade the current existing Tool Shed installation end-to-end from the latest verified published GitHub release, including guarded backup and update, provider convergence, exact release qualification plus focused client smoke (with full local validation for overridden, unattested, or changed identities), installed Codex skill synchronization and exact verification when applicable, and rollback on failure.
- The full-upgrade route does not authorize publishing a release, rewriting history, overwriting a modified or unmanaged installation, deleting unknown recovery material, or changing other workspaces or fleet targets.
- Treat lifecycle stages as applicable only when the requested outcome includes them, repository policy mandates them, or concrete risk or observed failure justifies them. Wording that merely mentions or discusses `ts:ship` is not an end-to-end delivery request.
- State the concrete reason before expanding focused verification into broad qualification, deployment, or external publication.
- Continue through every applicable lifecycle stage; do not stop merely because planning, coding, tests, or a build succeeded.
- Use the workspace's own tooling, environments, runbooks, and protected-environment controls.
- Keep changes scoped to the goal and preserve unrelated user work.
- Do not ask for repeated confirmation for reversible, in-scope steps already clearly authorized by the operator. One request may authorize multiple named operations. Ask again only when an action materially expands scope, targets a protected environment, is destructive or irreversible, uses an unknown deployment target, publishes externally, or otherwise requires new authority.
- Before an already-authorized consequential stage, identify at most three credible ways the plan could fail and add proportionate prevention, detection, verification, or rollback. Skip this check for routine reversible work.
- Verify the delivered result in its target environment before claiming completion.
- The route does not waive safety rules, credential boundaries, provider controls, or authorization limits.
- If a stage is inapplicable, explain why. If deployment is blocked, complete every safe preceding stage and report the exact blocker.
{SHIP_GUIDANCE_END}
"""

EXECUTION_GUIDANCE_START = "<!-- BEGIN TOOL SHED EVIDENCE RESPONSE GUIDANCE -->"
EXECUTION_GUIDANCE_END = "<!-- END TOOL SHED EVIDENCE RESPONSE GUIDANCE -->"
EXECUTION_GUIDANCE = f"""{EXECUTION_GUIDANCE_START}
## Tool Shed evidence-response loop

- Use the loop for nontrivial planning, implementation, debugging, research, validation, and deployment.
- Keep the desired outcome and the current condition limiting progress visible.
- After each material action or new observation, compare the actual state with the expected state. If they differ, update assumptions, the plan, and the next action before continuing; command success alone is not outcome success.
- Preserve the operator's scope, authority, and safety boundaries while adapting. A newly discovered action does not authorize itself.
- Skip explicit loop ceremony for simple answers and known single-step reversible work; execute and verify them directly.
{EXECUTION_GUIDANCE_END}
"""

CAMPAIGN_GUIDANCE_START = "<!-- BEGIN TOOL SHED CAMPAIGN GUIDANCE -->"
CAMPAIGN_GUIDANCE_END = "<!-- END TOOL SHED CAMPAIGN GUIDANCE -->"
CAMPAIGN_GUIDANCE = f"""{CAMPAIGN_GUIDANCE_START}
## Tool Shed campaign continuity

- Treat the requested outcome in the current chat as the campaign. Plans, checklists, workpackages, tests, builds, and deployments are possible stages or artifacts, not the campaign itself.
- Keep working while the next action is reversible, in scope, and already authorized. A progress summary, artifact update, phase boundary, or useful review point is not an approval gate.
- Preserve the selected coordination level while continuing; campaign continuity does not upgrade Direct work or make inapplicable lifecycle stages apply.
- Do not stop because the operator might want to inspect completed work. Pause only for requested review, a material unresolved decision, contradictory evidence, new authority, or a protected, destructive, irreversible, or not-yet-authorized external action.
- If review is required, identify the exact file or result and relevant section, state the exact decision or approval needed, and say what happens after the response. Never use a vague "review this" or "let me know."
- End every final response for a Tool Shed campaign with exactly one verdict: `Campaign status: COMPLETE`, `Campaign status: CONTINUE`, or `Campaign status: BLOCKED`.
- `COMPLETE` means the whole requested outcome and applicable verification are finished, not merely an artifact or intermediate stage.
- `CONTINUE` means work remains but the current turn must end without needing operator input; name the next concrete action. Do not stop if that action can safely be performed now.
- `BLOCKED` means progress requires a named decision, dependency, permission, credential, external-state change, or required review; state the blocker and precise operator action.
{CAMPAIGN_GUIDANCE_END}
"""

ASK_GUIDANCE_START = "<!-- BEGIN TOOL SHED Q&A GUIDANCE -->"
ASK_GUIDANCE_END = "<!-- END TOOL SHED Q&A GUIDANCE -->"
ASK_GUIDANCE = f"""{ASK_GUIDANCE_START}
## Tool Shed Q&A inbox

- Treat `ts:ask` and `ts: ask` as requests to run `python3 <shed>/scripts/read_ask_inbox.py --workspace <workspace> --json`.
- The canonical inbox is `work/01-q&a/ask.txt`; inspect `work/q&a/ask.txt` only as a pre-migration legacy fallback.
- Ignore blank lines and lines beginning with `#` in both files.
- Use canonical content when only it is actionable. If only fallback content is actionable, process it and clearly report its noncanonical location.
- If both files are actionable, do not merge or act on either; report the conflict and ask which request to use.
- Apply normal scope, authorization, safety, and routing rules to the selected request.
- Dispatch the selected request under its natural coordination level; `ts:ask` does not turn a bounded Direct request into a heavyweight campaign.
- Never move, clear, rewrite, or delete either inbox without explicit operator authorization.
- Summarize what was read and what was done in the final response.
{ASK_GUIDANCE_END}
"""

CAMPAIGN_QUEUE_GUIDANCE_START = "<!-- BEGIN TOOL SHED OWNER CAMPAIGN GUIDANCE -->"
CAMPAIGN_QUEUE_GUIDANCE_END = "<!-- END TOOL SHED OWNER CAMPAIGN GUIDANCE -->"
CAMPAIGN_QUEUE_GUIDANCE = f"""{CAMPAIGN_QUEUE_GUIDANCE_START}
## Tool Shed owner campaign queue

- Keep durable owner-facing campaign state under first-sorted `work/00-campaigns/`; keep `work/01-q&a/ask.txt` as transient intake.
- Treat `ts: queue` and `ts: status` as requests to read the active owner capsule and validate lifecycle state.
- Treat bare `ts: next` as a request to resume the working campaign or select the first ready campaign, then execute only that campaign under its natural coordination and requested work level.
- Resolve eligible App Server execution in this order: one-command `--gui`, strict one-command `--app-server`, the protected user-local preference changed by `ts: app-server on|off` (`appserver` alias), then the committed GUI default. A fresh schema-v2 `on` is operator-runtime trust for supported local roles, including bounded CAMP; unknown or updated Codex versions do not require positive qualification or executable-hash certification. Only an exact evidence-backed `unqualified` registry record denies a version in normal mode. Keep discussion, brainstorming, qualification workflows, and unsupported work GUI-native. Store preference state only under Codex home, never in a workspace or installed snapshot.
- In persistent mode, selection, authentication, qualification, startup, network, model, read-only preparation, and other pre-mutation failures must record a sanitized event and continue the same action immediately in GUI without operator interaction. If mutation is possible, reconcile the existing mutation journal and Git state in GUI before continuing and never replay the App Server step. Append only timestamp, route, outcome, controlled category, mutation state, backend, preference mode, and strict-request flag under Codex home; never prompts, responses, raw tool output, credentials, secrets, exception text, or repository content. Logging failure never blocks fallback. Explicit `--app-server` remains fail-closed.
- When `ts: next` resolves to App Server, invoke `python3 <shed>/scripts/app_server_dispatch.py --workspace . next --json` directly; `ts: next --app-server` adds the strict `--app-server` option. Never wrap either form in `codex exec` or another Codex agent. The dispatcher must reuse normal `next` navigation and an existing valid capsule. When a ready campaign has no capsule, it assembles a deterministic focused snapshot from the campaign, project instructions, Git state, relevant file inventory, and bounded source excerpts; gives only that isolated snapshot to the supported read-only planning role without tools; validates and persists the resulting strict capsule through the guarded campaign transaction; and continues to the existing bounded Terra/medium `camp-run` path in the same invocation. The actual role operation performs startup, ChatGPT authentication, live-model, and requested-sandbox checks; do not add a parallel preflight system. Unsafe or indeterminate preparation fails before mutation. Do not make `next` a role, change its selection, force GUI-native or non-executable work through CAMP execution, bypass compatibility, or add API fallback.
- Use one shared Cycle State Capsule in `overview`, `status`, and `next`: Program Cycle → Milestone Wave Cycle → Queue Cycle → Campaign Cycle → Evidence Loop. Completing an inner cycle returns control upward and never proves an outer cycle complete.
- Compute work origin independently from coordination and work1-work5: no queue record is direct; Roadmap traceability is roadmap-derived; Detour For/Return To is detour; other queued work is owner-originated. Do not reuse `Campaign: standalone` as an origin.
- When bare `next` has no ready campaign, report the owning cycle and exact safe transition: Dangler Resolution, current campaign-plan authority evaluation, incomplete milestone/gate work, next-milestone derivation, roadmap drift review, completed roadmap, or no higher-level driver. Continue an unambiguous covered transition automatically; never infer a material decision or bypass the active envelope from this projection.
- Treat `ts: next 1,2` and `ts: next que 1,2` as ordered queue-position batches, `ts: next camp 025,example-id` as an ordered stable campaign-number-or-ID batch, and `ts: next *` as every campaign in one fresh validated active-queue snapshot. Resolve the complete selection to stable IDs before execution, reject duplicates or invalid targets, retain the snapshot so wildcard excludes later additions, resume a selected working campaign first, and run sequentially with at most one working campaign. After each passed completion gate, complete through the guarded lifecycle command, refresh and validate campaign/index/stale-path/work state, and recompute readiness. Stop at the first failure, blocker, decision, stale state, dependency, protected action, or authority boundary and report completed and remaining IDs with the exact resume point. Batch scope never grants work5, deployment, release, production promotion, destructive, credential, or other consequential authority.
- In owner-queue requests, interpret `camp` as `campaign`. Interpret `que N` as the mutable 1-based queue position, resolved from a fresh status read; a heading such as `1. (004) Title` distinguishes queue position 1 from stable campaign number 004, and every card separately displays its full stable `Campaign ID`. Name lifecycle requests `<number>-<campaign-id>.md`, preserve matching numeric ID prefixes, use guarded `backfill-numbers` to rename legacy slug-only histories and refresh projections, and accept an exact zero-padded number or full Campaign ID for lifecycle commands. Never guess a missing or out-of-range position.
- Treat `ts: add`, `ts: unblock`, `ts: defer`, `ts: abandon`, and campaign completion as exact state-token-guarded lifecycle mutations. `ts: unblock` returns blocked work to queued state and clears its decision. Continue into start only when the same outcome, endpoint, and autonomy envelope cover it. Read the current state token immediately before writing and reject stale state.
- Treat `ts: reconcile campaigns` as authorization for `reconcile_campaign_queue.py` to automatically create or refresh exactly one Dangler Resolution campaign as the first queued work while preserving any working campaign. Report whole-work coverage, exclusions, and queue drift. Use `--dry-run` for read-only inspection. Apply other unambiguous reversible operations from an exact current manifest when the autonomy envelope covers them; never apply proposed execution order or ambiguous lifecycle decisions implicitly.
- Never silently reorder a campaign when priority or direction is ambiguous. Preserve blocked work as active; require a reason and reactivation condition for deferral and a disposition for abandonment.
- Complete a campaign only after its explicit completion gate and applicable verification pass. Then update active and completed queues as one recoverable operation and promote the next ready campaign.
- Treat `work/focus-areas.md` as an optional project-specific catalog. Onboarding creates it as proposed; resolve its authority before it governs campaign assignments or queue cards. Derive areas from project evidence rather than a built-in taxonomy.
- Treat `ts: build focus areas` as an evidence-backed catalog and assignment route. Apply a faithful reversible proposal automatically under planning autonomy; request a decision for material ownership, split, merge, responsibility, or priority choices.
- After authority resolution, write the approved catalog, apply all active-campaign assignments, refresh indexes, and validate campaign, stale-path, and work state. Preserve stable IDs and accepted boundaries unless cited project evidence justifies a named change; never infer a material taxonomy decision or leave approved active work unmapped.
- When an approved catalog exists, require known primary focus-area IDs for ordinary active campaigns, keep supporting IDs optional, and use the shared dependency/decision readiness states for status, selection, rendering, and reconciliation.
- Preview legacy outcome focus phrases without writing; apply only fully matched focus assignments through an exact current reconciliation manifest after authority-envelope evaluation.
- The workspace installer migrates legacy `work/q&a/` and root `q&a/` contents into `work/01-q&a/` without overwriting collisions, then removes the old folders. Campaign conversion remains preview-only until an exact manifest is explicitly approved.
{CAMPAIGN_QUEUE_GUIDANCE_END}
"""

ROADMAP_GUIDANCE_START = "<!-- BEGIN TOOL SHED PROGRAM ROADMAP GUIDANCE -->"
ROADMAP_GUIDANCE_END = "<!-- END TOOL SHED PROGRAM ROADMAP GUIDANCE -->"
ROADMAP_GUIDANCE = f"""{ROADMAP_GUIDANCE_START}
## Tool Shed Program Roadmaps

- `PRM` means Plan → Roadmap → Milestone: the complete outer Tool Shed coordination lifecycle from understood intent and settled project direction, through a state-token-guarded Program Roadmap, to successive evidence-gated milestone waves. An optional Brainstorm / Discovery Cycle precedes PRM when an idea needs durable multi-session exploration. Treat `ts: prm <outcome>` as a request to continue that full lifecycle through every covered transition until the outcome and applicable gates pass or genuine owner intervention is required.
- Treat `ts: prm idea <idea-id-or-path>` as PRM sourced from one selected `work/ideas/idea-*.md` brief. Run readiness status first, reuse only `CURRENT-READY`, and trigger the adaptive review when no current ready result exists. Preserve its unknowns and provenance; mark it promoted with the approved project map in `Produces:` only after that map captures its direction and exact readiness gate transfer passes.
- Apply KISS through PRM: plan the smallest valuable outcome, use the fewest necessary milestones and evidence gates, and make each milestone the smallest independently useful, verifiable slice.
- The PRM Plan Cycle settles intent and project-map direction; its Roadmap Cycle is the human-facing name for the existing Program Cycle; and its Milestone Cycle is the human-facing name for the existing Milestone Wave Cycle. PRM contains rather than replaces the Queue, Campaign, and Evidence cycles, and stable machine-facing cycle-state names remain unchanged.
- PRM is not blanket authority. It automatically accepts faithful derived maps, roadmaps, campaign plans, materialization, and lifecycle transitions when the active authority envelope covers them; it never publishes or deploys beyond the requested endpoint or crosses protected, credential, destructive, or unknown-target boundaries. An empty queue or completed inner artifact does not complete PRM; the intended outcome and applicable gates must pass.
- Treat `ts: develop roadmap`, `ts: propose roadmap`, `ts: approve roadmap <token>`, `ts: derive campaigns for milestone <id>`, `ts: approve campaign plan <token>`, `ts: roadmap status`, `ts: review roadmap`, and `ts: overview` as the opt-in Program Roadmap lifecycle between project maps and campaigns.
- Keep development, review, campaign derivation, status, and overview read-only. A roadmap proposal may create only a proposed `work/roadmaps/` revision; it cannot approve intent or create campaigns.
- Require settled initial project-map direction for greenfield adoption. Existing or upgraded projects may use an active map and must preserve and classify all owner-authored work as completed, active, remaining, superseded, excluded, or uncertain from evidence.
- Roadmap and campaign-plan mutations retain separate exact state tokens, but those tokens do not create separate human approval gates. Apply faithful covered transitions automatically, reject stale source, roadmap, or campaign state, and preserve superseded approved revisions.
- Materialized campaigns must reference their Roadmap, Roadmap Revision, Milestone, and Unlocks Gate. Continue into execution only when the same requested outcome, endpoint, target, and autonomy envelope cover it.
- Installation and upgrade create only the empty compatible topology. They never ingest work, propose or approve a roadmap, or materialize campaigns implicitly.
{ROADMAP_GUIDANCE_END}
"""

GUIDANCE_BLOCKS = (
    (ROUTING_GUIDANCE_START, ROUTING_GUIDANCE_END, ROUTING_GUIDANCE),
    (DOCTOR_GUIDANCE_START, DOCTOR_GUIDANCE_END, DOCTOR_GUIDANCE),
    (IDENTITY_GUIDANCE_START, IDENTITY_GUIDANCE_END, IDENTITY_GUIDANCE),
    (AUTONOMY_GUIDANCE_START, AUTONOMY_GUIDANCE_END, AUTONOMY_GUIDANCE),
    (DISCUSSION_GUIDANCE_START, DISCUSSION_GUIDANCE_END, DISCUSSION_GUIDANCE),
    (BRAINSTORM_GUIDANCE_START, BRAINSTORM_GUIDANCE_END, BRAINSTORM_GUIDANCE),
    (HELP_GUIDANCE_START, HELP_GUIDANCE_END, HELP_GUIDANCE),
    (COORDINATION_GUIDANCE_START, COORDINATION_GUIDANCE_END, COORDINATION_GUIDANCE),
    (GUIDANCE_START, GUIDANCE_END, GUIDANCE),
    (WORK_LEVEL_GUIDANCE_START, WORK_LEVEL_GUIDANCE_END, WORK_LEVEL_GUIDANCE),
    (SHIP_GUIDANCE_START, SHIP_GUIDANCE_END, SHIP_GUIDANCE),
    (EXECUTION_GUIDANCE_START, EXECUTION_GUIDANCE_END, EXECUTION_GUIDANCE),
    (CAMPAIGN_GUIDANCE_START, CAMPAIGN_GUIDANCE_END, CAMPAIGN_GUIDANCE),
    (ASK_GUIDANCE_START, ASK_GUIDANCE_END, ASK_GUIDANCE),
    (
        CAMPAIGN_QUEUE_GUIDANCE_START,
        CAMPAIGN_QUEUE_GUIDANCE_END,
        CAMPAIGN_QUEUE_GUIDANCE,
    ),
    (ROADMAP_GUIDANCE_START, ROADMAP_GUIDANCE_END, ROADMAP_GUIDANCE),
)


def ensure_root_gitignore(repository: Path) -> list[str]:
    path = repository / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    existing_lines = {line.strip() for line in existing.splitlines()}
    missing = [entry for entry in IGNORE_ENTRIES if entry not in existing_lines]
    if not missing:
        return []
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    block = prefix + "\n# Tool Shed workspace-local and generated outputs\n" + "\n".join(missing) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(block)
    return missing


def replace_managed_block(existing: str, start: str, end: str, replacement: str) -> tuple[str, bool]:
    start_index = existing.find(start)
    end_index = existing.find(end, start_index + len(start)) if start_index >= 0 else -1
    if start_index >= 0 and end_index >= 0:
        end_index += len(end)
        updated = existing[:start_index] + replacement.rstrip("\n") + existing[end_index:]
        return updated, updated != existing
    if start_index >= 0:
        updated = existing[:start_index] + replacement
        return updated, updated != existing
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    updated = existing + prefix + ("\n" if existing else "") + replacement
    return updated, True


def remove_managed_block(existing: str, start: str, end: str) -> tuple[str, bool]:
    """Remove every complete managed block without rewriting surrounding owner text."""
    updated = existing
    changed = False
    while True:
        start_index = updated.find(start)
        if start_index < 0:
            return updated, changed
        end_index = updated.find(end, start_index + len(start))
        if end_index < 0:
            raise ValueError(f"managed guidance block is missing its end marker: {start}")
        end_index += len(end)
        updated = updated[:start_index] + updated[end_index:]
        changed = True


def ensure_provider_guidance(repository: Path, provider_id: str) -> tuple[Path, bool]:
    config = provider_config(provider_id)
    path = repository / str(config["instruction_path"])
    current = path
    while current != repository:
        if current.is_symlink():
            raise ValueError(f"provider instruction path must not traverse a symlink: {current}")
        current = current.parent
    try:
        path.resolve(strict=False).relative_to(repository.resolve())
    except ValueError as error:
        raise ValueError(f"provider instruction path escapes the repository: {path}") from error
    if path.exists() and not path.is_file():
        raise ValueError(f"provider instruction target must be a regular file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if config["instruction_format"] == "mdc" and not existing:
        existing = "---\ndescription: Tool Shed workspace coordination\nalwaysApply: true\n---\n"
    updated = existing
    if provider_id == "codex":
        updated, _ = replace_managed_block(
            updated,
            ROUTING_GUIDANCE_START,
            ROUTING_GUIDANCE_END,
            ROUTING_GUIDANCE,
        )
        for start, end, _ in GUIDANCE_BLOCKS[1:]:
            updated, _ = remove_managed_block(updated, start, end)
    else:
        for start, end, guidance in GUIDANCE_BLOCKS:
            updated, _ = replace_managed_block(updated, start, end, guidance)
    if updated == existing:
        return path, False
    path.write_text(updated, encoding="utf-8", newline="\n")
    return path, True


def ensure_ask_inbox(workspace: Path) -> bool:
    path = workspace / "work" / "01-q&a" / "ask.txt"
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Put a question or direction below, then send ts:ask to your AI agent.\n",
        encoding="utf-8",
    )
    return True


def _collision_path(target: Path, label: str, content: bytes, claimed: dict[Path, bytes]) -> Path:
    if target not in claimed and not target.exists():
        return target
    existing = claimed.get(target)
    if existing is None and target.is_file():
        existing = target.read_bytes()
    if existing == content:
        return target
    candidate = target.with_name(f"{target.stem}.{label}{target.suffix}")
    counter = 2
    while candidate in claimed or candidate.exists():
        existing = claimed.get(candidate)
        if existing is None and candidate.is_file():
            existing = candidate.read_bytes()
        if existing == content:
            return candidate
        candidate = target.with_name(f"{target.stem}.{label}-{counter}{target.suffix}")
        counter += 1
    return candidate


def migrate_legacy_q_and_a(workspace: Path) -> list[tuple[Path, Path]]:
    target_root = workspace / "work" / "01-q&a"
    sources = (
        (workspace / "work" / "q&a", "legacy-work-q-and-a"),
        (workspace / "q&a", "legacy-root-q-and-a"),
    )
    mappings: list[tuple[Path, Path]] = []
    claimed: dict[Path, bytes] = {}
    for source_root, label in sources:
        if not source_root.exists():
            continue
        if source_root.is_symlink() or not source_root.is_dir():
            raise ValueError(f"legacy Q&A source must be a real directory: {source_root}")
        for path in sorted(source_root.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"legacy Q&A migration refuses symlink: {path}")
            if path.is_dir():
                continue
            if not path.is_file():
                raise ValueError(f"legacy Q&A migration found unsupported entry: {path}")
            content = path.read_bytes()
            destination = _collision_path(target_root / path.relative_to(source_root), label, content, claimed)
            claimed[destination] = content
            mappings.append((path, destination))

    created: list[Path] = []
    try:
        for source, destination in mappings:
            content = source.read_bytes()
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.copy2(source, destination)
                created.append(destination)
            if not destination.is_file() or destination.read_bytes() != content:
                raise ValueError(f"legacy Q&A copy verification failed: {source} -> {destination}")
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise

    for source, _ in mappings:
        source.unlink()
    for source_root, _ in sources:
        if source_root.is_dir():
            for directory in sorted(
                (path for path in source_root.rglob("*") if path.is_dir()),
                key=lambda path: len(path.parts),
                reverse=True,
            ):
                directory.rmdir()
            source_root.rmdir()
    return mappings


def existing_generated_outputs(repository: Path) -> tuple[int, int]:
    paths = [
        path
        for path in (repository / "work" / "evidence" / "generated").rglob("*")
        if path.is_file()
    ] if (repository / "work" / "evidence" / "generated").exists() else []
    paths.extend(path for path in repository.glob("tool_shed.backup-*.tar") if path.is_file())
    return len(paths), sum(path.stat().st_size for path in paths)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the project work artifact tree.")
    parser.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Project workspace root. Defaults to current directory.",
    )
    choices = (*provider_ids(), "all")
    parser.add_argument(
        "--provider",
        action="append",
        choices=choices,
        help=(
            "Install native guidance for a provider. Repeat for multiple providers or use 'all'. "
            "Defaults to codex for backward compatibility."
        ),
    )
    parser.add_argument(
        "--guidance-only",
        action="store_true",
        help="Refresh provider instruction blocks without changing work/, indexes, inboxes, or .gitignore.",
    )
    parser.add_argument(
        "--project-binding",
        help="Current binding from project_identity.py identity --operation workspace-install.",
    )
    return parser.parse_args()


def selected_providers(values: list[str] | None) -> tuple[str, ...]:
    available = provider_ids()
    if not values:
        return ("codex",)
    if "all" in values:
        return available
    return tuple(dict.fromkeys(values))


def report_codex_skill_state() -> None:
    shed = Path(__file__).resolve().parents[1]
    source = shed / "skills" / "tool-shed"
    known_releases = load_release_skill_digests(
        shed / "adapters" / "codex-skill-releases.json"
    )
    state = inspect_codex_skill(source, known_releases)
    print(f"Codex skill: {state['state']} at {state['path']}.")
    if state.get("compatibility") == "mismatch":
        print(
            "TOOL_SHED_SKILL_MISMATCH: "
            f"{state['compatibility_detail']}."
        )
    if state["state"] in {"missing", "stale-released"}:
        print(
            "Safe Codex skill synchronization: "
            f"{state['sync_command']}."
        )
    elif state["state"] not in {"current"}:
        print("Codex skill synchronization refused: modified, unmanaged, or unsafe installation.")
    print("Codex skill changes require a fresh Codex session before they take effect.")


def codex_cli_readiness_report() -> dict[str, Any]:
    """Return the shared resolver vocabulary used for install-time reporting."""

    resolution = CodexCliResolver().resolve()
    report = resolution.as_dict()
    report["codex_cli"] = (
        "INVALID" if resolution.readiness is CodexReadiness.INVALID_EXECUTABLE
        else ("AVAILABLE" if resolution.found else "NOT FOUND")
    )
    report["discovery"] = (
        "OpenAI VS Code extension"
        if resolution.source and resolution.source.value == "openai_vscode_extension"
        else (resolution.source.value.replace("_", " ").title() if resolution.source else "not found")
    )
    report["compatibility"] = {
        CodexReadiness.AVAILABLE_QUALIFIED: "QUALIFIED VERSION",
        CodexReadiness.AVAILABLE_UNQUALIFIED: "UNQUALIFIED VERSION",
        CodexReadiness.APP_SERVER_UNAVAILABLE: "APP SERVER UNAVAILABLE",
        CodexReadiness.INVALID_EXECUTABLE: "INVALID EXECUTABLE",
        CodexReadiness.NOT_FOUND: "NOT INSTALLED OR NOT FOUND",
    }[resolution.readiness]
    return report


def report_codex_cli_readiness() -> dict[str, Any]:
    """Print non-blocking App Server readiness when the Codex provider applies."""

    report = codex_cli_readiness_report()
    print(f"Codex CLI: {report['codex_cli']}")
    print(f"Discovery: {report['discovery']}")
    print(f"Executable: {report['executable'] or 'not detected'}")
    print(f"Installed Codex: {report['version'] or 'not detected'}")
    print(
        "App Server: "
        f"{'AVAILABLE' if report['readiness'] in {'available_qualified', 'available_unqualified'} else 'UNAVAILABLE'}"
    )
    print(f"Compatibility: {report['compatibility']}")
    if report["readiness"] not in {"available_qualified", "available_unqualified"}:
        print("Normal GUI Tool Shed operation remains available; only App Server execution is unavailable.")
    return report


def main() -> int:
    args = parse_args()
    root = Path(args.workspace).expanduser().resolve()
    providers = selected_providers(args.provider)
    try:
        validate_workspace_config(root)
    except WorkLevelConfigError as error:
        print(f"Work-level configuration failed: {error}", file=sys.stderr)
        return 1
    if args.guidance_only:
        repository = inspect_work_ignore(root).repository
        if repository is None or repository != root:
            print("Guidance-only installation requires the exact Git repository root.", file=sys.stderr)
            return 1
        try:
            load_project_identity(root)
            require_project_binding(
                root,
                args.project_binding,
                operation="workspace-install",
            )
            for provider_id in providers:
                guidance_path, changed = ensure_provider_guidance(repository, provider_id)
                state = "updated" if changed else "current"
                print(f"Provider guidance ({provider_id}): {state} at {guidance_path}.")
        except (ProjectIdentityError, ValueError) as error:
            print(f"Provider guidance failed: {error}", file=sys.stderr)
            return 1
        if "codex" in providers:
            report_codex_skill_state()
            report_codex_cli_readiness()
        return 0
    identity_exists = (root / IDENTITY_RELATIVE_PATH).exists() or any(
        (root / relative).exists() for relative in LEGACY_IDENTITY_PATHS
    )
    try:
        if identity_exists:
            load_project_identity(root)
            require_project_binding(
                root,
                args.project_binding,
                operation="workspace-install",
            )
        identity, identity_created = ensure_project_identity(root)
    except ProjectIdentityError as error:
        print(f"Project identity failed: {error}", file=sys.stderr)
        return 1
    ensure_work_tree(root)
    try:
        migrated_inboxes = migrate_legacy_q_and_a(root)
    except ValueError as error:
        print(f"Q&A inbox migration failed: {error}", file=sys.stderr)
        return 1
    ask_created = ensure_ask_inbox(root)

    repository = inspect_work_ignore(root).repository
    if repository is not None:
        generated_count, generated_bytes = existing_generated_outputs(repository)
        added = ensure_root_gitignore(repository)
        if added:
            print("Repository policy: appended missing Tool Shed entries to root .gitignore: " + ", ".join(added))
            if generated_count:
                print(
                    "Adoption warning: the new generated-output rules cover "
                    f"{generated_count} existing file(s), {format_bytes(generated_bytes)}. "
                    "Files were not moved, deleted, or rewritten; review the rules and retain "
                    "small versioned summaries or manifests outside generated/."
                )
        try:
            for provider_id in providers:
                guidance_path, changed = ensure_provider_guidance(repository, provider_id)
                if changed:
                    print(
                        f"Provider guidance ({provider_id}): updated Tool Shed rules in {guidance_path}."
                    )
        except ValueError as error:
            print(f"Provider guidance failed: {error}", file=sys.stderr)
            return 1
        if "codex" in providers:
            report_codex_skill_state()
            report_codex_cli_readiness()

    index_script = Path(__file__).resolve().with_name("update_work_index.py")
    if index_script.exists():
        subprocess.run(
            [sys.executable, str(index_script), "--workspace", str(root), "--no-preflight"],
            check=True,
            stdout=subprocess.DEVNULL,
        )

    print(f"Initialized work tree under {root / 'work'}")
    identity_state = "created" if identity_created else "preserved"
    print(
        f"Project identity: {identity_state} {identity['project_id']} at "
        f"{root / 'work' / 'tool-shed-project.json'}"
    )
    canonical_ask = root / "work" / "01-q&a" / "ask.txt"
    if ask_created:
        print(f"Initialized Tool Shed Q&A inbox at {canonical_ask}")
    else:
        print(f"Preserved existing Tool Shed Q&A inbox at {canonical_ask}")
    if migrated_inboxes:
        print(
            f"Migrated {len(migrated_inboxes)} legacy Q&A file(s) into {canonical_ask.parent} "
            "and removed the old Q&A folders after byte verification."
        )
    state = inspect_work_ignore(root)
    failed = False
    if state.match is None:
        if state.repository is not None:
            print("Repository policy: root work/ is trackable (Tool Shed default).")
    else:
        match = state.match
        print(
            f"Repository policy: root work/ is ignored by {match.source}:{match.line}: {match.rule!r} "
            f"(matched {match.path})."
        )
        print(
            f"Trackability preview: {state.file_count} file(s), {format_bytes(state.total_bytes)}, "
            "currently ignored under work/."
        )
        if state.exception_reason:
            print(f"Documented exception in {POLICY_FILE}: {state.exception_reason}")
        else:
            if state.exception_error:
                print(f"Invalid exception: {state.exception_error}")
            print(
                "Remove only the root /work/ ignore rule shown above, then rerun this command. "
                f"If ignoring work/ is intentional, document it in repository-root {POLICY_FILE}. "
                "No work/ files were deleted, replaced, relocated, or rewritten by this policy check."
            )
            failed = True

    repository, snapshot_match = inspect_snapshot_ignore(root)
    if repository is not None and (repository / "tool_shed").exists():
        if snapshot_match:
            print(
                f"Repository policy: /tool_shed/ is ignored by {snapshot_match.source}:"
                f"{snapshot_match.line}: {snapshot_match.rule!r}."
            )
        else:
            print("Repository policy: add /tool_shed/ to the repository-root .gitignore.")
            failed = True
    _, findings, _, _ = inspect(root)
    if findings:
        print("Workspace preflight warnings:")
        for finding in findings:
            print(f"- [{finding.code}] {finding.message}")
    else:
        print("Workspace preflight passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
