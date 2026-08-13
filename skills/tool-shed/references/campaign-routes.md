# Tool Shed campaign routes

Read this reference for `ts:ship`, campaign execution, `ts: help`, and `ts:ask`.

## Ship Route

Treat `ts:ship <goal>` and `ts: ship <goal>` as authorization to plan, implement, validate, build,
deploy, and verify the workspace goal end to end.

- Inspect workspace guidance and active work before choosing the smallest sufficient plan.
- Continue through every applicable lifecycle stage. Tests or a build are intermediate evidence.
- Treat a lifecycle stage as applicable only when the requested outcome includes it, repository
  policy mandates it, or concrete risk or observed failure justifies it. `ts:ship` explicitly
  requests end-to-end delivery; wording that merely appears near or discusses `ts:ship` does not.
- Do not create planning artifacts, branches, PRs, releases, deployments, or broad qualification
  solely because a request uses Tool Shed. State the concrete reason when expanding beyond focused
  verification.
- Use the project's own tooling, environments, runbooks, and protected-environment controls.
- Keep changes scoped and preserve unrelated work.
- Do not ask for repeated confirmation for reversible, in-scope steps already authorized. One
  request may authorize multiple named operations.
- Ask again only when an action materially expands scope, targets a protected environment, is
  destructive or irreversible, uses an unknown deployment target, publishes externally, or
  otherwise requires new authority.
- Before an already-authorized consequential stage, identify at most three credible failure modes
  and add proportionate prevention, detection, verification, or rollback.
- Explain inapplicable lifecycle stages and complete every safe preceding stage if blocked.

## Evidence-Response Loop

For nontrivial work:

1. Keep the desired outcome and current limiting condition visible.
2. Take the smallest material action that advances or tests the outcome.
3. Compare actual evidence with expected state.
4. When they differ, revise assumptions, the plan, and the next action.

Command success alone is not outcome success. Adaptation does not broaden authority. Skip explicit
loop ceremony for simple answers and known single-step reversible work.

## Campaign Continuity

The requested outcome is the campaign. Plans, artifacts, tests, builds, and deployments are stages,
not the campaign itself.

- Keep working while the next action is reversible, in scope, and already authorized.
- Preserve the selected coordination level while continuing. Campaign continuity does not upgrade
  Direct work to Guided, Coordinated, or Deep and does not make inapplicable lifecycle stages apply.
- A progress summary, artifact update, phase boundary, or useful review point is not an approval gate.
- Pause only for requested review, a material unresolved decision, contradictory evidence, new
  authority, or a protected, destructive, irreversible, or not-yet-authorized external action.
- When review is required, identify the exact file or result and section, the precise decision or
  approval, and what follows.

End every Tool Shed campaign response with exactly one verdict:

- `Campaign status: COMPLETE` only when the whole outcome and applicable verification are finished.
- `Campaign status: CONTINUE` when work remains but the turn must end without operator input; name
  the next action. Do not stop if that action can safely run now.
- `Campaign status: BLOCKED` when progress requires a named decision, dependency, permission,
  credential, external-state change, or required review; state the precise operator action.

## Help Route

For `ts: help` or `ts: help <topic>`, read `docs/operator-guide.md` and return a concise relevant
menu with example prompts. Do not create or modify artifacts for a help-only request.

## Q&A Inbox Route

For `ts:ask` or `ts: ask`, run:

```bash
python3 <shed>/scripts/read_ask_inbox.py --workspace <workspace> --json
```

The canonical inbox is `work/q&a/ask.txt`; `q&a/ask.txt` is a legacy fallback. Ignore blank and
comment lines. Use the only actionable inbox. If both are actionable, do not merge or act; report
the conflict and ask which to use. Never move, clear, rewrite, or delete either file without
explicit authorization. Dispatch the selected content under its natural coordination level;
`ts:ask` does not turn a bounded Direct request into a heavyweight campaign. Summarize what was
selected and done.
