#!/usr/bin/env python3
"""Managed database-owned Tool Shed document operations."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import contextlib
import copy
import difflib
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable, Sequence

import hybrid_state
from document_contract import GENERATED
from document_store_schema import (
    DOCUMENT_PORTABLE_TABLES,
    DOCUMENT_SCHEMA_VERSION,
    DOCUMENT_TABLES,
    HYBRID_SCHEMA_VERSION,
    create_document_schema,
    document_migration_digest,
)
from hybrid_state_schema import PORTABLE_TABLES
from project_identity import ProjectIdentityError, require_path_within, require_project_binding, resolved_workspace


OPERATION = "hybrid-state"
CHECKPOINT_KIND = "tool-shed-document-state-checkpoint"
CHECKPOINT_FORMAT = 2
VISIBLE_ID = re.compile(r"^(?P<namespace>[A-Z]{2,5})-(?P<number>[0-9]{4,})$")
EDIT_HEADER = "tool_shed_document: 1"
LIFECYCLES = ("active", "working", "blocked", "parked", "deferred", "completed", "abandoned", "superseded")


class DocumentStoreError(RuntimeError):
    pass


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='table'")}


def domain_tables(connection: sqlite3.Connection) -> tuple[str, ...]:
    present = _tables(connection)
    return tuple(table for table in (*hybrid_state.DOMAIN_TABLES, *DOCUMENT_TABLES) if table in present)


def portable_tables(connection: sqlite3.Connection) -> tuple[str, ...]:
    present = _tables(connection)
    return tuple(table for table in (*PORTABLE_TABLES, *DOCUMENT_PORTABLE_TABLES) if table in present)


def domain_digest(connection: sqlite3.Connection) -> str:
    tables = (table for table in domain_tables(connection) if table != "workspace")
    return hashlib.sha256(canonical_bytes({table: hybrid_state.table_rows(connection, table) for table in tables})).hexdigest()


def _body_header_value(body: str, field: str) -> str | None:
    prefix = field + ":"
    for line in body.splitlines()[:80]:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def _semantic_document_findings(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Report recoverable document/domain drift without invalidating managed-write safety."""
    if not set(DOCUMENT_TABLES).issubset(_tables(connection)):
        return []
    findings: list[dict[str, Any]] = []
    rows = connection.execute(
        "SELECT d.id, d.visible_id, d.namespace, d.lifecycle_state, d.metadata_json, "
        "a.type AS stored_type, a.current_path, r.body_markdown FROM document d JOIN artifact a ON a.id=d.id "
        "JOIN document_revision r ON r.document_id=d.id AND r.revision_number=d.current_revision "
        "ORDER BY d.visible_id"
    ).fetchall()
    for row in rows:
        metadata = json.loads(row["metadata_json"])
        declared_type = str(metadata.get("document_type") or "").strip()
        effective_type = declared_type or str(row["stored_type"])
        if declared_type and declared_type != row["stored_type"]:
            findings.append({
                "code": "DOCUMENT_TYPE_DRIFT",
                "visible_id": row["visible_id"],
                "stored_type": row["stored_type"],
                "declared_type": declared_type,
                "message": f"{row['visible_id']} stores type {row['stored_type']} but declares {declared_type}",
            })
        idea_status = (_body_header_value(row["body_markdown"], "Status") or "").casefold()
        if effective_type != "idea-brief" or row["lifecycle_state"] != "active" or idea_status != "promoted":
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
        if cycle is None:
            findings.append({
                "code": "PROMOTED_IDEA_MISSING_OUTCOME",
                "visible_id": row["visible_id"],
                "idea_status": idea_status,
                "document_lifecycle": row["lifecycle_state"],
                "message": f"{row['visible_id']} is promoted and active but has no owning outcome loop",
            })
            continue
        reconciliation = connection.execute(
            "SELECT r.state, ov.disposition FROM reconciliation r "
            "JOIN outcome_verdict ov ON ov.id=r.verdict_id WHERE r.cycle_id=? "
            "ORDER BY r.compared_at DESC, r.id DESC LIMIT 1",
            (cycle["id"],),
        ).fetchone()
        if cycle["lifecycle_state"] == "terminal" and reconciliation and reconciliation["state"] == "reconciled":
            expected = "superseded" if reconciliation["disposition"] == "superseded" else "completed"
            findings.append({
                "code": "PROMOTED_IDEA_LIFECYCLE_STALE",
                "visible_id": row["visible_id"],
                "cycle_id": cycle["id"],
                "disposition": reconciliation["disposition"],
                "document_lifecycle": row["lifecycle_state"],
                "expected_lifecycle": expected,
                "message": f"{row['visible_id']} has a terminal reconciled outcome but remains active",
            })
    return findings


def audit_connection(workspace: Path, connection: sqlite3.Connection) -> dict[str, Any]:
    findings: list[str] = []
    integrity = [str(row[0]) for row in connection.execute("PRAGMA integrity_check")]
    if integrity != ["ok"]:
        findings.extend(f"integrity: {item}" for item in integrity)
    foreign = list(connection.execute("PRAGMA foreign_key_check"))
    if foreign:
        findings.append(f"foreign-key violations: {len(foreign)}")
    user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if user_version != HYBRID_SCHEMA_VERSION:
        findings.append(f"document operations require Hybrid schema {HYBRID_SCHEMA_VERSION}; found {user_version}")
    meta = hybrid_state.meta_row(connection)
    if int(meta["schema_version"]) != HYBRID_SCHEMA_VERSION:
        findings.append("state metadata schema version differs from PRAGMA user_version")
    required = set(DOCUMENT_TABLES)
    if not required.issubset(_tables(connection)):
        findings.append(f"missing document tables: {sorted(required - _tables(connection))}")
    current_schema_digest = hybrid_state.schema_digest(connection)
    if meta["schema_trigger_digest"] != current_schema_digest:
        findings.append("schema or accounting-trigger digest changed")
    active = int(connection.execute("SELECT count(*) FROM active_operation").fetchone()[0])
    if active:
        findings.append("an incomplete managed operation context remains active")
    duplicate_relationships = hybrid_state.duplicate_active_relationship_count(connection)
    if duplicate_relationships:
        findings.append(f"duplicate active relationship edges: {duplicate_relationships}")
    hard_finding_count = len(findings)
    mismatches = int(connection.execute(
        "SELECT count(*) FROM document d JOIN document_revision r ON r.document_id=d.id AND r.revision_number=d.current_revision "
        "WHERE d.title<>r.title OR d.lifecycle_state<>r.lifecycle_state OR d.metadata_json<>r.metadata_json OR d.body_sha256<>r.body_sha256"
    ).fetchone()[0]) if required.issubset(_tables(connection)) else 0
    if mismatches:
        findings.append(f"current document/revision mismatches: {mismatches}")
    current_revision = int(meta["current_revision"])
    observed = domain_digest(connection) if hard_finding_count == 0 else None
    changed = observed is not None and observed != meta["source_digest"]
    unmanaged = bool(meta["unmanaged_write_detected"])
    if hard_finding_count:
        classification = "INVALID"
    elif unmanaged:
        classification = "UNMANAGED_REVIEW"
        findings.append("unmanaged writes require an explicit material-change disposition")
    elif mismatches:
        classification = "UNJOURNALED"
        findings.append("document current/revision parity changed without managed disposition")
    elif changed and not unmanaged:
        classification = "UNJOURNALED"
        findings.append("domain state changed without complete revision-ledger evidence")
    elif current_revision > int(meta["last_checkpoint_revision"]):
        classification = "VALID_DIRTY"
    else:
        classification = "CLEAN"
    semantic_findings = _semantic_document_findings(connection)
    return {
        "schema_version": DOCUMENT_SCHEMA_VERSION,
        "hybrid_schema": user_version,
        "kind": "tool-shed-document-store-audit",
        "classification": classification,
        "findings": findings,
        "semantic_findings": semantic_findings,
        "semantic_finding_count": len(semantic_findings),
        "current_revision": current_revision,
        "last_checkpoint_revision": int(meta["last_checkpoint_revision"]),
        "domain_digest": observed,
        "unmanaged_write_detected": unmanaged,
        "storage_mode": meta["storage_mode"],
        "writes_performed": False,
    }


