# Prove repaired first-pass code and test preparation on Linux

Status: abandoned
Type: campaign
Updated: 2026-08-26
Next Action: none
Campaign ID: prove-repaired-first-pass-code-test-campaign-on-linux
Campaign Number: 075
Outcome: A fresh bounded code-and-test campaign completes from one App Server command with expected source supplied inline and bounded worker inspection.
Primary Focus Areas: provider-portability
Supporting Focus Areas: campaign-lifecycle, workspace-safety
Depends On: prove-first-pass-documentation-campaign-on-linux
Decision: none
Detour For: none
Return To: none
Completion Gate: The replacement code/test proof contributes passing evidence to G11 with first-worker execution, scoped output, and exactly-once verification.
Completion Evidence: none
Disposition: First worker reached the fourth model request after authorized mutation and reserved verification then failed during reconciliation; first-worker correctness cannot pass and the worker is not replayed.; replacement: prove-mutation-first-code-test-campaign-on-linux
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 4
Milestone: M11-LINUX-FIRST-PASS-PROOF
Unlocks Gate: none

## Request

Select one small useful code-and-focused-test improvement in the maintained Tool Shed workspace. Start it through ts: next --app-server with no manually authored execution capsule. Automatic preparation must select exact source/test paths, inject every existing expected UTF-8 source that fits the context budget, and choose a deterministic verifier whose output fits the declared limit. The worker must not reread supplied files and every inspection command must remain below 12,288 serialized bytes. Capture source binding, preparation and execution usage, turns, tool-result bytes, journal, and exactly-once verification. Complete only if the first worker attempt verifies within default budgets and changes only declared paths. Do not resume or replay Campaign 073, publish, synchronize skills, upgrade clients, or run the full suite.

## App Server Preparation Contract

```json
{
  "campaign_id": "prove-repaired-first-pass-code-test-campaign-on-linux",
  "completion_evidence": "The replacement code/test proof contributes passing evidence to G11 with first-worker execution, scoped output, and exactly-once verification.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "A fresh bounded code-and-test campaign completes from one App Server command with expected source supplied inline and bounded worker inspection.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## App Server Execution Capsule

```json
{
  "camp": "harden-provider-adapter-path-validation",
  "campaign_id": "prove-repaired-first-pass-code-test-campaign-on-linux",
  "context_files": [
    "adapters/providers.json",
    "scripts/check_provider_adapters.py"
  ],
  "estimated_max_tool_result_bytes": 8192,
  "estimated_model_turns": 2,
  "execution_shape": "atomic",
  "expected_paths": [
    "scripts/check_provider_adapters.py",
    "tests/test_check_provider_adapters_paths.py"
  ],
  "prompt": "Implement one atomic provider-portability improvement in the maintained Tool Shed workspace: harden scripts/check_provider_adapters.py so every provider-declared filesystem path accepted by the existing manifest schema is a portable repository-relative POSIX path. Preserve the current schema and valid behavior. Reject POSIX absolute paths, Windows drive-rooted or UNC paths, backslash-separated paths, and paths containing parent-traversal components. Produce deterministic validation errors that identify the provider and relevant field. Add focused stdlib unittest coverage in tests/test_check_provider_adapters_paths.py for valid nested relative paths and each rejected path class, including Windows-shaped inputs while running on Linux.\n\nThe current UTF-8 contents of scripts/check_provider_adapters.py and adapters/providers.json are supplied inline by automatic preparation. Use those supplied contents as the authoritative source snapshot. Do not run commands that reread either supplied file, and do not inspect unrelated repository files. You may mutate only scripts/check_provider_adapters.py and tests/test_check_provider_adapters_paths.py. Do not change campaign or lifecycle files, queues, roadmaps, evidence, indexes, Tool Shed snapshot/install/update machinery, generated outputs, Git metadata, deployment or production configuration, credentials, or any other path. Do not use network access, publish, synchronize skills, upgrade clients, resume or replay Campaign 073, or run tests or other verification commands. Verification is reserved for the orchestrator and will run exactly once after implementation. Keep command output and every inspection result below 12,288 serialized bytes. After making the bounded implementation and focused tests, report the changed paths and finish with the exact marker camp_ready_for_verification.",
  "schema_version": 1,
  "source_state_token": "419776b4db1e59ae",
  "verification_commands": [
    [
      "/usr/bin/python3",
      "-m",
      "unittest",
      "discover",
      "-s",
      "tests",
      "-p",
      "test_check_provider_adapters_paths.py"
    ]
  ]
}
```

## Completion Check

The replacement code/test proof contributes passing evidence to G11 with first-worker execution, scoped output, and exactly-once verification.
