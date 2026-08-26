# Evidence: Linux path-state command-free code/test proof

Status: verified
Type: evidence
Updated: 2026-08-26
Campaign: prove-path-state-command-free-first-pass-code-test-campaign-on-linux

## Result

Campaign 082 passed its first-worker gate through the normal App Server route. Automatic
preparation resolved the provider validation change to `scripts/provider_adapters.py` and the
authorized absent creation target `tests/test_provider_adapters.py`, supplied the production source
inline, and reserved one quiet standard-library verifier.

The CAMP worker completed the entire two-file mutation in one `fileChange`. It issued no
`commandExecution`, and Tool Shed interrupted it immediately after the completed file change with
the `worker_file_change_ready` control stop. The mutation journal found only the two declared paths
and preserved all pre-existing dirty state.

## Usage and control evidence

- Automatic preparation: one frontier-model turn; 33,790 input tokens and 1,810 output tokens.
- CAMP execution: one workhorse-model turn; 20,962 input tokens, including 9,984 cached input
  tokens, and 1,296 output tokens.
- Worker tools: exactly one `fileChange`; zero commands.
- Control stop: interrupt requested and acknowledged after the completed file change.
- Expected path states: existing production file plus absent authorized test creation target.
- Unexpected paths: none.

## Exactly-once verification

Tool Shed, not the worker, ran the reserved verifier exactly once:

```text
/usr/bin/python3 -m unittest -q tests/test_provider_adapters.py
```

Result: two tests passed. The journal final state is `verified` and its recovery action is
`advance_to_next_camp_step`.

## Boundary

This satisfies the code/test contribution to G11. The dependent asset-aware proof remains required
before the Linux first-pass milestone is complete. Publication, installed-skill synchronization,
Core snapshot upgrade, Windows execution, and deployment remain outside this evidence.
