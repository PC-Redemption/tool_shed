---
name: tool-shed
description: Structured work artifacts and workspace coordination with a local tool_shed. Use when Codex needs to choose, create, or maintain planning/documentation artifacts such as checklists, tickets, project maps, workpackages, ADRs, runbooks, incidents, spikes, inventories, or decision matrices; when loading tool_shed into an existing project; when a user asks for visual project coordination, 30,000 ft to ground navigation, or Level 2 onboarding/backfill; or when a workspace contains tool_shed/ or the tool_shed repository files.
---

# Tool Shed

Use this skill as a thin adoption layer for a workspace-local `tool_shed`. Do not treat the skill as the source of templates or project state.

## Request Prefix

Treat `ts:` as an authoritative route for the current request only. The remainder of the request
must use the workspace-local Tool Shed rules and tooling. Do not carry the prefix into later
requests.

The global setup may also define `mp:` for private Marshal owner work and `ws:` for the current
workspace. A request uses at most one leading route prefix; when an unprefixed write could
materially target either Marshal or the workspace, ask one concise routing question before writing.

### Reasoning Preflight

Before substantial Tool Shed implementation, debugging, research, planning, or validation work,
perform one lightweight reasoning preflight inside the initial response. Do not run a command,
read a cache, access the network, invoke another model, or add a separate analysis turn for this
preflight. Use only task shape and model/reasoning metadata already exposed in the current session.

When the current session or user-provided context establishes an available model and effort pair,
give the lowest adequate picker-level recommendation on its own line:

### **Reasoning: <model> / <effort>**

This is advice for the operator to compare with the picker, not a statement of the active setting.
Render the recommendation exactly as a level-three Markdown header with the full line bolded; do
not substitute a blockquote, plain paragraph, code formatting, or another heading level.
Do not mention picker visibility, use abstract labels such as `deep`, or pause merely for a model or
effort change. If the available picker options are not established, continue silently rather than
guessing a model name. The operator can explicitly ask for `ts: recommend reasoning <task>` to
refresh the account-aware catalog and receive a concrete recommendation.

Choose the model before the effort. When those options are advertised, use Luna for clear,
repeatable work; Terra as the everyday engineering default; and Sol for ambiguous, difficult, or
high-judgment work. Use Light for quick, well-scoped tasks; Medium for ordinary planning; High for
difficult multi-step debugging, implementation, and releases; Extra High for long, agentic,
reasoning-heavy work; and Ultra only when the task separates into useful independent subproblems.

Run the preflight once for a materially new user request, not after tool results, automatic
continuations, steering additions, or context compaction. Skip it for conversation, Tool Shed help,
version/status checks, and explicit instructions to continue without preflight.

- Give the concrete recommendation whenever a usable picker pair is established.
- Continue immediately after the recommendation. Reasoning choice alone does not justify a stop.
- If no usable picker pair is established, do not emit a generic or abstract recommendation.

Model names and effort labels change. Runtime session/account capability metadata is authoritative.
The optional local reasoning catalog is maintenance and diagnostic evidence only; never read or
refresh it on the ordinary request path. Refresh it explicitly with:

```bash
python3 <shed>/scripts/reasoning_catalog.py refresh
```

Inspect it without network or subprocess discovery with:

```bash
python3 <shed>/scripts/reasoning_catalog.py status
```

The refresh uses Codex app-server `model/list`, preserves unfamiliar future effort labels, writes
atomically, and retains the last verified cache if refresh fails. Refresh after Codex login/account
changes, a Codex client update, a visible model-picker change, or when the cache expires. It is not
proof of the active thread setting; only current-session metadata can establish that.

### Ship Route

Treat `ts:ship <goal>` and `ts: ship <goal>` as authorization to carry the workspace goal through
the complete delivery lifecycle: plan, implement, validate, build, deploy, and verify.

- Inspect the workspace and its local Tool Shed guidance before choosing the smallest sufficient
  plan or work artifact.
- Continue through every applicable lifecycle stage instead of stopping after planning, code, or a
  successful build.
- Use the project's own tests, build system, deployment tooling, environments, and runbooks.
- Keep changes scoped to the stated goal, preserve unrelated user work, and report meaningful
  progress during long-running work.
