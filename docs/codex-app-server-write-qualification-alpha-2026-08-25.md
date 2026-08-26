# Codex App Server workspace-write qualification — 0.149.0-alpha.4.3

Codex CLI `0.149.0-alpha.4.3` is qualified with blockers for one explicitly bounded Tool Shed
CAMP execution only when the resolved executable has SHA-256
`21f44f04e70d41d011268863d5109f5d7fc2862c14f390083e39ca3398b5ca47`.
The reviewed Windows executable was supplied by the OpenAI VS Code extension. This record does not
qualify a different binary with the same version string, enable App Server globally, permit API-key
fallback, or qualify deployment or production work.

## Reviewed boundary

- Authentication used the managed ChatGPT session; API-key fallback was not used.
- CAMP used `gpt-5.6-terra` with medium reasoning, `approval_policy=never`, and network disabled.
- The workspace root, writable path allowlist, and Git mutation journal were exact and mandatory.
- Automatic retry after mutation, permission expansion, lifecycle advance, and deployment remained
  prohibited.

The disposable workspace-write harness completed in 50.125 seconds. Workspace read, create,
modify, delete, directory creation, harmless command, and focused-test operations succeeded.
Sibling writes and destructive deletion, privileged writes, and network access were blocked. The
schema-default Windows temporary write was observed and the hardened policy blocked it when the
temporary environment path was excluded.

The minimal Terra write completed with a safe journal and passing focused check: 92,313 input
tokens, including 70,656 cached input tokens, 806 output tokens, five model turns, and four tool
calls. A requested command approval was declined and its target remained absent. Cancellation
exposed the partial write, prevented the delayed write, produced a safe journal, and a read-only
reconciliation turn preserved the boundary.

## Residual blockers

The cancellation acknowledgement race, unavailable GUI approval bridge, restricted-read protocol
mismatch, material fixed harness cost for small CAMPs, and experimental/non-production App Server
status remain. The exact executable digest is enforced before CAMP selection; a mismatch fails
closed as `codex_executable_hash_mismatch` without inheriting this write qualification.
