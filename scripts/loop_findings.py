#!/usr/bin/env python3
"""Discover, persist, audit, and resolve bounded outcome-loop findings."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import contextlib
import hashlib
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any, Sequence

import document_store
import hybrid_state
from loop_findings_schema import (
    HYBRID_SCHEMA_VERSION,
    LOOP_FINDING_SCHEMA_VERSION,
    LOOP_FINDING_TABLES,
    create_loop_finding_schema,
    loop_finding_migration_digest,
)
from project_identity import load_project_identity, require_project_binding, resolved_workspace


SCHEMA_VERSION = 1
DISCOVERY_VERSION = "loop-findings-v1"
ZERO_DIGEST = "0" * 64
MAX_ACTIVE_REPORT = 50
MAX_RECENT_RESOLVED_REPORT = 50


class LoopFindingError(RuntimeError):
    pass


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='table'")}


def _body_status(body: str) -> str:
    for line in body.splitlines():
        if line.casefold().startswith("status:"):
            return line.split(":", 1)[1].strip().casefold()
    return ""


def discover_candidates(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return the controlled current finding set without mutating authority."""
    candidates: list[dict[str, Any]] = []
    rows = connection.execute(
        "SELECT d.id, d.visible_id, d.lifecycle_state, a.current_path, d.current_revision, "
        "a.type AS stored_type, r.metadata_json, r.body_markdown "
        "FROM document d JOIN artifact a ON a.id=d.id "
        "JOIN document_revision r ON r.document_id=d.id AND r.revision_number=d.current_revision "
        "ORDER BY d.visible_id"
    ).fetchall()
    for row in rows:
        metadata = json.loads(row["metadata_json"])
        effective_type = str(metadata.get("document_type") or row["stored_type"])
        if (
            effective_type != "idea-brief"
            or str(row["lifecycle_state"]) != "active"
            or _body_status(str(row["body_markdown"])) != "promoted"
        ):
            continue
        cycle = connection.execute(
            "SELECT c.id, c.lifecycle_state FROM cycle c WHERE c.origin_artifact_id=? OR EXISTS ("
            "SELECT 1 FROM relationship rel WHERE rel.from_artifact_id=c.origin_artifact_id "
            "AND rel.to_artifact_id=? AND rel.relation_type='historical-overlay-for' "
            "AND rel.retired_revision IS NULL) OR EXISTS (SELECT 1 FROM evidence_reference er "
            "WHERE er.cycle_id=c.id AND er.kind='historical-origin' AND er.reference=?) "
            "ORDER BY c.opened_at DESC, c.id DESC LIMIT 1",
            (row["id"], row["id"], row["current_path"]),
        ).fetchone()
        if cycle is None or str(cycle["lifecycle_state"]) != "terminal":
            continue
        reconciliation = connection.execute(
            "SELECT r.state, ov.disposition FROM reconciliation r "
            "JOIN outcome_verdict ov ON ov.id=r.verdict_id WHERE r.cycle_id=? "
            "ORDER BY r.compared_at DESC, r.id DESC LIMIT 1",
            (cycle["id"],),
        ).fetchone()
        if reconciliation is None or str(reconciliation["state"]) != "reconciled":
            continue
        if str(reconciliation["disposition"]) not in {"satisfied", "superseded"}:
            continue
        expected = "superseded" if reconciliation["disposition"] == "superseded" else "completed"
        key_material = {
            "category": "semantic-lifecycle-drift",
            "reason_code": "PROMOTED_IDEA_LIFECYCLE_STALE",
            "subject_artifact_id": str(row["id"]),
            "expected_state": expected,
        }
        finding_key = _digest(key_material)
        candidates.append(
            {
                "finding_key": finding_key,
                "visible_id": f"LOOP-{finding_key[:12].upper()}",
                "category": "semantic-lifecycle-drift",
                "severity": "attention",
                "reason_code": "PROMOTED_IDEA_LIFECYCLE_STALE",
                "subject_artifact_id": str(row["id"]),
                "subject_visible_id": str(row["visible_id"]),
                "observed_state": "active",
                "expected_state": expected,
                "command": f"ts: resolve loop LOOP-{finding_key[:12].upper()}",
            }
        )
    return candidates


