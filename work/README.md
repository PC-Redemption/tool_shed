# Work

Project-specific work artifacts live here.

Use `tool_shed/selection.md` before choosing an artifact type.
Use `work/index.md` as the first orientation surface after README/docs. Use `work/index.json` for automation.

## Project Identity

- `work/tool-shed-project.json` is this project's stable tracked identity; preserve it across clones and upgrades.
- Before mutation, run `python3 scripts/project_identity.py --workspace . identity --operation <operation> --json`, surface the target capsule, and pass its operation-specific project binding.
- Treat an outside-root path as `WORKSPACE_MISMATCH`; switch only through an explicit `ts: use` followed by target instruction and skill reload.

## Campaigns

- Read `work/00-campaigns/active-queue.md` for the owner-facing execution order.
- Durable campaign requests move through `active/`, `completed/`, `deferred/`, and `abandoned/`.
- Keep `work/01-q&a/ask.txt` as transient intake; it is not the durable queue.
- Use `python3 scripts/campaign_queue.py --workspace . status` to get the current project-bound stale-write token before a lifecycle mutation; pass the matching `--project-binding` too.
- Use `python3 scripts/reconcile_campaign_queue.py --workspace . --json` to inspect queue drift and whole-work coverage while automatically creating or refreshing one Dangler Resolution campaign as the first queued work; add `--dry-run` for read-only inspection, and require an exact approved manifest plus the reported whole-work token for every other write.

## Program Roadmaps

- Keep opt-in Program Roadmaps under `work/roadmaps/` between project maps and campaigns.
- Use `python3 scripts/program_roadmap.py --workspace . develop --json` and `overview --json` for read-only discovery.
- Roadmap approval and campaign-plan approval are separate exact-token mutations.
- Installation and upgrade preserve existing work and never create or approve a roadmap implicitly.

## Active

- Project maps: `work/maps/`
- Program Roadmaps: `work/roadmaps/`
- Workpackages: `work/wp/active/`
- Tickets: `work/tickets/`
- Spikes: `work/spikes/`
- Checklists: `work/checklists/`

## Workspace Work-Level Customization

`work/tool-shed.yaml` may add workspace-specific actions around one canonical `work1` through
`work5` endpoint without changing Tool Shed defaults elsewhere. Validate or resolve it with:

```bash
python3 scripts/work_level_config.py --workspace . resolve work3 --json
```

Installed snapshots use `tool_shed/scripts/work_level_config.py`. Missing configuration preserves
standard behavior. The installer and updater preserve an existing owner-authored declaration.

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
Run `python3 scripts/check_work_tree.py --workspace . --json` after structural changes to verify the canonical work topology.
