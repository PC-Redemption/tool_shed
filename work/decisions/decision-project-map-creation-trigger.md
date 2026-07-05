# Decision Matrix: Project map creation trigger

Status: active
Type: decision-matrix
Updated: 2026-07-05
Next Action: review recommendation and accept, revise, or reject
Parent: work/maps/map-tool-shed-foundation.md

## Decision

When should `tool_shed` create or recommend a project map instead of relying only on tickets, workpackages, or a work README?

## Options

| Option | Pros | Cons | Risk | Pick |
| --- | --- | --- | --- | --- |
| Always create a project map | Every project has a visual navigation surface from the start | Adds ceremony to small linear tasks | Maps become stale clutter | No |
| Create only on explicit request | No extra artifacts unless the human asks | Codex may miss moments where visual coordination would help | Large projects can drift before anyone asks for a map | No |
| Threshold trigger with human override | Maps appear when complexity makes them useful; human can ask anytime | Requires clear trigger rules | Some borderline cases need judgment | Yes |
| Use only workpackage indexes | Keeps artifact set smaller | Does not serve visual zoom/navigation needs well | Big projects stay text-heavy and harder to orient | No |

## Recommendation

Use a threshold trigger with human override.

Create or recommend a project map when any of these are true:

- the project has two or more active workpackages
- the work spans three or more artifact types
- dependencies or sequencing affect what should happen next
- the user says they are lost, need to see the whole project, or are working from a big-picture idea toward ground tasks
- Codex is loading `tool_shed` into an existing project and needs to learn/backfill the work

Do not create a project map for a single linear task, a small isolated ticket, or a checklist-sized cleanup unless the human asks for a visual map.
