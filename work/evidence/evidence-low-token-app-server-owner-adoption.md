# Low-token App Server owner adoption

Date: 2026-08-25
Campaign: adopt-low-token-app-server-campaign-loop
Gate: G5-OWNER-ADOPTION
Result: passed

## Daily path

For a prepared, ready Tool Shed campaign in a qualified Linux or Windows workspace, send one
command in the normal Codex GUI:

```text
ts: next --app-server
```

Routine CAMP execution selects `gpt-5.6-terra` with medium reasoning. Planning uses Sol/high and
verification uses Terra/low only when those roles are explicitly selected with `--app-server`.
Discussion stays in the GUI. App Server and API fallback remain default-off, so every use is an
invocation-scoped choice.

Before mutation, Tool Shed requires a ready campaign, a strict execution capsule, bounded context,
declared relative paths, shell-free deterministic verification, writable Codex state, ChatGPT
authentication, model-list access, and exact workspace-write qualification. A failure before
mutation can fall back by rerunning `ts: next` without `--app-server`. After mutation, no automatic
replay is allowed: follow the compact journal's category, mutation state, and recovery action and
reconcile first.

## Measured direct results

| Measure | Linux direct | Windows direct |
| --- | ---: | ---: |
| Model | Terra / medium | Terra / medium |
| Model turns | 2 | 2 |
| Input tokens | 38,124 | 38,324 |
| Cached input | 18,176 | 29,184 |
| Output tokens | 222 | 379 |
| Reasoning output | 32 | 73 |
| Total tokens | 38,346 | 38,703 |
| Weighted usage proxy | 23,097.6 | 14,332.4 |
| Model/CAMP time | 9.042 s CAMP | 11.500 s model / 12.343 s CAMP |
| Total dispatcher time | 9.663 s | 13.031 s |
| Dispatcher model tokens | 0 | 0 |
| Nested Codex | false | false |
| Declared verification | 1 passed | 1 passed |
| Mid-run owner prompts | 0 | 0 |

The Linux weighted value is calculated from the recorded raw categories using the same published
weighted-usage v1 factors. The metric is a relative usage proxy, not price or ChatGPT allowance.
The GUI's outer conversation token count is not exposed and is not estimated.

Both direct runs retained the representative two-turn shape and were safe and verified. Windows
used 95.71% fewer input tokens than the 893,723-token nested-wrapper fixture. That fixture measured
an unnecessary outer `codex exec` agent, not the supported dispatcher, and is no longer part of the
route.

## Supported boundary

- Linux: field-proven direct dispatcher with qualified Codex 0.149.0.
- Windows: field-proven from the logged-in GUI console with exact project-reviewed Codex
  `0.149.0-alpha.4.3`; normal GUI use needs no `PATH` setup.
- Remote Windows automation: it must enter the existing console session. A direct SSH service
  process cannot reach the GUI sandbox runner pipe.
- Other operating systems, API-key authentication, unqualified workspace-writing versions,
  deployments, and roles disabled by policy are not supported by this proof.
- App Server remains experimental and explicit opt-in. The ordinary GUI path remains available by
  omitting `--app-server`.

No implementation inputs changed during adoption. Only operator guidance changed, so the focused
documentation smoke is the appropriate final check rather than another full suite.
