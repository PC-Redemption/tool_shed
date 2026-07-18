# Work

Project-specific work artifacts live here.

Use `tool_shed/selection.md` before choosing an artifact type.
Use `work/index.md` as the first orientation surface after README/docs. Use `work/index.json` for automation.

## Active

- Project maps: `work/maps/`
- Workpackages: `work/wp/active/`
- Tickets: `work/tickets/`
- Spikes: `work/spikes/`
- Checklists: `work/checklists/`

## Durable Records

- ADRs: `work/adr/`
- Incidents: `work/incidents/`
- Runbooks: `work/runbooks/`
- Inventories: `work/inventories/`
- Decisions: `work/decisions/`

## Rule

Completed work artifacts are history. Settled truth belongs in `docs/` or `README.md`.

Run `python tool_shed/scripts/update_work_index.py --workspace .` after creating, moving, or completing artifacts.
Use `python tool_shed/scripts/complete_workpackage.py work/wp/active/wp-example.md --workspace .` to move active workpackages to completed.
Run `python tool_shed/scripts/check_stale_paths.py --workspace .` after moving or completing artifacts.
Use `python3` on Linux/macOS when that is your configured Python 3 launcher.