def audit(workspace: Path, database: Path | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    path = require_path_within(workspace, database or hybrid_state.database_path(workspace))
    with contextlib.closing(hybrid_state.connect(path)) as connection:
        return audit_connection(workspace, connection)


def is_authoritative(workspace: Path, database: Path | None = None) -> bool:
    """Return whether generated-document write authority has cut over to schema 2."""
    workspace = resolved_workspace(workspace)
    path = require_path_within(workspace, database or hybrid_state.database_path(workspace))
    if not path.is_file():
        return False
    with contextlib.closing(hybrid_state.connect(path, writable=False)) as connection:
        if int(connection.execute("PRAGMA user_version").fetchone()[0]) != HYBRID_SCHEMA_VERSION:
            return False
        meta = hybrid_state.meta_row(connection)
        return str(meta["storage_mode"]) == "hybrid"


def _replace_file(source: Path, destination: Path) -> None:
    with source.open("r+b") as handle:
        os.fsync(handle.fileno())
    os.replace(source, destination)


def migrate(workspace: Path, *, project_binding: str, database: Path | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    require_project_binding(workspace, project_binding, operation=OPERATION)
    source = require_path_within(workspace, database or hybrid_state.database_path(workspace))
    shadow = source.with_name(source.name + ".schema2-next")
    if shadow.exists():
        raise DocumentStoreError(f"stale migration shadow requires review: {shadow.relative_to(workspace)}")
    with hybrid_state.WorkspaceLock(hybrid_state.lock_path(workspace)):
        # Windows refuses to replace an open SQLite file. Keep the workspace
        # lock across promotion, but close the live connection after the
        # backup and before os.replace promotes the qualified shadow.
        with contextlib.closing(hybrid_state.connect(source)) as live:
            base = hybrid_state.audit_connection(workspace, live)
            if base["classification"] not in {"CLEAN", "VALID_DIRTY", "CHECKPOINT_DUE"}:
                raise DocumentStoreError(f"migration refused from {base['classification']}")
            if int(live.execute("PRAGMA user_version").fetchone()[0]) != 1:
                raise DocumentStoreError("migration requires Hybrid schema 1")
            with contextlib.closing(sqlite3.connect(shadow)) as target:
                live.backup(target)
                target.commit()
        try:
            with contextlib.closing(hybrid_state.connect(shadow)) as target:
                target.execute("BEGIN IMMEDIATE")
                create_document_schema(target, include_triggers=True)
                stamp = hybrid_state.now()
                target.execute(
                    "INSERT INTO migration_ledger VALUES (?, 1, 2, ?, ?, ?, 'complete', ?, ?)",
                    (str(uuid.uuid4()), document_migration_digest(), base["domain_digest"], source.relative_to(workspace).as_posix(), stamp, stamp),
                )
                target.execute("UPDATE state_meta SET schema_version=2 WHERE id=1")
                target.execute("PRAGMA user_version=2")
                target.execute(
                    "UPDATE state_meta SET source_digest=?, schema_trigger_digest=? WHERE id=1",
                    (domain_digest(target), hybrid_state.schema_digest(target)),
                )
                target.commit()
                checked = audit_connection(workspace, target)
                if checked["classification"] not in {"CLEAN", "VALID_DIRTY"}:
                    raise DocumentStoreError(f"migration shadow failed audit: {checked['classification']}")
                target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            _replace_file(shadow, source)
        except BaseException:
            shadow.unlink(missing_ok=True)
            raise
    result = audit(workspace, source)
    result.update({"kind": "tool-shed-document-store-migration", "from_schema": 1, "to_schema": 2, "writes_performed": True})
    return result


ManagedCallback = Callable[[sqlite3.Connection, int], Any]
ExistingCallback = Callable[[sqlite3.Connection], Any | None]


def managed_write(workspace: Path, *, project_binding: str, command: str, actor: str, callback: ManagedCallback, existing: ExistingCallback | None = None, database: Path | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    require_project_binding(workspace, project_binding, operation=OPERATION)
    path = require_path_within(workspace, database or hybrid_state.database_path(workspace))
    with hybrid_state.WorkspaceLock(hybrid_state.lock_path(workspace)), contextlib.closing(hybrid_state.connect(path)) as connection:
        entrance = audit_connection(workspace, connection)
        if entrance["classification"] not in {"CLEAN", "VALID_DIRTY"}:
            raise DocumentStoreError(f"managed mutation refused from {entrance['classification']}: {'; '.join(entrance['findings'])}")
        existing_result = existing(connection) if existing is not None else None
        if existing_result is not None:
            return {
                "schema_version": 1,
                "kind": "tool-shed-document-operation",
                "operation_id": None,
                "revision": entrance["current_revision"],
                "actual_writes": 0,
                "result": existing_result,
                "audit": entrance,
                "writes_performed": False,
            }
        operation_id = str(uuid.uuid4())
        stamp = hybrid_state.now()
        try:
            connection.execute("BEGIN IMMEDIATE")
            revision = int(connection.execute("SELECT current_revision + 1 FROM state_meta WHERE id=1").fetchone()[0])
            connection.execute(
                "INSERT INTO managed_operation VALUES (?, ?, ?, ?, ?, NULL, NULL, 0, 'active')",
                (operation_id, revision, command, actor, stamp),
            )
            connection.execute("INSERT INTO active_operation VALUES (1, ?, ?)", (operation_id, revision))
            value = callback(connection, revision)
            actual = int(connection.execute("SELECT actual_writes FROM managed_operation WHERE id=?", (operation_id,)).fetchone()[0])
            connection.execute("DELETE FROM active_operation WHERE id=1")
            connection.execute("UPDATE managed_operation SET status='complete', committed_at=? WHERE id=?", (hybrid_state.now(), operation_id))
            connection.execute(
                "UPDATE state_meta SET current_revision=?, last_verified_revision=?, source_digest=?, dirty=1, checkpoint_pending=1 WHERE id=1",
                (revision, revision, domain_digest(connection)),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        result = audit_connection(workspace, connection)
        if result["classification"] != "VALID_DIRTY":
            raise DocumentStoreError(f"managed mutation left {result['classification']}")
        response = {"schema_version": 1, "kind": "tool-shed-document-operation", "operation_id": operation_id, "revision": revision, "actual_writes": actual, "result": value, "audit": result, "writes_performed": True}
    try:
        import dashboard_reporter

        dashboard_reporter.enqueue_if_connected(workspace, reason="managed-document-update")
    except (ImportError, AttributeError):
        pass
    return response


def _parse_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or fallback
    return fallback


def _namespace_for(document_type: str) -> str:
    try:
        return GENERATED[document_type]
    except KeyError as error:
        raise DocumentStoreError(f"unsupported generated document type: {document_type}") from error


def _allocate(connection: sqlite3.Connection, namespace: str, assigned: int | None) -> int:
    row = connection.execute("SELECT next_number FROM document_namespace WHERE id=?", (namespace,)).fetchone()
    if row is None:
        connection.execute("INSERT INTO document_namespace VALUES (?, 1)", (namespace,))
        next_number = 1
    else:
        next_number = int(row[0])
    number = assigned if assigned is not None else next_number
    if number < 1:
        raise DocumentStoreError("visible ID number must be positive")
    if connection.execute("SELECT 1 FROM document WHERE namespace=? AND display_number=?", (namespace, number)).fetchone():
        raise DocumentStoreError(f"visible ID collision: {namespace}-{number:04d}")
    connection.execute("UPDATE document_namespace SET next_number=? WHERE id=?", (max(next_number, number + 1), namespace))
    return number


def import_document(workspace: Path, *, project_binding: str, source: Path, document_type: str, lifecycle: str, actor: str, reason: str, assigned_number: int | None = None, artifact_id: str | None = None, database: Path | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    require_project_binding(workspace, project_binding, operation=OPERATION)
    path = require_path_within(workspace, source if source.is_absolute() else workspace / source)
    raw = path.read_bytes()
    try:
        body = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise DocumentStoreError("document import requires UTF-8") from error
    relative = path.relative_to(workspace).as_posix()
    title = _parse_title(body, path.stem)
    namespace = _namespace_for(document_type)
    body_hash = hashlib.sha256(raw).hexdigest()
    database_path = require_path_within(workspace, database or hybrid_state.database_path(workspace))

    # A conversion replay is a read-only success when the exact retained source
    # was already imported.  Keep this outside managed_write so retries do not
    # create empty operations or advance the database revision.
    with contextlib.closing(hybrid_state.connect(database_path, writable=False)) as connection:
        existing = connection.execute(
            "SELECT dc.*, a.type AS artifact_type FROM document_conversion dc "
            "JOIN artifact a ON a.id=dc.artifact_id WHERE dc.source_path=?",
            (relative,),
        ).fetchone()
        if existing:
            expected_visible = f"{namespace}-{assigned_number:04d}" if assigned_number is not None else None
            conflicts = []
            if existing["source_sha256"] != body_hash:
                conflicts.append("source digest")
            if existing["artifact_type"] != document_type:
                conflicts.append("document type")
            if artifact_id is not None and existing["artifact_id"] != artifact_id:
                conflicts.append("artifact ID")
            if expected_visible is not None and existing["visible_id"] != expected_visible:
                conflicts.append("visible ID")
            if existing["status"] not in {"verified", "cutover"} or not existing["byte_parity"] or not existing["render_parity"]:
                conflicts.append("qualification state")
            if conflicts:
                raise DocumentStoreError("existing conversion conflicts with replay: " + ", ".join(conflicts))
            checked = audit_connection(workspace, connection)
            if checked["classification"] in {"INVALID", "UNJOURNALED"}:
                raise DocumentStoreError(f"idempotent import refused from {checked['classification']}")
            return {
                "schema_version": HYBRID_SCHEMA_VERSION,
                "kind": "tool-shed-hybrid-state-operation",
                "operation_id": None,
                "revision": checked["current_revision"],
                "actual_writes": 0,
                "result": {
                    "artifact_id": existing["artifact_id"],
                    "visible_id": existing["visible_id"],
                    "retained_source": relative,
                    "source_sha256": body_hash,
                    "idempotent": True,
                },
                "audit": checked,
                "writes_performed": False,
            }

    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        existing_conversion = connection.execute("SELECT * FROM document_conversion WHERE source_path=?", (relative,)).fetchone()
        if existing_conversion:
            if existing_conversion["source_sha256"] != body_hash:
                raise DocumentStoreError("retained source changed after conversion planning")
            return {"artifact_id": existing_conversion["artifact_id"], "visible_id": existing_conversion["visible_id"], "idempotent": True}
        assigned_artifact = artifact_id
        if assigned_artifact is None:
            prior = connection.execute("SELECT id FROM artifact WHERE current_path=?", (relative,)).fetchone()
            assigned_artifact = str(prior[0]) if prior else str(uuid.uuid4())
        artifact = connection.execute("SELECT * FROM artifact WHERE id=?", (assigned_artifact,)).fetchone()
        stamp = hybrid_state.now()
        if artifact is None:
            connection.execute(
                "INSERT INTO artifact VALUES (?, ?, NULL, ?, 'sqlite', ?, ?, ?, ?)",
                (assigned_artifact, document_type, relative, lifecycle, body_hash, stamp, stamp),
            )
        else:
            connection.execute(
                "UPDATE artifact SET type=?, authority_mode='sqlite', lifecycle_state=?, content_sha256=?, updated_at=? WHERE id=?",
                (document_type, lifecycle, body_hash, stamp, assigned_artifact),
            )
        number = _allocate(connection, namespace, assigned_number)
        visible = f"{namespace}-{number:04d}"
        metadata = json.dumps({"document_type": document_type, "retained_source": relative}, sort_keys=True, separators=(",", ":"))
        connection.execute(
            "INSERT INTO document VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)",
            (assigned_artifact, visible, namespace, number, title, lifecycle, metadata, body_hash, stamp, stamp),
        )
        connection.execute(
            "INSERT INTO document_revision VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), assigned_artifact, title, lifecycle, metadata, body, body_hash, actor, reason, revision, stamp),
        )
        connection.execute(
            "INSERT INTO document_path_alias VALUES (?, ?, ?, 'retained-source', ?, NULL)",
            (str(uuid.uuid4()), assigned_artifact, relative, revision),
        )
        connection.execute(
            "INSERT INTO document_conversion VALUES (?, ?, ?, ?, ?, 'generated', 'verified', 1, 1, ?, ?, ?)",
            (str(uuid.uuid4()), relative, body_hash, assigned_artifact, visible, revision, stamp, stamp),
        )
        return {"artifact_id": assigned_artifact, "visible_id": visible, "document_revision": 1, "retained_source": relative, "source_sha256": body_hash, "idempotent": False}

    return managed_write(workspace, project_binding=project_binding, command="document-import", actor=actor, callback=apply, database=database_path)


def _lookup(connection: sqlite3.Connection, identity: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT d.*, r.body_markdown FROM document d JOIN document_revision r ON r.document_id=d.id AND r.revision_number=d.current_revision WHERE d.id=? OR d.visible_id=?",
        (identity, identity),
    ).fetchone()
    if row is None:
        alias = connection.execute("SELECT document_id FROM document_path_alias WHERE path=? AND retired_revision IS NULL", (identity,)).fetchone()
        if alias:
            row = connection.execute(
                "SELECT d.*, r.body_markdown FROM document d JOIN document_revision r ON r.document_id=d.id AND r.revision_number=d.current_revision WHERE d.id=?",
                (alias[0],),
            ).fetchone()
    if row is None:
        raise DocumentStoreError(f"document not found: {identity}")
    return row


def show(workspace: Path, identity: str, *, database: Path | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    path = require_path_within(workspace, database or hybrid_state.database_path(workspace))
    with contextlib.closing(hybrid_state.connect(path, writable=False)) as connection:
        checked = audit_connection(workspace, connection)
        if checked["classification"] in {"INVALID", "UNJOURNALED"}:
            detail = "; ".join(checked["findings"])
            raise DocumentStoreError(f"read refused from {checked['classification']}: {detail}")
        row = _lookup(connection, identity)
        return {"schema_version": 1, "kind": "tool-shed-document", "artifact_id": row["id"], "visible_id": row["visible_id"], "document_revision": row["current_revision"], "database_revision": checked["current_revision"], "title": row["title"], "lifecycle": row["lifecycle_state"], "metadata": json.loads(row["metadata_json"]), "body_markdown": row["body_markdown"], "body_sha256": row["body_sha256"], "writes_performed": False}


def list_documents(workspace: Path, *, lifecycle: str | None = None, document_type: str | None = None, limit: int = 100, database: Path | None = None) -> dict[str, Any]:
    if not 1 <= limit <= 500:
        raise DocumentStoreError("list limit must be 1..500")
    workspace = resolved_workspace(workspace)
    path = require_path_within(workspace, database or hybrid_state.database_path(workspace))
    clauses, values = [], []
    if lifecycle:
        clauses.append("d.lifecycle_state=?"); values.append(lifecycle)
    if document_type:
        clauses.append("COALESCE(NULLIF(json_extract(d.metadata_json, '$.document_type'), ''), a.type)=?"); values.append(document_type)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with contextlib.closing(hybrid_state.connect(path, writable=False)) as connection:
        checked = audit_connection(workspace, connection)
        rows = [dict(row) for row in connection.execute(
            "SELECT d.id AS artifact_id, d.visible_id, "
            "COALESCE(NULLIF(json_extract(d.metadata_json, '$.document_type'), ''), a.type) AS type, "
            "a.type AS stored_type, d.title, d.lifecycle_state AS lifecycle, d.current_revision AS document_revision "
            "FROM document d JOIN artifact a ON a.id=d.id" + where + " ORDER BY d.lifecycle_state, d.visible_id LIMIT ?",
            (*values, limit),
        )]
    return {"schema_version": 1, "kind": "tool-shed-document-list", "database_revision": checked["current_revision"], "documents": rows, "count": len(rows), "writes_performed": False}


def search(workspace: Path, query: str, *, limit: int = 20, database: Path | None = None) -> dict[str, Any]:
    if not query.strip() or not 1 <= limit <= 100:
        raise DocumentStoreError("search needs a query and limit 1..100")
    workspace = resolved_workspace(workspace)
    path = require_path_within(workspace, database or hybrid_state.database_path(workspace))
    pattern = f"%{query.casefold()}%"
    with contextlib.closing(hybrid_state.connect(path, writable=False)) as connection:
        rows = [dict(row) for row in connection.execute(
            "SELECT d.id AS artifact_id, d.visible_id, a.type, d.title, d.lifecycle_state AS lifecycle, d.current_revision AS document_revision "
            "FROM document d JOIN artifact a ON a.id=d.id JOIN document_revision r ON r.document_id=d.id AND r.revision_number=d.current_revision "
            "WHERE lower(d.title) LIKE ? OR lower(r.body_markdown) LIKE ? ORDER BY d.visible_id LIMIT ?",
            (pattern, pattern, limit),
        )]
    return {"schema_version": 1, "kind": "tool-shed-document-search", "query": query, "documents": rows, "count": len(rows), "search_mode": "portable-bounded-fallback", "writes_performed": False}


def resolve(workspace: Path, identity: str, *, database: Path | None = None) -> dict[str, Any]:
    document = show(workspace, identity, database=database)
    workspace = resolved_workspace(workspace)
    path = require_path_within(workspace, database or hybrid_state.database_path(workspace))
    with contextlib.closing(hybrid_state.connect(path, writable=False)) as connection:
        aliases = [dict(row) for row in connection.execute(
            "SELECT path, alias_kind, created_revision, retired_revision FROM document_path_alias WHERE document_id=? ORDER BY path",
            (document["artifact_id"],),
        )]
    return {"schema_version": 1, "kind": "tool-shed-document-resolution", "artifact_id": document["artifact_id"], "visible_id": document["visible_id"], "title": document["title"], "lifecycle": document["lifecycle"], "aliases": aliases, "writes_performed": False}


def context_capsule(workspace: Path, identity: str, *, byte_budget: int = 16_384, database: Path | None = None) -> dict[str, Any]:
    if not 512 <= byte_budget <= 1_000_000:
        raise DocumentStoreError("context byte budget must be 512..1000000")
    primary = show(workspace, identity, database=database)
    relation_rows = related(workspace, identity, database=database)["relationships"]
    candidate_ids = sorted({
        row["to_visible_id"] if row["from_visible_id"] == primary["visible_id"] else row["from_visible_id"]
        for row in relation_rows
    })
    included = [primary]
    used = len(canonical_bytes(primary))
    omitted: list[str] = []
    for candidate in candidate_ids:
        document = show(workspace, candidate, database=database)
        size = len(canonical_bytes(document))
        if used + size <= byte_budget:
            included.append(document); used += size
        else:
            omitted.append(candidate)
    return {"schema_version": 1, "kind": "tool-shed-document-context", "requested": primary["visible_id"], "byte_budget": byte_budget, "supplied_bytes": used, "documents": included, "relationships": relation_rows, "omitted_ids": omitted, "budget_exceeded_by_primary": used > byte_budget and len(included) == 1, "writes_performed": False}


def create_document(workspace: Path, *, project_binding: str, document_type: str, title: str, body: str, lifecycle: str, metadata: dict[str, Any], actor: str, reason: str, preferred_path: str | None = None, database: Path | None = None) -> dict[str, Any]:
    if lifecycle not in LIFECYCLES or not title.strip():
        raise DocumentStoreError("create needs a title and supported lifecycle")
    namespace = _namespace_for(document_type)
    body_hash = sha256_text(body)

    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        number = _allocate(connection, namespace, None)
        visible = f"{namespace}-{number:04d}"
        artifact_id, stamp = str(uuid.uuid4()), hybrid_state.now()
        metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        connection.execute("INSERT INTO artifact VALUES (?, ?, ?, ?, 'sqlite', ?, ?, ?, ?)", (artifact_id, document_type, visible, f"sqlite/documents/{visible}", lifecycle, body_hash, stamp, stamp))
        connection.execute("INSERT INTO document VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)", (artifact_id, visible, namespace, number, title, lifecycle, metadata_json, body_hash, stamp, stamp))
        connection.execute("INSERT INTO document_revision VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), artifact_id, title, lifecycle, metadata_json, body, body_hash, actor, reason, revision, stamp))
        if preferred_path:
            relative = require_path_within(workspace, workspace / preferred_path).relative_to(workspace).as_posix()
            connection.execute(
                "INSERT INTO document_path_alias VALUES (?, ?, ?, 'preferred-view', ?, NULL)",
                (str(uuid.uuid4()), artifact_id, relative, revision),
            )
        return {"artifact_id": artifact_id, "visible_id": visible, "document_revision": 1, "preferred_path": preferred_path}
    return managed_write(workspace, project_binding=project_binding, command="document-create", actor=actor, callback=apply, database=database)


def set_lifecycle(workspace: Path, *, project_binding: str, identity: str, lifecycle: str, expected_revision: int, actor: str, reason: str, database: Path | None = None) -> dict[str, Any]:
    if lifecycle not in LIFECYCLES:
        raise DocumentStoreError(f"unsupported lifecycle: {lifecycle}")
    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        current = _lookup(connection, identity)
        if int(current["current_revision"]) != expected_revision:
            raise DocumentStoreError("stale document revision")
        new_revision, stamp = expected_revision + 1, hybrid_state.now()
        connection.execute("INSERT INTO document_revision VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), current["id"], new_revision, current["title"], lifecycle, current["metadata_json"], current["body_markdown"], current["body_sha256"], actor, reason, revision, stamp))
        connection.execute("UPDATE document SET lifecycle_state=?, current_revision=?, updated_at=? WHERE id=?", (lifecycle, new_revision, stamp, current["id"]))
        connection.execute("UPDATE artifact SET lifecycle_state=?, updated_at=? WHERE id=?", (lifecycle, stamp, current["id"]))
        return {"artifact_id": current["id"], "visible_id": current["visible_id"], "document_revision": new_revision, "lifecycle": lifecycle}
    return managed_write(workspace, project_binding=project_binding, command="document-set-lifecycle", actor=actor, callback=apply, database=database)


def set_type(workspace: Path, *, project_binding: str, identity: str, document_type: str, expected_revision: int, actor: str, reason: str, database: Path | None = None) -> dict[str, Any]:
    expected_namespace = _namespace_for(document_type)
    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        current = _lookup(connection, identity)
        if int(current["current_revision"]) != expected_revision:
            raise DocumentStoreError("stale document revision")
        if current["namespace"] != expected_namespace:
            raise DocumentStoreError(
                f"document namespace {current['namespace']} is incompatible with type {document_type}"
            )
        metadata_type = str(json.loads(current["metadata_json"]).get("document_type") or "").strip()
        if metadata_type and metadata_type != document_type:
            raise DocumentStoreError(
                f"document metadata declares {metadata_type}, not requested type {document_type}"
            )
        stored_type = connection.execute("SELECT type FROM artifact WHERE id=?", (current["id"],)).fetchone()[0]
        if stored_type == document_type:
            return {
                "artifact_id": current["id"], "visible_id": current["visible_id"],
                "document_revision": expected_revision, "type": document_type, "idempotent": True,
            }
        connection.execute(
            "UPDATE artifact SET type=?, updated_at=? WHERE id=?",
            (document_type, hybrid_state.now(), current["id"]),
        )
        return {
            "artifact_id": current["id"], "visible_id": current["visible_id"],
            "document_revision": expected_revision, "type": document_type, "idempotent": False,
        }
    return managed_write(workspace, project_binding=project_binding, command="document-set-type", actor=actor, callback=apply, database=database)


def render_edit(document: dict[str, Any]) -> str:
    return "\n".join([
        "---", EDIT_HEADER, f"artifact_id: {document['artifact_id']}", f"visible_id: {document['visible_id']}",
        f"revision: {document['document_revision']}", f"title: {json.dumps(document['title'], ensure_ascii=False)}",
        f"lifecycle: {document['lifecycle']}", f"metadata_json: {json.dumps(document['metadata'], ensure_ascii=False, sort_keys=True, separators=(',', ':'))}",
        "---", document["body_markdown"],
    ])


def export_edit(workspace: Path, identity: str, output: Path, *, database: Path | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    target = require_path_within(workspace, output if output.is_absolute() else workspace / output)
    document = show(workspace, identity, database=database)
    target.parent.mkdir(parents=True, exist_ok=True)
    content = render_edit(document)
    target.write_text(content, encoding="utf-8", newline="\n")
    return {"schema_version": 1, "kind": "tool-shed-document-edit-export", "path": target.relative_to(workspace).as_posix(), "artifact_id": document["artifact_id"], "visible_id": document["visible_id"], "document_revision": document["document_revision"], "sha256": sha256_text(content), "writes_performed": True}


def parse_edit(content: str) -> dict[str, Any]:
    lines = content.splitlines()
    if len(lines) < 9 or lines[0] != "---" or lines[1] != EDIT_HEADER:
        raise DocumentStoreError("edit projection header is missing")
    try:
        end = lines.index("---", 2)
    except ValueError as error:
        raise DocumentStoreError("edit projection header is unterminated") from error
    fields: dict[str, str] = {}
    for line in lines[2:end]:
        key, separator, value = line.partition(": ")
        if not separator or key in fields:
            raise DocumentStoreError("edit projection header field is malformed or duplicated")
        fields[key] = value
    expected = {"artifact_id", "visible_id", "revision", "title", "lifecycle", "metadata_json"}
    if fields.keys() != expected:
        raise DocumentStoreError(f"edit projection fields differ: {sorted(set(fields) ^ expected)}")
    try:
        title = json.loads(fields["title"])
        metadata = json.loads(fields["metadata_json"])
        revision = int(fields["revision"])
    except (json.JSONDecodeError, ValueError) as error:
        raise DocumentStoreError("edit projection structured field is invalid") from error
    if not isinstance(title, str) or not isinstance(metadata, dict):
        raise DocumentStoreError("edit projection title/metadata types are invalid")
    return {"artifact_id": fields["artifact_id"], "visible_id": fields["visible_id"], "revision": revision, "title": title, "lifecycle": fields["lifecycle"], "metadata": metadata, "body_markdown": "\n".join(lines[end + 1 :]) + ("\n" if content.endswith("\n") else "")}


def apply_edit(workspace: Path, *, project_binding: str, edit: Path, actor: str, reason: str, database: Path | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    path = require_path_within(workspace, edit if edit.is_absolute() else workspace / edit)
    parsed = parse_edit(path.read_text(encoding="utf-8"))

    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        current = _lookup(connection, parsed["artifact_id"])
        if current["visible_id"] != parsed["visible_id"]:
            raise DocumentStoreError("edit projection visible identity changed")
        if int(current["current_revision"]) != parsed["revision"]:
            raise DocumentStoreError("stale document revision")
        document_revision = parsed["revision"] + 1
        body_hash = sha256_text(parsed["body_markdown"])
        metadata_json = json.dumps(parsed["metadata"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        stamp = hybrid_state.now()
        connection.execute(
            "INSERT INTO document_revision VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), current["id"], document_revision, parsed["title"], parsed["lifecycle"], metadata_json, parsed["body_markdown"], body_hash, actor, reason, revision, stamp),
        )
        connection.execute(
            "UPDATE document SET title=?, lifecycle_state=?, current_revision=?, metadata_json=?, body_sha256=?, updated_at=? WHERE id=?",
            (parsed["title"], parsed["lifecycle"], document_revision, metadata_json, body_hash, stamp, current["id"]),
        )
        connection.execute(
            "UPDATE artifact SET lifecycle_state=?, content_sha256=?, updated_at=? WHERE id=?",
            (parsed["lifecycle"], body_hash, stamp, current["id"]),
        )
        return {"artifact_id": current["id"], "visible_id": current["visible_id"], "document_revision": document_revision, "body_sha256": body_hash}

    return managed_write(workspace, project_binding=project_binding, command="document-apply-edit", actor=actor, callback=apply, database=database)


def history(workspace: Path, identity: str, *, database: Path | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    path = require_path_within(workspace, database or hybrid_state.database_path(workspace))
    with contextlib.closing(hybrid_state.connect(path, writable=False)) as connection:
        row = _lookup(connection, identity)
        revisions = [dict(item) for item in connection.execute(
            "SELECT revision_number, title, lifecycle_state, body_sha256, actor, reason, source_revision, created_at FROM document_revision WHERE document_id=? ORDER BY revision_number",
            (row["id"],),
        )]
    return {"schema_version": 1, "kind": "tool-shed-document-history", "artifact_id": row["id"], "visible_id": row["visible_id"], "revisions": revisions, "writes_performed": False}


def diff_revisions(workspace: Path, identity: str, left: int, right: int, *, database: Path | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    path = require_path_within(workspace, database or hybrid_state.database_path(workspace))
    with contextlib.closing(hybrid_state.connect(path, writable=False)) as connection:
        document = _lookup(connection, identity)
        rows = connection.execute("SELECT revision_number, body_markdown FROM document_revision WHERE document_id=? AND revision_number IN (?, ?) ORDER BY revision_number", (document["id"], left, right)).fetchall()
    if len(rows) != 2:
        raise DocumentStoreError("both requested revisions must exist and differ")
    diff = "".join(difflib.unified_diff(rows[0]["body_markdown"].splitlines(True), rows[1]["body_markdown"].splitlines(True), fromfile=f"{document['visible_id']}@{left}", tofile=f"{document['visible_id']}@{right}"))
    return {"schema_version": 1, "kind": "tool-shed-document-diff", "visible_id": document["visible_id"], "from_revision": left, "to_revision": right, "diff": diff, "writes_performed": False}


def relate(workspace: Path, *, project_binding: str, source: str, relation: str, target: str, actor: str, database: Path | None = None) -> dict[str, Any]:
    def find_existing(connection: sqlite3.Connection) -> dict[str, Any] | None:
        left, right = _lookup(connection, source), _lookup(connection, target)
        existing = hybrid_state.active_relationship(
            connection, left["id"], relation, right["id"]
        )
        if existing is not None:
            return {
                "relationship_id": existing["id"],
                "from": left["visible_id"],
                "relation": relation,
                "to": right["visible_id"],
                "created": False,
                "idempotent": True,
            }
        return None

    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        left, right = _lookup(connection, source), _lookup(connection, target)
        relation_id = str(uuid.uuid4())
        connection.execute("INSERT INTO relationship VALUES (?, ?, ?, ?, 'document-store-v1', ?, NULL)", (relation_id, left["id"], relation, right["id"], revision))
        return {"relationship_id": relation_id, "from": left["visible_id"], "relation": relation, "to": right["visible_id"], "created": True, "idempotent": False}
    return managed_write(workspace, project_binding=project_binding, command="document-relate", actor=actor, callback=apply, existing=find_existing, database=database)


def unrelate(workspace: Path, *, project_binding: str, relationship_id: str, actor: str, database: Path | None = None) -> dict[str, Any]:
    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        row = connection.execute("SELECT retired_revision FROM relationship WHERE id=?", (relationship_id,)).fetchone()
        if row is None:
            raise DocumentStoreError("relationship not found")
        if row[0] is not None:
            raise DocumentStoreError("relationship is already retired")
        connection.execute("UPDATE relationship SET retired_revision=? WHERE id=?", (revision, relationship_id))
        return {"relationship_id": relationship_id, "retired_revision": revision}
    return managed_write(workspace, project_binding=project_binding, command="document-unrelate", actor=actor, callback=apply, database=database)


def related(workspace: Path, identity: str, *, database: Path | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    path = require_path_within(workspace, database or hybrid_state.database_path(workspace))
    with contextlib.closing(hybrid_state.connect(path, writable=False)) as connection:
        document = _lookup(connection, identity)
        rows = [dict(row) for row in connection.execute(
            "SELECT r.id, r.relation_type, a.visible_id AS from_visible_id, b.visible_id AS to_visible_id "
            "FROM relationship r JOIN document a ON a.id=r.from_artifact_id JOIN document b ON b.id=r.to_artifact_id "
            "WHERE (r.from_artifact_id=? OR r.to_artifact_id=?) AND r.retired_revision IS NULL ORDER BY r.relation_type, r.id",
            (document["id"], document["id"]),
        )]
    return {"schema_version": 1, "kind": "tool-shed-document-relationships", "visible_id": document["visible_id"], "relationships": rows, "writes_performed": False}


RETIREMENT_MANIFEST_KIND = "tool-shed-retained-source-retirement-manifest"
RETIREMENT_REFERENCE_PROJECTIONS = {
    "work/index.md",
    "work/index.json",
    "work/00-campaigns/active-queue.md",
    "work/00-campaigns/completed-queue.md",
}
RETIREMENT_HISTORICAL_REFERENCE_PATHS = {
    "schemas/document-store/v1/maintainer-assigned-ids.json",
    "schemas/hybrid-state/v1/maintainer-assigned-ids.json",
    "schemas/outcome-reconciliation/v1/hpt2-compatibility-fixture.json",
}


def _retirement_manifest_token(manifest: dict[str, Any]) -> str:
    payload = copy.deepcopy(manifest)
    payload.pop("manifest_token", None)
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()[:16]


def _repository_files(workspace: Path) -> list[Path]:
    if (workspace / ".git").is_dir():
        result = subprocess.run(
            ["git", "ls-files", "-z"], cwd=workspace, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=False,
        )
        if result.returncode == 0:
            files: list[Path] = []
            for value in result.stdout.split(b"\0"):
                if not value:
                    continue
                path = workspace / value.decode("utf-8", errors="surrogateescape")
                if path.is_file():
                    files.append(path)
            return files
    excluded = {".git", ".tool-shed", ".venv", "build", "__pycache__"}
    return sorted(
        path for path in workspace.rglob("*")
        if path.is_file() and not any(part in excluded for part in path.relative_to(workspace).parts)
    )


def retirement_plan(workspace: Path, *, database: Path | None = None) -> dict[str, Any]:
    """Build an exact, read-only plan for retiring converted generated source aliases."""
    workspace = resolved_workspace(workspace)
    target = require_path_within(workspace, database or hybrid_state.database_path(workspace))
    with contextlib.closing(hybrid_state.connect(target, writable=False)) as connection:
        entrance = audit_connection(workspace, connection)
        if entrance["classification"] not in {"CLEAN", "VALID_DIRTY"}:
            raise DocumentStoreError(
                f"retirement planning refused from {entrance['classification']}: "
                + "; ".join(entrance["findings"])
            )
        rows = connection.execute(
            "SELECT dc.source_path, dc.source_sha256, dc.artifact_id, dc.visible_id, "
            "dc.status, dc.byte_parity, dc.render_parity, pa.id AS alias_id, "
            "pa.retired_revision FROM document_conversion dc LEFT JOIN document_path_alias pa "
            "ON pa.document_id=dc.artifact_id AND pa.path=dc.source_path "
            "AND pa.alias_kind='retained-source' WHERE dc.classification='generated' "
            "ORDER BY dc.source_path"
        ).fetchall()

    findings: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    candidate_paths = {str(row["source_path"]) for row in rows}
    for row in rows:
        relative = str(row["source_path"])
        source = require_path_within(workspace, workspace / relative)
        observed_sha256 = hybrid_state.file_sha256(source) if source.is_file() else None
        state = "active" if row["alias_id"] and row["retired_revision"] is None else "retired"
        if not source.is_file():
            findings.append({"code": "SOURCE_MISSING", "path": relative})
        elif observed_sha256 != row["source_sha256"]:
            findings.append({"code": "SOURCE_HASH_DRIFT", "path": relative})
        if row["status"] != "verified" or not row["byte_parity"] or not row["render_parity"]:
            findings.append({"code": "CONVERSION_NOT_VERIFIED", "path": relative})
        if not row["alias_id"]:
            findings.append({"code": "RETAINED_ALIAS_MISSING", "path": relative})
        candidates.append({
            "path": relative,
            "source_sha256": str(row["source_sha256"]),
            "observed_sha256": observed_sha256,
            "artifact_id": str(row["artifact_id"]),
            "visible_id": str(row["visible_id"]),
            "alias_id": str(row["alias_id"]) if row["alias_id"] else None,
            "alias_state": state,
            "retired_revision": row["retired_revision"],
        })

    references: list[dict[str, Any]] = []
    if candidate_paths:
        pattern = re.compile(
            "|".join(re.escape(value) for value in sorted(candidate_paths, key=lambda item: (-len(item), item)))
        )
        for path in _repository_files(workspace):
            relative = path.relative_to(workspace).as_posix()
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            matches: dict[str, int] = {}
            for match in pattern.finditer(text):
                matches[match.group(0)] = matches.get(match.group(0), 0) + 1
            for target_path, occurrences in sorted(matches.items()):
                if relative in candidate_paths:
                    disposition = "co-retired-source"
                elif relative.startswith("work/state/") or relative.startswith(
                    "work/evidence/bootstrap-closure-"
                ) or relative in RETIREMENT_HISTORICAL_REFERENCE_PATHS:
                    disposition = "historical-recovery-reference"
                elif relative in RETIREMENT_REFERENCE_PROJECTIONS:
                    disposition = "disposable-projection"
                else:
                    disposition = "rewrite-required"
                references.append({
                    "source_path": relative,
                    "target_path": target_path,
                    "occurrences": occurrences,
                    "disposition": disposition,
                })

    reference_counts = {
        name: sum(1 for item in references if item["disposition"] == name)
        for name in (
            "co-retired-source", "historical-recovery-reference",
            "disposable-projection", "rewrite-required",
        )
    }
    work_files = sum(1 for path in (workspace / "work").rglob("*") if path.is_file())
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": RETIREMENT_MANIFEST_KIND,
        "project_id": hybrid_state.load_project_identity(workspace)["project_id"],
        "expected_revision": entrance["current_revision"],
        "expected_domain_digest": entrance["domain_digest"],
        "prepared_at": hybrid_state.now(),
        "candidate_count": len(candidates),
        "active_alias_count": sum(1 for item in candidates if item["alias_state"] == "active"),
        "excluded_work_file_count": max(0, work_files - len(candidates)),
        "candidates": candidates,
        "references": references,
        "reference_counts": reference_counts,
        "findings": findings,
        "valid": not findings,
        "applicable": not findings and reference_counts["rewrite-required"] == 0
            and bool(candidates) and all(item["alias_state"] == "active" for item in candidates),
        "writes_performed": False,
    }
    manifest["manifest_token"] = _retirement_manifest_token(manifest)
    return manifest


def retire_source_aliases(
    workspace: Path, *, project_binding: str, manifest_path: Path,
    expected_token: str, actor: str, reason: str, database: Path | None = None,
) -> dict[str, Any]:
    """Retire exactly manifest-bound aliases without deleting filesystem sources."""
    workspace = resolved_workspace(workspace)
    path = require_path_within(
        workspace, manifest_path if manifest_path.is_absolute() else workspace / manifest_path,
    )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("kind") != RETIREMENT_MANIFEST_KIND:
        raise DocumentStoreError("unsupported retained-source retirement manifest")
    token = _retirement_manifest_token(manifest)
    if token != manifest.get("manifest_token") or token != expected_token:
        raise DocumentStoreError("retirement manifest token mismatch")
    if not manifest.get("applicable"):
        raise DocumentStoreError("retirement manifest is not applicable")
    identity = hybrid_state.load_project_identity(workspace)
    if manifest.get("project_id") != identity["project_id"]:
        raise DocumentStoreError("retirement manifest belongs to another project")

    def preflight(connection: sqlite3.Connection) -> None:
        current = audit_connection(workspace, connection)
        if current["current_revision"] != manifest.get("expected_revision"):
            raise DocumentStoreError("retirement manifest expected_revision is stale")
        if current["domain_digest"] != manifest.get("expected_domain_digest"):
            raise DocumentStoreError("retirement manifest domain digest is stale")
        for candidate in manifest["candidates"]:
            source = require_path_within(workspace, workspace / candidate["path"])
            if not source.is_file() or hybrid_state.file_sha256(source) != candidate["source_sha256"]:
                raise DocumentStoreError(f"retirement source drift: {candidate['path']}")
            row = connection.execute(
                "SELECT id, retired_revision FROM document_path_alias WHERE id=? "
                "AND document_id=? AND path=? AND alias_kind='retained-source'",
                (candidate["alias_id"], candidate["artifact_id"], candidate["path"]),
            ).fetchone()
            if row is None or row["retired_revision"] is not None:
                raise DocumentStoreError(f"retirement alias drift: {candidate['path']}")
            conversion = connection.execute(
                "SELECT 1 FROM document_conversion WHERE artifact_id=? AND source_path=? "
                "AND source_sha256=? AND classification='generated' AND status='verified' "
                "AND byte_parity=1 AND render_parity=1",
                (candidate["artifact_id"], candidate["path"], candidate["source_sha256"]),
            ).fetchone()
            if conversion is None:
                raise DocumentStoreError(f"retirement conversion drift: {candidate['path']}")
        return None

    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        retired: list[str] = []
        for candidate in manifest["candidates"]:
            connection.execute(
                "UPDATE document_path_alias SET retired_revision=? WHERE id=?",
                (revision, candidate["alias_id"]),
            )
            retired.append(candidate["path"])
        return {
            "manifest_token": token,
            "retired_alias_count": len(retired),
            "retired_paths": retired,
            "filesystem_deletions": 0,
        }

    return managed_write(
        workspace, project_binding=project_binding, command="retire-retained-source-aliases",
        actor=actor, callback=apply, existing=preflight, database=database,
    )


def open_outcome(workspace: Path, *, project_binding: str, identity: str, accepted_outcome: str, actor: str, database: Path | None = None) -> dict[str, Any]:
    """Open one governed outcome loop on a database-owned document."""
    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        document = _lookup(connection, identity)
        if connection.execute("SELECT 1 FROM cycle WHERE origin_artifact_id=? AND lifecycle_state<>'terminal'", (document["id"],)).fetchone():
            raise DocumentStoreError("document already has an open outcome loop")
        cycle_id, requirement_id, verdict_id, reconciliation_id = (str(uuid.uuid4()) for _ in range(4))
        stamp = hybrid_state.now()
        connection.execute("INSERT INTO cycle VALUES (?, 'document', ?, ?, 'working', ?, NULL)", (cycle_id, document["id"], accepted_outcome, stamp))
        connection.execute("INSERT INTO requirement VALUES (?, ?, ?, ?, 'accepted', ?, 'document-thin-slice', 'open-outcome')", (requirement_id, cycle_id, document["id"], accepted_outcome, revision))
        connection.execute("INSERT INTO outcome_verdict VALUES (?, ?, ?, 'open', ?, ?, ?, ?)", (verdict_id, cycle_id, document["visible_id"], accepted_outcome, actor, revision, stamp))
        connection.execute("INSERT INTO reconciliation VALUES (?, ?, ?, ?, ?, 'open', ?, '[]')", (reconciliation_id, cycle_id, revision, f"document:{document['id']}", verdict_id, stamp))
        return {"cycle_id": cycle_id, "origin_artifact_id": document["id"], "visible_id": document["visible_id"], "lifecycle": "working", "verdict": "open", "reconciliation": "open"}
    return managed_write(workspace, project_binding=project_binding, command="document-open-outcome", actor=actor, callback=apply, database=database)


def _slug(title: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")
    return value[:80] or "untitled"


def render_views(workspace: Path, *, output: Path | None = None, database: Path | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    database_path = require_path_within(workspace, database or hybrid_state.database_path(workspace))
    target = require_path_within(workspace, output or workspace / ".tool-shed/views/work")
    temporary = target.with_name(target.name + ".next")
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    with contextlib.closing(hybrid_state.connect(database_path, writable=False)) as connection:
        checked = audit_connection(workspace, connection)
        if checked["classification"] in {"INVALID", "UNJOURNALED"}:
            raise DocumentStoreError(f"view render refused from {checked['classification']}")
        rows = list(connection.execute(
            "SELECT d.*, a.type, r.body_markdown FROM document d JOIN artifact a ON a.id=d.id "
            "JOIN document_revision r ON r.document_id=d.id AND r.revision_number=d.current_revision ORDER BY d.lifecycle_state, d.visible_id"
        ))
        import idea_readiness

        readiness_projections = {
            row["id"]: idea_readiness.render_projection(connection, row)
            for row in rows
            if row["type"] == "idea-brief"
        }
    counts: dict[str, int] = {}
    for lifecycle in LIFECYCLES:
        directory = temporary / lifecycle
        directory.mkdir()
        selected = [row for row in rows if row["lifecycle_state"] == lifecycle]
        index_lines = [f"# {lifecycle.title()} Tool Shed Work", "", f"Database revision: {checked['current_revision']}", "", "Generated view — do not edit.", ""]
        for row in selected:
            filename = f"{row['visible_id']}--{_slug(row['title'])}.md"
            readiness_projection = readiness_projections.get(row["id"], "")
            body = row["body_markdown"]
            if readiness_projection:
                body = body.rstrip() + "\n\n" + readiness_projection + "\n"
            rendered = "\n".join([
                f"# {row['visible_id']}: {row['title']}", "", "Generated view — do not edit.", "",
                f"Artifact ID: {row['id']}", f"Type: {row['type']}", f"Lifecycle: {row['lifecycle_state']}",
                f"Document Revision: {row['current_revision']}", f"Database Revision: {checked['current_revision']}", "", body,
            ])
            (directory / filename).write_text(rendered, encoding="utf-8", newline="\n")
            index_lines.append(f"- {row['visible_id']} — {row['title']} ({row['type']}, r{row['current_revision']})")
        (directory / "_index.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8", newline="\n")
        counts[lifecycle] = len(selected)
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(temporary, target)
    return {"schema_version": 1, "kind": "tool-shed-document-lifecycle-views", "path": target.relative_to(workspace).as_posix(), "database_revision": checked["current_revision"], "counts": counts, "files": sum(counts.values()) + len(LIFECYCLES), "writes_performed": True}


def checkpoint_digest(payload: dict[str, Any]) -> str:
    material = copy.deepcopy(payload)
    material["envelope"].pop("digest", None)
    return hashlib.sha256(canonical_bytes(material)).hexdigest()


def write_checkpoint(workspace: Path, *, project_binding: str, output: Path, database: Path | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    require_project_binding(workspace, project_binding, operation=OPERATION)
    source = require_path_within(workspace, database or hybrid_state.database_path(workspace))
    target = require_path_within(workspace, output if output.is_absolute() else workspace / output)
    target.parent.mkdir(parents=True, exist_ok=True)
    object_root = require_path_within(workspace, workspace / "work/state/objects/sha256")
    object_root.mkdir(parents=True, exist_ok=True)
    with hybrid_state.WorkspaceLock(hybrid_state.lock_path(workspace)), contextlib.closing(hybrid_state.connect(source)) as connection:
        checked = audit_connection(workspace, connection)
        if checked["classification"] not in {"CLEAN", "VALID_DIRTY"}:
            raise DocumentStoreError(f"checkpoint refused from {checked['classification']}")
        tables = {table: hybrid_state.table_rows(connection, table) for table in portable_tables(connection)}
        objects: list[str] = []
        for row in tables["document_revision"]:
            body = row.pop("body_markdown")
            digest = sha256_text(body)
            if digest != row["body_sha256"]:
                raise DocumentStoreError("revision body hash mismatch")
            relative = f"work/state/objects/sha256/{digest[:2]}/{digest}"
            object_path = workspace / relative
            object_path.parent.mkdir(parents=True, exist_ok=True)
            if object_path.exists() and object_path.read_bytes() != body.encode("utf-8"):
                raise DocumentStoreError("content object collision")
            if not object_path.exists():
                object_path.write_bytes(body.encode("utf-8"))
            row["body_object"] = relative
            objects.append(relative)
        meta = hybrid_state.meta_row(connection)
        payload = {
            "schema_version": CHECKPOINT_FORMAT,
            "kind": CHECKPOINT_KIND,
            "envelope": {
                "project_id": meta["project_id"], "workspace_id": meta["workspace_id"], "hybrid_schema": 2,
                "database_revision": meta["current_revision"], "storage_mode": meta["storage_mode"],
                "created_at": hybrid_state.now(), "objects": sorted(set(objects)), "digest": None,
            },
            "tables": tables,
        }
        digest = checkpoint_digest(payload)
        payload["envelope"]["digest"] = digest
        descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            _replace_file(temporary, target)
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("UPDATE state_meta SET last_checkpoint_revision=?, checkpoint_digest=?, dirty=0, checkpoint_pending=0 WHERE id=1", (meta["current_revision"], digest))
            connection.commit()
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    return {"schema_version": 2, "kind": "tool-shed-document-checkpoint-result", "path": target.relative_to(workspace).as_posix(), "digest": digest, "revision": meta["current_revision"], "objects": sorted(set(objects)), "writes_performed": True}


def rebuild(workspace: Path, *, project_binding: str, checkpoint: Path, output: Path) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    require_project_binding(workspace, project_binding, operation=OPERATION)
    source = require_path_within(workspace, checkpoint if checkpoint.is_absolute() else workspace / checkpoint)
    destination = require_path_within(workspace, output if output.is_absolute() else workspace / output)
    if destination.exists():
        raise DocumentStoreError(f"rebuild output exists: {destination.relative_to(workspace)}")
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 2 or payload.get("kind") != CHECKPOINT_KIND or checkpoint_digest(payload) != payload.get("envelope", {}).get("digest"):
        raise DocumentStoreError("checkpoint identity or digest is invalid")
    temporary = destination.with_name(destination.name + ".next")
    try:
        connection = sqlite3.connect(temporary, isolation_level=None)
        hybrid_state.configure(connection)
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("BEGIN IMMEDIATE")
        hybrid_state.create_schema(connection, include_triggers=False)
        create_document_schema(connection, include_triggers=False)
        envelope, tables = payload["envelope"], payload["tables"]
        meta_source = tables.pop("state_meta", None)
        connection.execute(
            "INSERT INTO state_meta VALUES (1, 2, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?)",
            (envelope["project_id"], hybrid_state.stable_uuid(envelope["project_id"], f"workspace:{workspace.resolve()}"), envelope["storage_mode"], envelope["database_revision"], envelope["database_revision"], envelope["database_revision"], hybrid_state.EMPTY_SHA256, envelope["digest"], hybrid_state.EMPTY_SHA256),
        )
        for table in (*PORTABLE_TABLES, *DOCUMENT_PORTABLE_TABLES):
            if table == "workspace":
                continue
            for original in tables.get(table, []):
                row = dict(original)
                if table == "document_revision":
                    object_path = require_path_within(workspace, workspace / row.pop("body_object"))
                    # Content objects are addressed by their exact UTF-8
                    # bytes. Text-mode reads translate CRLF on Windows and
                    # can therefore invalidate an otherwise correct digest.
                    body = object_path.read_bytes().decode("utf-8")
                    if sha256_text(body) != row["body_sha256"]:
                        raise DocumentStoreError("checkpoint content object hash mismatch")
                    row["body_markdown"] = body
                columns = list(row)
                connection.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})", tuple(row[item] for item in columns))
        workspace_row = tables["workspace"][0]
        connection.execute("INSERT INTO workspace VALUES (?, ?, ?, ?)", (hybrid_state.stable_uuid(envelope["project_id"], f"workspace:{workspace.resolve()}"), envelope["project_id"], workspace_row["name"], workspace_row["created_at"]))
        hybrid_state.create_triggers(connection)
        from document_store_schema import document_trigger_sql
        connection.executescript(document_trigger_sql())
        connection.execute("UPDATE state_meta SET source_digest=?, schema_trigger_digest=? WHERE id=1", (domain_digest(connection), hybrid_state.schema_digest(connection)))
        connection.execute("PRAGMA user_version=2")
        connection.commit()
        connection.execute("PRAGMA foreign_keys=ON")
        if list(connection.execute("PRAGMA foreign_key_check")):
            raise DocumentStoreError("rebuilt checkpoint has foreign-key violations")
        connection.close()
        _replace_file(temporary, destination)
    except BaseException:
        with contextlib.suppress(Exception):
            connection.close()
        temporary.unlink(missing_ok=True)
        raise
    checked = audit(workspace, destination)
    if checked["classification"] != "CLEAN":
        destination.unlink(missing_ok=True)
        raise DocumentStoreError(f"rebuilt database is {checked['classification']}")
    return {"schema_version": 1, "kind": "tool-shed-document-rebuild", "output": destination.relative_to(workspace).as_posix(), "checkpoint_digest": envelope["digest"], "domain_digest": checked["domain_digest"], "writes_performed": True}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--database")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("audit",):
        commands.add_parser(name)
    migrate_parser = commands.add_parser("migrate")
    migrate_parser.add_argument("--project-binding", required=True)
    import_parser = commands.add_parser("import-apply")
    import_parser.add_argument("--project-binding", required=True); import_parser.add_argument("--source", required=True); import_parser.add_argument("--type", required=True); import_parser.add_argument("--lifecycle", default="active"); import_parser.add_argument("--actor", required=True); import_parser.add_argument("--reason", required=True); import_parser.add_argument("--assigned-number", type=int)
    create_parser = commands.add_parser("create"); create_parser.add_argument("--project-binding", required=True); create_parser.add_argument("--type", required=True); create_parser.add_argument("--title", required=True); create_body = create_parser.add_mutually_exclusive_group(required=True); create_body.add_argument("--body"); create_body.add_argument("--body-file"); create_parser.add_argument("--lifecycle", default="active"); create_parser.add_argument("--metadata-json", default="{}"); create_parser.add_argument("--preferred-path"); create_parser.add_argument("--actor", required=True); create_parser.add_argument("--reason", required=True)
    list_parser = commands.add_parser("list"); list_parser.add_argument("--lifecycle"); list_parser.add_argument("--type"); list_parser.add_argument("--limit", type=int, default=100)
    show_parser = commands.add_parser("show"); show_parser.add_argument("identity")
    search_parser = commands.add_parser("search"); search_parser.add_argument("query"); search_parser.add_argument("--limit", type=int, default=20)
    context_parser = commands.add_parser("context"); context_parser.add_argument("identity"); context_parser.add_argument("--byte-budget", type=int, default=16384)
    resolve_parser = commands.add_parser("resolve"); resolve_parser.add_argument("identity")
    export_parser = commands.add_parser("export-edit"); export_parser.add_argument("identity"); export_parser.add_argument("--output", required=True)
    apply_parser = commands.add_parser("apply-edit"); apply_parser.add_argument("--project-binding", required=True); apply_parser.add_argument("--edit", required=True); apply_parser.add_argument("--actor", required=True); apply_parser.add_argument("--reason", required=True)
    lifecycle_parser = commands.add_parser("set-lifecycle"); lifecycle_parser.add_argument("identity"); lifecycle_parser.add_argument("--project-binding", required=True); lifecycle_parser.add_argument("--lifecycle", required=True); lifecycle_parser.add_argument("--expect-revision", type=int, required=True); lifecycle_parser.add_argument("--actor", required=True); lifecycle_parser.add_argument("--reason", required=True)
    type_parser = commands.add_parser("set-type"); type_parser.add_argument("identity"); type_parser.add_argument("--project-binding", required=True); type_parser.add_argument("--type", required=True); type_parser.add_argument("--expect-revision", type=int, required=True); type_parser.add_argument("--actor", required=True); type_parser.add_argument("--reason", required=True)
    history_parser = commands.add_parser("history"); history_parser.add_argument("identity")
    diff_parser = commands.add_parser("diff"); diff_parser.add_argument("identity"); diff_parser.add_argument("--from-revision", type=int, required=True); diff_parser.add_argument("--to-revision", type=int, required=True)
    relate_parser = commands.add_parser("relate"); relate_parser.add_argument("--project-binding", required=True); relate_parser.add_argument("--from", dest="source", required=True); relate_parser.add_argument("--relation", required=True); relate_parser.add_argument("--to", dest="target", required=True); relate_parser.add_argument("--actor", required=True)
    unrelate_parser = commands.add_parser("unrelate"); unrelate_parser.add_argument("--project-binding", required=True); unrelate_parser.add_argument("--relationship", required=True); unrelate_parser.add_argument("--actor", required=True)
    related_parser = commands.add_parser("related"); related_parser.add_argument("identity")
    commands.add_parser("retirement-plan")
    retire_parser = commands.add_parser("retire-source-aliases"); retire_parser.add_argument("--project-binding", required=True); retire_parser.add_argument("--manifest", required=True); retire_parser.add_argument("--expect", required=True); retire_parser.add_argument("--actor", required=True); retire_parser.add_argument("--reason", required=True)
    views_parser = commands.add_parser("render-views"); views_parser.add_argument("--output")
    checkpoint_parser = commands.add_parser("checkpoint"); checkpoint_parser.add_argument("--project-binding", required=True); checkpoint_parser.add_argument("--output", required=True)
    rebuild_parser = commands.add_parser("rebuild"); rebuild_parser.add_argument("--project-binding", required=True); rebuild_parser.add_argument("--checkpoint", required=True); rebuild_parser.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        workspace = resolved_workspace(Path(args.workspace))
        database = Path(args.database) if args.database else None
        if database and not database.is_absolute(): database = workspace / database
        if args.command == "audit": result = audit(workspace, database)
        elif args.command == "migrate": result = migrate(workspace, project_binding=args.project_binding, database=database)
        elif args.command == "import-apply": result = import_document(workspace, project_binding=args.project_binding, source=Path(args.source), document_type=args.type, lifecycle=args.lifecycle, actor=args.actor, reason=args.reason, assigned_number=args.assigned_number, database=database)
        elif args.command == "create":
            body = args.body if args.body is not None else require_path_within(workspace, workspace / args.body_file).read_text(encoding="utf-8")
            result = create_document(workspace, project_binding=args.project_binding, document_type=args.type, title=args.title, body=body, lifecycle=args.lifecycle, metadata=json.loads(args.metadata_json), actor=args.actor, reason=args.reason, preferred_path=args.preferred_path, database=database)
        elif args.command == "list": result = list_documents(workspace, lifecycle=args.lifecycle, document_type=args.type, limit=args.limit, database=database)
        elif args.command == "show": result = show(workspace, args.identity, database=database)
        elif args.command == "search": result = search(workspace, args.query, limit=args.limit, database=database)
        elif args.command == "context": result = context_capsule(workspace, args.identity, byte_budget=args.byte_budget, database=database)
        elif args.command == "resolve": result = resolve(workspace, args.identity, database=database)
        elif args.command == "export-edit": result = export_edit(workspace, args.identity, Path(args.output), database=database)
        elif args.command == "apply-edit": result = apply_edit(workspace, project_binding=args.project_binding, edit=Path(args.edit), actor=args.actor, reason=args.reason, database=database)
        elif args.command == "set-lifecycle": result = set_lifecycle(workspace, project_binding=args.project_binding, identity=args.identity, lifecycle=args.lifecycle, expected_revision=args.expect_revision, actor=args.actor, reason=args.reason, database=database)
        elif args.command == "set-type": result = set_type(workspace, project_binding=args.project_binding, identity=args.identity, document_type=args.type, expected_revision=args.expect_revision, actor=args.actor, reason=args.reason, database=database)
        elif args.command == "history": result = history(workspace, args.identity, database=database)
        elif args.command == "diff": result = diff_revisions(workspace, args.identity, args.from_revision, args.to_revision, database=database)
        elif args.command == "relate": result = relate(workspace, project_binding=args.project_binding, source=args.source, relation=args.relation, target=args.target, actor=args.actor, database=database)
        elif args.command == "unrelate": result = unrelate(workspace, project_binding=args.project_binding, relationship_id=args.relationship, actor=args.actor, database=database)
        elif args.command == "related": result = related(workspace, args.identity, database=database)
        elif args.command == "retirement-plan": result = retirement_plan(workspace, database=database)
        elif args.command == "retire-source-aliases": result = retire_source_aliases(workspace, project_binding=args.project_binding, manifest_path=Path(args.manifest), expected_token=args.expect, actor=args.actor, reason=args.reason, database=database)
        elif args.command == "render-views": result = render_views(workspace, output=Path(args.output) if args.output else None, database=database)
        elif args.command == "checkpoint": result = write_checkpoint(workspace, project_binding=args.project_binding, output=Path(args.output), database=database)
        else: result = rebuild(workspace, project_binding=args.project_binding, checkpoint=Path(args.checkpoint), output=Path(args.output))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if args.command == "audit" and result["classification"] in {"INVALID", "UNJOURNALED"} else 0
    except (DocumentStoreError, hybrid_state.HybridStateError, ProjectIdentityError, OSError, ValueError, sqlite3.DatabaseError, json.JSONDecodeError) as error:
        print(f"Document store operation failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
