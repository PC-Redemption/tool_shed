#!/usr/bin/env python3
"""Deterministic lifecycle qualification records, driver, and independent oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform as host_platform
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


SCHEMA_VERSION = 1
ORACLE_VERSION = "lifecycle-truth-oracle-v1"
MANIFEST_KIND = "tool-shed-qualification-run-manifest"
JOURNAL_KIND = "tool-shed-qualification-journal-event"
RESULT_KIND = "tool-shed-qualification-result"
TRUTH_KIND = "tool-shed-qualification-truth-vector"
VERDICTS = {"PASS", "PRODUCT-FAIL", "HARNESS-FAIL", "INFRA-BLOCKED"}
SCENARIO_ROOT = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "lifecycle-qualification"
    / "v1"
    / "scenarios"
)
SEED_PROJECT_IDS = {
    "10000000-0000-4000-8000-000000000001",
    "10000000-0000-4000-8000-000000000002",
}


class QualificationError(RuntimeError):
    pass


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise QualificationError(f"cannot load {label}: {error}") from error
    if not isinstance(value, dict):
        raise QualificationError(f"{label} must be a JSON object")
    return value


def scenario_path(value: str | Path) -> Path:
    supplied = Path(value)
    if supplied.is_file():
        return supplied.resolve()
    candidate = SCENARIO_ROOT / f"{str(value).upper()}.json"
    if candidate.is_file():
        return candidate
    raise QualificationError(f"scenario does not exist: {value}")


def validate_scenario(value: dict[str, Any]) -> None:
    required = {"schema_version", "kind", "scenario_id", "version", "title", "platforms", "checkpoints"}
    missing = sorted(required - set(value))
    if missing:
        raise QualificationError("scenario lacks: " + ", ".join(missing))
    if value["schema_version"] != 1 or value["kind"] != "tool-shed-qualification-scenario":
        raise QualificationError("unsupported qualification scenario")
    if not str(value["scenario_id"]).startswith("QH-") or int(value["version"]) < 1:
        raise QualificationError("scenario identity or version is invalid")
    if not value["platforms"] or not isinstance(value["checkpoints"], list):
        raise QualificationError("scenario platforms and checkpoints must be nonempty lists")
    checkpoint_ids = [item.get("id") for item in value["checkpoints"] if isinstance(item, dict)]
    if len(checkpoint_ids) != len(value["checkpoints"]) or len(set(checkpoint_ids)) != len(checkpoint_ids):
        raise QualificationError("scenario checkpoints need unique ids")


def seal_manifest(
    scenario: dict[str, Any],
    *,
    candidate_commit: str,
    candidate_version: str,
    platform_name: str,
    project_id: str,
    instance_id: str,
    serial: int,
    seed: int,
    target_environment: str,
    baseline_digest: str,
    checkpoint_id: str | None = None,
) -> dict[str, Any]:
    validate_scenario(scenario)
    if platform_name not in scenario["platforms"]:
        raise QualificationError(f"scenario does not support platform: {platform_name}")
    if serial < 1 or seed < 0:
        raise QualificationError("serial must be positive and seed must be nonnegative")
    checkpoint_ids = [str(item["id"]) for item in scenario["checkpoints"]]
    selected_checkpoint = checkpoint_id or (checkpoint_ids[0] if len(checkpoint_ids) == 1 else None)
    if selected_checkpoint not in checkpoint_ids:
        raise QualificationError("manifest requires an exact declared checkpoint selector")
    material: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": MANIFEST_KIND,
        "scenario": {
            "id": scenario["scenario_id"],
            "version": scenario["version"],
            "sha256": digest(scenario),
            "checkpoint_id": selected_checkpoint,
        },
        "candidate": {"commit": candidate_commit, "version": candidate_version},
        "fixture": {
            "platform": platform_name,
            "project_id": project_id,
            "instance_id": instance_id,
            "baseline_digest": baseline_digest,
        },
        "run": {"serial": serial, "seed": seed, "clock_mode": "observed-utc"},
        "target": {"environment": target_environment},
        "contracts": {"oracle_version": ORACLE_VERSION, "record_schema_version": SCHEMA_VERSION},
    }
    manifest_digest = digest(material)
    return {
        **material,
        "manifest_digest": manifest_digest,
        "run_id": f"tsqh-{manifest_digest[:24]}",
    }


def validate_manifest(value: dict[str, Any]) -> None:
    if value.get("schema_version") != 1 or value.get("kind") != MANIFEST_KIND:
        raise QualificationError("unsupported run manifest")
    material = {key: item for key, item in value.items() if key not in {"manifest_digest", "run_id"}}
    expected = digest(material)
    if value.get("manifest_digest") != expected or value.get("run_id") != f"tsqh-{expected[:24]}":
        raise QualificationError("run manifest seal is invalid")
    if not str(value.get("scenario", {}).get("checkpoint_id") or "").strip():
        raise QualificationError("run manifest has no checkpoint selector")


def append_journal(path: Path, event: dict[str, Any]) -> dict[str, Any]:
    """Append one hash-chained event; an exact repeated idempotency key is a no-op."""
    prior: list[dict[str, Any]] = []
    if path.is_file():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError as error:
                raise QualificationError(f"journal line {number} is invalid") from error
            validate_journal_event(item, prior[-1] if prior else None)
            prior.append(item)
    key = str(event.get("idempotency_key") or "")
    matches = [item for item in prior if item["idempotency_key"] == key]
    if matches:
        generated = {"schema_version", "kind", "sequence", "prior_event_digest", "event_digest"}
        comparable = {name: value for name, value in event.items() if name not in generated}
        existing = {name: value for name, value in matches[0].items() if name not in generated}
        if comparable != existing:
            raise QualificationError("idempotency key was reused with different journal content")
        return matches[0]
    if not key:
        raise QualificationError("journal event requires idempotency_key")
    base = {
        "schema_version": 1,
        "kind": JOURNAL_KIND,
        **event,
        "sequence": len(prior) + 1,
        "prior_event_digest": prior[-1]["event_digest"] if prior else None,
    }
    base.pop("event_digest", None)
    sealed = {**base, "event_digest": digest(base)}
    validate_journal_event(sealed, prior[-1] if prior else None)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(descriptor, canonical_bytes(sealed) + b"\n")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return sealed


def validate_journal_event(value: dict[str, Any], previous: dict[str, Any] | None) -> None:
    if value.get("schema_version") != 1 or value.get("kind") != JOURNAL_KIND:
        raise QualificationError("unsupported journal event")
    if value.get("sequence") != (int(previous["sequence"]) + 1 if previous else 1):
        raise QualificationError("journal sequence is not contiguous")
    if value.get("prior_event_digest") != (previous["event_digest"] if previous else None):
        raise QualificationError("journal hash chain is broken")
    material = {key: item for key, item in value.items() if key != "event_digest"}
    if value.get("event_digest") != digest(material):
        raise QualificationError("journal event digest is invalid")


def _connect_readonly(database: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='table'")}


def _latest_by_cycle(connection: sqlite3.Connection, table: str, cycle_id: str) -> dict[str, Any] | None:
    order = "decided_revision DESC" if table == "outcome_verdict" else "origin_revision DESC"
    row = connection.execute(f"SELECT * FROM {table} WHERE cycle_id=? ORDER BY {order} LIMIT 1", (cycle_id,)).fetchone()
    return dict(row) if row else None


def independent_closure(connection: sqlite3.Connection) -> dict[str, Any]:
    """Rebuild closure only from authority tables; never read product paths, blockers, or rollups."""
    tables = _table_names(connection)
    required = {"closure_element", "lineage_claim", "requirement", "closure_record", "recovery_case"}
    if not required <= tables:
        return {"available": False, "reason": "closure-authority-tables-unavailable", "elements": {}}
    elements = {str(row["id"]): dict(row) for row in connection.execute("SELECT * FROM closure_element ORDER BY id")}
    requirements = {str(row["id"]): dict(row) for row in connection.execute("SELECT * FROM requirement")}
    children: dict[str, list[tuple[str, str | None]]] = {key: [] for key in elements}
    findings: dict[str, set[str]] = {key: set() for key in elements}
    parents: dict[str, list[str]] = {key: [] for key in elements}

    for parent in elements.values():
        if parent["role"] != "cycle":
            continue
        for child in elements.values():
            requirement = requirements.get(str(child.get("requirement_id")))
            if child["role"] == "obligation" and requirement and str(requirement["cycle_id"]) == str(parent["cycle_id"]):
                if requirement["disposition"] not in {"not-applicable", "retired", "superseded"}:
                    children[parent["id"]].append((child["id"], child.get("requirement_id")))
    for row in connection.execute("SELECT * FROM lineage_claim WHERE retired_revision IS NULL ORDER BY id"):
        child_id, parent_id, requirement_id = map(str, (row["child_element_id"], row["parent_element_id"], row["parent_requirement_id"]))
        if child_id not in elements or parent_id not in elements:
            findings.setdefault(child_id, set()).add("MISSING_PARENT")
            continue
        parents[child_id].append(parent_id)
        if requirement_id not in requirements:
            findings[child_id].add("MISSING_REQUIREMENT")
            continue
        requirement = requirements[requirement_id]
        digest_fields = (
            "id", "cycle_id", "origin_artifact_id", "accepted_outcome", "disposition",
            "accepted_revision", "milestone_key", "evidence_gate_key",
        )
        if "observed_requirement_digest" in row.keys() and all(field in requirement for field in digest_fields):
            observed = digest({field: requirement[field] for field in digest_fields})
            if str(row["observed_requirement_digest"]) != observed:
                findings[child_id].add("CONFLICTING_LINEAGE")
        if row["relationship_type"] in {"fulfills", "contributes"}:
            obligation = next((item for item in elements.values() if str(item.get("requirement_id")) == requirement_id), None)
            if obligation and child_id != obligation["id"]:
                children[obligation["id"]].append((child_id, requirement_id))
    for value in children.values():
        value.sort()

    visiting: list[str] = []
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            for member in visiting[visiting.index(node):]:
                findings[member].add("CYCLE")
            return
        if node in visited:
            return
        visiting.append(node)
        for parent in parents.get(node, []):
            visit(parent)
        visiting.pop()
        visited.add(node)

    for element_id in sorted(elements):
        visit(element_id)

    recovery: dict[str, set[str]] = {}
    for row in connection.execute("SELECT element_id, reason_code, state FROM recovery_case WHERE element_id IS NOT NULL"):
        if row["state"] in {"open", "retry-wait", "escalated"}:
            recovery.setdefault(str(row["element_id"]), set()).add(str(row["reason_code"]))

    memo: dict[str, dict[str, Any]] = {}
    active: set[str] = set()

    def evaluate(element_id: str) -> dict[str, Any]:
        if element_id in memo:
            return memo[element_id]
        if element_id in active:
            return {"local_closure": "open", "evidence_health": "not-required", "graph_health": "invalid", "effective_closed": False, "reason_codes": ["CYCLE"], "open_descendants": 0, "invalid_descendants": 1, "unknown_descendants": 0}
        active.add(element_id)
        element = elements[element_id]
        closure = connection.execute(
            "SELECT method,evidence_health FROM closure_record WHERE element_id=? AND superseded_revision IS NULL ORDER BY created_revision DESC,id DESC LIMIT 1",
            (element_id,),
        ).fetchone()
        local = str(closure["method"]) if closure else "open"
        evidence = str(closure["evidence_health"]) if closure else "not-required"
        reasons = set(findings.get(element_id, set())) | recovery.get(element_id, set())
        graph = "invalid" if "CYCLE" in reasons or "CONFLICTING_LINEAGE" in reasons else "valid"
        if recovery.get(element_id) or {"MISSING_PARENT", "MISSING_REQUIREMENT"} & reasons:
            graph = "recovery-required"
        child_results = [evaluate(child_id) for child_id, _ in children[element_id] if child_id in elements]
        derived = element["role"] == "obligation" and bool(child_results) and all(item["effective_closed"] for item in child_results)
        if derived and local == "open":
            local, evidence = "closed-loop", "current"
        if local == "open" and not derived:
            reasons.add("LOCAL_OPEN")
        if element["role"] == "obligation" and not child_results and local == "open":
            reasons.add("UNFULFILLED_REQUIREMENT")
        if any(not item["effective_closed"] for item in child_results):
            reasons.add("DESCENDANT_OPEN")
        evidence_reasons = {"missing": "UNPROVEN", "stale": "STALE_EVIDENCE", "checker-error": "CHECKER_ERROR"}
        if evidence in evidence_reasons:
            reasons.add(evidence_reasons[evidence])
        effective = local in {"closed-loop", "closed-manual"} and evidence in {"not-required", "current"} and graph == "valid" and all(item["effective_closed"] for item in child_results)
        result = {
            "local_closure": local,
            "evidence_health": evidence,
            "graph_health": graph,
            "effective_closed": effective,
            "reason_codes": sorted(reasons),
            "open_descendants": sum((not item["effective_closed"]) + int(item["open_descendants"]) for item in child_results),
            "unknown_descendants": sum(int(item["unknown_descendants"]) for item in child_results),
            "invalid_descendants": sum(int(item["invalid_descendants"]) for item in child_results) + int(graph != "valid"),
        }
        active.remove(element_id)
        memo[element_id] = result
        return result

    for element_id in sorted(elements):
        evaluate(element_id)
    return {"available": True, "oracle_version": ORACLE_VERSION, "elements": memo}


def compare_closure_projection(connection: sqlite3.Connection, oracle: dict[str, Any]) -> list[dict[str, Any]]:
    if not oracle["available"]:
        return []
    mismatches: list[dict[str, Any]] = []
    stored = {str(row["element_id"]): dict(row) for row in connection.execute("SELECT * FROM closure_rollup")}
    for element_id, expected in oracle["elements"].items():
        actual = stored.get(element_id)
        if not actual:
            mismatches.append({"element_id": element_id, "field": "row", "expected": "present", "actual": "missing"})
            continue
        values = {
            "local_closure": actual["local_closure"],
            "evidence_health": actual["evidence_health"],
            "graph_health": actual["graph_health"],
            "effective_closed": bool(actual["effective_closed"]),
            "reason_codes": sorted(json.loads(actual["reason_codes_json"])),
            "open_descendants": int(actual["open_descendants"]),
            "unknown_descendants": int(actual["unknown_descendants"]),
            "invalid_descendants": int(actual["invalid_descendants"]),
        }
        for field, expected_value in expected.items():
            if field in values and values[field] != expected_value:
                mismatches.append({"element_id": element_id, "field": field, "expected": expected_value, "actual": values[field]})
    for unexpected in sorted(set(stored) - set(oracle["elements"])):
        mismatches.append({"element_id": unexpected, "field": "row", "expected": "absent", "actual": "unexpected"})
    return mismatches


def observe_local(database: Path, run_id: str) -> dict[str, Any]:
    connection = _connect_readonly(database)
    try:
        tables = _table_names(connection)
        meta = dict(connection.execute("SELECT * FROM state_meta WHERE id=1").fetchone()) if "state_meta" in tables else {}
        documents: list[dict[str, Any]] = []
        if "document" in tables:
            for row in connection.execute("SELECT d.*,a.type FROM document d JOIN artifact a ON a.id=d.id ORDER BY d.visible_id"):
                metadata = json.loads(row["metadata_json"])
                if metadata.get("qualification_run_id") == run_id:
                    documents.append({"artifact_id": row["id"], "visible_id": row["visible_id"], "type": row["type"], "lifecycle": row["lifecycle_state"], "revision": row["current_revision"]})
        artifact_ids = [item["artifact_id"] for item in documents]
        cycles: list[dict[str, Any]] = []
        requirements: list[dict[str, Any]] = []
        if artifact_ids:
            marks = ",".join("?" for _ in artifact_ids)
            cycles = [dict(row) for row in connection.execute(f"SELECT * FROM cycle WHERE origin_artifact_id IN ({marks}) ORDER BY opened_at,id", artifact_ids)]
            cycle_ids = [item["id"] for item in cycles]
            if cycle_ids:
                cycle_marks = ",".join("?" for _ in cycle_ids)
                requirements = [dict(row) for row in connection.execute(f"SELECT * FROM requirement WHERE cycle_id IN ({cycle_marks}) ORDER BY id", cycle_ids)]
                for cycle in cycles:
                    cycle["verdict"] = _latest_by_cycle(connection, "outcome_verdict", cycle["id"])
                    cycle["reconciliation"] = _latest_by_cycle(connection, "reconciliation", cycle["id"])
        relationships: list[dict[str, Any]] = []
        if artifact_ids:
            marks = ",".join("?" for _ in artifact_ids)
            relationships = [dict(row) for row in connection.execute(
                f"SELECT id,from_artifact_id,relation_type,to_artifact_id,created_revision,retired_revision FROM relationship WHERE retired_revision IS NULL AND (from_artifact_id IN ({marks}) OR to_artifact_id IN ({marks})) ORDER BY created_revision,id",
                [*artifact_ids, *artifact_ids],
            )]
        closure = independent_closure(connection)
        projection_mismatches = compare_closure_projection(connection, closure) if "closure_rollup" in tables else []
        run_cycle_ids = {item["id"] for item in cycles}
        run_requirement_ids = {item["id"] for item in requirements}
        closure_elements: dict[str, dict[str, Any]] = {}
        if closure["available"] and run_cycle_ids:
            for row in connection.execute("SELECT id,role,cycle_id,requirement_id FROM closure_element ORDER BY id"):
                identity = dict(row)
                if identity.get("cycle_id") not in run_cycle_ids and identity.get("requirement_id") not in run_requirement_ids:
                    continue
                element_id = str(identity["id"])
                closure_elements[element_id] = {**identity, **closure["elements"][element_id]}
        return {
            "schema_version": 1,
            "kind": TRUTH_KIND,
            "run_id": run_id,
            "source": {"layer": "local-sqlite", "authority_class": "authoritative", "database": database.name},
            "database": {"schema": connection.execute("PRAGMA user_version").fetchone()[0], "revision": meta.get("current_revision"), "dirty": bool(meta.get("dirty", 0)) if meta else None},
            "documents": documents,
            "cycles": cycles,
            "requirements": requirements,
            "relationships": relationships,
            "closure": {"available": closure["available"], "elements": closure_elements, "projection_mismatches": projection_mismatches},
        }
    finally:
        connection.close()


def evaluate_qh001(scenario: dict[str, Any], dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    expected = set(scenario.get("expectations", {}).get("operational_project_names", []))
    projects = dashboard.get("projects", [])
    instances = dashboard.get("instances", [])
    visible = [item for item in projects if not item.get("is_hidden")]
    visible_names = {str(item.get("name")) for item in visible}
    checks = [
        {"id": "QH001-EXACT-PROJECT-SET", "passed": visible_names == expected, "expected": sorted(expected), "actual": sorted(visible_names)},
        {"id": "QH001-SEEDS-NOT-OPERATIONAL", "passed": not any(str(item.get("external_id")) in SEED_PROJECT_IDS for item in visible), "expected": [], "actual": sorted(str(item.get("external_id")) for item in visible if str(item.get("external_id")) in SEED_PROJECT_IDS)},
        {"id": "QH001-UNIQUE-PROJECT-IDS", "passed": len({str(item.get("external_id")) for item in projects}) == len(projects), "expected": len(projects), "actual": len({str(item.get("external_id")) for item in projects})},
    ]
    operational_ids = {str(item.get("external_id")) for item in visible}
    operational_instances = [item for item in instances if str(item.get("project_external_id")) in operational_ids]
    pairs = [(str(item.get("project_external_id")), str(item.get("external_id"))) for item in operational_instances]
    checks.append({"id": "QH001-ONE-UNIQUE-INSTANCE-PER-PROJECT", "passed": len(pairs) == len(set(pairs)) == len(expected), "expected": len(expected), "actual": len(pairs)})
    return checks


def evaluate_qh002(scenario: dict[str, Any], local: dict[str, Any]) -> list[dict[str, Any]]:
    documents = local["documents"]
    cycles = local["cycles"]
    relationships = local["relationships"]
    expected_types = set(scenario.get("expectations", {}).get("document_types", []))
    actual_types = {item["type"] for item in documents}
    terminal = [item for item in cycles if item["lifecycle_state"] == "terminal" and item.get("verdict", {}).get("disposition") == "satisfied" and item.get("reconciliation", {}).get("state") == "reconciled"]
    artifact_ids = {item["artifact_id"] for item in documents}
    parent_edges = {(item["from_artifact_id"], item["to_artifact_id"]) for item in relationships if item["relation_type"] == "outcome-parent" and item["from_artifact_id"] in artifact_ids and item["to_artifact_id"] in artifact_ids}
    propagated = {(item["from_artifact_id"], item["to_artifact_id"]) for item in relationships if item["relation_type"] == "outcome-result-propagated" and item["from_artifact_id"] in artifact_ids and item["to_artifact_id"] in artifact_ids}
    expected_cycle_ids = {item["id"] for item in cycles}
    closure_elements = local["closure"]["elements"]
    projected_cycle_ids = {
        item["cycle_id"] for item in closure_elements.values()
        if item.get("role") == "cycle" and item.get("cycle_id") in expected_cycle_ids
    }
    closure_projection_actual = {
        "missing_cycles": sorted(expected_cycle_ids - projected_cycle_ids),
        "open_elements": sorted(
            element_id for element_id, item in closure_elements.items()
            if not item.get("effective_closed")
        ),
        "projection_mismatches": local["closure"]["projection_mismatches"][:20],
    }
    closure_projection_passed = (
        local["closure"]["available"]
        and projected_cycle_ids == expected_cycle_ids
        and bool(closure_elements)
        and not closure_projection_actual["open_elements"]
        and not closure_projection_actual["projection_mismatches"]
    )
    checks = [
        {"id": "QH002-EXACT-DOCUMENT-TYPES", "passed": actual_types == expected_types and len(documents) == len(expected_types), "expected": sorted(expected_types), "actual": sorted(actual_types)},
        {"id": "QH002-DOCUMENTS-COMPLETED", "passed": len(documents) == len(expected_types) and all(item["lifecycle"] == "completed" for item in documents), "expected": len(expected_types), "actual": sum(item["lifecycle"] == "completed" for item in documents)},
        {"id": "QH002-OUTCOMES-TERMINAL-RECONCILED", "passed": len(terminal) == len(expected_types), "expected": len(expected_types), "actual": len(terminal)},
        {"id": "QH002-PARENT-CHAIN", "passed": len(parent_edges) == max(0, len(expected_types) - 1), "expected": max(0, len(expected_types) - 1), "actual": len(parent_edges)},
        {"id": "QH002-PROPAGATED-CHAIN", "passed": parent_edges == propagated, "expected": sorted(parent_edges), "actual": sorted(propagated)},
        {"id": "QH002-NO-ACTIVE-RUN-RESIDUE", "passed": not any(item["lifecycle"] != "completed" for item in documents) and not any(item["lifecycle_state"] != "terminal" for item in cycles), "expected": 0, "actual": sum(item["lifecycle"] != "completed" for item in documents) + sum(item["lifecycle_state"] != "terminal" for item in cycles)},
        {"id": "QH002-CLOSURE-PROJECTION-PARITY", "passed": closure_projection_passed, "expected": {"missing_cycles": [], "open_elements": [], "projection_mismatches": []}, "actual": closure_projection_actual},
    ]
    return checks


def evaluate_qh002_hosted(
    scenario: dict[str, Any],
    local: dict[str, Any],
    dashboard: dict[str, Any],
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compare the run's authoritative document identities with the hosted projection."""
    expected_types = set(scenario.get("expectations", {}).get("document_types", []))
    local_by_id = {item["artifact_id"]: item for item in local["documents"]}
    projected = [
        item for item in dashboard.get("work_artifacts", [])
        if item.get("artifact_external_id") in local_by_id
    ]
    projected_by_id = {item["artifact_external_id"]: item for item in projected}
    expected_ids = set(local_by_id)
    actual_ids = set(projected_by_id)
    identity_errors = [
        artifact_id for artifact_id, item in projected_by_id.items()
        if item.get("project_external_id") != manifest["fixture"]["project_id"]
        or item.get("instance_external_id") != manifest["fixture"]["instance_id"]
        or item.get("artifact_type") != local_by_id[artifact_id]["type"]
    ]
    state_errors = [
        artifact_id for artifact_id, item in projected_by_id.items()
        if item.get("document_lifecycle") != "completed"
        or item.get("outcome_lifecycle") != "terminal"
        or item.get("outcome_disposition") != "satisfied"
        or item.get("reconciliation_state") != "reconciled"
        or item.get("closure_status", {}).get("effective_closed") is not True
    ]
    return [
        {
            "id": "QH002-HOSTED-EXACT-RUN-SET",
            "passed": expected_ids == actual_ids and len(expected_ids) == len(expected_types),
            "expected": sorted(expected_ids),
            "actual": sorted(actual_ids),
        },
        {
            "id": "QH002-HOSTED-IDENTITY-PARITY",
            "passed": not identity_errors and expected_ids == actual_ids,
            "expected": [],
            "actual": sorted(identity_errors),
        },
        {
            "id": "QH002-HOSTED-TERMINAL-CLOSED",
            "passed": not state_errors and expected_ids == actual_ids,
            "expected": [],
            "actual": sorted(state_errors),
        },
    ]


