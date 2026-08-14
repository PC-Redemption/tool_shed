# Conventions

## Boundaries

The workspace-local `tool_shed/` is a disconnected snapshot. It must not contain `.git/`, be registered as a submodule, or be tracked by the parent codebase repository. The parent repository should ignore `/tool_shed/`. Workspace use must not push changes back to the canonical Tool Shed repository.

This exclusion applies only to the tooling snapshot. Root `work/` is repository-tracked by default.
An existing ignore rule is not an intentional exception. Ignoring `work/` requires both a matching
Git ignore rule and a valid repository-root `.tool-shed-policy.json` with
`schema_version: 1`, `work_git_policy.ignore: true`, and a non-empty
`work_git_policy.reason`.

`tool_shed/` contains:

- selection rules
- conventions
- templates
- helper scripts
- examples

## Provider Portability

Tool Shed's artifact model, campaign behavior, and deterministic scripts are provider-neutral.
`adapters/providers.json` records native instruction paths and honestly qualified capability levels.
Run `scripts/install_into_workspace.py --provider <provider-id>` to add or refresh only marked Tool
Shed blocks while preserving owner-authored instruction content.

The portable `skills/tool-shed/SKILL.md` progressively loads route references. Provider-specific
instruction discovery, tool names, permissions, hooks, model catalogs, and packaging stay behind
adapters. Files and Git remain authoritative; MCP is optional. A compatibility claim must name the
provider surface and observed capability level described in `docs/provider-adapters.md`.

`work/` contains project-specific generated artifacts:

- owner-facing campaign queues and lifecycle requests under first-sorted `work/00-campaigns/`
- project maps
- active and completed workpackages
- tickets
- ADRs
- incidents
- runbooks
- spikes
- checklists
- inventories
- decision records

## Validation Evidence

`work/evidence/` is the standard Tool Shed repository for validation evidence.

- Version human-readable evidence such as `work/evidence/**/*.md`.
- Version selected small JSON summaries and manifests when they are useful project records.
- Store raw captures, dumps, images, device captures, large logs, and test payloads under
  `work/evidence/generated/`.
- Keep a small versioned manifest outside the ignored generated directory. Record hashes,
  timestamps, target identity, commands or test IDs, outcomes, and relative artifact locations.

The installer adds `/work/evidence/generated/` to the repository-root `.gitignore`. Use
`.gitignore` for this shared project convention. Use `.git/info/exclude` for additional
machine-local evidence. Existing workspaces may add an exact local exclusion without moving or
deleting existing evidence.

Run `python3 tool_shed/scripts/workspace_preflight.py --workspace .` before long validation
campaigns. The check emits a workspace profile, derives explainable risk budgets from repository
scale and explicit local policy, and warns about excessive untracked count or bytes, binaries in
versioned `work/` paths, oversized tracked diffs, and visible Tool Shed backup archives. It is
read-only. General hard safety limits cap local overrides so an already unsafe workspace cannot
normalize the same risk away.

Use `python3 tool_shed/scripts/profile_workspace_performance.py --workspace .` when workspace or
`work/` growth may be slowing Codex-facing operations. The profiler is read-only and saved JSON is
restricted to aggregate scale, lifecycle, platform, warning-code, and timing fields. Do not infer
permission to collect reports, update snapshots, clean files, or archive evidence from permission
to profile. Use controlled, one-variable-at-a-time comparisons; the profiler cannot establish
undocumented Codex internal behavior.

An optional repository-root `.tool-shed-policy.json` may adapt evidence handling:

```json
{
  "schema_version": 1,
  "evidence_policy": {
    "reason": "This data workspace emits many small result shards.",
    "generated_path": "artifacts/generated",
    "evidence_paths": ["artifacts/results", "reports/evidence"],
    "thresholds": {
      "untracked_count": 200,
      "untracked_bytes": 104857600,
      "diff_bytes": 2097152
    }
  }
}
```

The reason is mandatory. Generated and evidence paths must be repository-relative; the generated
path must be separately ignored by repository policy. Every effective threshold reports whether it
came from workspace policy or the adaptive baseline. Invalid policy is an actionable preflight
finding.

