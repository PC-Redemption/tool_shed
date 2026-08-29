# Decision Matrix: Plugin packaging readiness

Status: decided
Type: decision-matrix
Updated: 2026-07-05
Next Action: defer plugin packaging until distribution friction appears
Parent: work/maps/map-tool-shed-foundation.md

## Decision

Should `tool_shed` be packaged as a plugin now, after creating the repo-local and installed local `tool-shed` skill?

## Options

| Option | Pros | Cons | Risk | Pick |
| --- | --- | --- | --- | --- |
| Keep repo-local plus installed local skill | Matches current use; avoids new packaging layer | Not one-click portable across machines | Manual install/copy remains needed | Yes |
| Create plugin now | Bundles skill/install story for distribution | Adds manifest/cache/install workflow before need is proven | Plugin may freeze still-evolving assumptions | No |
| Wait for real distribution friction | Lets actual use define plugin requirements | Requires revisiting later | Slight delay when portability becomes urgent | Yes |
| Bundle full `tool_shed` into skill/plugin | Most portable | Duplicates source of truth | Drift between repo and package | No |

## Recommendation

Defer plugin packaging.

Field tests using real project clones showed that repo-local plus installed local skill packaging is enough for current use:

- `/tmp/tool-shed-field-lottery`
- `/tmp/tool-shed-field-plex-cleanup`

Each test used a workspace with `tool_shed/` present and produced only the expected Level 2 artifacts:

- `work/README.md`
- one project map
- one existing-project inventory

Plugin packaging should be reconsidered when one of these becomes true:

- the shed needs one-command install/update across multiple machines
- users beyond this local environment need the skill and scripts together
- versioned plugin releases become important
- local repo copying/linking becomes repetitive or error-prone

Until then, keep `tool_shed` as plain files/scripts plus a thin Codex skill.
