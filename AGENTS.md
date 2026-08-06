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
- Start or fork a fresh Codex task after exceptionally large qualification campaigns.
<!-- END TOOL SHED GENERATED EVIDENCE GUIDANCE -->

<!-- BEGIN TOOL SHED SHIP GUIDANCE -->
## Tool Shed ship route

- Treat `ts:ship <goal>` and `ts: ship <goal>` as authorization to plan, implement, validate, build, deploy, and verify the workspace goal end-to-end.
- Continue through every applicable lifecycle stage; do not stop merely because planning, coding, tests, or a build succeeded.
- Use the workspace's own tooling, environments, runbooks, and protected-environment controls.
- Keep changes scoped to the goal and preserve unrelated user work.
- Do not ask for repeated confirmation for reversible, in-scope steps already clearly authorized by the operator. One request may authorize multiple named operations. Ask again only when an action materially expands scope, targets a protected environment, is destructive or irreversible, uses an unknown deployment target, publishes externally, or otherwise requires new authority.
- Verify the delivered result in its target environment before claiming completion.
- The route does not waive safety rules, required approvals, credential boundaries, or authorization limits.
- If a stage is inapplicable, explain why. If deployment is blocked, complete every safe preceding stage and report the exact blocker.
<!-- END TOOL SHED SHIP GUIDANCE -->

<!-- BEGIN TOOL SHED CAMPAIGN GUIDANCE -->
## Tool Shed campaign continuity

- Treat the requested outcome in the current chat as the campaign. Plans, checklists, workpackages, tests, builds, and deployments are possible stages or artifacts, not the campaign itself.
- Keep working while the next action is reversible, in scope, and already authorized. A progress summary, artifact update, phase boundary, or useful review point is not an approval gate.
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
- Never move, clear, rewrite, or delete either inbox without explicit operator authorization.
- Summarize what was read and what was done in the final response.
<!-- END TOOL SHED Q&A GUIDANCE -->
