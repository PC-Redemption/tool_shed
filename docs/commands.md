# Tool Shed AI Command Reference

Tool Shed commands are prompts for a workspace-capable AI agent. They are not shell commands and
there is no separate Tool Shed server. Put one route at the start of the request; it applies only
to that request.

Use this page for the complete prompt inventory. Use the
[operator guide](operator-guide.md) for workflows and examples, and use `--help` on the underlying
Python scripts for their CLI arguments.

## Syntax

```text
ts: <request>
```

The `ts:` prefix routes the remainder of the request to the workspace-local Tool Shed. It does not
carry into the next message. A natural-language request may combine planning with an execution
endpoint, for example:

```text
ts: plan the documentation refresh, then work3
```

Routes never bypass repository policy, safety controls, credentials, protected-environment
approvals, or the authority stated in the request.

## Help And Discovery

| Prompt | Usage |
| --- | --- |
| `ts: help` | Return a concise use-case menu. Read-only unless the same request explicitly asks for a change. |
| `ts: commands` | Return the complete command groups and usage from this reference. Read-only. |
| `ts: help all` | Alias for the complete command reference. Read-only. |
| `ts: help <topic-or-command>` | Explain the named workflow or route with relevant examples. Read-only. |
| `ts: discuss <topic>` | Explore the outcome, constraints, assumptions, unknowns, and smallest useful next route without modifying workspace artifacts. |
| `ts: build focus areas` | Inspect existing workspace sources and propose a project-specific focus-area catalog and active-campaign assignments. Requires explicit approval before writing. |
| `ts: develop roadmap` | Read project evidence and clarify an opt-in Program Roadmap without mutation. |
| `ts: overview` | Combine maps, approved roadmaps, gates, focus areas, campaign state, and drift. Read-only. |

`discussion: <topic>` is also accepted as an informal, read-only discussion signal.

## Execution Endpoints

The numbered levels are cumulative stopping points. They do not make a Direct request more
complex or grant authority outside the stated goal.

| Prompt | Stop after |
| --- | --- |
| `ts:work1 <goal>` | Implement, run the quickest meaningful check, and create a scoped local checkpoint commit. Do not deploy. |
| `ts:work2 <goal>` | Perform work1, deploy to the configured work environment, and run focused browser and changed-behavior checks. |
| `ts:work3 [scope]` | Review the accumulated coded work and create, read, update, or delete project documentation as needed so it matches the candidate; then fully validate and build, update the work environment when relevant, and freeze it locally. |
| `ts:work4 [scope]` | Perform work3, then push without intentionally promoting production. |
| `ts:work5 [scope]` | Qualify, push, release or promote production, and verify the production target. |

Readable aliases:

| Alias | Equivalent route |
| --- | --- |
| `ts:work <goal>` | `ts:work2 <goal>` |
| `ts:freeze [scope]` | `ts:work3 [scope]` |
| `ts:push [scope]` | `ts:work4 [scope]` |
| `ts:ship <goal>` | `ts:work5 <goal>` |

Validation-only route:

```text
ts:check <spot|focused|full|release>
```

This validates only. It does not implement, commit, push, deploy, or release.

Work3 document changes stay within the requested candidate scope. Preserve unrelated owner
documentation and historical records, and delete documentation only when the coded change makes it
obsolete.

Projects may define `work/tool-shed.yaml` with `work_model: combined` or `work_model: split`.
Combined work and production targets mean work2 or work3 may affect the live site. Split mode
reserves production promotion for work5.

## Owner Campaign Queue

Durable owner-facing state lives under `work/00-campaigns/`.

| Prompt | Usage |
| --- | --- |
| `ts: status` | Show and validate the active owner capsule, including any pending or active Dangler Resolution campaign for unclassified work. |
| `ts: queue` | Alias for `ts: status`. |
| `ts: completed` | Summarize recent verified campaign completions. |
| `ts: next` | Select the first ready campaign and surface pending Dangler Resolution work before reconciliation adds it. |
| `ts: add <idea>` | Check active, deferred, and completed work for overlap or direction conflicts, then add the approved campaign using the current state token. |
| `ts: unblock <campaign>` | Return blocked work to queued state and clear its recorded decision; starting remains a separate transition. |
| `ts: reconcile campaigns` | Inspect queue and whole-`work/` coverage, automatically creating or refreshing one Dangler Resolution campaign as the first queued work. |
| `ts: defer <campaign>` | Move active work to deferred with a reason and reactivation condition. |
| `ts: abandon <campaign>` | Preserve cancelled or superseded work with a disposition and replacement when applicable. |