def candidate_digest(candidates: list[dict[str, Any]]) -> str:
    return _digest(sorted(candidates, key=lambda item: item["finding_key"]))


def synchronize_findings(connection: sqlite3.Connection, *, revision: int) -> dict[str, Any]:
    """Refresh persisted findings inside the caller's managed transaction."""
    if int(connection.execute("PRAGMA user_version").fetchone()[0]) != HYBRID_SCHEMA_VERSION:
        return {"applicable": False, "active_count": 0, "resolved_count": 0, "recurrence_count": 0}
    if not set(LOOP_FINDING_TABLES) <= _tables(connection):
        raise LoopFindingError("schema 4 is missing loop-finding authority tables")
    candidates = discover_candidates(connection)
    by_key = {item["finding_key"]: item for item in candidates}
    existing = {
        str(row["finding_key"]): row
        for row in connection.execute("SELECT * FROM loop_finding ORDER BY finding_key")
    }
    stamp = hybrid_state.now()
    project_id = str(connection.execute("SELECT project_id FROM state_meta WHERE id=1").fetchone()[0])
    recurrences = 0
    for key, item in sorted(by_key.items()):
        row = existing.get(key)
        if row is None:
            finding_id = hybrid_state.stable_uuid(project_id, f"loop-finding:{key}")
            connection.execute(
                "INSERT INTO loop_finding VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, NULL, 0, ?)",
                (
                    finding_id,
                    item["visible_id"],
                    key,
                    item["category"],
                    item["severity"],
                    item["reason_code"],
                    item["subject_artifact_id"],
                    item["subject_visible_id"],
                    item["observed_state"],
                    item["expected_state"],
                    revision,
                    stamp,
                    stamp,
                    item["command"],
                ),
            )
        else:
            recurring = str(row["state"]) == "resolved"
            recurrences += int(recurring)
            connection.execute(
                "UPDATE loop_finding SET severity=?, observed_state=?, expected_state=?, state='active', "
                "source_revision=?, last_observed_at=?, resolved_at=NULL, recurrence_count=recurrence_count+?, command=? "
                "WHERE finding_key=?",
                (
                    item["severity"],
                    item["observed_state"],
                    item["expected_state"],
                    revision,
                    stamp,
                    int(recurring),
                    item["command"],
                    key,
                ),
            )
    for key, row in existing.items():
        if key not in by_key and str(row["state"]) == "active":
            connection.execute(
                "UPDATE loop_finding SET state='resolved', source_revision=?, last_observed_at=?, resolved_at=? "
                "WHERE finding_key=?",
                (revision, stamp, stamp, key),
            )
    digest = candidate_digest(candidates)
    connection.execute(
        "UPDATE loop_finding_meta SET discovery_version=?, last_source_revision=?, last_source_digest=?, updated_at=? WHERE id=1",
        (DISCOVERY_VERSION, revision, digest, stamp),
    )
    counts = {
        str(row["state"]): int(row["count"])
        for row in connection.execute("SELECT state, COUNT(*) AS count FROM loop_finding GROUP BY state")
    }
    return {
        "applicable": True,
        "active_count": counts.get("active", 0),
        "resolved_count": counts.get("resolved", 0),
        "recurrence_count": recurrences,
        "source_revision": revision,
        "source_digest": digest,
    }


def _public_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "finding_id": str(row["visible_id"]),
        "category": str(row["category"]),
        "severity": str(row["severity"]),
        "reason_code": str(row["reason_code"]),
        "subject_id": str(row["subject_visible_id"]),
        "observed_state": str(row["observed_state"]),
        "expected_state": str(row["expected_state"]),
        "state": str(row["state"]),
        "source_revision": int(row["source_revision"]),
        "first_observed_at": str(row["first_observed_at"]),
        "last_observed_at": str(row["last_observed_at"]),
        "resolved_at": str(row["resolved_at"]) if row["resolved_at"] else None,
        "recurrence_count": int(row["recurrence_count"]),
        "command": str(row["command"]),
    }


