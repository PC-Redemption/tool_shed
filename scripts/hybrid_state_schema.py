#!/usr/bin/env python3
"""Schema-version-1 resources for Tool Shed's hybrid operational state."""

from __future__ import annotations

import hashlib
import re
import sqlite3


SCHEMA_VERSION = 1
APPLICATION_ID = 0x54534831  # TSH1
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()

DOMAIN_TABLES = (
    "workspace",
    "cycle",
    "artifact",
    "import_record",
    "relationship",
    "requirement",
    "material_change",
    "evidence_reference",
    "verification_result",
    "outcome_verdict",
    "reconciliation",
)

PORTABLE_TABLES = (
    "workspace",
    "managed_operation",
    "structural_change",
    "event",
    "cycle",
    "artifact",
    "import_record",
    "relationship",
    "requirement",
    "material_change",
    "evidence_reference",
    "verification_result",
    "outcome_verdict",
    "reconciliation",
    "migration_ledger",
    "export_ledger",
    "checkpoint_ledger",
)

APPEND_ONLY_TABLES = (
    "structural_change",
    "event",
    "migration_ledger",
    "export_ledger",
    "checkpoint_ledger",
)

IMMUTABLE_DOMAIN_FIELDS = {
    "workspace": ("id", "project_id", "created_at"),
    "cycle": ("id", "origin_artifact_id", "opened_at"),
    "artifact": ("id", "created_at"),
    "import_record": (
        "id",
        "artifact_id",
        "source_path",
        "source_sha256",
        "provenance",
        "parser_version",
        "imported_at",
    ),
    "relationship": (
        "id",
        "from_artifact_id",
        "relation_type",
        "to_artifact_id",
        "provenance",
        "created_revision",
    ),
    "requirement": ("id", "cycle_id", "origin_artifact_id", "accepted_revision"),
    "material_change": (
        "id",
        "cycle_id",
        "requirement_id",
        "decision_id",
        "recorded_revision",
    ),
    "evidence_reference": (
        "id",
        "cycle_id",
        "reference",
        "sha256",
        "target_identity",
        "collected_at",
    ),
    "verification_result": (
        "id",
        "evidence_id",
        "requirement_id",
        "source_revision",
        "verified_at",
    ),
    "outcome_verdict": (
        "id",
        "cycle_id",
        "authorization_ref",
        "decided_revision",
        "decided_at",
    ),
    "reconciliation": ("id", "cycle_id", "origin_revision", "verdict_id"),
}


