# Prove command-free first-pass code and test preparation on Linux

Status: abandoned
Type: campaign
Updated: 2026-08-26
Next Action: none
Campaign ID: prove-command-free-first-pass-code-test-campaign-on-linux
Campaign Number: 078
Outcome: A fresh bounded code-and-test campaign completes from one App Server command through the command-free first-file-change handoff.
Primary Focus Areas: provider-portability
Supporting Focus Areas: campaign-lifecycle, workspace-safety
Depends On: prove-first-pass-documentation-campaign-on-linux, establish-deterministic-app-server-worker-handoff
Decision: none
Detour For: none
Return To: none
Completion Gate: The command-free code/test proof contributes passing evidence to G11 with one file-change handoff, no worker shell, and exactly-once verification.
Completion Evidence: none
Disposition: The first command-free worker correctly returned unknown because the generic proof request let automatic preparation invent an integration point absent from supplied source; no mutation or replay occurred. See work/evidence/evidence-linux-command-free-code-proof-underspecified.md.; replacement: prove-specified-command-free-first-pass-code-test-campaign-on-linux
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 5
Milestone: M11-LINUX-FIRST-PASS-PROOF
Unlocks Gate: none

## Request

Select one small useful code-and-focused-test improvement in the maintained Tool Shed workspace. Start it through ts: next --app-server with no manually authored capsule. Automatic preparation must provide complete bounded source context, exact expected paths, and a quiet verifier. The write worker must issue no commandExecution; its first completed fileChange must be interrupted into Tool Shed-owned exactly-once verification without a final model handoff request. Capture source binding, preparation and execution usage, turns, control stop, journal, and verification. Complete only if the first worker verifies within default budgets and changes only declared paths. Do not replay Campaigns 073 or 075, publish, synchronize skills, upgrade clients, or run the full suite.

## App Server Preparation Contract

```json
{
  "campaign_id": "prove-command-free-first-pass-code-test-campaign-on-linux",
  "completion_evidence": "The command-free code/test proof contributes passing evidence to G11 with one file-change handoff, no worker shell, and exactly-once verification.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "A fresh bounded code-and-test campaign completes from one App Server command through the command-free first-file-change handoff.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## App Server Execution Capsule

```json
{
  "camp": "portable-provider-executable-name-matching",
  "campaign_id": "prove-command-free-first-pass-code-test-campaign-on-linux",
  "context_files": [
    "AGENTS.md",
    "adapters/providers.json",
    "scripts/provider_adapters.py"
  ],
  "estimated_max_tool_result_bytes": 4096,
  "estimated_model_turns": 1,
  "execution_shape": "atomic",
  "expected_paths": [
    "scripts/provider_adapters.py",
    "tests/test_provider_adapters.py"
  ],
  "prompt": "Implement one bounded provider-portability improvement using only the supplied inline source context. In scripts/provider_adapters.py, add and integrate a pure executable-name normalization rule wherever configured provider executable names or command heads are matched: accept either POSIX or Windows path separators, compare basenames case-insensitively, and remove at most one trailing .exe suffix before comparison. Preserve existing provider selection, configuration validation, and CLI behavior otherwise. Add tests/test_provider_adapters.py using the standard library unittest framework. Cover at minimum: /usr/bin/codex matching codex; a Windows-style path ending in CODEX.EXE matching codex; and codex-helper remaining distinct from codex. Tests must exercise the matching behavior used by provider selection, not merely duplicate the normalization algorithm in test code.\n\nThe only authorized mutations are scripts/provider_adapters.py and tests/test_provider_adapters.py. Apply all code and test edits in exactly one completed fileChange operation; Tool Shed will interrupt immediately after that first completed fileChange and run reserved verification exactly once. Do not issue commandExecution or invoke a shell, Python, tests, Git, search, file listing, network access, or any other command at any point. Do not reread files through command output; the required source is supplied inline. Do not mutate campaign or lifecycle state, work/00-campaigns, snapshot or skill machinery, Git metadata, generated evidence, deployment or production configuration, credentials, protected environment state, or any undeclared path. Do not publish, synchronize skills, upgrade clients, perform unrelated cleanup, or request a final model handoff. Verification belongs exclusively to the orchestrator. If the supplied source does not contain a safe provider-executable matching integration point, if the requested behavior already exists completely, or if all edits cannot be completed safely in the single fileChange, return unknown without mutation. After the single implementation fileChange, report camp_ready_for_verification without further tool use.",
  "schema_version": 1,
  "source_state_token": "6b3ecd7dba239608",
  "verification_commands": [
    [
      "/usr/bin/python3",
      "-m",
      "unittest",
      "discover",
      "-s",
      "tests",
      "-p",
      "test_provider_adapters.py",
      "-q"
    ]
  ]
}
```

## Completion Check

The command-free code/test proof contributes passing evidence to G11 with one file-change handoff, no worker shell, and exactly-once verification.
