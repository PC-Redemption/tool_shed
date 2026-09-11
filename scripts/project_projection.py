#!/usr/bin/env python3
"""Build one authority-aware projection of the complete local project world."""

from __future__ import annotations

import contextlib
import json
import re
from pathlib import Path
from typing import Any

import authority_resolver
import campaign_queue
import hybrid_state
import loop_findings
import planning_order
import update_work_index


SCHEMA_VERSION = 1


class ProjectProjectionError(RuntimeError):
    pass


def _summary(workspace: Path, authority: dict[str, Any]) -> dict[str, Any]:
    if authority["authority"] == "file":
        work = workspace / "work"
        artifacts = update_work_index.discover_artifacts(work) if work.is_dir() else []
        ideas = [item for item in artifacts if item.kind() == "idea-brief" and item.is_active()]
        campaigns = list(campaign_queue.load_all(workspace).values())
        active = [item for item in campaigns if item.status not in {"complete", "completed", "abandoned", "deferred"}]
        return {
            "working_count": sum(item.status == "working" for item in active),
            "ready_count": sum(item.status in {"queued", "ready"} for item in active),
            "queued_count": sum(item.status in {"queued", "ready"} for item in active),
            "blocked_count": sum(item.status == "blocked" for item in active),
            "closure_debt_count": 0,
            "active_idea_count": len(ideas),
            "open_outcome_count": 0,
            "unreconciled_outcome_count": 0,
            "active_loop_finding_count": 0,
            "last_completed_id": next(
                (item.campaign_id for item in campaigns if item.status in {"complete", "completed"}),
                None,
            ),
        }
    if authority["authority"] != "sqlite":
        raise ProjectProjectionError(authority["reason"])
    with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)) as connection:
        has_documents = bool(connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='document'"
        ).fetchone())
        has_closure = bool(connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='closure_rollup'"
        ).fetchone())
        campaign_rows = connection.execute(
            "SELECT d.lifecycle_state, r.body_markdown FROM document d JOIN artifact a ON a.id=d.id "
            "JOIN document_revision r ON r.document_id=d.id AND r.revision_number=d.current_revision "
            "WHERE a.type='campaign' AND d.lifecycle_state IN ('active','working','blocked')"
        ).fetchall() if has_documents else []
        active_idea_count = int(connection.execute(
            "SELECT COUNT(*) FROM document WHERE namespace='IDEA' AND lifecycle_state='active'"
        ).fetchone()[0]) if has_documents else 0
        last_completed = connection.execute(
            "SELECT visible_id FROM document WHERE namespace='CAMP' AND lifecycle_state='completed' "
            "ORDER BY visible_id DESC LIMIT 1"
        ).fetchone() if has_documents else None
        work_states = [loop_findings._body_status(str(row["body_markdown"])) for row in campaign_rows]
        blocked_campaigns = sum(
            str(row["lifecycle_state"]) == "blocked" or state == "blocked"
            for row, state in zip(campaign_rows, work_states)
        )
        queued_campaigns = sum(state in {"queued", "ready"} for state in work_states)
        working_campaigns = len(campaign_rows) - blocked_campaigns - queued_campaigns
        open_outcomes = int(connection.execute("SELECT COUNT(*) FROM cycle WHERE lifecycle_state <> 'terminal'").fetchone()[0])
        unreconciled = int(
            connection.execute(
                "SELECT COUNT(*) FROM cycle AS c WHERE COALESCE((SELECT r.state FROM reconciliation AS r "
                "WHERE r.cycle_id = c.id ORDER BY r.compared_at DESC, r.id DESC LIMIT 1), 'open') = 'reconciliation-required' "
                "OR (c.lifecycle_state = 'terminal' AND COALESCE((SELECT r.state FROM reconciliation AS r "
                "WHERE r.cycle_id = c.id ORDER BY r.compared_at DESC, r.id DESC LIMIT 1), 'open') <> 'reconciled')"
            ).fetchone()[0]
        )
        closure_debt = int(connection.execute(
            "SELECT COUNT(*) FROM document d JOIN cycle c ON c.origin_artifact_id=d.id "
            "WHERE c.lifecycle_state='terminal' AND c.id=(SELECT newer.id FROM cycle newer "
            "WHERE newer.origin_artifact_id=d.id ORDER BY newer.opened_at DESC, newer.id DESC LIMIT 1) "
            "AND 'reconciled'=(SELECT r.state FROM reconciliation r WHERE r.cycle_id=c.id "
            "ORDER BY r.compared_at DESC, r.id DESC LIMIT 1) AND COALESCE((SELECT cr.effective_closed "
            "FROM closure_element ce JOIN closure_rollup cr ON cr.element_id=ce.id "
            "WHERE ce.cycle_id=c.id AND ce.role='cycle' "
            "ORDER BY ce.subject_revision DESC, ce.id LIMIT 1), 0)=0"
        ).fetchone()[0]) if has_documents and has_closure else 0
    finding_count = loop_findings.report_projection(workspace)["total_active_count"]
    return {
        "working_count": working_campaigns,
        "ready_count": queued_campaigns,
        "queued_count": queued_campaigns,
        "blocked_count": blocked_campaigns,
        "closure_debt_count": closure_debt,
        "active_idea_count": active_idea_count,
        "open_outcome_count": open_outcomes,
        "unreconciled_outcome_count": unreconciled,
        "active_loop_finding_count": finding_count,
        "last_completed_id": str(last_completed["visible_id"]) if last_completed else None,
    }


