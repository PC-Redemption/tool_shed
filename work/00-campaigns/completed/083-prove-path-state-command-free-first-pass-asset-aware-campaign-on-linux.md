# Prove path-state command-free asset revision on Linux

Status: complete
Type: campaign
Updated: 2026-08-26
Next Action: none
Campaign ID: prove-path-state-command-free-first-pass-asset-aware-campaign-on-linux
Campaign Number: 083
Outcome: Documentation asset cache revisions cover every direct site asset deterministically through a command-free worker with explicit expected-path starting states.
Primary Focus Areas: provider-portability
Supporting Focus Areas: workspace-safety, campaign-lifecycle
Depends On: prove-path-state-command-free-first-pass-code-test-campaign-on-linux
Decision: none
Detour For: none
Return To: none
Completion Gate: G11-LINUX-FIRST-PASS-RELIABLE passes across documentation plus path-state command-free code/test and asset-aware task shapes.
Completion Evidence: work/evidence/evidence-linux-path-state-command-free-asset-proof.md
Completion Date: 2026-08-26
Completion Order: 69
Disposition: completed
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 7
Milestone: M11-LINUX-FIRST-PASS-PROOF
Unlocks Gate: G11-LINUX-FIRST-PASS-RELIABLE

## Request

Harden the documentation site's asset_revision behavior so its cache revision is derived deterministically from every regular file directly under site/assets, not only the two currently hard-coded asset names. Hash stable relative filenames as well as bytes so rename-only changes alter the revision; ignore directories and keep output at the existing 12 hexadecimal characters. Add focused tests using a temporary asset directory and the production function to prove stable ordering, content changes, rename-only changes, and directory exclusion. Start through ts: next --app-server with no manually authored capsule. Automatic preparation must use metadata-only inventory for site assets, exclude binary or generated payloads from inline context, supply complete bounded text source/test context, a quiet verifier, and explicit expected-path starting states. The write worker must issue no commandExecution; its first completed fileChange must hand off directly to Tool Shed-owned exactly-once verification. Capture source binding, usage, turns, control stop, path-start state, journal, and verification. Complete only on first-worker verification or correct pre-worker reduction. Do not replay Campaigns 074, 076, 079, or 081, publish, synchronize skills, upgrade clients, or run the full suite.

## App Server Preparation Contract

```json
{
  "campaign_id": "prove-path-state-command-free-first-pass-asset-aware-campaign-on-linux",
  "completion_evidence": "G11-LINUX-FIRST-PASS-RELIABLE passes across documentation plus path-state command-free code/test and asset-aware task shapes.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "Documentation asset cache revisions cover every direct site asset deterministically through a command-free worker with explicit expected-path starting states.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## App Server Execution Capsule

```json
{
  "camp": "generalize-docs-asset-revision",
  "campaign_id": "prove-path-state-command-free-first-pass-asset-aware-campaign-on-linux",
  "context_files": [
    "scripts/build_docs_site.py",
    "tests/test_docs_site.py"
  ],
  "estimated_max_tool_result_bytes": 8192,
  "estimated_model_turns": 1,
  "execution_shape": "atomic",
  "expected_paths": [
    "scripts/build_docs_site.py",
    "tests/test_docs_site.py"
  ],
  "prompt": "Implement the complete campaign request as one atomic, command-free file change.\n\nObjective: Harden the documentation site's production asset_revision behavior so its existing 12-character lowercase hexadecimal cache revision is derived deterministically from every regular file directly under site/assets, rather than from hard-coded asset names. Include each file's stable relative filename and bytes in the hash so a rename with unchanged content changes the revision. Process files in deterministic filename order and ignore directories and their contents. Use unambiguous filename/content framing so distinct filename-and-byte sequences cannot be conflated.\n\nTests: In tests/test_docs_site.py, add focused tests that call the production asset_revision function with temporary asset directories and prove: creation/insertion ordering does not affect the result; changing file content changes it; renaming a file without changing its bytes changes it; and directories, including files nested inside them, are excluded. Preserve assertions that the result remains exactly 12 lowercase hexadecimal characters. Keep tests independent of the real site asset payloads.\n\nAuthoritative supplied context consists of scripts/build_docs_site.py and tests/test_docs_site.py at dispatch-time source freshness. The site/assets inventory is metadata-only; asset payloads are intentionally absent and must not be requested or embedded. Do not reread supplied files through command output.\n\nExpected-path starting states: scripts/build_docs_site.py and tests/test_docs_site.py both exist as regular UTF-8 repository files and their exact dispatch-time contents are supplied inline. Preparation observed a clean worktree, but dispatcher-owned capsule and lifecycle changes may already exist during execution; do not inspect, alter, or make claims about overall Git cleanliness.\n\nMutation boundary: modify only scripts/build_docs_site.py and tests/test_docs_site.py. Make exactly one completed fileChange covering both paths. Do not create, delete, rename, or modify any other path. Do not touch work/00-campaigns, Tool Shed lifecycle or snapshot machinery, Git metadata, deployment or production configuration, credentials, protected environment state, generated outputs, or unrelated cleanup.\n\nControl boundary: commandExecution is forbidden at every point. Do not run tests, Git, shell commands, Python, formatters, searches, or file-listing commands. Do not use the network, request approvals, expand permissions, publish, synchronize skills, upgrade clients, replay earlier campaigns, or perform campaign lifecycle transitions. The orchestrator exclusively owns source binding, usage and turn accounting, the control stop, expected-path and mutation journals, and exactly-once verification.\n\nIf the supplied source and test context is insufficient to make this exact bounded change safely, return unknown without any mutation. Otherwise perform the source and test edits together in the first and only completed fileChange, then stop immediately and return camp_ready_for_verification. That first completed fileChange is the direct handoff to Tool Shed-owned exactly-once verification; do not issue another tool call or attempt verification yourself.",
  "schema_version": 1,
  "source_state_token": "0d02211aaaa57dd0",
  "verification_commands": [
    [
      "/usr/bin/python3",
      "-m",
      "unittest",
      "discover",
      "-s",
      "tests",
      "-p",
      "test_docs_site.py",
      "-q"
    ]
  ]
}
```

## Completion Check

G11-LINUX-FIRST-PASS-RELIABLE passes across documentation plus path-state command-free code/test and asset-aware task shapes.
