# Prove first-pass documentation preparation on Linux

Status: complete
Type: campaign
Updated: 2026-08-26
Next Action: none
Campaign ID: prove-first-pass-documentation-campaign-on-linux
Campaign Number: 072
Outcome: A fresh useful documentation campaign completes from one App Server command using automatically prepared current collateral.
Primary Focus Areas: provider-portability
Supporting Focus Areas: campaign-lifecycle
Depends On: make-app-server-collateral-correct-before-worker-launch
Decision: none
Detour For: none
Return To: none
Completion Gate: The documentation proof contributes passing evidence to G11 with no manual capsule repair, replay, or preventable reconciliation.
Completion Evidence: First worker attempt verified README.md exactly once with one expected path, no unexpected paths, no replay, source-bound automatic capsule, preparation 29,900 input tokens/1 turn, execution 61,032 input tokens/3 turns; one pre-worker output-risk false positive was repaired in shared validation without capsule editing or mutation.
Completion Date: 2026-08-26
Completion Order: 66
Disposition: completed
Roadmap: low-token-cross-platform-campaign-execution
Roadmap Revision: 3
Milestone: M11-LINUX-FIRST-PASS-PROOF
Unlocks Gate: none

## Request

Select one small useful documentation correction in the maintained Tool Shed workspace that has an exact path and focused assertion. Start it through ts: next --app-server with no manually authored execution capsule. Capture preparation source binding, preparation and execution usage, turns, tool-result bytes, journal, and exactly-once verification. Complete only if the first worker attempt verifies within default budgets and changes only declared paths. Repair any shared preparation defect in the owning M10 implementation before retrying this proof; do not edit the proof capsule manually, publish, synchronize skills, or run the full suite.

## App Server Preparation Contract

```json
{
  "campaign_id": "prove-first-pass-documentation-campaign-on-linux",
  "completion_evidence": "The documentation proof contributes passing evidence to G11 with no manual capsule repair, replay, or preventable reconciliation.",
  "exact_resolution": "dispatch-time",
  "execution_shape": "single-bounded-camp",
  "inline_assets": "metadata-only",
  "objective": "A fresh useful documentation campaign completes from one App Server command using automatically prepared current collateral.",
  "schema_version": 1,
  "source_freshness": "required",
  "verification": "orchestrator-exactly-once"
}
```

## App Server Execution Capsule

```json
{
  "camp": "correct-readme-provider-portability-term",
  "campaign_id": "prove-first-pass-documentation-campaign-on-linux",
  "context_files": [],
  "estimated_max_tool_result_bytes": 2048,
  "estimated_model_turns": 1,
  "execution_shape": "atomic",
  "expected_paths": [
    "README.md"
  ],
  "prompt": "Implement one focused documentation correction in README.md. Inspect the existing introductory sentence that describes `tool_shed` as a \"provider-neutral collaboration toolkit\" and replace only the term \"provider-neutral\" with \"provider-portable\" so the introduction accurately reflects the documented provider-specific adapters and portable artifact model. Preserve all other wording and formatting. You may mutate only README.md; do not modify campaign or lifecycle artifacts, work/00-campaigns, Tool Shed snapshot or skill machinery, tests, generated outputs, Git metadata, deployment or production configuration, credentials, or any other path. Do not use network services, publish, deploy, synchronize skills, install software, or perform protected-environment work. Do not run verification commands or tests because verification is reserved for the orchestrator. After making the implementation and confirming that no other worker-owned edits were made, respond with camp_ready_for_verification and a concise summary.",
  "schema_version": 1,
  "source_state_token": "17908fed82ff6c91",
  "verification_commands": [
    [
      "/usr/bin/python3",
      "-c",
      "from pathlib import Path\ntext = Path('README.md').read_text(encoding='utf-8')\nexpected = '`tool_shed` is a provider-portable collaboration toolkit for structured work with AI agents.'\nobsolete = '`tool_shed` is a provider-neutral collaboration toolkit for structured work with AI agents.'\nassert text.count(expected) == 1, 'expected corrected introductory sentence exactly once'\nassert obsolete not in text, 'obsolete provider-neutral introductory sentence remains'"
    ]
  ]
}
```

## Completion Check

The documentation proof contributes passing evidence to G11 with no manual capsule repair, replay, or preventable reconciliation.
