# Checklist: tool-shed skill field test

Status: complete
Type: checklist
Updated: 2026-07-05
Next Action: none
Parent: work/maps/map-tool-shed-foundation.md

## Goal

Use the installed `tool-shed` skill workflow against real project clones, then decide whether plugin packaging is justified now or should remain deferred.

## Checklist

- [x] Run Level 2 onboarding through the installed skill workflow on a real project clone with `tool_shed/` present.
- [x] Run Level 2 onboarding through the installed skill workflow on a second real project clone with `tool_shed/` present.
- [x] Confirm the workflow creates only a map, inventory, and work README.
- [x] Confirm generated inventory parent links point at generated maps.
- [x] Record whether repo-local and installed skill packaging are enough for current use.
- [x] Decide whether plugin packaging is needed now.

## Results

- `/tmp/tool-shed-field-lottery` created `work/README.md`, `work/maps/map-lottery.md`, and `work/inventories/inventory-lottery-surfaces.md`.
- `/tmp/tool-shed-field-plex-cleanup` created `work/README.md`, `work/maps/map-plex-cleanup.md`, and `work/inventories/inventory-plex-cleanup-surfaces.md`.
- Both inventories linked to their generated project maps.
- No workpackages, tickets, ADRs, incidents, or runbooks were created.
- Decision: `work/decisions/decision-plugin-packaging-readiness.md`.

## Verification

- [x] `quick_validate.py` passes for repo and installed skill copies.
- [x] Skill copies remain identical.
- [x] `python3 -m py_compile` passes for shed scripts.
- [x] Field-test artifacts in temp clones match Level 2 boundaries.
