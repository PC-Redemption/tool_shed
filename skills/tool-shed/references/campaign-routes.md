# Tool Shed campaign routes

Read this reference for numbered work levels, `ts:ship`, campaign execution, `ts: help`, and
`ts:ask`.

## Numbered Work Levels

Treat a leading numbered route as the operator's explicit stopping point for the current execution:

| Route | Required endpoint |
| --- | --- |
| `ts:work1 <goal>` | Implement, run the quickest meaningful check, checkpoint only the requested changes in a local commit, leave the worktree clean when unrelated pre-existing changes do not prevent it, and stop without deployment. |
| `ts:work2 <goal>` | Perform `work1`, deploy to the configured work environment, run focused browser and changed-behavior checks, checkpoint, and stop. |
| `ts:work3 [scope]` | Run the repository's full applicable validation and build for the accumulated candidate, update and verify the work environment when relevant, freeze it in a local commit, and stop. |
| `ts:work4 [scope]` | Perform `work3`, then push the frozen source without intentionally releasing or promoting production. |
| `ts:work5 [scope]` | Perform release qualification, push, release or promote production, and verify the production target. This is equivalent to an explicit `ts:ship`. |

The levels are cumulative execution boundaries, not coordination levels. Keep Direct, Guided,
Coordinated, and Deep selection independent. Aliases are `ts:work` for `work2`, `ts:freeze` for
`work3`, `ts:push` for `work4`, and `ts:ship` for `work5`. `ts:check
<spot|focused|full|release>` runs only the corresponding validation and does not implement, commit,
push, deploy, or release.

Read optional project state from root `work/tool-shed.yaml` when present. The minimal supported
declaration is:

```yaml
schema_version: 1
work_model: combined
```

- `combined`: the work environment and production are the same target. State plainly before
  remote mutation that `work2` or `work3` may change the live site; `work5` formalizes and verifies
  the release but may not be its first production exposure.
- `split`: `work2` and `work3` affect development only; only `work5` promotes production.

Target names may be declared as `development_target` and `production_target` when existing
workspace docs and tooling do not resolve them. The file is tracked agent-readable project state,
not a credential store, deployment framework, or grant of authority. Reuse existing scripts,
hosting configuration, and runbooks. When the declaration is absent, preserve existing workspace
behavior and ask one concise target question only when repository evidence cannot route a requested
remote stage safely. Reject unsupported schema versions or work models rather than guessing.

Do not force unrelated pre-existing changes into a checkpoint. If they prevent a clean worktree,
preserve them and report the exception. If the only available `work4` push automatically deploys
production, stop before pushing unless production release is explicitly authorized; never report
that coupled endpoint as non-production.

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

## Owner Campaign Queue

Durable owner-facing campaign state lives under first-sorted `work/00-campaigns/`:

- `active-queue.md`: canonical ordered queue plus last completed, working now, next, blockers,
  decisions, and detour/return state;
- `completed-queue.md`: newest-first verified completion history;
- `active/`, `completed/`, `deferred/`, and `abandoned/`: detailed campaign requests by lifecycle.

Keep `work/01-q&a/ask.txt` as transient intake. Accepting an inbox request may create a durable
campaign, but never moves, clears, or rewrites the inbox without explicit operator authorization.

Use `python3 <shed>/scripts/campaign_queue.py --workspace <workspace>` for deterministic reads and
mutations:

- `ts: queue` and `ts: status`: run `status`, report the compact owner capsule and findings.
- `ts: completed`: run `completed` and summarize recent verified outcomes.
- `ts: next`: run `next`, then execute only the selected ready campaign under its natural
  coordination and requested work level.
- `ts: add <idea>`: compare with active, deferred, and completed IDs and content; report material
  overlap or direction conflicts; after resolving placement, run `add` with the current state token.
- `ts: defer <campaign>`: require a reason and reactivation condition, then run `defer` with the
  current state token.
- `ts: abandon <campaign>`: require a disposition and replacement when applicable, then run
  `abandon` with the current state token.
- Campaign completion: require the request's explicit completion gate and applicable verification,
  then run `complete --gate-passed --evidence ...` with the current state token.

Every mutation requires `--expect TOKEN` obtained immediately beforehand from `status`. Reject a
stale token rather than overwriting newer state. Lifecycle operations use a recovery journal and
validate queue/folder invariants before committing. Do not silently reorder a campaign when
priority or direction is ambiguous. Blocked campaigns stay active; deferral is an intentional
priority decision; abandonment preserves disposition history.

Use `migrate-preview` to inspect Markdown requests and actionable inbox lines in canonical
`work/01-q&a/` or pre-installer legacy `work/q&a/`. It never writes. Campaign conversion requires a separate exact approved manifest and is
not implied by preview, installation, update, or `ts:ask`.

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

The canonical inbox is `work/01-q&a/ask.txt`; `work/q&a/ask.txt` is a pre-migration legacy fallback. Ignore blank and
comment lines. Use the only actionable inbox. If both are actionable, do not merge or act; report
the conflict and ask which to use. Never move, clear, rewrite, or delete either file without
explicit authorization. Dispatch the selected content under its natural coordination level;
`ts:ask` does not turn a bounded Direct request into a heavyweight campaign. Summarize what was
selected and done.

During workspace installation or upgrade, copy and byte-verify all contents from legacy
`work/q&a/` and root `q&a/` into `work/01-q&a/`, preserve collisions under source-specific names,
then remove the old folders. This filesystem migration does not convert inbox content into durable
campaigns and does not clear the canonical inbox.
