# tool_shed

[![Validate](https://github.com/PC-Redemption/tool_shed/actions/workflows/validate.yml/badge.svg)](https://github.com/PC-Redemption/tool_shed/actions/workflows/validate.yml)

`tool_shed` is a provider-neutral collaboration toolkit for structured work with AI agents.

It is not the project. It is the workbench copied into or referenced from a project workspace so human and assistant can choose the right artifact, use the same shapes consistently, and keep project code/documentation uncluttered.

Core boundary:

```text
tool_shed/ = tools, templates, rules
work/      = project-specific work artifacts
docs/      = settled project documentation
code/      = product implementation
```

Short version:

**tool_shed creates. work contains. docs canonize. code implements.**

## What This Is For

Use `tool_shed` when a project benefits from consistent structure for:

- checklists
- tickets
- project maps
- Program Roadmaps
- workpackages
- ADRs
- runbooks
- incidents
- spikes
- inventories
- decision matrices

## What This Is Not

The reusable `tool_shed/` machinery directory is not:

- a server
- a database
- a task tracker
- a place for active project state (durable active state belongs under root `work/`)
- a place for app code
- a replacement for project docs

No server should be required. Start with plain files, Python scripts, and Git. Provider adapters
add native instruction discovery without changing the portable artifact model.

## AI Provider Support

Tool Shed ships one portable Agent Skills workflow plus native instruction adapters for OpenAI
Codex, Anthropic Claude Code, Google Gemini CLI, GitHub Copilot, and Cursor. Compatibility is
declared by product surface and capability level rather than as a binary claim.

```bash
python3 tool_shed/scripts/install_into_workspace.py . --provider codex
python3 tool_shed/scripts/install_into_workspace.py . --provider claude-code
python3 tool_shed/scripts/install_into_workspace.py . --provider all
```

Omitting `--provider` preserves the historical Codex default. See
[provider adapters](docs/provider-adapters.md) for native paths, capability levels, and conformance
gates.

## Recommended Project Layout

When installed into a project workspace:

```text
project/
  tool_shed/
  work/
    00-campaigns/
      active-queue.md
      completed-queue.md
      active/
      completed/
      deferred/
      abandoned/
    01-q&a/
      ask.txt
    README.md
    index.md
    index.json
    tool-shed.yaml  # optional environment model
    maps/
    roadmaps/
    wp/
      active/
      completed/
    tickets/
    adr/
    incidents/
    runbooks/
    spikes/
    checklists/
    inventories/
    decisions/
    evidence/
      generated/
  docs/
  ...
```

Project-specific artifacts should go under `work/`, not inside `tool_shed/`.

## Workspace Installation Boundary

Install `tool_shed/` into a project as a local, one-way snapshot of the blank templates, instructions, and helper scripts. The workspace copy is not a checkout for developing the canonical Tool Shed repository.

Canonical source: [https://github.com/PC-Redemption/tool_shed](https://github.com/PC-Redemption/tool_shed)

- Do not leave `tool_shed/.git/` in the project workspace.
- Do not configure the workspace copy as a Git submodule.
- Do not run `git pull`, `git push`, or otherwise return workspace changes to `PC-Redemption/tool_shed`.
- Add `/tool_shed/`, `/tool_shed.backup-*.tar`, and `/work/evidence/generated/` to the project repository's root `.gitignore`.
- Keep project-specific artifacts in root `work/` and track that directory with the project by default.
- Ignore root `work/` only through the explicit, documented repository exception described below. An existing `/work/` ignore is not evidence of an intentional exception.

Use the supported cross-platform updater from a current Tool Shed release checkout:

```bash
python /path/to/current/tool_shed/scripts/update_snapshot.py --workspace . \
  --project-binding <update-snapshot-binding>
```

Codex users can explicitly synchronize the separately installed user-level skill during the same
verified update:

```bash
python /path/to/current/tool_shed/scripts/update_snapshot.py --workspace . --sync-codex-skill \
  --project-binding <update-snapshot-binding>
```

For the concise, fully authorized upgrade route, type:

```text
ts: fulltsupgrade
```

This upgrades the current existing Tool Shed installation from the latest verified published
GitHub release, including backup, provider convergence, exact release qualification and focused
client-installation validation, installed Codex skill synchronization when applicable, exact
verification, and rollback on failure. Overridden, unattested, or changed validation identities
fall back to the complete local validator. It does not publish
a new release, rewrite history, overwrite modified or unmanaged installations, delete unknown
recovery material, or update other workspaces.

It detects a new installation versus an existing update, selects the highest stable tag, disables
Git line-ending conversion, verifies two-commit release provenance and byte-level manifest
integrity, stages a disconnected snapshot, retains a verified update backup, preserves
owner-authored `work/` content while transactionally converging Tool Shed-owned work topology and
indexes, refreshes auto-detected provider guidance, and restores the snapshot, affected workspace
state, and provider instruction files after a failed post-install check. Codex skill state is always
reported when the Codex adapter is selected. Synchronization is
opt-in: a missing skill can be installed and an exact prior released skill is backed up outside the
active `skills/` discovery directory and replaced, while a modified, unmanaged, or unsafe skill is
refused. Start a fresh Codex session
after synchronization so discovery does not retain the old instructions. POSIX and PowerShell
launchers are available as `scripts/update-tool-shed.sh` and `scripts/update-tool-shed.ps1`.

Before writing a backup, the updater reports the exact transaction mutation surface and estimated
archive size. The embedded manifest records included and excluded paths, per-file hashes,
source/target versions, protocol, timestamp, and transaction identity. Ordinary updates exclude
untouched policy-declared generated output such as `work/evidence/generated/`; a protocol may
expand scope only when it declares why that path can be mutated. Rollback removes or restores only
the declared paths and verifies excluded generated trees remain unchanged.

After the update, all validation, and optional Codex skill synchronization succeed, the updater
verifies updater-owned workspace and skill backups, protects the immediate rollback archive, and
keeps the newest two by default. It prunes only older archives with valid ownership manifests;
unknown, malformed, manually named, unsupported, or unverifiable recovery material is preserved
and reported. Deletion is irreversible. Use `--backup-retention COUNT`, `--no-prune-backups`, or
the read-only `--prune-preview`. A repository policy can set
`backup_policy.retention` in `.tool-shed-policy.json`. No-op current-version checks create no new
archive.

The updater emits concise clone/fetch, manifest, release-validation, staging, post-install, and
completion progress to stderr, plus a heartbeat every 20 seconds while a phase remains active,
leaving `--json` stdout machine-readable. Clone and fetch commands default to a 120-second timeout;
release and post-install validators default to 900 seconds. Use `--network-timeout SECONDS` or
`--validation-timeout SECONDS` when a known-slow environment needs a different explicit bound.

One recoverable user-local lock prevents concurrent upgrades of the same workspace. Successful
release validation is reusable only for the exact release commit, validator hash, operating
system, architecture, Python implementation, and Python version. Every attempt writes a sanitized
transaction report beneath `${CODEX_HOME:-~/.codex}/tool-shed/snapshot-upgrade-transactions/` with
stage durations, validation mode/cache state, error class, and rollback outcome. Reports never
contain prompts, responses, command output, credentials, secrets, or workspace paths.

Final transactions also carry stable `TSU-*` issue codes and a bounded updater identity. Run
`python scripts/snapshot_upgrade_report.py latest` (or supply an exact transaction ID) for a
sanitized maintainer-ready Markdown draft; add `--json` for structured output. The reporter is
read-only, rejects foreign or malformed records, and cannot publish to GitHub.

If the installed snapshot predates `update_snapshot.py`, obtain a current released Tool Shed
checkout outside the project and run the updater from that checkout. Never replace or pull inside
the stale workspace snapshot to bootstrap the updater.

After a new installation, or when a workspace needs its work tree initialized, run
`install_into_workspace.py`. Protocol-3 snapshot updates run the selected release's full installer
transactionally so older work trees converge to the current structure. The full installer detects whether the
parent Git repository ignores root `work/`. If a stale ignore exists, it reports the exact ignore
file, line, and rule; previews the count and size of ignored evidence; and exits without altering
any existing `work/` file. Remove only the reported root `/work/` rule and rerun the command.

An intentional exception must be documented in tracked repository-root
`.tool-shed-policy.json`:

```json
{
  "schema_version": 1,
  "work_git_policy": {
    "ignore": true,
    "reason": "Explain why this repository must not track project work artifacts."
  }
}
```

The exception file makes the departure from the default reviewable; the matching Git ignore rule
remains separate. Missing, malformed, or reason-free policy does not legitimize an ignored
`work/`.

## Validation Evidence

`work/evidence/` is the standard repository for validation evidence. Markdown evidence and
selected small JSON summaries or manifests remain visible and versionable. Raw `.bin`, `.dmp`,
images, device captures, large logs, and test payloads belong in the ignored
`work/evidence/generated/` directory.

Each campaign should leave a small versioned manifest with hashes, timestamps, target identity,
commands or test IDs, outcomes, and relative raw-artifact locations. The installer preserves
existing `.gitignore` and provider-native instruction content and appends or refreshes only marked
Tool Shed rules.

Before a long campaign, run:

```bash
python3 tool_shed/scripts/workspace_preflight.py --workspace .
```

Preflight profiles the workspace, including repository scale, tracked and untracked evidence,
dominant evidence types, large files, dirty state, and explicit evidence policy. It derives
explainable thresholds from that profile while retaining non-overridable hard safety limits.
Defaults start at 50 untracked files, 25 MiB of untracked data, or a 1 MiB tracked diff and scale
for larger repositories. It also detects binary files beneath versioned `work/` paths and visible
root `tool_shed.backup-*.tar` archives. It never deletes, moves, ignores, or rewrites evidence.

Use repository-root `.tool-shed-policy.json` to declare a reasoned generated path or threshold
adjustments for the current workspace. Policy is visible in JSON output, cannot silently bypass
hard limits, and never makes a hazardous existing baseline safe merely because it already exists.
See [conventions.md](conventions.md) for the schema.

For a repository that already tracks raw evidence, prepare a reversible migration outside the
repository:

```bash
python3 tool_shed/scripts/migrate_generated_evidence.py prepare \
  --workspace . \
  --output /safe/outside/path/evidence-migration
```

Review the generated manifest, set top-level `approved` and only intended per-candidate `approved`
fields to `true`, then run its `apply` subcommand. Apply verifies the archive, source hashes, exact
workspace, and ignored destination before moving approved files. It does not stage, commit, delete
the rollback archive, or rewrite Git history.

For rollback, inspect and extract `evidence-backup.tar` into a separate recovery directory, verify
the restored file hashes against `evidence-migration.json`, then copy only the intended files back
to their recorded original paths. Do not extract an unreviewed archive directly over the
repository.

Use repository-root `.gitignore` for the shared generated path. Use `.git/info/exclude` for
machine-local evidence or to adopt the mitigation around existing evidence without relocating it.

## Quick Start

Operator help and use cases:

```text
ts: help
ts: commands
ts: help spikes
ts: help existing projects
ts: discuss <topic>
ts: identity
ts: use <project-alias-or-path>
ts: doctor
ts: build focus areas
ts: appserver status
ts: plan <request> --app-server
ts: verify <request> --app-server
ts: camp run <camp> --app-server
ts: status
ts: next
ts: next --app-server
ts: next 1,2
ts: next *
ts:work1 <goal> ... ts:work5 <goal>
ts:check <spot|focused|full|release>
ts:ask
```

See the [AI command reference](docs/commands.md) for every defined route, alias, and authority
boundary. See the [Tool Shed operator guide](docs/operator-guide.md) for workflow explanations and
examples.

The four `--app-server` forms are explicit, per-command opt-ins for qualified real-world testing.
`ts: next --app-server` performs the ordinary `next` selection and forwards the option only when
the selected action already has a qualified App Server role; CAMP execution reuses the existing
Terra/medium runner. `next` itself is not an App Server role.
Unflagged commands remain in the GUI and `ts: discuss` is always GUI-native. Read-only planning and
verification use a minimum Codex version of `0.146.0` with no upper cutoff: an unseen eligible
version runs a bounded dirty qualification and continues the original explicit request immediately
only when that qualification passes. Sanitized results are cached outside Tool Shed under the
user's Codex state so the same executable and policies do not repeat the harness. Transient
authentication, network, service, or model-catalog failures are never cached and remain retryable;
reviewed unsafe denials remain authoritative until their fingerprint changes or the operator uses
explicit requalification. Versions below the floor, unsafe or unknown qualification outcomes, and
unqualified roles fail closed. CAMP writing remains
version-specific and requires a separate reviewed write harness. The committed global App Server
default remains off. `ts: appserver on|off` is intentionally unavailable because the skill surface
has no reliable session-scoped state store; use the explicit option on each test command.

App Server tooling resolves Codex through one bounded resolver. A supplied override remains
authoritative. Without one, the resolver inventories `PATH`, trusted platform locations, and
OpenAI VS Code extension bundles, then selects the highest semantically eligible CLI at or above
`0.146.0`; source priority breaks only equal-version ties. An older `PATH` executable therefore
cannot mask a newer eligible bundle. On Linux, bundles are limited to desktop, Insiders, remote-server, and
remote-server Insiders extension roots and the x86_64, aarch64, and arm64 Codex payloads. It
validates `--version` and App Server support separately, so status can report
the complete candidate inventory, selected path and source, executable-specific enabled roles,
and exact-qualified, dirty-qualifying, below-minimum, transient-fallback, unsafe-blocked, and
write-not-qualified states. The same resolver is used by status,
selection, smoke, startup, version detection, qualification, reasoning refresh, and installation
and upgrade readiness checks. It never installs Codex, changes permanent `PATH`, searches arbitrary
locations, or enables API fallback; missing Codex only makes explicit App Server execution unavailable.

Every installed workspace has one tracked `work/tool-shed-project.json` identity containing a
stable UUID and project name. Before the first mutation in a provider session, `ts: identity`
surfaces a target capsule with that identity, the resolved repository root, repository fingerprint,
working campaign or operation, and an operation-specific session binding. State tokens also hash
the project ID and resolved root, so byte-identical workspaces and ordinary clones cannot exchange
mutation tokens accidentally. Deterministic mutations require both the fresh state token and the
matching `--project-binding` when they have a token-bearing lifecycle.

An absolute path outside the bound root produces `WORKSPACE_MISMATCH`; mentioning or reading a path
does not switch projects. `ts: use <project-alias-or-path>` is the explicit read-only switch
boundary: verify the target identity, then reload its instructions and Tool Shed skill and obtain
fresh target-bound state before writing. Generic file and shell tools obey the same fence.

Audit the complete supported workspace surface with one read-only command:

```bash
python3 tool_shed/scripts/doctor.py --workspace .
python3 tool_shed/scripts/doctor.py --workspace . --json --strict
```

Equivalent routing is `ts: doctor`. The command composes boundary, integrity, preflight, Git,
topology, campaign, index-freshness, stale-path, work-state, and reconciliation checks into one
`HEALTHY`, `DEGRADED`, `NEEDS_DECISION`, or `INVALID` verdict with compact findings and exact next
actions. It explicitly does not prove current external/runtime truth. Token-bound `--repair`
regenerates stale deterministic work indexes only; semantic and lifecycle repair remains under the
existing manifest and owner-approval boundaries.

`ts: discuss <topic>` is a non-mutating discovery route. A leading `discussion:` is an informal
read-only campaign entry. Discussion surfaces a compact campaign seed and the smallest useful next
route; it creates no artifact until the operator explicitly asks to capture or plan.

A clear, reversible bug fix or enhancement in one repository defaults to Direct coordination,
including through `ts:ask`: orient once, implement the focused change, and run focused tests. Tool
Shed does not add artifacts, branches, PRs, releases, deployments, evidence, or new worktrees unless
requested, required by repository policy, or justified by concrete risk or failure. Campaign
continuity preserves Direct rather than upgrading it. Use `Coordination: direct` or `Route: direct`
when you want to make that intent explicit.

Use `ts:work1` through `ts:work5` to state the stopping point for one execution without changing
its coordination level. `work1` makes a locally committed, minimally checked change; `work2`
adds deployment to the configured work environment and focused browser checks; `work3` reviews
the accumulated coded work and can create, read, update, or delete project documentation as needed
so it matches the candidate, then fully validates and freezes the accumulated work locally; `work4`
pushes without intentional production promotion; and `work5` releases or promotes production and
verifies it. Readable aliases are
`ts:work` = `work2`, `ts:freeze` = `work3`, `ts:push` = `work4`, and `ts:ship` = `work5`.
`ts:check <spot|focused|full|release>` validates without implementation or Git/environment
mutation.

Work3 documentation alignment stays within the requested candidate scope. Preserve unrelated
owner documentation and historical records, and delete documentation only when the coded change
makes it obsolete.

Projects may optionally track `work/tool-shed.yaml` with `schema_version: 1` and either
`work_model: combined` or `work_model: split`. Combined mode lets `work2` and `work3` use the same
target as production and therefore may change the live site. Split mode keeps those levels on
development and reserves production promotion for `work5`. The declaration is optional; Tool
Shed reuses existing workspace scripts and hosting configuration rather than requiring new
infrastructure or credentials in this file.

The same file may define `work_levels` entries with ordered `before` and `after` actions plus
`run_default: false` when a workspace deliberately replaces one standard endpoint. Resolve the
selected route with `tool_shed/scripts/work_level_config.py`; aliases share their canonical level,
only the selected endpoint's envelope runs, and missing configuration preserves all standard
behavior. See [workspace work-level customization](docs/work-level-customization.md) for the schema,
ordering, failure, safety, installation, and upgrade contract.

`ts:ship <goal>` is the end-to-end delivery route: plan, implement, validate, build, deploy, and
verify the requested workspace goal. It continues through all applicable stages while preserving
normal safety, approval, credential, and protected-environment boundaries.

Stages are applicable only when the outcome includes them, repository policy mandates them, or
concrete risk or observed failure justifies them. Merely mentioning or discussing `ts:ship` does not
request delivery, and broader qualification requires a concrete reason.

Before an already-authorized consequential stage, the agent identifies at most three credible ways the
plan could fail and adds proportionate prevention, detection, verification, or rollback. Routine
reversible work skips this check.

Tool Shed does not require repeated confirmation for reversible, in-scope steps already clearly
authorized by the operator. One request may authorize multiple named operations; new confirmation
is reserved for material scope expansion, protected environments, destructive or irreversible
actions, unknown deployment targets, external publication, or other genuinely new authority.

For nontrivial work, Tool Shed uses an evidence-response loop: keep the desired outcome and current
limiting condition visible, take a material action, compare actual with expected state, and update
the next action when evidence differs. Command success is not outcome success. The loop never
broadens authority, and simple answers or known single-step reversible work execute and verify
without extra ceremony.

The workspace installer also creates `work/01-q&a/ask.txt`, a Git-ignored operator inbox. Add a question
or direction to that file and send `ts:ask`; the agent reads it and acts under the same safety and
authorization rules as a normal chat request. It also checks `work/q&a/ask.txt` as a
pre-migration fallback and warns when actionable content exists only there. If both files contain actionable
content, the agent reports a conflict instead of merging them. It preserves both files after
inspection; `work/01-q&a/ask.txt` is the canonical inbox. The selected request retains its natural
coordination level, so a bounded Direct request does not become a heavyweight campaign.

The installer also creates a first-sorted `work/00-campaigns/` owner control surface. Its
`active-queue.md` shows last completed plus accessible readiness cards for working, ready, waiting,
blocked, dependencies, focus areas, and detour/return state;
`completed-queue.md` preserves verified outcomes newest-first. Detailed requests move through
`active/`, `completed/`, `deferred/`, and `abandoned/`. The campaign lifecycle is separate from
`ask.txt`: intake stays transient while accepted work becomes durable and ordered.
Every active card heading displays its stable zero-padded campaign number in parentheses after the
mutable 1-based queue position, and the card displays its full stable `Campaign ID` underneath.
For example, `1. (004) Produce and freeze corrected firmware bundle` means queue position 1,
campaign number 004. Its lifecycle request filename is also prefixed, such as
`004-produce-and-freeze-corrected-firmware-bundle.md`. Existing IDs beginning with a numeric prefix
retain that number; the guarded `backfill-numbers --expect TOKEN` migration assigns durable numbers
and renames legacy slug-only campaign files atomically.
Lifecycle commands accept either the exact zero-padded number or the full Campaign ID.
Released snapshot upgrades run this convergence automatically when read-only validation reports a
legacy campaign layout. The release declares `work/00-campaigns` in its backed-up mutation scope;
migration preserves owner extensions and rolls the complete campaign tree back on failure.

For far-reaching projects, opt into `work/roadmaps/` between a project map and the campaign queue.
`ts: develop roadmap` and `ts: overview` are read-only; roadmap proposal/approval and derived
campaign-plan approval use separate exact state tokens. Existing work is classified from evidence,
uncertain history stays uncertain, approved revisions are preserved when superseded, and campaign
completion evidence rolls up to stable milestones and gates. Installation and upgrade create only
the compatible empty directory—they never ingest or approve planning implicitly.

The operating model is nested: Program Cycle → Milestone Wave Cycle → Queue Cycle → Campaign
Cycle → Evidence Loop. Each inner completion returns control to its owner; an empty queue does not
mean the milestone or program is done. `ts: overview`, `ts: status`, and `ts: next` share one Cycle
State Capsule that identifies the owning cycle and exact safe transition, including pending exact
plan approval, milestone derivation or gate review, roadmap review/completion, and the absence of a
higher-level driver. The capsule never approves or materializes work.

Work origin is independently computed as `direct`, `owner-originated`, `roadmap-derived`, or
`detour`. It remains separate from Direct/Guided/Coordinated/Deep coordination, the work1–work5
execution endpoint, and the current cycle state. `Campaign: standalone` keeps its existing meaning
for work-artifact coverage and is not reused as an origin label.

During installation or upgrade, Tool Shed copies and byte-verifies every file from legacy
`work/q&a/` and root `q&a/` into `work/01-q&a/`. Name collisions are preserved with
source-specific filenames; the old folders are removed only after verification.

Use `ts: status`, `ts: next`, `ts: add <idea>`, `ts: unblock <campaign>`, `ts: defer <campaign>`,
`ts: abandon <campaign>`, `ts: reconcile campaigns`, and `ts: completed`. Deterministic mutations
require the current project binding plus current project-and-root-bound state token and reject
stale or foreign-project writes. In owner-queue requests, `camp` aliases `campaign`, while `que N`
identifies the campaign at 1-based ordered queue number N and is resolved from a fresh status read.
Bare `ts: next` still runs one campaign. `ts: next 1,2` (or explicit `que 1,2`) snapshots queue
positions, `ts: next camp 025,example-id` uses stable references, and `ts: next *` snapshots all
active campaigns. Batches execute sequentially, validate and recompute readiness after each passed
completion gate, stop with completed/remaining IDs and a precise resume point, exclude later queue
additions, and do not expand deployment, release, production, destructive, credential, or other
consequential authority.
`campaign_queue.py migrate-preview` reports legacy candidates but never moves or rewrites them;
this includes legacy `Focus areas: ...` outcome prose. Projects may approve their own
evidence-backed catalog at `work/focus-areas.md`; once approved, active campaigns use known
primary/supporting IDs and cards display their names. Applying any migration requires a separate
exact approved manifest.

Use `ts: build focus areas` to inspect existing source, documentation, tests, integrations,
runtime and delivery boundaries, and durable work history. The agent first presents an exact
evidence-backed catalog and active-campaign assignment proposal without writing. Only explicit
owner approval of that proposal authorizes creation or refresh of the approved catalog and its
assignments.
`reconcile_campaign_queue.py` reports queue drift, whole-`work/` campaign coverage and exclusions,
unresolved clusters, lifecycle mismatches, and a reasoned execution order. Its default route
automatically creates or refreshes one Dangler Resolution campaign as the first queued work while
preserving any working campaign; `--dry-run` is read-only. Unresolved artifacts can declare
`Campaign: <id>`, `Campaign: standalone`, or `Campaign: excluded` with a reason. Other writes
require an exact approved manifest and a stale-write token covering the scanned work surface; it
never silently resolves semantic decisions, and terminal operations preserve lifecycle history.

## Planned Completion Watchers

The accepted [completion watcher protocol](docs/completion-watcher-protocol.md) defines the v1
descriptor, four-state checker result, durable outbox event, locking and lease recovery,
permissions, cancellation, and downgrade behavior for GitHub issue #42. This workspace includes a
local alpha watcher implementation (`scripts/completion_watcher.py`) with durable local state,
status/cancel commands, and on-demand single-runner execution; hosted service integration remains
an unshipped roadmap milestone.

Check the installed snapshot without using the network, or compare it with the canonical manifest:

```bash
python3 tool_shed/scripts/check_shed_version.py --shed tool_shed --local-only
python3 tool_shed/scripts/check_shed_version.py --shed tool_shed
```

Equivalent Tool Shed requests are `ts: version`, `ts: check for updates`, and `ts: update status`.
Checks are read-only and do not authorize snapshot replacement.
For a strict standalone integrity and boundary check, use:

```bash
python3 tool_shed/scripts/check_shed_version.py --shed tool_shed --local-only --strict --verification-only --snapshot
```

Released manifests declare `minimum_updater_protocol`. A release whose lifecycle exceeds an old
updater's protocol refuses that updater before workspace mutation and directs the operator to run a
current released updater from outside the workspace. Protocol 3 adds transactional work-tree
convergence and verified rollback coverage for the workspace structure changed by migration.

Tool Shed performs a zero-I/O reasoning preflight before substantial routed work. When current
context establishes a usable picker pair, it recommends it as a bold level-three header using
`### **Reasoning: <model> / <effort>**`; it does not use abstract labels or claim to see the active
picker.
Maintain the optional account-aware model/effort catalog outside ordinary requests:

```bash
python3 tool_shed/scripts/reasoning_catalog.py refresh
python3 tool_shed/scripts/reasoning_catalog.py status
```

Refresh queries Codex app-server `model/list` and writes the user-local cache atomically. Run it
after login/account changes, Codex updates, visible model-picker changes, or cache expiry. Use
`ts: recommend reasoning <task>` when you want Codex to refresh this catalog and provide a
concrete picker recommendation. Missing or stale cache data never blocks ordinary work.

Create the project work tree:

```bash
python3 tool_shed/scripts/install_into_workspace.py .
```

Create a new artifact:

```bash
python3 tool_shed/scripts/new_artifact.py checklist "Root docs cleanup" --workspace .
python3 tool_shed/scripts/new_artifact.py project-map "Plugin migration" --workspace .
python3 tool_shed/scripts/new_artifact.py wp "Plugin migration" --workspace .
python3 tool_shed/scripts/new_artifact.py adr "Hosted installer uses plugin bootstrapper" --workspace .
python3 tool_shed/scripts/new_artifact.py deep-research "Cross-layer compatibility contract" --workspace .
```

Complete an active workpackage:

```bash
python3 tool_shed/scripts/complete_workpackage.py work/wp/active/wp-plugin-migration.md --workspace .
```

Refresh the work index:

```bash
python3 tool_shed/scripts/update_work_index.py --workspace .
```

Read `work/index.md` after README/docs to find active artifacts quickly. Use `work/index.json` when automation needs the same navigation data. Both files are generated from artifact headers; current truth still belongs in docs or README files.

Check for stale work artifact links after moving or completing artifacts:

```bash
python3 tool_shed/scripts/check_stale_paths.py --workspace .
```

Review whether work artifacts and planning are still aligned:

```bash
python3 tool_shed/scripts/review_work_state.py --workspace .
python3 tool_shed/scripts/review_work_state.py --workspace . --json
```

Run this during orientation, after artifact lifecycle changes, in validation, and weekly as a
backstop. Add `--strict` when findings should fail CI.

Measure privacy-safe workspace scale and representative read-only operation latency:

```bash
python3 tool_shed/scripts/profile_workspace_performance.py --workspace .
python3 tool_shed/scripts/profile_workspace_performance.py --workspace . --json
```

The saved JSON report contains aggregates and timings, not paths, filenames, repository identity,
command output, or per-file hashes. Profiling cannot prove undocumented Codex hashing or indexing.
See `docs/workspace-performance-profiling.md` for the comparison protocol and the separate approval
boundaries for profiling, report collection, snapshot updates, and cleanup.

Run the full repository validation:

```bash
python3 scripts/validate_tool_shed.py
```

GitHub Actions runs the same validation on push and pull requests.

The public human/AI process guide and generated command reference are maintained under `site/` and
published at [ts.rookaro.com](https://ts.rookaro.com). See the
[documentation site maintainer guide](docs/documentation-site.md) for generation, preview,
deployment, routing, verification, and command-propagation procedures.
The same command is safe in a disconnected snapshot: canonical `work/` indexing and reconciliation
steps are skipped, the snapshot source fingerprint must remain unchanged, and embedded `.git/` or
`work/` content is refused.

Before releasing a changed snapshot, intentionally bump the semantic version and refresh its
content hashes:

```bash
python3 scripts/update_shed_manifest.py --write --version MAJOR.MINOR.PATCH --notes "Release summary"
python3 scripts/update_shed_manifest.py --check
```

For a published release, also pass `--release-commit`, `--release-tag vMAJOR.MINOR.PATCH`, and
`--released-at`. Use `--allow-same-version` only to rebuild an unpublished manifest. Equal version
numbers with different canonical content are reported as `release-mismatch`.

Follow [docs/releasing.md](docs/releasing.md) for the two-commit provenance workflow, annotated tag,
automated GitHub Release publication, and post-push verification. A pushed tag without its matching
non-draft GitHub Release object is an incomplete publication.

Before choosing an artifact, read:

- [selection.md](./selection.md)
- [conventions.md](./conventions.md)
- [existing-projects.md](./existing-projects.md) when loading `tool_shed` into an existing project

## AI Agent Start Prompts

Use short prompts and let the current workspace-capable agent operate the scripts:

The Tool Shed request prefix is authoritative for one request only:

- `ts:` uses the workspace-local Tool Shed rules and tooling for the remainder of the request.
- `ts:ship <goal>` plans, implements, validates, builds, deploys, and verifies the workspace goal
  end-to-end.
Never carry the prefix into a later request. Workspace owners may define unrelated routing prefixes
in their own provider instructions; those are not part of Tool Shed's portable command surface.

For a complete operator-facing inventory, use `ts: commands` or read
[docs/commands.md](docs/commands.md). Every `ts: help` response retains local offline guidance and
also offers [public Tool Shed help](https://ts.rookaro.com/); command inventories may link directly
to the [public reference](https://ts.rookaro.com/ref/) without checking site availability first.

```text
ts: orient me
```

```text
ts: create the smallest artifact for this
```

```text
ts: complete work/wp/active/wp-example.md
```

The agent should read README/docs first, then `work/index.md`, then active artifacts. It should use
`work/index.json` only when automation needs machine-readable navigation. It should then run the
read-only work-state review and surface findings before choosing the next action.

### Install or update prompt

```text
Use the single-workspace request in docs/install-or-update-snapshot.md. First detect whether
tool_shed/ is an existing disconnected snapshot. Update it when present or install it when absent,
using the highest stable tag and verified two-commit release provenance.
```

Installation or update changes only the ignored `tool_shed/` machinery plus documented installer
outputs. It must preserve owner-authored `work/` content; deterministic convergence may relocate
legacy Tool Shed paths and regenerate Tool Shed-owned indexes or queue projections.

## Existing Projects

For an existing project, install the work tree first, then learn before backfilling:

```bash
python3 tool_shed/scripts/install_into_workspace.py .
```

Recommended flow:

1. Inspect the project layout, docs, code surfaces, tests, and existing planning material.
2. Default to Level 2 backfill: create a project map, then create an inventory of existing docs/code/work surfaces.
3. Use the map and inventory before deciding whether to backfill workpackages, tickets, ADRs, runbooks, or checklists.
4. Backfill only useful current-state artifacts.
5. Keep observed current truth in `docs/` or README files; keep work coordination in `work/`.
6. Regenerate `work/index.md` and `work/index.json` after artifacts are created, moved, completed, or superseded.
7. Use `complete_workpackage.py` for active workpackage closeout, then fix stale links if the command reports warnings.

Level 2 artifact commands:

```bash
python3 tool_shed/scripts/onboard_existing_project.py "Project name" --workspace .
```

Manual equivalent:

```bash
python3 tool_shed/scripts/new_artifact.py project-map "Project name" --workspace .
python3 tool_shed/scripts/new_artifact.py existing-project-inventory "Project name surfaces" --workspace .
```

## Repository Governance

Canonical repository: [PC-Redemption/tool_shed](https://github.com/PC-Redemption/tool_shed).

The repository should be public for visibility, but direct changes should be limited to owners/admins of the `PC-Redemption` organization. Public readers may fork or propose changes through normal GitHub flows, but maintainers should avoid granting broad write access.

This governance applies to intentional development checkouts of the canonical repository. A `tool_shed/` directory installed inside another project is a disconnected snapshot and must not be used to contribute changes upstream.

## Portable Skill And Codex Installation

`tool_shed` includes a thin provider-neutral Agent Skills package at `skills/tool-shed`.

The skill may also be installed at `${CODEX_HOME:-~/.codex}/skills/tool-shed` for Codex
auto-discovery. Its metadata activates only for explicit Tool Shed routing or Tool Shed
artifact/campaign work; merely containing `tool_shed/` does not activate it. Root `AGENTS.md`
receives one compact conditional routing block instead of the portable workflow contract. This
user-level copy is a separate lifecycle target from a workspace snapshot; the installer reports
`TOOL_SHED_SKILL_MISMATCH` when the copies differ, and the updater can synchronize them safely with
`--sync-codex-skill`. Other providers use their native instruction adapter to route into the same
workspace-local skill. The skill progressively loads route-specific references instead of
duplicating templates or loading every procedure for every request.

Initial skill packaging is local plus repo-packaged. Plugin packaging is intentionally deferred until real use shows it is needed.
