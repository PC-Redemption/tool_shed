# Tool Shed Operator Guide

Tool Shed helps a human and AI agent preserve project coordination in plain Markdown. The
workspace-local `tool_shed/` directory supplies reusable rules, templates, and scripts; the
project's tracked `work/` directory holds its planning artifacts.

## Getting Help

Type:

```text
ts: help
```

The active agent should read this guide and return a concise menu of relevant use cases with example prompts.
Help is read-only: it must not create or change artifacts unless the same request explicitly asks
for a change.

For the complete prompt inventory rather than a focused menu, type:

```text
ts: commands
ts: help all
```

Both routes read the [AI command reference](commands.md). Use `ts: help <topic-or-command>` for a
focused explanation and examples.

Ask for focused help with:

```text
ts: help spikes
ts: help existing projects
ts: help completing work
ts: help install
ts: help update
ts: help version
ts: help providers
```

## Discuss A Campaign Before Planning

Use discussion when an idea is still forming:

```text
discussion: should Tool Shed support another AI provider?
ts: discuss how to reduce campaign token cost
```

`ts: discuss` is the authoritative Tool Shed discovery route. `discussion:` is an informal
read-only entry signal. The agent explores the outcome, motivation, constraints, assumptions,
unknowns, and credible options, then recommends the smallest useful next route. It does not create
or modify an artifact unless the same request explicitly asks to capture or plan.

## Choose The Minimum Coordination Level

- Direct: clear, reversible, single-step work; no artifact.
- Guided: bounded known steps; checklist or ticket.
- Coordinated: dependencies, branching, multi-session work, or handoff; workpackage or map.
- Deep: consequential cross-layer uncertainty or repeated failure; bounded research and controlled
  evidence.

Start at the lowest adequate level, load only the route-specific instructions needed, and escalate
only when evidence shows additional risk or coordination cost.

Direct is the default for a clear, reversible bug fix or enhancement in one repository, including
requests dispatched through `ts:ask`. The agent resolves the named target once, makes the focused
change, and runs focused tests. It does not create planning artifacts, branches, PRs, releases,
deployments, evidence artifacts, or new worktrees unless you requested them, repository policy
requires them, or concrete risk, conflicting evidence, or an observed failure justifies expansion.
Campaign continuity keeps the request moving without upgrading its coordination level.

An optional `Coordination: direct` or `Route: direct` line makes the intended level explicit:

```text
Coordination: direct
In the current Django repository, replace the dashboard's 30-second reload with read-only SSE.
Run the focused dashboard tests.
```

Contrast that with a coordinated qualification campaign:

```text
Qualify and release the firmware update across the supported hardware matrix, preserve evidence,
document rollback, and hand the result to operations.
```

The second request has cross-target sequencing, evidence, release, rollback, and handoff cost, so a
workpackage and staged verification are appropriate.

## Use Another AI Provider

Tool Shed supports native instruction adapters for Codex, Claude Code, Gemini CLI, GitHub Copilot,
and Cursor:

```bash
python3 tool_shed/scripts/install_into_workspace.py . --provider <provider-id>
```

Repeat the option or use `--provider all`. Compatibility is expressed as a provider surface plus
capability level; a static planning adapter does not imply that every surface can deploy or verify.
See [provider adapters](provider-adapters.md).

## Choose An Execution Endpoint

Use the same five levels in every workspace:

| Route | Stop after |
| --- | --- |
| `ts:work1 <goal>` | A minimally checked local checkpoint commit; no deployment. |
| `ts:work2 <goal>` | Deployment to the configured work environment plus focused browser and changed-behavior checks. |
| `ts:work3 [scope]` | Full applicable validation/build and a locally frozen candidate. |
| `ts:work4 [scope]` | The frozen source is pushed without intentional production promotion. |
| `ts:work5 [scope]` | Production is released or promoted and verified. |

The levels are cumulative and do not change Direct, Guided, Coordinated, or Deep coordination.
Use `ts:work` as an alias for `work2`, `ts:freeze` for `work3`, `ts:push` for `work4`, and
`ts:ship` for `work5`. Use `ts:check <spot|focused|full|release>` when validation is wanted without
implementation, commits, pushes, deployment, or release.

