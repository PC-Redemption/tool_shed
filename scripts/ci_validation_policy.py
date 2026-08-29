#!/usr/bin/env python3
"""Select the minimum sufficient Tool Shed CI profile from changed paths."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import json
import os
import sys
from pathlib import Path


FULL_PREFIXES = (
    ".github/workflows/",
    "schemas/",
    "scripts/",
    "skills/",
    "templates/",
    "tests/",
)
FULL_FILES = {
    ".gitignore",
    "SHED_VERSION.json",
    "install.sh",
    "install.ps1",
    "pyproject.toml",
}
PERFORMANCE_PATHS = {
    "scripts/benchmark_validation.py",
    "scripts/validate_tool_shed.py",
    ".github/workflows/validation-performance.yml",
}


def job_matrix(*, full: bool) -> dict[str, list[dict[str, object]]]:
    if not full:
        return {
            "include": [
                {
                    "os": "ubuntu-latest",
                    "python_version": "3.x",
                    "shard": 0,
                    "shard_count": 1,
                    "test_jobs": 8,
                    "profile": "focused",
                }
            ]
        }
    return {
        "include": [
            {
                "os": operating_system,
                "python_version": python_version,
                "shard": shard,
                "shard_count": 8,
                "test_jobs": 6 if operating_system == "windows-latest" else 8,
                "profile": "release",
            }
            for operating_system in ("ubuntu-latest", "windows-latest")
            for python_version in ("3.11", "3.x")
            for shard in range(8)
        ]
    }


def classify(paths: list[str], *, force_full: bool = False) -> dict[str, object]:
    normalized = sorted({Path(value.strip()).as_posix() for value in paths if value.strip()})
    full_paths = [
        path
        for path in normalized
        if path in FULL_FILES or path.startswith(FULL_PREFIXES)
    ]
    full = force_full or not normalized or bool(full_paths)
    performance = force_full or any(
        path in PERFORMANCE_PATHS or path.startswith("tests/fixtures/validation-performance-")
        for path in normalized
    )
    result = {
        "schema_version": 1,
        "kind": "tool-shed-ci-validation-policy",
        "profile": "release" if full else "focused",
        "full_matrix": full,
        "shard_count": 8 if full else 1,
        "performance": performance,
        "reason": (
            "explicit full-validation override"
            if force_full
            else "no changed paths; fail-safe full validation"
            if not normalized
            else "product, schema, test, template, or workflow surface changed"
            if full_paths
            else "documentation or database-state collateral only"
        ),
        "changed_paths": normalized,
        "full_trigger_paths": full_paths,
    }
    result["matrix"] = job_matrix(full=full)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--paths-file")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--github-output")
    args = parser.parse_args(argv)
    paths = list(args.paths)
    if args.paths_file:
        paths.extend(Path(args.paths_file).read_text(encoding="utf-8").splitlines())
    force_full = args.full or os.environ.get("TOOL_SHED_FULL_VALIDATION") == "1"
    result = classify(paths, force_full=force_full)
    output = json.dumps(result, indent=2, sort_keys=True)
    print(output)
    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as handle:
            for key in ("profile", "full_matrix", "shard_count", "performance"):
                handle.write(f"{key}={str(result[key]).lower()}\n")
            handle.write(f"matrix={json.dumps(result['matrix'], separators=(',', ':'))}\n")
            handle.write(f"reason={result['reason']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
