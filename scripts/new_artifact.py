from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path


ARTIFACTS = {
    "checklist": ("templates/checklist.md", "work/checklists", "checklist"),
    "ticket": ("templates/ticket.md", "work/tickets", "ticket"),
    "map": ("templates/project-map.md", "work/maps", "map"),
    "project-map": ("templates/project-map.md", "work/maps", "map"),
    "coordination-map": ("templates/project-map.md", "work/maps", "map"),
    "wp": ("templates/workpackage.md", "work/wp/active", "wp"),
    "workpackage": ("templates/workpackage.md", "work/wp/active", "wp"),
    "adr": ("templates/adr.md", "work/adr", "adr"),
    "runbook": ("templates/runbook.md", "work/runbooks", "runbook"),
    "incident": ("templates/incident.md", "work/incidents", "incident"),
    "spike": ("templates/spike.md", "work/spikes", "spike"),
    "inventory": ("templates/inventory.md", "work/inventories", "inventory"),
    "decision": ("templates/decision-matrix.md", "work/decisions", "decision"),
    "decision-matrix": ("templates/decision-matrix.md", "work/decisions", "decision"),
}


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "untitled"


def render_template(template: str, *, title: str) -> str:
    return (
        template.replace("{{ title }}", title.strip())
        .replace("{{ date }}", date.today().isoformat())
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a project work artifact from tool_shed templates.")
    parser.add_argument("kind", choices=sorted(ARTIFACTS))
    parser.add_argument("title")
    parser.add_argument("--workspace", default=".", help="Project workspace root. Defaults to current directory.")
    parser.add_argument("--shed", default=None, help="Path to tool_shed. Defaults to this script's parent.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing artifact.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    shed = Path(args.shed).expanduser().resolve() if args.shed else Path(__file__).resolve().parents[1]
    template_path, destination_dir, prefix = ARTIFACTS[args.kind]

    template = (shed / template_path).read_text(encoding="utf-8")
    destination = workspace / destination_dir / f"{prefix}-{slugify(args.title)}.md"
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and not args.force:
        raise SystemExit(f"refusing to overwrite existing artifact: {destination}")

    destination.write_text(render_template(template, title=args.title), encoding="utf-8")
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
