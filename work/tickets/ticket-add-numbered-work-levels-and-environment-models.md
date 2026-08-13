# Ticket: Add numbered work levels and environment models

Status: complete
Type: ticket
Updated: 2026-08-13
Next Action: none
Parent: work/maps/map-tool-shed-evolution.md

## Problem

Tool Shed has a lightweight Direct route and an end-to-end `ts:ship` route, but it does not give
the operator a compact way to state how far one execution should proceed. Small website changes
can therefore stop short of a useful hosted browser check or expand into full validation,
publication, release, and deployment when only a clean local checkpoint was wanted.

Environment topology is also being mixed with execution intent. Some current workspaces develop
and serve production through one remote environment and entry point; future workspaces may split
development and production for uptime or data protection. Requiring a separate environment or a
new deployment framework now would add setup work without improving the current sites.

## Expected Behavior

Add five cumulative, explicit execution routes whose operator-facing meaning stays stable across
workspace topologies:

| Route | Validation and stopping point |
| --- | --- |
| `ts:work1 <goal>` | Implement, run the quickest meaningful check, create a local checkpoint commit, leave the worktree clean, and stop without deployment. |
| `ts:work2 <goal>` | Implement, deploy to the configured work environment, run focused browser and changed-behavior checks, create a checkpoint commit, leave the worktree clean, and stop. |
| `ts:work3 [scope]` | Run the repository's full applicable validation/build against accumulated candidate work, update and verify the work environment when relevant, freeze it in a local commit, leave the worktree clean, and stop. |
| `ts:work4 [scope]` | Perform `work3`, then push the frozen source without intentionally releasing or promoting production. |
| `ts:work5 [scope]` | Perform release qualification, push, release or promote production, and verify the production target. This is the numbered equivalent of explicit `ts:ship`. |

Keep readable aliases: `ts:work` maps to `work2`, `ts:freeze` to `work3`, `ts:push` to
`work4`, and `ts:ship` to `work5`. Keep `ts:check <spot|focused|full|release>` as a
non-mutating validation-only route. The work level is an execution boundary and remains
independent of Direct, Guided, Coordinated, and Deep coordination.

Support two work models with the same commands:

1. `combined`: the configured work environment is also the production environment. `work2` and
   `work3` may therefore change the live site and must say so plainly; `work5` records and verifies
   the formal release rather than pretending it is necessarily the first production exposure.
2. `split`: `work2` and `work3` affect development only; `work5` promotes the frozen candidate to
   the separate production environment.

Allow a small, tracked workspace declaration at `work/tool-shed.yaml`:

```yaml
schema_version: 1
work_model: combined
```

A later topology change only needs `work_model: split` plus development and production target
names when existing workspace documentation cannot already resolve them. The declaration is
agent-readable project state, not a new runtime service or general deployment schema. It contains
no credentials and does not require Tool Shed to create deployment scripts or infrastructure.

When the file is absent, preserve existing behavior and use existing repository documentation,
scripts, and hosting configuration. Ask one concise target question only when an explicit
`work2`-`work5` request cannot be routed safely. Do not silently infer permission to modify a live
or protected target.

## Implementation Plan

1. Define the provider-neutral numbered work-level contract and its relationship to coordination
   levels in `skills/tool-shed/SKILL.md` and the campaign route reference.
2. Extend the managed instruction blocks in `scripts/install_into_workspace.py` so installed
   providers recognize the same routes, aliases, stopping points, clean-worktree expectation, and
   environment-model boundary while preserving owner-authored instructions.
3. Document the two work models, minimal `work/tool-shed.yaml` declaration, missing-config
   behavior, combined-environment live-impact warning, and split-environment promotion flow in the
   operator guide and README.
4. Make configuration adoption optional and incremental. Reuse existing deployment commands,
   repository scripts, and target documentation; do not add an environment conversion wizard,
   runtime router, or mandatory generated configuration.
5. Add frozen routing scenarios and validation assertions covering all five levels, aliases,
   combined and split models, missing/invalid configuration, pre-existing dirty worktrees, failed
   validation, and a push that would automatically deploy production.