The optional tracked file `work/tool-shed.yaml` declares how remote work maps to environments:

```yaml
schema_version: 1
work_model: combined
```

In `combined` mode, development and production share the configured target, so `work2` and
`work3` may change the live site. In `split` mode, those levels deploy only to development and
`work5` promotes the frozen candidate to production. Optional `development_target` and
`production_target` names are needed only when existing project docs and tooling do not already
resolve them.

The file does not hold credentials, create infrastructure, or grant deployment authority. If it
is absent, Tool Shed uses existing workspace evidence and asks one concise target question only
when safe routing is genuinely ambiguous. It rejects invalid schemas or modes. When a normal push
automatically deploys production, `work4` stops before that push unless production release is
explicitly authorized.

## Ship End to End

Use the ship route when the intended outcome is a delivered, verified change rather than a plan or
an intermediate implementation:

```text
ts:ship <goal>
```

`ts:ship` means: plan, implement, validate, build, deploy, and verify the requested workspace goal
end-to-end. Codex continues through every applicable stage, uses the project's own delivery
tooling, and verifies the result in the target environment before declaring completion.

A lifecycle stage is applicable only when the requested outcome includes it, repository policy
mandates it, or concrete risk or an observed failure justifies it. Merely mentioning, documenting,
or discussing `ts:ship` is not an end-to-end delivery request. When verification expands beyond
focused tests, the agent states the concrete reason.

The route authorizes the normal workspace changes and deployment actions needed for the stated
goal, but it does not override safety rules, protected-environment controls, required approvals,
or credential and authorization boundaries. Codex explains any inapplicable stage. If it cannot
safely deploy, it completes every safe preceding stage and reports the exact blocker.

Codex does not request repeated confirmation for reversible, in-scope steps that the operator has
already clearly authorized. One request may authorize multiple named operations. Codex asks
again only when an action materially expands scope, targets a protected environment, is destructive
or irreversible, uses an unknown deployment target, publishes externally, or otherwise requires
new authority.

For nontrivial work, Codex keeps the requested outcome and current limiting condition visible. It
compares the actual result with the expected state after material actions and updates the next
action when evidence changes the situation. A command completing successfully is not enough if the
target state is still wrong. This loop preserves the original authority boundary and is skipped as
explicit ceremony for simple answers and known single-step reversible work.

Before an already-authorized consequential stage, Codex checks at most three credible failure
modes and adds proportionate prevention, detection, verification, or rollback. Routine reversible
work does not receive a generic failure-analysis ritual.

## Campaign Status And Continuity

Tool Shed treats the requested outcome in the current chat as the campaign. A plan, checklist,
workpackage, test, build, or deployment may be part of that campaign, but finishing one does not
necessarily finish the requested outcome.

Codex keeps going when the next action is reversible, in scope, and already authorized. Progress
updates and useful inspection points do not become approval gates merely because the operator
might want to review them. Review pauses are reserved for explicitly requested review, material
unresolved decisions, evidence that contradicts the plan, new authority, or protected,
destructive, irreversible, or not-yet-authorized external actions.

Continuity preserves the selected coordination level. It does not upgrade Direct work to Guided,
Coordinated, or Deep or make an otherwise inapplicable lifecycle stage apply.

Every final response for a Tool Shed campaign ends with one explicit verdict:

- `Campaign status: COMPLETE` means the whole requested outcome and applicable verification are
  finished.
- `Campaign status: CONTINUE` means work remains, no operator decision is needed, and the response
  names the next concrete action. Codex does not use this verdict to stop when it can safely perform
  that action in the current turn.
- `Campaign status: BLOCKED` identifies the exact decision, dependency, permission, credential,
  external-state change, or required review preventing progress and the precise operator action.

When review is genuinely required, Codex points to the exact file or result and relevant section,
states the exact question or approval, and explains what resumes afterward. A vague request to
"review this" or "let me know" is not a valid handoff.

## Owner Campaign Queue

Tool Shed places durable owner-facing execution state in the first-sorted
`work/00-campaigns/` folder. This is separate from the transient Q&A inbox.

