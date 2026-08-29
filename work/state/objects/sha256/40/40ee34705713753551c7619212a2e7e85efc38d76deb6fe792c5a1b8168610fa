# Evidence: Passive App Server dogfooding core

Status: verified
Type: evidence
Updated: 2026-08-27
Next Action: none
Campaign: qualify-passive-app-server-dogfooding-core
Campaign Reason: G1-PASSIVE-CORE-QUALIFIED completion evidence

## Candidate

- Unpublished Tool Shed version: `0.30.0`
- Repository App Server default: off
- Preference state: protected user-local JSON under Codex home
- Diagnostic state: sanitized best-effort JSON Lines under Codex home
- Publication, tag, push, installed-skill synchronization, downstream upgrade, and deployment: not performed

## Focused behavior evidence

The final candidate passed 88 focused App Server preference, selection, dispatch, fallback,
mutation-reconciliation, no-replay, and privacy tests. The coverage includes:

- persistent on/off and status, canonical `app-server` route, retained `appserver` alias, and
  atomic private storage outside repositories and installed snapshots;
- precedence of `--gui`, strict explicit `--app-server`, persisted preference, and committed GUI
  default;
- unchanged GUI-native discussion and brainstorming behavior;
- qualified eligible selection and persistent-mode pre-mutation GUI fallback;
- mutation-aware GUI reconciliation with App Server replay forbidden;
- best-effort logging failure and the exact sanitized event-field allowlist, excluding prompts,
  responses, raw tool output, credentials, exception text, and repository content.

## Installer and provider parity

Seventeen focused installer, generated-provider, documentation-site, and adapter tests passed in
disposable workspaces. The generated Claude, Gemini, GitHub Copilot, and Cursor instructions retain
the same preference precedence, immediate fallback, reconciliation/no-replay, event privacy, and
strict-explicit contract as the canonical portable skill. Codex retains its compact workspace-local
skill routing contract. Provider adapter conformance and canonical skill validation also passed.

## Focused commands

```text
python3 -m unittest tests.test_app_server_user_state tests.test_codex_execution \
  tests.test_app_server_dispatch tests.test_next_app_server_forwarding -q
88 tests passed

python3 -m unittest \
  tests.test_scripts.ScriptTests.test_installer_supports_all_provider_adapters_idempotently \
  tests.test_scripts.ScriptTests.test_operator_help_is_packaged_and_routed \
  tests.test_docs_site tests.test_provider_adapters -q
17 tests passed

python3 scripts/check_provider_adapters.py
Provider adapter conformance passed

python3 /home/jon/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/tool-shed
Skill is valid

python3 scripts/update_shed_manifest.py --check
SHED_VERSION.json matches 143 tracked files

git diff --check
passed
```

## Full validation

The single final full validator run on the unchanged shipped `0.30.0` inputs passed:

```text
python3 scripts/validate_tool_shed.py
310 tests passed
Provider adapter conformance passed
No stale work paths found
Work state is reconciled
Program Roadmaps valid with no findings
Disposable all-provider installation and lifecycle smoke passed
tool_shed validation passed
```

The disposable smoke installed every provider surface, verified compact Codex routing and complete
portable provider guidance, exercised canonical work creation and lifecycle transitions, and left
no snapshot-local state. This supplies the snapshot/install parity proof for the unpublished
candidate. The validator reported expected development drift between the unpublished canonical
skill and the installed published client; synchronization was intentionally not performed.

## Gate verdict

`G1-PASSIVE-CORE-QUALIFIED`: PASS.
