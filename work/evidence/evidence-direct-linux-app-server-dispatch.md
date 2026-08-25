# Evidence: Direct Linux App Server campaign dispatch

Status: complete
Type: evidence
Updated: 2026-08-25
Next Action: return to the Campaign 059 Windows and Bactron Core consent boundary
Campaign: eliminate-nested-codex-wrapper-and-prove-linux-dispatch

## Candidate and scope

- Local unpublished candidate: Tool Shed `0.29.0`.
- Disposable native Linux client: `/tmp/ts-linux-dispatch-proof.or2fbT/client`.
- Scope remained inside the Tool Shed source workspace and disposable client. Nothing was
  published or synchronized, and Bactron Core was not accessed.
- The dispatcher reuses ordinary campaign selection, guarded campaign start, the existing
  qualified `camp-run` implementation, and the existing mutation journal. It does not invoke
  `codex exec`.

## Candidate validation

- Focused dispatcher and forwarding tests passed: 8 tests in 0.043 seconds.
- The unchanged candidate then passed the full Tool Shed validator: 264 tests in 63.955 seconds,
  provider-adapter conformance, generated indexes, stale-path checks, work-state reconciliation,
  roadmap validation, temporary-workspace smoke, and template/example sanity.
- The version manifest matched all 140 tracked snapshot files and `git diff --check` passed.

## Direct Linux execution

The disposable client contained one queued campaign with one strict App Server execution capsule.
This GUI session invoked the dispatcher directly once:

```text
env PYTHONDONTWRITEBYTECODE=1 python3 /tmp/ts-linux-dispatch-proof.or2fbT/client/tool_shed/scripts/app_server_dispatch.py --workspace /tmp/ts-linux-dispatch-proof.or2fbT/client next --app-server --json
```

Preflight confirmed writable Codex state, managed ChatGPT authentication, a successful model-list
network check, selected-model availability, Codex `0.149.0`, and exact qualification. The ordinary
`next` result selected and guarded-started campaign `prove-direct-linux-dispatch`.

The existing App Server CAMP runner then:

- used `gpt-5.6-terra` with medium reasoning and no API fallback;
- created only `docs/direct-linux-dispatch-proof.md`;
- reported no modified, deleted, or unexpected paths;
- ran the single declared shell-free verification exactly once and passed it; and
- reached mutation-journal final state `verified` with no recovery action required.

The dispatcher completed in 9.663 seconds with zero dispatcher model tokens and
`nested_codex_exec: false`. Inner App Server execution took 9.042 seconds across two model turns
and one `fileChange` tool call. It used 38,124 input tokens, including 18,176 cached input tokens,
222 output tokens, 32 reasoning-output tokens, and 38,346 total tokens. The Codex GUI does not
expose the current outer conversation's token count to the dispatcher, so that field is reported
honestly as `not exposed` rather than estimated.

## Gate result

Campaign 060 passes. The earlier 893,723-token nested-wrapper result has been structurally
mitigated: the supported fast path is now deterministic orchestration with zero dispatcher model
tokens, while the bounded App Server CAMP remains the only model-driven execution layer. The same
dispatcher is implemented with cross-platform Python and portable path/argv validation; Windows
installation and Bactron Core proof remain Campaign 059 and require the owner's retained consent.
Completing the detour caused the queue lifecycle to auto-promote Campaign 059 without executing
any Windows or Core work; it was immediately placed in blocked consent-held state so no protected
action can begin implicitly.
