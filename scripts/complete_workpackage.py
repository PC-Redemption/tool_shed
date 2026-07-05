from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path


HEADER_RE = re.compile(r"^(Status|Updated|Next Action):\s*.*$")


def workspace_relative(path: Path, workspace: Path) -> Path:
    resolved = path.expanduser()
    if not resolved.is_absolute():
        resolved = workspace / resolved
    try:
        return resolved.resolve().relative_to(workspace)
    except ValueError as exc:
        raise SystemExit(f"workpackage must be inside workspace: {resolved}") from exc


def rewrite_header(text: str, *, next_action: str) -> str:
    replacements = {
        "Status": "Status: complete",
        "Updated": f"Updated: {date.today().isoformat()}",
        "Next Action": f"Next Action: {next_action}",
    }
    seen: set[str] = set()
    lines = []
    for line in text.splitlines():
        match = HEADER_RE.match(line)
        if match:
            key = match.group(1)
            lines.append(replacements[key])
            seen.add(key)
        else:
            lines.append(line)
    missing = [key for key in ["Status", "Updated", "Next Action"] if key not in seen]
    if missing:
        raise SystemExit(f"workpackage header missing required fields: {', '.join(missing)}")
    suffix = "\n" if text.endswith("\n") else ""
    return "\n".join(lines) + suffix


def refresh_work_index(workspace: Path, shed: Path) -> None:
    subprocess.run(
        [sys.executable, str(shed / "scripts" / "update_work_index.py"), "--workspace", str(workspace)],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def check_stale_paths(workspace: Path, shed: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(shed / "scripts" / "check_stale_paths.py"), "--workspace", str(workspace)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Move an active workpackage to completed and refresh work indexes.")
    parser.add_argument("workpackage", help="Path to a work/wp/active/*.md workpackage.")
    parser.add_argument("--workspace", default=".", help="Project workspace root. Defaults to current directory.")
    parser.add_argument("--shed", default=None, help="Path to tool_shed. Defaults to this script's parent.")
    parser.add_argument("--next-action", default="none", help="Completed workpackage Next Action value.")
    parser.add_argument(
        "--strict-stale-check",
        action="store_true",
        help="Return a non-zero exit code if stale work paths remain after the move.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    shed = Path(args.shed).expanduser().resolve() if args.shed else Path(__file__).resolve().parents[1]
    source_relative = workspace_relative(Path(args.workpackage), workspace)

    if source_relative.parts[:3] != ("work", "wp", "active") or len(source_relative.parts) != 4:
        raise SystemExit(f"expected work/wp/active/*.md path, got: {source_relative.as_posix()}")
    if source_relative.suffix != ".md":
        raise SystemExit(f"expected Markdown workpackage, got: {source_relative.as_posix()}")

    source = workspace / source_relative
    destination_relative = Path("work") / "wp" / "completed" / source_relative.name
    destination = workspace / destination_relative

    if not source.exists():
        raise SystemExit(f"workpackage does not exist: {source_relative.as_posix()}")
    if destination.exists():
        raise SystemExit(f"refusing to overwrite completed workpackage: {destination_relative.as_posix()}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(rewrite_header(source.read_text(encoding="utf-8"), next_action=args.next_action), encoding="utf-8")
    source.unlink()
    refresh_work_index(workspace, shed)

    stale = check_stale_paths(workspace, shed)
    print(f"Moved {source_relative.as_posix()} -> {destination_relative.as_posix()}")
    if stale.returncode == 0:
        print(stale.stdout.strip())
        return 0

    if stale.stdout:
        print(stale.stdout.strip())
    if stale.stderr:
        print(stale.stderr.strip(), file=sys.stderr)
    if args.strict_stale_check:
        return stale.returncode
    print("Stale-path findings are warnings. Re-run with --strict-stale-check to fail on them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