- Do not ask for repeated confirmation for reversible, in-scope steps already clearly authorized
  by the operator. One request may authorize multiple named operations. Ask again only when an
  action materially expands scope, targets a protected environment, is destructive or irreversible,
  uses an unknown deployment target, publishes externally, or otherwise requires new authority.
- Treat a stage as inapplicable only when the workspace provides evidence that it is unnecessary;
  state the reason in the final response.
- Do not claim completion until the deployed or otherwise delivered result has been verified in
  its target environment.
- `ts:ship` does not waive safety rules, required approvals, protected-environment controls, or
  authorization boundaries. If deployment requires an unknown target, unavailable credential,
  new authority, or an irreversible action that was not clearly authorized, finish every safe
  preceding stage and report the exact blocker.

### Help Route

When the request is `ts: help`, read `<shed>/docs/operator-guide.md` and return a concise,
operator-facing menu of common use cases with example `ts:` prompts. Do not create or modify
artifacts for a help-only request.

When the request is `ts: help <topic>`, use the same guide and focus the response on that topic.
If the guide is missing from an older snapshot, fall back to `README.md`, `selection.md`, and
`existing-projects.md`, and mention that the snapshot does not yet include the operator guide.

### Q&A Inbox Route

When the request is `ts:ask` or `ts: ask`, run
`python3 <shed>/scripts/read_ask_inbox.py --workspace <workspace> --json`. The canonical inbox is
`<workspace>/work/q&a/ask.txt`; the resolver also inspects `<workspace>/q&a/ask.txt` as a legacy or
misplaced fallback. It ignores blank lines and lines beginning with `#` in both files.

- `canonical`: act on the canonical content.
- `fallback`: act on the fallback content and clearly report that it came from the noncanonical
  path.
- `conflict`: do not merge or act on either request; report that both are populated and ask the
  operator which request to use.
- `empty`: report that neither inbox contains actionable content.

Apply the same scope, authorization, safety, and routing rules as if the selected contents were
typed directly in chat. Never move, clear, rewrite, or delete either inbox without explicit
operator authorization. In the final response, briefly summarize what was selected and what was
done. If the resolver is absent from an older snapshot, inspect both paths manually using the same
rules.

### Version Routes

When the request is `ts: refresh reasoning catalog`, run
`python3 <shed>/scripts/reasoning_catalog.py refresh` and report the source, retrieval/expiry times,
available models, and their advertised reasoning efforts. This is an explicit maintenance action,
never an automatic request-time step.

When the request is `ts: reasoning status`, run
`python3 <shed>/scripts/reasoning_catalog.py status`. This is local-only and must clearly report
fresh, stale, missing, or invalid cache state. It does not establish the active thread setting.

When the request is `ts: recommend reasoning <task>`, run
`python3 <shed>/scripts/reasoning_catalog.py refresh`, use its advertised models and efforts with
the preflight selection rules, and return the concrete standalone recommendation format. This is an
explicit maintenance request, never ordinary request-path work.

When the request is `ts: version`, run
`python3 <shed>/scripts/check_shed_version.py --shed <shed> --local-only` and report the local
version and integrity. This route is read-only.

When the request is `ts: check for updates` or `ts: update status`, run
`python3 <shed>/scripts/check_shed_version.py --shed <shed>` and report the local version,
canonical version, version relation, and any locally modified or missing tracked files. A check
does not authorize an update. If an older snapshot lacks the script, read `SHED_VERSION.json` and
explain that its version tooling must be updated before it can perform a reliable canonical check.

### Snapshot Install And Update Route

For a normal workspace installation or snapshot update, prefer the supported updater from a
current released Tool Shed checkout:

```bash
python <current-shed>/scripts/update_snapshot.py --workspace <workspace>
```

The updater is authoritative on Windows and Linux. It selects the highest stable tag with
`core.autocrlf=false`, verifies two-commit provenance and byte-level manifest integrity, stages a
disconnected snapshot, preserves root `work/`, retains a verified backup for updates, and restores
the previous snapshot after failed post-install verification. If the installed snapshot predates
the updater, obtain a current released checkout outside the project and run the updater from there;
never pull inside or develop from the disconnected workspace snapshot.

