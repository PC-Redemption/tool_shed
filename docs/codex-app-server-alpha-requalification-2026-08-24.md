# Codex App Server Alpha Requalification — 2026-08-24

## Decision

Codex CLI `0.149.0-alpha.4.3` is qualified with blockers for Tool Shed's explicit read-only
planning and verification roles. CAMP workspace writing is not qualified because no reviewed
disposable workspace-write harness was run for this exact executable. The global default and API
fallback remain off, and unknown Codex versions remain fail-closed.

This document records the 2026-08-24 read-only result. A separately reviewed 2026-08-25 harness
subsequently qualified one exact executable digest for bounded CAMP writing; see
[`codex-app-server-write-qualification-alpha-2026-08-25.md`](codex-app-server-write-qualification-alpha-2026-08-25.md).

This is an exact, version-specific qualification. It does not treat the alpha as semantically
equivalent to stable `0.149.0`, establish an open-ended minimum version, or inherit the stable
build's workspace-write qualification.

## Installed executable

- Version: `codex-cli 0.149.0-alpha.4.3`
- Resolver source: explicit trusted OpenAI VS Code Server extension override
- Platform: Debian 13, x86_64
- Authentication: ChatGPT; API-key fallback disabled
- App Server user agent: `codex_vscode/0.149.0-alpha.4.3`

The same version was first observed through Tool Shed's trusted OpenAI VS Code extension discovery
on Windows, where `codex` was absent from `PATH`. That field run and this local run agreed on App
Server startup, authentication, model availability, new-thread isolation, fail-closed approvals,
restricted-read incompatibility, and the fixed token baseline.

## Read-only compatibility smoke

The local live smoke passed executable resolution, version detection, App Server startup, ChatGPT
authentication, no-API-fallback enforcement, GUI fallback, GUI-native discussion, fail-closed
approval behavior, planning and verification model availability, completed read-only turns,
distinct new threads, cancellation reconciliation, and the tiny-operation token baseline.

| Role | Model / reasoning | Input | Cached input | Output | Result |
| --- | --- | ---: | ---: | ---: | --- |
| Planning | `gpt-5.6-sol` / high | 18,917 | 9,984 | 12 | completed |
| Verification | `gpt-5.6-terra` / low | 18,916 | 9,984 | 11 | completed |

Cancellation returned `no active turn`; immediate thread reconciliation observed `interrupted`,
and Tool Shed safely classified the operation as cancelled. The acknowledgement race remains a
blocker.

Restricted read remains blocked. This build rejects `readOnly.access` and requires
`permissionProfile`. Tool Shed does not add a version-specific protocol workaround as part of this
qualification.

## Boundary

- Qualified: explicit Sol/high planning and Terra/low verification.
- Not qualified: CAMP execution or any other workspace writing.
- Still disabled: implementation, testing, build, deployment, permission expansion, network
  access, API fallback, and automatic lifecycle transitions.
- Stable `0.149.0` retains its separately reviewed planning, verification, and CAMP qualification.
- Versions without an exact reviewed record and configuration allowlist entry remain fail-closed.

Sanitized telemetry was retained outside the repository under the user's Codex state directory.
No raw prompt or response content is committed.
