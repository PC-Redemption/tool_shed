# Work

Project-specific work artifacts live here.

Use `tool_shed/selection.md` before choosing an artifact type.
Use `work/index.md` as the first orientation surface after README/docs. Use `work/index.json` for automation.

## Campaigns

- Read `work/00-campaigns/active-queue.md` for the owner-facing execution order.
- Durable campaign requests move through `active/`, `completed/`, `deferred/`, and `abandoned/`.
- Keep `work/q&a/ask.txt` as transient intake; it is not the durable queue.
- Use `python3 scripts/campaign_queue.py --workspace . status` to get the current stale-write token before a lifecycle mutation.

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

Run `python3 tool_shed/scripts/update_work_index.py --workspace .` after creating, moving, or completing artifacts.
Use `python3 tool_shed/scripts/complete_workpackage.py work/wp/active/wp-example.md --workspace .` to move active workpackages to completed.
Run `python3 tool_shed/scripts/check_stale_paths.py --workspace .` after moving or completing artifacts.
