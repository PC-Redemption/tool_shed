from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


DEFAULT_REPO_URL = "https://github.com/PC-Redemption/tool_shed.git"
DEFAULT_BRANCH = "main"
REQUIRED_SNAPSHOT_PATHS = [
    "README.md",
    "selection.md",
    "conventions.md",
    "existing-projects.md",
    "templates",
    "scripts",
]


class InstallerError(Exception):
    def __init__(self, message: str, returncode: int = 1) -> None:
        super().__init__(message)
        self.returncode = returncode


def run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "untitled"


def resolve_workspace(positional: str | None, option: str | None) -> Path:
    workspace = option or positional or "."
    return Path(workspace).expanduser().resolve()


def verify_snapshot(snapshot: Path) -> None:
    missing = [relative for relative in REQUIRED_SNAPSHOT_PATHS if not (snapshot / relative).exists()]
    if missing:
        raise SystemExit(f"snapshot missing required Tool Shed paths: {', '.join(missing)}")

    validation_script = snapshot / "scripts" / "validate_tool_shed.py"
    install_script = snapshot / "scripts" / "install_into_workspace.py"
    if not validation_script.exists():
        raise SystemExit("snapshot missing scripts/validate_tool_shed.py")
    if not install_script.exists():
        raise SystemExit("snapshot missing scripts/install_into_workspace.py")


def clone_snapshot(repo_url: str, branch: str, temp_root: Path) -> Path:
    snapshot = temp_root / "tool_shed"
    command = [
        "git",
        "clone",
        "--branch",
        branch,
        "--single-branch",
        repo_url,
        str(snapshot),
    ]
    run(command)
    return snapshot


def validate_snapshot(snapshot: Path) -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_tool_shed.py"],
        cwd=str(snapshot),
        text=True,
    )
    if result.returncode != 0:
        raise InstallerError(f"Tool Shed validation failed with exit code {result.returncode}", result.returncode)


def normalize_gitignore(workspace: Path) -> tuple[bool, str | None]:
    gitignore = workspace / ".gitignore"
    old_text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else None
    lines = old_text.splitlines() if old_text is not None else []

    next_lines: list[str] = []
    inserted = False
    for line in lines:
        if line == "/tool_shed/":
            if inserted:
                continue
            inserted = True
        next_lines.append(line)

    if not inserted:
        if next_lines and next_lines[-1] != "":
            next_lines.append("")
        next_lines.append("/tool_shed/")

    new_text = "\n".join(next_lines) + "\n"
    gitignore.write_text(new_text, encoding="utf-8")
    return old_text != new_text, old_text


def restore_gitignore(workspace: Path, old_text: str | None) -> None:
    gitignore = workspace / ".gitignore"
    if old_text is None:
        gitignore.unlink(missing_ok=True)
    else:
        gitignore.write_text(old_text, encoding="utf-8")


def remove_tracked_tool_shed_from_index(workspace: Path) -> None:
    inside = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "--is-inside-work-tree"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return

    tracked = subprocess.run(
        ["git", "-C", str(workspace), "ls-files", "-z", "--", "tool_shed"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    if not tracked.stdout:
        return

    subprocess.run(
        ["git", "-C", str(workspace), "rm", "-r", "--cached", "--quiet", "--", "tool_shed"],
        check=True,
    )


def copy_snapshot_without_git(snapshot: Path, target: Path) -> None:
    shutil.copytree(
        snapshot,
        target,
        ignore=shutil.ignore_patterns(".git"),
    )


def run_workspace_install(target: Path, workspace: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(target / "scripts" / "install_into_workspace.py"), str(workspace)],
    )
    if result.returncode != 0:
        raise InstallerError(f"Workspace initialization failed with exit code {result.returncode}", result.returncode)


def infer_project_title(workspace: Path) -> str:
    for readme in sorted(workspace.glob("README*")):
        if not readme.is_file():
            continue
        for line in readme.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
                if title:
                    return title
    return workspace.name


def maybe_onboard_existing(target: Path, workspace: Path, project_title: str | None) -> None:
    title = project_title or infer_project_title(workspace)
    slug = slugify(title)
    map_path = workspace / "work" / "maps" / f"map-{slug}.md"
    inventory_path = workspace / "work" / "inventories" / f"inventory-{slug}-surfaces.md"
    if map_path.exists() or inventory_path.exists():
        print(f"Level 2 onboarding already present for {title}; skipping duplicate artifacts.")
        return

    subprocess.run(
        [
            sys.executable,
            str(target / "scripts" / "onboard_existing_project.py"),
            title,
            "--workspace",
            str(workspace),
            "--shed",
            str(target),
        ],
        check=True,
    )


def install_snapshot(snapshot: Path, workspace: Path, *, onboard_existing: bool, project_title: str | None) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    target = workspace / "tool_shed"
    backup = workspace / f".tool_shed.old.{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    old_gitignore: str | None = None
    gitignore_touched = False
    backup_created = False
    target_created = False

    try:
        if target.exists():
            target.rename(backup)
            backup_created = True

        copy_snapshot_without_git(snapshot, target)
        target_created = True

        _, old_gitignore = normalize_gitignore(workspace)
        gitignore_touched = True
        remove_tracked_tool_shed_from_index(workspace)
        run_workspace_install(target, workspace)

        if onboard_existing:
            maybe_onboard_existing(target, workspace, project_title)

    except Exception:
        if target_created and target.exists():
            shutil.rmtree(target)
        if backup_created and backup.exists():
            backup.rename(target)
        if gitignore_touched:
            restore_gitignore(workspace, old_gitignore)
        raise
    else:
        if backup_created and backup.exists():
            shutil.rmtree(backup)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install or update Tool Shed in a workspace from the canonical repository."
    )
    parser.add_argument(
        "workspace",
        nargs="?",
        default=None,
        help="Workspace root. Defaults to the current directory.",
    )
    parser.add_argument(
        "--workspace",
        dest="workspace_option",
        default=None,
        help="Workspace root. Overrides the positional workspace when provided.",
    )
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="Tool Shed Git repository URL.")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="Tool Shed branch to clone.")
    parser.add_argument(
        "--source",
        default=None,
        help="Use an existing local Tool Shed snapshot instead of cloning. Intended for tests and local development.",
    )
    parser.add_argument(
        "--onboard-existing",
        action="store_true",
        help="Create Level 2 onboarding artifacts when they are not already present.",
    )
    parser.add_argument(
        "--project-title",
        default=None,
        help="Project title for optional Level 2 onboarding. Defaults to README heading or directory name.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = resolve_workspace(args.workspace, args.workspace_option)

    try:
        with tempfile.TemporaryDirectory(prefix="tool-shed-install-") as temp:
            temp_root = Path(temp)
            snapshot = Path(args.source).expanduser().resolve() if args.source else clone_snapshot(
                args.repo_url,
                args.branch,
                temp_root,
            )

            verify_snapshot(snapshot)
            validate_snapshot(snapshot)
            install_snapshot(
                snapshot,
                workspace,
                onboard_existing=args.onboard_existing,
                project_title=args.project_title,
            )
    except InstallerError as error:
        print(error, file=sys.stderr)
        return error.returncode
    except subprocess.CalledProcessError as error:
        print(f"command failed with exit code {error.returncode}: {' '.join(error.cmd)}", file=sys.stderr)
        return error.returncode or 1

    print(f"Installed Tool Shed into {workspace / 'tool_shed'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
