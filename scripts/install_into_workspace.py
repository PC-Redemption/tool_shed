from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from repository_policy import POLICY_FILE, format_bytes, inspect_snapshot_ignore, inspect_work_ignore
from work_tree import ensure_work_tree


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
    ensure_work_tree(root)

    index_script = Path(__file__).resolve().with_name("update_work_index.py")
    if index_script.exists():
        subprocess.run(
            [sys.executable, str(index_script), "--workspace", str(root)],
            check=True,
            stdout=subprocess.DEVNULL,
        )

    print(f"Initialized work tree under {root / 'work'}")
    state = inspect_work_ignore(root)
    failed = False
    if state.match is None:
        if state.repository is not None:
            print("Repository policy: root work/ is trackable (Tool Shed default).")
    else:
        match = state.match
        print(
            f"Repository policy: root work/ is ignored by {match.source}:{match.line}: {match.rule!r} "
            f"(matched {match.path})."
        )
        print(
            f"Trackability preview: {state.file_count} file(s), {format_bytes(state.total_bytes)}, "
            "currently ignored under work/."
        )
        if state.exception_reason:
            print(f"Documented exception in {POLICY_FILE}: {state.exception_reason}")
        else:
            if state.exception_error:
                print(f"Invalid exception: {state.exception_error}")
            print(
                "Remove only the root /work/ ignore rule shown above, then rerun this command. "
                f"If ignoring work/ is intentional, document it in repository-root {POLICY_FILE}. "
                "No work/ files were deleted, replaced, relocated, or rewritten by this policy check."
            )
            failed = True

    repository, snapshot_match = inspect_snapshot_ignore(root)
    if repository is not None and (repository / "tool_shed").exists():
        if snapshot_match:
            print(
                f"Repository policy: /tool_shed/ is ignored by {snapshot_match.source}:"
                f"{snapshot_match.line}: {snapshot_match.rule!r}."
            )
        else:
            print("Repository policy: add /tool_shed/ to the repository-root .gitignore.")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
