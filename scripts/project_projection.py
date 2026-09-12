#!/usr/bin/env python3
"""Build one authority-aware projection of the complete local project world."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import contextlib
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

import authority_resolver
import campaign_queue
import hybrid_state
import loop_findings
import planning_order
import update_work_index


SCHEMA_VERSION = 2
EXECUTIVE_SCHEMA_VERSION = 4
EXECUTIVE_RELATIVE = Path("work/100k.md")
EXECUTIVE_MARKER = "<!-- GENERATED: TOOL-SHED-PROJECT-EXECUTIVE-VIEW-V4; DO NOT EDIT -->"
LEGACY_EXECUTIVE_MARKERS = (
    "<!-- GENERATED: TOOL-SHED-PROJECT-EXECUTIVE-VIEW-V3; DO NOT EDIT -->",
    "<!-- GENERATED: TOOL-SHED-PROJECT-EXECUTIVE-VIEW-V2; DO NOT EDIT -->",
    "<!-- GENERATED: TOOL-SHED-PROJECT-EXECUTIVE-VIEW-V1; DO NOT EDIT -->",
)
EXECUTIVE_INTENT_RELATIVE = Path("work/project-executive-intent.md")
EXECUTIVE_INTENT_ROLE = "project-executive-intent-v1"
EXECUTIVE_DIRECTIVE_ROLE = "project-executive-directive-v1"
EXECUTIVE_DIRECTIVE_LIMIT = 50
EXECUTIVE_RECENT_COMPLETED_LIMIT = 8
EXECUTIVE_INTENT_SECTIONS = (
    ("north_star", "North Star"),
    ("completion_horizon", "Current Completion Horizon"),
    ("strategic_context", "Strategic Context"),
    ("priorities", "Current Priorities"),
    ("non_goals", "Deliberate Non-Goals"),
    ("decisions_needed", "Decisions Needed"),
    ("review_triggers", "Review Triggers"),
)
TYPE_BY_NAMESPACE = {"IDEA": "idea-brief", "MAP": "project-map", "PRM": "program-roadmap", "CAMP": "campaign"}
NAMESPACE_BY_TYPE = {value: key for key, value in TYPE_BY_NAMESPACE.items()}


class ProjectProjectionError(RuntimeError):
    pass


def _unknown_closure(reason: str, evaluated_at: str) -> dict[str, Any]:
    return {
        "local_closure": "unknown", "evidence_health": "unknown", "graph_health": "unknown",
        "effective_closed": False,
        "reason_codes": [reason],
        "counts": {"open": 0, "unknown": 1, "invalid": 0},
        "blockers": [], "subject_revision": 0, "graph_revision": 0,
        "evaluator_version": "not-available", "evaluated_at": evaluated_at,
    }


def _state(
    campaigns: list[tuple[str, str]],
    *,
    closure_debt: int = 0,
    active_ideas: int = 0,
    open_outcomes: int = 0,
    unreconciled: int = 0,
    active_findings: int = 0,
    last_completed: str | None = None,
) -> dict[str, Any]:
    blocked = sum(lifecycle == "blocked" or status == "blocked" for lifecycle, status in campaigns)
    queued = sum(status in {"queued", "ready"} for _, status in campaigns)
    return {
        "working_count": len(campaigns) - blocked - queued,
        "ready_count": queued, "queued_count": queued, "blocked_count": blocked,
        "closure_debt_count": closure_debt, "active_idea_count": active_ideas,
        "open_outcome_count": open_outcomes, "unreconciled_outcome_count": unreconciled,
        "active_loop_finding_count": active_findings, "last_completed_id": last_completed,
    }


def _file_summary(workspace: Path) -> dict[str, Any]:
    work = workspace / "work"
    artifacts = update_work_index.discover_artifacts(work) if work.is_dir() else []
    all_campaigns = list(campaign_queue.load_all(workspace).values())
    active = [
        item for item in all_campaigns
        if item.status not in {"complete", "completed", "abandoned", "deferred"}
    ]
    return _state(
        [(item.status, item.status) for item in active],
        active_ideas=sum(item.kind() == "idea-brief" and item.is_active() for item in artifacts),
        last_completed=next(
            (item.campaign_id for item in all_campaigns if item.status in {"complete", "completed"}), None
        ),
    )


def _sqlite_summary(connection: Any, active_findings: int) -> dict[str, Any]:
    rows = connection.execute(
        "SELECT d.lifecycle_state, r.body_markdown FROM document d JOIN artifact a ON a.id=d.id "
        "JOIN document_revision r ON r.document_id=d.id AND r.revision_number=d.current_revision "
        "WHERE a.type='campaign' AND d.lifecycle_state IN ('active','working','blocked')"
    ).fetchall()
    counts = connection.execute(
        "SELECT (SELECT COUNT(*) FROM document WHERE namespace='IDEA' AND lifecycle_state='active'), "
        "(SELECT COUNT(*) FROM cycle WHERE lifecycle_state <> 'terminal'), "
        "(SELECT COUNT(*) FROM cycle c WHERE COALESCE((SELECT r.state FROM reconciliation r WHERE "
        "r.cycle_id=c.id ORDER BY r.compared_at DESC,r.id DESC LIMIT 1),'open')='reconciliation-required' "
        "OR (c.lifecycle_state='terminal' AND COALESCE((SELECT r.state FROM reconciliation r WHERE "
        "r.cycle_id=c.id ORDER BY r.compared_at DESC,r.id DESC LIMIT 1),'open')<>'reconciled')), "
        "(SELECT visible_id FROM document WHERE namespace='CAMP' AND lifecycle_state='completed' "
        "ORDER BY visible_id DESC LIMIT 1)"
    ).fetchone()
    has_closure = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='closure_rollup'"
    ).fetchone()
    closure_debt = int(connection.execute(
        "SELECT COUNT(*) FROM document d JOIN cycle c ON c.origin_artifact_id=d.id "
        "WHERE c.lifecycle_state='terminal' AND c.id=(SELECT newer.id FROM cycle newer WHERE "
        "newer.origin_artifact_id=d.id ORDER BY newer.opened_at DESC,newer.id DESC LIMIT 1) AND "
        "'reconciled'=(SELECT r.state FROM reconciliation r WHERE r.cycle_id=c.id ORDER BY "
        "r.compared_at DESC,r.id DESC LIMIT 1) AND COALESCE((SELECT cr.effective_closed FROM "
        "closure_element ce JOIN closure_rollup cr ON cr.element_id=ce.id WHERE ce.cycle_id=c.id "
        "AND ce.role='cycle' ORDER BY ce.subject_revision DESC,ce.id LIMIT 1),0)=0"
    ).fetchone()[0]) if has_closure else 0
    campaigns = [(str(row["lifecycle_state"]), loop_findings._body_status(str(row["body_markdown"]))) for row in rows]
    return _state(
        campaigns, closure_debt=closure_debt, active_ideas=int(counts[0]),
        open_outcomes=int(counts[1]), unreconciled=int(counts[2]),
        active_findings=active_findings, last_completed=str(counts[3]) if counts[3] else None,
    )


def _inventory(workspace: Path, authority: dict[str, Any]) -> dict[str, Any]:
    """Build a bounded, privacy-safe lifecycle projection from canonical state."""
    if authority["authority"] == "file":
        work = workspace / "work"
        discovered = update_work_index.discover_artifacts(work) if work.is_dir() else []
        selected = [item for item in discovered if item.kind() in NAMESPACE_BY_TYPE]
        planning_items = {
            item["path"]: item
            for artifact_type in ("idea-brief", "program-roadmap")
            for item in planning_order.file_projection(workspace, artifact_type, authority=authority)["items"]
        }
        artifacts = []
        for item in selected[:500]:
            relative = item.path.as_posix()
            artifact_type = item.kind()
            namespace = NAMESPACE_BY_TYPE[artifact_type]
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
                    "visible_id": visible_id, "artifact_type": artifact_type,
                    "title": " ".join(item.title.split())[:160] or visible_id,
                    "metadata_role": item.fields.get("Role"),
                    "metadata_directive_text": item.fields.get("Directive Text"),
                    "document_lifecycle": document_lifecycle,
                    "outcome_lifecycle": "unknown", "outcome_disposition": "unknown",
                    "reconciliation_state": "unknown", "terminal_reason": None,
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
                    "closure_status": _unknown_closure("HYBRID_OUTCOME_UNAVAILABLE", updated_at), "updated_at": updated_at,
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
                   d.metadata_json, dr.body_markdown,
                   COALESCE((SELECT c.lifecycle_state FROM cycle c WHERE c.origin_artifact_id=d.id
                       ORDER BY c.opened_at DESC,c.id DESC LIMIT 1), 'unknown') AS outcome_lifecycle,
                   COALESCE((SELECT v.disposition FROM outcome_verdict v JOIN cycle c ON c.id=v.cycle_id
                       WHERE c.origin_artifact_id=d.id ORDER BY c.opened_at DESC,v.decided_revision DESC,v.id DESC LIMIT 1),
                       CASE WHEN EXISTS (SELECT 1 FROM cycle c WHERE c.origin_artifact_id=d.id)
                       THEN 'open' ELSE 'unknown' END) AS outcome_disposition,
                   COALESCE((SELECT r.state FROM reconciliation r JOIN cycle c ON c.id=r.cycle_id
                       WHERE c.origin_artifact_id=d.id ORDER BY c.opened_at DESC,r.origin_revision DESC,r.id DESC LIMIT 1),
                       CASE WHEN EXISTS (SELECT 1 FROM cycle c WHERE c.origin_artifact_id=d.id)
                       THEN 'open' ELSE 'unknown' END) AS reconciliation_state
            FROM document AS d
            JOIN document_revision AS dr
              ON dr.document_id = d.id AND dr.revision_number = d.current_revision
            WHERE d.namespace IN ('IDEA','MAP','PRM','CAMP')
            ORDER BY d.visible_id
            LIMIT 500
            """
        ).fetchall()
        terminal_reasons = {}
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='campaign_reconciliation_audit'").fetchone():
            reason_rows = connection.execute(
                "SELECT c.origin_artifact_id AS artifact_id, cra.reason FROM campaign_reconciliation_audit cra "
                "JOIN cycle c ON c.id=cra.cycle_id WHERE cra.recorded_revision=(SELECT MAX(newer.recorded_revision) "
                "FROM campaign_reconciliation_audit newer WHERE newer.cycle_id=cra.cycle_id) ORDER BY c.origin_artifact_id"
            )
            terminal_reasons = {str(row["artifact_id"]): str(row["reason"])[:240] for row in reason_rows}
        try:
            planning_items = {item["artifact_id"]: item
                              for artifact_type in ("idea-brief", "program-roadmap")
                              for item in planning_order.projection_for_connection(connection, artifact_type)["items"]}
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
            related_ids = {str(value) for relation in relations
                           for value in (relation["from_artifact_id"], relation["to_artifact_id"])
                           if str(value) not in visible_by_id}
            if related_ids:
                related_placeholders = ",".join("?" for _ in related_ids)
                for related in connection.execute(
                    f"SELECT id, visible_id FROM document WHERE id IN ({related_placeholders})", tuple(sorted(related_ids))
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
                    "local_closure": str(closure["local_closure"]), "evidence_health": str(closure["evidence_health"]),
                    "graph_health": str(closure["graph_health"]),
                    "effective_closed": bool(closure["effective_closed"]),
                    "reason_codes": json.loads(closure["reason_codes_json"]),
                    "counts": {
                        "open": int(closure["open_descendants"]), "unknown": int(closure["unknown_descendants"]),
                        "invalid": int(closure["invalid_descendants"]),
                    },
                    "blockers": [], "subject_revision": int(closure["subject_revision"]),
                    "graph_revision": int(closure["graph_revision"]), "evaluator_version": str(closure["evaluator_version"]),
                    "evaluated_at": str(closure["evaluated_at"]),
                }
            element_to_closure = {str(value["_element_id"]): value for value in closure_by_artifact.values()}
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
                        projected.append({
                            "blocking_element_id": item["blocking_element_id"],
                            "blocking_obligation_id": item["blocking_obligation_id"],
                            "reason_code": item["reason_code"], "depth": int(item["depth"]),
                        })
            for value in closure_by_artifact.values():
                value.pop("_element_id")
    artifacts = []
    for row in rows:
        artifact_id = str(row["id"])
        artifact_type = TYPE_BY_NAMESPACE[str(row["namespace"])]
        metadata = json.loads(str(row["metadata_json"]))
        planning = planning_items.get(artifact_id)
        campaign_readiness = loop_findings._body_status(str(row["body_markdown"])) if artifact_type == "campaign" else None
        title = " ".join(str(row["title"]).split())[:160] or str(row["visible_id"])
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "visible_id": str(row["visible_id"]), "artifact_type": artifact_type, "title": title,
                "metadata_role": metadata.get("role"),
                "metadata_directive_text": metadata.get("directive_text"),
                "document_lifecycle": str(row["lifecycle_state"]),
                "outcome_lifecycle": str(row["outcome_lifecycle"]), "outcome_disposition": str(row["outcome_disposition"]),
                "reconciliation_state": str(row["reconciliation_state"]),
                "terminal_reason": terminal_reasons.get(artifact_id),
                "parent_ids": sorted(set(parent_ids[artifact_id]))[:16], "produces_ids": sorted(set(produces_ids[artifact_id]))[:16],
                "planning_position": planning["position"] if planning else None,
                "planning_order_source": planning["order_source"] if planning else (
                    "derived" if artifact_type in planning_order.SUPPORTED_TYPES or artifact_type == "campaign" else "not-applicable"
                ),
                "planning_readiness": (
                    planning["readiness"] if planning else "terminal"
                    if (artifact_type == "campaign" and str(row["lifecycle_state"]) in planning_order.TERMINAL_DOCUMENT_STATES)
                    or artifact_type in planning_order.SUPPORTED_TYPES
                    else campaign_readiness if campaign_readiness in planning_order.READINESS_RANK else "not-applicable"
                ),
                "closure_status": closure_by_artifact.get(
                    artifact_id, _unknown_closure("CLOSURE_NOT_AVAILABLE", str(row["updated_at"]))
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
    loop_projection = loop_findings.report_projection(workspace)
    if authority["authority"] == "file":
        state = _file_summary(workspace)
    else:
        with contextlib.closing(
            hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)
        ) as connection:
            state = _sqlite_summary(connection, loop_projection["total_active_count"])
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-project-projection",
        "authority": {
            "state": authority["state"],
            "authority": authority["authority"],
            "feature_limits": list(authority.get("feature_limits", [])),
        },
        "state": state,
        "work_inventory": _inventory(workspace, authority),
        "loop_findings": loop_projection,
        "writes_performed": False,
    }


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _markdown_headers(body: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for raw in body.splitlines()[:80]:
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip()] = value.strip()
    return headers


