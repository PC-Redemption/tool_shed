from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\((work/[^)\s]+\.md(?:#[^)]+)?)\)")
HEADER_PATH_KEYS = {"Parent", "Project Map", "Canonical Truth", "Supersedes", "Superseded By"}
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "examples"}
SKIP_FILES = {("work", "index.md")}


@dataclass
class Finding:
    source: Path
    line_number: int
    reference: str
    reason: str
    suggestion: str = ""


def should_skip_tool_shed(root: Path) -> bool:
    script_path = Path(__file__).resolve()
    copied_script = (root / "tool_shed" / "scripts" / Path(__file__).name).resolve()
    return copied_script == script_path


def git_visible_markdown_files(root: Path) -> list[Path] | None:
    repository = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if repository.returncode or Path(repository.stdout.strip()).resolve() != root:
        return None
    visible = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "*.md",
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if visible.returncode:
        detail = visible.stderr.decode(errors="replace").strip()
        raise RuntimeError(detail or "git ls-files failed")
    paths = []
    for raw_path in visible.stdout.split(b"\0"):
        if not raw_path:
            continue
        path = root / Path(raw_path.decode("utf-8", errors="surrogateescape"))
        if path.is_file():
            paths.append(path)
    return sorted(set(paths))


def iter_markdown_files(root: Path) -> list[Path]:
    git_visible = git_visible_markdown_files(root)
    candidates = git_visible if git_visible is not None else sorted(root.rglob("*.md"))
    paths = []
    skip_tool_shed = should_skip_tool_shed(root)
    for path in candidates:
        relative_parts = path.relative_to(root).parts
        if skip_tool_shed and relative_parts[:1] == ("tool_shed",):
            continue
        if relative_parts in SKIP_FILES:
            continue
        parts = set(relative_parts)
        if parts & SKIP_DIRS:
            continue
        if path.is_file():
            paths.append(path)
    return paths


def strip_anchor(reference: str) -> str:
    return reference.split("#", 1)[0]


def completed_workpackage_for(reference_path: Path, root: Path) -> Path | None:
    try:
        relative = reference_path.relative_to(root)
    except ValueError:
        return None
    parts = relative.parts
    if len(parts) == 4 and parts[:3] == ("work", "wp", "active"):
        candidate = root / "work" / "wp" / "completed" / parts[3]
        if candidate.exists():
            return candidate
    return None


def scan_file(path: Path, root: Path) -> list[Finding]:
    findings: list[Finding] = []
    relative_source = path.relative_to(root)
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        references = [match.group(1).rstrip(".,;:") for match in MARKDOWN_LINK_RE.finditer(line)]
        if ":" in line:
            key, raw_value = line.split(":", 1)
            if key.strip() in HEADER_PATH_KEYS:
                value = raw_value.strip()
                if value.startswith("work/") and ".md" in value:
                    references.append(value.split()[0].rstrip(".,;:"))
        for reference in references:
            findings.extend(check_reference(relative_source, line_number, reference, root))
    return findings


def check_reference(source: Path, line_number: int, reference: str, root: Path) -> list[Finding]:
    reference_path = root / strip_anchor(reference)
    if reference_path.exists():
        return []
    completed = completed_workpackage_for(reference_path, root)
    if completed:
        return [
            Finding(
                source=source,
                line_number=line_number,
                reference=reference,
                reason="active workpackage path is stale; completed path exists",
                suggestion=completed.relative_to(root).as_posix(),
            )
        ]
    return [
        Finding(
            source=source,
            line_number=line_number,
            reference=reference,
            reason="referenced work artifact does not exist",
        )
    ]


def scan(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_markdown_files(root):
        findings.extend(scan_file(path, root))
    return findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan Markdown files for stale work artifact paths.")
    parser.add_argument("--workspace", default=".", help="Project workspace root. Defaults to current directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.workspace).expanduser().resolve()
    findings = scan(root)
    if not findings:
        print("No stale work paths found.")
        return 0
    for item in findings:
        location = f"{item.source}:{item.line_number}"
        suffix = f" -> {item.suggestion}" if item.suggestion else ""
        print(f"{location}: {item.reason}: {item.reference}{suffix}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