def _hosted_instance(
    dashboard: dict[str, Any], project_id: str, instance_id: str
) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in dashboard.get("instances", [])
            if str(item.get("project_external_id")) == project_id
            and str(item.get("external_id")) == instance_id
        ),
        None,
    )


def _canonical_closure(value: object) -> object:
    if not isinstance(value, dict):
        return value
    normalized = dict(value)
    observed = normalized.get("evaluated_at")
    if isinstance(observed, str):
        try:
            parsed = datetime.fromisoformat(observed.replace("Z", "+00:00"))
        except ValueError:
            pass
        else:
            normalized["evaluated_at"] = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return normalized


def evaluate_hosted_truth(
    transport: dict[str, Any],
    dashboard: dict[str, Any],
    browser: dict[str, Any],
    manifest: dict[str, Any],
    *,
    prefix: str,
) -> list[dict[str, Any]]:
    """Compare one reporter truth record with hosted rows and browser claims."""
    project_id = str(manifest["fixture"]["project_id"])
    instance_id = str(manifest["fixture"]["instance_id"])
    latest = transport.get("latest_payload") or {}
    inventory = latest.get("work_inventory") or {}
    expected_items = inventory.get("artifacts") or []
    expected_by_id = {str(item.get("artifact_id")): item for item in expected_items}
    hosted_items = [
        item
        for item in dashboard.get("work_artifacts", [])
        if str(item.get("project_external_id")) == project_id
        and str(item.get("instance_external_id")) == instance_id
    ]
    hosted_by_id = {str(item.get("artifact_external_id")): item for item in hosted_items}
    hosted_instance = _hosted_instance(dashboard, project_id, instance_id)
    state_errors: list[str] = []
    for artifact_id in sorted(set(expected_by_id) & set(hosted_by_id)):
        source = expected_by_id[artifact_id]
        hosted = hosted_by_id[artifact_id]
        for source_field, hosted_field in (
            ("visible_id", "visible_id"),
            ("artifact_type", "artifact_type"),
            ("title", "title"),
            ("document_lifecycle", "document_lifecycle"),
            ("outcome_lifecycle", "outcome_lifecycle"),
            ("outcome_disposition", "outcome_disposition"),
            ("reconciliation_state", "reconciliation_state"),
            ("parent_ids", "parent_ids"),
            ("produces_ids", "produces_ids"),
            ("closure_status", "closure_status"),
        ):
            source_value = source.get(source_field)
            hosted_value = hosted.get(hosted_field)
            if source_field == "closure_status":
                source_value = _canonical_closure(source_value)
                hosted_value = _canonical_closure(hosted_value)
            if source_value != hosted_value:
                state_errors.append(f"{artifact_id}:{source_field}")
    expected_ids = set(expected_by_id)
    hosted_ids = set(hosted_by_id)
    receipt_keys = [
        str(item.get("idempotency_key"))
        for item in dashboard.get("ingest_receipts", [])
        if str(item.get("instance_external_id")) == instance_id
    ]
    accepted_keys = sorted(str(item) for item in transport.get("accepted_idempotency_keys", []))
    browser_project = next(
        (
            item
            for item in browser.get("projects", [])
            if str(item.get("name")) == str(transport.get("project_name"))
        ),
        None,
    )
    browser_ids = set((browser_project or {}).get("work_artifact_ids") or [])
    return [
        {
            "id": f"{prefix}-TRANSPORT-IDENTITY",
            "passed": transport.get("run_id") == manifest["run_id"]
            and str(transport.get("project_id")) == project_id
            and str(transport.get("instance_id")) == instance_id,
            "expected": [manifest["run_id"], project_id, instance_id],
            "actual": [transport.get("run_id"), transport.get("project_id"), transport.get("instance_id")],
        },
        {
            "id": f"{prefix}-HOSTED-EXACT-WORK-SET",
            "passed": expected_ids == hosted_ids and len(hosted_items) == len(hosted_by_id),
            "expected": sorted(expected_ids),
            "actual": sorted(hosted_ids),
        },
        {
            "id": f"{prefix}-HOSTED-FIELD-PARITY",
            "passed": not state_errors and expected_ids == hosted_ids,
            "expected": [],
            "actual": state_errors[:40],
        },
        {
            "id": f"{prefix}-HOSTED-CURRENT-SEQUENCE",
            "passed": hosted_instance is not None
            and hosted_instance.get("last_sequence") == latest.get("sequence")
            and hosted_instance.get("work_inventory_sequence") == latest.get("sequence")
            and hosted_instance.get("work_inventory_total") == inventory.get("total_count"),
            "expected": [latest.get("sequence"), inventory.get("total_count")],
            "actual": None
            if hosted_instance is None
            else [hosted_instance.get("last_sequence"), hosted_instance.get("work_inventory_total")],
        },
        {
            "id": f"{prefix}-RECEIPTS-EXACT-AND-UNIQUE",
            "passed": sorted(receipt_keys) == accepted_keys and len(receipt_keys) == len(set(receipt_keys)),
            "expected": accepted_keys,
            "actual": sorted(receipt_keys),
        },
        {
            "id": f"{prefix}-BROWSER-INVENTORY-AND-WORK",
            "passed": browser.get("links_ok") is True
            and browser_project is not None
            and browser_ids == {str(item.get("visible_id")) for item in expected_items},
            "expected": sorted(str(item.get("visible_id")) for item in expected_items),
            "actual": sorted(browser_ids),
        },
        {
            "id": f"{prefix}-BROWSER-FRESHNESS",
            "passed": browser_project is not None
            and browser_project.get("freshness") == "fresh"
            and browser_project.get("attention_state") not in {"stale", "unknown"},
            "expected": "fresh",
            "actual": None if browser_project is None else browser_project.get("freshness"),
        },
    ]


