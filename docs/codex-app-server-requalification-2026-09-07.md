# Codex App Server 0.153.0 Qualification — 2026-09-07

## Decision

Codex CLI 0.153.0 is **unqualified** for Tool Shed's default App Server routes. Linux passed the
read-only planning and verification roles plus bounded Terra/medium CAMP execution. Windows passed
read-only planning and verification, but its workspace-write turns could not read or mutate the
disposable qualification workspace. Because Tool Shed promises the bounded CAMP role on both
supported platforms, the exact version is denylisted until the Windows failure is repaired and
requalified. The existing GUI route remains available.

This decision is based on separate exact-version runs; neither platform inherits the other's
result. OpenAI describes App Server as the protocol used by rich Codex clients and documents named
permission profiles as beta. Tool Shed continues to treat it as a local integration rather than a
production workload. See the
[official App Server documentation](https://developers.openai.com/codex/app-server).

## Exact executables

| Platform | Executable source | SHA-256 | Result |
| --- | --- | --- | --- |
| Linux x86_64 | official `@openai/codex@0.153.0` optional Linux payload in the disposable testbed | `fce635028842bfe9257140e8b7d53162732945e2f356fc35225be0702b4974be` | qualified with retained product blockers |
| Windows x86_64 | OpenAI VS Code extension `openai.chatgpt-26.901.22334-win32-x64` | `0f8ed9678bca539aa6517adb0c8d50ad9a94ff5df4d21e149ae700d219fff69d` | unqualified: workspace-write access denied |

The Windows run used the extension path directly while `Get-Command codex` remained absent. It ran
from a logged-in GOGETTER console task because the SSH service session cannot reach the GUI sandbox
surface. The Linux package was installed only under the disposable Linux testbed; the host's normal
Codex selection was not changed.

## Read-only qualification

Both platforms started App Server with managed ChatGPT authentication and no API-key fallback.
Sol/high planning and Terra/low verification completed on distinct threads under the allowed
`:read-only` permission profile, emitted no mutation events, and left the disposable workspace
unchanged. Cancellation was requested only after the matching `turn/started` event, acknowledged by
0.153.0, and reconciled to terminal `interrupted` state.

The initial Linux probe requested interruption immediately after `turn/start`. App Server returned
`no_active_turn` while `thread/read` still reported `inProgress`, reproducing the historical race.
The qualification harness now waits for `turn/started`; focused regression coverage preserves that
ordering without weakening the bounded terminal-state reconciler.

## Linux workspace-write result

The Linux harness passed the hardened exact-root boundary, controller-owned focused test, denial,
and interruption/no-replay checks. Its Terra/medium turn changed only `sample.py`, produced a safe
Git journal with no unexpected paths, and passed the focused test. The interrupted turn left the
expected partial file, prevented the delayed write, and resumed read-only as
`needs_user_intervention`. The full write harness completed in 51.016 seconds.

## Windows workspace-write blocker

The Windows result is a safe failure, not a partial qualification:

- `permissionProfile/list` reported `:workspace` as allowed, but both that profile and the legacy
  `workspaceWrite` turn path returned filesystem access denied before reading `sample.py`;
- the failure repeated in fresh fixtures under the E: testbed and the user's temporary directory;
- direct `command/exec` rejected Tool Shed's hardened split writable-root policy rather than
  running unsandboxed;
- the approval-denial probe passed and its target remained absent;
- interruption reached terminal `interrupted`, the delayed file remained absent, the journal was
  safe, and the read-only resume boundary held; and
- the pre-existing `work/index.json` and `work/index.md` testbed drift was preserved exactly.

Tool Shed does not invoke Windows sandbox setup, broaden ACLs, weaken temporary-directory
exclusions, or fall back to API keys to manufacture a pass. Those actions exceed this campaign's
testbed authority and would weaken the supported safety contract.

## Released behavior

The registry records 0.153.0 as an exact reviewed `unqualified` version. Operator-runtime trust
therefore does not treat it as merely unseen: Tool Shed returns the action to the GUI. Positive
0.149.0 qualifications remain unchanged. The Windows-aware write harness now records native command
behavior and handle-retention limits without mistaking cleanup timing for an execution failure.

Machine-readable, content-free evidence is in
[`work/evidence/camp-0171-codex-app-server-0.153.0.json`](../work/evidence/camp-0171-codex-app-server-0.153.0.json).
