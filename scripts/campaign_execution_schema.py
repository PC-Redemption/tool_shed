#!/usr/bin/env python3
"""Hybrid schema-6 campaign execution and terminal reconciliation resources."""

from __future__ import annotations

import hashlib
import sqlite3

from hybrid_state_schema import UUID_SQL


HYBRID_SCHEMA_VERSION = 6
CAMPAIGN_EXECUTION_SCHEMA_VERSION = 1
CAMPAIGN_EXECUTION_TABLES = (
    "campaign_execution_meta",
    "campaign_execution",
    "campaign_execution_snapshot",
    "campaign_run",
    "campaign_operation",
    "campaign_assignment",
    "campaign_reconciliation_audit",
)
CAMPAIGN_EXECUTION_DOMAIN_TABLES = CAMPAIGN_EXECUTION_TABLES
CAMPAIGN_EXECUTION_PORTABLE_TABLES = CAMPAIGN_EXECUTION_TABLES


SCHEMA_SQL = r"""
CREATE TABLE campaign_execution_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    updated_at TEXT NOT NULL
);

CREATE TABLE campaign_execution (
    id TEXT PRIMARY KEY,
    cycle_id TEXT NOT NULL UNIQUE REFERENCES cycle(id) ON DELETE RESTRICT,
    source_version INTEGER NOT NULL CHECK (source_version > 0),
    source_digest TEXT NOT NULL CHECK (length(source_digest) = 64),
    state TEXT NOT NULL CHECK (state IN ('running', 'terminal')),
    result TEXT NOT NULL CHECK (result IN ('open', 'accepted', 'not-satisfied', 'superseded', 'mixed', 'unknown')),
    created_revision INTEGER NOT NULL CHECK (created_revision > 0),
    updated_revision INTEGER NOT NULL CHECK (updated_revision >= created_revision),
    updated_at TEXT NOT NULL
) WITHOUT ROWID;
CREATE INDEX campaign_execution_state_idx ON campaign_execution(state, cycle_id);

CREATE TABLE campaign_execution_snapshot (
    id TEXT PRIMARY KEY,
    campaign_execution_id TEXT NOT NULL REFERENCES campaign_execution(id) ON DELETE RESTRICT,
    source_version INTEGER NOT NULL,
    source_digest TEXT NOT NULL CHECK (length(source_digest) = 64),
    snapshot_json TEXT NOT NULL CHECK (json_valid(snapshot_json)),
    recorded_revision INTEGER NOT NULL CHECK (recorded_revision > 0),
    recorded_at TEXT NOT NULL,
    UNIQUE (campaign_execution_id, source_version),
    UNIQUE (campaign_execution_id, source_digest)
) WITHOUT ROWID;
CREATE INDEX campaign_execution_snapshot_idx ON campaign_execution_snapshot(campaign_execution_id, source_version);

CREATE TABLE campaign_run (
    id TEXT PRIMARY KEY,
    campaign_execution_id TEXT NOT NULL REFERENCES campaign_execution(id) ON DELETE RESTRICT,
    state TEXT NOT NULL CHECK (state IN ('queued', 'running', 'completed', 'failed', 'cancelled', 'superseded')),
    result TEXT NOT NULL,
    updated_revision INTEGER NOT NULL CHECK (updated_revision > 0)
) WITHOUT ROWID;
CREATE INDEX campaign_run_execution_idx ON campaign_run(campaign_execution_id, state, id);

CREATE TABLE campaign_operation (
    id TEXT PRIMARY KEY,
    campaign_execution_id TEXT NOT NULL REFERENCES campaign_execution(id) ON DELETE RESTRICT,
    run_id TEXT REFERENCES campaign_run(id) ON DELETE RESTRICT,
    state TEXT NOT NULL CHECK (state IN ('queued', 'running', 'completed', 'failed', 'cancelled', 'superseded')),
    result TEXT NOT NULL,
    updated_revision INTEGER NOT NULL CHECK (updated_revision > 0)
) WITHOUT ROWID;
CREATE INDEX campaign_operation_execution_idx ON campaign_operation(campaign_execution_id, state, id);

CREATE TABLE campaign_assignment (
    id TEXT PRIMARY KEY,
    campaign_execution_id TEXT NOT NULL REFERENCES campaign_execution(id) ON DELETE RESTRICT,
    run_id TEXT REFERENCES campaign_run(id) ON DELETE RESTRICT,
    operation_id TEXT REFERENCES campaign_operation(id) ON DELETE RESTRICT,
    state TEXT NOT NULL CHECK (state IN ('pending', 'leased', 'completed', 'cancelled', 'retired')),
    runnable INTEGER NOT NULL CHECK (runnable IN (0, 1)),
    stale_reason TEXT,
    terminal_disposition TEXT,
    retired_revision INTEGER,
    updated_revision INTEGER NOT NULL CHECK (updated_revision > 0),
    CHECK ((state = 'retired' AND runnable = 0 AND stale_reason IS NOT NULL
            AND terminal_disposition IS NOT NULL AND retired_revision IS NOT NULL)
        OR (state <> 'retired' AND terminal_disposition IS NULL AND retired_revision IS NULL))
) WITHOUT ROWID;
CREATE INDEX campaign_assignment_execution_idx ON campaign_assignment(campaign_execution_id, state, runnable, id);

CREATE TABLE campaign_reconciliation_audit (
    id TEXT PRIMARY KEY,
    campaign_execution_id TEXT NOT NULL REFERENCES campaign_execution(id) ON DELETE RESTRICT,
    cycle_id TEXT NOT NULL REFERENCES cycle(id) ON DELETE RESTRICT,
    manifest_digest TEXT NOT NULL UNIQUE CHECK (length(manifest_digest) = 64),
    prior_state TEXT NOT NULL,
    counts_json TEXT NOT NULL CHECK (json_valid(counts_json)),
    assignment_dispositions_json TEXT NOT NULL CHECK (json_valid(assignment_dispositions_json)),
    execution_result TEXT NOT NULL,
    terminal_disposition TEXT NOT NULL CHECK (terminal_disposition IN ('administratively-reconciled', 'not-satisfied', 'superseded')),
    reason TEXT NOT NULL,
    actor TEXT NOT NULL,
    authorization_ref TEXT NOT NULL,
    handoff_evidence TEXT,
    superseding_outcome_ref TEXT,
    recorded_revision INTEGER NOT NULL CHECK (recorded_revision > 0),
    recorded_at TEXT NOT NULL
) WITHOUT ROWID;
CREATE INDEX campaign_reconciliation_cycle_idx ON campaign_reconciliation_audit(cycle_id, recorded_revision, id);
"""


