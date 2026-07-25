from __future__ import annotations

from pathlib import Path


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
Run `python3 tool_shed/scripts/workspace_preflight.py --workspace .` before long automated campaigns.
"""


def ensure_work_tree(workspace: Path) -> None:
    for relative in WORK_DIRS:
        (workspace / relative).mkdir(parents=True, exist_ok=True)

    readme = workspace / "work" / "README.md"
    if not readme.exists():
        readme.write_text(WORK_README, encoding="utf-8")