def audit(workspace: Path, *, database: Path | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    path = database or hybrid_state.database_path(workspace)
    with contextlib.closing(hybrid_state.connect(path, writable=False)) as connection:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version != HYBRID_SCHEMA_VERSION or not set(LOOP_FINDING_TABLES) <= _tables(connection):
            raise LoopFindingError(f"loop findings require Hybrid schema 4; found {version}")
        meta = connection.execute("SELECT * FROM loop_finding_meta WHERE id=1").fetchone()
        candidates = discover_candidates(connection)
        rows = list(
            connection.execute(
                "SELECT * FROM loop_finding ORDER BY CASE state WHEN 'active' THEN 0 ELSE 1 END, "
                "last_observed_at DESC, visible_id"
            )
        )
        current_revision = int(hybrid_state.meta_row(connection)["current_revision"])
        current_digest = candidate_digest(candidates)
        fresh = bool(
            meta
            and int(meta["last_source_revision"]) == current_revision
            and str(meta["last_source_digest"]) == current_digest
        )
    findings = [_public_row(row) for row in rows]
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-loop-finding-audit",
        "discovery_version": DISCOVERY_VERSION,
        "database_revision": current_revision,
        "fresh": fresh,
        "active_count": sum(item["state"] == "active" for item in findings),
        "resolved_count": sum(item["state"] == "resolved" for item in findings),
        "findings": findings,
        "writes_performed": False,
    }


def report_projection(workspace: Path) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)) as connection:
        if int(connection.execute("PRAGMA user_version").fetchone()[0]) < HYBRID_SCHEMA_VERSION:
            return {"total_active_count": 0, "total_resolved_count": 0, "truncated": False, "findings": []}
    result = audit(workspace)
    active = [item for item in result["findings"] if item["state"] == "active"][:MAX_ACTIVE_REPORT]
    resolved = [item for item in result["findings"] if item["state"] == "resolved"][:MAX_RECENT_RESOLVED_REPORT]
    projected = [*active, *resolved]
    return {
        "total_active_count": result["active_count"],
        "total_resolved_count": result["resolved_count"],
        "truncated": len(active) < result["active_count"] or len(resolved) < result["resolved_count"],
        "findings": projected,
    }


def resolve(workspace: Path, finding_id: str) -> dict[str, Any]:
    result = audit(workspace)
    selected = next(
        (item for item in result["findings"] if item["finding_id"].casefold() == finding_id.casefold()),
        None,
    )
    if selected is None:
        raise LoopFindingError("loop finding was not found in this workspace")
    with contextlib.closing(
        hybrid_state.connect(hybrid_state.database_path(resolved_workspace(workspace)), writable=False)
    ) as connection:
        current_ids = {item["visible_id"] for item in discover_candidates(connection)}
    current = selected["finding_id"] in current_ids
    if selected["state"] == "resolved" or not current:
        status = "already-resolved"
        action = "none"
    else:
        status = "actionable"
        action = "correct-document-lifecycle"
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-loop-finding-resolution",
        "status": status,
        "finding": selected,
        "recommended_action": action,
        "authority": "local-hybrid-sqlite",
        "fresh_read": True,
        "writes_performed": False,
    }