def _markdown_sections(body: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in body.splitlines():
        if raw.startswith("## "):
            current = raw[3:].strip()
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(raw)
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def _section_items(value: str) -> list[str]:
    return [
        line[2:].strip()
        for line in value.splitlines()
        if line.startswith("- ") and line[2:].strip()
    ]


def _parse_executive_intent(
    body: str,
    *,
    identity: str,
    revision: int | None,
    updated_at: str | None,
) -> dict[str, Any]:
    sections = _markdown_sections(body)
    scalar_sections = {
        "north_star": "North Star",
        "completion_horizon": "Current Completion Horizon",
        "strategic_context": "Strategic Context",
    }
    list_sections = {
        "priorities": "Current Priorities",
        "non_goals": "Deliberate Non-Goals",
        "decisions_needed": "Decisions Needed",
        "review_triggers": "Review Triggers",
    }
    result: dict[str, Any] = {
        "state": "current",
        "identity": identity,
        "revision": revision,
        "updated_at": updated_at,
    }
    missing: list[str] = []
    for key, heading in scalar_sections.items():
        value = sections.get(heading, "").strip()
        result[key] = value or None
        if not value:
            missing.append(heading)
    for key, heading in list_sections.items():
        value = _section_items(sections.get(heading, ""))
        result[key] = value
        if not value:
            missing.append(heading)
    result["missing_sections"] = missing
    if missing:
        result["state"] = "incomplete"
    return result


def _missing_executive_intent() -> dict[str, Any]:
    return {
        "state": "missing", "identity": None, "revision": None,
        "updated_at": None, "north_star": None, "completion_horizon": None,
        "strategic_context": None, "priorities": [], "non_goals": [],
        "decisions_needed": [], "review_triggers": [],
        "missing_sections": [heading for _, heading in EXECUTIVE_INTENT_SECTIONS],
    }


def _executive_intent(workspace: Path, authority: dict[str, Any]) -> dict[str, Any]:
    """Read the one narrowly authoritative project executive-intent document."""
    if authority["authority"] == "sqlite":
        with contextlib.closing(
            hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)
        ) as connection:
            rows = connection.execute(
                "SELECT d.visible_id,d.current_revision,d.updated_at,d.metadata_json,r.body_markdown "
                "FROM document d JOIN artifact a ON a.id=d.id JOIN document_revision r ON "
                "r.document_id=d.id AND r.revision_number=d.current_revision WHERE a.type='decision' "
                "AND d.lifecycle_state IN ('active','working') ORDER BY d.visible_id"
            ).fetchall()
        matches = []
        for row in rows:
            metadata = json.loads(str(row["metadata_json"]))
            if metadata.get("role") == EXECUTIVE_INTENT_ROLE:
                matches.append(row)
        if len(matches) > 1:
            identities = ", ".join(str(row["visible_id"]) for row in matches)
            raise ProjectProjectionError(
                f"multiple active project executive-intent documents: {identities}"
            )
        if not matches:
            return _missing_executive_intent()
        selected = matches[0]
        return _parse_executive_intent(
            str(selected["body_markdown"]),
            identity=str(selected["visible_id"]),
            revision=int(selected["current_revision"]),
            updated_at=str(selected["updated_at"]),
        )

    path = workspace / EXECUTIVE_INTENT_RELATIVE
    if not path.is_file():
        return _missing_executive_intent()
    body = path.read_text(encoding="utf-8")
    headers = _markdown_headers(body)
    if headers.get("Type") != "decision" or headers.get("Role") != EXECUTIVE_INTENT_ROLE:
        raise ProjectProjectionError(
            f"{EXECUTIVE_INTENT_RELATIVE.as_posix()} must declare Type: decision and "
            f"Role: {EXECUTIVE_INTENT_ROLE}"
        )
    return _parse_executive_intent(
        body,
        identity=EXECUTIVE_INTENT_RELATIVE.as_posix(),
        revision=None,
        updated_at=headers.get("Updated"),
    )


