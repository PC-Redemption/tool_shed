# Evidence: Linux path-state command-free asset-aware proof

Status: verified
Type: evidence
Updated: 2026-08-26
Campaign: prove-path-state-command-free-first-pass-asset-aware-campaign-on-linux

## Result

Campaign 083 passed its first-worker gate through the normal App Server route. Automatic
preparation supplied the complete 30,650-byte text boundary from `scripts/build_docs_site.py` and
`tests/test_docs_site.py`; site asset payloads remained outside the inline context as required.
Both authorized paths were explicitly identified as existing files.

The CAMP worker generalized the production asset revision and added focused tests in one completed
`fileChange`. It issued no `commandExecution`. Tool Shed interrupted it immediately after that file
change with the `worker_file_change_ready` control stop, found only the two declared modified paths,
and preserved all pre-existing dirty state.

## Usage and control evidence

- Automatic preparation: one frontier-model turn; 33,104 input tokens and 2,554 output tokens.
- CAMP execution: one workhorse-model turn; 27,364 input tokens and 1,186 output tokens.
- Worker tools: exactly one `fileChange`; zero commands.
- Control stop: interrupt requested and acknowledged after the completed file change.
- Expected path states: two existing regular source files.
- Unexpected paths: none.

## Exactly-once verification

Tool Shed, not the worker, ran the reserved verifier exactly once:

```text
/usr/bin/python3 -m unittest discover -s tests -p test_docs_site.py -q
```

Result: 13 tests passed. The focused coverage proves deterministic filename ordering, content and
rename sensitivity, direct-file-only behavior, and the existing 12-character lowercase hexadecimal
contract. The journal final state is `verified` and its recovery action is
`advance_to_next_camp_step`.

## Gate result and boundary

Together with the documentation and provider code/test proofs, this satisfies
G11-LINUX-FIRST-PASS-RELIABLE. Fresh representative Linux campaigns now have evidence for the
one-command, source-fresh, automatically prepared, command-free worker path without manual capsule
editing or worker replay.

Publication, installed-skill synchronization, Core snapshot upgrade, Windows execution, and
deployment remain separately authorized work.
