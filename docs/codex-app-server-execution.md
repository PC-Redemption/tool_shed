# Codex App Server Execution

Status: maintenance/watch; feature-flagged read-only and bounded CAMP integration; default off

Tool Shed can route selected read-only lifecycle roles through the locally installed Codex App
Server while retaining the current Codex GUI conversation as the default and fallback execution
surface. One explicitly bounded workspace-writing CAMP step is also qualified through the dedicated
`camp-run` path; broader writing is not enabled.

The current qualified implementation targets Codex CLI 0.149.0 and App Server v2 over local stdio
JSONL. The
[official App Server documentation](https://developers.openai.com/codex/app-server) describes the
handshake, thread and turn lifecycle, token events, and server-initiated approvals. It also labels
the App Server command experimental and unsupported for production workloads. This integration
therefore remains opt-in even though its read-only path is qualified.

For the short operational handoff, read the
[App Server maintainer note](codex-app-server-maintainer-note.md). Further engineering is
event-triggered rather than an active Tool Shed development priority.

## Qualified Baseline

Codex CLI 0.144.6 remains the larger real-campaign comparison baseline for future App Server
changes. Codex CLI 0.149.0 was separately requalified for protocol, routing, and bounded writing on
2026-08-21; it does not inherit the older version's qualification record.

| Measurement | Qualified value |
| --- | ---: |
| Real planning operations | 10 |
| Real verification operations | 20 |
| Core successes | 30 / 30 |
| Measured model operations | 33 |
| Input tokens | 939,307 |
| Estimated avoidable input | 323,297 |
| Input reduction versus old strategy | 82.54% |
| Elapsed-time reduction | 70.31% |

The current requalification evidence is in
[the 2026-08-21 report](codex-app-server-requalification-2026-08-21.md). The version-specific
machine record is
`adapters/codex-app-server-qualifications.json`. It records authentication, routing, read-only,
cancellation, approval, restricted-read, bounded workspace-writing, support-status,
harness-baseline, and savings evidence explicitly. A new Codex version has no inherited
qualification. The write evidence is in
[the 2026-08-20 write qualification](codex-app-server-write-qualification-2026-08-20.md).

## Routing Boundary

The feature policy is centralized in `adapters/codex-app-server-config.json`; model and reasoning
policy remains centralized in `adapters/codex-model-policy.json`.

```text
ts: discuss                                  -> current Codex GUI conversation
ts: plan <request>                           -> current GUI path
ts: plan <request> --app-server              -> App Server / Sol / high
ts: verify <request>                         -> current GUI path
ts: verify <request> --app-server            -> App Server / Terra / low
ts: camp run <camp>                          -> current GUI path
ts: camp run <camp> --app-server             -> App Server / Terra / medium through camp-run
ts: next                                     -> normal selection and current GUI path
ts: next --app-server                        -> normal selection, then the selected qualified role
unqualified roles or incompatible Codex      -> blocked; GUI remains available without the flag
```

The committed defaults are:

```text
codex_app_server_enabled = false
planning                 = true
verification             = true
program_derivation       = false
camp_derivation          = false
camp_execution           = true
implementation           = false
normal_debug             = false
testing                   = false
build                     = false
deployment                = false
escalation                = false
allowed_sandboxes         = read-only and workspace-write
workspace_write_enabled   = false
```

`--enable-app-server` is an invocation-scoped override for qualification; it does not modify the
default-off configuration. It is an internal orchestration flag. The user-facing Tool Shed option
is `--app-server` on the qualified `ts:` commands above.

`ts: next --app-server` is forwarding, not a fourth execution role. Tool Shed first performs the
same navigation and readiness selection as ordinary `ts: next`. When the selected action is CAMP
execution, it invokes the existing `camp-run` selector and bounded Terra/medium runner. A selected
discussion, decision, blocker, external gate, GUI-native action, or unsupported role is reported
on its natural route without starting App Server. Compatibility failure remains fail-closed, the
unflagged GUI route stays available, and the selector is not retained for later commands.

Resolve and display the user-facing selection before execution:

```bash
python3 scripts/app_server_control.py select plan --app-server
python3 scripts/app_server_control.py select verify --app-server
python3 scripts/app_server_control.py select camp-run --app-server
python3 scripts/app_server_control.py status
```

The selector reuses the centralized config, model policy, qualification registry, and installed
Codex version check. Exact records remain authoritative for known versions and all CAMP writing.
For planning and verification, an unseen executable with a numeric release core of `0.146.0` or
newer runs the dirty read harness automatically, with no upper cutoff. The original explicit
request continues in the same invocation only after a qualified result. The existing GUI remains
available by rerunning without `--app-server`; the control never switches to API execution.

Dirty read summaries are stored in a protected user-local cache at
`$CODEX_HOME/tool-shed/dirty-read-qualifications.json`, falling back to the matching `~/.codex`
location. The path is rejected if it is inside canonical or installed Tool Shed content. Records
contain only the executable path and hash, version, protocol fingerprint, qualification-policy
hash, model-policy hash, platform, sanitized outcome and blocker names, and timestamps—never
prompts, responses, credentials, secrets, or telemetry. Writes use an inter-process lock, atomic
replacement, and mode `0600` where supported. Malformed, partial, foreign-platform, stale, or
mismatched successes are ignored safely. Reviewed unsafe denials do not expire on the success TTL;
they remain authoritative until a relevant fingerprint changes or `select ... --requalify` is
used. Transient authentication, network, service, and model-catalog failures remain GUI fallbacks
and are not cached, so later explicit requests retry. Status exposes cache source and invalidation
reason without exposing probe content.

## Codex Executable Readiness

One centralized resolver selects a Codex executable for every App Server consumer. A supported
explicit override is authoritative. Without one, it inventories `PATH`, bounded trusted platform
locations, and OpenAI VS Code extension bundles, validates `--version` and App Server support for
each, and selects the highest semantically eligible version at or above `0.146.0`. Source priority
breaks only equal-version ties, so an older `PATH` executable cannot mask a newer eligible bundle.

`status`, selection, compatibility smoke, App Server startup, version detection, qualification,
reasoning-catalog refresh, and installation and upgrade readiness reporting all use that same
resolver and report its inventory, selected path, source, version, App Server availability,
qualification state, and executable-specific usable roles. Status and selection distinguish
`exact-qualified`, `dirty-qualifying`, `dirty-qualified`, `transient-fallback`, `unsafe-blocked`,
`below-minimum`, and `write-not-qualified`. A missing or unsupported CLI blocks only explicit App Server execution:
unflagged Tool Shed requests remain in the GUI, and there is no API fallback.

Trusted discovery is deliberately bounded. Tool Shed does not search arbitrary disk locations,
install or copy Codex, modify permanent `PATH`, persist discovered user paths in tracked files, or
automatically qualify a discovered version. Linux extension
discovery covers the normal `.vscode`, `.vscode-insiders`, `.vscode-server`, and
`.vscode-server-insiders` extension roots and the `linux-x86_64`, `linux-aarch64`, and
`linux-arm64` payload directories.

### Windows GUI release gate (external evidence still required)

Automated regression coverage exercises resolver precedence, invalid and missing candidates,
App Server absence, qualification states, Windows extension-version ordering, Linux behavior, and
resolver use across status and execution paths. It does **not** replace the required Windows field
test. From a fresh, normally launched Codex GUI session with `Get-Command codex` still failing and
without any temporary or permanent `PATH` preparation, `ts: appserver status` must identify the
trusted OpenAI VS Code bundle and report its path, source, version, and compatibility state. A
GUI-triggered `--app-server` operation, smoke, startup, version detection, and qualification must
then record the same executable identity. Do not mark this release gate passed until that external
evidence exists.

`ts: discuss ... --app-server` is rejected because discussion is intentionally GUI-native.
Session-scoped `ts: appserver on|off` is not implemented because the Codex skill surface does not
provide reliable skill-owned session storage. The corresponding helper command reports that
limitation without writing configuration. With no session mode, the unflagged command is the GUI
choice and no separate `--gui` option is introduced.

Show the selected backend without starting App Server:

```bash
python3 scripts/codex_orchestration.py route --role planning
python3 scripts/codex_orchestration.py \
  --enable-app-server route --role planning
python3 scripts/codex_orchestration.py \
  --enable-app-server route --role discussion --request "ts: discuss context cost"
```

Run a selected read-only role:

```bash
python3 scripts/codex_orchestration.py \
  --enable-app-server run \
  --role verification \
  --cwd . \
  --file adapters/codex-model-policy.json \
  --prompt "Verify the supplied model policy."
```

Run one explicitly scoped CAMP write from a clean Git state:

```bash
python3 scripts/codex_orchestration.py \
  --enable-app-server camp-run \
  --cwd . \
  --campaign 036-app-server-write-qualification-and-camp-execution \
  --camp focused-change \
  --expected-path tests/test_codex_execution.py \
  --file tests/test_codex_execution.py \
  --verify-command-json '["env","PYTHONDONTWRITEBYTECODE=1","python3","-m","unittest","tests.test_codex_execution"]' \
  --prompt "Make only the requested bounded change."
```

`camp-run` requires exact declared paths and a Git mutation journal. Generic `run` refuses the
workspace-write sandbox. `--verify-command-json` accepts a shell-free JSON argv array and may be
repeated. The orchestrator runs these checks through App Server after the model edit, retains only
compact success/diagnostic evidence, and exits nonzero if verification fails.

When routing selects the fallback, the command reports that the initiating workflow must continue
in the existing GUI. It does not attempt to emulate or spawn a second GUI conversation.

Internal App Server routes attach a version mismatch as `compatibility_warning`. The user-facing
selector is stricter: it blocks explicit App Server execution before the orchestrator starts. The
normal GUI path never requires App Server compatibility:

```text
Codex App Server version changed. Qualified version: 0.149.0. Installed version: <version>.
Run `python3 scripts/codex_app_server_compatibility.py smoke --cwd .` before relying on App Server execution.
```

## Authentication and Model Policy

On every new App Server client connection the adapter completes `initialize` / `initialized`, calls
`account/read`, and refuses execution unless `account.type` is exactly `chatgpt`. API-key,
unauthenticated, Bedrock, and other provider modes fail closed. Tool Shed does not read, persist, or
accept an OpenAI API key and has no API-key fallback.

The live `model/list` response is the authority for model identifiers and supported reasoning
efforts. The current policy is:

| Lifecycle roles | Model | Reasoning |
| --- | --- | --- |
| planning, program/campaign derivation and design, escalation | `gpt-5.6-sol` | `high` |
| architecture | `gpt-5.6-sol` | `xhigh` |
| CAMP execution, implementation, normal debugging, deployment | `gpt-5.6-terra` | `medium` |
| verification, testing, build | `gpt-5.6-terra` | `low` |

Planning, verification, and the dedicated `camp_execution` path are currently App Server eligible.
All other routes are prepared in the centralized model policy but disabled in the feature policy.

## Context and Token Accounting

Telemetry distinguishes:

- cumulative input, cached input, output, reasoning-output, and total tokens for the current turn;
- the last model request inside the turn;
- raw App Server thread-cumulative usage;
- model, reasoning, role, thread and turn IDs;
- new versus resumed thread;
- source workspace, execution directory, context mode and delivery strategy;
- loaded `instructionSources`, explicitly selected file names and byte counts, and prompt size;
- rerouting, retry attempt, escalation and reason, recovery action, and context warnings.
- campaign, Program, CAMP, qualification run, timestamps, duration, and fallback use;
- observed model turns and completed tool calls, with tool-call types;
- ordered model-turn anatomy with per-request token categories, elapsed time, preceding tool type,
  and serialized tool-result bytes;
- versioned model-aware `weighted_codex_usage`, including separate uncached, cached, and output
  components without double-counting reasoning output;
- inline file count and bytes, summary bytes, summary source files and source bytes, and whether
  more context was requested after a summary.

The App Server protocol does not expose a first-class model-request count. `model_turns` is therefore
an observed proxy: the count of distinct `thread/tokenUsage/updated.last` payloads during the turn.
Telemetry names that source as `distinct_token_usage_last_updates` rather than presenting it as an
exact provider-side billing metric. Tool calls are counted only from completed App Server item
types such as command execution, file change, MCP, dynamic-tool, and web-search items.

Prompts, responses, account email, tokens, and credentials are not written to telemetry.

### Bounded CAMP token optimization

Campaign 040 reduced the same representative controller-regression CAMP from 241,524 to 61,516
input tokens, from seven to two observed model requests, and from six to one model tool. Full elapsed
time fell from 36.704 to 12.458 seconds, while the versioned weighted proxy fell from 67,362.0 to
36,468.4 units. The declared file remained the only changed path and all 22 focused tests passed.

The reduction comes from a focused trigger-neutral worker capsule, orchestrator-owned Git state,
and deterministic App Server verification outside the model turn. The exact safety boundary is
unchanged. See
[the 2026-08-20 CAMP token optimization report](codex-app-server-camp-token-optimization-2026-08-20.md)
for per-turn anatomy, metric weights, additional samples, and limitations.

### Why a tiny turn was about 19k input tokens

Live measurements isolated the fixed harness cost:

| Scope | Instruction sources | Input tokens |
| --- | ---: | ---: |
| Empty temporary directory, 51-character prompt | user `AGENTS.md` only | 18,782 |
| Tool Shed worktree, 55-character prompt | user and repository `AGENTS.md` | 19,007 |
| Resumed Tool Shed thread, 54-character prompt | same two sources | 19,033 |

Only 225 tokens separated the empty directory from the repository. Tool Shed supplied only the
short user prompt; it did not copy the outer GUI conversation or workspace files into App Server.
The approximately 18.8k baseline is therefore primarily the Codex harness: built-in instructions,
available tool definitions, provider/session metadata, and the user-level instruction source. The
repository `AGENTS.md` adds a comparatively small amount.

Qualification uses a documented estimate of 18,800 input tokens per measured operation and reports
`avoidable_input_tokens = max(actual_input_tokens - 18,800, 0)`. This is comparative analysis, not
billing attribution. The estimate, exact reviewed versions, and `0.146.0` dirty-read floor are
stored in `adapters/codex-app-server-config.json`. An unseen eligible read-only request
automatically reruns the protocol, authentication, routing, read-only/approval, cancellation,
unchanged-workspace, and token-baseline checks. Workspace-write remains a separate exact-version
qualification.

Thread reuse did not reduce input-token count: the second tiny turn rose from 19,007 to 19,033,
while cached input remained 9,984. Reuse can improve cache composition, but it accumulates history.
Planning and verification therefore default to new ephemeral threads. Resume remains available for
recovery of a known interrupted thread, not as the routine short-task optimization.

### Avoiding repeated fixed harness cost

The first benchmark strategy placed only relevant files in a focused temporary snapshot and asked
the agent to read them. It successfully constrained scope, but every file-reading/tool round paid
the fixed harness cost again. The four tasks used 339,602 input tokens.

The current strategy keeps the focused temporary directory and supplies only the explicitly named
UTF-8 files inline, capped at 100,000 bytes. This reduced all four tasks to one model request each.
Larger inputs must be reduced to a relevant summary rather than silently copying an unbounded
workspace.

For a focused summary, pass the summary as inline context and list every source file used to create
it. The summary must contain a `## Source files` section with one exact workspace-relative `- path`
entry per source. The adapter rejects a summary that does not declare each source path, records
source and summary bytes separately, and does not cache summaries automatically:

```bash
python3 scripts/codex_orchestration.py \
  --enable-app-server run \
  --role planning \
  --qualification-id 2026-08-real-campaigns \
  --campaign 024-compact-tool-shed-site \
  --cwd . \
  --summary-file work/evidence/app-server/context-summary.md \
  --summary-source-file work/00-campaigns/completed/024-compact-tool-shed-site-and-publish-guided-workflows.md \
  --prompt "Plan the next safe read-only review from the supplied campaign summary."
```

Summaries remain ephemeral per operation until observed reuse demonstrates that campaign or
Program/CAMP caching would save enough context to justify invalidation complexity.

| Benchmark | Reference-file input | Inline input | Reduction |
| --- | ---: | ---: | ---: |
| Small planning | 38,914 | 25,819 | 33.65% |
| Medium planning | 101,486 | 31,961 | 68.51% |
| Small verification | 37,211 | 18,813 | 49.44% |
| Medium verification | 161,991 | 33,893 | 79.08% |
| Total | 339,602 | 110,486 | 67.47% |

The repeatable tasks are in `adapters/codex-app-server-benchmarks.json`; the measured baseline is
`docs/codex-app-server-benchmark-baseline.json`.

Run them with:

```bash
python3 scripts/codex_orchestration.py \
  --enable-app-server benchmark --cwd .
```

The benchmark compares current input against the committed baseline. A task exceeding 1.5 times
its baseline is reported as a regression but is not hard-stopped. Output records baseline and
current absolute input, absolute token change, and relative percentage change per task and in
aggregate. The 82.54% real-campaign reduction remains the version-specific qualification reference;
the repeatable four-task suite protects against drift without pretending every legitimate task has
the same size. The equivalent GUI path does not expose per-turn token telemetry in this workspace,
so a reliable numerical GUI comparison is not available.

## Thread and Failure Recovery

The adapter classifies terminal and transport outcomes into an explicit recovery contract:

| Evidence | Recovery action |
| --- | --- |
| Completed turn | `none` |
| Interrupted turn | `safe_to_resume` |
| Timeout, transport close, or server termination | `safe_to_resume` after status reconciliation; never blind replay |
| Recoverable failed turn | `safe_to_retry` |
| Stale/unknown thread or context-window exhaustion | `requires_new_thread` |
| Bad request, authentication, or usage-limit failure | `requires_user_intervention` |

Qualification covers new threads, resumed threads, completed turns, cancellation/interruption,
unexpected process termination, client/server restart, stale IDs, failed turns, bounded retries,
and timeouts. Focused planning and verification threads are ephemeral by default. A controlled
qualification can use `--retain-thread`, then supply the returned ID with both `--thread-id` and
`--retain-thread`; because the complete selected context is inline, resume creates a new focused
temporary directory and does not rely on the previous directory surviving. Routine operations
still start fresh.

CLI 0.144.6 demonstrated that `turn/interrupt` can return `no active turn to interrupt` while an
immediate `thread/read` still reports the target turn `inProgress`. CLI 0.149.0 retained the
contradictory acknowledgement but its immediate reconciled state was terminal `interrupted`.
Cancellation performs a bounded
reconciliation loop over queued `turn/completed` events and authoritative `thread/read` state. It
returns exactly `cancelled`, `completed`, `failed`, or `unknown`; a completed turn observed after a
cancel request is classified `completed`, never silently accepted as a successful cancellation.
An unresolved `inProgress` state becomes `unknown` with `user_intervention` after the deadline.

Each cancellation writes prompt-free diagnostics containing thread and turn IDs, cancel request and
response timestamps, ordered observed events, terminal evidence, final classification, App Server
process state, and recovery action. The loop is time-bounded and never replays a prompt. This makes
the race diagnosable, but does not mark cancellation globally safe: the acknowledgement
inconsistency remains a blocker even though the 0.149.0 reconciliation safely classified the
observed turn.

The post-qualification smoke reproduced the exact sequence: `turn/interrupt` returned “no active
turn,” `thread/read` kept returning `inProgress` for approximately 4.56 seconds, and the turn then
became `completed`. Tool Shed correctly returned `completed`, not `cancelled`. Because the
contradictory response and state both came from App Server while Tool Shed only observed and
bounded them, the remaining defect is classified as an App Server/protocol inconsistency; Tool
Shed's reconciler is a safety mitigation, not proof that cancellation works.

There are no unbounded retries. A Terra role receives at most two attempts: the initial attempt and
one diagnostic retry. If both end in an explicitly recoverable failure, one Sol escalation is
allowed and records `recoverable_failure_exhausted`. Authentication, usage-limit, bad-request,
context-limit, timeout, and ambiguous transport failures are never automatically replayed.

## Approval Bridge

`ApprovalBridge` implements a bounded callback contract for current v2 command-execution and
file-change approval requests. It validates thread, turn, and item IDs; restricts responses to the
documented decisions; respects `availableDecisions`; times out; and records prompt-free approval
events. Malformed, unexpected, denied, cancelled, timed-out, unavailable, or resolver-failed
requests fail closed.

Tests cover shell-command approval, file-change approval, accept, decline, cancel, timeout, and
malformed requests. However, there is no product-surface bridge from the standalone Python adapter
back into the initiating Codex GUI approval panel. Interactive permission expansion therefore stays
disabled and fails closed. The qualified CAMP path instead uses approval policy `never`, a
hardened exact-root workspace-write sandbox, an exact path allowlist, and a Git mutation journal.
All other workspace-writing roles remain on the existing GUI path.

Both reviewed CLI runtimes rejected `readOnly.access` and directed clients to permission profiles.
Dirty qualification negotiates this protocol rather than keying behavior to a version: it queries
`permissionProfile/list`, requires the allowed built-in `:read-only` profile, and sends
`permissions` without `sandbox` or `sandboxPolicy`. If the method is unavailable, the same turns
validate the legacy read-only sandbox. Exposed-but-unavailable read-only profiles fail closed.

## Operational Visibility

Show the concise operator status:

```bash
python3 scripts/codex_app_server_compatibility.py status
python3 scripts/codex_app_server_compatibility.py status --json
```

Run the live compatibility smoke after every Codex CLI update:

```bash
python3 scripts/codex_app_server_compatibility.py smoke --cwd .
```

The smoke checks CLI version detection, App Server startup, ChatGPT-only authentication, absent API
fallback, Sol/Terra availability and reasoning, new read-only planning and verification threads,
GUI/discussion fallback, deliberately active-turn cancellation, fail-closed approvals,
permission-profile or legacy enforcement, unchanged disposable workspace contents, absent protocol
mutation events, and the tiny-operation token baseline. Dirty mode reports safe blockers separately
from fatal, transient, and unknown states and never updates the qualification registry. Re-run
`scripts/codex_app_server_write_qualification.py` separately before retaining workspace-write
qualification on a new CLI version.

Show the last 20 prompt-free operations:

```bash
python3 scripts/codex_execution.py activity --limit 20
```

The report includes time, role, Program, CAMP, model, reasoning, token categories, success, failure,
escalation and reason, thread reuse, and context warnings, plus aggregate counts by model and role.
No dollar cost is inferred from ChatGPT subscription usage.

Generate the aggregate observation report for one qualification run:

```bash
python3 scripts/codex_execution.py \
  --telemetry ~/.codex/tool-shed/execution-telemetry.jsonl \
  qualification-report \
  --qualification-id 2026-08-real-campaigns \
  --baseline-input-tokens 18800 \
  --expected-codex-version 0.149.0
```

The report includes planning and verification totals, cached input, model-turn and tool-call rates,
context and summary bytes, duration, recovery, retries, resumes, fallback and escalation counts,
version drift, and progress against the 10-planning/20-verification observation gate. Version
compatibility participates in the gate, so a changed CLI cannot pass until compatibility smoke
checks establish and configure a new validated version. An optional
`--comparison` JSON file can attach manually reviewed GUI/App Server quality evidence; absent GUI
token metrics remain `null` rather than being estimated.

## Promotion Decision

App Server is ready for explicitly enabled, read-only planning and verification trials and one
bounded `camp_execution` step. It is not ready to become Tool Shed's default execution path because:

1. OpenAI still labels App Server experimental and unsupported for production workloads.
2. CLI 0.149.0 still returned a contradictory `turn/interrupt` acknowledgement, although bounded
   reconciliation safely observed terminal `interrupted`.
3. The real Codex GUI approval surface is not connected to `ApprovalBridge`.
4. The optimized representative write CAMP succeeded safely at 61,516 input tokens and demonstrated
   material savings, but the fixed harness floor remains large and does not justify global enablement.
5. Broader workspace writing, build, deployment, and permission expansion remain unqualified.
6. The installed runtime and published/schema restricted-read surfaces currently disagree.

Promotion should occur only after those conditions are resolved. The existing GUI path remains the
default and rollback path throughout. The completed real-campaign observation and measurements are
recorded in [the 2026-08-20 qualification report](codex-app-server-qualification-2026-08-20.md).

### Gate A: default planning and verification

All of these must pass on the installed Codex version:

- App Server support risk is acceptable explicitly;
- cancellation reconciliation is reliable;
- the compatibility smoke and version record agree;
- authentication remains ChatGPT-only with no API fallback;
- Sol/high and Terra/low routing remains correct;
- focused-context savings remain strong against absolute and relative baselines;
- the existing GUI fallback remains reliable.

### Gate B: broader workspace-writing roles

All Gate A criteria plus all of these must pass:

- a supported bridge reaches the initiating GUI approval surface;
- file-write and command approvals are qualified live;
- denial, cancellation, and approval timeout are qualified live;
- restricted-read behavior is understood and qualified;
- structured CAMP outcomes are integrated for the target role;
- each additional workspace-writing role receives live end-to-end qualification;
- rollback and interrupted-write recovery are validated.

The narrow `camp_execution` exception passed its dedicated safety gate without passing this broader
promotion gate. Its exact policy, partial-write evidence, real CAMP observation, and token finding
are recorded in the write qualification report linked above.

### CAMP completion and verification handoff

App Server `turn/completed` means that the model turn reached a protocol terminal event. It does
not prove that a CAMP is verified. A bounded CAMP worker that has finished its authorized edits
returns `step_ready_for_verification` or `camp_ready_for_verification`; it must not run commands
reserved by the enclosing orchestrator. The older `step_complete` and `camp_complete` values remain
accepted for compatibility, but have the same implementation-ready, verification-pending meaning.

Only one of those four handoff outcomes authorizes the orchestrator to run the declared
deterministic verification commands. Each declared command runs exactly once. The Git mutation
journal then reports the combined result truthfully:

- `safe_unverified` means the path boundary is safe but CAMP verification did not establish
  completion;
- `verification_failed` means at least one reserved deterministic command failed;
- `verified` means the mutation boundary is safe and every required deterministic command passed.

Malformed, partial, `unknown`, interrupted, unsafe, or unexpected-path results remain fail-closed.
After any mutation they are not retried or replayed automatically. Input-token warnings and worker
tool results above `context.max_tool_result_bytes` are retained only as compact metadata and block
lifecycle advance with an explicit context-budget finding; command output is not copied into the
journal.

Passing unit tests alone does not promote a role. API fallback and Luna routing remain out of scope.

## Merge Readiness

The infrastructure is sufficiently isolated to merge into the normal Tool Shed codebase while it
remains disabled by default: it is confined to App Server adapters/scripts, explicit configuration,
tests, and documentation; normal GUI routing is unchanged; and unsupported roles fail back to the
existing path. The recommended long-term state is infrastructure present on `main`, global default
disabled, explicit read-only opt-in available, and compatibility status visible.

Do not merge by mutating or cleaning the active dirty checkout. Merge only through a reviewed,
clean Git operation after its unrelated campaign work is reconciled. This hardening phase prepares
that recommendation; it does not authorize or perform the merge.