def evaluate_qualification_namespace(
    transport: dict[str, Any],
    dashboard: dict[str, Any],
    browser: dict[str, Any],
    manifest: dict[str, Any],
    *,
    prefix: str,
) -> list[dict[str, Any]]:
    """Prove hosted qualification truth without treating it as operational inventory."""
    run_id = str(manifest["run_id"])
    project_id = str(manifest["fixture"]["project_id"])
    instance_id = str(manifest["fixture"]["instance_id"])
    runs = [item for item in dashboard.get("qualification_runs", []) if item.get("run_id") == run_id]
    projects = [item for item in dashboard.get("projects", []) if item.get("external_id") == project_id]
    instances = [
        item
        for item in dashboard.get("instances", [])
        if item.get("external_id") == instance_id and item.get("project_external_id") == project_id
    ]
    latest = transport.get("latest_payload") or {}
    inventory = latest.get("work_inventory") or {}
    expected = {str(item.get("artifact_id")) for item in inventory.get("artifacts", [])}
    hosted = {
        str(item.get("artifact_external_id"))
        for item in dashboard.get("work_artifacts", [])
        if item.get("project_external_id") == project_id and item.get("instance_external_id") == instance_id
    }
    browser_runs = {str(item.get("run_id")) for item in browser.get("qualification_runs", [])}
    operational_names = set(browser.get("project_names") or [])
    run = runs[0] if len(runs) == 1 else {}
    return [
        {
            "id": f"{prefix}-QUALIFICATION-ROOT-EXACT",
            "passed": len(runs) == 1
            and run.get("manifest_digest") == manifest.get("manifest_digest")
            and run.get("candidate_commit") == manifest.get("candidate", {}).get("commit")
            and run.get("scenario_id") == manifest.get("scenario", {}).get("id")
            and run.get("environment") == "development"
            and run.get("status") == "active",
            "expected": [run_id, manifest.get("manifest_digest"), "development", "active"],
            "actual": [run.get("run_id"), run.get("manifest_digest"), run.get("environment"), run.get("status")],
        },
        {
            "id": f"{prefix}-MANIFEST-OWNED-LINEAGE",
            "passed": len(projects) == 1
            and projects[0].get("qualification_run_id") == run_id
            and len(instances) == 1
            and run.get("project_ids") == [project_id],
            "expected": {"project": project_id, "instance": instance_id, "run": run_id},
            "actual": {"projects": projects, "instance_count": len(instances), "root_project_ids": run.get("project_ids")},
        },
        {
            "id": f"{prefix}-QUALIFICATION-SCOPE-ONLY",
            "passed": transport.get("credential_scope") == "qualification:write"
            and transport.get("qualification_run_id") == run_id,
            "expected": ["qualification:write", run_id],
            "actual": [transport.get("credential_scope"), transport.get("qualification_run_id")],
        },
        {
            "id": f"{prefix}-HOSTED-EXACT-ARTIFACT-SET",
            "passed": expected == hosted and len(expected) == int(inventory.get("total_count", -1)),
            "expected": sorted(expected),
            "actual": sorted(hosted),
        },
        {
            "id": f"{prefix}-OPERATIONAL-ABSENCE",
            "passed": str(transport.get("project_name")) not in operational_names,
            "expected": "qualification project absent from operational browser inventory",
            "actual": sorted(operational_names),
        },
        {
            "id": f"{prefix}-AUTHENTICATED-QUALIFICATION-VISIBILITY",
            "passed": browser.get("requested_qualification_run_visible") is True and run_id in browser_runs,
            "expected": run_id,
            "actual": sorted(browser_runs),
        },
    ]


