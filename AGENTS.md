<!-- BEGIN TOOL SHED GENERATED EVIDENCE GUIDANCE -->
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
<!-- END TOOL SHED GENERATED EVIDENCE GUIDANCE -->

<!-- BEGIN TOOL SHED SHIP GUIDANCE -->
## Tool Shed ship route

- Treat `ts:ship <goal>` and `ts: ship <goal>` as authorization to plan, implement, validate, build, deploy, and verify the workspace goal end-to-end.
- Treat lifecycle stages as applicable only when the requested outcome includes them, repository policy mandates them, or concrete risk or observed failure justifies them. Wording that merely mentions or discusses `ts:ship` is not an end-to-end delivery request.
- State the concrete reason before expanding focused verification into broad qualification, deployment, or external publication.
- Continue through every applicable lifecycle stage; do not stop merely because planning, coding, tests, or a build succeeded.
- Use the workspace's own tooling, environments, runbooks, and protected-environment controls.
- Keep changes scoped to the goal and preserve unrelated user work.
- Do not ask for repeated confirmation for reversible, in-scope steps already clearly authorized by the operator. One request may authorize multiple named operations. Ask again only when an action materially expands scope, targets a protected environment, is destructive or irreversible, uses an unknown deployment target, publishes externally, or otherwise requires new authority.
- Before an already-authorized consequential stage, identify at most three credible ways the plan could fail and add proportionate prevention, detection, verification, or rollback. Skip this check for routine reversible work.
- Verify the delivered result in its target environment before claiming completion.
- The route does not waive safety rules, required approvals, credential boundaries, or authorization limits.
- If a stage is inapplicable, explain why. If deployment is blocked, complete every safe preceding stage and report the exact blocker.
<!-- END TOOL SHED SHIP GUIDANCE -->

<!-- BEGIN TOOL SHED CAMPAIGN GUIDANCE -->
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
<!-- END TOOL SHED CAMPAIGN GUIDANCE -->

<!-- BEGIN TOOL SHED Q&A GUIDANCE -->
## Tool Shed Q&A inbox

- Treat `ts:ask` and `ts: ask` as requests to run `python3 <shed>/scripts/read_ask_inbox.py --workspace <workspace> --json`.
- The canonical inbox is `work/q&a/ask.txt`; also inspect `q&a/ask.txt` as a legacy or misplaced fallback.
- Ignore blank lines and lines beginning with `#` in both files.
- Use canonical content when only it is actionable. If only fallback content is actionable, process it and clearly report its noncanonical location.
- If both files are actionable, do not merge or act on either; report the conflict and ask which request to use.
- Apply normal scope, authorization, safety, and routing rules to the selected request.
- Dispatch the selected request under its natural coordination level; `ts:ask` does not turn a bounded Direct request into a heavyweight campaign.
- Never move, clear, rewrite, or delete either inbox without explicit operator authorization.
- Summarize what was read and what was done in the final response.
<!-- END TOOL SHED Q&A GUIDANCE -->

<!-- BEGIN TOOL SHED EVIDENCE RESPONSE GUIDANCE -->
## Tool Shed evidence-response loop

- Use the loop for nontrivial planning, implementation, debugging, research, validation, and deployment.
- Keep the desired outcome and the current condition limiting progress visible.
- After each material action or new observation, compare the actual state with the expected state. If they differ, update assumptions, the plan, and the next action before continuing; command success alone is not outcome success.
- Preserve the operator's scope, authority, and safety boundaries while adapting. A newly discovered action does not authorize itself.
- Skip explicit loop ceremony for simple answers and known single-step reversible work; execute and verify them directly.
<!-- END TOOL SHED EVIDENCE RESPONSE GUIDANCE -->

<!-- BEGIN TOOL SHED ROUTING GUIDANCE -->
## Tool Shed request routing

- Treat a leading `ts:` as authoritative Tool Shed routing for the current request only.
- Locate the workspace-local shed, then read its `skills/tool-shed/SKILL.md` before acting.
- Keep project state in root `work/`; the workspace-local shed contains reusable machinery.
- Use only the provider capabilities actually available in the current product surface.
<!-- END TOOL SHED ROUTING GUIDANCE -->

<!-- BEGIN TOOL SHED DISCUSSION GUIDANCE -->
## Tool Shed discussion route

- Treat `ts: discuss <topic>` as the authoritative Tool Shed discovery route.
- Treat a leading `discussion:` as an informal, read-only campaign-entry signal.
- Explore the outcome, motivation, constraints, assumptions, unknowns, and smallest useful next route.
- Do not create or modify workspace artifacts unless the operator explicitly asks to capture or plan.
<!-- END TOOL SHED DISCUSSION GUIDANCE -->

<!-- BEGIN TOOL SHED COORDINATION GUIDANCE -->
## Tool Shed minimum sufficient coordination

- Start at the lowest adequate level: Direct, Guided, Coordinated, or Deep.
- Default a clear, reversible, single-repository bug fix or enhancement to Direct, including when it arrives through `ts:ask`.
- For Direct work, orient to the named target once, implement the focused change, and run focused, proportionate verification.
- Do not create artifacts, branches, PRs, releases, deployments, broad qualification, or new worktrees for Direct work unless explicitly requested, mandated by repository policy, or justified by concrete risk, conflicting evidence, or observed failure.
- Escalate only when evidence shows ambiguity, consequence, irreversibility, repeated failure, coordination, or handoff cost.
- Load route-specific instructions and references only when the route needs them.
- Preserve a compact campaign state: outcome, current constraint, decisions, evidence, and next action.
<!-- END TOOL SHED COORDINATION GUIDANCE -->

<!-- BEGIN TOOL SHED WORK LEVEL GUIDANCE -->
## Tool Shed numbered work levels

- Treat `ts:work1` through `ts:work5` as cumulative execution endpoints, independent of Direct, Guided, Coordinated, or Deep coordination.
- `work1`: implement, run the quickest meaningful check, checkpoint only requested changes in a local commit, leave the worktree clean when unrelated prior changes permit, and stop without deployment.
- `work2`: perform `work1`, deploy to the configured work environment, run focused browser and changed-behavior checks, checkpoint, and stop.
- `work3`: fully validate and build the accumulated candidate, update and verify the work environment when relevant, freeze it locally, and stop.
- `work4`: perform `work3`, then push without intentionally releasing or promoting production.
- `work5`: qualify, push, release or promote production, and verify the production target; this is equivalent to explicit `ts:ship`.
- Aliases are `ts:work` = `work2`, `ts:freeze` = `work3`, `ts:push` = `work4`, and `ts:ship` = `work5`. `ts:check <spot|focused|full|release>` validates only and does not mutate source, Git, or environments.
- Read optional tracked project state from `work/tool-shed.yaml`. `work_model: combined` means work and production share a target, so state that `work2` or `work3` may change the live site. `work_model: split` keeps `work2` and `work3` on development and reserves production promotion for `work5`.
- Reuse existing workspace tooling. The config is not a credential store, deployment framework, or authority grant. If absent, preserve existing behavior and ask one concise target question only when safe routing cannot be derived. Reject invalid schemas or modes rather than guessing.
- Preserve unrelated pre-existing changes. If they prevent a clean checkpoint, report it. If a `work4` push automatically deploys production, stop before pushing unless production release is explicitly authorized.
<!-- END TOOL SHED WORK LEVEL GUIDANCE -->