def _focus_coverage(
    workspace: Path, authority: dict[str, Any], artifacts: list[dict[str, Any]]
) -> dict[str, Any]:
    """Project approved focus areas onto active campaigns without changing dashboard fields."""
    catalog = campaign_queue.load_focus_area_catalog(workspace)
    approved = catalog is not None and catalog.status == "approved"
    names = {key: value.name for key, value in catalog.areas.items()} if approved and catalog else {}
    assignments: dict[str, list[str]] = {}
    decisions_needed: list[dict[str, str]] = []
    if authority["authority"] == "sqlite":
        with contextlib.closing(
            hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)
        ) as connection:
            rows = connection.execute(
                "SELECT d.visible_id,d.metadata_json,r.body_markdown FROM document d "
                "JOIN document_revision r ON r.document_id=d.id AND r.revision_number=d.current_revision "
                "WHERE d.namespace='CAMP' AND d.lifecycle_state IN ('active','working','blocked')"
            ).fetchall()
        for row in rows:
            metadata = json.loads(str(row["metadata_json"]))
            values = [
                *metadata.get("primary_focus_areas", []),
                *metadata.get("supporting_focus_areas", []),
            ]
            assignments[str(row["visible_id"])] = sorted(set(map(str, values)))
            match = re.search(r"(?m)^Decision:\s*(.+?)\s*$", str(row["body_markdown"]))
            if match and match.group(1).casefold() not in {"none", "n/a", "pending"}:
                decisions_needed.append({"campaign_id": str(row["visible_id"]), "decision": match.group(1)})
    else:
        for item in campaign_queue.load_all(workspace).values():
            if item.status not in {"complete", "completed", "abandoned", "deferred"}:
                assignments[item.campaign_id] = sorted(
                    set([*item.primary_focus_areas, *item.supporting_focus_areas])
                )
                decision = item.fields.get("Decision", "")
                if decision.casefold() not in {"", "none", "n/a", "pending"}:
                    decisions_needed.append({"campaign_id": item.campaign_id, "decision": decision})
    active_ids = {
        item["visible_id"] for item in artifacts
        if item["artifact_type"] == "campaign"
        and item["document_lifecycle"] in {"active", "working", "blocked"}
    }
    areas = [
        {
            "focus_area_id": area_id,
            "name": names[area_id],
            "active_campaigns": sorted(
                campaign_id for campaign_id in active_ids
                if area_id in assignments.get(campaign_id, [])
            ),
        }
        for area_id in sorted(names)
    ]
    return {
        "catalog_state": "approved" if approved else "unavailable",
        "areas": areas,
        "unassigned_campaigns": sorted(
            campaign_id for campaign_id in active_ids if not assignments.get(campaign_id)
        ) if approved else [],
        "decisions_needed": sorted(decisions_needed, key=lambda item: item["campaign_id"]),
    }


