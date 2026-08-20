# Codex App Server Execution Adapter

Status: proof of concept

Tool Shed can use the locally installed `codex app-server` as an opt-in machine-facing execution
backend while retaining the interactive Codex UI as its operator surface. The existing interactive
execution path remains unchanged and is the fallback until this adapter is qualified.

## Verified Local Surface

The proof of concept targets Codex CLI 0.144.6 and App Server v2 over the default stdio JSONL
transport. At runtime the adapter performs the required `initialize` / `initialized` handshake,
calls `account/read`, and refuses execution unless the returned account type is exactly `chatgpt`.
It never accepts, reads, or falls back to an OpenAI API key.

`model/list` is the runtime authority for model identifiers and supported effort labels. The
central policy is `adapters/codex-model-policy.json`; Programs and CAMPs pass only lifecycle roles.
The adapter validates every configured role against the live catalog before starting work.

The installed CLI still labels `app-server` experimental. Clients can stay off explicitly
experimental v2 methods and fields by omitting `capabilities.experimentalApi`, but this proof of
concept should not be treated as a production-stable integration until OpenAI changes the command's
stability commitment.

## Boundary

```text
Tool Shed lifecycle role
        |
        v
CodexExecutionAdapter ---- centralized model policy
        |
        v
CodexAppServerClient ----- stdio JSONL / v2
        |
        v
ChatGPT-authenticated Codex
```

`CodexExecutionAdapter` provides `start_work`, `resume_work`, `execute`, `cancel`, `get_status`,
and an explicit bounded `escalate` operation. `CodexAppServerClient` isolates the handshake,
request correlation, thread/turn lifecycle, streaming notifications, approvals, and process
shutdown. The existing reasoning catalog now reuses this transport.

## Operation

Probe authentication and policy compatibility without exposing account email or tokens:

```bash
python3 scripts/codex_execution.py probe
```

Run a role-routed request:

```bash
python3 scripts/codex_execution.py run \
  --role camp_execution \
  --cwd . \
  --prompt "Execute the established CAMP instructions."
```

Run the two-model proof of concept:

```bash
python3 scripts/codex_execution.py poc --cwd .
```

The CLI defaults to `read-only`, `approvalPolicy: never`, and no network. Workspace-changing
callers must deliberately select a different sandbox and implement an approval bridge appropriate
to their user surface.

## Protocol Findings

- Launch: spawn `codex app-server --stdio`; one process can own multiple loaded threads.
- Authentication: `account/read` reports `chatgpt`, `apiKey`, or another configured provider. Only
  managed `chatgpt` is accepted here; Codex owns OAuth persistence and refresh.
- Model and effort: set `model` on `thread/start` or `thread/resume`, and set both `model` and
  `effort` on `turn/start`. Discover valid values through `model/list`.
- Threads: stable methods cover start, resume, fork, read, list, archive, and unsubscribe. There is
  no ordinary "terminate thread" call; interrupt the active turn and unsubscribe or close the
  client. Permanent `thread/delete` is destructive and outside this adapter.
- Streaming: consume `turn/*`, `item/*`, `thread/tokenUsage/updated`, warnings, errors, and model
  reroute notifications until `turn/completed` reports `completed`, `interrupted`, or `failed`.
- Agent capabilities: shell runs and file changes appear as streamed items. When approval is
  required, App Server sends a server-initiated request that the client must answer. This proof of
  concept cancels unhandled approval requests rather than granting authority silently.
- Errors: failed turns include typed `codexErrorInfo` values. Authentication, usage-limit, bad
  request, and context-limit failures must fail without retries or model escalation. Transient
  transport retries belong in a later orchestrator layer and must remain bounded.
- Usage: `thread/tokenUsage/updated` exposes input, cached input, output, reasoning output, and total
  tokens. It does not establish dollar cost for ChatGPT subscription usage.

## Escalation Policy

The adapter never loops automatically. Workhorse execution is capped at two attempts. A caller may
request frontier escalation after the cap, or immediately for the named architectural or complex
failure reasons. Escalation is recorded separately. Semantic blocker detection should eventually
use a structured CAMP result rather than guessing from prose.

## Telemetry

The default append-only JSONL file is `~/.codex/tool-shed/execution-telemetry.jsonl`. Records include
run and operation IDs, Program and CAMP identifiers when supplied, role, model class, requested and
actual model, reasoning effort, thread/turn IDs, timestamps, status, rerouting, escalation, and
token usage. Prompts, responses, account email, tokens, and credentials are deliberately excluded.

## Incremental Migration Plan

1. Keep the adapter opt-in and qualify read-only planning and verification turns against current
   Codex releases. Preserve the interactive path unchanged.
2. Add a provider-owned execution-role field at the Tool Shed orchestration boundary. Programs and
   CAMPs continue to describe lifecycle intent and never contain RPC method names or model IDs.
3. Route Program/CAMP derivation to frontier roles and established CAMP execution to workhorse
   roles behind a feature flag. Persist thread IDs only in runtime state, not canonical artifacts.
4. Bridge server-initiated approvals to the interactive Codex UI or another explicit operator
   surface before enabling workspace-write execution. Never auto-approve commands or patches.
5. Add structured CAMP outcomes (`success`, `expected_failure`, `unexpected_blocker`) so bounded
   retry and escalation decisions are evidence-based.
6. Compare Sol/Terra role and token telemetry over representative campaigns. Promote App Server to
   the default only after cancellation, restart/resume, approval, and interrupted-stream recovery
   tests pass; retain a feature-flag rollback to the interactive execution path.
