from __future__ import annotations

from pathlib import Path

from campaign_queue import ensure_tree as ensure_campaign_tree


WORK_DIRS = [
    "work/maps",
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

## Campaigns

- Read `work/00-campaigns/active-queue.md` for the owner-facing execution order.
- Durable campaign requests move through `active/`, `completed/`, `deferred/`, and `abandoned/`.
- Keep `work/01-q&a/ask.txt` as transient intake; it is not the durable queue.
- Use `python3 tool_shed/scripts/campaign_queue.py --workspace . status` to get the current stale-write token before a lifecycle mutation.

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
