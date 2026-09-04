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
from datetime import datetime, timedelta, timezone
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
from project_identity import (
    bind_state_token,
    load_project_identity,
    require_path_within,
    require_project_binding,
    resolved_workspace,
)


SCHEMA_VERSION = 1
DISCOVERY_VERSION = "loop-findings-v2"
ZERO_DIGEST = "0" * 64
MAX_ACTIVE_REPORT = 50
MAX_RECENT_RESOLVED_REPORT = 50
STALL_AFTER = timedelta(days=30)
HISTORY_REVIEW_KIND = "tool-shed-loop-history-review-manifest"
HISTORY_REVIEW_DECISIONS = {
    "apply-expected-state",
    "retain-open",
    "requires-evidence",
}
MAX_HISTORY_SELECTION = 50


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


def _candidate(
    *, category: str, reason_code: str, artifact_id: str, visible_id: str,
    observed: str, expected: str,
) -> dict[str, Any]:
    key = _digest({
        "category": category,
        "reason_code": reason_code,
        "subject_artifact_id": artifact_id,
        "expected_state": expected,
    })
    finding_id = f"LOOP-{key[:12].upper()}"
    return {
        "finding_key": key,
        "visible_id": finding_id,
        "category": category,
        "severity": "attention",
        "reason_code": reason_code,
        "subject_artifact_id": artifact_id,
        "subject_visible_id": visible_id,
        "observed_state": observed,
        "expected_state": expected,
        "command": f"ts: resolve loop {finding_id}",
    }


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _discover_current_cycle_findings(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    cutoff = datetime.now(timezone.utc) - STALL_AFTER
    rows = connection.execute(
        "SELECT c.id AS cycle_id, c.lifecycle_state, c.opened_at, c.origin_artifact_id, "
        "COALESCE(d.visible_id, a.display_number, a.current_path) AS visible_id, a.updated_at, "
        "(SELECT r.state FROM reconciliation r WHERE r.cycle_id=c.id "
        " ORDER BY r.origin_revision DESC, r.id DESC LIMIT 1) AS reconciliation_state, "
        "(SELECT ov.disposition FROM reconciliation r JOIN outcome_verdict ov ON ov.id=r.verdict_id "
        " WHERE r.cycle_id=c.id ORDER BY r.origin_revision DESC, r.id DESC LIMIT 1) AS disposition, "
        "MAX(c.opened_at, a.updated_at, "
        "COALESCE((SELECT MAX(ov.decided_at) FROM outcome_verdict ov WHERE ov.cycle_id=c.id), ''), "
        "COALESCE((SELECT MAX(r.compared_at) FROM reconciliation r WHERE r.cycle_id=c.id), ''), "
        "COALESCE((SELECT MAX(er.collected_at) FROM evidence_reference er WHERE er.cycle_id=c.id), '')) AS latest_activity "
        "FROM cycle c JOIN artifact a ON a.id=c.origin_artifact_id "
        "LEFT JOIN document d ON d.id=a.id ORDER BY c.opened_at, c.id"
    ).fetchall()
    for row in rows:
        artifact_id, visible_id = str(row["origin_artifact_id"]), str(row["visible_id"])
        lifecycle = str(row["lifecycle_state"])
        reconciliation = str(row["reconciliation_state"] or "open")
        disposition = str(row["disposition"] or "open")
        if lifecycle == "blocked":
            findings.append(_candidate(
                category="outcome-health", reason_code="OUTCOME_BLOCKED",
                artifact_id=artifact_id, visible_id=visible_id,
                observed="blocked", expected="working-or-terminal",
            ))
        elif lifecycle not in {"terminal", "completed", "abandoned", "superseded"}:
            latest = _parse_time(row["latest_activity"])
            if latest is not None and latest < cutoff:
                findings.append(_candidate(
                    category="outcome-health", reason_code="OUTCOME_STALLED",
                    artifact_id=artifact_id, visible_id=visible_id,
                    observed="stalled-30-days", expected="recent-progress-or-terminal",
                ))
        if lifecycle in {"terminal", "completed", "abandoned", "superseded"} and reconciliation != "reconciled":
            findings.append(_candidate(
                category="outcome-reconciliation", reason_code="TERMINAL_OUTCOME_UNRECONCILED",
                artifact_id=artifact_id, visible_id=visible_id,
                observed=reconciliation, expected="reconciled",
            ))
        if reconciliation == "reconciled" and disposition == "open":
            findings.append(_candidate(
                category="outcome-reconciliation", reason_code="INVALID_RECONCILED_DISPOSITION",
                artifact_id=artifact_id, visible_id=visible_id,
                observed="reconciled-open", expected="terminal-disposition",
            ))
        if lifecycle in {"terminal", "completed", "abandoned", "superseded"} and reconciliation == "reconciled":
            missing = connection.execute(
                "SELECT 1 FROM relationship p WHERE p.from_artifact_id=? "
                "AND p.relation_type='outcome-parent' AND p.retired_revision IS NULL "
                "AND NOT EXISTS (SELECT 1 FROM relationship x WHERE x.from_artifact_id=p.from_artifact_id "
                "AND x.to_artifact_id=p.to_artifact_id AND x.relation_type='outcome-result-propagated' "
                "AND x.retired_revision IS NULL) LIMIT 1",
                (artifact_id,),
            ).fetchone()
            if missing:
                findings.append(_candidate(
                    category="outcome-propagation", reason_code="OUTCOME_RESULT_UNPROPAGATED",
                    artifact_id=artifact_id, visible_id=visible_id,
                    observed="terminal-not-propagated", expected="outcome-result-propagated",
                ))
    return findings


def _discover_closure_findings(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    rows = connection.execute(
        "SELECT ce.artifact_id, COALESCE(d.visible_id, a.display_number, a.current_path) AS visible_id, "
        "cr.graph_health, cr.evidence_health FROM closure_rollup cr "
        "JOIN closure_element ce ON ce.id=cr.element_id AND ce.role='cycle' "
        "JOIN artifact a ON a.id=ce.artifact_id LEFT JOIN document d ON d.id=a.id "
        "ORDER BY visible_id"
    ).fetchall()
    for row in rows:
        artifact_id, visible_id = str(row["artifact_id"]), str(row["visible_id"])
        graph = str(row["graph_health"])
        evidence = str(row["evidence_health"])
        if graph != "valid":
            findings.append(_candidate(
                category="lineage-health",
                reason_code="LINEAGE_INVALID" if graph == "invalid" else "LINEAGE_RECOVERY_REQUIRED",
                artifact_id=artifact_id, visible_id=visible_id,
                observed=graph, expected="valid",
            ))
        if evidence in {"missing", "stale", "checker-error"}:
            reason = {
                "missing": "CLOSURE_EVIDENCE_MISSING",
                "stale": "CLOSURE_EVIDENCE_STALE",
                "checker-error": "CLOSURE_EVIDENCE_CHECKER_ERROR",
            }[evidence]
            findings.append(_candidate(
                category="evidence-health", reason_code=reason,
                artifact_id=artifact_id, visible_id=visible_id,
                observed=evidence, expected="current",
            ))
    return findings


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
        candidates.append(_candidate(
            category="semantic-lifecycle-drift",
            reason_code="PROMOTED_IDEA_LIFECYCLE_STALE",
            artifact_id=str(row["id"]), visible_id=str(row["visible_id"]),
            observed="active", expected=expected,
        ))
    if int(connection.execute("PRAGMA user_version").fetchone()[0]) >= 5:
        candidates.extend(_discover_current_cycle_findings(connection))
        candidates.extend(_discover_closure_findings(connection))
    return candidates


def candidate_digest(candidates: list[dict[str, Any]]) -> str:
    return _digest(sorted(candidates, key=lambda item: item["finding_key"]))


def synchronize_findings(connection: sqlite3.Connection, *, revision: int) -> dict[str, Any]:
    """Refresh persisted findings inside the caller's managed transaction."""
    hybrid_schema = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if hybrid_schema not in {4, 5}:
        return {"applicable": False, "active_count": 0, "resolved_count": 0, "recurrence_count": 0}
    if not set(LOOP_FINDING_TABLES) <= _tables(connection):
        raise LoopFindingError(f"schema {hybrid_schema} is missing loop-finding authority tables")
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
        ("loop-findings-v1" if hybrid_schema == 4 else DISCOVERY_VERSION, revision, digest, stamp),
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
        if version not in {4, 5} or not set(LOOP_FINDING_TABLES) <= _tables(connection):
            raise LoopFindingError(f"loop findings require Hybrid schema 4 or 5; found {version}")
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
        "discovery_version": "loop-findings-v1" if version == 4 else DISCOVERY_VERSION,
        "database_revision": current_revision,
        "fresh": fresh,
        "active_count": sum(item["state"] == "active" for item in findings),
        "resolved_count": sum(item["state"] == "resolved" for item in findings),
        "findings": findings,
        "writes_performed": False,
    }


def history_audit(
    workspace: Path,
    *,
    sources: Sequence[str] = (),
    database: Path | None = None,
) -> dict[str, Any]:
    """Return bounded active and resolved history for explicit local sources."""
    result = audit(workspace, database=database)
    normalized = [item.strip().casefold() for item in sources if item.strip()]
    if len(normalized) > MAX_HISTORY_SELECTION:
        raise LoopFindingError(
            f"history audit accepts at most {MAX_HISTORY_SELECTION} source selectors"
        )
    findings = result["findings"]
    if normalized:
        findings = [
            item for item in findings
            if any(
                selector in {
                    str(item["finding_id"]).casefold(),
                    str(item["subject_id"]).casefold(),
                    str(item["category"]).casefold(),
                    str(item["reason_code"]).casefold(),
                    str(item["state"]).casefold(),
                }
                for selector in normalized
            )
        ]
    return {
        **result,
        "kind": "tool-shed-loop-finding-history-audit",
        "selection": list(sources),
        "selected_count": len(findings),
        "findings": findings,
    }


def _history_cluster_ids(
    connection: sqlite3.Connection, subject_artifact_ids: set[str]
) -> set[str]:
    pending = list(subject_artifact_ids)
    connected = set(subject_artifact_ids)
    while pending:
        artifact_id = pending.pop(0)
        rows = connection.execute(
            "SELECT from_artifact_id, to_artifact_id FROM relationship "
            "WHERE relation_type='outcome-parent' AND retired_revision IS NULL "
            "AND (from_artifact_id=? OR to_artifact_id=?)",
            (artifact_id, artifact_id),
        ).fetchall()
        for row in rows:
            for candidate in (str(row["from_artifact_id"]), str(row["to_artifact_id"])):
                if candidate not in connected:
                    connected.add(candidate)
                    pending.append(candidate)
    rows = connection.execute(
        "SELECT visible_id FROM loop_finding WHERE state='active' AND subject_artifact_id IN ("
        + ",".join("?" for _ in connected)
        + ") ORDER BY visible_id",
        sorted(connected),
    ).fetchall()
    return {str(row["visible_id"]) for row in rows}


def _review_token(workspace: Path, payload: dict[str, Any]) -> str:
    material = dict(payload)
    material.pop("manifest_token", None)
    material.pop("manifest_digest", None)
    return bind_state_token(workspace, "loop-history-review", _digest(material))


def history_review_plan(
    workspace: Path,
    *,
    decisions: Sequence[str],
    rationale: str,
    complete_cluster: bool,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    if not rationale.strip() or len(rationale.strip()) > 2048:
        raise LoopFindingError("history review requires a bounded rationale")
    parsed: dict[str, str] = {}
    for supplied in decisions:
        finding_id, separator, decision = supplied.partition("=")
        finding_id, decision = finding_id.strip().upper(), decision.strip()
        if not separator or not finding_id or decision not in HISTORY_REVIEW_DECISIONS:
            raise LoopFindingError(
                "history decisions must use LOOP-id=apply-expected-state|retain-open|requires-evidence"
            )
        if finding_id in parsed:
            raise LoopFindingError(f"duplicate history decision: {finding_id}")
        parsed[finding_id] = decision
    if not parsed or len(parsed) > MAX_HISTORY_SELECTION:
        raise LoopFindingError(
            f"history review requires 1 to {MAX_HISTORY_SELECTION} decisions"
        )
    audit_result = audit(workspace)
    if not audit_result["fresh"]:
        raise LoopFindingError("loop discovery is stale; perform a managed refresh before review")
    identity = load_project_identity(workspace)
    with contextlib.closing(
        hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)
    ) as connection:
        placeholders = ",".join("?" for _ in parsed)
        rows = list(
            connection.execute(
                f"SELECT * FROM loop_finding WHERE upper(visible_id) IN ({placeholders}) "
                "ORDER BY visible_id",
                sorted(parsed),
            )
        )
        found = {str(row["visible_id"]).upper() for row in rows}
        missing = sorted(set(parsed) - found)
        if missing:
            raise LoopFindingError("history findings were not found: " + ", ".join(missing))
        if any(str(row["state"]) != "active" for row in rows):
            raise LoopFindingError("history review accepts only currently active findings")
        if complete_cluster:
            required = _history_cluster_ids(
                connection, {str(row["subject_artifact_id"]) for row in rows}
            )
            omitted = sorted(required - set(parsed))
            if omitted:
                raise LoopFindingError(
                    "complete cluster review omitted active findings: " + ", ".join(omitted)
                )
        items: list[dict[str, Any]] = []
        for row in rows:
            public = _public_row(row)
            decision = parsed[str(row["visible_id"]).upper()]
            document_revision = None
            if decision == "apply-expected-state":
                if str(row["reason_code"]) != "PROMOTED_IDEA_LIFECYCLE_STALE":
                    raise LoopFindingError(
                        f"{row['visible_id']} does not support apply-expected-state"
                    )
                document = connection.execute(
                    "SELECT current_revision FROM document WHERE id=?",
                    (row["subject_artifact_id"],),
                ).fetchone()
                if document is None:
                    raise LoopFindingError(f"{row['visible_id']} subject is not a managed document")
                document_revision = int(document["current_revision"])
            items.append(
                {
                    "finding": public,
                    "subject_artifact_id": str(row["subject_artifact_id"]),
                    "document_revision": document_revision,
                    "decision": decision,
                }
            )
    payload: dict[str, Any] = {
        "schema_version": 1,
        "kind": HISTORY_REVIEW_KIND,
        "project_id": identity["project_id"],
        "database_revision": audit_result["database_revision"],
        "domain_digest": document_store.audit(workspace)["domain_digest"],
        "discovery_version": audit_result["discovery_version"],
        "selection_mode": "complete-lineage-cluster" if complete_cluster else "per-finding",
        "rationale": rationale.strip(),
        "decisions": items,
        "writes_performed": False,
    }
    material = dict(payload)
    material.pop("writes_performed")
    payload["manifest_digest"] = _digest(material)
    payload["manifest_token"] = _review_token(workspace, payload)
    return payload


def load_history_review_manifest(workspace: Path, supplied: Path) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    path = require_path_within(
        workspace, supplied if supplied.is_absolute() else workspace / supplied
    )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LoopFindingError(f"cannot load history review manifest: {error}") from error
    if not isinstance(payload, dict):
        raise LoopFindingError("history review manifest must be a JSON object")
    return payload


def validate_history_review(workspace: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    identity = load_project_identity(workspace)
    if (
        manifest.get("schema_version") != 1
        or manifest.get("kind") != HISTORY_REVIEW_KIND
        or manifest.get("project_id") != identity["project_id"]
    ):
        raise LoopFindingError("history review manifest does not match this project or schema")
    decisions = manifest.get("decisions")
    if not isinstance(decisions, list) or not 1 <= len(decisions) <= MAX_HISTORY_SELECTION:
        raise LoopFindingError("history review manifest has an invalid decision set")
    material = dict(manifest)
    supplied_token = str(material.pop("manifest_token", ""))
    supplied_digest = str(material.pop("manifest_digest", ""))
    material.pop("writes_performed", None)
    expected_digest = _digest(material)
    if supplied_digest != expected_digest:
        raise LoopFindingError("history review manifest digest does not match its content")
    if supplied_token != _review_token(workspace, manifest):
        raise LoopFindingError("history review manifest token does not match its content")
    current = document_store.audit(workspace)
    audit_result = audit(workspace)
    if (
        int(manifest.get("database_revision", -1)) != current["current_revision"]
        or manifest.get("domain_digest") != current["domain_digest"]
        or not audit_result["fresh"]
    ):
        raise LoopFindingError("history review manifest is stale")
    current_by_id = {
        str(item["finding_id"]): item for item in audit_result["findings"]
    }
    seen: set[str] = set()
    subject_ids: set[str] = set()
    with contextlib.closing(
        hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)
    ) as connection:
        for item in decisions:
            if not isinstance(item, dict) or not isinstance(item.get("finding"), dict):
                raise LoopFindingError("history review decision is malformed")
            finding = item["finding"]
            finding_id = str(finding.get("finding_id") or "")
            if finding_id in seen or item.get("decision") not in HISTORY_REVIEW_DECISIONS:
                raise LoopFindingError("history review decisions must be unique and controlled")
            seen.add(finding_id)
            current_finding = current_by_id.get(finding_id)
            if current_finding != finding or current_finding.get("state") != "active":
                raise LoopFindingError(f"history finding changed before review: {finding_id}")
            row = connection.execute(
                "SELECT subject_artifact_id FROM loop_finding WHERE visible_id=?",
                (finding_id,),
            ).fetchone()
            if row is None or str(row["subject_artifact_id"]) != item.get("subject_artifact_id"):
                raise LoopFindingError(f"history finding subject changed: {finding_id}")
            subject_ids.add(str(row["subject_artifact_id"]))
            if item["decision"] == "apply-expected-state":
                document = connection.execute(
                    "SELECT current_revision FROM document WHERE id=?",
                    (row["subject_artifact_id"],),
                ).fetchone()
                if document is None or int(document["current_revision"]) != item.get("document_revision"):
                    raise LoopFindingError(f"history document revision changed: {finding_id}")
        if manifest.get("selection_mode") == "complete-lineage-cluster":
            required = _history_cluster_ids(connection, subject_ids)
            if required != seen:
                raise LoopFindingError("history lineage cluster changed before review")
        elif manifest.get("selection_mode") != "per-finding":
            raise LoopFindingError("history review selection mode is invalid")
    return {
        "schema_version": 1,
        "kind": "tool-shed-loop-history-review-validation",
        "manifest_digest": supplied_digest,
        "manifest_token": supplied_token,
        "decision_count": len(decisions),
        "applicable": True,
        "writes_performed": False,
    }


def _subject_cycle_id(connection: sqlite3.Connection, artifact_id: str) -> str:
    row = connection.execute(
        "SELECT id FROM cycle WHERE origin_artifact_id=? ORDER BY opened_at DESC, id DESC LIMIT 1",
        (artifact_id,),
    ).fetchone()
    if row is None:
        row = connection.execute(
            "SELECT c.id FROM relationship rel JOIN cycle c ON c.origin_artifact_id=rel.from_artifact_id "
            "WHERE rel.to_artifact_id=? AND rel.relation_type='historical-overlay-for' "
            "AND rel.retired_revision IS NULL ORDER BY c.opened_at DESC, c.id DESC LIMIT 1",
            (artifact_id,),
        ).fetchone()
    if row is None:
        raise LoopFindingError("history finding subject has no outcome cycle")
    return str(row["id"])


def apply_history_review(
    workspace: Path,
    *,
    manifest: dict[str, Any],
    expected_token: str,
    project_binding: str,
    authorization: str,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    validated = validate_history_review(workspace, manifest)
    if expected_token != validated["manifest_token"]:
        raise LoopFindingError("history review token is stale or does not match")
    require_project_binding(workspace, project_binding, operation="hybrid-state")
    if not authorization.strip() or len(authorization.strip()) > 2048:
        raise LoopFindingError("history review apply requires bounded authorization evidence")

    def write(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        if hybrid_state.meta_row(connection)["current_revision"] != manifest["database_revision"]:
            raise LoopFindingError("history review revision changed before apply")
        stamp = hybrid_state.now()
        applied: list[str] = []
        retained: list[str] = []
        project_id = load_project_identity(workspace)["project_id"]
        for item in manifest["decisions"]:
            finding = item["finding"]
            finding_id = str(finding["finding_id"])
            cycle_id = _subject_cycle_id(connection, str(item["subject_artifact_id"]))
            evidence_id = hybrid_state.stable_uuid(
                project_id, f"loop-history-review:{manifest['manifest_digest']}:{finding_id}"
            )
            connection.execute(
                "INSERT INTO evidence_reference VALUES (?, ?, 'loop-history-review', ?, NULL, ?, ?)",
                (
                    evidence_id,
                    cycle_id,
                    f"loop-history-review:{manifest['manifest_digest']}",
                    item["decision"],
                    stamp,
                ),
            )
            if item["decision"] != "apply-expected-state":
                retained.append(finding_id)
                continue
            artifact_id = str(item["subject_artifact_id"])
            current = connection.execute(
                "SELECT d.*, r.body_markdown FROM document d JOIN document_revision r "
                "ON r.document_id=d.id AND r.revision_number=d.current_revision WHERE d.id=?",
                (artifact_id,),
            ).fetchone()
            if current is None or int(current["current_revision"]) != item["document_revision"]:
                raise LoopFindingError(f"history document changed before apply: {finding_id}")
            lifecycle = str(finding["expected_state"])
            if lifecycle not in document_store.LIFECYCLES:
                raise LoopFindingError(f"history expected lifecycle is unsupported: {lifecycle}")
            document_revision = int(current["current_revision"]) + 1
            connection.execute(
                "INSERT INTO document_revision VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()), artifact_id, document_revision, current["title"], lifecycle,
                    current["metadata_json"], current["body_markdown"], current["body_sha256"],
                    "loop-history-review", authorization.strip(), revision, stamp,
                ),
            )
            connection.execute(
                "UPDATE document SET lifecycle_state=?, current_revision=?, updated_at=? WHERE id=?",
                (lifecycle, document_revision, stamp, artifact_id),
            )
            connection.execute(
                "UPDATE artifact SET lifecycle_state=?, updated_at=? WHERE id=?",
                (lifecycle, stamp, artifact_id),
            )
            applied.append(finding_id)
        return {
            "manifest_digest": manifest["manifest_digest"],
            "applied": applied,
            "retained": retained,
            "authorization": authorization.strip(),
        }

    result = hybrid_state.managed_write(
        workspace,
        project_binding=project_binding,
        command="apply-loop-history-review",
        actor="loop-history-review",
        callback=write,
    )
    result["audit"] = audit(workspace)
    return result


def report_projection(workspace: Path) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    path = hybrid_state.database_path(workspace)
    if not path.is_file():
        return {"total_active_count": 0, "total_resolved_count": 0, "truncated": False, "findings": []}
    with contextlib.closing(hybrid_state.connect(path, writable=False)) as connection:
        if int(connection.execute("PRAGMA user_version").fetchone()[0]) < 4:
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
        action = {
            "PROMOTED_IDEA_LIFECYCLE_STALE": "correct-document-lifecycle",
            "OUTCOME_BLOCKED": "inspect-blocker-and-continue-or-dispose",
            "OUTCOME_STALLED": "confirm-owner-and-continue-or-dispose",
            "TERMINAL_OUTCOME_UNRECONCILED": "reconcile-terminal-outcome",
            "INVALID_RECONCILED_DISPOSITION": "correct-outcome-disposition",
            "OUTCOME_RESULT_UNPROPAGATED": "propagate-outcome-result",
            "LINEAGE_INVALID": "repair-or-disposition-invalid-lineage",
            "LINEAGE_RECOVERY_REQUIRED": "recover-lineage-authority",
            "CLOSURE_EVIDENCE_MISSING": "collect-required-closure-evidence",
            "CLOSURE_EVIDENCE_STALE": "refresh-required-closure-evidence",
            "CLOSURE_EVIDENCE_CHECKER_ERROR": "repair-checker-and-rerun-evidence",
        }[selected["reason_code"]]
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
    shadow = source.with_name(source.name + ".loop-schema.next")
    if shadow.exists():
        raise LoopFindingError(f"stale migration shadow requires review: {shadow.relative_to(workspace)}")
    with contextlib.closing(hybrid_state.connect(source, writable=False)) as probe:
        entrance = document_store.audit_connection(workspace, probe)
        if entrance["classification"] not in {"CLEAN", "VALID_DIRTY"}:
            raise LoopFindingError(f"migration refused from {entrance['classification']}")
        from_schema = int(probe.execute("PRAGMA user_version").fetchone()[0])
        if from_schema not in {3, 4}:
            raise LoopFindingError("loop-finding migration requires Hybrid schema 3 or 4")
        expected_revision = int(entrance["current_revision"])
        expected_digest = str(entrance["domain_digest"])
    backup_root = workspace / ".tool-shed/backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    to_schema = from_schema + 1
    backup = backup_root / f"loop-findings-schema{from_schema}-r{expected_revision}.sqlite3"
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
                revision = expected_revision + 1
                operation_id = str(uuid.uuid4())
                stamp = hybrid_state.now()
                target.execute(
                    "INSERT INTO managed_operation VALUES (?, ?, ?, 'loop-findings', ?, NULL, NULL, 0, 'active')",
                    (operation_id, revision, f"loop-findings-schema{to_schema}-migrate", stamp),
                )
                target.execute("INSERT INTO active_operation VALUES (1, ?, ?)", (operation_id, revision))
                if from_schema == 3:
                    create_loop_finding_schema(target, include_triggers=True, schema_version=1)
                    target.execute("UPDATE state_meta SET schema_version=4 WHERE id=1")
                    target.execute("PRAGMA user_version=4")
                    target.execute(
                        "INSERT INTO loop_finding_meta VALUES (1, 1, 'loop-findings-v1', 0, ?, ?)",
                        (ZERO_DIGEST, stamp),
                    )
                else:
                    for table in LOOP_FINDING_TABLES:
                        for operation in ("insert", "update", "delete"):
                            target.execute(f"DROP TRIGGER ts_account_{table}_{operation}")
                    target.execute("DROP INDEX loop_finding_state_idx")
                    target.execute("DROP INDEX loop_finding_subject_idx")
                    target.execute("ALTER TABLE loop_finding_meta RENAME TO loop_finding_meta_v1")
                    target.execute("ALTER TABLE loop_finding RENAME TO loop_finding_v1")
                    create_loop_finding_schema(target, include_triggers=True, schema_version=2)
                    target.execute(
                        "INSERT INTO loop_finding_meta SELECT id, 2, ?, last_source_revision, "
                        "last_source_digest, updated_at FROM loop_finding_meta_v1",
                        (DISCOVERY_VERSION,),
                    )
                    target.execute("INSERT INTO loop_finding SELECT * FROM loop_finding_v1")
                    target.execute("DROP TABLE loop_finding_v1")
                    target.execute("DROP TABLE loop_finding_meta_v1")
                    target.execute("UPDATE state_meta SET schema_version=5 WHERE id=1")
                    target.execute("PRAGMA user_version=5")
                synchronize_findings(target, revision=revision)
                target.execute(
                    "INSERT INTO migration_ledger VALUES (?, ?, ?, ?, ?, ?, 'complete', ?, ?)",
                    (
                        str(uuid.uuid4()),
                        from_schema,
                        to_schema,
                        loop_finding_migration_digest(schema_version=1 if to_schema == 4 else 2),
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
        "from_schema": from_schema,
        "to_schema": to_schema,
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
    audit_parser = commands.add_parser("audit")
    audit_parser.add_argument("--history", action="store_true")
    audit_parser.add_argument("--source", action="append", default=[])
    resolve_parser = commands.add_parser("resolve")
    resolve_parser.add_argument("finding_id")
    plan_parser = commands.add_parser("history-plan")
    plan_parser.add_argument("--decision", action="append", required=True)
    plan_parser.add_argument("--rationale", required=True)
    plan_parser.add_argument("--complete-cluster", action="store_true")
    validate_parser = commands.add_parser("history-validate")
    validate_parser.add_argument("--manifest", required=True)
    apply_parser = commands.add_parser("history-apply")
    apply_parser.add_argument("--manifest", required=True)
    apply_parser.add_argument("--expect", required=True)
    apply_parser.add_argument("--project-binding", required=True)
    apply_parser.add_argument("--authorization", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        workspace = Path(args.workspace)
        if args.command == "migrate":
            result = migrate(workspace, project_binding=args.project_binding)
        elif args.command == "audit":
            result = (
                history_audit(workspace, sources=args.source)
                if args.history or args.source
                else audit(workspace)
            )
        elif args.command == "resolve":
            result = resolve(workspace, args.finding_id)
        elif args.command == "history-plan":
            result = history_review_plan(
                workspace,
                decisions=args.decision,
                rationale=args.rationale,
                complete_cluster=args.complete_cluster,
            )
        elif args.command == "history-validate":
            result = validate_history_review(
                workspace, load_history_review_manifest(workspace, Path(args.manifest))
            )
        else:
            result = apply_history_review(
                workspace,
                manifest=load_history_review_manifest(workspace, Path(args.manifest)),
                expected_token=args.expect,
                project_binding=args.project_binding,
                authorization=args.authorization,
            )
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