def _release_horizon(workspace: Path, authority: dict[str, Any]) -> dict[str, Any]:
    if authority["authority"] != "sqlite":
        return {"available": False, "base_tag": None, "active_cohorts": []}
    # Lazy import prevents the dashboard projection from acquiring release-cohort coupling.
    import release_cohort

    status = release_cohort.status(workspace)
    return {
        "available": True,
        "base_tag": status["current_base_tag"],
        "active_cohorts": [
            {
                "cycle_id": item["cycle_id"],
                "lifecycle_state": item["lifecycle_state"],
                "candidate_count": len(item["candidates"]),
            }
            for item in status["active"]
        ],
        "finding_count": status["finding_count"],
    }


def executive(workspace: Path) -> dict[str, Any]:
    """Build the deterministic operator-facing 100k contract from canonical projections."""
    workspace = workspace.resolve()
    projection = build(workspace)
    inventory = projection["work_inventory"]
    artifacts = inventory["artifacts"]
    authority = projection["authority"]
    intent = _executive_intent(workspace, authority)
    focus = _focus_coverage(workspace, authority, artifacts)
    release = _release_horizon(workspace, authority)
    if authority["authority"] == "sqlite":
        audit = hybrid_state.audit(workspace)
        source_revision = audit["current_revision"]
        source_digest = audit["domain_digest"]
    else:
        source_revision = None
        source_digest = hashlib.sha256(_canonical({
            "projection": projection,
            "executive_intent": intent,
        })).hexdigest()

    working = [
        item for item in artifacts
        if item["document_lifecycle"] == "working"
    ]
    ready_campaigns = [
        item for item in artifacts
        if item["artifact_type"] == "campaign"
        and item["document_lifecycle"] in {"active", "working"}
        and item["planning_readiness"] in {"queued", "ready", "working"}
    ]
    planned = [
        item for item in artifacts
        if item["artifact_type"] in {"program-roadmap", "idea-brief"}
        and item["document_lifecycle"] == "active"
        and item["planning_readiness"] in {"ready", "working"}
    ]
    recommendations = sorted(
        [*working, *ready_campaigns, *planned],
        key=lambda item: (
            0 if item["document_lifecycle"] == "working" else 1,
            item["planning_position"] if item["planning_position"] is not None else 10**9,
            item["visible_id"],
        ),
    )
    deduplicated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in recommendations:
        if item["artifact_id"] not in seen:
            seen.add(item["artifact_id"])
            deduplicated.append(item)

    all_executive_directives = [
        item for item in artifacts
        if item.get("metadata_role") == EXECUTIVE_DIRECTIVE_ROLE
    ]
    active_executive_directives = sorted(
        (
            item for item in all_executive_directives
            if item["document_lifecycle"] not in {"completed", "terminal", "abandoned", "superseded"}
        ),
        key=lambda item: (
            item["planning_position"] if item["planning_position"] is not None else 10**9,
            item["updated_at"],
            item["visible_id"],
        ),
    )
    completed_executive_directives = sorted(
        (item for item in all_executive_directives if item not in active_executive_directives),
        key=lambda item: (item["updated_at"], item["visible_id"]),
        reverse=True,
    )
    selected_executive_directives = active_executive_directives[:EXECUTIVE_DIRECTIVE_LIMIT]
    completed_slots = min(
        EXECUTIVE_RECENT_COMPLETED_LIMIT,
        EXECUTIVE_DIRECTIVE_LIMIT - len(selected_executive_directives),
    )
    selected_executive_directives.extend(completed_executive_directives[:completed_slots])
    directives_truncated = len(selected_executive_directives) < len(all_executive_directives)

    executive_directives = []
    for item in selected_executive_directives:
        if item["document_lifecycle"] in {"completed", "terminal"}:
            stage = "completed"
        elif item["document_lifecycle"] in {"blocked", "parked", "deferred"}:
            stage = item["document_lifecycle"]
        elif item["outcome_disposition"] not in {"unknown", "open"}:
            stage = item["outcome_disposition"]
        elif item["produces_ids"]:
            stage = "working" if item["planning_readiness"] == "working" else "delegated"
        else:
            stage = "queued"
        executive_directives.append({
            **item,
            "directive_stage": stage,
            "subordinate_handoff": item["produces_ids"] or ["Plan Cycle (queued)"],
            "directive_text": item.get("metadata_directive_text") or item["title"],
        })

    attention: list[dict[str, str]] = []
    if inventory["truncated"]:
        attention.append({
            "code": "INVENTORY_TRUNCATED",
            "summary": "The strategic ledger exceeded its safety bound and is not complete.",
        })
    if directives_truncated:
        attention.append({
            "code": "EXECUTIVE_DIRECTIVES_TRUNCATED",
            "summary": (
                f"The CEO directive view is showing {len(executive_directives)} of "
                f"{len(all_executive_directives)} directives; all active directives are shown "
                f"unless the {EXECUTIVE_DIRECTIVE_LIMIT}-item safety bound is exceeded."
            ),
        })
    if focus["unassigned_campaigns"]:
        attention.append({
            "code": "FOCUS_AREA_UNASSIGNED",
            "summary": "Active campaigns lack an approved focus-area assignment: "
            + ", ".join(focus["unassigned_campaigns"]),
        })
    for decision in focus["decisions_needed"]:
        attention.append({
            "code": "DECISION_NEEDED",
            "summary": f"{decision['campaign_id']}: {decision['decision']}",
        })
    state = projection["state"]
    for key, code, label in (
        ("blocked_count", "BLOCKED_WORK", "blocked campaign(s)"),
        ("closure_debt_count", "CLOSURE_DEBT", "closure debt item(s)"),
        ("unreconciled_outcome_count", "OUTCOME_UNRECONCILED", "unreconciled outcome(s)"),
        ("active_loop_finding_count", "LOOP_FINDINGS", "active loop finding(s)"),
    ):
        if state.get(key):
            attention.append({"code": code, "summary": f"{state[key]} {label} require attention."})
    if release.get("finding_count"):
        attention.append({"code": "RELEASE_COHORT_INVALID", "summary": "Release cohort findings require attention."})

    recent = sorted(
        artifacts, key=lambda item: (item["updated_at"], item["visible_id"]), reverse=True
    )[:10]
    material = {
        "projection": projection,
        "executive_intent": intent,
        "source_revision": source_revision,
        "source_digest": source_digest,
        "focus_coverage": focus,
        "release_horizon": release,
        "attention": attention,
        "recommendations": [item["artifact_id"] for item in deduplicated[:8]],
        "executive_directives": [item["artifact_id"] for item in executive_directives],
        "executive_directive_counts": {
            "total": len(all_executive_directives),
            "active": len(active_executive_directives),
            "completed": len(completed_executive_directives),
            "truncated": directives_truncated,
        },
        "recent": [item["artifact_id"] for item in recent],
    }
    return {
        "schema_version": EXECUTIVE_SCHEMA_VERSION,
        "kind": "tool-shed-project-executive-view",
        "authority": authority,
        "source_revision": source_revision,
        "source_digest": source_digest,
        "state_digest": hashlib.sha256(_canonical(material)).hexdigest(),
        "latest_source_update": max(
            [
                *(item["updated_at"] for item in artifacts),
                *([intent["updated_at"]] if intent.get("updated_at") else []),
            ],
            default=None,
        ),
        "state": state,
        "complete_accounting": not inventory["truncated"],
        "inventory": inventory,
        "executive_intent": intent,
        "focus_coverage": focus,
        "release_horizon": release,
        "attention": attention,
        "recommendations": deduplicated[:8],
        "executive_directives": executive_directives,
        "executive_directive_count": len(all_executive_directives),
        "active_executive_directive_count": len(active_executive_directives),
        "completed_executive_directive_count": len(completed_executive_directives),
        "executive_directives_truncated": directives_truncated,
        "recent_changes": recent,
        "loop_findings": projection["loop_findings"],
        "writes_performed": False,
    }


