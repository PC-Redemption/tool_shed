from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
