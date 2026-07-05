# Decision Matrix: Codex skill readiness

Status: decided
Type: decision-matrix
Updated: 2026-07-05
Next Action: use skill on real projects and evaluate plugin packaging later
Parent: work/maps/map-tool-shed-foundation.md

## Decision

Is `tool_shed` ready to be encoded as a Codex skill, and if so, what is the next action?

## Options

| Option | Pros | Cons | Risk | Pick |
| --- | --- | --- | --- | --- |
| Wait for more foundation work | Avoids encoding churn | Delays useful consistency gains | Codex continues relying on chat memory and lessons only | No |
| Design the skill now, create after choosing target | Captures stable behavior without prematurely installing | Requires one more approval/location choice | Small delay before use | Yes |
| Create/install the skill immediately | Fastest path to reusable behavior | Needs target location and validation setup; may skip design review | Skill may encode repo-local assumptions incorrectly | No |
| Bundle all templates/scripts into the skill | Portable without repo checkout | Duplicates `tool_shed` and creates drift | Skill becomes second source of truth | No |

## Recommendation

`tool_shed` is ready for skill design.

Do not bundle the whole shed into the skill. The skill should be a thin adoption/routing layer that teaches Codex to:

- recognize a workspace-local `tool_shed/`
- read `selection.md` and `conventions.md` before choosing artifacts
- read `existing-projects.md` when loading onto an existing project
- prefer the smallest fitting artifact
- use helper scripts when available
- keep project-specific artifacts under `work/`
- promote stable current truth into `docs/` or README files
- avoid duplicating bulky templates or treating work artifacts as canonical truth

Recommended skill shape:

- Skill name: `tool-shed`
- Skill type: local Codex skill, not a plugin yet
- `SKILL.md`: concise routing workflow and boundary rules
- References: optional links/copies for `selection.md`, `conventions.md`, and `existing-projects.md` only if the skill is meant to work without a local `tool_shed/`
- Scripts/assets: none at first; use workspace-local scripts instead

Readiness result:

- Foundation behavior is stable enough to design the skill.
- Created both selected targets: repo-local package at `skills/tool-shed` and installed local copy at `/home/jon/.codex/skills/tool-shed`.
- Plugin packaging is deferred until real use shows it is needed.
- Validation should include at least one workspace with `tool_shed/` and one existing-project Level 2 onboarding scenario.
