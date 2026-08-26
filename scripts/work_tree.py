from __future__ import annotations

from pathlib import Path

from campaign_queue import ensure_tree as ensure_campaign_tree


WORK_DIRS = [
    "work/ideas",
    "work/maps",
    "work/roadmaps",
    "work/wp/active",
    "work/wp/completed",
    "work/tickets",
    "work/adr",
    "work/incidents",
    "work/runbooks",
    "work/spikes",
    "work/checklists",
    "work/inventories",
    "work/decisions",
    "work/evidence",
    "work/evidence/generated",
]


WORK_README = """# Work

Project-specific work artifacts live here.

Use `tool_shed/selection.md` before choosing an artifact type.
Use `work/index.md` as the first orientation surface after README/docs. Use `work/index.json` for automation.

## Project Identity

- `work/tool-shed-project.json` is the stable tracked project identity; preserve it across clones and upgrades.
- Before mutation, run `tool_shed/scripts/project_identity.py --workspace . identity --operation <operation> --json`, surface the target capsule, and pass its operation-specific project binding.
- Treat an outside-root path as `WORKSPACE_MISMATCH`; switch only through an explicit `ts: use` followed by target instruction and skill reload.

## Campaigns

- Read `work/00-campaigns/active-queue.md` for the owner-facing execution order.
- Durable campaign requests move through `active/`, `completed/`, `deferred/`, and `abandoned/`.
- Keep the optional project-specific focus catalog at `work/focus-areas.md`; approve it only after
  evidence-backed discovery, then map every active campaign to a known primary area.
- Use `ts: build focus areas` to inspect existing project sources and present an exact catalog and
  campaign-assignment proposal; it writes only after explicit owner approval.
- Keep `work/01-q&a/ask.txt` as transient intake; it is not the durable queue.
- Use `python3 tool_shed/scripts/campaign_queue.py --workspace . status` to get the current project-bound stale-write token before a lifecycle mutation; pass the matching `--project-binding` too.
- Use `python3 tool_shed/scripts/reconcile_campaign_queue.py --workspace . --json` to inspect queue drift and whole-work coverage while automatically creating or refreshing one Dangler Resolution campaign as the first queued work; add `--dry-run` for read-only inspection, and require an exact approved manifest plus the reported whole-work token for every other write.

## Ideas And Brainstorming

- Keep durable pre-PRM Idea Briefs under `work/ideas/`.
- `ts: brainstorm <idea>` and its exact alias `ts: bs <idea>` create or resume one living Idea Brief.
- Keep a concise current synthesis above dated exploration notes; preserve reminders, alternatives,
  tradeoffs, constraints, open questions, and decisions without forcing every section to be complete.
- Idea Briefs remain outside campaign reconciliation. Use `ts: prm idea <idea-id-or-path>` to carry
  a selected brief into PRM; promotion does not bypass project-map, roadmap, or campaign-plan approval.

## Program Roadmaps

- Keep opt-in Program Roadmaps under `work/roadmaps/` between project maps and campaigns.
- Use `program_roadmap.py develop` and `overview` for read-only discovery.
- Roadmap approval and campaign-plan approval are separate exact-token mutations.
- Installation and upgrade preserve existing work and never create or approve a roadmap implicitly.

## Active

- Idea Briefs: `work/ideas/`
- Project maps: `work/maps/`
- Workpackages: `work/wp/active/`
- Tickets: `work/tickets/`
- Spikes: `work/spikes/`
- Checklists: `work/checklists/`

## Workspace Work-Level Customization

`work/tool-shed.yaml` may add workspace-specific actions around one canonical `work1` through
`work5` endpoint without changing Tool Shed defaults elsewhere. Resolve it before executing a
numbered route with `python3 tool_shed/scripts/work_level_config.py --workspace . resolve work3
--json`. Missing configuration preserves standard behavior. Installation and upgrade preserve an
owner-authored declaration.

## Durable Records

- ADRs: `work/adr/`
- Incidents: `work/incidents/`
- Runbooks: `work/runbooks/`
- Inventories: `work/inventories/`
- Decisions: `work/decisions/`

## Evidence

- Keep human-readable evidence in `work/evidence/**/*.md`.
- Small JSON summaries and manifests may be versioned.
- Put raw captures, dumps, images, large logs, and test payloads in `work/evidence/generated/`.
- Record hashes, timestamps, target identity, command or test IDs, outcomes, and relative artifact paths in a small versioned manifest outside the generated directory.
- `work/evidence/generated/` is ignored by the shared project convention. Use `.git/info/exclude` instead for additional machine-local evidence paths.

## Rule

Completed work artifacts are history. Settled truth belongs in `docs/` or `README.md`.

Run `python3 tool_shed/scripts/update_work_index.py --workspace .` after creating, moving, or completing artifacts.
Use `python3 tool_shed/scripts/complete_workpackage.py work/wp/active/wp-example.md --workspace .` to move active workpackages to completed.
Run `python3 tool_shed/scripts/check_stale_paths.py --workspace .` after moving or completing artifacts.
Run `python3 tool_shed/scripts/review_work_state.py --workspace .` during orientation and regular planning review.
Run `python3 tool_shed/scripts/check_work_tree.py --workspace . --json` after installation or upgrade to verify the canonical work topology.
Run `python3 tool_shed/scripts/workspace_preflight.py --workspace . --json` before long automated
campaigns. Review its workspace profile, policy sources, risk budgets, and mitigations. For
already tracked raw evidence, use `migrate_generated_evidence.py prepare` with an output path
outside the repository; apply requires an exact approved manifest and verified archive.
"""


def ensure_work_tree(workspace: Path) -> None:
    for relative in WORK_DIRS:
        (workspace / relative).mkdir(parents=True, exist_ok=True)
    ensure_campaign_tree(workspace)

    readme = workspace / "work" / "README.md"
    if not readme.exists():
        readme.write_text(WORK_README, encoding="utf-8")
