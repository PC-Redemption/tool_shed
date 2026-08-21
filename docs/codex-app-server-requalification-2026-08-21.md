# Codex App Server Requalification — 2026-08-21

## Decision

Codex CLI 0.149.0 is qualified with blockers for Tool Shed's existing explicit App Server roles:
Sol/high planning, Terra/low verification, and one bounded Terra/medium `camp_execution` step. The
global default remains off. Generic implementation, testing, build, deployment, permission
expansion, network access, API-key fallback, and automatic campaign transitions remain disabled.

This is a new version-specific decision, not inherited qualification from Codex CLI 0.144.6. It is
based on a live read-only compatibility smoke and a separately reviewed disposable workspace-write
harness on this host. OpenAI continues to describe App Server as experimental and unsupported for
production workloads in the [official App Server documentation](https://developers.openai.com/codex/app-server).

## Installed executable

- Version: `codex-cli 0.149.0`
- Resolver source: `PATH`
- Resolver path: `/home/jon/.local/bin/codex`
- Standalone target: `/home/jon/.codex/packages/standalone/releases/0.149.0-x86_64-unknown-linux-musl/bin/codex`
- Authentication: ChatGPT Pro; API-key fallback disabled
- App Server user agent: `codex_vscode/0.149.0 (Debian 13.0.0; x86_64)`

Before the registry update, both user-facing status paths reported the executable as available and
App Server-capable but correctly returned `UNQUALIFIED VERSION` against the 0.144.6 record.

## GUI-triggered explicit route

After recording the new qualification, the active Codex GUI workflow invoked the same selector and
orchestrator chain used by `ts: plan ... --app-server`. The selector allowed explicit App Server
planning with `gpt-5.6-sol` / high. The orchestrator resolved `/home/jon/.local/bin/codex`, started
App Server with user agent `codex_vscode/0.149.0`, supplied only the Campaign 045 request inline,
completed in one model turn without tools or mutations, and returned no compatibility warning.
This proves the local GUI-triggered route uses the requalified centralized resolver; it does not
replace the separate Windows GUI/no-PATH release gate.

## Read-only compatibility smoke

The live smoke passed executable resolution, version detection, App Server startup, ChatGPT
authentication, no-API-fallback enforcement, GUI fallback, GUI-native discussion, fail-closed
approval behavior, model/reasoning availability, planning and verification turns, distinct new
threads, cancellation reconciliation, and the tiny-operation token baseline.

| Role | Model / reasoning | Input | Cached input | Output | Result |
| --- | --- | ---: | ---: | ---: | --- |
| Planning | `gpt-5.6-sol` / high | 18,984 | 9,984 | 12 | completed |
| Verification | `gpt-5.6-terra` / low | 18,983 | 9,984 | 11 | completed |

The cancellation request returned `no active turn`, but immediate thread reconciliation observed
terminal `interrupted` and Tool Shed safely classified the operation as cancelled. The
acknowledgement race therefore remains a blocker even though the bounded recovery result passed.

Restricted read remains inconsistent. Codex 0.149.0 rejected `readOnly.access` and requires
`permissionProfile`; Tool Shed retains its already validated read-only mechanism and does not add a
version-specific workaround.

## Disposable workspace-write harness

The full harness completed in 36.693 seconds and passed every required boundary:

- authorized read/create/modify/delete/directory creation, harmless command, and focused test;
- blocked sibling write and destructive delete, privileged write, network access, and hardened
  `/tmp` access;
- schema-default `/tmp` access remained observable, confirming that both temp exclusions are
  required;
- an approval request was declined and its target remained absent;
- the Terra/medium write changed only the declared file, passed its focused test, and produced a
  safe Git journal with no unexpected paths; and
- interruption left an expected partial file, prevented the delayed write, produced a safe
  journal, and preserved the read-only boundary during resume.

The minimal Terra write used 77,864 input tokens, 56,576 cached input tokens, 393 output tokens,
four model turns, and three tool calls. Raw prompt-free harness output is retained under the ignored
`work/evidence/generated/codex-app-server-write-qualification-0.149.0.json` path.

## Retained blockers and boundary

- cancellation acknowledgement race;
- GUI approval bridge unavailable;
- restricted-read protocol mismatch;
- fixed App Server harness cost remains material for tiny CAMPs; and
- App Server remains experimental and unsupported for production.

The qualification therefore remains invocation-scoped and fail-closed. Any version mismatch,
authentication change, journal drift, unexpected path, partial mutation, unknown outcome, or
policy mismatch blocks App Server execution while leaving the unflagged GUI route available.
