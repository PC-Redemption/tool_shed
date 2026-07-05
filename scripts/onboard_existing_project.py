from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "untitled"


def render_template(template: str, *, title: str) -> str:
    return (
        template.replace("{{ title }}", title.strip())
        .replace("{{ date }}", date.today().isoformat())
    )


def read_template(shed: Path, relative_path: str) -> str:
    return (shed / relative_path).read_text(encoding="utf-8")


def write_artifact(path: Path, content: str, *, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        raise SystemExit(f"refusing to overwrite existing artifact: {path}")
    path.write_text(content, encoding="utf-8")


def refresh_work_index(workspace: Path, shed: Path) -> None:
    index_script = shed / "scripts" / "update_work_index.py"
    if index_script.exists():
        subprocess.run(
            [sys.executable, str(index_script), "--workspace", str(workspace)],
            check=True,
            stdout=subprocess.DEVNULL,
        )


def ensure_work_tree(workspace: Path) -> None:
    work_dirs = [
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
    for relative in work_dirs:
        (workspace / relative).mkdir(parents=True, exist_ok=True)

    readme = workspace / "work" / "README.md"
    if not readme.exists():
        readme.write_text(
            """# Work

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

Run `python3 tool_shed/scripts/update_work_index.py --workspace .` after creating, moving, or completing artifacts.
Run `python3 tool_shed/scripts/check_stale_paths.py --workspace .` after moving or completing artifacts.
""",
            encoding="utf-8",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scaffold Level 2 onboarding artifacts for an existing project."
    )
    parser.add_argument("title", help="Project name to use for the map and inventory.")
    parser.add_argument("--workspace", default=".", help="Project workspace root. Defaults to current directory.")
    parser.add_argument("--shed", default=None, help="Path to tool_shed. Defaults to this script's parent.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing Level 2 artifacts.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    shed = Path(args.shed).expanduser().resolve() if args.shed else Path(__file__).resolve().parents[1]
    slug = slugify(args.title)

    ensure_work_tree(workspace)

    map_path = workspace / "work" / "maps" / f"map-{slug}.md"
    inventory_path = workspace / "work" / "inventories" / f"inventory-{slug}-surfaces.md"

    map_content = render_template(
        read_template(shed, "templates/project-map.md"),
        title=args.title,
    )
    inventory_content = render_template(
        read_template(shed, "templates/existing-project-inventory.md"),
        title=f"{args.title} surfaces",
    ).replace("Parent: work/maps/...", f"Parent: work/maps/map-{slug}.md")

    write_artifact(map_path, map_content, force=args.force)
    write_artifact(inventory_path, inventory_content, force=args.force)
    refresh_work_index(workspace, shed)

    print(f"Initialized work tree under {workspace / 'work'}")
    print(map_path)
    print(inventory_path)
    print()
    print("Next discovery commands:")
    print("find . -maxdepth 2 -type f -not -path './.git/*' | sort")
    print("find . -maxdepth 3 -type d -not -path './.git/*' | sort")
    print()
    print("Next reading targets:")
    print("- README*")
    print("- docs/")
    print("- package/build/test files")
    print("- existing planning files")
    print("- CI/workflow files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
