from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from work_tree import ensure_work_tree

try:
    import document_store
except ModuleNotFoundError:  # Older partial snapshots retain file authority.
    document_store = None  # type: ignore[assignment]


ARTIFACTS = {
    "idea": ("templates/idea-brief.md", "work/ideas", "idea"),
    "idea-brief": ("templates/idea-brief.md", "work/ideas", "idea"),
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
    "deep-research": ("templates/deep-research-spike.md", "work/spikes", "spike"),
    "deep-research-spike": ("templates/deep-research-spike.md", "work/spikes", "spike"),
    "inventory": ("templates/inventory.md", "work/inventories", "inventory"),
    "project-inventory": ("templates/existing-project-inventory.md", "work/inventories", "inventory"),
    "existing-project-inventory": ("templates/existing-project-inventory.md", "work/inventories", "inventory"),
    "level-2-inventory": ("templates/existing-project-inventory.md", "work/inventories", "inventory"),
    "decision": ("templates/decision-matrix.md", "work/decisions", "decision"),
    "decision-matrix": ("templates/decision-matrix.md", "work/decisions", "decision"),
}

DATABASE_TYPES = {
    "idea": "idea-brief", "idea-brief": "idea-brief", "checklist": "checklist", "ticket": "ticket",
    "map": "project-map", "project-map": "project-map", "coordination-map": "project-map",
    "wp": "workpackage", "workpackage": "workpackage", "adr": "adr", "runbook": "runbook",
    "incident": "incident", "spike": "spike", "deep-research": "spike", "deep-research-spike": "spike",
    "inventory": "inventory", "project-inventory": "inventory", "existing-project-inventory": "inventory",
    "level-2-inventory": "inventory", "decision": "decision", "decision-matrix": "decision",
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


def refresh_work_index(workspace: Path, shed: Path) -> None:
    index_script = shed / "scripts" / "update_work_index.py"
    if index_script.exists():
        subprocess.run(
            [sys.executable, str(index_script), "--workspace", str(workspace)],
            check=True,
            stdout=subprocess.DEVNULL,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a project work artifact from tool_shed templates.")
    parser.add_argument("kind", choices=sorted(ARTIFACTS))
    parser.add_argument("title")
    parser.add_argument("--workspace", default=".", help="Project workspace root. Defaults to current directory.")
    parser.add_argument("--shed", default=None, help="Path to tool_shed. Defaults to this script's parent.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing artifact.")
    parser.add_argument("--project-binding", help="Required when generated-document authority is SQLite.")
    parser.add_argument("--actor", default="tool-shed")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    shed = Path(args.shed).expanduser().resolve() if args.shed else Path(__file__).resolve().parents[1]
    template_path, destination_dir, prefix = ARTIFACTS[args.kind]

    template = (shed / template_path).read_text(encoding="utf-8")
    destination = workspace / destination_dir / f"{prefix}-{slugify(args.title)}.md"
    rendered = render_template(template, title=args.title)

    if document_store is not None and document_store.is_authoritative(workspace):
        if not args.project_binding:
            raise SystemExit("SQLite-authoritative artifact creation requires --project-binding")
        status = next((line.split(":", 1)[1].strip().casefold() for line in rendered.splitlines()[:45] if line.startswith("Status:")), "active")
        lifecycle = {"complete": "completed", "promoted": "active", "approved": "active", "proposed": "active"}.get(status, status)
        if lifecycle not in document_store.LIFECYCLES:
            lifecycle = "active"
        result = document_store.create_document(
            workspace,
            project_binding=args.project_binding,
            document_type=DATABASE_TYPES[args.kind],
            title=args.title,
            body=rendered,
            lifecycle=lifecycle,
            metadata={"document_type": DATABASE_TYPES[args.kind], "logical_path": destination.relative_to(workspace).as_posix()},
            actor=args.actor,
            reason="create Tool Shed artifact",
            preferred_path=destination.relative_to(workspace).as_posix(),
        )
        print(result["result"]["visible_id"])
        return 0

    ensure_work_tree(workspace)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and not args.force:
        raise SystemExit(f"refusing to overwrite existing artifact: {destination}")

    destination.write_text(rendered, encoding="utf-8")
    refresh_work_index(workspace, shed)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
