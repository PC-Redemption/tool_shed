#!/usr/bin/env python3
"""Run the focused client-installation smoke for an attested Tool Shed release."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import json
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CRITICAL_SCRIPTS = (
    "check_shed_version.py",
    "install_into_workspace.py",
    "project_identity.py",
    "provider_adapters.py",
    "update_snapshot.py",
)


def run(arguments: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        arguments,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"client smoke command failed ({result.returncode}): {detail}")
    return result


def main() -> int:
    manifest = json.loads((ROOT / "SHED_VERSION.json").read_text(encoding="utf-8"))
    if not manifest.get("release_commit") or not manifest.get("released_at"):
        raise SystemExit("client smoke requires published release provenance")
    for name in CRITICAL_SCRIPTS:
        py_compile.compile(str(ROOT / "scripts" / name), doraise=True)

    run(
        [
            sys.executable,
            "-B",
            "scripts/check_shed_version.py",
            "--shed",
            ".",
            "--local-only",
            "--strict",
            "--verification-only",
        ],
        cwd=ROOT,
    )

    with tempfile.TemporaryDirectory(prefix="tool-shed-client-smoke-") as temporary:
        workspace = Path(temporary)
        run(["git", "init", "--quiet"], cwd=workspace)
        run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts" / "install_into_workspace.py"),
                str(workspace),
                "--provider",
                "all",
            ],
            cwd=workspace,
        )
        required = (
            workspace / "work" / "tool-shed-project.json",
            workspace / "work" / "00-campaigns" / "active-queue.md",
            workspace / "work" / "index.json",
            workspace / "AGENTS.md",
            workspace / "CLAUDE.md",
            workspace / "GEMINI.md",
        )
        missing = [str(path.relative_to(workspace)) for path in required if not path.is_file()]
        if missing:
            raise SystemExit("client smoke missing installed paths: " + ", ".join(missing))
        if (ROOT / "work").exists() and not (ROOT / ".git").exists():
            raise SystemExit("disconnected release contains forbidden snapshot-local work")

    print("Tool Shed focused client installation smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