For existing tracked raw evidence, use
`scripts/migrate_generated_evidence.py prepare --workspace . --output <outside-repository-path>`.
Preparation writes a candidate manifest and SHA-256-verified archive outside the repository without
changing Git or working files. Apply requires top-level and per-file approval, revalidates source
hashes and the archive, refuses a destination that is not ignored, and moves only explicitly
approved candidates. It never rewrites Git history.

`docs/` contains settled project truth:

- operator docs
- reference docs
- project/product docs
- current-state docs

`work/01-q&a/ask.txt` is a transient, workspace-local operator inbox:

- the installer creates it without replacing existing contents
- `ts:ask` inspects it first and supports `work/q&a/ask.txt` only as a pre-migration fallback
- blank lines and `#` comment lines are ignored in both locations
- canonical content wins only when the fallback is not also actionable
- fallback-only content may be processed with a clear noncanonical-path warning
- when both files are actionable, the agent reports a conflict and asks which request to use
- the agent preserves both files unless the operator explicitly asks to move, clear, rewrite, or delete
  one
- the repository ignores it because durable project truth belongs in docs and durable work belongs
  under `work/`

## Owner Campaign Lifecycle

`work/00-campaigns/` is the first-sorted owner control surface:

- `active-queue.md` is the canonical top-to-bottom execution order and compact owner state capsule
- `completed-queue.md` is verified completion history, newest first
- `active/` contains queued, working, and blocked campaign requests
- `completed/` contains requests whose explicit completion gate and applicable verification passed
- `deferred/` contains intentionally postponed requests with a reason and reactivation condition
- `abandoned/` contains cancelled, rejected, or superseded requests with a disposition

Every lifecycle mutation uses `scripts/campaign_queue.py`, requires the current state token, and
updates requests and both queue projections through a recoverable transaction. Manual or stale
queue edits fail validation. Blocked work remains active. Deferral and abandonment are explicit
priority decisions, not substitutes for temporary blocking.

`work/01-q&a/ask.txt` remains transient intake. Accepting an inbox entry may create a durable campaign
under `work/00-campaigns/active/`, but no campaign operation clears or rewrites the inbox. Legacy
request migration is preview-only until an exact manifest is separately approved.

The workspace installer migrates all files from legacy `work/q&a/` and root `q&a/` into
`work/01-q&a/`, verifies copied bytes, preserves collisions with source-specific filenames, and
removes the old folders only after verification. This filesystem move is separate from converting
inbox requests into durable campaigns.

## Artifact Headers

Every project artifact should start with a compact status block:

```text
Status: active
Type: workpackage
Updated: 2026-07-05
Next Action: ...
Canonical Truth: docs/...
```

This saves context and lets the agent decide whether to read deeper.

## Work Index

`work/index.md` and `work/index.json` are generated orientation surfaces.

- Regenerate them with `python3 tool_shed/scripts/update_work_index.py --workspace .` after creating, moving, completing, or superseding artifacts.
- Read project README/docs first for current truth, then `work/index.md`, then the active artifacts it points to.
- Use `work/index.json` for automation that needs the same artifact list.
- Do not treat the indexes as canonical truth. They are navigation aids built from artifact headers.
- Completed artifacts remain useful history, but docs and README files hold current operating truth.

## Work-State Reconciliation

Git history makes work artifacts visible, but it does not keep them aligned. Track `work/` by
default and keep the workspace-local `/tool_shed/` snapshot ignored. A project may ignore
`work/` only through the explicit documented exception above.

Run `python3 tool_shed/scripts/review_work_state.py --workspace .`:

- when an agent or human orients in the project
- after creating, completing, cancelling, or superseding an artifact
- during the repository validation workflow
- weekly as a backstop for quiet projects

The review is read-only. It reports orphaned active work, stale next actions, broken parent/output
links, completed spikes without a disposition, active plans that still point at finished work, and
repositories that ignore `work/`. Use `--json` for automation and `--strict` when any finding
should fail CI.