def _cell(value: object) -> str:
    return str(value if value not in {None, ""} else "—").replace("|", "\\|").replace("\n", " ")


def _orientation_sources(workspace: Path) -> list[str]:
    """List a bounded set of likely owner-orientation sources without interpreting them."""
    names = {"readme", "architecture", "strategy", "vision", "goals", "roadmap", "project"}
    sources: list[str] = []
    for directory in (workspace, workspace / "docs"):
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir(), key=lambda candidate: candidate.name.casefold()):
            if len(sources) >= 20:
                return sources
            if (
                not path.is_file()
                or path.is_symlink()
                or path.suffix.casefold() not in {".md", ".rst", ".txt"}
                or path.stem.casefold() not in names
            ):
                continue
            sources.append(path.relative_to(workspace).as_posix())
    return sources


def executive_intent_setup(workspace: Path, view: dict[str, Any]) -> dict[str, Any]:
    """Build a read-only evidence packet for an owner-reviewed intent proposal."""
    intent = view.get("executive_intent") or _missing_executive_intent()
    evidence: list[dict[str, Any]] = []
    seen: set[str] = set()
    active = [
        item for item in view["inventory"]["artifacts"]
        if item["document_lifecycle"] not in {
            "completed", "terminal", "abandoned", "superseded", "deferred", "parked",
        }
    ]
    for item in [*view.get("recommendations", []), *active, *view.get("recent_changes", [])]:
        identity = str(item["artifact_id"])
        if identity in seen:
            continue
        seen.add(identity)
        evidence.append({
            "visible_id": item["visible_id"],
            "artifact_type": item["artifact_type"],
            "title": item["title"],
            "lifecycle": item["document_lifecycle"],
            "planning_readiness": item["planning_readiness"],
        })
        if len(evidence) >= 12:
            break
    existing = {
        key: intent.get(key)
        for key, _ in EXECUTIVE_INTENT_SECTIONS
    }
    missing = list(intent.get("missing_sections", []))
    if intent.get("state") == "missing":
        missing = [heading for _, heading in EXECUTIVE_INTENT_SECTIONS]
    authority = view["authority"]["authority"]
    destination = (
        "one active managed decision with metadata role "
        f"{EXECUTIVE_INTENT_ROLE} and preferred path {EXECUTIVE_INTENT_RELATIVE.as_posix()}"
        if authority == "sqlite"
        else f"{EXECUTIVE_INTENT_RELATIVE.as_posix()} with Type: decision and Role: {EXECUTIVE_INTENT_ROLE}"
    )
    needs_proposal = intent.get("state") in {"missing", "incomplete"}
    return {
        "schema_version": EXECUTIVE_SCHEMA_VERSION,
        "kind": "tool-shed-project-executive-intent-setup",
        "state": "owner-review-required" if needs_proposal else "already-established",
        "authority": view["authority"],
        "intent_state": intent.get("state"),
        "intent_identity": intent.get("identity"),
        "destination": destination,
        "required_sections": [heading for _, heading in EXECUTIVE_INTENT_SECTIONS],
        "missing_sections": missing,
        "existing_values": existing,
        "orientation_sources": _orientation_sources(workspace),
        "artifact_evidence": evidence,
        "artifact_count": view["inventory"]["total_count"],
        "complete_accounting": view["complete_accounting"],
        "owner_acceptance_required": needs_proposal,
        "writes_performed": False,
    }


