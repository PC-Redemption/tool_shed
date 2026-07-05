# Project Map: tool_shed foundation

Status: active
Type: project-map
Updated: 2026-07-05
Next Action: decide routing for observed facts versus settled docs

## Purpose

Navigate `tool_shed` foundation work from the broad goal down to the next concrete edit, especially when the project has enough moving parts that text-only planning becomes hard to hold in working memory.

## Visual Map

```mermaid
flowchart TD
  A[Reusable Codex workbench] --> B[Artifact selection]
  A --> C[Artifact composition]
  A --> D[Visual coordination]
  A --> E[Workspace installation]
  A --> F[Existing project onboarding]
  A --> G[Future Codex skill]

  B --> H[selection.md]
  C --> I[templates with parent links]
  D --> J[project maps]
  D --> K[decision: map creation trigger]
  E --> L[scripts/install_into_workspace.py]
  E --> M[scripts/new_artifact.py]
  F --> N[wp: existing project onboarding and backfill]
  G --> O[ticket: add skill after foundation stabilizes]

  N --> P[Ground: decide facts vs docs routing]
```

## Zoom Levels

30,000 ft:

- Overall outcome: `tool_shed` is a reusable collaboration toolkit for structured Codex work.
- Success shape: Codex can pick the right artifact, compose artifacts across a large effort, and keep project state visible without turning the shed into a server or task tracker.

10,000 ft:

- Major workstreams: artifact selection, artifact composition, visual coordination, workspace installation, existing project onboarding, future Codex skill.
- Key dependencies: stabilize local Markdown/scripts before packaging behavior into a Codex skill.

1,000 ft:

- Active workpackages: `work/wp/active/wp-existing-project-onboarding-and-backfill.md`.
- Active tickets: `work/tickets/ticket-add-codex-skill-after-foundation-stabilizes.md`.
- Open decisions: whether project maps need generated indexes, rendered diagrams, or stay plain Markdown/Mermaid for now.

Ground:

- Current next action: decide which discovered facts become `work/` artifacts versus settled `docs/` or README updates.
- Owner/context: Codex and human working in `/home/jon/docker/tool_shed`.
- Verification: script syntax checks pass and generated map artifacts land under `work/maps/`.

## Workstreams

| Workstream | Status | Lead Artifact | Depends On | Next Action |
| --- | --- | --- | --- | --- |
| Artifact selection | active | `selection.md` | none | Keep examples aligned with real use |
| Artifact composition | active | `conventions.md` | stable artifact headers | Validate parent links in templates |
| Visual coordination | active | `templates/project-map.md` | Mermaid/plain Markdown viability | Use threshold trigger rule |
| Workspace installation | active | `scripts/install_into_workspace.py` | directory convention stability | Keep generated `work/README.md` aligned |
| Existing project onboarding | active | `work/wp/active/wp-existing-project-onboarding-and-backfill.md` | map trigger rule | Decide facts vs docs routing |
| Future Codex skill | deferred | `work/tickets/ticket-add-codex-skill-after-foundation-stabilizes.md` | foundation stability | Design only after conventions settle |

## Dependency Notes

- Existing project onboarding should be solved before the Codex skill so the skill can consistently learn and backfill real projects.
- The Codex skill should wait until artifact selection, composition, visual coordination, and onboarding/backfill have settled.
- Project maps should stay light enough to remain useful as a navigation surface, not become a second project management system.
- Templates should support links between artifacts, but detailed work should remain in the artifact that fits it best.

## Current Navigation

You are here:

- Deciding how project maps get created and how existing projects get learned/backfilled.

Do next:

- [x] Validate `project-map` creation through `new_artifact.py`.
- [x] Confirm installer creates `work/maps/`.
- [x] Draft `work/decisions/decision-project-map-creation-trigger.md`.
- [x] Define backfill levels in `work/wp/active/wp-existing-project-onboarding-and-backfill.md`.
- [x] Design the Level 2 existing-project onboarding workflow.
- [x] Test Level 2 onboarding on an existing project clone.
- [x] Decide whether Level 2 onboarding needs helper automation.
- [x] Test `scripts/onboard_existing_project.py` on an existing project clone.
- [ ] Decide which discovered facts become `work/` artifacts versus settled `docs` or README updates.

Avoid for now:

- Do not build a server, database, renderer, or heavyweight tracker before plain Markdown and scripts fail.
- Do not add the Codex skill until the foundation is stable.

## Related Artifacts

- Workpackages: `work/wp/active/wp-existing-project-onboarding-and-backfill.md`
- Tickets: `work/tickets/ticket-add-codex-skill-after-foundation-stabilizes.md`
- Checklists:
- Spikes:
- ADRs:
- Runbooks:
- Inventories:
- Decision matrices: `work/decisions/decision-project-map-creation-trigger.md`, `work/decisions/decision-level-2-onboarding-helper-automation.md`