def evaluate_qh007(
    transport: dict[str, Any],
    dashboard: dict[str, Any],
    browser: dict[str, Any],
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    outage = transport.get("outage") or {}
    delivery = transport.get("delivery") or {}
    submissions = delivery.get("submissions") or []
    statuses = [str(item.get("status")) for item in submissions]
    sequences = [int(item.get("sequence", -1)) for item in transport.get("queued", [])]
    checks = [
        {
            "id": "QH007-OUTAGE-RETAINED-PENDING",
            "passed": outage.get("status") == "unavailable"
            and int(outage.get("pending_count", 0)) >= 2
            and int(outage.get("latest_sequence", 0)) > int(outage.get("hosted_sequence", 0))
            and outage.get("browser_freshness") == "stale",
            "expected": "unavailable with at least two newer queued reports",
            "actual": outage,
        },
        {
            "id": "QH007-QUEUED-SEQUENCE-MONOTONIC",
            "passed": bool(sequences)
            and sequences == sorted(sequences)
            and len(sequences) == len(set(sequences)),
            "expected": sorted(set(sequences)),
            "actual": sequences,
        },
        {
            "id": "QH007-REORDER-DUPLICATE-CLASSIFIED",
            "passed": "accepted" in statuses and "duplicate" in statuses and "stale" in statuses,
            "expected": ["accepted", "duplicate", "stale"],
            "actual": statuses,
        },
        {
            "id": "QH007-OUTBOX-DRAINED",
            "passed": delivery.get("pending_count") == 0,
            "expected": 0,
            "actual": delivery.get("pending_count"),
        },
    ]
    return checks + evaluate_hosted_truth(
        transport, dashboard, browser, manifest, prefix="QH007"
    )


def result_summary(manifest: dict[str, Any], checks: list[dict[str, Any]], *, evidence: list[dict[str, Any]], replay: list[str]) -> dict[str, Any]:
    validate_manifest(manifest)
    verdict = "PASS" if checks and all(item.get("passed") is True for item in checks) else "PRODUCT-FAIL"
    result = {
        "schema_version": 1,
        "kind": RESULT_KIND,
        "run_id": manifest["run_id"],
        "manifest_digest": manifest["manifest_digest"],
        "scenario_id": manifest["scenario"]["id"],
        "checkpoint_id": manifest["scenario"]["checkpoint_id"],
        "verdict": verdict,
        "oracle_version": ORACLE_VERSION,
        "checks": checks,
        "first_divergence": next((item["id"] for item in checks if not item.get("passed")), None),
        "evidence": evidence,
        "replay": replay,
    }
    result["result_digest"] = digest(result)
    return result


def validate_result(value: dict[str, Any]) -> None:
    if value.get("schema_version") != 1 or value.get("kind") != RESULT_KIND or value.get("verdict") not in VERDICTS:
        raise QualificationError("unsupported qualification result")
    material = {key: item for key, item in value.items() if key != "result_digest"}
    if value.get("result_digest") != digest(material):
        raise QualificationError("qualification result digest is invalid")


def drive_qh002(workspace: Path, manifest: dict[str, Any], *, project_binding: str) -> dict[str, Any]:
    """Drive one append-only Idea→Map→PRM→Campaign lifecycle through guarded services."""
    validate_manifest(manifest)
    if manifest["scenario"]["id"] != "QH-002":
        raise QualificationError("drive supports QH-002 only")
    if manifest["target"]["environment"] != "development":
        raise QualificationError("normal lifecycle driver is restricted to development")
    scripts = Path(__file__).resolve().parent
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import document_store  # type: ignore
    import hybrid_state  # type: ignore
    import outcome_loop  # type: ignore

    workspace = workspace.resolve()
    run_id = manifest["run_id"]
    runtime = workspace / ".tool-shed" / "qualification" / "runs" / run_id
    runtime.mkdir(parents=True, exist_ok=True)
    journal = runtime / "journal.jsonl"
    database = workspace / ".tool-shed" / "state.sqlite3"
    existing = observe_local(database, run_id)
    if existing["documents"]:
        checks = evaluate_qh002(load_json(scenario_path("QH-002"), label="scenario"), existing)
        if all(item["passed"] for item in checks):
            return {"run_id": run_id, "resumed": True, "truth": existing, "checks": checks}
        raise QualificationError("run identity already exists but is not at a verified terminal checkpoint")

    def log(action: str, state: str, payload: object) -> None:
        append_journal(journal, {"run_id": run_id, "action": action, "state": state, "logical_tick": len(journal.read_text(encoding="utf-8").splitlines()) + 1 if journal.exists() else 1, "idempotency_key": digest([run_id, action]), "payload_digest": digest(payload)})

    types = [("idea-brief", "Qualification Idea"), ("project-map", "Qualification Map"), ("program-roadmap", "Qualification Roadmap"), ("campaign", "Qualification Campaign")]
    documents: list[dict[str, Any]] = []
    cycles: list[str] = []
    for document_type, label in types:
        body = f"# {label}: {run_id}\n\nStatus: active\nType: {document_type}\nQualification Run: {run_id}\n"
        created = document_store.create_document(workspace, project_binding=project_binding, document_type=document_type, title=f"{label} {run_id}", body=body, lifecycle="active", metadata={"qualification_run_id": run_id, "qualification_scenario": "QH-002"}, actor="lifecycle-qualification", reason="QH-002 deterministic lifecycle")
        documents.append(created["result"])
        opened = document_store.open_outcome(workspace, project_binding=project_binding, identity=created["result"]["visible_id"], accepted_outcome=f"Complete {label} for {run_id}", actor="lifecycle-qualification")
        cycles.append(opened["result"]["cycle_id"])
        log(f"create-{document_type}", "passed", {"document": created["result"], "cycle": opened["result"]})
    for parent, child in zip(documents, documents[1:]):
        document_store.relate(workspace, project_binding=project_binding, source=parent["visible_id"], relation="produces", target=child["visible_id"], actor="lifecycle-qualification")
        document_store.relate(workspace, project_binding=project_binding, source=child["visible_id"], relation="outcome-parent", target=parent["visible_id"], actor="lifecycle-qualification")
    log("link-lineage", "passed", [item["visible_id"] for item in documents])

    evidence_path = runtime / "driver-evidence.json"
    evidence_value = {"schema_version": 1, "kind": "tool-shed-qualification-driver-evidence", "run_id": run_id, "status": "passed", "manifest_digest": manifest["manifest_digest"]}
    evidence_path.write_text(json.dumps(evidence_value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    installed_scenario = (
        workspace
        / "tool_shed"
        / "schemas"
        / "lifecycle-qualification"
        / "v1"
        / "scenarios"
        / "QH-002.json"
    )
    selected_scenario = installed_scenario if installed_scenario.is_file() else scenario_path("QH-002")
    scenario_relative = selected_scenario.relative_to(workspace)
    evidence_relative = evidence_path.relative_to(workspace)
    direct = outcome_loop.plan_direct_result(workspace, origin_summary=f"QH-002 governed work evidence {run_id}", accepted_outcome=f"Produce passing governed work evidence for {run_id}", product_truth=[scenario_relative.as_posix()], evidence_paths=[evidence_relative.as_posix()], disposition="satisfied", authorization_ref="QH-002 development fixture manifest", parent_cycle_id=cycles[-1])
    direct_result = outcome_loop.apply_manifest(workspace, direct, expected_token=direct["manifest_token"], project_binding=project_binding)
    child_cycle = direct_result["result"]["cycle_id"]
    log("complete-governed-work", "passed", direct_result["result"])

    supporting = child_cycle
    for index in range(len(cycles) - 1, -1, -1):
        transition = outcome_loop.prepare_transition(workspace, cycles[index], lifecycle_state="terminal", disposition="satisfied", reconciliation_state="reconciled", summary=f"QH-002 checkpoint closed {documents[index]['visible_id']}", authorization_ref="QH-002 development fixture manifest", supporting_cycle_ids=[supporting], residual_work=[])
        outcome_loop.apply_transition(workspace, transition, expected_token=transition["manifest_token"], project_binding=project_binding)
        current = document_store.show(workspace, documents[index]["visible_id"])
        document_store.set_lifecycle(workspace, project_binding=project_binding, identity=documents[index]["visible_id"], lifecycle="completed", expected_revision=current["document_revision"], actor="lifecycle-qualification", reason="QH-002 terminal reconciled outcome")
        supporting = cycles[index]
        log(f"close-{documents[index]['visible_id']}", "passed", {"cycle_id": supporting})

    truth = observe_local(database, run_id)
    scenario = load_json(scenario_path("QH-002"), label="scenario")
    checks = evaluate_qh002(scenario, truth)
    return {"run_id": run_id, "resumed": False, "truth": truth, "checks": checks, "journal": journal.relative_to(workspace).as_posix()}


def drive_local_corpus(workspace: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Drive one M2 local scenario in an isolated database below the OS fixture."""
    validate_manifest(manifest)
    supported = {"QH-003", "QH-004", "QH-005", "QH-006", "QH-008", "QH-009", "QH-010"}
    scenario_id = str(manifest["scenario"]["id"])
    if scenario_id not in supported:
        raise QualificationError(f"local corpus driver does not support {scenario_id}")
    if manifest["target"]["environment"] != "development":
        raise QualificationError("local corpus driver is restricted to development")
    scripts = Path(__file__).resolve().parent
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import lifecycle_qualification_scenarios  # type: ignore

    prior_state_root = os.environ.get("TOOL_SHED_STATE_ROOT")
    isolated_state = (
        Path(tempfile.gettempdir())
        / "tool-shed-qualification-state"
        / str(manifest["run_id"])
    )
    os.environ["TOOL_SHED_STATE_ROOT"] = str(isolated_state)
    try:
        return lifecycle_qualification_scenarios.drive(
            workspace,
            manifest,
            oracle=independent_closure,
            compare=compare_closure_projection,
        )
    except RuntimeError as error:
        raise QualificationError(str(error)) from error
    finally:
        if prior_state_root is None:
            os.environ.pop("TOOL_SHED_STATE_ROOT", None)
        else:
            os.environ["TOOL_SHED_STATE_ROOT"] = prior_state_root


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def qualification_run_manifest(workspace: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(manifest)
    from project_identity import load_project_identity

    identity = load_project_identity(workspace)
    if str(identity["project_id"]) != str(manifest["fixture"]["project_id"]):
        raise QualificationError("qualification source project does not match the sealed manifest")
    return {
        "run_id": manifest["run_id"],
        "manifest_digest": manifest["manifest_digest"],
        "candidate_commit": manifest["candidate"]["commit"],
        "scenario_id": manifest["scenario"]["id"],
        "platform": manifest["target"]["platform"],
        "project": {"id": identity["project_id"], "name": identity["project_name"]},
        "instance": {
            "id": manifest["fixture"]["instance_id"],
            "platform": manifest["target"]["platform"],
            "client_version": manifest["candidate"]["version"],
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    seal = commands.add_parser("seal")
    seal.add_argument("--scenario", required=True); seal.add_argument("--candidate-commit", required=True); seal.add_argument("--candidate-version", required=True)
    seal.add_argument("--platform", required=True); seal.add_argument("--project-id", required=True); seal.add_argument("--instance-id", required=True)
    seal.add_argument("--serial", required=True, type=int); seal.add_argument("--seed", type=int, default=0); seal.add_argument("--target-environment", default="development"); seal.add_argument("--checkpoint")
    seal.add_argument("--baseline-digest", required=True); seal.add_argument("--output", required=True)
    observe = commands.add_parser("observe-local"); observe.add_argument("--database", required=True); observe.add_argument("--run-id", required=True); observe.add_argument("--output")
    evaluate = commands.add_parser("evaluate"); evaluate.add_argument("--manifest", required=True); evaluate.add_argument("--local"); evaluate.add_argument("--transport"); evaluate.add_argument("--dashboard"); evaluate.add_argument("--browser"); evaluate.add_argument("--qualification-namespace", action="store_true"); evaluate.add_argument("--output", required=True)
    drive = commands.add_parser("drive-qh002"); drive.add_argument("--workspace", required=True); drive.add_argument("--manifest", required=True); drive.add_argument("--project-binding", required=True); drive.add_argument("--output", required=True)
    local_drive = commands.add_parser("drive-local"); local_drive.add_argument("--workspace", required=True); local_drive.add_argument("--manifest", required=True); local_drive.add_argument("--output", required=True)
    root_manifest = commands.add_parser("qualification-root"); root_manifest.add_argument("--workspace", required=True); root_manifest.add_argument("--manifest", required=True); root_manifest.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "seal":
            scenario = load_json(scenario_path(args.scenario), label="scenario")
            result = seal_manifest(scenario, candidate_commit=args.candidate_commit, candidate_version=args.candidate_version, platform_name=args.platform, project_id=args.project_id, instance_id=args.instance_id, serial=args.serial, seed=args.seed, target_environment=args.target_environment, baseline_digest=args.baseline_digest, checkpoint_id=args.checkpoint)
            _write_json(Path(args.output), result)
        elif args.command == "observe-local":
            result = observe_local(Path(args.database), args.run_id)
            if args.output: _write_json(Path(args.output), result)
        elif args.command == "drive-qh002":
            manifest = load_json(Path(args.manifest), label="manifest")
            result = drive_qh002(Path(args.workspace), manifest, project_binding=args.project_binding)
            _write_json(Path(args.output), result)
        elif args.command == "drive-local":
            manifest = load_json(Path(args.manifest), label="manifest")
            result = drive_local_corpus(Path(args.workspace), manifest)
            _write_json(Path(args.output), result)
        elif args.command == "qualification-root":
            manifest = load_json(Path(args.manifest), label="manifest")
            result = qualification_run_manifest(Path(args.workspace), manifest)
            _write_json(Path(args.output), result)
        else:
            manifest = load_json(Path(args.manifest), label="manifest")
            validate_manifest(manifest)
            scenario = load_json(scenario_path(manifest["scenario"]["id"]), label="scenario")
            if scenario["scenario_id"] == "QH-001":
                if not args.dashboard: raise QualificationError("QH-001 requires --dashboard")
                dashboard = load_json(Path(args.dashboard), label="dashboard snapshot")
                checks = evaluate_qh001(scenario, dashboard)
                evidence = [{"layer": "hosted-projection", "sha256": file_digest(Path(args.dashboard)), "path": Path(args.dashboard).name}]
                if args.browser:
                    browser = load_json(Path(args.browser), label="browser snapshot")
                    expected_names = set(scenario.get("expectations", {}).get("operational_project_names", []))
                    actual_names = set(browser.get("project_names") or [])
                    checks.append({"id": "QH001-BROWSER-EXACT-PROJECT-SET", "passed": browser.get("links_ok") is True and actual_names == expected_names, "expected": sorted(expected_names), "actual": sorted(actual_names)})
                    evidence.append({"layer": "browser", "sha256": file_digest(Path(args.browser)), "path": Path(args.browser).name})
            elif scenario["scenario_id"] == "QH-007":
                if not args.transport or not args.dashboard or not args.browser:
                    raise QualificationError("QH-007 requires --transport, --dashboard, and --browser")
                transport = load_json(Path(args.transport), label="transport record")
                dashboard = load_json(Path(args.dashboard), label="dashboard snapshot")
                browser = load_json(Path(args.browser), label="browser snapshot")
                checks = evaluate_qh007(transport, dashboard, browser, manifest)
                evidence = [
                    {"layer": "transport-record", "sha256": file_digest(Path(args.transport)), "path": Path(args.transport).name},
                    {"layer": "hosted-projection", "sha256": file_digest(Path(args.dashboard)), "path": Path(args.dashboard).name},
                    {"layer": "browser", "sha256": file_digest(Path(args.browser)), "path": Path(args.browser).name},
                ]
            elif scenario["scenario_id"] == "QH-002":
                if not args.local: raise QualificationError("QH-002 requires --local")
                if not args.dashboard: raise QualificationError("QH-002 requires --dashboard")
                local = load_json(Path(args.local), label="local truth vector")
                dashboard = load_json(Path(args.dashboard), label="dashboard snapshot")
                checks = evaluate_qh002(scenario, local) + evaluate_qh002_hosted(scenario, local, dashboard, manifest)
                evidence = [
                    {"layer": "local-sqlite", "sha256": file_digest(Path(args.local)), "path": Path(args.local).name},
                    {"layer": "hosted-projection", "sha256": file_digest(Path(args.dashboard)), "path": Path(args.dashboard).name},
                ]
            elif scenario["scenario_id"] in {"QH-003", "QH-004", "QH-005", "QH-006", "QH-008", "QH-009", "QH-010"}:
                if not args.local: raise QualificationError(f"{scenario['scenario_id']} requires --local")
                local = load_json(Path(args.local), label="local drive result")
                if local.get("run_id") != manifest["run_id"] or local.get("scenario_id") != scenario["scenario_id"]:
                    raise QualificationError("local drive result does not match the sealed run")
                checks = list(local.get("checks") or [])
                if not checks:
                    raise QualificationError("local drive result has no invariant checks")
                evidence = [{"layer": "local-sqlite", "sha256": file_digest(Path(args.local)), "path": Path(args.local).name}]
                if scenario["scenario_id"] in {"QH-008", "QH-009", "QH-010"} and any((args.transport, args.dashboard, args.browser)):
                    if not args.transport or not args.dashboard or not args.browser:
                        raise QualificationError(f"hosted {scenario['scenario_id']} requires --transport, --dashboard, and --browser")
                    transport = load_json(Path(args.transport), label="transport record")
                    dashboard = load_json(Path(args.dashboard), label="dashboard snapshot")
                    browser = load_json(Path(args.browser), label="browser snapshot")
                    evaluator = evaluate_qualification_namespace if args.qualification_namespace else evaluate_hosted_truth
                    checks += evaluator(
                        transport,
                        dashboard,
                        browser,
                        manifest,
                        prefix=scenario["scenario_id"].replace("-", ""),
                    )
                    evidence += [
                        {"layer": "transport-record", "sha256": file_digest(Path(args.transport)), "path": Path(args.transport).name},
                        {"layer": "hosted-projection", "sha256": file_digest(Path(args.dashboard)), "path": Path(args.dashboard).name},
                        {"layer": "browser", "sha256": file_digest(Path(args.browser)), "path": Path(args.browser).name},
                    ]
            else:
                raise QualificationError("scenario evaluator is not implemented")
            result = result_summary(manifest, checks, evidence=evidence, replay=["python3 scripts/lifecycle_qualification.py evaluate", "--manifest", Path(args.manifest).name])
            _write_json(Path(args.output), result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if result.get("verdict") in {"PRODUCT-FAIL", "HARNESS-FAIL", "INFRA-BLOCKED"} else 0
    except (QualificationError, OSError, sqlite3.DatabaseError, ValueError) as error:
        print(f"Lifecycle qualification failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