| Route | Result |
| --- | --- |
| `ts: status` or `ts: queue` | Show last completed, working now, next, blockers, detours, and lifecycle findings. |
| `ts: next` | Select and execute only the first ready campaign. |
| `ts: add <idea>` | Check overlap, dependencies, and direction conflicts before inserting an approved campaign. |
| `ts: unblock <campaign>` | Return blocked work to queued state and clear the blocker decision without starting it. |
| `ts: reconcile campaigns` | Inspect and propose deterministic queue repairs and execution order without writing. |
| `ts: defer <campaign>` | Move an active campaign with a reason and reactivation condition. |
| `ts: abandon <campaign>` | Preserve a cancelled or superseded campaign with its disposition. |
| `ts: completed` | Show recent verified outcomes newest-first. |

In owner-queue requests, `camp` is an alias for `campaign`, and `que N` identifies the campaign at
1-based ordered queue number N. Tool Shed resolves `que N` from a fresh status read immediately
before acting and rejects missing or out-of-range numbers rather than guessing.

The active queue is the canonical execution order. Detailed requests live in lifecycle folders:

```text
work/00-campaigns/
├── active-queue.md
├── completed-queue.md
├── active/
├── completed/
├── deferred/
└── abandoned/
```

Every mutation uses the current state token returned by `status`; a stale token is rejected.
Completion requires the request's explicit completion gate and applicable verification, then moves
the request and updates both queue views through a recoverable operation. Blocked work stays
active. Deferral and abandonment require explicit lifecycle reasons.

`reconcile_campaign_queue.py` is dry-run-first. Its report separates mechanically repairable
projection drift from stalled lifecycle decisions and a proposed execution order. An explicit
`--apply --expect TOKEN` repairs projections only; reprioritization remains owner-controlled.

Use `python3 tool_shed/scripts/campaign_queue.py --workspace . migrate-preview --json` to inspect
Markdown requests under `work/01-q&a/` or legacy `work/q&a/` and actionable inbox lines. Preview never writes, and
installation never converts those requests into campaigns or clears the canonical inbox. Applying
a campaign conversion requires a separately approved exact manifest. The filesystem migration of
legacy Q&A folders is a distinct installer operation described below.

## Q&A Inbox

The installer creates a workspace-local scratch inbox at `work/01-q&a/ask.txt`. Put a question or
direction there while Codex is busy, then type:

```text
ts:ask
```

Codex inspects the canonical file and `work/q&a/ask.txt`, which is supported only as a pre-migration
misplaced fallback. Blank lines and lines beginning with `#` are ignored in both files. If only the
canonical file is actionable, Codex uses it. If only the fallback is actionable, Codex may process
it but clearly identifies the noncanonical path. If both are actionable, Codex does not merge or
run either request; it reports the conflict and asks which one to use. If neither is actionable,
Codex reports that the inbox is empty.

The selected content keeps its natural coordination level. A small bug fix remains Direct; the
inbox transport does not create planning or delivery ceremony by itself.

Both files are preserved during read-only inspection. The installer separately migrates all files
from legacy `work/q&a/` and root `q&a/` into `work/01-q&a/`, verifies copied bytes, preserves
collisions under source-specific filenames, and removes the old folders. The canonical inbox is
ignored by Git because it is transient operator input, not project documentation or durable work
state.

## Common Use Cases

### Check reasoning before substantial work

Tool Shed performs a one-time, zero-I/O reasoning preflight before substantial routed work. It uses
only the request and current-session metadata. When a usable picker pair is known, it recommends
the lowest adequate choice on its own line, for example:

### **Reasoning: GPT-5.6 Terra / High**

It does not use abstract labels, claim to observe the active picker, or pause work for a reasoning
choice. If the available picker options are unknown, it continues silently instead of guessing.

The request path never refreshes catalogs. Refresh the optional account-aware diagnostic cache
after a Codex login/account change, client update, visible model-picker change, or cache expiry:

```bash
python3 tool_shed/scripts/reasoning_catalog.py refresh
python3 tool_shed/scripts/reasoning_catalog.py status
```

Equivalent requests are `ts: refresh reasoning catalog` and `ts: reasoning status`.
Use `ts: recommend reasoning <task>` when you want an explicit catalog refresh followed by a
concrete picker recommendation.

Refresh uses Codex app-server `model/list`; status is local-only. The cache preserves future model
and effort labels without treating release-time names as permanent policy. It cannot establish the
active thread setting, and stale data never blocks ordinary work.

