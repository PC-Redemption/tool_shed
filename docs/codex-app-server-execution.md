# Codex App Server Execution

Status: feature-flagged read-only integration; default off

Tool Shed can route selected read-only lifecycle roles through the locally installed Codex App
Server while retaining the current Codex GUI conversation as the default and fallback execution
surface. Workspace-writing CAMP execution is not enabled.

The implementation targets Codex CLI 0.144.6 and App Server v2 over local stdio JSONL. The
[official App Server documentation](https://developers.openai.com/codex/app-server) describes the
handshake, thread and turn lifecycle, token events, and server-initiated approvals. It also labels
the App Server command experimental and unsupported for production workloads. This integration
therefore remains opt-in even though its read-only path is qualified.

## Qualified Baseline

Codex CLI 0.144.6 is the comparison baseline for future App Server changes:

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

The version-specific machine record is
`adapters/codex-app-server-qualifications.json`. It records authentication, routing, read-only,
cancellation, approval, restricted-read, workspace-writing, support-status, harness-baseline, and
savings evidence explicitly. A new Codex version has no inherited qualification.

## Routing Boundary

The feature policy is centralized in `adapters/codex-app-server-config.json`; model and reasoning
policy remains centralized in `adapters/codex-model-policy.json`.

```text
ts: discuss              -> current Codex GUI conversation
planning                 -> App Server / Sol / high, when explicitly enabled
verification             -> App Server / Terra / low, when explicitly enabled
all writing roles        -> existing GUI path
feature disabled         -> existing GUI path
```

The committed defaults are:

```text
codex_app_server_enabled = false
planning                 = true
verification             = true
program_derivation       = false
camp_derivation          = false
camp_execution           = false
implementation           = false
normal_debug             = false
testing                   = false
build                     = false
deployment                = false
escalation                = false
allowed_sandboxes         = read-only only
workspace_write_enabled   = false
```

`--enable-app-server` is an invocation-scoped override for qualification; it does not modify the
default-off configuration.

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

When routing selects the fallback, the command reports that the initiating workflow must continue
in the existing GUI. It does not attempt to emulate or spawn a second GUI conversation.

App Server-selected routes compare the installed CLI with the qualified version. A mismatch is
attached to route/run/benchmark output as `compatibility_warning`; it never blocks or warns on the
normal GUI fallback path:

```text
Codex App Server version changed. Qualified version: 0.144.6. Installed version: <version>.
Run the App Server compatibility smoke test before relying on App Server execution.
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

Only planning and verification are currently App Server eligible. The other routes are prepared in
the centralized model policy but disabled in the feature policy.

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
- inline file count and bytes, summary bytes, summary source files and source bytes, and whether
  more context was requested after a summary.

The App Server protocol does not expose a first-class model-request count. `model_turns` is therefore
an observed proxy: the count of distinct `thread/tokenUsage/updated.last` payloads during the turn.
Telemetry names that source as `distinct_token_usage_last_updates` rather than presenting it as an
exact provider-side billing metric. Tool calls are counted only from completed App Server item
types such as command execution, file change, MCP, dynamic-tool, and web-search items.

Prompts, responses, account email, tokens, and credentials are not written to telemetry.

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
billing attribution. The estimate and validated CLI version are stored in
`adapters/codex-app-server-config.json`; a CLI version change requires the protocol, authentication,
routing, read-only/approval, and token-baseline smoke checks to be rerun.

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

CLI 0.144.6 can acknowledge `turn/interrupt` with `no active turn to interrupt` while an immediate
`thread/read` still reports the target turn `inProgress`. Cancellation now performs a bounded
reconciliation loop over queued `turn/completed` events and authoritative `thread/read` state. It
returns exactly `cancelled`, `completed`, `failed`, or `unknown`; a completed turn observed after a
cancel request is classified `completed`, never silently accepted as a successful cancellation.
An unresolved `inProgress` state becomes `unknown` with `user_intervention` after the deadline.

Each cancellation writes prompt-free diagnostics containing thread and turn IDs, cancel request and
response timestamps, ordered observed events, terminal evidence, final classification, App Server
process state, and recovery action. The loop is time-bounded and never replays a prompt. This makes
the race diagnosable, but does not mark cancellation qualified: the live 0.144.6 inconsistency must
still be re-observed as reliably terminal before promotion.

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
back into the initiating Codex GUI approval panel. The feature configuration therefore keeps
`workspace_write_enabled = false`, permits only the read-only sandbox, and leaves all
workspace-writing roles on the existing GUI path.

The installed CLI/runtime also rejected `readOnly.access` with `Invalid request: readOnly.access is
no longer supported; use permissionProfile for restricted reads`, although the generated 0.144.6
schema and official documentation still describe that field. Tool Shed treats the observed runtime
as authoritative and does not enable the beta permission-profile path in this phase. Compatibility
smoke skips this expensive known-mismatch probe while the version remains 0.144.6 and automatically
retests it after a version change; `--retest-restricted-read` is available for an explicit focused
recheck.

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
GUI/discussion fallback, cancellation reconciliation, fail-closed approvals, restricted-read
behavior when the version changed, and the tiny-operation token baseline. It never updates the
qualification registry automatically. Review new-version evidence, then add a version-specific
record deliberately.

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
  --expected-codex-version 0.144.6
```

The report includes planning and verification totals, cached input, model-turn and tool-call rates,
context and summary bytes, duration, recovery, retries, resumes, fallback and escalation counts,
version drift, and progress against the 10-planning/20-verification observation gate. Version
compatibility participates in the gate, so a changed CLI cannot pass until compatibility smoke
checks establish and configure a new validated version. An optional
`--comparison` JSON file can attach manually reviewed GUI/App Server quality evidence; absent GUI
token metrics remain `null` rather than being estimated.

## Promotion Decision

App Server is ready for explicitly enabled, read-only planning and verification trials. It is not
ready to become Tool Shed's default execution path because:

1. OpenAI still labels App Server experimental and unsupported for production workloads.
2. CLI 0.144.6 exhibited a live `turn/interrupt` versus `thread/read` cancellation-state race.
3. The real Codex GUI approval surface is not connected to `ApprovalBridge`.
4. Workspace-writing CAMP roles remain disabled and unqualified end to end.
5. The installed runtime and published/schema restricted-read surfaces currently disagree.

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

### Gate B: workspace-writing roles

All Gate A criteria plus all of these must pass:

- a supported bridge reaches the initiating GUI approval surface;
- file-write and command approvals are qualified live;
- denial, cancellation, and approval timeout are qualified live;
- restricted-read behavior is understood and qualified;
- structured CAMP outcomes are integrated;
- workspace-writing roles receive live end-to-end qualification;
- rollback and interrupted-write recovery are validated.

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
