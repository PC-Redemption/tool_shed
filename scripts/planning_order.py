#!/usr/bin/env python3
"""Derive and owner-override local Idea Brief and PRM planning order."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import contextlib
import hashlib
import json
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any, Sequence

import document_store
import hybrid_state
from project_identity import ProjectIdentityError, require_path_within, resolved_workspace


RELATION = "planning-precedes"
PROVENANCE = "owner-planning-order"
SUPPORTED_TYPES = {"idea-brief", "program-roadmap"}
TYPE_ALIASES = {
    "idea": "idea-brief",
    "ideas": "idea-brief",
    "bs": "idea-brief",
    "idea-brief": "idea-brief",
    "prm": "program-roadmap",
    "prms": "program-roadmap",
    "program-roadmap": "program-roadmap",
}
TERMINAL_DOCUMENT_STATES = {"completed", "abandoned", "superseded"}
READINESS_RANK = {"working": 0, "ready": 1, "waiting": 2, "blocked": 3}


class PlanningOrderError(RuntimeError):
    pass


def normalize_type(value: str) -> str:
    artifact_type = TYPE_ALIASES.get(value.strip().casefold())
    if artifact_type not in SUPPORTED_TYPES:
        raise PlanningOrderError("planning order supports only Idea Briefs and PRMs")
    return artifact_type


def _effective_type_sql(alias: str = "d") -> str:
    return f"COALESCE(NULLIF(json_extract({alias}.metadata_json, '$.document_type'), ''), a.type)"


def _readiness(row: sqlite3.Row) -> str:
    document_state = str(row["lifecycle_state"])
    outcome_state = str(row["outcome_lifecycle"])
    reconciliation = str(row["reconciliation_state"])
    if document_state in TERMINAL_DOCUMENT_STATES or (
        outcome_state == "terminal" and reconciliation == "reconciled"
    ):
        return "terminal"
    if document_state == "blocked" or outcome_state == "blocked":
        return "blocked"
    if document_state in {"parked", "deferred"}:
        return "waiting"
    if document_state == "working" or outcome_state == "working":
        return "working"
    return "ready"


def _document_rows(connection: sqlite3.Connection, artifact_type: str) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            f"""
            SELECT d.id, d.visible_id, d.title, d.lifecycle_state, d.updated_at,
                   COALESCE((
                       SELECT c.lifecycle_state FROM cycle AS c
                       WHERE c.origin_artifact_id = d.id
                       ORDER BY c.opened_at DESC, c.id DESC LIMIT 1
                   ), 'unknown') AS outcome_lifecycle,
                   COALESCE((
                       SELECT r.state FROM reconciliation AS r
                       JOIN cycle AS c ON c.id = r.cycle_id
                       WHERE c.origin_artifact_id = d.id
                       ORDER BY c.opened_at DESC, r.compared_at DESC, r.id DESC LIMIT 1
                   ), 'open') AS reconciliation_state
            FROM document AS d JOIN artifact AS a ON a.id = d.id
            WHERE {_effective_type_sql()} = ?
            ORDER BY d.updated_at DESC, d.visible_id DESC
            """,
            (artifact_type,),
        )
    )


def _override_chain(connection: sqlite3.Connection, all_ids: set[str]) -> tuple[list[str], list[sqlite3.Row]]:
    edges = list(
        connection.execute(
            "SELECT id, from_artifact_id, to_artifact_id, created_revision FROM relationship "
            "WHERE relation_type=? AND retired_revision IS NULL ORDER BY created_revision, id",
            (RELATION,),
        )
    )
    edges = [
        edge
        for edge in edges
        if str(edge["from_artifact_id"]) in all_ids and str(edge["to_artifact_id"]) in all_ids
    ]
    if not edges:
        return [], []
    successors: dict[str, str] = {}
    predecessors: dict[str, str] = {}
    for edge in edges:
        source, target = str(edge["from_artifact_id"]), str(edge["to_artifact_id"])
        if source in successors or target in predecessors:
            raise PlanningOrderError("owner planning override is not a single ordered chain")
        successors[source] = target
        predecessors[target] = source
    heads = sorted(set(successors) - set(predecessors))
    if len(heads) != 1:
        raise PlanningOrderError("owner planning override contains a cycle or disconnected chains")
    chain: list[str] = []
    current = heads[0]
    while current not in chain:
        chain.append(current)
        if current not in successors:
            break
        current = successors[current]
    if len(chain) != len(set(successors) | set(predecessors)):
        raise PlanningOrderError("owner planning override contains a cycle or disconnected chains")
    return chain, edges


def projection_for_connection(connection: sqlite3.Connection, artifact_type: str) -> dict[str, Any]:
    artifact_type = normalize_type(artifact_type)
    rows = _document_rows(connection, artifact_type)
    all_ids = {str(row["id"]) for row in rows}
    active_rows = [row for row in rows if _readiness(row) != "terminal"]
    base_index = {str(row["id"]): index for index, row in enumerate(rows)}
    derived_rows = sorted(
        active_rows,
        key=lambda row: (READINESS_RANK[_readiness(row)], base_index[str(row["id"])]),
    )
    derived_ids = [str(row["id"]) for row in derived_rows]
    owner_chain, edges = _override_chain(connection, all_ids)
    active_ids = set(derived_ids)
    owner_ids = [artifact_id for artifact_id in owner_chain if artifact_id in active_ids]
    ordered_ids = [*owner_ids, *(artifact_id for artifact_id in derived_ids if artifact_id not in owner_ids)]
    row_by_id = {str(row["id"]): row for row in rows}
    items = []
    for position, artifact_id in enumerate(ordered_ids, start=1):
        row = row_by_id[artifact_id]
        items.append(
            {
                "artifact_id": artifact_id,
                "visible_id": str(row["visible_id"]),
                "title": str(row["title"]),
                "artifact_type": artifact_type,
                "position": position,
                "order_source": "owner" if artifact_id in owner_ids else "derived",
                "readiness": _readiness(row),
                "updated_at": str(row["updated_at"]),
            }
        )
    current_revision = int(connection.execute("SELECT current_revision FROM state_meta WHERE id=1").fetchone()[0])
    token_material = {
        "artifact_type": artifact_type,
        "current_revision": current_revision,
        "documents": [
            [str(row["id"]), str(row["visible_id"]), str(row["lifecycle_state"]), str(row["updated_at"])]
            for row in rows
        ],
        "edges": [
            [str(edge["id"]), str(edge["from_artifact_id"]), str(edge["to_artifact_id"]), int(edge["created_revision"])]
            for edge in edges
        ],
    }
    state_token = hashlib.sha256(
        json.dumps(token_material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": 1,
        "kind": "tool-shed-planning-order",
        "artifact_type": artifact_type,
        "state_token": state_token,
        "database_revision": current_revision,
        "override_active": bool(owner_chain),
        "items": items,
        "writes_performed": False,
    }


def status(workspace: Path, artifact_type: str, *, database: Path | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    path = require_path_within(workspace, database or hybrid_state.database_path(workspace))
    with contextlib.closing(hybrid_state.connect(path, writable=False)) as connection:
        checked = document_store.audit_connection(workspace, connection)
        if checked["classification"] in {"INVALID", "UNJOURNALED", "UNMANAGED_REVIEW"}:
            raise PlanningOrderError(f"planning order read refused from {checked['classification']}")
        return projection_for_connection(connection, artifact_type)


def _retire_override_edges(
    connection: sqlite3.Connection, artifact_type: str, revision: int
) -> None:
    connection.execute(
        f"""
        UPDATE relationship SET retired_revision=?
        WHERE relation_type=? AND retired_revision IS NULL
          AND from_artifact_id IN (
              SELECT d.id FROM document AS d JOIN artifact AS a ON a.id=d.id
              WHERE {_effective_type_sql()}=?
          )
        """,
        (revision, RELATION, artifact_type),
    )


def set_order(
    workspace: Path,
    *,
    project_binding: str,
    artifact_type: str,
    ordered_ids: list[str],
    expected_token: str,
    actor: str,
    database: Path | None = None,
) -> dict[str, Any]:
    artifact_type = normalize_type(artifact_type)
    if len(ordered_ids) != len(set(ordered_ids)):
        raise PlanningOrderError("owner planning order contains duplicate IDs")

    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        current = projection_for_connection(connection, artifact_type)
        if current["state_token"] != expected_token:
            raise PlanningOrderError("planning order state token is stale")
        current_ids = [item["visible_id"] for item in current["items"]]
        if set(ordered_ids) != set(current_ids) or len(ordered_ids) != len(current_ids):
            raise PlanningOrderError("owner planning order must contain every current non-terminal ID exactly once")
        artifact_by_visible = {item["visible_id"]: item["artifact_id"] for item in current["items"]}
        _retire_override_edges(connection, artifact_type, revision)
        for source, target in zip(ordered_ids, ordered_ids[1:]):
            connection.execute(
                "INSERT INTO relationship VALUES (?, ?, ?, ?, ?, ?, NULL)",
                (
                    str(uuid.uuid4()),
                    artifact_by_visible[source],
                    RELATION,
                    artifact_by_visible[target],
                    PROVENANCE,
                    revision,
                ),
            )
        return {"artifact_type": artifact_type, "ordered_ids": ordered_ids, "override_active": len(ordered_ids) > 1}

    return document_store.managed_write(
        workspace,
        project_binding=project_binding,
        command="planning-order-set",
        actor=actor,
        callback=apply,
        database=database,
    )


def reset_order(
    workspace: Path,
    *,
    project_binding: str,
    artifact_type: str,
    expected_token: str,
    actor: str,
    database: Path | None = None,
) -> dict[str, Any]:
    artifact_type = normalize_type(artifact_type)

    def existing(connection: sqlite3.Connection) -> dict[str, Any] | None:
        current = projection_for_connection(connection, artifact_type)
        if current["state_token"] != expected_token:
            raise PlanningOrderError("planning order state token is stale")
        if not current["override_active"]:
            return {"artifact_type": artifact_type, "override_active": False, "idempotent": True}
        return None

    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        _retire_override_edges(connection, artifact_type, revision)
        return {"artifact_type": artifact_type, "override_active": False, "idempotent": False}

    return document_store.managed_write(
        workspace,
        project_binding=project_binding,
        command="planning-order-reset",
        actor=actor,
        callback=apply,
        existing=existing,
        database=database,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--database")
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    status_parser = commands.add_parser("status")
    status_parser.add_argument("--type", required=True)
    set_parser = commands.add_parser("set")
    set_parser.add_argument("--type", required=True)
    set_parser.add_argument("--ids", nargs="+", required=True)
    set_parser.add_argument("--expect", required=True)
    set_parser.add_argument("--project-binding", required=True)
    set_parser.add_argument("--actor", default="operator")
    move_parser = commands.add_parser("move")
    move_parser.add_argument("identity")
    move_parser.add_argument("--position", required=True, type=int)
    move_parser.add_argument("--type", required=True)
    move_parser.add_argument("--expect", required=True)
    move_parser.add_argument("--project-binding", required=True)
    move_parser.add_argument("--actor", default="operator")
    reset_parser = commands.add_parser("reset")
    reset_parser.add_argument("--type", required=True)
    reset_parser.add_argument("--expect", required=True)
    reset_parser.add_argument("--project-binding", required=True)
    reset_parser.add_argument("--actor", default="operator")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        workspace = resolved_workspace(Path(args.workspace))
        database = Path(args.database) if args.database else None
        if database and not database.is_absolute():
            database = workspace / database
        if args.command == "status":
            result = status(workspace, args.type, database=database)
        elif args.command == "set":
            result = set_order(
                workspace,
                project_binding=args.project_binding,
                artifact_type=args.type,
                ordered_ids=args.ids,
                expected_token=args.expect,
                actor=args.actor,
                database=database,
            )
        elif args.command == "move":
            current = status(workspace, args.type, database=database)
            if current["state_token"] != args.expect:
                raise PlanningOrderError("planning order state token is stale")
            ids = [item["visible_id"] for item in current["items"]]
            if args.identity not in ids:
                raise PlanningOrderError(f"planning-order ID not found: {args.identity}")
            ids.remove(args.identity)
            position = min(max(args.position, 1), len(ids) + 1)
            ids.insert(position - 1, args.identity)
            result = set_order(
                workspace,
                project_binding=args.project_binding,
                artifact_type=args.type,
                ordered_ids=ids,
                expected_token=args.expect,
                actor=args.actor,
                database=database,
            )
        else:
            result = reset_order(
                workspace,
                project_binding=args.project_binding,
                artifact_type=args.type,
                expected_token=args.expect,
                actor=args.actor,
                database=database,
            )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (
        PlanningOrderError,
        document_store.DocumentStoreError,
        hybrid_state.HybridStateError,
        ProjectIdentityError,
        OSError,
        ValueError,
        sqlite3.DatabaseError,
    ) as error:
        print(f"Planning order operation failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