Owner-queue shorthand:

| Term | Meaning |
| --- | --- |
| `camp` | Alias for `campaign`. |
| `que N` | Alias for the campaign at 1-based ordered queue number N. |

Resolve `que N` from a fresh queue status immediately before acting. Missing or out-of-range
numbers are errors and are never guessed.

Blocked work remains active. Queue mutations reject stale state and do not silently reorder
ambiguous priorities. Campaign completion requires its explicit completion gate and applicable
verification.

Queue entries are readable cards with icon-plus-text readiness states: `WORKING`, `READY`,
`WAITING`, `BLOCKED`, or `COMPLETE`. The state comes from the same dependency/decision calculation
used by `next` and reconciliation. Projects may approve an evidence-backed catalog at
`work/focus-areas.md`; once approved, active campaigns require known `Primary Focus Areas` and may
also declare `Supporting Focus Areas`. The CLI accepts repeatable `--primary-focus-area ID` and
`--supporting-focus-area ID` options on `add`.

### Build Focus Areas From Existing Sources

```text
ts: build focus areas
```

The agent inspects enduring project evidence across source, documentation, tests, integrations,
runtime and hardware boundaries, qualification, delivery workflows, and durable work history. It
then presents an exact proposed catalog with stable IDs, boundaries, evidence paths, uncertainty,
coverage gaps, and proposed assignments for every active campaign.

This first stage is read-only. The command does not silently create or approve
`work/focus-areas.md`, and an existing approved catalog keeps its stable IDs and accepted
boundaries unless the proposal names evidence for a change. After the owner explicitly approves
the exact catalog and assignment set, the agent writes the approved catalog, applies the active
campaign assignments, refreshes indexes, and validates campaign state, stale paths, and work state.

The deterministic reconciliation utility automatically creates or refreshes one Dangler
Resolution campaign when unclassified unresolved artifacts exist. It places that campaign first
among queued work while preserving any currently working campaign. It also reports complete scan
and exclusion totals; explicit `Campaign: <id>`, `Campaign: standalone`, and `Campaign: excluded`
associations; unresolved artifact clusters; lifecycle mismatches; and queue projection drift:

```bash
python3 tool_shed/scripts/reconcile_campaign_queue.py --workspace . --json
```

Use `--dry-run` to inspect and save the exact proposed manifest without changing the workspace:

```bash
python3 tool_shed/scripts/reconcile_campaign_queue.py --workspace . --dry-run --json \
  | jq '.reconciliation_manifest' > /tmp/campaign-reconciliation.json
```

Automatic mutation is limited to creating or refreshing Dangler Resolution. After reviewing any
other `reconciliation_manifest` operations, save the exact approved manifest and pass `--apply
--expect TOKEN --manifest PATH`. The token covers the complete scanned work surface.
Generated projection repairs preserve the current valid relative order and never apply the
separately reported execution-order proposal. Approved manifest operations can create campaigns,
set explicit associations or focus areas, or transition campaigns; terminal transitions preserve
lifecycle history instead of deleting files. `migrate-preview` can suggest exact
`set_focus_areas` operations for fully matched legacy `Focus areas: ...` outcome prose, but it
never rewrites that prose itself. Ambiguous semantic, catalog-approval, or priority choices remain
owner-owned.

```bash
python3 tool_shed/scripts/reconcile_campaign_queue.py --workspace . \
  --apply --expect <whole-work-token> --manifest /tmp/campaign-reconciliation.json --json
```

## Program Roadmaps

Use this optional lifecycle when a project map needs approved phases, milestones, gates, and
rolling-wave campaign planning:

| Prompt | Usage |
| --- | --- |
| `ts: develop roadmap` | Read and classify project evidence. Greenfield projects establish and approve the initial map first. No writes. |
| `ts: propose roadmap` | Capture an exact proposed roadmap revision from a fresh source-state token. Creates no campaigns. |
| `ts: approve roadmap <token>` | Approve exactly one unchanged proposal; preserve any prior approved revision as superseded. |
| `ts: derive campaigns for milestone <id>` | Preview an exact dependency-aware campaign manifest for one milestone. No writes. |
| `ts: approve campaign plan <token>` | Materialize only the exact current manifest. Does not start campaign execution. |
| `ts: roadmap status` | Compute milestone and gate progress from linked campaign evidence. No writes. |
| `ts: review roadmap` | Report assumptions, source drift, blockers, and revision needs. No writes. |
| `ts: overview` | Show whole-project strategic and execution state together. No writes. |

