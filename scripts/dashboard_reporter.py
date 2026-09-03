#!/usr/bin/env python3
"""Enroll and run the privacy-bounded local Tool Shed dashboard reporter."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import contextlib
import hashlib
import html
import json
import os
import platform
import random
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

import app_server_user_state
import app_server_control
import codex_execution
import document_store
import hybrid_state
import planning_order
import release_cohort
import work_orchestration
from project_identity import ProjectIdentityError, binding_token, load_project_identity, require_project_binding, resolved_workspace
try:
    from scripts import subprocess_launch
except ModuleNotFoundError:  # Direct execution: python scripts/dashboard_reporter.py
    import subprocess_launch  # type: ignore[no-redef]


SCHEMA_VERSION = 1
REPORT_SCHEMA_VERSION = 7
OUTBOX_RELATIVE = Path(".tool-shed/dashboard/outbox.sqlite3")
MAX_RESPONSE_BYTES = 65_536
LOCK_SECONDS = 30
PROCESS_LOCK_SECONDS = 120
LAUNCH_LOCK_SECONDS = 30
HEARTBEAT_SECONDS = 60
IDLE_EXIT_SECONDS = 7_200
IDLE_POLL_SECONDS = 60
SAFETY_DRAIN_LIMIT = 64


class DashboardReporterError(RuntimeError):
    pass


class DashboardHTTPError(DashboardReporterError):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"dashboard request failed with HTTP {status_code}: {detail}")


def now() -> datetime:
    return datetime.now(timezone.utc)


def stamp(value: datetime | None = None) -> str:
    return (value or now()).isoformat().replace("+00:00", "Z")


def local_shed_version(workspace: Path) -> str:
    try:
        value = json.loads((workspace / "SHED_VERSION.json").read_text(encoding="utf-8"))
        version = value.get("shed_version")
    except (OSError, json.JSONDecodeError):
        version = None
    return str(version or "unknown")


def _state_root() -> Path:
    configured = os.environ.get("TOOL_SHED_STATE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    codex_home = os.environ.get("CODEX_HOME")
    return (Path(codex_home).expanduser() if codex_home else Path.home() / ".codex") / "tool-shed"


def connection_path(project_id: str) -> Path:
    return _state_root() / "dashboard-connections" / f"{project_id}.json"


def _restrict_windows_acl(path: Path) -> None:
    identity = subprocess_launch.run(
        ["whoami"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        windowless=True,
    ).stdout.strip()
    if not identity:
        raise DashboardReporterError("Windows private-state owner could not be resolved")
    subprocess_launch.run(
        ["icacls", str(path), "/inheritance:r", "/grant:r", f"{identity}:(F)"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        windowless=True,
    )


def _write_private_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    windows = platform.system().lower() == "windows"
    if windows:
        _restrict_windows_acl(path.parent)
    else:
        try:
            os.chmod(path.parent, 0o700)
        except OSError:
            pass
    temporary = path.with_name(path.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if windows:
            _restrict_windows_acl(temporary)
        os.replace(temporary, path)
        if windows:
            _restrict_windows_acl(path)
        else:
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _write_private_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    temporary = path.with_name(path.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def load_connection(workspace: Path, *, required: bool = True) -> dict[str, Any] | None:
    identity = load_project_identity(workspace)
    path = connection_path(identity["project_id"])
    if not path.is_file():
        if required:
            raise DashboardReporterError("dashboard connection is not configured; run connect first")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DashboardReporterError("dashboard connection state is unreadable") from error
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION or value.get("project_id") != identity["project_id"]:
        raise DashboardReporterError("dashboard connection state is invalid or belongs to another project")
    return value


def report_endpoint(state: dict[str, Any]) -> str:
    scope = state.get("credential_scope", "operational")
    if scope == "qualification:write":
        return state["server"] + "/api/v1/qualification/reports"
    if scope != "operational":
        raise DashboardReporterError("dashboard credential scope is unsupported")
    return state["server"] + "/api/v1/reports"


def _request(url: str, *, payload: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        raw = error.read(MAX_RESPONSE_BYTES)
        try:
            detail = json.loads(raw).get("error", "remote request failed")
        except (json.JSONDecodeError, AttributeError):
            detail = "remote request failed"
        raise DashboardHTTPError(error.code, str(detail)) from error
    except urllib.error.URLError as error:
        raise DashboardReporterError(f"dashboard request was unavailable: {error.reason}") from error
    if len(raw) > MAX_RESPONSE_BYTES:
        raise DashboardReporterError("dashboard response exceeded 64 KiB")
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as error:
        raise DashboardReporterError("dashboard returned invalid JSON") from error
    if not isinstance(result, dict):
        raise DashboardReporterError("dashboard returned an invalid response")
    return result


def connect(workspace: Path, *, server: str, project_binding: str) -> dict[str, Any]:
    require_project_binding(workspace, project_binding, operation="dashboard-connect")
    identity = load_project_identity(workspace)
    current = load_connection(workspace, required=False)
    instance_id = (current or {}).get("instance_id") or str(uuid.uuid4())
    endpoint = server.rstrip("/") + "/api/v1/enrollment/requests"
    result = _request(
        endpoint,
        payload={
            "project_id": identity["project_id"],
            "project_name": identity["project_name"],
            "instance_id": instance_id,
            "platform": f"{platform.system().lower()}-{platform.machine().lower()}",
            "client_version": local_shed_version(workspace),
        },
    )
    required = {"request_id", "user_code", "device_secret", "expires_at"}
    if not required.issubset(result):
        raise DashboardReporterError("dashboard enrollment response is incomplete")
    state = {
        "schema_version": SCHEMA_VERSION,
        "project_id": identity["project_id"],
        "instance_id": instance_id,
        "server": server.rstrip("/"),
        "status": "pending",
        "request_id": str(result["request_id"]),
        "user_code": str(result["user_code"]),
        "device_secret": str(result["device_secret"]),
        "expires_at": str(result["expires_at"]),
        "reporter_token": None,
        "updated_at": stamp(),
    }
    _write_private_json(connection_path(identity["project_id"]), state)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-dashboard-connect",
        "status": "pending-approval",
        "server": state["server"],
        "request_id": state["request_id"],
        "user_code": state["user_code"],
        "expires_at": state["expires_at"],
        "approval_url": state["server"] + "/dashboard/enrollments/",
        "next_action": "Approve the matching code in the authenticated dashboard, then run connect-poll.",
        "writes_performed": True,
    }


def connect_poll(workspace: Path, *, project_binding: str) -> dict[str, Any]:
    require_project_binding(workspace, project_binding, operation="dashboard-connect")
    state = load_connection(workspace)
    if state["status"] == "connected":
        return {"schema_version": SCHEMA_VERSION, "kind": "tool-shed-dashboard-connect", "status": "connected", "writes_performed": False}
    result = _request(
        f"{state['server']}/api/v1/enrollment/requests/{state['request_id']}/poll",
        payload={},
        headers={"X-Tool-Shed-Device-Secret": state["device_secret"]},
    )
    if result.get("status") != "issued":
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "tool-shed-dashboard-connect",
            "status": result.get("status", "unknown"),
            "expires_at": result.get("expires_at", state["expires_at"]),
            "writes_performed": False,
        }
    token = result.get("reporter_token")
    if not isinstance(token, str) or len(token) < 32:
        raise DashboardReporterError("dashboard did not issue a valid reporter credential")
    state.update({"status": "connected", "reporter_token": token, "device_secret": None, "user_code": None, "updated_at": stamp()})
    _write_private_json(connection_path(state["project_id"]), state)
    return {"schema_version": SCHEMA_VERSION, "kind": "tool-shed-dashboard-connect", "status": "connected", "server": state["server"], "writes_performed": True}


def outbox_path(workspace: Path) -> Path:
    return workspace / OUTBOX_RELATIVE


def _outbox(workspace: Path) -> sqlite3.Connection:
    path = outbox_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, sequence INTEGER NOT NULL UNIQUE, payload_json TEXT NOT NULL, "
        "attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL, created_at TEXT NOT NULL, delivered_at TEXT) WITHOUT ROWID"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS worker_lease (id INTEGER PRIMARY KEY CHECK(id=1), owner TEXT NOT NULL, expires_at REAL NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS worker_process (id INTEGER PRIMARY KEY CHECK(id=1), owner TEXT NOT NULL, expires_at REAL NOT NULL)"
    )
    return connection


def _meta(connection: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = connection.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return str(row[0]) if row else default


def _set_meta(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute("INSERT INTO meta VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def _next_sequence(connection: sqlite3.Connection) -> int:
    value = int(_meta(connection, "sequence", "0") or 0) + 1
    _set_meta(connection, "sequence", str(value))
    return value


def _dashboard_state(workspace: Path) -> dict[str, Any]:
    campaigns = document_store.list_documents(workspace, lifecycle="active", document_type="campaign", limit=500)["documents"]
    ideas = document_store.list_documents(workspace, lifecycle="active", document_type="idea-brief", limit=500)["documents"]
    completed = document_store.list_documents(workspace, lifecycle="completed", document_type="campaign", limit=500)["documents"]
    with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)) as connection:
        open_outcomes = int(connection.execute("SELECT COUNT(*) FROM cycle WHERE lifecycle_state <> 'terminal'").fetchone()[0])
        unreconciled = int(
            connection.execute(
                "SELECT COUNT(*) FROM cycle AS c WHERE COALESCE((SELECT r.state FROM reconciliation AS r "
                "WHERE r.cycle_id = c.id ORDER BY r.compared_at DESC, r.id DESC LIMIT 1), 'open') = 'reconciliation-required' "
                "OR (c.lifecycle_state = 'terminal' AND COALESCE((SELECT r.state FROM reconciliation AS r "
                "WHERE r.cycle_id = c.id ORDER BY r.compared_at DESC, r.id DESC LIMIT 1), 'open') <> 'reconciled')"
            ).fetchone()[0]
        )
    return {
        "working_count": len(campaigns),
        "ready_count": 0,
        "blocked_count": 0,
        "active_idea_count": len(ideas),
        "open_outcome_count": open_outcomes,
        "unreconciled_outcome_count": unreconciled,
        "last_completed_id": completed[-1]["visible_id"] if completed else None,
    }


def _work_inventory(workspace: Path) -> dict[str, Any]:
    """Build a bounded, privacy-safe lifecycle projection from canonical state."""
    database = hybrid_state.database_path(workspace)
    with contextlib.closing(hybrid_state.connect(database, writable=False)) as connection:
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='document'").fetchone() is None:
            return {"total_count": 0, "truncated": False, "artifacts": []}
        total = int(
            connection.execute(
                "SELECT COUNT(*) FROM document WHERE namespace IN ('IDEA','MAP','PRM','CAMP')"
            ).fetchone()[0]
        )
        rows = connection.execute(
            """
            SELECT d.id, d.visible_id, d.namespace, d.title, d.lifecycle_state, d.updated_at,
                   COALESCE((
                       SELECT c.lifecycle_state FROM cycle AS c
                       WHERE c.origin_artifact_id = d.id
                       ORDER BY c.opened_at DESC, c.id DESC LIMIT 1
                   ), 'unknown') AS outcome_lifecycle,
                   COALESCE((
                       SELECT v.disposition FROM outcome_verdict AS v
                       JOIN cycle AS c ON c.id = v.cycle_id
                       WHERE c.origin_artifact_id = d.id
                       ORDER BY c.opened_at DESC, v.decided_at DESC, v.id DESC LIMIT 1
                   ), CASE WHEN EXISTS (
                       SELECT 1 FROM cycle AS c WHERE c.origin_artifact_id = d.id
                   ) THEN 'open' ELSE 'unknown' END) AS outcome_disposition,
                   COALESCE((
                       SELECT r.state FROM reconciliation AS r
                       JOIN cycle AS c ON c.id = r.cycle_id
                       WHERE c.origin_artifact_id = d.id
                       ORDER BY c.opened_at DESC, r.compared_at DESC, r.id DESC LIMIT 1
                   ), CASE WHEN EXISTS (
                       SELECT 1 FROM cycle AS c WHERE c.origin_artifact_id = d.id
                   ) THEN 'open' ELSE 'unknown' END) AS reconciliation_state
            FROM document AS d
            WHERE d.namespace IN ('IDEA','MAP','PRM','CAMP')
            ORDER BY d.visible_id
            LIMIT 500
            """
        ).fetchall()
        try:
            planning_items = {
                item["artifact_id"]: item
                for artifact_type in ("idea-brief", "program-roadmap")
                for item in planning_order.projection_for_connection(connection, artifact_type)["items"]
            }
        except planning_order.PlanningOrderError as error:
            raise DashboardReporterError(f"local planning order is invalid: {error}") from error
        artifact_ids = [str(row["id"]) for row in rows]
        visible_by_id = {str(row["id"]): str(row["visible_id"]) for row in rows}
        parent_ids: dict[str, list[str]] = {value: [] for value in artifact_ids}
        produces_ids: dict[str, list[str]] = {value: [] for value in artifact_ids}
        closure_by_artifact: dict[str, dict[str, Any]] = {}
        if artifact_ids:
            placeholders = ",".join("?" for _ in artifact_ids)
            relations = connection.execute(
                f"SELECT from_artifact_id, relation_type, to_artifact_id FROM relationship "
                f"WHERE retired_revision IS NULL AND relation_type IN ('outcome-parent','produces') "
                f"AND (from_artifact_id IN ({placeholders}) OR to_artifact_id IN ({placeholders}))",
                (*artifact_ids, *artifact_ids),
            ).fetchall()
            related_ids = {
                str(value)
                for relation in relations
                for value in (relation["from_artifact_id"], relation["to_artifact_id"])
                if str(value) not in visible_by_id
            }
            if related_ids:
                related_placeholders = ",".join("?" for _ in related_ids)
                for related in connection.execute(
                    f"SELECT id, visible_id FROM document WHERE id IN ({related_placeholders})",
                    tuple(sorted(related_ids)),
                ):
                    visible_by_id[str(related["id"])] = str(related["visible_id"])
            for relation in relations:
                source = str(relation["from_artifact_id"])
                target = str(relation["to_artifact_id"])
                if relation["relation_type"] == "outcome-parent" and source in parent_ids and target in visible_by_id:
                    parent_ids[source].append(visible_by_id[target])
                elif relation["relation_type"] == "produces":
                    if source in produces_ids and target in visible_by_id:
                        produces_ids[source].append(visible_by_id[target])
                    if target in parent_ids and source in visible_by_id:
                        parent_ids[target].append(visible_by_id[source])
        if artifact_ids and connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='closure_rollup'"
        ).fetchone():
            placeholders = ",".join("?" for _ in artifact_ids)
            closure_rows = connection.execute(
                f"SELECT ce.artifact_id, ce.id AS element_id, ce.subject_revision, "
                f"cr.local_closure, cr.evidence_health, cr.graph_health, cr.effective_closed, "
                f"cr.reason_codes_json, cr.open_descendants, cr.unknown_descendants, "
                f"cr.invalid_descendants, cr.graph_revision, cr.evaluator_version, cr.evaluated_at "
                f"FROM closure_element ce JOIN closure_rollup cr ON cr.element_id=ce.id "
                f"WHERE ce.role='cycle' AND ce.artifact_id IN ({placeholders}) "
                f"ORDER BY ce.artifact_id, ce.subject_revision DESC, ce.id",
                tuple(artifact_ids),
            ).fetchall()
            for closure in closure_rows:
                artifact_id = str(closure["artifact_id"])
                if artifact_id in closure_by_artifact:
                    continue
                blockers = [
                    {
                        "blocking_element_id": item["blocking_element_id"],
                        "blocking_obligation_id": item["blocking_obligation_id"],
                        "reason_code": item["reason_code"],
                        "depth": int(item["depth"]),
                    }
                    for item in connection.execute(
                        "SELECT blocking_element_id, blocking_obligation_id, reason_code, depth "
                        "FROM closure_blocker WHERE ancestor_element_id=? "
                        "ORDER BY depth, reason_code, id LIMIT 20",
                        (closure["element_id"],),
                    )
                ]
                closure_by_artifact[artifact_id] = {
                    "local_closure": str(closure["local_closure"]),
                    "evidence_health": str(closure["evidence_health"]),
                    "graph_health": str(closure["graph_health"]),
                    "effective_closed": bool(closure["effective_closed"]),
                    "reason_codes": json.loads(closure["reason_codes_json"]),
                    "counts": {
                        "open": int(closure["open_descendants"]),
                        "unknown": int(closure["unknown_descendants"]),
                        "invalid": int(closure["invalid_descendants"]),
                    },
                    "blockers": blockers,
                    "subject_revision": int(closure["subject_revision"]),
                    "graph_revision": int(closure["graph_revision"]),
                    "evaluator_version": str(closure["evaluator_version"]),
                    "evaluated_at": str(closure["evaluated_at"]),
                }
    type_by_namespace = {
        "IDEA": "idea-brief",
        "MAP": "project-map",
        "PRM": "program-roadmap",
        "CAMP": "campaign",
    }
    artifacts = []
    for row in rows:
        artifact_id = str(row["id"])
        artifact_type = type_by_namespace[str(row["namespace"])]
        planning = planning_items.get(artifact_id)
        title = " ".join(str(row["title"]).split())[:160] or str(row["visible_id"])
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "visible_id": str(row["visible_id"]),
                "artifact_type": artifact_type,
                "title": title,
                "document_lifecycle": str(row["lifecycle_state"]),
                "outcome_lifecycle": str(row["outcome_lifecycle"]),
                "outcome_disposition": str(row["outcome_disposition"]),
                "reconciliation_state": str(row["reconciliation_state"]),
                "parent_ids": sorted(set(parent_ids[artifact_id]))[:16],
                "produces_ids": sorted(set(produces_ids[artifact_id]))[:16],
                "planning_position": planning["position"] if planning else None,
                "planning_order_source": (
                    planning["order_source"]
                    if planning
                    else "derived"
                    if artifact_type in planning_order.SUPPORTED_TYPES
                    else "not-applicable"
                ),
                "planning_readiness": (
                    planning["readiness"]
                    if planning
                    else "terminal"
                    if artifact_type in planning_order.SUPPORTED_TYPES
                    else "not-applicable"
                ),
                "closure_status": closure_by_artifact.get(
                    artifact_id,
                    {
                        "local_closure": "unknown",
                        "evidence_health": "unknown",
                        "graph_health": "unknown",
                        "effective_closed": False,
                        "reason_codes": ["CLOSURE_NOT_AVAILABLE"],
                        "counts": {"open": 0, "unknown": 1, "invalid": 0},
                        "blockers": [],
                        "subject_revision": 0,
                        "graph_revision": 0,
                        "evaluator_version": "not-available",
                        "evaluated_at": str(row["updated_at"]),
                    },
                ),
                "updated_at": str(row["updated_at"]),
            }
        )
    return {"total_count": total, "truncated": total > len(artifacts), "artifacts": artifacts}


def _lifecycle_events(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    *,
    instance_id: str,
    sequence: int,
    occurred_at: str,
) -> list[dict[str, Any]]:
    if previous is None:
        return []
    old_by_id = {item["artifact_id"]: item for item in previous.get("artifacts", [])}
    transitions = (
        ("document_lifecycle", "document-lifecycle"),
        ("outcome_lifecycle", "outcome-lifecycle"),
        ("outcome_disposition", "outcome-disposition"),
        ("reconciliation_state", "reconciliation"),
    )
    events: list[dict[str, Any]] = []
    for item in current["artifacts"]:
        old = old_by_id.get(item["artifact_id"])
        changes = [("created", "absent", item["document_lifecycle"])] if old is None else [
            (transition, str(old.get(field, "unknown")), str(item[field]))
            for field, transition in transitions
            if old.get(field) != item[field]
        ]
        for transition, before, after in changes:
            material = f"{instance_id}:{sequence}:{item['artifact_id']}:{transition}:{before}:{after}"
            events.append(
                {
                    "event_key": hashlib.sha256(material.encode()).hexdigest(),
                    "artifact_id": item["artifact_id"],
                    "visible_id": item["visible_id"],
                    "artifact_type": item["artifact_type"],
                    "title": item["title"],
                    "transition": transition,
                    "from_state": before,
                    "to_state": after,
                    "occurred_at": occurred_at,
                }
            )
    return events[:50]


def _release_chain_projection(
    status: dict[str, Any], inventory: dict[str, Any]
) -> dict[str, Any]:
    """Roll release registrations up to operator-facing Idea chains.

    The release cohort intentionally retains one registration per owning outcome.  The
    dashboard needs the distinct chain count, so derive connected components from the
    locally authoritative reported relationships without sending paths or document bodies.
    """
    registrations: list[tuple[str, str, int]] = []
    for cohort in status.get("active", []):
        for candidate in cohort.get("candidates", []):
            origin_path = candidate.get("origin_path")
            commit = candidate.get("commit")
            if not isinstance(origin_path, str) or not origin_path.startswith("sqlite/documents/"):
                continue
            visible_id = origin_path.removeprefix("sqlite/documents/")
            if not visible_id or "/" in visible_id or len(visible_id) > 64:
                continue
            if not isinstance(commit, str) or len(commit) != 40:
                continue
            registrations.append((visible_id, commit, len(registrations)))

    artifacts = {
        str(item.get("visible_id")): item
        for item in inventory.get("artifacts", [])
        if isinstance(item, dict) and item.get("visible_id")
    }
    graph = {visible_id: set() for visible_id in artifacts}
    for visible_id, artifact in artifacts.items():
        for related_id in [
            *artifact.get("parent_ids", []),
            *artifact.get("produces_ids", []),
        ]:
            if related_id in graph:
                graph[visible_id].add(related_id)
                graph[related_id].add(visible_id)

    component_by_id: dict[str, set[str]] = {}
    visited: set[str] = set()
    for visible_id in graph:
        if visible_id in visited:
            continue
        component: set[str] = set()
        pending = [visible_id]
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            pending.extend(graph[current] - visited)
        for member in component:
            component_by_id[member] = component

    registered_ids = {visible_id for visible_id, _, _ in registrations}
    components: dict[str, set[str]] = {}
    for visible_id in registered_ids:
        component = component_by_id.get(visible_id, {visible_id})
        key = min(component)
        components[key] = component

    artifact_type_fields = {
        "idea-brief": "idea_id",
        "project-map": "map_id",
        "program-roadmap": "prm_id",
        "campaign": "campaign_id",
    }
    prefix_fields = {
        "IDEA-": "idea_id",
        "MAP-": "map_id",
        "PRM-": "prm_id",
        "CAMP-": "campaign_id",
    }
    chains: list[tuple[int, dict[str, Any]]] = []
    for component in components.values():
        component_registrations = [
            (visible_id, commit, ordinal)
            for visible_id, commit, ordinal in registrations
            if visible_id in component
        ]
        if not component_registrations:
            continue
        ids: dict[str, str | None] = {
            "idea_id": None,
            "map_id": None,
            "prm_id": None,
            "campaign_id": None,
        }
        for visible_id in sorted(component):
            artifact = artifacts.get(visible_id)
            field = artifact_type_fields.get(str(artifact.get("artifact_type"))) if artifact else None
            if field is None:
                field = next(
                    (candidate for prefix, candidate in prefix_fields.items() if visible_id.startswith(prefix)),
                    None,
                )
            if field and ids[field] is None:
                ids[field] = visible_id
        latest_visible_id, latest_commit, latest_ordinal = max(
            component_registrations, key=lambda item: item[2]
        )
        root_id = next(
            (ids[field] for field in ("idea_id", "map_id", "prm_id", "campaign_id") if ids[field]),
            latest_visible_id,
        )
        chains.append(
            (
                latest_ordinal,
                {
                    "root_id": root_id,
                    **ids,
                    "stage": "awaiting-work5",
                    "latest_commit": latest_commit,
                    "candidate_count": len({commit for _, commit, _ in component_registrations}),
                },
            )
        )
    chains.sort(key=lambda item: (item[0], str(item[1]["root_id"])), reverse=True)
    bounded = [item for _, item in chains[:50]]
    return {
        "awaiting_work5_chain_count": len(chains),
        "candidate_commit_count": len({commit for _, commit, _ in registrations}),
        "registration_count": len(registrations),
        "release_chains": bounded,
        "release_chains_truncated": len(chains) > len(bounded),
    }


def _release_posture(
    workspace: Path, *, inventory: dict[str, Any], observed_at: str
) -> dict[str, Any]:
    installed = local_shed_version(workspace)
    stable_version = None
    stable_source = "unknown"
    candidate_version = None
    pending_candidates = 0
    production_version = None
    production_source = "unknown"
    projection = {
        "awaiting_work5_chain_count": 0,
        "candidate_commit_count": 0,
        "registration_count": 0,
        "release_chains": [],
        "release_chains_truncated": False,
    }
    try:
        status = release_cohort.status(workspace)
        stable_version = status.get("current_base_tag")
        if isinstance(stable_version, str) and stable_version.startswith("v"):
            stable_source = "local-git-tag"
        else:
            stable_version = None
        pending_candidates = min(
            sum(len(item.get("candidates", [])) for item in status.get("active", [])),
            10_000,
        )
        if pending_candidates and installed != "unknown":
            candidate_version = installed
        production_version = next(
            (
                item.get("release_tag")
                for item in status.get("recent_terminal", [])
                if item.get("release_tag")
            ),
            None,
        )
        if production_version:
            production_source = "release-cohort"
        projection = _release_chain_projection(status, inventory)
    except (
        OSError,
        ProjectIdentityError,
        release_cohort.ReleaseCohortError,
        hybrid_state.HybridStateError,
    ):
        pass
    normalized_installed = installed.removeprefix("v")
    normalized_stable = str(stable_version or "").removeprefix("v")
    return {
        "installed_version": installed,
        "stable_version": stable_version,
        "stable_source": stable_source,
        "candidate_version": candidate_version,
        "pending_candidate_count": pending_candidates,
        "production_version": production_version,
        "production_source": production_source,
        "observed_at": observed_at,
        "compatibility_state": "compatible",
        "qualification_state": (
            "qualified"
            if normalized_stable and normalized_installed == normalized_stable
            else "unknown"
        ),
        **projection,
    }


def _instance_health(
    workspace: Path,
    *,
    state: dict[str, Any],
    inventory: dict[str, Any],
    quiescent: bool,
    observed_at: str,
) -> dict[str, Any]:
    pending_count = 0
    last_delivery_at = None
    delayed = False
    with contextlib.closing(_outbox(workspace)) as connection:
        pending_count = min(
            int(connection.execute("SELECT COUNT(*) FROM outbox WHERE delivered_at IS NULL").fetchone()[0]),
            10_000,
        )
        raw_delivery = _meta(connection, "last_delivery")
    if raw_delivery:
        try:
            delivered = datetime.fromtimestamp(float(raw_delivery), timezone.utc)
            last_delivery_at = stamp(delivered)
            delayed = pending_count > 0 and now() - delivered > timedelta(minutes=5)
        except (ValueError, OverflowError):
            delayed = pending_count > 0
    elif pending_count:
        delayed = True
    reporter_state = "quiescent" if quiescent else "delivery-delayed" if delayed else "active"
    semantic_digest = hashlib.sha256(
        json.dumps(
            {"state": state, "work_inventory": inventory},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "reporter_state": reporter_state,
        "pending_event_count": pending_count,
        "last_delivery_at": last_delivery_at,
        "semantic_digest": semantic_digest,
        "release": _release_posture(
            workspace, inventory=inventory, observed_at=observed_at
        ),
    }


def report_payload(
    workspace: Path,
    *,
    sequence: int,
    reason: str | None = None,
    quiescent: bool = False,
    work_inventory: dict[str, Any] | None = None,
    lifecycle_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    identity = load_project_identity(workspace)
    state = load_connection(workspace)
    efficiency = work_orchestration.efficiency_report(workspace, hours=24)
    app_events = app_server_user_state.AppServerEventStore()
    app = app_events.report(hours=168)
    preference = app_server_user_state.AppServerPreferenceStore().status()
    observed_at = now()
    observed = stamp(observed_at)
    telemetry_path = codex_execution.default_telemetry_path()
    performance_windows: dict[str, dict[str, Any]] = {}
    performance_failure_groups: list[dict[str, Any]] = []
    for window_id, hours in (("24h", 24), ("7d", 168), ("30d", 720)):
        metrics = codex_execution.app_server_performance_report(
            telemetry_path, hours=hours, observed_at=observed_at
        )
        metrics["fallbacks"] = int(app_events.report(hours=hours).get("gui_fallbacks", 0))
        if window_id == "7d":
            performance_failure_groups = list(metrics.get("failure_groups", []))
        metrics.pop("failure_groups", None)
        performance_windows[window_id] = metrics
    selected_performance = performance_windows["7d"]
    readiness_state = "disabled" if not preference.enabled else "unknown"
    readiness_client = selected_performance.get("client_version")
    if preference.enabled:
        try:
            readiness = app_server_control.control_status(workspace=workspace)
        except (OSError, ValueError, RuntimeError):
            readiness = {}
        if readiness.get("app_server_available") is False:
            readiness_state = "unavailable"
        elif readiness.get("app_server_available") is True:
            readiness_state = "available" if readiness.get("enabled_roles") else "unqualified"
        readiness_client = readiness.get("installed_codex") or readiness_client
    allowed_reasons = {
        "managed-document-update",
        "managed-update",
        "safety-convergence",
        "quiescent",
        "client-connected",
        "client-disconnected",
    }
    summary_code = reason if reason in allowed_reasons else "managed-update"
    events = [] if not reason or reason == "heartbeat" else [{"kind": "state-change", "summary_code": summary_code, "occurred_at": observed}]
    dashboard_state = _dashboard_state(workspace)
    inventory = work_inventory if work_inventory is not None else _work_inventory(workspace)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "idempotency_key": str(uuid.uuid4()),
        "sequence": sequence,
        "observed_at": observed,
        "project": {"id": identity["project_id"], "name": identity["project_name"]},
        "instance": {
            "id": state["instance_id"],
            "platform": f"{platform.system().lower()}-{platform.machine().lower()}",
            "client_version": local_shed_version(workspace),
            "counter_epoch": efficiency["counter_epoch"],
            "quiescent": quiescent,
        },
        "state": dashboard_state,
        "material_events": events,
        "app_server": {
            "enabled": preference.enabled,
            "availability_state": readiness_state,
            "attempts": int(selected_performance["attempts"]),
            "failures": int(selected_performance["failures"] + selected_performance["interruptions"]),
            "fallbacks": int(app.get("gui_fallbacks", 0)),
            "last_success": selected_performance.get("last_success"),
            "last_failure": selected_performance.get("last_failure"),
            "client_version": readiness_client or "unknown",
            "failure_groups": performance_failure_groups or app.get("failure_groups", []),
            "readiness_observed_at": observed,
            "performance": {"default_window": "7d", "windows": performance_windows},
        },
        "work_efficiency": {
            "window_start": efficiency["window"]["started_at"],
            "window_end": efficiency["window"]["ended_at"],
            "remedial_tokens_actual": efficiency["remedial_tokens_actual"],
            "remedial_token_coverage": efficiency["remedial_token_coverage"],
            "remedial_interactions": efficiency["remedial_proxy"]["interactions"],
            "remedial_output_bytes": efficiency["remedial_proxy"]["output_bytes"],
            "remedial_duration_ms": efficiency["remedial_proxy"]["duration_ms"],
            "remedial_retries": efficiency["remedial_proxy"]["retry_count"],
        },
        "work_inventory": inventory,
        "lifecycle_events": lifecycle_events or [],
        "instance_health": _instance_health(
            workspace,
            state=dashboard_state,
            inventory=inventory,
            quiescent=quiescent,
            observed_at=observed,
        ),
    }


def _enqueue_connected(workspace: Path, *, reason: str, quiescent: bool = False) -> dict[str, Any]:
    state = load_connection(workspace)
    if state["status"] != "connected":
        raise DashboardReporterError("dashboard connection is awaiting approval")
    with contextlib.closing(_outbox(workspace)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        sequence = _next_sequence(connection)
        inventory = _work_inventory(workspace)
        previous_raw = _meta(connection, "work_inventory_v2")
        try:
            previous = json.loads(previous_raw) if previous_raw else None
        except json.JSONDecodeError:
            previous = None
        observed = stamp()
        lifecycle_events = _lifecycle_events(
            previous,
            inventory,
            instance_id=str(state["instance_id"]),
            sequence=sequence,
            occurred_at=observed,
        )
        payload = report_payload(
            workspace,
            sequence=sequence,
            reason=reason,
            quiescent=quiescent,
            work_inventory=inventory,
            lifecycle_events=lifecycle_events,
        )
        event_id = str(uuid.uuid4())
        connection.execute(
            "INSERT INTO outbox VALUES (?, ?, ?, 0, ?, ?, NULL)",
            (event_id, sequence, json.dumps(payload, sort_keys=True, separators=(",", ":")), time.time(), stamp()),
        )
        _set_meta(connection, "last_activity", str(time.time()))
        _set_meta(connection, "work_inventory_v2", json.dumps(inventory, sort_keys=True, separators=(",", ":")))
        connection.commit()
    return {"schema_version": SCHEMA_VERSION, "kind": "tool-shed-dashboard-enqueue", "event_id": event_id, "sequence": sequence, "reason": reason, "writes_performed": True}


def enqueue(workspace: Path, *, project_binding: str, reason: str, quiescent: bool = False) -> dict[str, Any]:
    require_project_binding(workspace, project_binding, operation="dashboard-report")
    with subprocess_launch.windowless_subprocesses():
        return _enqueue_connected(workspace, reason=reason, quiescent=quiescent)


def enqueue_if_connected(workspace: Path, *, reason: str) -> dict[str, Any] | None:
    """Best-effort managed-write hook; the originating operation already proved project authority."""
    try:
        with subprocess_launch.windowless_subprocesses():
            state = load_connection(workspace, required=False)
            if not state or state.get("status") != "connected" or not state.get("reporter_token"):
                return None
            queued = _enqueue_connected(workspace, reason=reason)
            launch_claim = _claim_worker_launch(workspace)
            if launch_claim is None:
                return queued
            command = [
                subprocess_launch.background_python_executable(),
                str(Path(__file__).resolve()),
                "--workspace",
                str(workspace),
                "worker",
                "--project-binding",
                binding_token(workspace, operation="dashboard-report"),
                "--launch-claim",
                launch_claim,
            ]
        kwargs: dict[str, Any] = {
            "cwd": workspace,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
        }
        if platform.system().lower() != "windows":
            kwargs["start_new_session"] = True
        try:
            subprocess_launch.popen(
                command,
                windowless=True,
                **kwargs,
            )
        except (OSError, ValueError):
            _release_worker_process(workspace, launch_claim)
            raise
        return queued
    except (DashboardReporterError, OSError, ValueError, sqlite3.DatabaseError):
        return None


def _lease(connection: sqlite3.Connection, owner: str) -> bool:
    current = time.time()
    connection.execute("BEGIN IMMEDIATE")
    row = connection.execute("SELECT owner, expires_at FROM worker_lease WHERE id=1").fetchone()
    if row and row["owner"] != owner and float(row["expires_at"]) > current:
        connection.rollback()
        return False
    connection.execute(
        "INSERT INTO worker_lease VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE SET owner=excluded.owner, expires_at=excluded.expires_at",
        (owner, current + LOCK_SECONDS),
    )
    connection.commit()
    return True


def _claim_worker_launch(workspace: Path) -> str | None:
    """Atomically reserve the persistent-worker slot before spawning."""

    owner = str(uuid.uuid4())
    current = time.time()
    with contextlib.closing(_outbox(workspace)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT owner, expires_at FROM worker_process WHERE id=1"
        ).fetchone()
        if row and float(row["expires_at"]) > current:
            connection.rollback()
            return None
        connection.execute(
            "INSERT INTO worker_process VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET owner=excluded.owner, expires_at=excluded.expires_at",
            (owner, current + LAUNCH_LOCK_SECONDS),
        )
        connection.commit()
    return owner


def _adopt_worker_process(workspace: Path, launch_claim: str | None) -> str | None:
    """Adopt an exact live launch claim or directly claim an idle worker slot."""

    owner = launch_claim or str(uuid.uuid4())
    current = time.time()
    with contextlib.closing(_outbox(workspace)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT owner, expires_at FROM worker_process WHERE id=1"
        ).fetchone()
        if launch_claim is not None:
            if (
                row is None
                or str(row["owner"]) != launch_claim
                or float(row["expires_at"]) <= current
            ):
                connection.rollback()
                return None
        elif row and float(row["expires_at"]) > current:
            connection.rollback()
            return None
        connection.execute(
            "INSERT INTO worker_process VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET owner=excluded.owner, expires_at=excluded.expires_at",
            (owner, current + PROCESS_LOCK_SECONDS),
        )
        connection.commit()
    return owner


def _release_worker_process(workspace: Path, owner: str) -> None:
    with contextlib.closing(_outbox(workspace)) as connection:
        connection.execute("DELETE FROM worker_process WHERE id=1 AND owner=?", (owner,))


def worker_once(workspace: Path) -> dict[str, Any]:
    state = load_connection(workspace)
    if state["status"] != "connected" or not state.get("reporter_token"):
        raise DashboardReporterError("dashboard connection is not active")
    owner = str(uuid.uuid4())
    with contextlib.closing(_outbox(workspace)) as connection:
        if not _lease(connection, owner):
            return {"schema_version": SCHEMA_VERSION, "kind": "tool-shed-dashboard-worker", "status": "singleton-active", "writes_performed": False}
        row = connection.execute(
            "SELECT * FROM outbox WHERE delivered_at IS NULL AND next_attempt <= ? ORDER BY sequence LIMIT 1",
            (time.time(),),
        ).fetchone()
        if row is None:
            connection.execute("DELETE FROM worker_lease WHERE id=1 AND owner=?", (owner,))
            return {"schema_version": SCHEMA_VERSION, "kind": "tool-shed-dashboard-worker", "status": "idle", "writes_performed": False}
        payload = json.loads(row["payload_json"])
        try:
            result = _request(
                report_endpoint(state),
                payload=payload,
                headers={"Authorization": "Bearer " + state["reporter_token"]},
            )
            if result.get("status") not in {"accepted", "duplicate"}:
                raise DashboardReporterError("dashboard did not accept the report")
        except DashboardHTTPError as error:
            if error.status_code == 409 and error.detail == "report sequence is stale":
                retired = connection.execute(
                    "UPDATE outbox SET delivered_at=? WHERE delivered_at IS NULL AND sequence <= ?",
                    (stamp(), row["sequence"]),
                )
                connection.execute("DELETE FROM worker_lease WHERE id=1 AND owner=?", (owner,))
                return {
                    "schema_version": SCHEMA_VERSION,
                    "kind": "tool-shed-dashboard-worker",
                    "status": "superseded",
                    "sequence": row["sequence"],
                    "superseded_count": retired.rowcount,
                    "writes_performed": True,
                }
            attempts = int(row["attempts"]) + 1
            delay = min(300, 2 ** min(attempts, 8)) + random.random()
            connection.execute(
                "UPDATE outbox SET attempts=?, next_attempt=? WHERE id=?",
                (attempts, time.time() + delay, row["id"]),
            )
            connection.execute("DELETE FROM worker_lease WHERE id=1 AND owner=?", (owner,))
            raise
        except DashboardReporterError:
            attempts = int(row["attempts"]) + 1
            delay = min(300, 2 ** min(attempts, 8)) + random.random()
            connection.execute("UPDATE outbox SET attempts=?, next_attempt=? WHERE id=?", (attempts, time.time() + delay, row["id"]))
            connection.execute("DELETE FROM worker_lease WHERE id=1 AND owner=?", (owner,))
            raise
        retired = connection.execute(
            "UPDATE outbox SET delivered_at=? WHERE delivered_at IS NULL AND sequence <= ?",
            (stamp(), row["sequence"]),
        )
        _set_meta(connection, "last_delivery", str(time.time()))
        connection.execute("DELETE FROM worker_lease WHERE id=1 AND owner=?", (owner,))
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "tool-shed-dashboard-worker",
            "status": "delivered",
            "sequence": row["sequence"],
            "superseded_count": max(0, retired.rowcount - 1),
            "writes_performed": True,
        }


def _worker_sleep_seconds(
    *,
    current: float,
    last_activity: float,
    last_heartbeat: float,
    pending: int,
) -> float:
    """Keep retry delivery responsive without polling an empty outbox every second."""
    if pending:
        return 1.0
    return max(
        0.05,
        min(
            float(IDLE_POLL_SECONDS),
            last_heartbeat + HEARTBEAT_SECONDS - current,
            last_activity + IDLE_EXIT_SECONDS - current,
        ),
    )


def worker(
    workspace: Path,
    *,
    project_binding: str,
    max_cycles: int | None = None,
    launch_claim: str | None = None,
) -> dict[str, Any]:
    require_project_binding(workspace, project_binding, operation="dashboard-report")
    owner = _adopt_worker_process(workspace, launch_claim)
    if owner is None:
        status = "launch-claim-invalid" if launch_claim is not None else "singleton-active"
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "tool-shed-dashboard-worker",
            "status": status,
            "writes_performed": False,
        }
    cycles = 0
    try:
        while True:
            cycles += 1
            with contextlib.closing(_outbox(workspace)) as connection:
                current = time.time()
                connection.execute(
                    "UPDATE worker_process SET expires_at=? WHERE id=1 AND owner=?",
                    (current + PROCESS_LOCK_SECONDS, owner),
                )
                last_activity = float(_meta(connection, "last_activity", str(current)) or current)
                last_heartbeat = float(_meta(connection, "last_heartbeat", "0") or 0)
                pending = int(connection.execute("SELECT COUNT(*) FROM outbox WHERE delivered_at IS NULL").fetchone()[0])
            if current - last_heartbeat >= HEARTBEAT_SECONDS:
                enqueue(workspace, project_binding=project_binding, reason="heartbeat")
                with contextlib.closing(_outbox(workspace)) as connection:
                    _set_meta(connection, "last_heartbeat", str(current))
                last_heartbeat = current
            try:
                worker_once(workspace)
            except DashboardReporterError:
                pass
            if current - last_activity >= IDLE_EXIT_SECONDS and pending == 0:
                enqueue(workspace, project_binding=project_binding, reason="quiescent", quiescent=True)
                worker_once(workspace)
                return {"schema_version": SCHEMA_VERSION, "kind": "tool-shed-dashboard-worker", "status": "quiescent", "cycles": cycles, "writes_performed": True}
            if max_cycles is not None and cycles >= max_cycles:
                return {"schema_version": SCHEMA_VERSION, "kind": "tool-shed-dashboard-worker", "status": "bounded-stop", "cycles": cycles, "writes_performed": True}
            time.sleep(
                _worker_sleep_seconds(
                    current=current,
                    last_activity=last_activity,
                    last_heartbeat=last_heartbeat,
                    pending=pending,
                )
            )
    finally:
        _release_worker_process(workspace, owner)


def disconnect(workspace: Path, *, project_binding: str) -> dict[str, Any]:
    require_project_binding(workspace, project_binding, operation="dashboard-connect")
    state = load_connection(workspace)
    if state.get("status") != "connected" or not state.get("reporter_token"):
        return {"schema_version": SCHEMA_VERSION, "kind": "tool-shed-dashboard-disconnect", "status": state.get("status"), "writes_performed": False}
    result = _request(
        state["server"] + "/api/v1/credentials/revoke",
        payload={},
        headers={"Authorization": "Bearer " + state["reporter_token"]},
    )
    if result.get("status") != "revoked":
        raise DashboardReporterError("dashboard did not confirm credential revocation")
    state.update({"status": "revoked", "reporter_token": None, "updated_at": stamp()})
    _write_private_json(connection_path(state["project_id"]), state)
    return {"schema_version": SCHEMA_VERSION, "kind": "tool-shed-dashboard-disconnect", "status": "revoked", "writes_performed": True}


def scheduler_plan(workspace: Path) -> dict[str, Any]:
    system = platform.system().lower()
    project_id = str(load_project_identity(workspace)["project_id"])
    executable_path = Path(
        subprocess_launch.background_python_executable(sys.executable)
    )
    executable = executable_path.as_posix()
    script = Path(__file__).resolve().as_posix()
    root = workspace.resolve().as_posix()
    if system == "windows":
        command = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"Register-ScheduledTask ToolShedDashboardSafety-{project_id} for {executable} every 15 minutes",
        ]
    elif system == "darwin":
        command = ["launchctl", "bootstrap", "gui/<uid>", f"~/Library/LaunchAgents/com.toolshed.dashboard.{project_id}.plist"]
    else:
        command = ["systemctl", "--user", "enable", "--now", f"tool-shed-dashboard-safety-{project_id}.timer"]
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-dashboard-scheduler-plan",
        "platform": system,
        "cadence_minutes": 15,
        "command": command,
        "mutation_authorized": False,
        "writes_performed": False,
    }


def scheduler_install(workspace: Path, *, project_binding: str) -> dict[str, Any]:
    require_project_binding(workspace, project_binding, operation="dashboard-report")
    identity = load_project_identity(workspace)
    system = platform.system().lower()
    executable_path = Path(
        subprocess_launch.background_python_executable(sys.executable)
    )
    executable = str(executable_path)
    script = str(Path(__file__).resolve())
    root = str(workspace.resolve())
    binding = binding_token(workspace, operation="dashboard-report")
    if system == "linux":
        config_root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        unit_root = config_root / "systemd" / "user"
        suffix = str(identity["project_id"])
        service = unit_root / f"tool-shed-dashboard-safety-{suffix}.service"
        timer = unit_root / f"tool-shed-dashboard-safety-{suffix}.timer"
        _write_private_text(
            service,
            "[Unit]\nDescription=Tool Shed dashboard convergence report\n\n[Service]\nType=oneshot\n"
            f'ExecStart="{executable}" "{script}" --workspace "{root}" safety-pass --project-binding {binding}\n',
        )
        _write_private_text(
            timer,
            "[Unit]\nDescription=Tool Shed dashboard 15-minute safety pass\n\n[Timer]\nOnBootSec=2min\n"
            f"OnUnitActiveSec=15min\nPersistent=true\nUnit={service.name}\n\n[Install]\nWantedBy=timers.target\n",
        )
        subprocess_launch.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess_launch.run(["systemctl", "--user", "enable", "--now", timer.name], check=True)
        installed = [str(service), str(timer)]
    elif system == "darwin":
        label = "com.toolshed.dashboard." + str(identity["project_id"])
        target = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
        arguments = "".join(f"<string>{html.escape(value)}</string>" for value in (executable, script, "--workspace", root, "safety-pass", "--project-binding", binding))
        _write_private_text(
            target,
            '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0"><dict>'
            f"<key>Label</key><string>{label}</string><key>ProgramArguments</key><array>{arguments}</array>"
            "<key>StartInterval</key><integer>900</integer><key>RunAtLoad</key><true/></dict></plist>\n",
        )
        subprocess_launch.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(target)], check=True)
        installed = [str(target)]
    elif system == "windows":
        task = "ToolShedDashboardSafety-" + str(identity["project_id"])
        arguments = f'"{script}" --workspace "{root}" safety-pass --project-binding {binding}'

        def powershell_literal(value: str) -> str:
            return "'" + value.replace("'", "''") + "'"

        command = "; ".join(
            (
                f"$action = New-ScheduledTaskAction -Execute {powershell_literal(executable)} -Argument {powershell_literal(arguments)}",
                "$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(15) -RepetitionInterval (New-TimeSpan -Minutes 15)",
                "$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable",
                f"Register-ScheduledTask -TaskName {powershell_literal(task)} -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null",
            )
        )
        subprocess_launch.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            check=True,
            windowless=True,
        )
        installed = [task]
    else:
        raise DashboardReporterError(f"dashboard scheduling is unsupported on {system}")
    return {"schema_version": SCHEMA_VERSION, "kind": "tool-shed-dashboard-scheduler", "status": "installed", "platform": system, "targets": installed, "writes_performed": True}


def scheduler_remove(workspace: Path, *, project_binding: str) -> dict[str, Any]:
    require_project_binding(workspace, project_binding, operation="dashboard-report")
    identity = load_project_identity(workspace)
    system = platform.system().lower()
    suffix = str(identity["project_id"])
    removed: list[str] = []
    if system == "linux":
        unit_root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "systemd" / "user"
        service = unit_root / f"tool-shed-dashboard-safety-{suffix}.service"
        timer = unit_root / f"tool-shed-dashboard-safety-{suffix}.timer"
        subprocess_launch.run(["systemctl", "--user", "disable", "--now", timer.name], check=False)
        for target in (service, timer):
            if target.is_file():
                target.unlink()
                removed.append(str(target))
        subprocess_launch.run(["systemctl", "--user", "daemon-reload"], check=False)
    elif system == "darwin":
        label = "com.toolshed.dashboard." + suffix
        target = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
        subprocess_launch.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(target)], check=False)
        if target.is_file():
            target.unlink()
            removed.append(str(target))
    elif system == "windows":
        task = "ToolShedDashboardSafety-" + suffix
        subprocess_launch.run(["schtasks", "/Delete", "/F", "/TN", task], check=False)
        removed.append(task)
    else:
        raise DashboardReporterError(f"dashboard scheduling is unsupported on {system}")
    return {"schema_version": SCHEMA_VERSION, "kind": "tool-shed-dashboard-scheduler", "status": "removed", "platform": system, "targets": removed, "writes_performed": bool(removed)}


def safety_pass(workspace: Path, *, project_binding: str) -> dict[str, Any]:
    require_project_binding(workspace, project_binding, operation="dashboard-report")
    audit = document_store.audit(workspace)
    queued: dict[str, Any] | None = None
    with contextlib.closing(_outbox(workspace)) as connection:
        previous = _meta(connection, "last_domain_digest")
        current = str(audit["domain_digest"])
        pending = int(
            connection.execute(
                "SELECT COUNT(*) FROM outbox WHERE delivered_at IS NULL"
            ).fetchone()[0]
        )
    if previous != current:
        queued = enqueue(
            workspace,
            project_binding=project_binding,
            reason="safety-convergence",
        )
        with contextlib.closing(_outbox(workspace)) as connection:
            _set_meta(connection, "last_domain_digest", current)
    elif pending == 0:
        queued = enqueue(
            workspace,
            project_binding=project_binding,
            reason="heartbeat",
        )

    delivered_count = 0
    superseded_count = 0
    final_status = "idle"
    for _ in range(SAFETY_DRAIN_LIMIT):
        delivered = worker_once(workspace)
        final_status = str(delivered["status"])
        if final_status == "delivered":
            delivered_count += 1
            continue
        if final_status == "superseded":
            superseded_count += 1
            continue
        break
    with contextlib.closing(_outbox(workspace)) as connection:
        pending = int(
            connection.execute(
                "SELECT COUNT(*) FROM outbox WHERE delivered_at IS NULL"
            ).fetchone()[0]
        )
    if pending == 0 and (delivered_count or superseded_count):
        final_status = "delivered"
    elif pending:
        final_status = "pending" if final_status == "idle" else final_status
    result = {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-dashboard-safety-pass",
        "status": final_status,
        "delivered_count": delivered_count,
        "superseded_count": superseded_count,
        "pending_events": pending,
        "writes_performed": bool(queued or delivered_count or superseded_count),
    }
    if queued:
        result["sequence"] = queued["sequence"]
    return result


def status(workspace: Path) -> dict[str, Any]:
    state = load_connection(workspace, required=False)
    pending = 0
    path = outbox_path(workspace)
    if path.is_file():
        with contextlib.closing(_outbox(workspace)) as connection:
            pending = int(connection.execute("SELECT COUNT(*) FROM outbox WHERE delivered_at IS NULL").fetchone()[0])
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-dashboard-reporter-status",
        "connection": "absent" if state is None else state["status"],
        "server": None if state is None else state.get("server"),
        "instance_id": None if state is None else state.get("instance_id"),
        "pending_events": pending,
        "credential_present": bool(state and state.get("reporter_token")),
        "writes_performed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    connect_parser = commands.add_parser("connect")
    connect_parser.add_argument("--server", required=True)
    connect_parser.add_argument("--project-binding", required=True)
    poll_parser = commands.add_parser("connect-poll")
    poll_parser.add_argument("--project-binding", required=True)
    disconnect_parser = commands.add_parser("disconnect")
    disconnect_parser.add_argument("--project-binding", required=True)
    enqueue_parser = commands.add_parser("enqueue")
    enqueue_parser.add_argument("--project-binding", required=True)
    enqueue_parser.add_argument("--reason", default="managed-update")
    commands.add_parser("worker-once")
    worker_parser = commands.add_parser("worker")
    worker_parser.add_argument("--project-binding", required=True)
    worker_parser.add_argument("--max-cycles", type=int)
    worker_parser.add_argument("--launch-claim")
    commands.add_parser("scheduler-plan")
    install_parser = commands.add_parser("scheduler-install")
    install_parser.add_argument("--project-binding", required=True)
    remove_parser = commands.add_parser("scheduler-remove")
    remove_parser.add_argument("--project-binding", required=True)
    safety_parser = commands.add_parser("safety-pass")
    safety_parser.add_argument("--project-binding", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        background = args.command in {"worker-once", "worker", "safety-pass"}
        execution_context = (
            subprocess_launch.windowless_subprocesses()
            if background
            else contextlib.nullcontext()
        )
        with execution_context:
            workspace = resolved_workspace(Path(args.workspace))
            if args.command == "status":
                result = status(workspace)
            elif args.command == "connect":
                result = connect(workspace, server=args.server, project_binding=args.project_binding)
            elif args.command == "connect-poll":
                result = connect_poll(workspace, project_binding=args.project_binding)
            elif args.command == "disconnect":
                result = disconnect(workspace, project_binding=args.project_binding)
            elif args.command == "enqueue":
                result = enqueue(workspace, project_binding=args.project_binding, reason=args.reason)
            elif args.command == "worker-once":
                result = worker_once(workspace)
            elif args.command == "worker":
                result = worker(
                    workspace,
                    project_binding=args.project_binding,
                    max_cycles=args.max_cycles,
                    launch_claim=args.launch_claim,
                )
            elif args.command == "scheduler-plan":
                result = scheduler_plan(workspace)
            elif args.command == "scheduler-install":
                result = scheduler_install(workspace, project_binding=args.project_binding)
            elif args.command == "scheduler-remove":
                result = scheduler_remove(workspace, project_binding=args.project_binding)
            else:
                result = safety_pass(workspace, project_binding=args.project_binding)
        if sys.stdout is not None:
            print(json.dumps(result, indent=2, sort_keys=True), file=sys.stdout)
        return 0
    except (
        DashboardReporterError,
        ProjectIdentityError,
        app_server_user_state.AppServerUserStateError,
        OSError,
        ValueError,
        sqlite3.DatabaseError,
        subprocess.CalledProcessError,
    ) as error:
        payload = {"schema_version": SCHEMA_VERSION, "kind": "tool-shed-dashboard-reporter-error", "error": str(error), "writes_performed": False}
        if sys.stderr is not None:
            print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