def _accounting_trigger(table: str, operation: str) -> str:
    row = "OLD" if operation == "delete" else "NEW"
    revision = "COALESCE((SELECT revision FROM active_operation WHERE id=1), (SELECT current_revision + 1 FROM state_meta WHERE id=1))"
    operation_id = "(SELECT operation_id FROM active_operation WHERE id=1)"
    managed = "CASE WHEN EXISTS (SELECT 1 FROM active_operation WHERE id=1) THEN 1 ELSE 0 END"
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
    WHERE id = (SELECT operation_id FROM active_operation WHERE id=1);
  UPDATE state_meta
     SET current_revision = MAX(current_revision, {revision}), dirty = 1, checkpoint_pending = 1,
         unmanaged_write_detected = CASE WHEN EXISTS (SELECT 1 FROM active_operation WHERE id=1)
           THEN unmanaged_write_detected ELSE 1 END
   WHERE id=1;
END;
"""


def trigger_sql() -> str:
    statements = [
        _accounting_trigger(table, operation)
        for table in CAMPAIGN_EXECUTION_TABLES
        for operation in ("insert", "update", "delete")
    ]
    statements.extend(
        [
            "CREATE TRIGGER ts_immutable_campaign_reconciliation_audit_update BEFORE UPDATE ON campaign_reconciliation_audit BEGIN SELECT RAISE(ABORT, 'campaign reconciliation audit is append-only'); END;",
            "CREATE TRIGGER ts_immutable_campaign_reconciliation_audit_delete BEFORE DELETE ON campaign_reconciliation_audit BEGIN SELECT RAISE(ABORT, 'campaign reconciliation audit is append-only'); END;",
            "CREATE TRIGGER ts_immutable_campaign_execution_snapshot_update BEFORE UPDATE ON campaign_execution_snapshot BEGIN SELECT RAISE(ABORT, 'campaign execution snapshot is append-only'); END;",
            "CREATE TRIGGER ts_immutable_campaign_execution_snapshot_delete BEFORE DELETE ON campaign_execution_snapshot BEGIN SELECT RAISE(ABORT, 'campaign execution snapshot is append-only'); END;",
        ]
    )
    return "\n".join(statements)


def create_campaign_execution_schema(connection: sqlite3.Connection, *, include_triggers: bool = True) -> None:
    connection.executescript(SCHEMA_SQL)
    if include_triggers:
        connection.executescript(trigger_sql())


def migration_digest() -> str:
    return hashlib.sha256((SCHEMA_SQL + "\n" + trigger_sql()).encode()).hexdigest()
