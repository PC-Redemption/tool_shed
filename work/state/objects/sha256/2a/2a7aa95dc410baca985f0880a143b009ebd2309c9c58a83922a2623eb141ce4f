# Evidence: Core v0.29.13 first-pass owner-ready proof

Status: verified
Type: evidence
Updated: 2026-08-26
Campaign: adopt-first-pass-app-server-preparation-in-core

## Release adoption

The authorized Windows upgrade moved `E:\dev\bactron-core` transactionally from verified Tool
Shed v0.29.12 to verified v0.29.13. The selected content commit was
`eae28bee58b3f282b28862bb3e45e7d43e092594`, the annotated tag resolved to provenance commit
`1940cddc3b70bb64c5f12289151cc94e09c69802`, and canonical-manifest verification passed. The
bounded rollback archive is
`E:\dev\bactron-core\tool_shed.backup-20260826T175616Z.tar`. The Windows installed skill was
already exactly current, so it was not rewritten.

The exact GUI-bundled executable was
`C:\Users\jong.SHELDONMFG\.vscode\extensions\openai.chatgpt-26.818.61809-win32-x64\bin\windows-x86_64\codex.exe`,
version `0.149.0-alpha.4.3`.

## Fresh first-attempt proof

Fresh Core Campaign 024 began with stable semantic intent and no manually authored execution
capsule. From the normal logged-in Windows interactive session, one dispatcher invocation prepared
source-fresh collateral and completed one worker attempt:

- Preparation used `gpt-5.6-sol` / high for one turn: 25,244 input tokens, including 15,104 cached;
  2,219 output tokens; 1,333 reasoning tokens; 2,796 context bytes; one context file; one expected
  path; and 35.752 seconds.
- Execution used `gpt-5.6-terra` / medium for two observed protocol turns: 40,118 input tokens,
  including 30,208 cached; 749 output tokens; 268 reasoning tokens; one 1,242-byte `fileChange`;
  zero worker commands; and 19.093 seconds.
- The full dispatcher took 57.922 seconds, used zero dispatcher model tokens, and did not invoke a
  nested Codex wrapper. Total preparation-plus-execution input was 65,362 tokens, within the live
  execution ceilings and far below the earlier 540,741-input-token Core regression.
- The journal recorded only `docs/app_server_camp_preparation.md` as modified, with no created,
  deleted, or unexpected paths. The first completed file change triggered the acknowledged
  `worker_file_change_ready` control stop.
- The generated deterministic verifier used one shared whitespace-collapse and `casefold()`
  normalizer for the document and every expected semantic phrase. It ran exactly once, exited 0,
  emitted no output, and left final state `verified`.

Core Campaign 024 was completed with this evidence in Core commit
`a6dffc8274de5ab257d495cca472b0416a177a24`. Superseded Campaign 023 was abandoned with Campaign
024 recorded as its replacement; it was not replayed.

## Boundary

No product code, deployment configuration, production system, PID setting, or hardware was changed.
Bactron was not deployed. Raw dispatcher telemetry remains in the Windows user's local Tool Shed
proof directory; only the compact durable result is recorded here.
