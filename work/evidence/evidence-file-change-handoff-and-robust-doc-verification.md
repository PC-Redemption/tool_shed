# Evidence: File-Change Handoff and Robust Documentation Verification

Status: verified
Type: evidence
Updated: 2026-08-26
Campaign: preserve-file-change-handoff-and-robust-doc-verification

## Field observation

The first Windows execution of Core Campaign 022 through Tool Shed v0.29.11 proved that automatic
source-fresh preparation was working: preparation completed in one turn with 25,089 input tokens,
1,363 output tokens, 516 reasoning-output tokens, 2,013 context bytes, and one selected mutation
path. The command-free worker then completed the one expected documentation `fileChange` after four
model turns with 84,673 input tokens, including 60,672 cached input tokens, 3,705 output tokens,
331 reasoning-output tokens, and 4,700 serialized tool-result bytes.

Two orchestration defects prevented first-attempt closure:

- the fourth token-usage notification recorded a model-turn ceiling immediately before the
  completed `fileChange`, so the already-complete mutation did not enter its reserved deterministic
  verifier; and
- the generated documentation verifier compared raw multiword substrings, so ordinary Markdown
  wrapping split two required phrases and made the otherwise-correct document appear invalid.

Core changed only `docs/app_server_camp_preparation.md`. A no-replay, whitespace-normalized
reconciliation check passed, and Core preserved that result as commit
`347eccd` (`docs: reconcile source-fresh App Server preparation`). No Bactron deployment occurred.

## Repair

- `scripts/codex_app_server.py` now preserves a completed first-file-change handoff when the only
  same-boundary finding is the no-further-request model-turn ceiling. It still interrupts the turn,
  does not request another model turn, and retains input-token and tool-result budget findings.
- `scripts/app_server_dispatch.py` tells automatic preparation to normalize documentation
  whitespace before semantic phrase assertions and rejects Core-shaped raw-substring Markdown
  verifiers before capsule persistence or worker launch.
- Focused regressions reproduce the four-usage-update-then-file-change ordering, verify the
  Tool-Shed-owned verifier runs exactly once, preserve the ordinary pre-mutation turn-ceiling stop,
  prove input and tool-output ceilings remain fail-closed, reject the fragile Core-shaped verifier,
  and accept its whitespace-normalized equivalent.

## Verification

```text
python3 -m unittest tests.test_codex_execution tests.test_app_server_dispatch
Ran 71 tests in 12.901s
OK

git diff --check
passed
```

The expected compatibility warning for the host's unqualified newer Codex CLI
`0.200.0-alpha.7` appeared in the focused suite; it did not affect the fake-protocol regressions or
change the exact-qualified Windows executable used for the field proof.

## Boundary

This evidence closes the local repair only. It does not authorize or perform a new Tool Shed
release, installed-skill synchronization, another Core snapshot upgrade, another Windows worker,
Campaign 013 replay, or Bactron deployment.
