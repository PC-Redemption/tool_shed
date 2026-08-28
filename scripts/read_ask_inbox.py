#!/usr/bin/env python3
"""Inspect Tool Shed's canonical and fallback Q&A inboxes without modifying them."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import json
from pathlib import Path


CANONICAL_PATH = Path("work") / "01-q&a" / "ask.txt"
FALLBACK_PATH = Path("work") / "q&a" / "ask.txt"


def actionable_content(path: Path) -> str:
    if not path.is_file():
        return ""
    actionable = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return "\n".join(actionable)


def inspect_inboxes(workspace: Path) -> dict[str, object]:
    root = workspace.expanduser().resolve()
    canonical = root / CANONICAL_PATH
    fallback = root / FALLBACK_PATH
    canonical_content = actionable_content(canonical)
    fallback_content = actionable_content(fallback)

    if canonical_content and fallback_content:
        status = "conflict"
        selected_path = None
        content = None
    elif canonical_content:
        status = "canonical"
        selected_path = CANONICAL_PATH.as_posix()
        content = canonical_content
    elif fallback_content:
        status = "fallback"
        selected_path = FALLBACK_PATH.as_posix()
        content = fallback_content
    else:
        status = "empty"
        selected_path = None
        content = None

    return {
        "status": status,
        "selected_path": selected_path,
        "content": content,
        "canonical": {
            "path": CANONICAL_PATH.as_posix(),
            "exists": canonical.is_file(),
            "actionable": bool(canonical_content),
        },
        "fallback": {
            "path": FALLBACK_PATH.as_posix(),
            "exists": fallback.is_file(),
            "actionable": bool(fallback_content),
        },
    }


def render(payload: dict[str, object]) -> str:
    status = payload["status"]
    if status == "canonical":
        return f"Using canonical inbox work/01-q&a/ask.txt:\n\n{payload['content']}"
    if status == "fallback":
        return (
            "Warning: actionable inbox content was found at noncanonical "
            "legacy location work/q&a/ask.txt; the canonical inbox is work/01-q&a/ask.txt.\n\n"
            f"{payload['content']}"
        )
    if status == "conflict":
        return (
            "Conflict: both work/01-q&a/ask.txt and work/q&a/ask.txt contain actionable content. "
            "Choose which request to use; the inboxes were not merged or modified."
        )
    return (
        "The Tool Shed Q&A inbox is empty: neither work/01-q&a/ask.txt nor work/q&a/ask.txt "
        "contains actionable content."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace root containing work/01-q&a/ and optional legacy work/q&a/. Defaults to the current directory.",
    )
    parser.add_argument("--json", action="store_true", help="Emit the deterministic routing result as JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = inspect_inboxes(Path(args.workspace))
    print(json.dumps(payload, indent=2) if args.json else render(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