## Locate The Shed

Before choosing or creating work artifacts, locate the shed:

1. If `tool_shed/selection.md` exists, use `tool_shed/` as the shed directory.
2. Else if `selection.md`, `conventions.md`, `templates/`, and `scripts/` exist in the workspace root, treat the workspace root as the shed directory.
3. Else if no shed exists, explain that `tool_shed` must be installed or copied into the project before this skill can create shed artifacts.

Read these files from the shed before acting:

- `selection.md`
- `conventions.md`
- `existing-projects.md` when loading the shed into an existing project

Read `README.md` when installing, explaining, or verifying repository boundaries.
Read `docs/operator-guide.md` for `ts: help` requests.
Read `SHED_VERSION.json` when reporting Tool Shed version or update status.

When orienting in a workspace that already has work artifacts, read `work/index.md` if it exists after reading README/docs. Use `work/index.json` for automation if needed. Treat both as generated navigation aids, not canonical truth.

## Core Rules

- Treat workspace-local `tool_shed/` as a one-way, disconnected snapshot of templates, instructions, and scripts.
- Do not leave Git metadata in `tool_shed/`, configure it as a submodule, track it in the parent codebase repository, or push workspace changes back to the canonical Tool Shed repository.
- When installing from a temporary clone, verify the clone, remove only `tool_shed/.git/`, and add `/tool_shed/` to the parent repository's root `.gitignore`.
- Track project-specific root `work/` in the parent repository by default. Never treat an existing
  `/work/` ignore as intentional merely because it predates the snapshot update.
- Ignore `work/` only when repository-root `.tool-shed-policy.json` explicitly sets
  `schema_version` to `1`, `work_git_policy.ignore` to `true`, and documents a non-empty reason.
- Choose the smallest artifact that fits the immediate work.
- Keep project-specific artifacts under `work/`, not inside `tool_shed/`.
- Keep settled current truth in `docs/` or README files.
- Treat completed work artifacts as history, not canonical truth.
- Use `work/index.md` to find active artifacts quickly when it exists.
- Use `work/index.json` only as machine-readable navigation data.
- Run the read-only work-state review during orientation and after artifact lifecycle changes.
- Link related artifacts with plain Markdown paths.
- Do not create a server, database, or tracker unless plain files and scripts have failed.
- Do not duplicate bulky templates or shed docs inside the skill.

## Artifact Selection

Use the shed's `selection.md` as the authority.

Fast defaults:

- Checklist: bounded known steps.
- Ticket: specific bug or enhancement with clear acceptance criteria.
- Project map: visual coordination across moving parts.
- Workpackage: multi-step transformation with sequencing or handoff cost.
- ADR: durable decision with alternatives and consequences.
- Runbook: repeatable operation where commands, order, and recovery matter.
- Incident: break/fix learning.
- Spike: uncertainty where the deliverable is learning.
- Deep-research spike: cross-layer uncertainty driving repeated mitigations or risky assumptions;
  keep `Type: spike` and use `Research Depth: deep`.
- Inventory: classify, keep, move, delete, own, or route.
- Decision matrix: compare two to five plausible options.

Use a project map when the user needs to see the whole project, when work spans multiple workstreams/artifact types, when sequencing matters, or when loading `tool_shed` into an existing project.

Select a deep-research spike when standards, hardware, drivers, middleware, and application
behavior interact; compliant specimens diverge; a second mitigation failed or a third is being
considered; narrow vendor/model heuristics are proposed; mandatory versus optional behavior is
unclear; timing or recovery lacks authority; vendor guidance may be narrower than the domain; a
last-known-good implementation differs materially; or broad compatibility, reliability, safety,
or data integrity is at stake. Do not select it for importance or elapsed time alone. Before a
third mitigation, pause new narrow heuristics until mandatory, optional, and
implementation-specific behavior are separated. Deep research structures evidence and focused
target experiments; it is not a search engine or a substitute for testing. Bound it, promote
settled conclusions to docs, and allow urgent reversible containment without letting speculative
production heuristics outrun the research.

## Create Artifacts

Prefer shed scripts when available.

Install the work tree:

```bash
python3 <shed>/scripts/install_into_workspace.py <workspace>
```

Run this after both a new installation and a snapshot upgrade. If it reports an undocumented root
`work/` ignore, surface the exact ignore source and matching rule plus the file-count/size preview;
instruct the operator to remove only that root rule. Preserve every existing `work/` file: do not
delete, replace, relocate, or rewrite evidence while correcting Git policy.

Create an artifact:

```bash
python3 <shed>/scripts/new_artifact.py <kind> "Title" --workspace <workspace>
```

Complete an active workpackage:

```bash
python3 <shed>/scripts/complete_workpackage.py work/wp/active/wp-example.md --workspace <workspace>
```

Refresh the work index:

```bash
python3 <shed>/scripts/update_work_index.py --workspace <workspace>
```

Check stale work paths:

```bash
python3 <shed>/scripts/check_stale_paths.py --workspace <workspace>
```

Review planning and artifact alignment:

```bash
python3 <shed>/scripts/review_work_state.py --workspace <workspace>
```

The review must not report reconciliation when `work/` is ignored without the explicit exception.
Use `--strict` when that policy violation should fail automation.

Profile generated-evidence risk before long campaigns:

```bash
python3 <shed>/scripts/workspace_preflight.py --workspace <workspace> --json
```

The preflight adapts to the repository and optional `.tool-shed-policy.json`, while retaining hard
safety limits. Surface its workspace profile, policy sources, risk budgets, and mitigations. It is
read-only.

Measure privacy-safe workspace scale and representative read-only operation latency:

```bash
python3 <shed>/scripts/profile_workspace_performance.py --workspace <workspace>
python3 <shed>/scripts/profile_workspace_performance.py --workspace <workspace> --json
```

Use the profiler when repository or `work/` growth may be slowing Codex-facing operations. Saved
JSON is allowlisted and excludes paths, filenames, repository identity, command output, and
per-file hashes. Treat profile, collect, snapshot update, and cleanup as separately authorized
operations. Profiling cannot prove undocumented Codex hashing or indexing.

For already tracked raw evidence, prepare outside the repository before proposing cleanup:

```bash
python3 <shed>/scripts/migrate_generated_evidence.py prepare \
  --workspace <workspace> \
  --output <outside-repository-path>
```

Preparation is non-mutating. Apply requires a verified archive plus explicit top-level and per-file
approval. Never infer apply approval from a request to inspect, profile, plan, install, or update.

Check local version or canonical update status:

```bash
python3 <shed>/scripts/check_shed_version.py --shed <shed> --local-only
python3 <shed>/scripts/check_shed_version.py --shed <shed>
```

Run Level 2 existing-project onboarding:

```bash
python3 <shed>/scripts/onboard_existing_project.py "Project name" --workspace <workspace>
```

If scripts are missing, create files from the shed templates and preserve the naming/location conventions in `conventions.md`.

## Existing Projects

Default to Level 2 onboarding:

1. Create a project map.
2. Create an existing-project inventory.
3. Discover by reading front-door files, docs, code surfaces, tests, build/runtime files, existing planning files, and CI/workflow files.
4. Fill the map and inventory from observed evidence.
5. Refresh `work/index.md` and `work/index.json`.
6. Create deeper work artifacts only after review justifies them.

Do not invent history. Mark inferred or uncertain items clearly.

Routing rule:

- Stable current facts go to `docs/` or README files.
- Unresolved work, uncertainty, risks, and coordination needs go to `work/`.

## Verify

After creating or moving artifacts:

- Confirm files landed under `work/`.
- Refresh `work/index.md` and `work/index.json` when the script exists.
- Prefer `complete_workpackage.py` when moving active workpackages to completed.
- Check parent/map links when relevant.
- Scan for stale paths after moving completed workpackages.
- Run the work-state review and surface orphan, stale, disposition, and plan-drift findings.
- Run workspace preflight when validation may produce or expose bulk evidence.
- Keep migration preparation outside the repository, and never run migration apply without
  explicit approval of the exact manifest.
- Run relevant script syntax checks, such as `python3 -m py_compile`, when scripts changed.
- Keep git changes scoped to the shed/work artifacts involved.
