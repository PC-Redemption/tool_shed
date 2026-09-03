#!/usr/bin/env python3
"""Independent structural oracle for one fixed low-reasoning Tool Shed route smoke."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import contextlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Sequence

import hybrid_state
import lifecycle_qualification as qualification


EXPECTED_TYPES = {"idea-brief": 1, "project-map": 1, "program-roadmap": 1, "campaign": 1}


class RouteSmokeError(RuntimeError):
    pass


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def snapshot(workspace: Path, *, run_tag: str) -> dict[str, Any]:
    workspace = workspace.resolve()
    database = hybrid_state.database_path(workspace)
    with contextlib.closing(hybrid_state.connect(database, writable=False)) as connection:
        meta = dict(connection.execute("SELECT * FROM state_meta WHERE id=1").fetchone())
        rows = list(
            connection.execute(
                "SELECT d.*,a.type,r.body_markdown FROM document d "
                "JOIN artifact a ON a.id=d.id "
                "JOIN document_revision r ON r.document_id=d.id AND r.revision_number=d.current_revision "
                "WHERE d.title LIKE ? OR r.body_markdown LIKE ? OR d.metadata_json LIKE ? ORDER BY d.visible_id",
                (f"%{run_tag}%", f"%{run_tag}%", f"%{run_tag}%"),
            )
        )
        documents = [
            {
                "artifact_id": str(row["id"]),
                "visible_id": str(row["visible_id"]),
                "type": str(row["type"]),
                "title": str(row["title"]),
                "lifecycle": str(row["lifecycle_state"]),
                "revision": int(row["current_revision"]),
                "body_sha256": str(row["body_sha256"]),
                "metadata": json.loads(row["metadata_json"]),
            }
            for row in rows
        ]
        ids = [item["artifact_id"] for item in documents]
        relationships: list[dict[str, Any]] = []
        cycles: list[dict[str, Any]] = []
        readiness: list[dict[str, Any]] = []
        closure_elements: dict[str, dict[str, Any]] = {}
        projection_mismatches: list[dict[str, Any]] = []
        if ids:
            marks = ",".join("?" for _ in ids)
            relationships = [dict(row) for row in connection.execute(
                f"SELECT * FROM relationship WHERE retired_revision IS NULL AND (from_artifact_id IN ({marks}) OR to_artifact_id IN ({marks})) ORDER BY created_revision,id",
                [*ids, *ids],
            )]
            cycles = [dict(row) for row in connection.execute(
                f"SELECT * FROM cycle WHERE origin_artifact_id IN ({marks}) ORDER BY opened_at,id", ids
            )]
            for cycle in cycles:
                verdict = connection.execute("SELECT * FROM outcome_verdict WHERE cycle_id=? ORDER BY decided_revision DESC LIMIT 1", (cycle["id"],)).fetchone()
                reconciliation = connection.execute("SELECT * FROM reconciliation WHERE cycle_id=? ORDER BY origin_revision DESC LIMIT 1", (cycle["id"],)).fetchone()
                cycle["verdict"] = dict(verdict) if verdict else None
                cycle["reconciliation"] = dict(reconciliation) if reconciliation else None
            for row in connection.execute("SELECT payload_json FROM event WHERE kind='idea-readiness-review-v1' ORDER BY revision"):
                payload = json.loads(row[0])
                idea = payload.get("idea") if isinstance(payload, dict) else None
                if isinstance(idea, dict) and str(idea.get("artifact_id")) in ids:
                    readiness.append(payload)
            oracle = qualification.independent_closure(connection)
            projection_mismatches = qualification.compare_closure_projection(connection, oracle)
            cycle_ids = {str(item["id"]) for item in cycles}
            for row in connection.execute("SELECT id,cycle_id FROM closure_element WHERE cycle_id IS NOT NULL ORDER BY id"):
                if str(row["cycle_id"]) in cycle_ids:
                    closure_elements[str(row["id"])] = oracle["elements"][str(row["id"])]
        return {
            "schema_version": 1,
            "kind": "tool-shed-route-smoke-snapshot",
            "run_tag": run_tag,
            "database_revision": int(meta["current_revision"]),
            "domain_digest": hybrid_state.audit_connection(workspace, connection)["domain_digest"],
            "documents": documents,
            "relationships": relationships,
            "cycles": cycles,
            "readiness_results": readiness,
            "closure_elements": closure_elements,
            "projection_mismatches": projection_mismatches,
        }


def evaluate(
    before: dict[str, Any],
    completed: dict[str, Any],
    replayed: dict[str, Any],
    *,
    provider: str,
    model: str,
    effort: str,
    turns: int,
    duration_seconds: float,
    adapter_version: str,
    platform_name: str,
) -> dict[str, Any]:
    docs = completed["documents"]
    by_type: dict[str, list[dict[str, Any]]] = {}
    for item in docs:
        by_type.setdefault(str(item["type"]), []).append(item)
    actual_types = {name: len(by_type.get(name, [])) for name in EXPECTED_TYPES}
    idea = by_type.get("idea-brief", [None])[0]
    project_map = by_type.get("project-map", [None])[0]
    roadmap = by_type.get("program-roadmap", [None])[0]
    campaign = by_type.get("campaign", [None])[0]
    readiness = completed.get("readiness_results", [])
    idea_readiness = [item for item in readiness if idea and item.get("idea", {}).get("artifact_id") == idea["artifact_id"]]
    reviewed = idea_readiness[-1] if idea_readiness else {}
    expected_gates = sorted(str(item["id"]) for item in reviewed.get("prm_gates", []))
    map_gates = sorted(map(str, (project_map or {}).get("metadata", {}).get("readiness_gate_ids", [])))
    prm_gates = sorted(map(str, (roadmap or {}).get("metadata", {}).get("readiness_gate_ids", [])))
    ids = {item["artifact_id"] for item in docs}
    relations = {
        (str(item["from_artifact_id"]), str(item["relation_type"]), str(item["to_artifact_id"]))
        for item in completed.get("relationships", [])
    }
    expected_relations = set()
    chain = [idea, project_map, roadmap, campaign]
    if all(chain):
        for parent, child in zip(chain, chain[1:]):
            expected_relations.add((parent["artifact_id"], "produces", child["artifact_id"]))
            expected_relations.add((child["artifact_id"], "outcome-parent", parent["artifact_id"]))
    cycles = completed.get("cycles", [])
    terminal = all(
        item.get("lifecycle_state") == "terminal"
        and (item.get("verdict") or {}).get("disposition") == "satisfied"
        and (item.get("reconciliation") or {}).get("state") == "reconciled"
        for item in cycles
    )
    closure = completed.get("closure_elements", {})
    checks = [
        {"id": "ROUTE-CARDINALITY", "passed": actual_types == EXPECTED_TYPES and len(docs) == 4, "expected": EXPECTED_TYPES, "actual": actual_types},
        {"id": "ROUTE-CURRENT-READINESS", "passed": len(idea_readiness) == 1 and reviewed.get("verdict") in {"READY", "READY-WITH-PRM-GATES"}, "expected": "one revision-bound ready result", "actual": [{"revision": item.get("idea", {}).get("document_revision"), "verdict": item.get("verdict")} for item in idea_readiness]},
        {"id": "ROUTE-PROVENANCE", "passed": bool(idea and project_map and roadmap and reviewed and project_map["metadata"].get("reviewed_idea_artifact_id") == reviewed["idea"]["artifact_id"] and roadmap["metadata"].get("reviewed_idea_artifact_id") == reviewed["idea"]["artifact_id"] and project_map["metadata"].get("reviewed_idea_document_revision") == reviewed["idea"]["document_revision"] and roadmap["metadata"].get("reviewed_idea_document_revision") == reviewed["idea"]["document_revision"] and project_map["metadata"].get("reviewed_idea_body_sha256") == reviewed["idea"]["body_sha256"] and roadmap["metadata"].get("reviewed_idea_body_sha256") == reviewed["idea"]["body_sha256"]), "expected": "exact reviewed Idea artifact/revision/body provenance", "actual": {"reviewed_idea": reviewed.get("idea"), "map_metadata": (project_map or {}).get("metadata"), "roadmap_metadata": (roadmap or {}).get("metadata")}},
        {"id": "ROUTE-GATE-TRANSFER", "passed": bool(reviewed) and map_gates == prm_gates == expected_gates, "expected": expected_gates, "actual": {"map": map_gates, "roadmap": prm_gates}},
        {"id": "ROUTE-LINEAGE", "passed": expected_relations <= relations, "expected": sorted(expected_relations), "actual": sorted(relations)},
        {"id": "ROUTE-TERMINAL-RECONCILED", "passed": len(cycles) >= 4 and terminal, "expected": "all run-owned cycles terminal/satisfied/reconciled", "actual": cycles},
        {"id": "ROUTE-CLOSURE", "passed": bool(closure) and all(item.get("effective_closed") for item in closure.values()) and not completed.get("projection_mismatches"), "expected": "all run-owned cycle elements effectively closed with oracle parity", "actual": {"closure": closure, "mismatches": completed.get("projection_mismatches")}},
        {"id": "ROUTE-CLEAN-TAIL", "passed": all(item.get("lifecycle") == "completed" for item in docs), "expected": "all documents completed", "actual": {item["visible_id"]: item["lifecycle"] for item in docs}},
        {"id": "ROUTE-REVISION-ACCOUNTING", "passed": int(completed["database_revision"]) > int(before["database_revision"]), "expected": f"> {before['database_revision']}", "actual": completed["database_revision"]},
        {"id": "ROUTE-REPLAY-IDEMPOTENT", "passed": completed["database_revision"] == replayed["database_revision"] and ids == {item["artifact_id"] for item in replayed["documents"]} and completed["domain_digest"] == replayed["domain_digest"], "expected": {"revision": completed["database_revision"], "artifact_ids": sorted(ids), "domain_digest": completed["domain_digest"]}, "actual": {"revision": replayed["database_revision"], "artifact_ids": sorted(item["artifact_id"] for item in replayed["documents"]), "domain_digest": replayed["domain_digest"]}},
    ]
    result: dict[str, Any] = {
        "schema_version": 1,
        "kind": "tool-shed-low-reasoning-route-smoke-result",
        "run_tag": completed["run_tag"],
        "platform": platform_name,
        "execution": {"provider": provider, "model": model, "effort": effort, "turns": turns, "duration_seconds": duration_seconds, "adapter_version": adapter_version},
        "checks": checks,
        "first_divergence": next((item["id"] for item in checks if not item["passed"]), None),
    }
    result["verdict"] = "PASS" if result["first_divergence"] is None else "PRODUCT-FAIL"
    result["result_digest"] = qualification.digest(result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("snapshot")
    capture.add_argument("--workspace", required=True); capture.add_argument("--run-tag", required=True); capture.add_argument("--output", required=True)
    check = commands.add_parser("evaluate")
    check.add_argument("--before", required=True); check.add_argument("--completed", required=True); check.add_argument("--replayed", required=True); check.add_argument("--provider", required=True); check.add_argument("--model", required=True); check.add_argument("--effort", required=True); check.add_argument("--turns", required=True, type=int); check.add_argument("--duration-seconds", required=True, type=float); check.add_argument("--adapter-version", required=True); check.add_argument("--platform", required=True); check.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "snapshot":
            value = snapshot(Path(args.workspace), run_tag=args.run_tag)
        else:
            load = lambda name: json.loads(Path(name).read_text(encoding="utf-8"))
            value = evaluate(load(args.before), load(args.completed), load(args.replayed), provider=args.provider, model=args.model, effort=args.effort, turns=args.turns, duration_seconds=args.duration_seconds, adapter_version=args.adapter_version, platform_name=args.platform)
        _write(Path(args.output), value)
        print(json.dumps({"kind": value["kind"], "verdict": value.get("verdict"), "result_digest": value.get("result_digest")}, indent=2, sort_keys=True))
        return 0 if value.get("verdict", "PASS") == "PASS" else 3
    except (OSError, ValueError, sqlite3.Error, RouteSmokeError) as error:
        print(f"route smoke error: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
