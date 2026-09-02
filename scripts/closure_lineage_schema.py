#!/usr/bin/env python3
"""Schema-3 recursive closure lineage resources."""

from __future__ import annotations

import hashlib
import sqlite3

from hybrid_state_schema import UUID_SQL


HYBRID_SCHEMA_VERSION = 3
CLOSURE_SCHEMA_VERSION = 1
CLOSURE_TABLES = (
    "closure_graph_meta",
    "closure_element",
    "lineage_claim",
    "closure_record",
    "closure_ancestor_path",
    "closure_rollup",
    "closure_blocker",
    "proof_recipe",
    "proof_attempt",
    "recovery_case",
    "lineage_tombstone",
)
CLOSURE_DOMAIN_TABLES = CLOSURE_TABLES
CLOSURE_PORTABLE_TABLES = CLOSURE_TABLES


CLOSURE_SCHEMA_SQL = r"""
CREATE TABLE closure_graph_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    graph_revision INTEGER NOT NULL CHECK (graph_revision >= 0),
    evaluator_version TEXT NOT NULL,
    source_digest TEXT NOT NULL CHECK (length(source_digest) = 64),
    updated_at TEXT NOT NULL
);

CREATE TABLE closure_element (
    id TEXT PRIMARY KEY,
    role TEXT NOT NULL CHECK (role IN ('cycle', 'obligation')),
    element_kind TEXT NOT NULL,
    artifact_id TEXT REFERENCES artifact(id) ON DELETE RESTRICT,
    cycle_id TEXT UNIQUE REFERENCES cycle(id) ON DELETE RESTRICT,
    requirement_id TEXT UNIQUE REFERENCES requirement(id) ON DELETE RESTRICT,
    subject_revision INTEGER NOT NULL CHECK (subject_revision > 0),
    subject_digest TEXT NOT NULL CHECK (length(subject_digest) = 64),
    envelope_json TEXT NOT NULL CHECK (json_valid(envelope_json)),
    envelope_digest TEXT NOT NULL CHECK (length(envelope_digest) = 64),
    created_revision INTEGER NOT NULL CHECK (created_revision > 0),
    updated_revision INTEGER NOT NULL CHECK (updated_revision >= created_revision),
    CHECK ((role = 'cycle' AND cycle_id IS NOT NULL AND requirement_id IS NULL) OR
           (role = 'obligation' AND cycle_id IS NULL AND requirement_id IS NOT NULL))
) WITHOUT ROWID;
CREATE INDEX closure_element_artifact_idx ON closure_element(artifact_id, id);

CREATE TABLE lineage_claim (
    id TEXT PRIMARY KEY,
    child_element_id TEXT NOT NULL REFERENCES closure_element(id) ON DELETE RESTRICT,
    parent_element_id TEXT NOT NULL REFERENCES closure_element(id) ON DELETE RESTRICT,
    parent_requirement_id TEXT NOT NULL REFERENCES requirement(id) ON DELETE RESTRICT,
    relationship_type TEXT NOT NULL CHECK (relationship_type IN ('fulfills', 'contributes', 'informs', 'supersedes')),
    observed_parent_revision INTEGER NOT NULL CHECK (observed_parent_revision > 0),
    observed_requirement_digest TEXT NOT NULL CHECK (length(observed_requirement_digest) = 64),
    envelope_digest TEXT NOT NULL CHECK (length(envelope_digest) = 64),
    created_revision INTEGER NOT NULL CHECK (created_revision > 0),
    retired_revision INTEGER CHECK (retired_revision IS NULL OR retired_revision >= created_revision),
    CHECK (child_element_id <> parent_element_id)
) WITHOUT ROWID;
CREATE INDEX lineage_claim_child_idx ON lineage_claim(child_element_id, retired_revision, id);
CREATE INDEX lineage_claim_parent_idx ON lineage_claim(parent_element_id, parent_requirement_id, retired_revision, id);

CREATE TABLE closure_record (
    id TEXT PRIMARY KEY,
    element_id TEXT NOT NULL REFERENCES closure_element(id) ON DELETE RESTRICT,
    obligation_id TEXT REFERENCES requirement(id) ON DELETE RESTRICT,
    subject_revision INTEGER NOT NULL CHECK (subject_revision > 0),
    subject_digest TEXT NOT NULL CHECK (length(subject_digest) = 64),
    method TEXT NOT NULL CHECK (method IN ('closed-loop', 'closed-manual')),
    evidence_health TEXT NOT NULL CHECK (evidence_health IN ('not-required', 'current', 'missing', 'stale', 'checker-error')),
    authorization_ref TEXT NOT NULL,
    evidence_json TEXT NOT NULL CHECK (json_valid(evidence_json)),
    created_revision INTEGER NOT NULL CHECK (created_revision > 0),
    superseded_revision INTEGER CHECK (superseded_revision IS NULL OR superseded_revision >= created_revision)
) WITHOUT ROWID;
CREATE INDEX closure_record_current_idx ON closure_record(element_id, obligation_id, superseded_revision, created_revision);

CREATE TABLE closure_ancestor_path (
    id TEXT PRIMARY KEY,
    ancestor_element_id TEXT NOT NULL REFERENCES closure_element(id) ON DELETE RESTRICT,
    descendant_element_id TEXT NOT NULL REFERENCES closure_element(id) ON DELETE RESTRICT,
    shortest_depth INTEGER NOT NULL CHECK (shortest_depth > 0),
    path_count INTEGER NOT NULL CHECK (path_count > 0),
    graph_revision INTEGER NOT NULL CHECK (graph_revision > 0),
    UNIQUE (ancestor_element_id, descendant_element_id)
) WITHOUT ROWID;
CREATE INDEX closure_path_descendant_idx ON closure_ancestor_path(descendant_element_id, ancestor_element_id);

CREATE TABLE closure_rollup (
    id TEXT PRIMARY KEY,
    element_id TEXT NOT NULL UNIQUE REFERENCES closure_element(id) ON DELETE RESTRICT,
    local_closure TEXT NOT NULL CHECK (local_closure IN ('open', 'closed-loop', 'closed-manual')),
    evidence_health TEXT NOT NULL CHECK (evidence_health IN ('not-required', 'current', 'missing', 'stale', 'checker-error')),
    graph_health TEXT NOT NULL CHECK (graph_health IN ('valid', 'recovery-required', 'invalid')),
    effective_closed INTEGER NOT NULL CHECK (effective_closed IN (0, 1)),
    reason_codes_json TEXT NOT NULL CHECK (json_valid(reason_codes_json)),
    open_descendants INTEGER NOT NULL CHECK (open_descendants >= 0),
    unknown_descendants INTEGER NOT NULL CHECK (unknown_descendants >= 0),
    invalid_descendants INTEGER NOT NULL CHECK (invalid_descendants >= 0),
    subject_revision INTEGER NOT NULL CHECK (subject_revision > 0),
    graph_revision INTEGER NOT NULL CHECK (graph_revision > 0),
    evaluator_version TEXT NOT NULL,
    evaluated_at TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE closure_blocker (
    id TEXT PRIMARY KEY,
    ancestor_element_id TEXT NOT NULL REFERENCES closure_element(id) ON DELETE RESTRICT,
    governing_requirement_id TEXT REFERENCES requirement(id) ON DELETE RESTRICT,
    blocking_element_id TEXT REFERENCES closure_element(id) ON DELETE RESTRICT,
    blocking_obligation_id TEXT REFERENCES requirement(id) ON DELETE RESTRICT,
    reason_code TEXT NOT NULL,
    depth INTEGER NOT NULL CHECK (depth >= 0),
    graph_revision INTEGER NOT NULL CHECK (graph_revision > 0)
) WITHOUT ROWID;
CREATE INDEX closure_blocker_lookup_idx ON closure_blocker(ancestor_element_id, depth, reason_code, id);

CREATE TABLE proof_recipe (
    id TEXT PRIMARY KEY,
    version INTEGER NOT NULL CHECK (version > 0),
    recipe_digest TEXT NOT NULL CHECK (length(recipe_digest) = 64),
    checker_id TEXT NOT NULL,
    checker_digest TEXT NOT NULL CHECK (length(checker_digest) = 64),
    declaration_json TEXT NOT NULL CHECK (json_valid(declaration_json)),
    created_revision INTEGER NOT NULL CHECK (created_revision > 0),
    revoked_revision INTEGER CHECK (revoked_revision IS NULL OR revoked_revision >= created_revision),
    UNIQUE (id, version)
) WITHOUT ROWID;

CREATE TABLE proof_attempt (
    id TEXT PRIMARY KEY,
    recipe_id TEXT NOT NULL REFERENCES proof_recipe(id) ON DELETE RESTRICT,
    element_id TEXT NOT NULL REFERENCES closure_element(id) ON DELETE RESTRICT,
    obligation_id TEXT REFERENCES requirement(id) ON DELETE RESTRICT,
    subject_revision INTEGER NOT NULL CHECK (subject_revision > 0),
    subject_digest TEXT NOT NULL CHECK (length(subject_digest) = 64),
    target_identity TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE CHECK (length(idempotency_key) = 64),
    state TEXT NOT NULL CHECK (state IN ('eligible', 'running', 'passed', 'failed', 'blocked', 'checker-error', 'timed-out', 'superseded')),
    lease_owner TEXT,
    lease_expires_at TEXT,
    result_json TEXT NOT NULL CHECK (json_valid(result_json)),
    created_revision INTEGER NOT NULL CHECK (created_revision > 0),
    updated_revision INTEGER NOT NULL CHECK (updated_revision >= created_revision)
) WITHOUT ROWID;
CREATE INDEX proof_attempt_element_idx ON proof_attempt(element_id, obligation_id, created_revision);

CREATE TABLE recovery_case (
    id TEXT PRIMARY KEY,
    element_id TEXT REFERENCES closure_element(id) ON DELETE RESTRICT,
    reason_code TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('open', 'retry-wait', 'escalated', 'resolved-restored', 'resolved-reparented', 'resolved-retired')),
    owner_ref TEXT,
    attempt_count INTEGER NOT NULL CHECK (attempt_count >= 0),
    next_retry_at TEXT,
    detail_json TEXT NOT NULL CHECK (json_valid(detail_json)),
    created_revision INTEGER NOT NULL CHECK (created_revision > 0),
    updated_revision INTEGER NOT NULL CHECK (updated_revision >= created_revision),
    closed_revision INTEGER CHECK (closed_revision IS NULL OR closed_revision >= created_revision)
) WITHOUT ROWID;
CREATE INDEX recovery_case_open_idx ON recovery_case(state, next_retry_at, id);

CREATE TABLE lineage_tombstone (
    id TEXT PRIMARY KEY,
    element_id TEXT NOT NULL,
    claim_id TEXT,
    disposition TEXT NOT NULL CHECK (disposition IN ('reparented', 'retired', 'abandoned')),
    reason TEXT NOT NULL,
    authorization_ref TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    created_revision INTEGER NOT NULL CHECK (created_revision > 0)
) WITHOUT ROWID;
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


def closure_trigger_sql() -> str:
    statements = [
        _accounting_trigger(table, operation)
        for table in CLOSURE_TABLES
        for operation in ("insert", "update", "delete")
    ]
    statements.extend(
        [
            "CREATE TRIGGER ts_immutable_closure_record_update BEFORE UPDATE ON closure_record "
            "WHEN NEW.id IS NOT OLD.id OR NEW.element_id IS NOT OLD.element_id OR "
            "NEW.obligation_id IS NOT OLD.obligation_id OR NEW.subject_revision IS NOT OLD.subject_revision OR "
            "NEW.subject_digest IS NOT OLD.subject_digest OR NEW.method IS NOT OLD.method OR "
            "NEW.evidence_health IS NOT OLD.evidence_health OR NEW.authorization_ref IS NOT OLD.authorization_ref OR "
            "NEW.evidence_json IS NOT OLD.evidence_json OR NEW.created_revision IS NOT OLD.created_revision "
            "BEGIN SELECT RAISE(ABORT, 'closure_record is append-only except supersession'); END;",
            "CREATE TRIGGER ts_immutable_closure_record_delete BEFORE DELETE ON closure_record "
            "BEGIN SELECT RAISE(ABORT, 'closure_record is append-only'); END;",
            "CREATE TRIGGER ts_immutable_lineage_tombstone_update BEFORE UPDATE ON lineage_tombstone "
            "BEGIN SELECT RAISE(ABORT, 'lineage_tombstone is append-only'); END;",
            "CREATE TRIGGER ts_immutable_lineage_tombstone_delete BEFORE DELETE ON lineage_tombstone "
            "BEGIN SELECT RAISE(ABORT, 'lineage_tombstone is append-only'); END;",
        ]
    )
    return "\n".join(statements)


def create_closure_schema(connection: sqlite3.Connection, *, include_triggers: bool = True) -> None:
    connection.executescript(CLOSURE_SCHEMA_SQL)
    if include_triggers:
        connection.executescript(closure_trigger_sql())


def closure_migration_digest() -> str:
    return hashlib.sha256((CLOSURE_SCHEMA_SQL + "\n" + closure_trigger_sql()).encode()).hexdigest()
