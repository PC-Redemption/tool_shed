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
