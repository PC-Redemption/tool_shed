#!/usr/bin/env python3
"""Resolve the canonical generated-work authority for a Tool Shed workspace."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import contextlib
import json
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any

import hybrid_state
from project_identity import load_project_identity, require_path_within, resolved_workspace


SCHEMA_VERSION = 1
DOCUMENT_SCHEMA_MINIMUM = 2


class AuthorityResolutionError(RuntimeError):
    pass


def file_artifact_id(workspace: Path, relative_path: str) -> str:
    """Return the stable UUID used for one retained file-authoritative artifact."""
    project_id = load_project_identity(resolved_workspace(workspace))["project_id"]
    normalized = Path(relative_path.replace("\\", "/")).as_posix()
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"tool-shed:{project_id}:file:{normalized}"))


def resolve(
    workspace: Path,
    *,
    database: Path | None = None,
) -> dict[str, Any]:
    """Return one bounded authority decision without mutating the workspace.

    File authority remains active until an explicit Hybrid cutover records
    storage_mode=hybrid. If the database cannot be inspected, authority is
    indeterminate rather than silently guessed.
    """
    root = resolved_workspace(workspace)
    candidate = database or hybrid_state.database_path(root)
    path = require_path_within(root, candidate if candidate.is_absolute() else root / candidate)
    if not path.is_file():
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "tool-shed-authority-resolution",
            "authority": "file",
            "state": "file-only",
            "database_present": False,
            "hybrid_schema": None,
            "storage_mode": "file",
            "reason": "Hybrid database is absent; retained work files are authoritative",
            "feature_limits": ["hybrid-state-unavailable"],
            "next_action": "Initialize and qualify Hybrid state before requesting SQLite-backed features",
            "writes_performed": False,
        }
    try:
        with contextlib.closing(hybrid_state.connect(path, writable=False)) as connection:
            schema = int(connection.execute("PRAGMA user_version").fetchone()[0])
            has_meta = bool(
                connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='state_meta'"
                ).fetchone()
            )
            if not has_meta:
                raise AuthorityResolutionError("Hybrid database lacks state_meta")
            meta = hybrid_state.meta_row(connection)
            mode = str(meta["storage_mode"])
            qualified_shadow = (
                mode == "shadow"
                and bool(meta["checkpoint_digest"])
                and int(meta["last_checkpoint_revision"]) == int(meta["current_revision"])
                and not bool(meta["checkpoint_pending"])
                and not bool(meta["dirty"])
            )
    except (AuthorityResolutionError, sqlite3.DatabaseError, hybrid_state.HybridStateError, OSError, KeyError) as error:
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "tool-shed-authority-resolution",
            "authority": "unavailable",
            "state": "indeterminate",
            "database_present": True,
            "hybrid_schema": None,
            "storage_mode": "unknown",
            "reason": f"Hybrid authority cannot be resolved: {type(error).__name__}",
            "feature_limits": ["authority-indeterminate"],
            "next_action": "Run Tool Shed Doctor and repair or restore the Hybrid authority contract",
            "writes_performed": False,
        }

    if mode == "hybrid":
        if schema < DOCUMENT_SCHEMA_MINIMUM:
            return {
                "schema_version": SCHEMA_VERSION,
                "kind": "tool-shed-authority-resolution",
                "authority": "unavailable",
                "state": "invalid-hybrid",
                "database_present": True,
                "hybrid_schema": schema,
                "storage_mode": mode,
                "reason": "Hybrid authority is declared before the document schema is available",
                "feature_limits": ["authority-contract-invalid"],
                "next_action": "Repair the Hybrid schema before using generated-document features",
                "writes_performed": False,
            }
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "tool-shed-authority-resolution",
            "authority": "sqlite",
            "state": "hybrid",
            "database_present": True,
            "hybrid_schema": schema,
            "storage_mode": mode,
            "reason": "guarded cutover selected SQLite generated-document authority",
            "feature_limits": [],
            "next_action": None,
            "writes_performed": False,
        }

    limits = ["hybrid-document-writes-unavailable"]
    if mode == "shadow":
        limits.extend(
            [
                "idea-readiness-persistence-unavailable",
                "planning-order-overrides-unavailable",
                "hybrid-outcomes-unavailable",
            ]
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-authority-resolution",
        "authority": "file",
        "state": "qualified-shadow" if qualified_shadow else "shadow" if mode == "shadow" else "file",
        "database_present": True,
        "hybrid_schema": schema,
        "storage_mode": mode,
        "reason": (
            "qualified shadow awaits guarded cutover; retained work files remain authoritative"
            if qualified_shadow
            else "shadow database is not authoritative; retained work files remain authoritative"
            if mode == "shadow"
            else "state contract retains file authority"
        ),
        "feature_limits": sorted(set(limits)),
        "next_action": (
            "Complete guarded conversion, qualification, and cutover before using SQLite-backed features"
            if mode == "shadow"
            else "Complete guarded Hybrid initialization and cutover before using SQLite-backed features"
        ),
        "writes_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--database")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    database = Path(args.database).expanduser() if args.database else None
    result = resolve(workspace, database=database)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"authority={result['authority']} state={result['state']} "
            f"schema={result['hybrid_schema']} storage_mode={result['storage_mode']}"
        )
        print(result["reason"])
        if result["feature_limits"]:
            print("feature limits: " + ", ".join(result["feature_limits"]))
    return 2 if result["authority"] == "unavailable" else 0


if __name__ == "__main__":
    sys.exit(main())