For an undocumented ignore, the review reports the exact ignore source, line, and matching rule,
plus the count and size of currently ignored files. Remove only the reported root `/work/` rule.
Never delete, replace, relocate, or rewrite existing evidence as part of this migration.

Every active non-map artifact should name a concrete `Parent:` or `Project Map:`. Every completed
spike must set `Disposition:` to `planned`, `documented`, `no-action`, or `superseded`. A planned
spike must identify its follow-up artifact in `Produces:`.

Deep research is a spike mode, not a separate artifact model. It uses `Type: spike` and
`Research Depth: deep`, so normal indexing, disposition, and `Produces:` rules apply. Tool Shed
structures and preserves research; it is not a search engine. Findings remain work artifacts until
settled conclusions are promoted to `docs/` or README. Research does not replace target testing:
it should turn broad uncertainty into focused experiments. Timebox or bound the effort so deep
research prevents repeated symptom-level mitigation rather than enabling indefinite analysis.
Urgent reversible containment may proceed, but speculative production heuristics must not outrun
the research.

## Tool Shed Versioning

`SHED_VERSION.json` is the authoritative snapshot manifest. It records a semantic `shed_version`,
the artifact model version, canonical manifest URL, and hashes for shipped rules, docs, scripts,
skill files, and templates.

Use `scripts/check_shed_version.py --local-only` to verify local integrity without a network call.
Use it without `--local-only` to compare with canonical GitHub state. A version check is read-only
and must distinguish older, newer, current, locally modified, equal-version release mismatch, and
failed canonical checks.

Before releasing changed Tool Shed machinery, intentionally bump `MAJOR.MINOR.PATCH` and run
`scripts/update_shed_manifest.py --write`. A manifest write requires a greater version unless
`--allow-same-version` explicitly rebuilds an unpublished release. Released manifests record their
content commit, matching `v<version>` tag, and release timestamp. Repository validation fails when
manifest hashes or provenance are invalid.

Plan-drift checks inspect planning-bearing locations: `Next Action`, parent/project-map/dependency
fields, active workstream rows, unchecked tasks, and `Do next:` content. Historical, closeout, and
related-artifact links are valid references and do not become drift merely because their targets
are finished.

## Evidence-Responsive Execution

For nontrivial planning, implementation, debugging, research, validation, and deployment, keep the
desired outcome and the current condition limiting progress visible. After each material action or
new observation, compare actual with expected state. When they differ, revise assumptions, the
plan, and the next action before continuing. A successful command is evidence about execution, not
proof that the desired outcome exists.

Adaptation preserves the operator's original scope, authority, and safety boundaries. A newly
discovered action does not authorize itself. Simple answers and known single-step reversible work
should execute and verify directly without a formal loop.

Before an already-authorized consequential ship stage, identify at most three credible ways the
plan could fail and add proportionate prevention, detection, verification, or rollback. Do not turn
this into a generic premortem ritual for routine reversible work.

## Reasoning Preflight and Catalog

Reasoning preflight is an instruction-time routing check, not an additional program invocation.
It runs once before substantial Tool Shed work using only the request and model/reasoning metadata
already exposed to the session. It adds no network call, subprocess, cache read, extra model call,
or confirmation round-trip to ordinary requests. When a current picker pair is known, it uses the
standalone, bold level-three header format `### **Reasoning: <model> / <effort>**`. It does not
claim to observe the active picker, use abstract tiers, or pause ordinary work for a reasoning
change.

OpenAI model names and effort labels are changing capability data, not durable Tool Shed policy.
Use `scripts/reasoning_catalog.py refresh` outside request execution to query the account-aware
Codex app-server `model/list` endpoint and atomically update the user-local cache. Use `status` for
a local-only diagnostic. Refresh after login/account changes, Codex updates, model-picker changes,
or cache expiry. A cached or documentation-derived catalog may guide an explicit `ts: recommend
reasoning <task>` request but cannot prove the active thread setting.

## Stale Path Check

Run `python3 tool_shed/scripts/check_stale_paths.py --workspace .` after moving, completing, or renaming artifacts.

