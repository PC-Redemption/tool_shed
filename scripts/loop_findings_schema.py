#!/usr/bin/env python3
"""Persisted outcome-loop finding resources for Hybrid schemas 4 and 5."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import hashlib
import sqlite3

from hybrid_state_schema import UUID_SQL


HYBRID_SCHEMA_VERSION = 5
LOOP_FINDING_SCHEMA_VERSION = 2
LOOP_FINDING_TABLES = ("loop_finding_meta", "loop_finding")
LOOP_FINDING_DOMAIN_TABLES = LOOP_FINDING_TABLES
LOOP_FINDING_PORTABLE_TABLES = LOOP_FINDING_TABLES


LOOP_FINDING_SCHEMA_V1_SQL = r"""
CREATE TABLE loop_finding_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    discovery_version TEXT NOT NULL,
    last_source_revision INTEGER NOT NULL CHECK (last_source_revision >= 0),
    last_source_digest TEXT NOT NULL CHECK (length(last_source_digest) = 64),
    updated_at TEXT NOT NULL
);

CREATE TABLE loop_finding (
    id TEXT PRIMARY KEY,
    visible_id TEXT NOT NULL UNIQUE,
    finding_key TEXT NOT NULL UNIQUE CHECK (length(finding_key) = 64),
    category TEXT NOT NULL CHECK (category IN ('semantic-lifecycle-drift')),
    severity TEXT NOT NULL CHECK (severity IN ('attention')),
    reason_code TEXT NOT NULL CHECK (reason_code IN ('PROMOTED_IDEA_LIFECYCLE_STALE')),
    subject_artifact_id TEXT NOT NULL REFERENCES artifact(id) ON DELETE RESTRICT,
    subject_visible_id TEXT NOT NULL,
    observed_state TEXT NOT NULL,
    expected_state TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('active', 'resolved')),
    source_revision INTEGER NOT NULL CHECK (source_revision > 0),
    first_observed_at TEXT NOT NULL,
    last_observed_at TEXT NOT NULL,
    resolved_at TEXT,
    recurrence_count INTEGER NOT NULL CHECK (recurrence_count >= 0),
    command TEXT NOT NULL,
    CHECK ((state = 'active' AND resolved_at IS NULL) OR
           (state = 'resolved' AND resolved_at IS NOT NULL))
) WITHOUT ROWID;
CREATE INDEX loop_finding_state_idx ON loop_finding(state, severity, last_observed_at, visible_id);
CREATE INDEX loop_finding_subject_idx ON loop_finding(subject_artifact_id, state, visible_id);
"""

LOOP_FINDING_CATEGORIES = (
    "semantic-lifecycle-drift",
    "outcome-health",
    "outcome-reconciliation",
    "outcome-propagation",
    "lineage-health",
    "evidence-health",
)
LOOP_FINDING_REASON_CODES = (
    "PROMOTED_IDEA_LIFECYCLE_STALE",
    "OUTCOME_BLOCKED",
    "OUTCOME_STALLED",
    "TERMINAL_OUTCOME_UNRECONCILED",
    "INVALID_RECONCILED_DISPOSITION",
    "OUTCOME_RESULT_UNPROPAGATED",
    "LINEAGE_INVALID",
    "LINEAGE_RECOVERY_REQUIRED",
    "CLOSURE_EVIDENCE_MISSING",
    "CLOSURE_EVIDENCE_STALE",
    "CLOSURE_EVIDENCE_CHECKER_ERROR",
)

LOOP_FINDING_SCHEMA_V2_SQL = LOOP_FINDING_SCHEMA_V1_SQL.replace(
    "CHECK (schema_version = 1)",
    "CHECK (schema_version = 2)",
).replace(
    "CHECK (category IN ('semantic-lifecycle-drift'))",
    "CHECK (category IN (" + ", ".join(repr(value) for value in LOOP_FINDING_CATEGORIES) + "))",
).replace(
    "CHECK (reason_code IN ('PROMOTED_IDEA_LIFECYCLE_STALE'))",
    "CHECK (reason_code IN (" + ", ".join(repr(value) for value in LOOP_FINDING_REASON_CODES) + "))",
)


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


def loop_finding_trigger_sql() -> str:
    return "\n".join(
        _accounting_trigger(table, operation)
        for table in LOOP_FINDING_TABLES
        for operation in ("insert", "update", "delete")
    )


def create_loop_finding_schema(
    connection: sqlite3.Connection,
    *,
    include_triggers: bool = True,
    schema_version: int = LOOP_FINDING_SCHEMA_VERSION,
) -> None:
    if schema_version not in {1, 2}:
        raise ValueError(f"unsupported loop-finding schema version: {schema_version}")
    connection.executescript(
        LOOP_FINDING_SCHEMA_V1_SQL if schema_version == 1 else LOOP_FINDING_SCHEMA_V2_SQL
    )
    if include_triggers:
        connection.executescript(loop_finding_trigger_sql())


def loop_finding_migration_digest(*, schema_version: int = LOOP_FINDING_SCHEMA_VERSION) -> str:
    sql = LOOP_FINDING_SCHEMA_V1_SQL if schema_version == 1 else LOOP_FINDING_SCHEMA_V2_SQL
    return hashlib.sha256(
        (sql + "\n" + loop_finding_trigger_sql()).encode()
    ).hexdigest()