The deterministic CLI is:

```bash
python3 tool_shed/scripts/program_roadmap.py --workspace . develop --roadmap-id <id> --json
python3 tool_shed/scripts/program_roadmap.py --workspace . propose --manifest proposal.json --expect <source-token>
python3 tool_shed/scripts/program_roadmap.py --workspace . approve <id> --revision <n> --expect <source-token> --proposal-token <token>
python3 tool_shed/scripts/program_roadmap.py --workspace . derive <id> --milestone M1 --json
python3 tool_shed/scripts/program_roadmap.py --workspace . apply-campaign-plan --manifest campaign-plan.json --expect <manifest-token>
python3 tool_shed/scripts/program_roadmap.py --workspace . overview --json
```

Roadmap and campaign-plan approval are separate authority boundaries. Every mutation rejects stale
source, roadmap, or queue state. Existing standalone maps and queues remain supported.

## Q&A Inbox

```text
ts:ask
```

Read actionable content from canonical `work/01-q&a/ask.txt`, using legacy
`work/q&a/ask.txt` only as a pre-migration fallback. The agent does not merge conflicting inboxes
or move, clear, rewrite, or delete inbox content without explicit authorization. Inbox transport
does not change the request's natural coordination level.

## Version And Update Status

| Prompt | Usage |
| --- | --- |
| `ts: fulltsupgrade` | Upgrade the current existing Tool Shed installation end-to-end from the latest verified published GitHub release, including guarded backup/update, provider convergence, full validation, installed Codex skill synchronization when applicable, exact verification, and rollback. |
| `ts: version` | Verify the local Tool Shed snapshot and report its version without network access. |
| `ts: check for updates` | Verify locally, compare with the canonical manifest, and report the version relation. Read-only. |
| `ts: update status` | Alias for `ts: check for updates`. Read-only. |

An update-status check does not authorize replacement. Ask explicitly to install or update Tool
Shed when mutation is intended.

`ts: fulltsupgrade` is the concise full-authorization exception for the current installation. It
does not authorize publishing a release, rewriting history, forcing over modified or unmanaged
state, deleting unknown recovery material, or updating other workspaces or fleet targets.

## Codex Reasoning Maintenance

These optional routes apply only to Codex:

| Prompt | Usage |
| --- | --- |
| `ts: refresh reasoning catalog` | Refresh the account-aware local model/effort catalog. |
| `ts: reasoning status` | Inspect the local catalog without network access. |
| `ts: recommend reasoning <task>` | Refresh the catalog and recommend a concrete advertised model/effort pair for the task. |

Ordinary Tool Shed requests do not refresh or require this catalog.

## Artifact And Workspace Requests

Artifact operations use natural language after `ts:` rather than a rigid subcommand parser. Common
request forms are:

```text
ts: orient me
ts: choose the smallest artifact for this: <need>
ts: create a checklist for <goal>
ts: create a ticket for <behavior change>
ts: plan <multi-step outcome>
ts: map the active workstreams
ts: create a time-boxed spike for <unknown>
ts: record <decision> as an ADR
ts: create a rollback runbook
ts: review work state
ts: complete work/wp/active/<workpackage>.md
ts: onboard this existing project
ts: install Tool Shed in this workspace
ts: update Tool Shed in this workspace
```

The agent chooses the smallest sufficient artifact: checklist for bounded known steps, ticket for
a specific behavior change, project map for multiple workstreams, workpackage for a multi-step
transformation, ADR for a durable decision, runbook for a repeatable operation, incident for
break/fix learning, spike for bounded uncertainty, inventory for classification, and decision
matrix for visible tradeoffs.

## Related Shell Utilities

The AI routes normally operate these deterministic scripts from the workspace-local Tool Shed:

```text
scripts/campaign_queue.py
scripts/check_work_tree.py
scripts/check_shed_version.py
scripts/check_stale_paths.py
scripts/complete_workpackage.py
scripts/install_into_workspace.py
scripts/new_artifact.py
scripts/program_roadmap.py
scripts/read_ask_inbox.py
scripts/reconcile_campaign_queue.py
scripts/review_work_state.py
scripts/update_snapshot.py
scripts/update_work_index.py
scripts/workspace_preflight.py
```

Run `python3 <script> --help` for the exact shell interface. The scripts are the automation layer;
the `ts:` prompts are the operator-facing AI interface.
