# Ticket: Add Codex skill after foundation stabilizes

Status: active
Type: ticket
Updated: 2026-07-05
Next Action: wait for foundation stabilization criteria, then design the skill
Parent: work/maps/map-tool-shed-foundation.md

## Problem

`tool_shed` can make Codex artifact choices more consistent, but only after the local foundation is stable enough to avoid freezing premature conventions into a global skill.

The skill should not become the source of truth for templates or project-specific state. It should act as a thin adoption layer that teaches Codex how to recognize and use a workspace-local `tool_shed/`.

## Expected Behavior

After the foundation stabilizes, add a Codex skill that:

- detects or responds to workspaces that contain `tool_shed/`
- reads `tool_shed/selection.md` and `tool_shed/conventions.md` before choosing an artifact
- prefers the smallest artifact type that fits the work
- uses `tool_shed/scripts/new_artifact.py` when creating artifacts
- keeps project-specific artifacts under `work/`
- treats `docs/` or project README files as the home for settled truth

The skill should reference the local `tool_shed/` files instead of duplicating their full contents.

## Acceptance Criteria

- [ ] Foundation artifact types, templates, scripts, and conventions are stable enough that near-term churn is low.
- [ ] A concise skill design exists with trigger conditions, core workflow, and boundaries.
- [ ] The skill is implemented as a thin routing/adoption layer, not a second copy of `tool_shed`.
- [ ] The skill validates against at least one workspace that already has `tool_shed/`.
- [ ] The skill behavior preserves the boundary: `tool_shed/` creates, `work/` contains, `docs/` canonize, `code/` implements.

## Verification

- In a test workspace containing `tool_shed/`, Codex reads the selection and convention files before creating a planning/documentation artifact.
- For a bounded one-session task, Codex chooses a checklist instead of a workpackage.
- For a specific future enhancement, Codex chooses a ticket with acceptance criteria.
- Generated artifacts are created under `work/`, not under `tool_shed/`.
- The skill does not include bulky template copies that can drift from the repo.