The check is especially important after moving a workpackage from `work/wp/active/` to `work/wp/completed/`. It flags stale active-path references and missing `work/*.md` links.

## Workpackage Completion

Prefer the completion helper over a manual move:

```bash
python3 tool_shed/scripts/complete_workpackage.py work/wp/active/wp-example.md --workspace .
```

The helper moves the file to `work/wp/completed/`, marks `Status: complete`, updates `Updated:`, sets `Next Action: none` by default, regenerates `work/index.md` and `work/index.json`, and reports stale-link findings.

Use `--strict-stale-check` when automation should fail if old `work/wp/active/` links remain.

## Naming

Use lowercase kebab-case filenames.

Examples:

- `map-plugin-migration.md`
- `wp-plugin-migration.md`
- `adr-hosted-installer-plugin-bootstrapper.md`
- `incident-duplicate-mcp-table.md`
- `inventory-root-files.md`

## Artifact Composition

Artifacts should work in concert without duplicating each other.

- Use project maps as visual navigation for large projects.
- Use workpackages as delivery containers for larger transformations.
- Use tickets, checklists, spikes, ADRs, runbooks, inventories, and decision matrices as supporting tools when they fit the local problem.
- Link related artifacts with plain Markdown paths.
- Keep the coordinating artifact focused on orientation, dependencies, and next action.
- Keep detailed execution or decision content in the artifact type built for it.

## Existing Project Backfill

When loading `tool_shed` onto an existing project, learn before backfilling.

- Default to Level 2: create a project map, then create an inventory.
- Prefer the lowest useful backfill level.
- Capture observed current state before inferred plans.
- Do not invent historical decisions, completed work, or incidents.
- Mark uncertain or inferred items clearly.
- Use inventories for classification and spikes for unknowns.
- Promote settled current truth into `docs/` or README files.
- Keep coordination and future work under `work/`.

## Discovery Routing

Route discovered project facts by whether they are settled truth or unresolved work.

| Discovery | Route |
| --- | --- |
| Current setup steps | `README.md` or `docs/setup.md` |
| Current architecture or system shape | `docs/architecture.md` |
| Current operational procedure | `docs/` first, or `work/runbooks/` if still being tested |
| Open question | `work/spikes/` |
| Specific bug or enhancement | `work/tickets/` |
| Multi-step change | `work/wp/active/` |
| Known bounded execution steps | `work/checklists/` |
| Durable decision with alternatives | `work/adr/` |
| Classification list | `work/inventories/` |
| Visual coordination across moving parts | `work/maps/` |

Level 2 onboarding produces a project map and inventory only. After review, promote stable observed facts into `docs/` or README files, and create `work/` artifacts only for unresolved work.

## Promotion Rule

Work artifacts are not canonical truth by default.

When an artifact settles a durable fact, copy or summarize that fact into `README.md` or `docs/`.

Completed artifacts are history. Docs are current truth.

## Runtime And Local Config Rule

For operations, Docker, scheduler, or host-local work:

- Track examples and policy docs.
- Keep host-specific config, generated state, logs, and status payloads ignored unless the project explicitly decides otherwise.
- Record ignored local config paths in runbooks or closeout checklists when they materially affect behavior.
- Prove both sides of a migration closeout: the new runtime surface is healthy and the old runtime surface is disabled, inactive, or intentionally retained.

## Scheduler Rule

When a project introduces a scheduler or background worker, capture:

- cadence
- timeout
- action modes
- stale thresholds
- conflict or overlap rules
- cooldowns, retry limits, and restart guardrails
- runtime evidence showing whether jobs block or run concurrently

Use a runbook for repeatable operations, a checklist for bounded validation, and an ADR for durable policy changes.

## ADR Supersession Rule

Do not delete or rewrite old decisions to make history look tidy.

- Add `Supersedes:` to the new ADR when it replaces an older decision.
- Add `Superseded By:` to the old ADR.
- Promote the current operating policy to docs or README files.
- Keep the old ADR as historical context.