def render_intent_setup(setup: dict[str, Any]) -> str:
    """Render the read-only guided setup packet and proposal scaffold."""
    lines = [
        "# 100k Executive Intent Setup",
        "",
        "> Read-only discovery and proposal scaffold. It never infers, accepts, or persists owner",
        "> strategy. Review the evidence, revise the proposal, and explicitly accept it before write.",
        "",
        "## Setup Status",
        "",
        f"- State: **{setup['state']}**",
        f"- Existing intent: **{setup['intent_state']}**",
        f"- Destination after acceptance: `{setup['destination']}`",
        f"- Artifact accounting: **{'complete' if setup['complete_accounting'] else 'INCOMPLETE'}** "
        f"({setup['artifact_count']} artifacts)",
        "",
        "## Discovered Orientation Sources",
        "",
    ]
    if setup["orientation_sources"]:
        lines.extend(f"- `{path}`" for path in setup["orientation_sources"])
    else:
        lines.append("- No conventional README, architecture, strategy, vision, goals, roadmap, or project document was found.")
    lines.extend([
        "",
        "## Canonical Artifact Evidence",
        "",
        "| ID | Type | Lifecycle | Readiness | Title |",
        "| --- | --- | --- | --- | --- |",
    ])
    for item in setup["artifact_evidence"]:
        lines.append(
            "| " + " | ".join(_cell(value) for value in (
                f"`{item['visible_id']}`", item["artifact_type"], item["lifecycle"],
                item["planning_readiness"], item["title"],
            )) + " |"
        )
    if not setup["artifact_evidence"]:
        lines.append("| — | — | — | — | No canonical artifact evidence was discovered. |")
    lines.extend(["", "## Proposal Scaffold", ""])
    for key, heading in EXECUTIVE_INTENT_SECTIONS:
        lines.extend([f"### {heading}", ""])
        value = setup["existing_values"].get(key)
        if isinstance(value, list):
            lines.extend(f"- {item}" for item in value)
            if not value:
                lines.append("- [Owner decision required after evidence review.]")
        else:
            lines.append(str(value) if value else "[Owner decision required after evidence review.]")
        lines.append("")
    lines.extend([
        "## Acceptance Boundary",
        "",
        "1. Inspect the named orientation sources and relevant canonical artifacts.",
        "2. Present one exact seven-section proposal, with uncertainties left visible.",
        "3. Ask the owner to accept or revise that proposal.",
        "4. Only after explicit acceptance, persist it at the authority-specific destination and refresh `100k`.",
        "",
        "A workspace upgrade or bare `ts: 100k` read never performs step 4.",
    ])
    return "\n".join(lines).rstrip() + "\n"


