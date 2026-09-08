#!/usr/bin/env python3
"""Persist campaign execution facts and reconcile terminal stale assignments safely."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import uuid
from typing import Any, Sequence

import document_store
import hybrid_state
from campaign_execution_schema import (
    CAMPAIGN_EXECUTION_SCHEMA_VERSION,
    CAMPAIGN_EXECUTION_TABLES,
    HYBRID_SCHEMA_VERSION,
    create_campaign_execution_schema,
    migration_digest,
)
from project_identity import (
    bind_state_token,
    load_project_identity,
    require_path_within,
    require_project_binding,
    resolved_workspace,
)


SCHEMA_VERSION = 1
SNAPSHOT_KIND = "tool-shed-campaign-execution-snapshot"
MANIFEST_KIND = "tool-shed-terminal-campaign-reconciliation-manifest"
RUN_STATES = {"queued", "running", "completed", "failed", "cancelled", "superseded"}
TERMINAL_RUN_STATES = {"completed", "failed", "cancelled", "superseded"}
ASSIGNMENT_STATES = {"pending", "leased", "completed", "cancelled", "retired"}
ACTIVE_ASSIGNMENT_STATES = {"pending", "leased"}
STALE_REASONS = {"terminal-owner", "expired-lease", "orphaned-owner", "superseded-owner"}
TERMINAL_DISPOSITIONS = {"administratively-reconciled", "not-satisfied", "superseded"}
EXECUTION_RESULTS = {"open", "accepted", "not-satisfied", "superseded", "mixed", "unknown"}


class CampaignExecutionError(RuntimeError):
    pass


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='table'")}


def _require_schema(connection: sqlite3.Connection) -> None:
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version != HYBRID_SCHEMA_VERSION or not set(CAMPAIGN_EXECUTION_TABLES) <= _tables(connection):
        raise CampaignExecutionError(
            f"terminal campaign reconciliation requires Hybrid schema {HYBRID_SCHEMA_VERSION}; found {version}"
        )


def _document_cycle(connection: sqlite3.Connection, identity: str) -> tuple[sqlite3.Row, sqlite3.Row]:
    document = document_store._lookup(connection, identity)
    if str(document["namespace"]) != "CAMP":
        raise CampaignExecutionError("terminal campaign reconciliation requires a CAMP document")
    cycle = connection.execute(
        "SELECT * FROM cycle WHERE origin_artifact_id=? ORDER BY opened_at DESC, id DESC LIMIT 1",
        (document["id"],),
    ).fetchone()
    if cycle is None:
        raise CampaignExecutionError("campaign has no outcome cycle")
    return document, cycle


def _execution_row(connection: sqlite3.Connection, cycle_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM campaign_execution WHERE cycle_id=?", (cycle_id,)
    ).fetchone()


def _current_material(connection: sqlite3.Connection, document: sqlite3.Row, cycle: sqlite3.Row) -> dict[str, Any]:
    execution = _execution_row(connection, str(cycle["id"]))
    runs: list[dict[str, Any]] = []
    operations: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []
    if execution is not None:
        execution_id = str(execution["id"])
        runs = [dict(row) for row in connection.execute(
            "SELECT id, state, result FROM campaign_run WHERE campaign_execution_id=? ORDER BY id",
            (execution_id,),
        )]
        operations = [dict(row) for row in connection.execute(
            "SELECT id, run_id, state, result FROM campaign_operation WHERE campaign_execution_id=? ORDER BY id",
            (execution_id,),
        )]
        assignments = [dict(row) for row in connection.execute(
            "SELECT id, run_id, operation_id, state, runnable, stale_reason, terminal_disposition, retired_revision "
            "FROM campaign_assignment WHERE campaign_execution_id=? ORDER BY id",
            (execution_id,),
        )]
    return {
        "document": {
            "artifact_id": str(document["id"]),
            "visible_id": str(document["visible_id"]),
            "revision": int(document["current_revision"]),
            "lifecycle": str(document["lifecycle_state"]),
        },
        "cycle": {
            "id": str(cycle["id"]),
            "lifecycle": str(cycle["lifecycle_state"]),
            "accepted_outcome": str(cycle["accepted_outcome"]),
        },
        "execution": None if execution is None else {
            "id": str(execution["id"]),
            "source_version": int(execution["source_version"]),
            "source_digest": str(execution["source_digest"]),
            "state": str(execution["state"]),
            "result": str(execution["result"]),
        },
        "runs": runs,
        "operations": operations,
        "assignments": assignments,
    }


def state_token(workspace: Path, identity: str, *, connection: sqlite3.Connection | None = None) -> str:
    workspace = resolved_workspace(workspace)

    def calculate(active: sqlite3.Connection) -> str:
        _require_schema(active)
        document, cycle = _document_cycle(active, identity)
        material = _current_material(active, document, cycle)
        material["database_revision"] = int(hybrid_state.meta_row(active)["current_revision"])
        return bind_state_token(
            workspace,
            "campaign-terminal-reconciliation",
            digest(material),
            allow_unidentified=True,
        )

    if connection is not None:
        return calculate(connection)
    with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)) as active:
        return calculate(active)


def _validate_id(value: object, label: str) -> str:
    text = str(value or "")
    if not text or len(text) > 160 or any(character.isspace() for character in text):
        raise CampaignExecutionError(f"{label} must be a non-space identifier of at most 160 characters")
    return text


def validate_snapshot(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CampaignExecutionError("campaign execution snapshot must be a JSON object")
    expected = {
        "schema_version", "kind", "project_id", "campaign_id", "source_version",
        "campaign_state", "execution_result", "runs", "operations", "assignments",
    }
    if set(payload) != expected or payload.get("schema_version") != 1 or payload.get("kind") != SNAPSHOT_KIND:
        raise CampaignExecutionError("campaign execution snapshot fields or identity are unsupported")
    try:
        uuid.UUID(str(payload["project_id"]))
    except (TypeError, ValueError) as error:
        raise CampaignExecutionError("snapshot project_id must be a UUID") from error
    source_version = payload.get("source_version")
    if not isinstance(source_version, int) or isinstance(source_version, bool) or source_version < 1:
        raise CampaignExecutionError("snapshot source_version must be a positive integer")
    if payload.get("campaign_state") != "running":
        raise CampaignExecutionError("new execution snapshots must describe a running campaign")
    if payload.get("execution_result") not in EXECUTION_RESULTS:
        raise CampaignExecutionError("snapshot execution_result is unsupported")
    normalized: dict[str, Any] = {
        **payload,
        "campaign_id": _validate_id(payload.get("campaign_id"), "campaign_id"),
        "runs": [], "operations": [], "assignments": [],
    }
    seen: set[str] = set()
    for label, key in (("run", "runs"), ("operation", "operations"), ("assignment", "assignments")):
        values = payload.get(key)
        if not isinstance(values, list):
            raise CampaignExecutionError(f"snapshot {key} must be an array")
        for raw in values:
            if not isinstance(raw, dict):
                raise CampaignExecutionError(f"snapshot {label} must be an object")
            identifier = _validate_id(raw.get("id"), f"{label}.id")
            scoped = f"{label}:{identifier}"
            if scoped in seen:
                raise CampaignExecutionError(f"duplicate {label} ID: {identifier}")
            seen.add(scoped)
            if label == "run":
                if set(raw) != {"id", "state", "result"} or raw.get("state") not in RUN_STATES:
                    raise CampaignExecutionError(f"run {identifier} has unsupported fields or state")
                item = {"id": identifier, "state": raw["state"], "result": str(raw.get("result") or "unknown")}
            elif label == "operation":
                if set(raw) != {"id", "run_id", "state", "result"} or raw.get("state") not in RUN_STATES:
                    raise CampaignExecutionError(f"operation {identifier} has unsupported fields or state")
                run_id = raw.get("run_id")
                item = {
                    "id": identifier,
                    "run_id": None if run_id is None else _validate_id(run_id, "operation.run_id"),
                    "state": raw["state"],
                    "result": str(raw.get("result") or "unknown"),
                }
            else:
                expected_assignment = {"id", "run_id", "operation_id", "state", "runnable", "stale_reason"}
                if set(raw) != expected_assignment or raw.get("state") not in ASSIGNMENT_STATES:
                    raise CampaignExecutionError(f"assignment {identifier} has unsupported fields or state")
                if not isinstance(raw.get("runnable"), bool):
                    raise CampaignExecutionError(f"assignment {identifier} runnable must be boolean")
                stale_reason = raw.get("stale_reason")
                if stale_reason is not None and stale_reason not in STALE_REASONS:
                    raise CampaignExecutionError(f"assignment {identifier} stale_reason is unsupported")
                item = {
                    "id": identifier,
                    "run_id": None if raw.get("run_id") is None else _validate_id(raw["run_id"], "assignment.run_id"),
                    "operation_id": None if raw.get("operation_id") is None else _validate_id(raw["operation_id"], "assignment.operation_id"),
                    "state": raw["state"], "runnable": raw["runnable"], "stale_reason": stale_reason,
                }
            normalized[key].append(item)
    run_ids = {item["id"] for item in normalized["runs"]}
    operation_ids = {item["id"] for item in normalized["operations"]}
    if any(item["run_id"] is not None and item["run_id"] not in run_ids for item in normalized["operations"]):
        raise CampaignExecutionError("operation references an unknown run")
    for item in normalized["assignments"]:
        if item["run_id"] is not None and item["run_id"] not in run_ids:
            raise CampaignExecutionError(f"assignment {item['id']} references an unknown run")
        if item["operation_id"] is not None and item["operation_id"] not in operation_ids:
            raise CampaignExecutionError(f"assignment {item['id']} references an unknown operation")
    normalized["runs"].sort(key=lambda item: item["id"])
    normalized["operations"].sort(key=lambda item: item["id"])
    normalized["assignments"].sort(key=lambda item: item["id"])
    return normalized


def record_snapshot(
    workspace: Path, identity: str, snapshot_path: Path, *, project_binding: str,
    expected_token: str, actor: str,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    source = require_path_within(workspace, snapshot_path if snapshot_path.is_absolute() else workspace / snapshot_path)
    snapshot = validate_snapshot(json.loads(source.read_text(encoding="utf-8")))
    project = load_project_identity(workspace)
    if snapshot["project_id"] != project["project_id"]:
        raise CampaignExecutionError("snapshot belongs to another project")
    snapshot_digest = digest(snapshot)

    def existing(connection: sqlite3.Connection) -> dict[str, Any] | None:
        _require_schema(connection)
        document, cycle = _document_cycle(connection, identity)
        if snapshot["campaign_id"] != document["visible_id"]:
            raise CampaignExecutionError("snapshot campaign_id does not match the selected campaign")
        execution = _execution_row(connection, str(cycle["id"]))
        if execution is not None and str(execution["source_digest"]) == snapshot_digest:
            return {"campaign_id": document["visible_id"], "source_version": snapshot["source_version"], "idempotent": True}
        if state_token(workspace, identity, connection=connection) != expected_token:
            raise CampaignExecutionError("campaign execution state token is stale")
        if execution is not None:
            if str(execution["state"]) == "terminal":
                raise CampaignExecutionError("a reconciled terminal campaign cannot accept a new execution snapshot")
            if snapshot["source_version"] <= int(execution["source_version"]):
                raise CampaignExecutionError("snapshot source_version must advance monotonically")
        return None

    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        document, cycle = _document_cycle(connection, identity)
        execution = _execution_row(connection, str(cycle["id"]))
        execution_id = str(execution["id"]) if execution is not None else str(uuid.uuid4())
        stamp = hybrid_state.now()
        if execution is None:
            connection.execute(
                "INSERT INTO campaign_execution VALUES (?, ?, ?, ?, 'running', ?, ?, ?, ?)",
                (execution_id, cycle["id"], snapshot["source_version"], snapshot_digest,
                 snapshot["execution_result"], revision, revision, stamp),
            )
        else:
            connection.execute(
                "UPDATE campaign_execution SET source_version=?, source_digest=?, state='running', result=?, updated_revision=?, updated_at=? WHERE id=?",
                (snapshot["source_version"], snapshot_digest, snapshot["execution_result"], revision, stamp, execution_id),
            )
            connection.execute("DELETE FROM campaign_assignment WHERE campaign_execution_id=?", (execution_id,))
            connection.execute("DELETE FROM campaign_operation WHERE campaign_execution_id=?", (execution_id,))
            connection.execute("DELETE FROM campaign_run WHERE campaign_execution_id=?", (execution_id,))
        connection.execute(
            "INSERT INTO campaign_execution_snapshot VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), execution_id, snapshot["source_version"], snapshot_digest,
             canonical_bytes(snapshot).decode(), revision, stamp),
        )
        for item in snapshot["runs"]:
            connection.execute(
                "INSERT INTO campaign_run VALUES (?, ?, ?, ?, ?)",
                (item["id"], execution_id, item["state"], item["result"], revision),
            )
        for item in snapshot["operations"]:
            connection.execute(
                "INSERT INTO campaign_operation VALUES (?, ?, ?, ?, ?, ?)",
                (item["id"], execution_id, item["run_id"], item["state"], item["result"], revision),
            )
        for item in snapshot["assignments"]:
            connection.execute(
                "INSERT INTO campaign_assignment VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)",
                (item["id"], execution_id, item["run_id"], item["operation_id"], item["state"],
                 int(item["runnable"]), item["stale_reason"], revision),
            )
        return {
            "campaign_id": document["visible_id"], "cycle_id": cycle["id"],
            "source_version": snapshot["source_version"], "source_digest": snapshot_digest,
            "counts": {key: len(snapshot[key]) for key in ("runs", "operations", "assignments")},
            "idempotent": False,
        }

    return document_store.managed_write(
        workspace, project_binding=project_binding, command="campaign-execution-record",
        actor=actor, callback=apply, existing=existing,
    )


def _classify(material: dict[str, Any]) -> tuple[dict[str, int], list[dict[str, str]], list[str]]:
    runs = {item["id"]: item for item in material["runs"]}
    operations = {item["id"]: item for item in material["operations"]}
    blockers: list[str] = []
    nonterminal_runs = [item["id"] for item in material["runs"] if item["state"] not in TERMINAL_RUN_STATES]
    nonterminal_operations = [item["id"] for item in material["operations"] if item["state"] not in TERMINAL_RUN_STATES]
    if nonterminal_runs:
        blockers.append("nonterminal runs: " + ", ".join(nonterminal_runs))
    if nonterminal_operations:
        blockers.append("nonterminal operations: " + ", ".join(nonterminal_operations))
    classifications: list[dict[str, str]] = []
    for item in material["assignments"]:
        if item["state"] not in ACTIVE_ASSIGNMENT_STATES:
            continue
        if bool(item["runnable"]):
            blockers.append(f"runnable assignment: {item['id']}")
            continue
        reason = item.get("stale_reason")
        has_owner = item.get("run_id") is not None or item.get("operation_id") is not None
        run_terminal = item.get("run_id") is None or runs.get(item["run_id"], {}).get("state") in TERMINAL_RUN_STATES
        operation_terminal = item.get("operation_id") is None or operations.get(item["operation_id"], {}).get("state") in TERMINAL_RUN_STATES
        reason_matches_owner = (
            reason == "orphaned-owner" and not has_owner
        ) or (
            reason == "expired-lease"
        ) or (
            reason in {"terminal-owner", "superseded-owner"} and has_owner
        )
        if reason not in STALE_REASONS or not reason_matches_owner or not run_terminal or not operation_terminal:
            blockers.append(f"unproven stale assignment: {item['id']}")
            continue
        classifications.append({"assignment_id": item["id"], "classification": str(reason)})
    counts = {
        "runs": len(material["runs"]),
        "nonterminal_runs": len(nonterminal_runs),
        "operations": len(material["operations"]),
        "nonterminal_operations": len(nonterminal_operations),
        "assignments": len(material["assignments"]),
        "pending_assignments": sum(item["state"] in ACTIVE_ASSIGNMENT_STATES for item in material["assignments"]),
        "runnable_assignments": sum(item["state"] in ACTIVE_ASSIGNMENT_STATES and bool(item["runnable"]) for item in material["assignments"]),
        "retirable_assignments": len(classifications),
    }
    return counts, classifications, blockers


def plan(
    workspace: Path, identity: str, *, disposition: str, reason: str, actor: str,
    authorization_ref: str, handoff_evidence: str | None = None,
    superseding_outcome_ref: str | None = None,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    if disposition not in TERMINAL_DISPOSITIONS:
        raise CampaignExecutionError("unsupported terminal disposition")
    if not reason.strip() or not actor.strip() or not authorization_ref.strip():
        raise CampaignExecutionError("reason, actor, and authorization reference are required")
    if disposition == "superseded" and not (superseding_outcome_ref or "").strip():
        raise CampaignExecutionError("superseded disposition requires a superseding outcome reference")
    with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)) as connection:
        _require_schema(connection)
        document, cycle = _document_cycle(connection, identity)
        material = _current_material(connection, document, cycle)
        execution = material["execution"]
        if execution is None:
            raise CampaignExecutionError("campaign has no authoritative execution snapshot")
        if cycle["lifecycle_state"] == "terminal" or execution["state"] == "terminal":
            prior = connection.execute(
                "SELECT * FROM campaign_reconciliation_audit WHERE cycle_id=? ORDER BY recorded_revision DESC LIMIT 1",
                (cycle["id"],),
            ).fetchone()
            if prior is None:
                raise CampaignExecutionError("campaign is terminal without terminal reconciliation audit")
            return {
                "schema_version": SCHEMA_VERSION, "kind": MANIFEST_KIND,
                "campaign_id": document["visible_id"], "cycle_id": cycle["id"],
                "applicable": False, "terminal_disposition": prior["terminal_disposition"],
                "reason": prior["reason"], "idempotent": True, "writes_performed": False,
            }
        counts, classifications, blockers = _classify(material)
        project = load_project_identity(workspace)
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "kind": MANIFEST_KIND,
            "project_id": project["project_id"],
            "campaign_id": document["visible_id"],
            "artifact_id": document["id"],
            "document_revision": int(document["current_revision"]),
            "cycle_id": cycle["id"],
            "execution_id": execution["id"],
            "execution_source_version": execution["source_version"],
            "execution_source_digest": execution["source_digest"],
            "execution_result": execution["result"],
            "prior_campaign_state": document["lifecycle_state"],
            "expected_state_token": state_token(workspace, identity, connection=connection),
            "counts": counts,
            "assignment_dispositions": classifications,
            "terminal_disposition": disposition,
            "reason": reason.strip(),
            "actor": actor.strip(),
            "authorization_ref": authorization_ref.strip(),
            "handoff_evidence": (handoff_evidence or "").strip() or None,
            "superseding_outcome_ref": (superseding_outcome_ref or "").strip() or None,
            "applicable": not blockers and counts["pending_assignments"] == counts["retirable_assignments"],
            "blockers": blockers,
            "manifest_digest": None,
        }
        manifest["manifest_digest"] = digest({**manifest, "manifest_digest": None})
        return manifest


def _validate_manifest(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or payload.get("kind") != MANIFEST_KIND:
        raise CampaignExecutionError("unsupported terminal reconciliation manifest")
    supplied = payload.get("manifest_digest")
    if not isinstance(supplied, str) or supplied != digest({**payload, "manifest_digest": None}):
        raise CampaignExecutionError("terminal reconciliation manifest digest mismatch")
    if payload.get("terminal_disposition") not in TERMINAL_DISPOSITIONS:
        raise CampaignExecutionError("terminal reconciliation disposition is unsupported")
    if not payload.get("applicable") or payload.get("blockers"):
        raise CampaignExecutionError("terminal reconciliation manifest is not applicable")
    return payload


def apply_manifest(workspace: Path, manifest_path: Path, *, project_binding: str) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    path = require_path_within(workspace, manifest_path if manifest_path.is_absolute() else workspace / manifest_path)
    manifest = _validate_manifest(json.loads(path.read_text(encoding="utf-8")))
    project = load_project_identity(workspace)
    if manifest.get("project_id") != project["project_id"]:
        raise CampaignExecutionError("terminal reconciliation manifest belongs to another project")

    def existing(connection: sqlite3.Connection) -> dict[str, Any] | None:
        _require_schema(connection)
        audit = connection.execute(
            "SELECT * FROM campaign_reconciliation_audit WHERE manifest_digest=?",
            (manifest["manifest_digest"],),
        ).fetchone()
        if audit is not None:
            return {
                "campaign_id": manifest["campaign_id"], "cycle_id": manifest["cycle_id"],
                "terminal_disposition": audit["terminal_disposition"], "idempotent": True,
            }
        document, cycle = _document_cycle(connection, str(manifest["campaign_id"]))
        if document["id"] != manifest["artifact_id"] or cycle["id"] != manifest["cycle_id"]:
            raise CampaignExecutionError("terminal reconciliation campaign identity changed")
        if state_token(workspace, str(manifest["campaign_id"]), connection=connection) != manifest["expected_state_token"]:
            raise CampaignExecutionError("terminal reconciliation state token is stale")
        material = _current_material(connection, document, cycle)
        execution = material["execution"]
        if execution is None or execution["id"] != manifest["execution_id"]:
            raise CampaignExecutionError("campaign execution identity changed")
        counts, classifications, blockers = _classify(material)
        if blockers or counts != manifest["counts"] or classifications != manifest["assignment_dispositions"]:
            raise CampaignExecutionError("campaign execution became runnable or changed after planning")
        return None

    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        document, cycle = _document_cycle(connection, str(manifest["campaign_id"]))
        execution = _execution_row(connection, str(cycle["id"]))
        if execution is None:
            raise CampaignExecutionError("campaign execution disappeared during reconciliation")
        material = _current_material(connection, document, cycle)
        counts, classifications, blockers = _classify(material)
        if (
            blockers
            or counts != manifest["counts"]
            or classifications != manifest["assignment_dispositions"]
            or int(document["current_revision"]) != int(manifest["document_revision"])
            or str(cycle["lifecycle_state"]) == "terminal"
        ):
            raise CampaignExecutionError("campaign execution changed while reconciliation was acquiring its transaction")
        stamp = hybrid_state.now()
        for item in manifest["assignment_dispositions"]:
            updated = connection.execute(
                "UPDATE campaign_assignment SET state='retired', runnable=0, terminal_disposition=?, "
                "retired_revision=?, updated_revision=? WHERE id=? AND campaign_execution_id=? "
                "AND state IN ('pending','leased') AND runnable=0 AND stale_reason=?",
                (manifest["terminal_disposition"], revision, revision, item["assignment_id"],
                 execution["id"], item["classification"]),
            ).rowcount
            if updated != 1:
                raise CampaignExecutionError(f"assignment changed during reconciliation: {item['assignment_id']}")
        connection.execute(
            "UPDATE campaign_execution SET state='terminal', updated_revision=?, updated_at=? WHERE id=? AND state='running'",
            (revision, stamp, execution["id"]),
        )
        disposition = str(manifest["terminal_disposition"])
        lifecycle = "superseded" if disposition == "superseded" else "terminal"
        body_status = "superseded" if disposition == "superseded" else (
            "not-satisfied" if disposition == "not-satisfied" else "reconciled-terminal"
        )
        body = document_store.replace_body_header(str(document["body_markdown"]), "Status", body_status)
        body_hash = document_store.sha256_text(body)
        document_revision = int(document["current_revision"]) + 1
        connection.execute(
            "INSERT INTO document_revision VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), document["id"], document_revision, document["title"], lifecycle,
             document["metadata_json"], body, body_hash, manifest["actor"], manifest["reason"], revision, stamp),
        )
        connection.execute(
            "UPDATE document SET lifecycle_state=?, current_revision=?, body_sha256=?, updated_at=? WHERE id=?",
            (lifecycle, document_revision, body_hash, stamp, document["id"]),
        )
        connection.execute(
            "UPDATE artifact SET lifecycle_state=?, content_sha256=?, updated_at=? WHERE id=?",
            (lifecycle, body_hash, stamp, document["id"]),
        )
        connection.execute("UPDATE cycle SET lifecycle_state='terminal', closed_at=? WHERE id=?", (stamp, cycle["id"]))
        verdict_id = str(uuid.uuid4())
        connection.execute(
            "INSERT INTO outcome_verdict VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (verdict_id, cycle["id"], document["visible_id"], disposition, manifest["reason"],
             manifest["authorization_ref"], revision, stamp),
        )
        product_truth = manifest.get("handoff_evidence") or manifest.get("superseding_outcome_ref") or f"campaign-execution:{execution['id']}"
        connection.execute(
            "INSERT INTO reconciliation VALUES (?, ?, ?, ?, ?, 'reconciled', ?, '[]')",
            (str(uuid.uuid4()), cycle["id"], revision, product_truth, verdict_id, stamp),
        )
        parent = connection.execute(
            "SELECT to_artifact_id FROM relationship WHERE from_artifact_id=? AND relation_type='outcome-parent' "
            "AND retired_revision IS NULL ORDER BY id",
            (document["id"],),
        ).fetchall()
        if len(parent) > 1:
            raise CampaignExecutionError("campaign has multiple active outcome parents")
        if parent and not connection.execute(
            "SELECT 1 FROM relationship WHERE from_artifact_id=? AND to_artifact_id=? "
            "AND relation_type='outcome-result-propagated' AND retired_revision IS NULL",
            (document["id"], parent[0]["to_artifact_id"]),
        ).fetchone():
            connection.execute(
                "INSERT INTO relationship VALUES (?, ?, 'outcome-result-propagated', ?, 'campaign-terminal-reconciliation', ?, NULL)",
                (str(uuid.uuid4()), document["id"], parent[0]["to_artifact_id"], revision),
            )
        connection.execute(
            "INSERT INTO campaign_reconciliation_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), execution["id"], cycle["id"], manifest["manifest_digest"],
             manifest["prior_campaign_state"], json.dumps(manifest["counts"], sort_keys=True, separators=(",", ":")),
             json.dumps(manifest["assignment_dispositions"], sort_keys=True, separators=(",", ":")),
             manifest["execution_result"], disposition, manifest["reason"], manifest["actor"],
             manifest["authorization_ref"], manifest.get("handoff_evidence"),
             manifest.get("superseding_outcome_ref"), revision, stamp),
        )
        return {
            "campaign_id": document["visible_id"], "cycle_id": cycle["id"],
            "document_revision": document_revision, "lifecycle": lifecycle,
            "execution_result": manifest["execution_result"], "terminal_disposition": disposition,
            "retired_assignments": len(manifest["assignment_dispositions"]), "idempotent": False,
        }

    return document_store.managed_write(
        workspace, project_binding=project_binding, command="campaign-terminal-reconcile",
        actor=str(manifest["actor"]), callback=apply, existing=existing,
    )


def status(workspace: Path, identity: str) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)) as connection:
        _require_schema(connection)
        document, cycle = _document_cycle(connection, identity)
        material = _current_material(connection, document, cycle)
        counts, classifications, blockers = _classify(material)
        audit = connection.execute(
            "SELECT execution_result, terminal_disposition, reason, actor, authorization_ref, handoff_evidence, "
            "superseding_outcome_ref, recorded_revision, recorded_at FROM campaign_reconciliation_audit "
            "WHERE cycle_id=? ORDER BY recorded_revision DESC, id DESC LIMIT 1",
            (cycle["id"],),
        ).fetchone()
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "tool-shed-campaign-execution-status",
            "campaign": material["document"], "cycle": material["cycle"],
            "execution": material["execution"], "counts": counts,
            "pending_assignment_classifications": classifications,
            "reconciliation_ready": material["execution"] is not None and not blockers
                and counts["pending_assignments"] == counts["retirable_assignments"]
                and material["cycle"]["lifecycle"] != "terminal",
            "blockers": blockers,
            "terminal_reconciliation": dict(audit) if audit is not None else None,
            "state_token": state_token(workspace, identity, connection=connection),
            "writes_performed": False,
        }


def migrate(workspace: Path, *, project_binding: str) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    require_project_binding(workspace, project_binding, operation="hybrid-state")
    source = hybrid_state.database_path(workspace)
    shadow = source.with_name(source.name + ".campaign-execution.next")
    if shadow.exists():
        raise CampaignExecutionError(f"stale migration shadow requires review: {shadow.relative_to(workspace)}")
    with contextlib.closing(hybrid_state.connect(source, writable=False)) as probe:
        entrance = document_store.audit_connection(workspace, probe)
        if entrance["classification"] not in {"CLEAN", "VALID_DIRTY"}:
            raise CampaignExecutionError(f"migration refused from {entrance['classification']}")
        if int(probe.execute("PRAGMA user_version").fetchone()[0]) != 5:
            raise CampaignExecutionError("campaign execution migration requires Hybrid schema 5")
        expected_revision = int(entrance["current_revision"])
        expected_digest = str(entrance["domain_digest"])
    backup_root = workspace / ".tool-shed/backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = backup_root / f"campaign-execution-schema5-r{expected_revision}.sqlite3"
    if backup.exists():
        raise CampaignExecutionError(f"migration backup already exists and requires review: {backup.relative_to(workspace)}")
    with hybrid_state.WorkspaceLock(hybrid_state.lock_path(workspace)):
        with contextlib.closing(hybrid_state.connect(source)) as live:
            current = document_store.audit_connection(workspace, live)
            if current["current_revision"] != expected_revision or current["domain_digest"] != expected_digest:
                raise CampaignExecutionError("campaign execution migration source state changed")
            with contextlib.closing(sqlite3.connect(backup)) as target:
                live.backup(target)
            with contextlib.closing(sqlite3.connect(shadow)) as target:
                live.backup(target)
        try:
            with contextlib.closing(hybrid_state.connect(shadow)) as target:
                target.execute("BEGIN IMMEDIATE")
                revision = expected_revision + 1
                operation_id = str(uuid.uuid4())
                stamp = hybrid_state.now()
                target.execute(
                    "INSERT INTO managed_operation VALUES (?, ?, 'campaign-execution-schema6-migrate', 'campaign-execution', ?, NULL, NULL, 0, 'active')",
                    (operation_id, revision, stamp),
                )
                target.execute("INSERT INTO active_operation VALUES (1, ?, ?)", (operation_id, revision))
                create_campaign_execution_schema(target, include_triggers=True)
                target.execute("INSERT INTO campaign_execution_meta VALUES (1, ?, ?)", (CAMPAIGN_EXECUTION_SCHEMA_VERSION, stamp))
                target.execute("UPDATE state_meta SET schema_version=6 WHERE id=1")
                target.execute("PRAGMA user_version=6")
                target.execute(
                    "INSERT INTO migration_ledger VALUES (?, 5, 6, ?, ?, ?, 'complete', ?, ?)",
                    (str(uuid.uuid4()), migration_digest(), expected_digest, backup.relative_to(workspace).as_posix(), stamp, stamp),
                )
                target.execute("DELETE FROM active_operation WHERE id=1")
                target.execute("UPDATE managed_operation SET status='complete', committed_at=? WHERE id=?", (stamp, operation_id))
                source_digest = document_store.domain_digest(target)
                target.execute(
                    "UPDATE state_meta SET current_revision=?, last_verified_revision=?, source_digest=?, "
                    "schema_trigger_digest=?, dirty=1, checkpoint_pending=1 WHERE id=1",
                    (revision, revision, source_digest, hybrid_state.schema_digest(target)),
                )
                target.commit()
                checked = document_store.audit_connection(workspace, target)
                if checked["classification"] != "VALID_DIRTY":
                    raise CampaignExecutionError(
                        f"campaign execution migration shadow failed audit: {checked['classification']}: "
                        + "; ".join(checked["findings"])
                    )
                target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            os.replace(shadow, source)
        except BaseException:
            shadow.unlink(missing_ok=True)
            raise
    return {
        "schema_version": SCHEMA_VERSION, "kind": "tool-shed-campaign-execution-migration",
        "from_schema": 5, "to_schema": 6, "backup": backup.relative_to(workspace).as_posix(),
        "backup_sha256": hybrid_state.file_sha256(backup), "revision": expected_revision + 1,
        "writes_performed": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    migrate_parser = commands.add_parser("migrate")
    migrate_parser.add_argument("--project-binding", required=True)
    status_parser = commands.add_parser("status")
    status_parser.add_argument("campaign")
    record_parser = commands.add_parser("record-snapshot")
    record_parser.add_argument("campaign")
    record_parser.add_argument("--snapshot", required=True)
    record_parser.add_argument("--project-binding", required=True)
    record_parser.add_argument("--expect", required=True)
    record_parser.add_argument("--actor", required=True)
    plan_parser = commands.add_parser("plan")
    plan_parser.add_argument("campaign")
    plan_parser.add_argument("--disposition", choices=sorted(TERMINAL_DISPOSITIONS), required=True)
    plan_parser.add_argument("--reason", required=True)
    plan_parser.add_argument("--actor", required=True)
    plan_parser.add_argument("--authorization", required=True)
    plan_parser.add_argument("--handoff-evidence")
    plan_parser.add_argument("--superseding-outcome")
    apply_parser = commands.add_parser("apply")
    apply_parser.add_argument("--manifest", required=True)
    apply_parser.add_argument("--project-binding", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    workspace = Path(args.workspace)
    try:
        if args.command == "migrate":
            result = migrate(workspace, project_binding=args.project_binding)
        elif args.command == "status":
            result = status(workspace, args.campaign)
        elif args.command == "record-snapshot":
            result = record_snapshot(
                workspace, args.campaign, Path(args.snapshot), project_binding=args.project_binding,
                expected_token=args.expect, actor=args.actor,
            )
        elif args.command == "plan":
            result = plan(
                workspace, args.campaign, disposition=args.disposition, reason=args.reason,
                actor=args.actor, authorization_ref=args.authorization,
                handoff_evidence=args.handoff_evidence,
                superseding_outcome_ref=args.superseding_outcome,
            )
        else:
            result = apply_manifest(workspace, Path(args.manifest), project_binding=args.project_binding)
    except (CampaignExecutionError, document_store.DocumentStoreError, hybrid_state.HybridStateError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Campaign execution operation failed: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
