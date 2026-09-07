# Codex App Server 0.153.0 Windows Repair and Requalification — CAMP-0172

## Decision

Codex CLI 0.153.0 is **qualified with retained product blockers** for Tool Shed's supported local
planning, verification, and bounded CAMP roles on Linux x86_64 and Windows x86_64. This supersedes
CAMP-0171's global `unqualified` decision. It does not claim that the native Codex Windows
workspace-write sandbox was repaired: that path remains unusable on the qualified Windows host.
Tool Shed instead keeps the App Server thread read-only and exposes one controller-owned,
digest-bound file-replacement function for the declared CAMP paths.

The replacement is a supported execution path, not a GUI fallback. The exact Windows executable
ran the production `execute_camp_if_enabled` entrypoint, changed one allowlisted file, passed the
controller's deterministic read-only verification, produced a safe Git mutation journal, and
returned `advance_to_next_camp_step`.

## Exact executables

| Platform | Executable source | SHA-256 | Result |
| --- | --- | --- | --- |
| Linux x86_64 | official `@openai/codex@0.153.0` optional Linux payload | `fce635028842bfe9257140e8b7d53162732945e2f356fc35225be0702b4974be` | qualified |
| Windows x86_64 | OpenAI VS Code extension `openai.chatgpt-26.901.22334-win32-x64` | `0f8ed9678bca539aa6517adb0c8d50ad9a94ff5df4d21e149ae700d219fff69d` | qualified through Tool Shed's bounded controller path |

Both runs used managed ChatGPT authentication with API-key fallback disabled. Neither run changed
the user's global Codex selection or permission defaults.

## Windows compatibility repair

The observed 0.153.0 Windows failure was reproducible: native workspace-write turns could start,
but PowerShell failed during process initialization and other commands could not read or mutate the
fresh disposable workspace. Adding roots or broadening native permissions did not produce a safe,
usable CAMP path.

Tool Shed now uses these Windows controls:

- the model thread runs with the allowed `:read-only` permission profile;
- the only permitted worker tool type is `dynamicToolCall` and command execution is rejected;
- `write_workspace_file` accepts only a controller-declared repository-relative path, its exact
  starting SHA-256 (or `absent`), and complete UTF-8 replacement content;
- the controller rechecks the live digest, symlink state, parent, and byte budget before an atomic
  replacement;
- one handler instance permits exactly one mutation, so stale, outside, and replayed writes fail
  closed; and
- declared tests run after the worker through a network-disabled, root-read-only Codex sandbox
  profile, then the existing Git mutation journal decides whether the CAMP may advance.

Native Linux CAMP execution remains unchanged and continues to use the hardened workspace-write
sandbox. The cross-platform orchestrated fixture passed on both exact executables.

## Qualification results

Every section passed on both platforms: boundary enforcement, temporary-path denial, live
Terra/medium write, approval denial, cancellation/no-replay reconciliation, and the full production
CAMP entrypoint with controller verification. The Windows run recorded one `dynamicToolCall`, one
modified expected file, no unexpected paths, and a `verified` final journal state. The Linux run
recorded the corresponding native `fileChange` handoff and the same terminal result.

Machine-readable reports:

- [`camp-0172-codex-app-server-0.153.0-linux.json`](../work/evidence/camp-0172-codex-app-server-0.153.0-linux.json)
- [`camp-0172-codex-app-server-0.153.0-windows.json`](../work/evidence/camp-0172-codex-app-server-0.153.0-windows.json)

The reports' SHA-256 digests are respectively
`cf6c9dde148177c65b9acd6d682b5e656b25a0e1c0d655dee658960c7ea53350` and
`3a34694500372db8c2a0be34a1779d38d13685941fe46d2ee4e476f6bb48885f`.

## Retained boundaries

App Server remains a local integration rather than a Tool Shed production workload, and the GUI
approval bridge is still unavailable. The qualified Windows CAMP route supports one complete text
file replacement per bounded step; work requiring a different mutation shape must be split into a
new bounded step or returned for operator handling. Those limits do not deny the qualified local
roles.