### Orient in a project

Use this when returning to a project or deciding what deserves attention next.

```text
ts: orient me
ts: show active work and the next concrete actions
```

Codex reads project docs, `work/index.md`, active maps and artifacts, then runs the read-only
work-state review.

### Capture a small known task

Use a checklist when the steps are known and forgetting one is the main risk.

```text
ts: create the smallest artifact for validating the release
ts: make a checklist for cleaning up the root documentation
```

### Record a bug or enhancement

Use a ticket when expected behavior and acceptance criteria are clear.

```text
ts: create a ticket for the broken retry behavior
```

### Coordinate a larger change

Use a workpackage for a multi-step transformation and a project map when several workstreams or
artifacts must stay aligned.

```text
ts: plan the authentication migration
ts: map the active workstreams and show the current ground task
```

### Investigate uncertainty

Use a spike when the deliverable is learning rather than production code.

```text
ts: create a time-boxed spike to compare deployment options
ts: create a deep-research spike for the cross-layer compatibility contract
```

Choose deep research when unresolved uncertainty spans technical layers, compliant specimens
diverge, a second mitigation failed, or a proposed fix depends on narrow vendor/model heuristics.
Start it before a third mitigation when compatibility, reliability, safety, or data integrity is
broadly affected. Importance or elapsed time alone is not a trigger. Create it with:

```bash
python3 tool_shed/scripts/new_artifact.py deep-research "Compatibility contract" --workspace .
```

Tool Shed structures the evidence; it does not search for it. Use the resulting research to focus
target tests, then promote settled conclusions to project docs. Bound the effort, allow urgent
reversible containment when necessary, and pause speculative production heuristics until
mandatory, optional, and implementation-specific behavior are separated.

When a spike finishes, record `Disposition:` as `planned`, `documented`, `no-action`, or
`superseded`. A planned spike names its follow-up artifact in `Produces:`.

### Preserve a decision or operation

Use an ADR for a durable decision, a decision matrix to compare options, and a runbook for a
repeatable operation.

```text
ts: record the database choice as an ADR
ts: compare these hosting options in a decision matrix
ts: create a rollback runbook
```

### Onboard an existing project

Use Level 2 onboarding to create a project map and inventory before backfilling detailed work.

```text
ts: onboard this existing project
```

Codex observes the repository before creating inferred history. Stable facts go to project docs;
unresolved work stays under `work/`.

### Review planning drift

Use reconciliation when artifacts may have fallen out of sync with plans.

```text
ts: review work state
ts: find orphaned, stale, or undisposed work
```

The underlying command is:

```bash
python3 tool_shed/scripts/review_work_state.py --workspace .
```

It is advisory by default. `--json` supports automation and `--strict` makes findings fail the
command.

### Complete or supersede work

```text
ts: complete work/wp/active/wp-example.md
ts: supersede this decision and preserve the history
```

Completed artifacts remain history. Promote settled current truth to project `docs/` or README
files.

### Install or update Tool Shed

```text
ts: help install
ts: help update
```

