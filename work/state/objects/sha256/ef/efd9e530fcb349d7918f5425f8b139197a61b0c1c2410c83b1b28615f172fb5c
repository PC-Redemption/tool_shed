# Decision Matrix: Level 2 onboarding helper automation

Status: decided
Type: decision-matrix
Updated: 2026-07-05
Next Action: none
Parent: work/wp/completed/wp-existing-project-onboarding-and-backfill.md

## Decision

Should Level 2 existing-project onboarding stay purely runbook-driven, or should `tool_shed` add helper automation?

## Options

| Option | Pros | Cons | Risk | Pick |
| --- | --- | --- | --- | --- |
| Runbook only | Maximum human/Codex judgment; no extra code | Repeats easy-to-miss setup commands | Inconsistent artifact names and links | No |
| Minimal scaffold helper | Removes setup friction while preserving evidence-based discovery | Adds one script to maintain | Users may think it fills the map/inventory automatically | Yes |
| Auto-discovery helper | Drafts inventory from filesystem quickly | More complex; can overfit repo shapes | False confidence from generated guesses | No |
| Full onboarding engine | Could automate maps, inventories, and recommendations | Violates plain-file/toolkit boundary too early | Becomes a project tracker/server by accident | No |

## Recommendation

Implement a minimal scaffold helper.

The helper should:

- install the standard `work/` tree
- create one project map
- create one existing-project inventory
- set the inventory parent to the generated map path
- print the discovery commands and next manual steps

The helper should not:

- infer project architecture
- create workpackages, tickets, ADRs, incidents, or runbooks
- classify existing planning files
- mutate project docs or code

This keeps Level 2 onboarding consistent while preserving the core rule: learn from observed project evidence before backfilling detailed work.

Implemented as `scripts/onboard_existing_project.py`.