def _inventory(workspace: Path, authority: dict[str, Any]) -> dict[str, Any]:
    """Build a bounded, privacy-safe lifecycle projection from canonical state."""
    if authority["authority"] == "file":
        work = workspace / "work"
        discovered = update_work_index.discover_artifacts(work) if work.is_dir() else []
        allowed = {"idea-brief": "IDEA", "project-map": "MAP", "program-roadmap": "PRM", "campaign": "CAMP"}
        selected = [item for item in discovered if item.kind() in allowed]
        planning_items = {
            item["path"]: item
            for artifact_type in ("idea-brief", "program-roadmap")
            for item in planning_order.file_projection(workspace, artifact_type, authority=authority)["items"]
        }
        artifacts = []
        for item in selected[:500]:
            relative = item.path.as_posix()
            artifact_type = item.kind()
            namespace = allowed[artifact_type]
            match = re.search(rf"\b{namespace}-\d{{4,}}\b", item.title + " " + relative, re.I)
            visible_id = match.group(0).upper() if match else relative
            planning = planning_items.get(relative)
            status_value = item.status().casefold() or "unknown"
            terminal = status_value in {"complete", "completed", "abandoned", "superseded", "terminal"}
            document_lifecycle = (
                "completed" if status_value == "complete" else status_value
                if status_value in {
                    "active", "working", "blocked", "parked", "deferred", "completed",
                    "abandoned", "superseded", "terminal",
                }
                else "active"
            )
            updated_at = item.fields.get("Updated", "")
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated_at):
                updated_at += "T00:00:00Z"
            elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", updated_at):
                updated_at = "1970-01-01T00:00:00Z"
            parent = item.fields.get("Parent") or item.fields.get("Project Map") or item.fields.get("Source Project Map")
            produces = [value.strip() for value in item.fields.get("Produces", "").split(",") if value.strip()]
            artifacts.append(
                {
                    "artifact_id": authority_resolver.file_artifact_id(workspace, relative),
                    "visible_id": visible_id,
                    "artifact_type": artifact_type,
                    "title": " ".join(item.title.split())[:160] or visible_id,
                    "document_lifecycle": document_lifecycle,
                    "outcome_lifecycle": "unknown",
                    "outcome_disposition": "unknown",
                    "reconciliation_state": "unknown",
                    "terminal_reason": None,
                    "parent_ids": [parent] if parent else [],
                    "produces_ids": produces[:16],
                    "planning_position": planning["position"] if planning else None,
                    "planning_order_source": planning["order_source"] if planning else "derived",
                    "planning_readiness": (
                        planning["readiness"] if planning else "terminal" if terminal else
                        "blocked" if status_value == "blocked" else
                        "working" if status_value == "working" else
                        "waiting" if status_value in {"deferred", "parked"} else "ready"
                    ),
                    "closure_status": {
                        "local_closure": "unknown",
                        "evidence_health": "unknown",
                        "graph_health": "unknown",
                        "effective_closed": False,
                        "reason_codes": ["HYBRID_OUTCOME_UNAVAILABLE"],
                        "counts": {"open": 0, "unknown": 1, "invalid": 0},
                        "blockers": [],
                        "subject_revision": 0,
                        "graph_revision": 0,
                        "evaluator_version": "not-available",
                        "evaluated_at": updated_at,
                    },
                    "updated_at": updated_at,
                }
            )
        return {"total_count": len(selected), "truncated": len(selected) > len(artifacts), "artifacts": artifacts}
    if authority["authority"] != "sqlite":
        raise ProjectProjectionError(authority["reason"])
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
                   dr.body_markdown,
                   COALESCE((
                       SELECT c.lifecycle_state FROM cycle AS c
                       WHERE c.origin_artifact_id = d.id
                       ORDER BY c.opened_at DESC, c.id DESC LIMIT 1
                   ), 'unknown') AS outcome_lifecycle,
                   COALESCE((
                       SELECT v.disposition FROM outcome_verdict AS v
                       JOIN cycle AS c ON c.id = v.cycle_id
                       WHERE c.origin_artifact_id = d.id
                       ORDER BY c.opened_at DESC, v.decided_revision DESC, v.id DESC LIMIT 1
                   ), CASE WHEN EXISTS (
                       SELECT 1 FROM cycle AS c WHERE c.origin_artifact_id = d.id
                   ) THEN 'open' ELSE 'unknown' END) AS outcome_disposition,
                   COALESCE((
                       SELECT r.state FROM reconciliation AS r
                       JOIN cycle AS c ON c.id = r.cycle_id
                       WHERE c.origin_artifact_id = d.id
                       ORDER BY c.opened_at DESC, r.origin_revision DESC, r.id DESC LIMIT 1
                   ), CASE WHEN EXISTS (
                       SELECT 1 FROM cycle AS c WHERE c.origin_artifact_id = d.id
                   ) THEN 'open' ELSE 'unknown' END) AS reconciliation_state
            FROM document AS d
            JOIN document_revision AS dr
              ON dr.document_id = d.id AND dr.revision_number = d.current_revision
            WHERE d.namespace IN ('IDEA','MAP','PRM','CAMP')
            ORDER BY d.visible_id
            LIMIT 500
            """
        ).fetchall()
        terminal_reasons: dict[str, str] = {}
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='campaign_reconciliation_audit'"
        ).fetchone():
            terminal_reasons = {
                str(row["artifact_id"]): str(row["reason"])[:240]
                for row in connection.execute(
                    "SELECT c.origin_artifact_id AS artifact_id, cra.reason FROM campaign_reconciliation_audit cra "
                    "JOIN cycle c ON c.id=cra.cycle_id WHERE cra.recorded_revision=("
                    "SELECT MAX(newer.recorded_revision) FROM campaign_reconciliation_audit newer "
                    "WHERE newer.cycle_id=cra.cycle_id) ORDER BY c.origin_artifact_id"
                )
            }
        try:
            planning_items = {
                item["artifact_id"]: item
                for artifact_type in ("idea-brief", "program-roadmap")
                for item in planning_order.projection_for_connection(connection, artifact_type)["items"]
            }
        except planning_order.PlanningOrderError as error:
            raise ProjectProjectionError(f"local planning order is invalid: {error}") from error
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
                closure_by_artifact[artifact_id] = {
                    "_element_id": str(closure["element_id"]),
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
                    "blockers": [],
                    "subject_revision": int(closure["subject_revision"]),
                    "graph_revision": int(closure["graph_revision"]),
                    "evaluator_version": str(closure["evaluator_version"]),
                    "evaluated_at": str(closure["evaluated_at"]),
                }
            element_to_closure = {
                str(value["_element_id"]): value for value in closure_by_artifact.values()
            }
            if element_to_closure:
                blocker_placeholders = ",".join("?" for _ in element_to_closure)
                for item in connection.execute(
                    f"SELECT ancestor_element_id, blocking_element_id, "
                    f"blocking_obligation_id, reason_code, depth FROM closure_blocker "
                    f"WHERE ancestor_element_id IN ({blocker_placeholders}) "
                    f"ORDER BY ancestor_element_id, depth, reason_code, id",
                    tuple(element_to_closure),
                ):
                    projected = element_to_closure[str(item["ancestor_element_id"])]["blockers"]
                    if len(projected) < 20:
                        projected.append(
                            {
                                "blocking_element_id": item["blocking_element_id"],
                                "blocking_obligation_id": item["blocking_obligation_id"],
                                "reason_code": item["reason_code"],
                                "depth": int(item["depth"]),
                            }
                        )
            for value in closure_by_artifact.values():
                value.pop("_element_id")
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
        campaign_readiness = (
            loop_findings._body_status(str(row["body_markdown"]))
            if artifact_type == "campaign"
            else None
        )
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
                "terminal_reason": terminal_reasons.get(artifact_id),
                "parent_ids": sorted(set(parent_ids[artifact_id]))[:16],
                "produces_ids": sorted(set(produces_ids[artifact_id]))[:16],
                "planning_position": planning["position"] if planning else None,
                "planning_order_source": (
                    planning["order_source"]
                    if planning
                    else "derived"
                    if artifact_type in planning_order.SUPPORTED_TYPES or artifact_type == "campaign"
                    else "not-applicable"
                ),
                "planning_readiness": (
                    planning["readiness"]
                    if planning
                    else "terminal"
                    if artifact_type == "campaign" and str(row["lifecycle_state"]) in planning_order.TERMINAL_DOCUMENT_STATES
                    else campaign_readiness
                    if campaign_readiness in planning_order.READINESS_RANK
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

def build(workspace: Path) -> dict[str, Any]:
    """Return executive summary and exhaustive ledger from one authority decision."""
    authority = authority_resolver.resolve(workspace)
    if authority["authority"] not in {"file", "sqlite"}:
        raise ProjectProjectionError(authority["reason"])
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-project-projection",
        "authority": {
            "state": authority["state"],
            "authority": authority["authority"],
            "feature_limits": list(authority.get("feature_limits", [])),
        },
        "state": _summary(workspace, authority),
        "work_inventory": _inventory(workspace, authority),
        "writes_performed": False,
    }
