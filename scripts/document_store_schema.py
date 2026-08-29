#!/usr/bin/env python3
"""Schema-2 document resources layered on Tool Shed Hybrid state v1."""

from __future__ import annotations

import hashlib
import sqlite3

from hybrid_state_schema import UUID_SQL


DOCUMENT_SCHEMA_VERSION = 1
HYBRID_SCHEMA_VERSION = 2
DOCUMENT_TABLES = (
    "document_namespace",
    "document",
    "document_revision",
    "document_path_alias",
    "document_conversion",
)
DOCUMENT_PORTABLE_TABLES = DOCUMENT_TABLES


DOCUMENT_SCHEMA_SQL = r"""
CREATE TABLE document_namespace (
    id TEXT PRIMARY KEY,
    next_number INTEGER NOT NULL CHECK (next_number > 0)
) WITHOUT ROWID;

CREATE TABLE document (
    id TEXT PRIMARY KEY REFERENCES artifact(id) ON DELETE RESTRICT,
    visible_id TEXT NOT NULL UNIQUE,
    namespace TEXT NOT NULL REFERENCES document_namespace(id) ON DELETE RESTRICT,
    display_number INTEGER NOT NULL CHECK (display_number > 0),
    title TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL,
    current_revision INTEGER NOT NULL CHECK (current_revision > 0),
    metadata_json TEXT NOT NULL CHECK (json_valid(metadata_json)),
    body_sha256 TEXT NOT NULL CHECK (length(body_sha256) = 64),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (namespace, display_number)
) WITHOUT ROWID;

CREATE TABLE document_revision (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES document(id) ON DELETE RESTRICT,
    revision_number INTEGER NOT NULL CHECK (revision_number > 0),
    title TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL,
    metadata_json TEXT NOT NULL CHECK (json_valid(metadata_json)),
    body_markdown TEXT NOT NULL,
    body_sha256 TEXT NOT NULL CHECK (length(body_sha256) = 64),
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    source_revision INTEGER NOT NULL CHECK (source_revision > 0),
    created_at TEXT NOT NULL,
    UNIQUE (document_id, revision_number)
) WITHOUT ROWID;
CREATE INDEX document_revision_source_idx ON document_revision(source_revision, id);

CREATE TABLE document_path_alias (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES document(id) ON DELETE RESTRICT,
    path TEXT NOT NULL UNIQUE,
    alias_kind TEXT NOT NULL CHECK (alias_kind IN ('retained-source', 'historical', 'preferred-view')),
    created_revision INTEGER NOT NULL CHECK (created_revision > 0),
    retired_revision INTEGER CHECK (retired_revision IS NULL OR retired_revision >= created_revision)
) WITHOUT ROWID;

CREATE TABLE document_conversion (
    id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL UNIQUE,
    source_sha256 TEXT NOT NULL CHECK (length(source_sha256) = 64),
    artifact_id TEXT NOT NULL REFERENCES artifact(id) ON DELETE RESTRICT,
    visible_id TEXT NOT NULL,
    classification TEXT NOT NULL CHECK (classification IN ('generated', 'file-owned', 'projection', 'unresolved')),
    status TEXT NOT NULL CHECK (status IN ('planned', 'imported', 'verified', 'cutover', 'failed')),
    byte_parity INTEGER NOT NULL CHECK (byte_parity IN (0, 1)),
    render_parity INTEGER NOT NULL CHECK (render_parity IN (0, 1)),
    imported_revision INTEGER NOT NULL CHECK (imported_revision > 0),
    created_at TEXT NOT NULL,
    completed_at TEXT
) WITHOUT ROWID;
"""


