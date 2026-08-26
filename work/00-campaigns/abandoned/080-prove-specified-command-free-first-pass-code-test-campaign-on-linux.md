# Prove specified command-free provider path validation on Linux

Status: abandoned
Type: campaign
Updated: 2026-08-26
Next Action: none
Campaign ID: prove-specified-command-free-first-pass-code-test-campaign-on-linux
Campaign Number: 080
Outcome: Provider adapter instruction paths are validated identically on Linux and Windows, and the fix completes through the command-free first-file-change handoff.
Primary Focus Areas: provider-portability
Supporting Focus Areas: campaign-lifecycle, workspace-safety
Depends On: prove-first-pass-documentation-campaign-on-linux, establish-deterministic-app-server-worker-handoff
Decision: none
Detour For: none
Return To: none
Completion Gate: The specified code/test proof contributes passing evidence to G11 with one file-change handoff, no worker shell, and exactly-once verification.
Completion Evidence: none
Disposition: The first command-free worker stopped without mutation because Tool Shed did not state that the expected test path was absent and authorized for creation. See work/evidence/evidence-linux-specified-code-proof-missing-path-state.md.; replacement: prove-path-state-command-free-first-pass-code-test-campaign-on-linux
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 6
Milestone: M11-LINUX-FIRST-PASS-PROOF
Unlocks Gate: none

## Request

Harden the existing provider adapter safe-relative-path validation so manifest instruction paths remain repository-relative on both Linux and Windows. The current helper uses host Path semantics and can accept root-like dot paths or Windows-style backslash traversal when running on Linux. Preserve valid POSIX repository-relative paths, reject empty or dot/root paths, reject parent traversal with either slash style, reject POSIX absolute paths, Windows drive-absolute paths, UNC paths, and backslash-containing manifest paths, and add focused standard-library unittest coverage that calls the production validation behavior. Start through ts: next --app-server with no manually authored capsule. Automatic preparation must resolve exact paths, complete bounded context, and a quiet verifier. The write worker must issue no commandExecution; its first completed fileChange must hand off directly to Tool Shed-owned exactly-once verification. Capture source binding, usage, turns, control stop, journal, and verification. Complete only if the first worker verifies within default budgets and changes only declared paths. Do not replay Campaigns 073, 075, or 078, publish, synchronize skills, upgrade clients, or run the full suite.

## App Server Preparation Contract

```json
{
  "campaign_id": "prove-specified-command-free-first-pass-code-test-campaign-on-linux",
  "completion_evidence": "The specified code/test proof contributes passing evidence to G11 with one file-change handoff, no worker shell, and exactly-once verification.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "Provider adapter instruction paths are validated identically on Linux and Windows, and the fix completes through the command-free first-file-change handoff.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## App Server Execution Capsule

```json
{
  "camp": "harden-provider-instruction-path-validation",
  "campaign_id": "prove-specified-command-free-first-pass-code-test-campaign-on-linux",
  "context_files": [
    "AGENTS.md",
    "adapters/providers.json",
    "scripts/provider_adapters.py",
    "scripts/check_provider_adapters.py"
  ],
  "estimated_max_tool_result_bytes": 4096,
  "estimated_model_turns": 1,
  "execution_shape": "atomic",
  "expected_paths": [
    "scripts/provider_adapters.py",
    "tests/test_provider_adapters.py"
  ],
  "prompt": "Implement the complete atomic provider-path hardening slice using only the deterministically injected context and expected source files. Do not invoke commandExecution or any shell command at any point, and do not reread injected files through command output. Modify exactly scripts/provider_adapters.py and tests/test_provider_adapters.py in one completed atomic fileChange. In the existing production provider-adapter validation path, replace host-dependent Path interpretation with platform-independent validation for manifest instruction paths: preserve valid POSIX repository-relative file paths; reject empty values and paths consisting only of dot/root-like POSIX components (including '.', './', and equivalent repeated-dot forms); reject any parent traversal component whether expressed with forward slashes or backslashes; reject POSIX absolute paths, Windows drive-absolute paths, UNC paths, and every manifest path containing a backslash. Keep the change narrowly scoped to instruction-path safety and retain existing production interfaces and valid behavior. Add focused standard-library unittest coverage in tests/test_provider_adapters.py that imports and calls the production validation behavior rather than duplicating it. Cover representative accepted POSIX repository-relative paths and each required rejected class, including traversal embedded below a directory and Windows forms that are dangerous when evaluated on Linux. Do not modify campaign or lifecycle state, work/00-campaigns, snapshot/update machinery, Git metadata, deployment or production files, credentials, generated evidence, or unrelated code. Do not use network access, protected-environment access, permission expansion, cleanup, publishing, skill synchronization, client upgrades, or Campaigns 073, 075, or 078. The orchestrator exclusively owns verification, source binding, usage and turn accounting, control-stop handling, mutation journaling, and lifecycle decisions; do not run tests or author verification evidence. If the injected boundary is insufficient to safely identify and update the existing production behavior, return unknown without mutation. Otherwise make exactly one completed fileChange containing both declared paths; that first completed fileChange is the direct verification handoff. Issue no further tool call. If control remains for a textual outcome, return camp_ready_for_verification and nothing that requests worker-side verification.",
  "schema_version": 1,
  "source_state_token": "50393da7d3010bd4",
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

The specified code/test proof contributes passing evidence to G11 with one file-change handoff, no worker shell, and exactly-once verification.
