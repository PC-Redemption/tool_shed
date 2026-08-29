# Prove first-pass code and test preparation on Linux

Status: abandoned
Type: campaign
Updated: 2026-08-26
Next Action: none
Campaign ID: prove-first-pass-code-test-campaign-on-linux
Campaign Number: 073
Outcome: A fresh bounded code-and-test campaign completes from one App Server command without preparation repair after launch.
Primary Focus Areas: provider-portability
Supporting Focus Areas: campaign-lifecycle, workspace-safety
Depends On: prove-first-pass-documentation-campaign-on-linux
Decision: none
Detour For: none
Return To: none
Completion Gate: The code/test proof contributes passing evidence to G11 with scoped output, first-attempt execution, and exactly-once verification.
Completion Evidence: none
Disposition: First worker inspection exceeded the 16 KiB single-result ceiling before mutation; the first-worker completion gate can no longer pass.; replacement: prove-repaired-first-pass-code-test-campaign-on-linux
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 3
Milestone: M11-LINUX-FIRST-PASS-PROOF
Unlocks Gate: none

## Request

Select one small useful code-and-focused-test improvement in the maintained Tool Shed workspace. Start it through ts: next --app-server with no manually authored execution capsule. The automatic preparation must select exact source/test paths and a deterministic verifier whose output fits the declared limit. Capture source binding, preparation and execution usage, turns, tool-result bytes, journal, and exactly-once verification. Complete only if the first worker attempt verifies within default budgets and changes only declared paths. Do not publish, synchronize skills, upgrade clients, or run the full suite.

## App Server Preparation Contract

```json
{
  "campaign_id": "prove-first-pass-code-test-campaign-on-linux",
  "completion_evidence": "The code/test proof contributes passing evidence to G11 with scoped output, first-attempt execution, and exactly-once verification.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "A fresh bounded code-and-test campaign completes from one App Server command without preparation repair after launch.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## App Server Execution Capsule

```json
{
  "camp": "reject-duplicate-provider-identifiers",
  "campaign_id": "prove-first-pass-code-test-campaign-on-linux",
  "context_files": [
    "AGENTS.md"
  ],
  "estimated_max_tool_result_bytes": 8192,
  "estimated_model_turns": 2,
  "execution_shape": "atomic",
  "expected_paths": [
    "scripts/check_provider_adapters.py",
    "tests/test_check_provider_adapters.py"
  ],
  "prompt": "Implement one small provider-portability improvement: harden scripts/check_provider_adapters.py so the provider manifest's existing identifier structure rejects duplicate provider identifiers before later validation. Preserve current behavior for valid manifests and the existing CLI contract. Produce a deterministic, concise failure that identifies the duplicate identifier without emitting a broad manifest dump or traceback. Inspect the declared source to follow its current parsing, validation, and error conventions; do not redesign unrelated validation.\n\nAdd tests/test_check_provider_adapters.py using the standard-library unittest framework. Cover the duplicate-identifier failure and a valid-manifest control closely enough to demonstrate that the new guard does not reject valid input. Keep fixtures temporary and minimal, make the test file directly executable, and avoid network or environment-dependent behavior.\n\nYou may mutate only scripts/check_provider_adapters.py and tests/test_check_provider_adapters.py. Preserve all pre-existing changes and do not perform unrelated cleanup. Do not modify campaign or lifecycle state, work/00-campaigns, indexes, Tool Shed snapshot/install/update machinery, Git metadata, deployment or production configuration, credentials, generated evidence, or any other path. Do not publish, synchronize skills, upgrade clients, access the network, alter protected environment state, or run the full test suite.\n\nVerification is reserved for the orchestrator and must occur exactly once after implementation. Do not run tests, syntax checks, diff checks, or any other verification command yourself. After completing the bounded edits, respond with camp_ready_for_verification and a concise summary of the two changed paths.",
  "schema_version": 1,
  "source_state_token": "7688e791a5f53e48",
  "verification_commands": [
    [
      "/usr/bin/python3",
      "tests/test_check_provider_adapters.py",
      "-q"
    ]
  ]
}
```

## Completion Check

The code/test proof contributes passing evidence to G11 with scoped output, first-attempt execution, and exactly-once verification.