def render_ledger(view: dict[str, Any]) -> str:
    state = view["state"]
    lines = [
        "# 100k Complete Strategic Ledger",
        "",
        "> Deterministic read-only drill-down from the same project projection as `work/100k.md`.",
        "",
        "## Executive Review",
        "",
        f"- Authority: `{view['authority']['authority']}` ({view['authority']['state']})",
        f"- Source revision: `{_cell(view['source_revision'])}`",
        f"- Source digest: `{view['source_digest']}`",
        f"- View state digest: `{view['state_digest']}`",
        f"- Latest material source update: `{_cell(view['latest_source_update'])}`",
        f"- Accounting: **{'complete' if view['complete_accounting'] else 'INCOMPLETE'}** "
        f"({view['inventory']['total_count']} strategic artifacts)",
        "",
        "The project direction remains in the current Project Maps and their owner-approved source",
        "decisions. This view reports that world; it does not invent a strategy or choose work.",
        "",
        "### Project Health",
        "",
        "| Working | Ready | Blocked | Active ideas | Open outcomes | Unreconciled | Closure debt | Loop findings |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| {state['working_count']} | {state['ready_count']} | {state['blocked_count']} | "
        f"{state['active_idea_count']} | {state['open_outcome_count']} | "
        f"{state['unreconciled_outcome_count']} | {state['closure_debt_count']} | "
        f"{state['active_loop_finding_count']} |",
        "",
        "### Completion Horizon",
        "",
    ]
    release = view["release_horizon"]
    if not release["available"]:
        lines.append("- Release cohort state is unavailable under file authority.")
    else:
        lines.append(f"- Current release base: `{_cell(release['base_tag'])}`")
        if release["active_cohorts"]:
            for cohort in release["active_cohorts"]:
                lines.append(
                    f"- Cohort `{cohort['cycle_id']}`: {cohort['lifecycle_state']}; "
                    f"{cohort['candidate_count']} candidate(s); next governed transition is Work5."
                )
        else:
            lines.append("- No active release cohort; no Work2 candidate is awaiting Work5.")
    lines.extend(["", "### Recommended Next-Cycle Review", ""])
    if view["recommendations"]:
        for item in view["recommendations"]:
            position = f"planning position {item['planning_position']}" if item["planning_position"] else "derived order"
            lines.append(
                f"- `{item['visible_id']}` — {item['title']} ({item['document_lifecycle']}; "
                f"{item['planning_readiness']}; {position})"
            )
        lines.append("- Operator decision remains required before selecting or changing the next cycle.")
    else:
        lines.append("- No ready or working strategic cycle is currently projected.")
    lines.extend(["", "### Attention", ""])
    if view["attention"]:
        lines.extend(f"- **{item['code']}**: {item['summary']}" for item in view["attention"])
    else:
        lines.append("- No projected accounting, focus, outcome, closure, loop, or cohort attention signal.")
    lines.extend(["", "### Recent Material Changes", ""])
    for item in view["recent_changes"]:
        lines.append(
            f"- `{item['updated_at']}` `{item['visible_id']}` — {item['title']} "
            f"({item['document_lifecycle']})"
        )
    if not view["recent_changes"]:
        lines.append("- None.")
    lines.extend(["", "## Focus-Area Coverage", ""])
    focus = view["focus_coverage"]
    if focus["catalog_state"] != "approved":
        lines.append("- No approved focus-area catalog is available.")
    else:
        lines.extend(["| Focus area | Active campaigns |", "| --- | --- |"])
        for area in focus["areas"]:
            campaigns = ", ".join(f"`{value}`" for value in area["active_campaigns"]) or "—"
            lines.append(f"| `{area['focus_area_id']}` — {area['name']} | {campaigns} |")
    lines.extend([
        "", "## Complete Strategic Ledger", "",
        "Every canonical Idea, Project Map, Program Roadmap, and Campaign appears below. Use the",
        "existing status, overview, order, relationship, outcome, and loop commands for drill-down.",
        "",
        "| ID | Type | Lifecycle | Readiness/order | Outcome | Reconciliation | Closure | Parents | Produces | Title |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for item in view["inventory"]["artifacts"]:
        planning = item["planning_readiness"]
        if item["planning_position"] is not None:
            planning += f"/{item['planning_position']}"
        closure = item["closure_status"]
        closure_text = "closed" if closure["effective_closed"] else closure["local_closure"]
        lines.append(
            "| " + " | ".join(_cell(value) for value in (
                f"`{item['visible_id']}`", item["artifact_type"], item["document_lifecycle"],
                planning, f"{item['outcome_lifecycle']}/{item['outcome_disposition']}",
                item["reconciliation_state"], closure_text,
                ", ".join(item["parent_ids"]), ", ".join(item["produces_ids"]), item["title"],
            )) + " |"
        )
    lines.extend([
        "", "## Active Loop Findings", "",
        f"Active findings: {view['loop_findings']['total_active_count']}", "",
    ])
    findings = view["loop_findings"].get("findings", [])
    if findings:
        for item in findings:
            lines.append(f"- `{_cell(item.get('finding_id') or item.get('id'))}` — {_cell(item.get('summary') or item.get('finding_class'))}")
    else:
        lines.append("- None.")
    return "\n".join(lines).rstrip() + "\n"


def render_executive(view: dict[str, Any]) -> str:
    """Render the concise owner cockpit; exhaustive accounting stays in render_ledger."""
    state = view["state"]
    intent = view.get("executive_intent") or _missing_executive_intent()
    lines = [
        EXECUTIVE_MARKER,
        "# 100k Project Executive View",
        "",
        "> This file is a deterministic, read-only strategic cockpit. Do not edit it. Change",
        "> executive intent or the named Tool Shed source artifact, then refresh this view.",
        "",
        "## Executive Review",
        "",
        f"- Executive intent: **{intent['state']}**"
        + (f" (`{intent['identity']}`, revision {_cell(intent['revision'])})" if intent.get("identity") else ""),
        f"- Operational accounting: **{'complete' if view['complete_accounting'] else 'INCOMPLETE'}** "
        f"({view['inventory']['total_count']} strategic artifacts)",
        f"- Latest material update: `{_cell(view['latest_source_update'])}`",
        "",
        "Executive intent supplies direction; Ideas, maps, PRMs, campaigns, decisions, outcomes,",
        "and evidence retain execution truth. Reading this view never selects, prioritizes, starts,",
        "or completes work.",
        "",
        "## North Star",
        "",
    ]
    if intent.get("north_star"):
        lines.append(str(intent["north_star"]))
    else:
        lines.append(
            "**Not established.** Capture the project's enduring purpose before treating "
            "operational quiet as strategic completion."
        )

    lines.extend(["", "## Current Completion Horizon", ""])
    if intent.get("completion_horizon"):
        lines.append(str(intent["completion_horizon"]))
    else:
        lines.append(
            "**Not established.** Define what done-for-now means and what should trigger the next review."
        )
    release = view["release_horizon"]
    if release["available"]:
        lines.append(f"- Current release base: `{_cell(release['base_tag'])}`")
        if release["active_cohorts"]:
            for cohort in release["active_cohorts"]:
                lines.append(
                    f"- Release cohort `{cohort['cycle_id']}` is {cohort['lifecycle_state']} with "
                    f"{cohort['candidate_count']} candidate(s)."
                )
        else:
            lines.append("- No Work2 candidate is currently awaiting Work5.")
    else:
        lines.append("- Release-cohort state is unavailable under file authority.")

    lines.extend(["", "## Strategic Context", ""])
    lines.append(
        str(intent["strategic_context"])
        if intent.get("strategic_context")
        else "- No owner-authored strategic context is currently recorded."
    )

    lines.extend(["", "## Current Priorities", ""])
    priorities = list(intent.get("priorities", []))
    lines.extend(f"- {item}" for item in priorities)
    if not priorities:
        lines.append("- No owner-authored strategic priority order is currently recorded.")

    lines.extend(["", "## Executive Directives", ""])
    directives = list(view.get("executive_directives", []))
    if directives:
        lines.extend([
            "| Order | Directive | State | Subordinate handoff |",
            "| ---: | --- | --- | --- |",
        ])
        for item in directives:
            handoff = ", ".join(
                f"`{value}`" if re.fullmatch(r"[A-Z]+-\d+", value) else value
                for value in item["subordinate_handoff"]
            )
            lines.append(
                f"| {_cell(item['planning_position'])} | "
                f"`{item['visible_id']}` — {_cell(item['title'])} | "
                f"{_cell(item['directive_stage'])} | {handoff} |"
            )
        if view.get("executive_directives_truncated"):
            lines.append(
                f"\n- Showing {len(directives)} of {view['executive_directive_count']} directives; "
                "the bounded projection reports truncation explicitly."
            )
    else:
        lines.append(
            "- No executive directive is currently recorded. Issue one with "
            "`ts: 100k add <directive>`; Tool Shed will capture it durably in planning order."
        )

    lines.extend([
        "", "## Project Landscape", "",
        "| Working | Ready | Blocked | Active ideas | Open outcomes | Unreconciled | Closure debt | Loop findings |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| {state['working_count']} | {state['ready_count']} | {state['blocked_count']} | "
        f"{state['active_idea_count']} | {state['open_outcome_count']} | "
        f"{state['unreconciled_outcome_count']} | {state['closure_debt_count']} | "
        f"{state['active_loop_finding_count']} |",
        "",
    ])
    focus = view["focus_coverage"]
    if focus["catalog_state"] != "approved":
        lines.append("- No approved focus-area catalog is available.")
    else:
        lines.extend(["| Enduring focus area | Active campaigns |", "| --- | --- |"])
        for area in focus["areas"]:
            campaigns = ", ".join(f"`{value}`" for value in area["active_campaigns"]) or "—"
            lines.append(f"| `{area['focus_area_id']}` — {area['name']} | {campaigns} |")

    lines.extend(["", "## Decisions And Attention", ""])
    decisions: list[str] = []
    if intent["state"] == "missing":
        decisions.append(
            "**EXECUTIVE_INTENT_MISSING:** Establish the North Star, completion horizon, strategic "
            "context, priorities, deliberate non-goals, decisions, and review triggers. Run "
            "`ts: 100k setup` for a read-only evidence packet and owner-reviewed proposal."
        )
    elif intent["state"] == "incomplete":
        decisions.append(
            "**EXECUTIVE_INTENT_INCOMPLETE:** Complete: "
            + ", ".join(intent.get("missing_sections", []))
            + ". Run `ts: 100k setup` to preserve existing sections and propose only the gaps."
        )
    decisions.extend(str(item) for item in intent.get("decisions_needed", []))
    decisions.extend(f"**{item['code']}:** {item['summary']}" for item in view["attention"])
    if not view["recommendations"] and intent.get("completion_horizon"):
        decisions.append(
            "No working or ready strategic cycle is projected; confirm whether the current horizon "
            "is satisfied or choose the next outcome."
        )
    if decisions:
        lines.extend(f"- {item}" for item in decisions)
    else:
        lines.append("- No decision or attention signal.")

    lines.extend(["", "## Recommended Next Cycles", ""])
    if view["recommendations"]:
        for item in view["recommendations"]:
            position = (
                f"planning position {item['planning_position']}"
                if item["planning_position"] is not None else "derived order"
            )
            lines.append(
                f"- `{item['visible_id']}` — {item['title']} ({item['document_lifecycle']}; "
                f"{item['planning_readiness']}; {position})"
            )
        if any(
            item["document_lifecycle"] not in {"completed", "terminal"}
            for item in directives
        ):
            lines.append(
                "- The active CEO directive owns the outcome; subordinate cycles continue under "
                "its authority envelope."
            )
        else:
            lines.append("- The operator must explicitly choose or change the next cycle.")
    else:
        lines.append("- No working or ready strategic cycle is currently projected.")

    lines.extend(["", "## What Changed", ""])
    for item in view["recent_changes"][:5]:
        lines.append(
            f"- `{item['updated_at']}` `{item['visible_id']}` — {item['title']} "
            f"({item['document_lifecycle']})"
        )
    if not view["recent_changes"]:
        lines.append("- No material artifact changes are projected.")

    realized = [
        item for item in view["recent_changes"]
        if item["document_lifecycle"] in {"completed", "terminal"}
    ][:5]
    lines.extend(["", "## Realized Outcomes", ""])
    if realized:
        lines.extend(f"- `{item['visible_id']}` — {item['title']}" for item in realized)
    else:
        lines.append("- No recently realized strategic outcome is projected.")

    lines.extend(["", "## Deliberate Non-Goals", ""])
    non_goals = list(intent.get("non_goals", []))
    lines.extend(f"- {item}" for item in non_goals)
    if not non_goals:
        lines.append("- No deliberate non-goals are currently recorded.")

    lines.extend(["", "## Review Triggers", ""])
    triggers = list(intent.get("review_triggers", []))
    lines.extend(f"- {item}" for item in triggers)
    if not triggers:
        lines.append("- No owner-authored review triggers are currently recorded.")

    lines.extend([
        "", "## Accounting And Drill-Down", "",
        f"- Accounting is **{'complete' if view['complete_accounting'] else 'INCOMPLETE'}** across "
        f"{view['inventory']['total_count']} canonical Ideas, Project Maps, Program Roadmaps, and Campaigns.",
        "- Review the exhaustive deterministic ledger with "
        "`python3 scripts/project_projection.py --workspace . 100k ledger`.",
        "- Use status, overview, order, relationship, outcome, and loop commands for focused detail.",
        f"- Authority: `{view['authority']['authority']}` ({view['authority']['state']}); "
        f"source revision `{_cell(view['source_revision'])}`; source digest `{view['source_digest']}`; "
        f"view digest `{view['state_digest']}`.",
    ])
    return "\n".join(lines).rstrip() + "\n"


def expected_executive_markdown(workspace: Path) -> tuple[dict[str, Any], str]:
    view = executive(workspace)
    return view, render_executive(view)


def check_executive(workspace: Path, output: Path = EXECUTIVE_RELATIVE) -> dict[str, Any]:
    workspace = workspace.resolve()
    absolute = authority_resolver.require_path_within(workspace, workspace / output)
    view, expected = expected_executive_markdown(workspace)
    observed = absolute.read_bytes() if absolute.is_file() else None
    expected_bytes = expected.encode("utf-8")
    state = "missing" if observed is None else "current" if observed == expected_bytes else "stale"
    if not view["complete_accounting"]:
        state = "incomplete"
    return {
        "schema_version": EXECUTIVE_SCHEMA_VERSION,
        "kind": "tool-shed-project-executive-check",
        "path": absolute.relative_to(workspace).as_posix(),
        "state": state,
        "valid": state == "current",
        "complete_accounting": view["complete_accounting"],
        "executive_intent_state": view["executive_intent"]["state"],
        "next_route": (
            "ts: 100k setup"
            if view["executive_intent"]["state"] in {"missing", "incomplete"}
            else None
        ),
        "source_revision": view["source_revision"],
        "source_digest": view["source_digest"],
        "state_digest": view["state_digest"],
        "expected_sha256": hashlib.sha256(expected_bytes).hexdigest(),
        "observed_sha256": hashlib.sha256(observed).hexdigest() if observed is not None else None,
        "writes_performed": False,
    }


def refresh_executive(workspace: Path, output: Path = EXECUTIVE_RELATIVE) -> dict[str, Any]:
    workspace = workspace.resolve()
    absolute = authority_resolver.require_path_within(workspace, workspace / output)
    if absolute.is_file():
        observed = absolute.read_text(encoding="utf-8")
        generated_markers = (EXECUTIVE_MARKER, *LEGACY_EXECUTIVE_MARKERS)
        if not observed.startswith(generated_markers):
            raise ProjectProjectionError(
                f"refusing to overwrite non-generated executive view: {absolute.relative_to(workspace)}"
            )
    view, content = expected_executive_markdown(workspace)
    absolute.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{absolute.name}.", dir=absolute.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, absolute)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "schema_version": EXECUTIVE_SCHEMA_VERSION,
        "kind": "tool-shed-project-executive-refresh",
        "path": absolute.relative_to(workspace).as_posix(),
        "source_revision": view["source_revision"],
        "source_digest": view["source_digest"],
        "state_digest": view["state_digest"],
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "complete_accounting": view["complete_accounting"],
        "executive_intent_state": view["executive_intent"]["state"],
        "next_route": (
            "ts: 100k setup"
            if view["executive_intent"]["state"] in {"missing", "incomplete"}
            else None
        ),
        "writes_performed": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    review = commands.add_parser("100k")
    review.add_argument("section", nargs="?", choices=("review", "ledger", "setup"), default="review")
    refresh = commands.add_parser("render-100k")
    refresh.add_argument("--output", type=Path, default=EXECUTIVE_RELATIVE)
    check = commands.add_parser("check-100k")
    check.add_argument("--output", type=Path, default=EXECUTIVE_RELATIVE)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workspace = Path(args.workspace).expanduser().resolve()
    try:
        if args.command == "100k":
            view, markdown = expected_executive_markdown(workspace)
            setup = executive_intent_setup(workspace, view) if args.section == "setup" else None
            if args.json:
                payload = view if args.section == "review" else setup if setup is not None else {
                    "schema_version": EXECUTIVE_SCHEMA_VERSION,
                    "kind": "tool-shed-project-executive-ledger",
                    "source_revision": view["source_revision"],
                    "source_digest": view["source_digest"],
                    "state_digest": view["state_digest"],
                    "complete_accounting": view["complete_accounting"],
                    "inventory": view["inventory"],
                    "loop_findings": view["loop_findings"],
                    "writes_performed": False,
                }
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                output = (
                    markdown if args.section == "review" else
                    render_intent_setup(setup) if setup is not None else
                    render_ledger(view)
                )
                print(output, end="")
            return 0 if view["complete_accounting"] else 1
        if args.command == "render-100k":
            result = refresh_executive(workspace, args.output)
        else:
            result = check_executive(workspace, args.output)
        print(json.dumps(result, indent=2, sort_keys=True) if args.json else (
            f"100k executive view: {result.get('state', 'refreshed')} ({result['path']})"
        ))
        return 0 if result.get("valid", result["complete_accounting"]) else 1
    except (ProjectProjectionError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Project executive view failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
