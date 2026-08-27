# Evidence: Operator-trust CAMP runtime enforcement

Status: verified
Type: evidence
Updated: 2026-08-27
Next Action: none
Campaign: qualify-and-document-operator-trust-camp-boundaries
Campaign Reason: G1-OPERATOR-TRUST-CAMP-PROVEN completion evidence

## Candidate

- Unpublished Tool Shed version: `0.33.0`
- Normal policy: fresh schema-v2 `ts: app-server on` records `operator-runtime` trust
- Optional policy: repository `strict-certified` mode retains exact certification gates
- Publication, push, release, deployment, installed-skill synchronization, and downstream upgrade:
  not performed

## Usability proof

Ninety-six focused App Server tests passed. The end-to-end CAMP case uses an unregistered Codex
`0.200.0`, selects it through fresh operator trust, performs a real bounded file mutation through
the existing App Server runner, preserves the existing Git mutation journal and exact path boundary,
runs controller-owned deterministic verification, and returns `verified`.

The focused suite also proves legacy schema-v1 `on` does not silently gain CAMP trust, fresh `on`
does not invoke the dirty-read harness, executable-hash mismatch is telemetry in normal mode,
explicit repository strict mode still requires certification, and an evidence-backed exact
`unqualified` record blocks only its recorded version while `0.200.1` runs normally.

No parallel runtime preflight, policy engine, mutation journal, quarantine database, or protected
state store was added. Startup, ChatGPT authentication, live model selection, and requested sandbox
remain part of the actual operation. Existing clean-worktree, exact-path, journal, bounded-execution,
deterministic-verification, reconciliation, and no-replay behavior remains authoritative.

## Documentation and installation parity

The README, command reference, operator guide, App Server execution and maintainer notes, canonical
Tool Shed skill route, and installer-generated provider guidance now describe the same contract.
Historical qualification reports remain unchanged as evidence. The full validator exercised
disposable provider installations and snapshot state without publishing or synchronizing them.

## Validation

```text
python3 -m unittest tests.test_app_server_user_state tests.test_codex_execution \
  tests.test_codex_cli_reporting tests.test_app_server_dispatch
96 tests passed

python3 scripts/validate_tool_shed.py --profile full
321 of 321 tests passed
Provider adapter conformance passed
No stale work paths found
Work state is reconciled
tool_shed full validation passed
```

## Gate verdict

`G1-OPERATOR-TRUST-CAMP-PROVEN`: PASS.