def _accounting_trigger(table: str, operation: str) -> str:
    row = "OLD" if operation == "delete" else "NEW"
    revision = "COALESCE((SELECT revision FROM active_operation WHERE id = 1), (SELECT current_revision + 1 FROM state_meta WHERE id = 1))"
    operation_id = "(SELECT operation_id FROM active_operation WHERE id = 1)"
    managed = "CASE WHEN EXISTS (SELECT 1 FROM active_operation WHERE id = 1) THEN 1 ELSE 0 END"
    stamp = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"
    return f"""
CREATE TRIGGER ts_account_{table}_{operation} AFTER {operation.upper()} ON {table}
BEGIN
  INSERT INTO structural_change
    (id, revision, operation_id, table_name, row_id, operation, managed, payload_digest, recorded_at)
  VALUES
    ({UUID_SQL}, {revision}, {operation_id}, '{table}', CAST({row}.id AS TEXT),
     '{operation}', {managed}, lower(hex(randomblob(32))), {stamp});
  INSERT INTO event
    (id, revision, operation_id, kind, entity_type, entity_id, payload_json, recorded_at)
  VALUES
    ({UUID_SQL}, {revision}, {operation_id}, 'structural-{operation}', '{table}',
     CAST({row}.id AS TEXT), json_object('operation', '{operation}', 'table', '{table}'), {stamp});
  UPDATE managed_operation SET actual_writes = actual_writes + 1
    WHERE id = (SELECT operation_id FROM active_operation WHERE id = 1);
  UPDATE state_meta
     SET current_revision = MAX(current_revision, {revision}), dirty = 1, checkpoint_pending = 1,
         unmanaged_write_detected = CASE WHEN EXISTS (SELECT 1 FROM active_operation WHERE id = 1)
           THEN unmanaged_write_detected ELSE 1 END
   WHERE id = 1;
END;
"""


def document_trigger_sql() -> str:
    statements = [
        _accounting_trigger(table, operation)
        for table in DOCUMENT_TABLES
        for operation in ("insert", "update", "delete")
    ]
    statements.extend(
        [
            "CREATE TRIGGER ts_immutable_document_identity BEFORE UPDATE ON document "
            "WHEN NEW.id IS NOT OLD.id OR NEW.visible_id IS NOT OLD.visible_id OR "
            "NEW.namespace IS NOT OLD.namespace OR NEW.display_number IS NOT OLD.display_number OR "
            "NEW.created_at IS NOT OLD.created_at BEGIN SELECT RAISE(ABORT, 'document identity is immutable'); END;",
            "CREATE TRIGGER ts_immutable_document_revision_update BEFORE UPDATE ON document_revision "
            "BEGIN SELECT RAISE(ABORT, 'document_revision is append-only'); END;",
            "CREATE TRIGGER ts_immutable_document_revision_delete BEFORE DELETE ON document_revision "
            "BEGIN SELECT RAISE(ABORT, 'document_revision is append-only'); END;",
            "CREATE TRIGGER ts_immutable_document_alias BEFORE UPDATE ON document_path_alias "
            "WHEN NEW.id IS NOT OLD.id OR NEW.document_id IS NOT OLD.document_id OR NEW.path IS NOT OLD.path "
            "OR NEW.alias_kind IS NOT OLD.alias_kind OR NEW.created_revision IS NOT OLD.created_revision "
            "BEGIN SELECT RAISE(ABORT, 'document alias identity is immutable'); END;",
            "CREATE TRIGGER ts_immutable_document_conversion BEFORE UPDATE ON document_conversion "
            "WHEN NEW.id IS NOT OLD.id OR NEW.source_path IS NOT OLD.source_path OR NEW.source_sha256 IS NOT OLD.source_sha256 "
            "OR NEW.artifact_id IS NOT OLD.artifact_id OR NEW.visible_id IS NOT OLD.visible_id "
            "OR NEW.classification IS NOT OLD.classification OR NEW.imported_revision IS NOT OLD.imported_revision "
            "OR NEW.created_at IS NOT OLD.created_at BEGIN SELECT RAISE(ABORT, 'document conversion identity is immutable'); END;",
        ]
    )
    return "\n".join(statements)


def create_document_schema(connection: sqlite3.Connection, *, include_triggers: bool = True) -> None:
    connection.executescript(DOCUMENT_SCHEMA_SQL)
    if include_triggers:
        connection.executescript(document_trigger_sql())


def document_migration_digest() -> str:
    return hashlib.sha256((DOCUMENT_SCHEMA_SQL + "\n" + document_trigger_sql()).encode("utf-8")).hexdigest()