def migrate(workspace: Path, *, project_binding: str) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    require_project_binding(workspace, project_binding, operation="hybrid-state")
    source = hybrid_state.database_path(workspace)
    shadow = source.with_name(source.name + ".loop-schema4.next")
    if shadow.exists():
        raise LoopFindingError(f"stale migration shadow requires review: {shadow.relative_to(workspace)}")
    with contextlib.closing(hybrid_state.connect(source, writable=False)) as probe:
        entrance = document_store.audit_connection(workspace, probe)
        if entrance["classification"] not in {"CLEAN", "VALID_DIRTY"}:
            raise LoopFindingError(f"migration refused from {entrance['classification']}")
        if int(probe.execute("PRAGMA user_version").fetchone()[0]) != 3:
            raise LoopFindingError("loop-finding migration requires Hybrid schema 3")
        expected_revision = int(entrance["current_revision"])
        expected_digest = str(entrance["domain_digest"])
    backup_root = workspace / ".tool-shed/backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = backup_root / f"loop-findings-schema3-r{expected_revision}.sqlite3"
    if backup.exists():
        raise LoopFindingError(f"migration backup already exists and requires review: {backup.relative_to(workspace)}")
    with hybrid_state.WorkspaceLock(hybrid_state.lock_path(workspace)):
        with contextlib.closing(hybrid_state.connect(source)) as live:
            current = document_store.audit_connection(workspace, live)
            if current["current_revision"] != expected_revision or current["domain_digest"] != expected_digest:
                raise LoopFindingError("loop-finding migration source state changed")
            with contextlib.closing(sqlite3.connect(backup)) as target:
                live.backup(target)
            with contextlib.closing(sqlite3.connect(shadow)) as target:
                live.backup(target)
        try:
            with contextlib.closing(hybrid_state.connect(shadow)) as target:
                target.execute("BEGIN IMMEDIATE")
                create_loop_finding_schema(target, include_triggers=True)
                revision = expected_revision + 1
                operation_id = str(uuid.uuid4())
                stamp = hybrid_state.now()
                target.execute(
                    "INSERT INTO managed_operation VALUES (?, ?, 'loop-findings-schema4-migrate', 'loop-findings', ?, NULL, NULL, 0, 'active')",
                    (operation_id, revision, stamp),
                )
                target.execute("INSERT INTO active_operation VALUES (1, ?, ?)", (operation_id, revision))
                target.execute("UPDATE state_meta SET schema_version=4 WHERE id=1")
                target.execute("PRAGMA user_version=4")
                target.execute(
                    "INSERT INTO loop_finding_meta VALUES (1, ?, ?, 0, ?, ?)",
                    (LOOP_FINDING_SCHEMA_VERSION, DISCOVERY_VERSION, ZERO_DIGEST, stamp),
                )
                synchronize_findings(target, revision=revision)
                target.execute(
                    "INSERT INTO migration_ledger VALUES (?, 3, 4, ?, ?, ?, 'complete', ?, ?)",
                    (
                        str(uuid.uuid4()),
                        loop_finding_migration_digest(),
                        expected_digest,
                        backup.relative_to(workspace).as_posix(),
                        stamp,
                        stamp,
                    ),
                )
                target.execute("DELETE FROM active_operation WHERE id=1")
                target.execute(
                    "UPDATE managed_operation SET status='complete', committed_at=? WHERE id=?",
                    (hybrid_state.now(), operation_id),
                )
                source_digest = document_store.domain_digest(target)
                target.execute(
                    "UPDATE state_meta SET current_revision=?, last_verified_revision=?, source_digest=?, "
                    "schema_trigger_digest=?, dirty=1, checkpoint_pending=1 WHERE id=1",
                    (revision, revision, source_digest, hybrid_state.schema_digest(target)),
                )
                target.commit()
                checked = document_store.audit_connection(workspace, target)
                if checked["classification"] != "VALID_DIRTY":
                    raise LoopFindingError(
                        f"loop-finding migration shadow failed audit: {checked['classification']}: "
                        + "; ".join(checked["findings"])
                    )
                target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            os.replace(shadow, source)
        except BaseException:
            shadow.unlink(missing_ok=True)
            raise
    result = audit(workspace)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-loop-finding-migration",
        "from_schema": 3,
        "to_schema": 4,
        "backup": backup.relative_to(workspace).as_posix(),
        "backup_sha256": hybrid_state.file_sha256(backup),
        "revision": result["database_revision"],
        "active_count": result["active_count"],
        "writes_performed": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    migrate_parser = commands.add_parser("migrate")
    migrate_parser.add_argument("--project-binding", required=True)
    commands.add_parser("audit")
    resolve_parser = commands.add_parser("resolve")
    resolve_parser.add_argument("finding_id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        workspace = Path(args.workspace)
        if args.command == "migrate":
            result = migrate(workspace, project_binding=args.project_binding)
        elif args.command == "audit":
            result = audit(workspace)
        else:
            result = resolve(workspace, args.finding_id)
    except (LoopFindingError, document_store.DocumentStoreError, hybrid_state.HybridStateError) as error:
        result = {
            "schema_version": SCHEMA_VERSION,
            "kind": "tool-shed-loop-finding-error",
            "error": str(error),
            "writes_performed": False,
        }
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(f"Loop finding operation failed: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
