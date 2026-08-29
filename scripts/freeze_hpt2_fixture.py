#!/usr/bin/env python3
"""Create the one-time frozen HPT2 compatibility fixture from a terminal ledger."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from project_identity import require_path_within, resolved_workspace


KIND = "tool-shed-hpt2-compatibility-fixture"


def load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot load {label}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def freeze(
    workspace: Path,
    *,
    source: Path,
    ids_path: Path,
    output: Path,
    baseline_commit: str,
    database_revision: int,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    source = require_path_within(workspace, source if source.is_absolute() else workspace / source)
    ids_path = require_path_within(
        workspace, ids_path if ids_path.is_absolute() else workspace / ids_path
    )
    output = require_path_within(workspace, output if output.is_absolute() else workspace / output)
    if output.exists():
        raise ValueError(f"refusing to replace frozen HPT2 fixture: {output.relative_to(workspace)}")
    if len(baseline_commit) != 40 or any(character not in "0123456789abcdef" for character in baseline_commit):
        raise ValueError("baseline commit must be a full lowercase Git object ID")
    source_payload = load_object(source, "bootstrap closure")
    if source_payload.get("kind") != "tool-shed-bootstrap-closure":
        raise ValueError("source is not a bootstrap closure")
    initiative = next(
        (
            item
            for item in source_payload.get("verdicts", [])
            if item.get("scope") == "initiative"
        ),
        {},
    )
    if initiative.get("disposition") == "open":
        raise ValueError("HPT2 fixture can only be frozen from a terminal bootstrap closure")
    assignments = load_object(ids_path, "HPT2 assigned IDs")
    groups = assignments.get("ids", {})
    required = {
        "requirement": [item["id"] for item in source_payload.get("requirements", [])],
        "change": [item["id"] for item in source_payload.get("changes", [])],
        "evidence": [item["id"] for item in source_payload.get("evidence", [])],
        "verification": [item["id"] for item in source_payload.get("evidence", [])],
        "verdict": [item["scope"] for item in source_payload.get("verdicts", [])],
    }
    for group, labels in required.items():
        missing = sorted(label for label in labels if label not in groups.get(group, {}))
        if missing:
            raise ValueError(f"assigned-ID manifest lacks frozen {group}: " + ", ".join(missing))
    fixture = {
        "schema_version": 1,
        "kind": KIND,
        "frozen_boundary": {
            "baseline_commit": baseline_commit,
            "database_revision": database_revision,
            "source_path": source.relative_to(workspace).as_posix(),
            "source_state_token": source_payload.get("state_token"),
        },
        "project": source_payload.get("project"),
        "state_token": source_payload.get("state_token"),
        "requirements": source_payload.get("requirements", []),
        "changes": source_payload.get("changes", []),
        "evidence": source_payload.get("evidence", []),
        "verdicts": source_payload.get("verdicts", []),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(fixture, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {
        "kind": KIND,
        "path": output.relative_to(workspace).as_posix(),
        "baseline_commit": baseline_commit,
        "database_revision": database_revision,
        "state_token": fixture["state_token"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--source", required=True)
    parser.add_argument("--ids", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--baseline-commit", required=True)
    parser.add_argument("--database-revision", type=int, required=True)
    args = parser.parse_args()
    try:
        result = freeze(
            Path(args.workspace),
            source=Path(args.source),
            ids_path=Path(args.ids),
            output=Path(args.output),
            baseline_commit=args.baseline_commit,
            database_revision=args.database_revision,
        )
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
