from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path


SKIP_NAMES = {"README.md", "index.md"}
HEADER_KEYS = {
    "Status",
    "Type",
    "Updated",
    "Next Action",
    "Parent",
    "Project Map",
    "Canonical Truth",
    "Supersedes",
    "Superseded By",
}


@dataclass
class Artifact:
    path: Path
    title: str
    fields: dict[str, str]


def parse_artifact(path: Path, work_dir: Path) -> Artifact:
    title = path.stem
    fields: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines()[:40]:
        line = raw_line.strip()
        if line.startswith("# "):
            title = line[2:].strip()
            continue
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key in HEADER_KEYS:
            fields[key] = value.strip()
    return Artifact(path=path.relative_to(work_dir.parent), title=title, fields=fields)


def discover_artifacts(work_dir: Path) -> list[Artifact]:
    artifacts = []
    for path in sorted(work_dir.rglob("*.md")):
        if path.name in SKIP_NAMES:
            continue
        artifacts.append(parse_artifact(path, work_dir))
    return artifacts


def link(path: Path) -> str:
    text = path.as_posix()
    return f"[{text}]({text})"


def table_text(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def value(fields: dict[str, str], key: str) -> str:
    return table_text(fields.get(key) or "-")


def render(artifacts: list[Artifact]) -> str:
    lines = [
        "# Work Index",
        "",
        "Generated from artifact headers. Do not put durable project truth only here; keep current truth in docs or README files.",
        "",
        f"Updated: {date.today().isoformat()}",
        "",
        "## Orientation",
        "",
        "| Artifact | Type | Status | Updated | Next Action | Parent / Canonical Truth |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if artifacts:
        for artifact in artifacts:
            fields = artifact.fields
            parent = (
                fields.get("Canonical Truth")
                or fields.get("Parent")
                or fields.get("Project Map")
                or fields.get("Superseded By")
                or "-"
            )
            parent = table_text(parent)
            lines.append(
                "| "
                + " | ".join(
                    [
                        link(artifact.path),
                        value(fields, "Type"),
                        value(fields, "Status"),
                        value(fields, "Updated"),
                        value(fields, "Next Action"),
                        parent,
                    ]
                )
                + " |"
            )
    else:
        lines.append("| - | - | - | - | No artifacts found yet | - |")

    active = [item for item in artifacts if item.fields.get("Status", "").lower() == "active"]
    completed = [
        item
        for item in artifacts
        if item.fields.get("Status", "").lower() in {"complete", "completed", "done", "decided", "accepted"}
    ]

    lines.extend(
        [
            "",
            "## Current Reading Order",
            "",
            "1. Read project README/docs for current truth.",
            "2. Read active maps and active work artifacts from this index.",
            "3. Read completed artifacts only for history, evidence, or handoff context.",
            "",
            "## Summary",
            "",
            f"- Total artifacts: {len(artifacts)}",
            f"- Active artifacts: {len(active)}",
            f"- Completed/decided artifacts: {len(completed)}",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate work/index.md from tool_shed artifact headers.")
    parser.add_argument("--workspace", default=".", help="Project workspace root. Defaults to current directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    work_dir = workspace / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    artifacts = discover_artifacts(work_dir)
    index_path = work_dir / "index.md"
    index_path.write_text(render(artifacts), encoding="utf-8")
    print(index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
