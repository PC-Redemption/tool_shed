# Evidence: Deterministic App Server worker handoff

Status: verified
Type: evidence
Updated: 2026-08-26
Campaign: establish-deterministic-app-server-worker-handoff

## Result

Tool Shed no longer relies on a CAMP worker to spend another model request describing a completed
mutation. For write-capable CAMP execution, the client now enforces this two-phase boundary:

1. read-only automatic preparation supplies complete bounded source context, exact mutation paths,
   and reserved deterministic verification;
2. the write worker may use `fileChange` but no `commandExecution`; the first completed file change
   is the verification handoff, the client interrupts the worker, journals actual paths, and runs
   the reserved verifier itself.

If the worker attempts `commandExecution`, Tool Shed interrupts it at `item/started`. With no
mutation, the recovery action is `prepare_fresh_camp_with_complete_context`; if any path changed
despite the interrupt race, the Git journal requires reconciliation. No GUI fallback or worker
replay occurs.

## Protocol research

The official Codex App Server contract documents per-turn model, effort, working directory,
approval policy, sandbox policy, output schema, and `turn/interrupt`. It documents experimental
dynamic tools, but the `thread/start` and `turn/start` contracts do not expose the Responses API
`allowed_tools` or forced built-in-tool choice needed to remove `commandExecution` while retaining
`fileChange`.

- Official App Server reference: https://developers.openai.com/codex/app-server
- Official Responses API reference showing `tool_choice` and allowed tool subsets outside the App
  Server turn contract: https://developers.openai.com/api/reference/cli/resources/responses/methods/create

The installed Tool Shed client and current App Server schema use the documented App Server fields
only. Tool Shed therefore enforces the narrower worker protocol from streamed lifecycle events
rather than sending an unsupported turn field.

## Failure evidence addressed

- Campaign 073 used an automatically prepared 8,192-byte estimate but emitted a 19,301-byte source
  inspection result before mutation.
- Campaign 075 kept tool results bounded, changed only expected paths, but two exploratory command
  turns consumed the request budget and the fourth request was interrupted before the model could
  return its verification handoff.
- Prompt-only mutation-first language did not make either behavior deterministic.

The new control removes both failure modes from the worker protocol: repository inspection belongs
to read-only preparation, and a completed file change no longer requires a final model turn.

## Focused verification

Command:

```text
python3 -m unittest tests.test_codex_execution tests.test_app_server_dispatch tests.test_cycles.CycleStateTests.test_abandoned_history_may_retain_an_abandoned_dependency
```

Result: 66 tests passed in 12.122 seconds.

The focused checks include:

- interrupting a worker `commandExecution` event before mutation and skipping verification;
- accepting the first completed `fileChange` as the handoff and running the reserved verifier;
- preserving budget interruption, mutation-journal, source injection, static collateral, and
  historical abandoned-dependency behavior.

## Remaining proof boundary

This is implementation and focused deterministic evidence, not the real Linux first-pass gate.
Fresh code/test and asset-aware campaigns must still demonstrate the protocol through the normal
`ts: next --app-server` one-command route. Publication, installed-skill synchronization, Core
snapshot upgrade, Windows execution, and deployment remain outside this evidence.