6. Run focused routing and installer tests, disposable provider-install fixtures, and then the
   complete Tool Shed validator. Treat release, installed-client synchronization, and fleet
   updates as separately authorized follow-up work.

## Scope Boundaries

- Do not provision, clone, or require separate development infrastructure.
- Do not create deployment scripts merely to satisfy the model; invoke the workspace's existing
  mechanisms.
- Do not put secrets, host credentials, private keys, or environment contents in
  `work/tool-shed.yaml`.
- Do not let configuration alone grant authority for destructive actions, protected targets, or
  otherwise unauthorized external publication.
- Do not force a commit across unrelated pre-existing changes. Preserve them and report when a
  clean worktree cannot safely be achieved.
- Do not claim `work4` is non-production when the configured canonical push automatically deploys
  production. Stop before the push and report the coupling, or use an already-configured
  non-production branch when that is within scope.
- Do not publish a Tool Shed release, update installed clients, or roll out workspace snapshots as
  part of implementing this ticket without separate authorization.

## Acceptance Criteria

- [x] `ts:work1` through `ts:work5` have one documented, cumulative execution contract across the
  portable skill, generated provider guidance, README, and operator guide.
- [x] `work1` stops after a quick meaningful check and clean local checkpoint; `work2` adds work-
  environment deployment and focused browser verification; `work3` adds full qualification and
  freeze; `work4` adds source publication without intentional production promotion; and `work5`
  adds production release/promotion and target verification.
- [x] `ts:work`, `ts:freeze`, `ts:push`, and `ts:ship` resolve to levels 2 through 5 respectively,
  while `ts:check` remains validation-only and non-mutating.
- [x] Work levels do not automatically select Guided, Coordinated, or Deep artifacts; coordination
  escalates only under the existing evidence-based rules.
- [x] In `combined` mode, guidance and fixtures make the live impact of `work2` and `work3`
  explicit without imposing release qualification on each iteration.
- [x] In `split` mode, `work2` and `work3` cannot promote production, and `work5` performs and
  verifies the production promotion.
- [x] A tracked `work/tool-shed.yaml` can declare `schema_version: 1` and `work_model` without
  containing credentials or requiring new infrastructure; changing `combined` to `split` does not
  change command names.
- [x] A missing declaration preserves backward compatibility and causes at most one concise target
  question when safe routing cannot be derived from existing workspace evidence.
- [x] Invalid configuration, protected-target ambiguity, failed validation, pre-existing unrelated
  changes, and auto-production-on-push prevent the affected endpoint rather than silently
  broadening authority or misreporting a clean/non-production result.
- [x] Installer and snapshot fixtures prove managed-block idempotence and preservation of
  owner-authored guidance for every supported provider adapter.
- [x] Focused tests and `python3 scripts/validate_tool_shed.py` pass.

## Verification

Use table-driven prompt fixtures to assert each route's permitted and prohibited stages under both
models. Exercise disposable installed workspaces with and without `work/tool-shed.yaml`; do not
deploy to a real remote server during repository tests.

Run the smallest relevant `unittest` selections while implementing, followed by:

```bash
python3 -m unittest tests.test_scripts
python3 scripts/validate_tool_shed.py
```

Inspect generated guidance for all provider adapters and confirm that repeated installation is
byte-stable outside managed blocks. Release-time field verification should cover one combined
workspace and one split workspace only after deployment and client-update authority is granted.

Verified 2026-08-13 with table-driven combined/split routing scenarios, idempotent disposable
installs across all five provider adapters, 92 passing repository tests, and the complete Tool Shed
validator. The workspace model remains optional agent-readable guidance; no runtime deployment
framework or credentials were added.

## Risks And Controls

- Risk: numbered levels become another heavy workflow. Control: make configuration optional,
  reuse existing workspace mechanisms, and prohibit automatic artifact or infrastructure creation.
- Risk: operators mistake combined-mode previewing for isolation. Control: require each remote
  result to identify whether the configured work target is live production.
- Risk: `work4` triggers production through branch automation. Control: detect documented or
  observed auto-deploy coupling and stop before publication unless production release is explicitly
  authorized.