SCHEMA_SQL = r"""
CREATE TABLE state_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version >= 1),
    project_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    storage_mode TEXT NOT NULL CHECK (storage_mode IN ('file', 'shadow', 'hybrid')),
    current_revision INTEGER NOT NULL CHECK (current_revision >= 0),
    last_verified_revision INTEGER NOT NULL CHECK (last_verified_revision >= 0),
    last_checkpoint_revision INTEGER NOT NULL CHECK (last_checkpoint_revision >= 0),
    dirty INTEGER NOT NULL CHECK (dirty IN (0, 1)),
    checkpoint_pending INTEGER NOT NULL CHECK (checkpoint_pending IN (0, 1)),
    unmanaged_write_detected INTEGER NOT NULL CHECK (unmanaged_write_detected IN (0, 1)),
    source_digest TEXT NOT NULL CHECK (length(source_digest) = 64),
    checkpoint_digest TEXT CHECK (checkpoint_digest IS NULL OR length(checkpoint_digest) = 64),
    schema_trigger_digest TEXT NOT NULL CHECK (length(schema_trigger_digest) = 64)
);

CREATE TABLE managed_operation (
    id TEXT PRIMARY KEY,
    revision INTEGER NOT NULL UNIQUE CHECK (revision > 0),
    command TEXT NOT NULL,
    actor TEXT NOT NULL,
    started_at TEXT NOT NULL,
    committed_at TEXT,
    expected_writes INTEGER CHECK (expected_writes IS NULL OR expected_writes >= 0),
    actual_writes INTEGER NOT NULL DEFAULT 0 CHECK (actual_writes >= 0),
    status TEXT NOT NULL CHECK (status IN ('active', 'complete', 'rolled-back'))
) WITHOUT ROWID;

CREATE TABLE active_operation (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    operation_id TEXT NOT NULL UNIQUE REFERENCES managed_operation(id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL UNIQUE REFERENCES managed_operation(revision) ON DELETE RESTRICT
);

CREATE TABLE structural_change (
    id TEXT PRIMARY KEY,
    revision INTEGER NOT NULL CHECK (revision > 0),
    operation_id TEXT REFERENCES managed_operation(id) ON DELETE RESTRICT,
    table_name TEXT NOT NULL,
    row_id TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('insert', 'update', 'delete')),
    managed INTEGER NOT NULL CHECK (managed IN (0, 1)),
    payload_digest TEXT NOT NULL CHECK (length(payload_digest) = 64),
    recorded_at TEXT NOT NULL
) WITHOUT ROWID;
CREATE INDEX structural_change_revision_idx ON structural_change(revision, id);

CREATE TABLE event (
    id TEXT PRIMARY KEY,
    revision INTEGER NOT NULL CHECK (revision > 0),
    operation_id TEXT REFERENCES managed_operation(id) ON DELETE RESTRICT,
    kind TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    recorded_at TEXT NOT NULL
) WITHOUT ROWID;
CREATE INDEX event_revision_idx ON event(revision, id);

CREATE TABLE workspace (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE cycle (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    origin_artifact_id TEXT REFERENCES artifact(id) ON DELETE RESTRICT,
    accepted_outcome TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    closed_at TEXT
) WITHOUT ROWID;

CREATE TABLE artifact (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    display_number TEXT,
    current_path TEXT NOT NULL UNIQUE,
    authority_mode TEXT NOT NULL CHECK (authority_mode IN ('file', 'sqlite', 'projection')),
    lifecycle_state TEXT NOT NULL,
    content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE import_record (
    id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL REFERENCES artifact(id) ON DELETE RESTRICT,
    source_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL CHECK (length(source_sha256) = 64),
    tracked_state TEXT NOT NULL CHECK (tracked_state IN ('tracked', 'untracked', 'ignored', 'unknown')),
    provenance TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    parse_status TEXT NOT NULL CHECK (parse_status IN ('parsed', 'unresolved', 'unsupported')),
    unresolved_json TEXT NOT NULL CHECK (json_valid(unresolved_json)),
    imported_at TEXT NOT NULL,
    UNIQUE (artifact_id, source_sha256)
) WITHOUT ROWID;

CREATE TABLE relationship (
    id TEXT PRIMARY KEY,
    from_artifact_id TEXT NOT NULL REFERENCES artifact(id) ON DELETE RESTRICT,
    relation_type TEXT NOT NULL,
    to_artifact_id TEXT NOT NULL REFERENCES artifact(id) ON DELETE RESTRICT,
    provenance TEXT NOT NULL,
    created_revision INTEGER NOT NULL CHECK (created_revision > 0),
    retired_revision INTEGER CHECK (retired_revision IS NULL OR retired_revision >= created_revision),
    CHECK (from_artifact_id <> to_artifact_id)
) WITHOUT ROWID;

CREATE TABLE requirement (
    id TEXT PRIMARY KEY,
    cycle_id TEXT NOT NULL REFERENCES cycle(id) ON DELETE RESTRICT,
    origin_artifact_id TEXT NOT NULL REFERENCES artifact(id) ON DELETE RESTRICT,
    accepted_outcome TEXT NOT NULL,
    disposition TEXT NOT NULL,
    accepted_revision INTEGER NOT NULL CHECK (accepted_revision > 0),
    milestone_key TEXT NOT NULL,
    evidence_gate_key TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE material_change (
    id TEXT PRIMARY KEY,
    cycle_id TEXT NOT NULL REFERENCES cycle(id) ON DELETE RESTRICT,
    requirement_id TEXT REFERENCES requirement(id) ON DELETE RESTRICT,
    decision_id TEXT,
    summary TEXT NOT NULL,
    rationale TEXT NOT NULL,
    authorization_ref TEXT NOT NULL,
    supersedes_change_id TEXT REFERENCES material_change(id) ON DELETE RESTRICT,
    evidence_rerun_json TEXT NOT NULL CHECK (json_valid(evidence_rerun_json)),
    recorded_revision INTEGER NOT NULL CHECK (recorded_revision > 0),
    CHECK (requirement_id IS NOT NULL OR decision_id IS NOT NULL)
) WITHOUT ROWID;

CREATE TABLE evidence_reference (
    id TEXT PRIMARY KEY,
    cycle_id TEXT NOT NULL REFERENCES cycle(id) ON DELETE RESTRICT,
    kind TEXT NOT NULL,
    reference TEXT NOT NULL,
    sha256 TEXT CHECK (sha256 IS NULL OR length(sha256) = 64),
    target_identity TEXT NOT NULL,
    collected_at TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE verification_result (
    id TEXT PRIMARY KEY,
    evidence_id TEXT NOT NULL REFERENCES evidence_reference(id) ON DELETE RESTRICT,
    requirement_id TEXT REFERENCES requirement(id) ON DELETE RESTRICT,
    status TEXT NOT NULL,
    command_or_test_id TEXT NOT NULL,
    source_revision INTEGER NOT NULL CHECK (source_revision > 0),
    verified_at TEXT NOT NULL,
    details_json TEXT CHECK (details_json IS NULL OR json_valid(details_json))
) WITHOUT ROWID;

CREATE TABLE outcome_verdict (
    id TEXT PRIMARY KEY,
    cycle_id TEXT NOT NULL REFERENCES cycle(id) ON DELETE RESTRICT,
    scope TEXT NOT NULL,
    disposition TEXT NOT NULL,
    summary TEXT NOT NULL,
    authorization_ref TEXT NOT NULL,
    decided_revision INTEGER NOT NULL CHECK (decided_revision > 0),
    decided_at TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE reconciliation (
    id TEXT PRIMARY KEY,
    cycle_id TEXT NOT NULL REFERENCES cycle(id) ON DELETE RESTRICT,
    origin_revision INTEGER NOT NULL CHECK (origin_revision > 0),
    product_truth_ref TEXT NOT NULL,
    verdict_id TEXT NOT NULL REFERENCES outcome_verdict(id) ON DELETE RESTRICT,
    state TEXT NOT NULL CHECK (state IN ('open', 'reconciliation-required', 'reconciled')),
    compared_at TEXT NOT NULL,
    residual_work_json TEXT NOT NULL CHECK (json_valid(residual_work_json))
) WITHOUT ROWID;

CREATE TABLE migration_ledger (
    id TEXT PRIMARY KEY,
    from_schema INTEGER NOT NULL CHECK (from_schema >= 0),
    to_schema INTEGER NOT NULL CHECK (to_schema > from_schema),
    migration_digest TEXT NOT NULL CHECK (length(migration_digest) = 64),
    source_digest TEXT NOT NULL CHECK (length(source_digest) = 64),
    backup_ref TEXT,
    status TEXT NOT NULL CHECK (status IN ('active', 'complete', 'failed')),
    started_at TEXT NOT NULL,
    completed_at TEXT
) WITHOUT ROWID;

CREATE TABLE export_ledger (
    id TEXT PRIMARY KEY,
    revision INTEGER NOT NULL CHECK (revision >= 0),
    format_version INTEGER NOT NULL CHECK (format_version >= 1),
    path TEXT NOT NULL,
    digest TEXT NOT NULL CHECK (length(digest) = 64),
    status TEXT NOT NULL CHECK (status IN ('complete', 'failed')),
    created_at TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE checkpoint_ledger (
    id TEXT PRIMARY KEY,
    revision INTEGER NOT NULL CHECK (revision >= 0),
    path TEXT NOT NULL,
    digest TEXT NOT NULL CHECK (length(digest) = 64),
    source_commit TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('complete', 'failed')),
    created_at TEXT NOT NULL
) WITHOUT ROWID;
"""