The canonical source is [PC-Redemption/tool_shed](https://github.com/PC-Redemption/tool_shed).
Installations are disconnected snapshots: ignore `/tool_shed/`, remove its `.git/`, and track
project-specific `/work/` by default. An update replaces only Tool Shed machinery and must preserve
`work/`, project docs, and code.

Use the supported updater from a current released Tool Shed checkout:

```bash
python /path/to/current/tool_shed/scripts/update_snapshot.py --workspace .
```

If the installed snapshot predates the updater, obtain the current released checkout outside the
project and run it from there. The Python updater is authoritative on Windows and Linux; thin
PowerShell and POSIX launchers are also included. It selects and verifies the highest stable tag
with Git line-ending conversion disabled, creates a recoverable backup for updates, preserves
project `work/`, and automatically restores the previous snapshot after failed post-install
verification. See [install-or-update-snapshot.md](install-or-update-snapshot.md) for the complete
guarded contract.

After installation or update, run:

```bash
python3 tool_shed/scripts/install_into_workspace.py .
python3 tool_shed/scripts/review_work_state.py --workspace .
```

Both commands detect a root `work/` ignore. An existing rule is not automatically repository
policy. Without a valid repository-root `.tool-shed-policy.json` exception, the output identifies
the exact ignore source and matching rule and previews the count and size of ignored files. Remove
only that root `/work/` rule. Do not delete, replace, relocate, or rewrite any `work/` evidence.

`work/evidence/` is the standard validation-evidence repository. Keep Markdown summaries and
small manifests versioned there, and write raw captures, dumps, images, large logs, and test
payloads under ignored `work/evidence/generated/`. Run
`python3 tool_shed/scripts/workspace_preflight.py --workspace .` before large campaigns.
Use `.git/info/exclude` for additional machine-local evidence paths.

Preflight adapts to the repository it inspects. Its JSON output includes the discovered workspace
profile, effective risk budget, policy source for each threshold, finding severity, and suggested
mitigation. Repository-root `.tool-shed-policy.json` can declare a reasoned generated path and
threshold adjustments; hard safety limits remain in force and invalid or reason-free policy is
reported.

To measure whether repository and `work/` growth correlate with slower operations, run:

```bash
python3 tool_shed/scripts/profile_workspace_performance.py --workspace .
python3 tool_shed/scripts/profile_workspace_performance.py --workspace . --json
```

The profiler is read-only, local, and privacy-allowlisted. It times representative Git,
filesystem, and Tool Shed operations but cannot prove undocumented Codex hashing or indexing.
Profiling does not authorize report collection, snapshot updates, cleanup, or archival. See
`docs/workspace-performance-profiling.md` for the report and comparison protocol.

For raw evidence that is already tracked, prepare a reversible migration:

```bash
python3 tool_shed/scripts/migrate_generated_evidence.py prepare \
  --workspace . \
  --output /safe/outside/path/evidence-migration
```

Preparation is read-only with respect to the repository. It classifies candidates as `keep`,
`migrate`, or `review`, records hashes and reasons, and creates an archive outside the repository.
Apply is a separate human-gated step: approve the manifest and individual migrate candidates, then
run `migrate_generated_evidence.py apply`. The helper revalidates the archive and source hashes,
requires an ignored destination, changes only approved files, and never rewrites history.

Rollback remains deliberate: inspect and extract `evidence-backup.tar` into a separate recovery
directory, verify restored hashes against `evidence-migration.json`, and copy only selected files
back to their recorded original paths. Never extract an unreviewed archive directly over the
repository.

An intentional exception uses:

```json
{
  "schema_version": 1,
  "work_git_policy": {
    "ignore": true,
    "reason": "Repository-specific reason for excluding project work artifacts."
  }
}
```

Evidence-specific adaptation can coexist in the same policy file:

```json
{
  "schema_version": 1,
  "evidence_policy": {
    "reason": "UI validation produces many screenshots and recordings.",
    "generated_path": "test-results/generated",
    "evidence_paths": ["test-results", "playwright-report"],
    "thresholds": {
      "untracked_count": 150,
      "untracked_bytes": 209715200
    }
  }
}
```

### Check version and update status

```text
ts: version
ts: check for updates
ts: update status
```

`ts: version` verifies the local snapshot against its own `SHED_VERSION.json` without using the
network. An update-status request also reads the canonical manifest from GitHub and distinguishes:

- `current`: local and canonical versions match and local tracked files are intact
- `older`: canonical has a newer semantic version
- `newer`: local declares a version ahead of canonical
- `modified`: local tracked content differs from its version manifest
- `release-mismatch`: equal local/canonical versions contain different release manifests
- `check-failed`: canonical status could not be retrieved or parsed

The check is read-only and never authorizes or applies an update.

## Artifact Menu

| Need | Artifact |
| --- | --- |
| Known bounded steps | Checklist |
| Clear bug or enhancement | Ticket |
| Multiple workstreams and navigation | Project map |
| Multi-step transformation | Workpackage |
| Durable decision | ADR |
| Repeatable operation | Runbook |
| Break/fix learning | Incident |
| Time-boxed uncertainty | Spike |
| Classify or route a collection | Inventory |
| Compare plausible options | Decision matrix |

When unsure, ask:

```text
ts: choose the smallest artifact for this: <describe the need>
```

Tool Shed should not become a server, database, general task tracker, or replacement for canonical
project documentation.
