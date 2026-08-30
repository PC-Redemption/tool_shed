#!/usr/bin/env python3
"""Verify that a workspace uses the current canonical Tool Shed work topology."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import json
import sys
from pathlib import Path

import campaign_queue
import document_store
import program_roadmap
from work_tree import WORK_DIRS


REQUIRED_FILES = (
    "work/README.md",
    "work/index.md",
    "work/index.json",
    "work/00-campaigns/active-queue.md",
    "work/00-campaigns/completed-queue.md",
    "work/01-q&a/ask.txt",
)


def inspect_work_tree(workspace: Path) -> dict[str, object]:
    database_authoritative = document_store.is_authoritative(workspace)
    findings: list[str] = []
    missing_directories = [
        relative for relative in WORK_DIRS if not (workspace / relative).is_dir()
    ]
    campaign_directories = [
        f"work/00-campaigns/{name}"
        for name in campaign_queue.LIFECYCLE_DIRS
        if not (workspace / "work" / "00-campaigns" / name).is_dir()
    ]
    missing_directories.extend(campaign_directories)
    missing_files = [
        relative for relative in REQUIRED_FILES if not (workspace / relative).is_file()
    ]
    legacy_paths = [
        relative
        for relative in ("work/q&a", "q&a")
        if (workspace / relative).exists() or (workspace / relative).is_symlink()
    ]
    if missing_directories:
        findings.append("missing canonical work directories: " + ", ".join(missing_directories))
    if missing_files:
        findings.append("missing canonical work files: " + ", ".join(missing_files))
    if legacy_paths:
        findings.append("legacy work paths remain: " + ", ".join(legacy_paths))
    index_path = workspace / "work" / "index.json"
    if index_path.is_file():
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            findings.append(f"work/index.json is invalid: {error}")
        else:
            if payload.get("schema_version") != 1:
                findings.append("work/index.json has unsupported schema_version")
    campaign_root = campaign_queue.campaign_root(workspace)
    if campaign_root.is_dir() and not missing_files and not database_authoritative:
        findings.extend(campaign_queue.validate(workspace))
    findings.extend(program_roadmap.validate_all(workspace))
    return {
        "schema_version": 1,
        "workspace": str(workspace),
        "campaign_authority": "sqlite" if database_authoritative else "file",
        "converged": not findings,
        "missing_directories": missing_directories,
        "missing_files": missing_files,
        "legacy_paths": legacy_paths,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".", help="Project workspace root.")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON.")
    args = parser.parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    try:
        report = inspect_work_tree(workspace)
    except (campaign_queue.CampaignError, program_roadmap.RoadmapError, OSError) as error:
        print(f"Work tree check failed: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["converged"]:
        print("Work tree matches the current Tool Shed structure.")
    else:
        for finding in report["findings"]:
            print(f"- {finding}")
    return 0 if report["converged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