UUID_SQL = (
    "lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || "
    "substr(lower(hex(randomblob(2))), 2) || '-' || "
    "substr('89ab', 1 + abs(random()) % 4, 1) || substr(lower(hex(randomblob(2))), 2) || '-' || "
    "lower(hex(randomblob(6)))"
)


def _trigger_sql(table: str, operation: str) -> str:
    row = "OLD" if operation == "delete" else "NEW"
    trigger = f"ts_account_{table}_{operation}"
    revision = "COALESCE((SELECT revision FROM active_operation WHERE id = 1), (SELECT current_revision + 1 FROM state_meta WHERE id = 1))"
    operation_id = "(SELECT operation_id FROM active_operation WHERE id = 1)"
    managed = "CASE WHEN EXISTS (SELECT 1 FROM active_operation WHERE id = 1) THEN 1 ELSE 0 END"
    stamp = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"
    return f"""
CREATE TRIGGER {trigger} AFTER {operation.upper()} ON {table}
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
     SET current_revision = MAX(current_revision, {revision}),
         dirty = 1,
         checkpoint_pending = 1,
         unmanaged_write_detected = CASE
           WHEN EXISTS (SELECT 1 FROM active_operation WHERE id = 1)
           THEN unmanaged_write_detected ELSE 1 END
   WHERE id = 1;
END;
"""


def trigger_sql() -> str:
    statements: list[str] = []
    for table in DOMAIN_TABLES:
        for operation in ("insert", "update", "delete"):
            statements.append(_trigger_sql(table, operation))
    for table, fields in IMMUTABLE_DOMAIN_FIELDS.items():
        changed = " OR ".join(f"NEW.{field} IS NOT OLD.{field}" for field in fields)
        statements.append(
            f"CREATE TRIGGER ts_immutable_{table}_fields BEFORE UPDATE ON {table} "
            f"WHEN {changed} BEGIN SELECT RAISE(ABORT, "
            f"'{table} identity or historical fields are immutable'); END;"
        )
    for table in APPEND_ONLY_TABLES:
        statements.append(
            f"CREATE TRIGGER ts_immutable_{table}_update BEFORE UPDATE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END;"
        )
        statements.append(
            f"CREATE TRIGGER ts_immutable_{table}_delete BEFORE DELETE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END;"
        )
    return "\n".join(statements)


def create_schema(connection: sqlite3.Connection, *, include_triggers: bool = True) -> None:
    connection.executescript(SCHEMA_SQL)
    if include_triggers:
        connection.executescript(trigger_sql())
    connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def create_triggers(connection: sqlite3.Connection) -> None:
    connection.executescript(trigger_sql())


def normalized_schema(connection: sqlite3.Connection) -> str:
    rows = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_schema "
        "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()
    return "\n".join(
        "|".join((str(row[0]), str(row[1]), str(row[2]), re.sub(r"\\s+", " ", str(row[3])).strip()))
        for row in rows
    )


def schema_digest(connection: sqlite3.Connection) -> str:
    return hashlib.sha256(normalized_schema(connection).encode("utf-8")).hexdigest()


def migration_digest() -> str:
    material = (SCHEMA_SQL + "\n" + trigger_sql()).encode("utf-8")
    return hashlib.sha256(material).hexdigest()
