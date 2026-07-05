from __future__ import annotations

import argparse
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
]


WORK_README = """# Work

Project-specific work artifacts live here.

Use `tool_shed/selection.md` before choosing an artifact type.

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
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the project work artifact tree.")
    parser.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Project workspace root. Defaults to current directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.workspace).expanduser().resolve()
    for relative in WORK_DIRS:
        (root / relative).mkdir(parents=True, exist_ok=True)

    readme = root / "work" / "README.md"
    if not readme.exists():
        readme.write_text(WORK_README, encoding="utf-8")

    print(f"Initialized work tree under {root / 'work'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
