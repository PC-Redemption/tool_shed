# Prove path-state command-free provider validation on Linux

Status: complete
Type: campaign
Updated: 2026-08-26
Next Action: none
Campaign ID: prove-path-state-command-free-first-pass-code-test-campaign-on-linux
Campaign Number: 082
Outcome: Provider adapter instruction paths are validated identically on Linux and Windows through a command-free worker that receives explicit expected-path starting states.
Primary Focus Areas: provider-portability
Supporting Focus Areas: campaign-lifecycle, workspace-safety
Depends On: prove-first-pass-documentation-campaign-on-linux, establish-deterministic-app-server-worker-handoff
Decision: none
Detour For: none
Return To: none
Completion Gate: The path-state code/test proof contributes passing evidence to G11 with one file-change handoff, no worker shell, explicit creation state, and exactly-once verification.
Completion Evidence: work/evidence/evidence-linux-path-state-command-free-code-proof.md
Completion Date: 2026-08-26
Completion Order: 68
Disposition: completed
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 7
Milestone: M11-LINUX-FIRST-PASS-PROOF
Unlocks Gate: none

## Request

Harden the existing provider adapter safe-relative-path validation so manifest instruction paths remain repository-relative on both Linux and Windows. The current helper uses host Path semantics and can accept root-like dot paths or Windows-style backslash traversal when running on Linux. Preserve valid POSIX repository-relative paths, reject empty or dot/root paths, reject parent traversal with either slash style, reject POSIX absolute paths, Windows drive-absolute paths, UNC paths, and backslash-containing manifest paths, and add focused standard-library unittest coverage that calls the production validation behavior. Start through ts: next --app-server with no manually authored capsule. Automatic preparation must resolve exact paths, complete bounded context, a quiet verifier, and the worker handoff must explicitly identify existing files and absent authorized creation targets. The write worker must issue no commandExecution; its first completed fileChange must hand off directly to Tool Shed-owned exactly-once verification. Capture source binding, usage, turns, control stop, path-start state, journal, and verification. Complete only if the first worker verifies within default budgets and changes only declared paths. Do not replay Campaigns 073, 075, 078, or 080, publish, synchronize skills, upgrade clients, or run the full suite.

## App Server Preparation Contract

```json
{
  "campaign_id": "prove-path-state-command-free-first-pass-code-test-campaign-on-linux",
  "completion_evidence": "The path-state code/test proof contributes passing evidence to G11 with one file-change handoff, no worker shell, explicit creation state, and exactly-once verification.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "Provider adapter instruction paths are validated identically on Linux and Windows through a command-free worker that receives explicit expected-path starting states.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## App Server Execution Capsule

```json
{
  "camp": "harden-provider-instruction-path-validation",
  "campaign_id": "prove-path-state-command-free-first-pass-code-test-campaign-on-linux",
  "context_files": [
    "scripts/provider_adapters.py"
  ],
  "estimated_max_tool_result_bytes": 4096,
  "estimated_model_turns": 1,
  "execution_shape": "atomic",
  "expected_paths": [
    "scripts/provider_adapters.py",
    "tests/test_provider_adapters.py"
  ],
  "prompt": "Implement the bounded provider instruction-path validation change using only the injected source snapshot. This is an atomic, command-free worker step.\n\nAuthorized mutation paths and required starting states:\n- scripts/provider_adapters.py: existing regular UTF-8 file; modify in place.\n- tests/test_provider_adapters.py: absent; create as a regular UTF-8 file.\n\nSource binding:\n- Treat the injected scripts/provider_adapters.py content as the complete current production source for this step.\n- Do not reread files through command output and do not use commandExecution at any point.\n- If the injected source does not expose a coherent production validation path that can be safely changed and exercised within these two paths, return unknown without mutating either path.\n\nImplementation requirements:\n- Harden the existing provider adapter safe-relative-path validation used for manifest instruction paths so its result is independent of the host operating system.\n- Preserve valid POSIX repository-relative manifest paths.\n- Reject empty paths and paths whose lexical meaning is only the current-directory/root-like dot path, including dot-only spellings.\n- Reject parent traversal components expressed with either slash style.\n- Reject POSIX absolute paths.\n- Reject Windows drive-absolute paths, including drive paths written with forward slashes.\n- Reject UNC paths.\n- Reject every manifest path containing a backslash, even when it would not traverse.\n- Keep validation lexical and command-free; do not resolve against the filesystem.\n- Avoid unrelated refactoring or behavior changes.\n\nFocused tests:\n- Create tests/test_provider_adapters.py using only the Python standard library unittest framework.\n- Exercise the production validation behavior rather than duplicating its logic in the test.\n- Cover representative accepted POSIX repository-relative paths.\n- Cover empty and dot/root-like paths; slash and backslash parent traversal at leading and nested positions; POSIX absolute paths; Windows drive-absolute paths; UNC paths; and ordinary backslash-containing paths.\n- Keep the test deterministic and platform-independent on Linux and Windows.\n\nExecution and control boundary:\n- Make exactly one completed fileChange containing all required edits to both declared paths. The first completed fileChange is the immediate handoff to Tool Shed-owned verification.\n- After that fileChange, issue no further mutation and no commandExecution. Return camp_ready_for_verification.\n- The orchestrator exclusively owns the exactly-once verification command, Git mutation journal, unexpected-path check, lifecycle state, usage/turn accounting, and control-stop evidence.\n- Do not modify campaign lifecycle files, work/00-campaigns, snapshots, skills, clients, Git metadata, deployment or production configuration, credentials, generated outputs, or any undeclared path.\n- Do not access the network, protected environment state, or external services. Do not publish, synchronize skills, upgrade clients, replay prior campaigns, run the full suite, deploy, or perform cleanup.",
  "schema_version": 1,
  "source_state_token": "185931925005e879",
  "verification_commands": [
    [
      "/usr/bin/python3",
      "-m",
      "unittest",
      "-q",
      "tests/test_provider_adapters.py"
    ]
  ]
}
```

## Completion Check

The path-state code/test proof contributes passing evidence to G11 with one file-change handoff, no worker shell, explicit creation state, and exactly-once verification.
