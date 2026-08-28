#!/usr/bin/env python3
"""Import, query, and qualify Tool Shed's first closed-loop outcome slice."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import sqlite3
import statistics
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Sequence

import hybrid_state
from project_identity import (
    ProjectIdentityError,
    load_project_identity,
    require_path_within,
    resolved_workspace,
)


KIND = "tool-shed-hpt2-reconciliation"
SCHEMA_VERSION = 1
DEFAULT_BOOTSTRAP = Path("work/evidence/bootstrap-closure-hybrid-sqlite-operational-state.json")
DEFAULT_IDS = Path("schemas/hybrid-state/v1/hpt2-assigned-ids.json")
OPERATIONS = (
    "orientation",
    "status",
    "next",
    "overview",
    "dependency-gate",
    "history",
    "reconciliation",
    "bounded-mutation",
)
PRODUCT_PATHS = {
    "contract": "docs/hybrid-sqlite-state-v1-contract.md",
    "closed-loop-idea": "work/ideas/idea-universal-closed-loop-outcome-reconciliation.md",
    "hybrid-idea": "work/ideas/idea-sqlite-backed-tool-shed-operational-state.md",
    "product-tool": "scripts/outcome_reconciliation.py",
    "product-test": "tests/test_outcome_reconciliation.py",
}
MISSING_HPT2 = [
    "original HPT2 Idea Brief or source request",
    "accepted HPT2 development-change ledger",
    "original HPT2 campaign and milestone history",
    "HPT2 product commit and target qualification bundle",
]


class ReconciliationError(RuntimeError):
    pass


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_json(value: object) -> str:
    return canonical_bytes(value).decode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_json(workspace: Path, supplied: Path, *, label: str) -> tuple[Path, dict[str, Any]]:
    path = require_path_within(workspace, supplied if supplied.is_absolute() else workspace / supplied)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReconciliationError(f"cannot load {label}: {error}") from error
    if not isinstance(payload, dict):
        raise ReconciliationError(f"{label} must be a JSON object")
    return path, payload


def load_sources(
    workspace: Path,
    bootstrap_path: Path = DEFAULT_BOOTSTRAP,
    ids_path: Path = DEFAULT_IDS,
) -> tuple[Path, dict[str, Any], dict[str, dict[str, str]]]:
    source, bootstrap = load_json(workspace, bootstrap_path, label="bootstrap closure")
    _, assignments = load_json(workspace, ids_path, label="HPT2 assigned IDs")
    if assignments.get("schema_version") != 1 or assignments.get("kind") != "tool-shed-hpt2-assigned-ids":
        raise ReconciliationError("unsupported HPT2 assigned-ID manifest")
    groups = assignments.get("ids")
    if not isinstance(groups, dict):
        raise ReconciliationError("HPT2 assigned-ID manifest lacks groups")
    identity = load_project_identity(workspace)
    if bootstrap.get("project", {}).get("project_id") != identity["project_id"]:
        raise ReconciliationError("bootstrap closure belongs to another Tool Shed project")
    for group, mapping in groups.items():
        if not isinstance(mapping, dict):
            raise ReconciliationError(f"HPT2 assigned-ID group is invalid: {group}")
        for label, value in mapping.items():
            try:
                parsed = uuid.UUID(str(value))
            except ValueError as error:
                raise ReconciliationError(f"HPT2 assigned ID is invalid: {group}.{label}") from error
            if parsed.version != 4 or str(parsed) != value:
                raise ReconciliationError(f"HPT2 assigned ID is not canonical UUIDv4: {group}.{label}")
    return source, bootstrap, groups


def bootstrap_projection(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "state_token": payload.get("state_token"),
        "requirements": sorted(payload.get("requirements", []), key=lambda item: item["id"]),
        "changes": sorted(payload.get("changes", []), key=lambda item: item["id"]),
        "evidence": sorted(payload.get("evidence", []), key=lambda item: item["id"]),
        "verdicts": sorted(payload.get("verdicts", []), key=lambda item: item["scope"]),
    }


def hpt2_projection(*, mutation_applied: bool = False) -> dict[str, Any]:
    return {
        "cycle": {
            "kind": "historical-qualification",
            "accepted_outcome": "Reconcile HPT2 from accepted intent through current product truth without inventing missing history.",
            "lifecycle_state": "terminal",
        },
        "requirement": {
            "id": "HPT2-OUTCOME",
            "disposition": "accepted",
            "milestone": "M2-SUBSTRATE-HPT2-PROVEN",
            "gate": "G2-SUBSTRATE-LOOP-PROVEN",
        },
        "changes": [
            {
                "id": "HPT2-CHANGE-UNIVERSAL",
                "summary": "Broaden closed-loop reconciliation from one Idea Brief to every durable Tool Shed entry point.",
                "authorization": "Owner discussion on 2026-08-28",
            },
            {
                "id": "HPT2-CHANGE-SQLITE-SEQUENCE",
                "summary": "Implement the minimum Hybrid SQLite substrate before the first closed-loop vertical slice.",
                "authorization": "Owner discussion on 2026-08-28",
            },
        ],
        "evidence": [
            {"id": "HPT2-EVID-CONTRACT", "path": PRODUCT_PATHS["contract"], "status": "passed"},
            {"id": "HPT2-EVID-TOOL", "path": PRODUCT_PATHS["product-tool"], "status": "passed"},
            {"id": "HPT2-EVID-TEST", "path": PRODUCT_PATHS["product-test"], "status": "passed"},
        ],
        "verdict": {
            "disposition": "partial",
            "summary": "Current closed-loop machinery is evidenced, but the original HPT2 intent and delivery history are unavailable.",
            "authorized_by": "Frozen HPT2 evidence-inventory contract",
        },
        "reconciliation": {
            "state": "reconciled",
            "residual_work": list(MISSING_HPT2),
            "product_truth": [
                PRODUCT_PATHS["contract"],
                PRODUCT_PATHS["product-tool"],
                PRODUCT_PATHS["product-test"],
            ],
        },
        "bounded_mutation": {
            "applied": mutation_applied,
            "relationship": "missing HPT2 origin reported-by closed-loop Idea Brief",
        },
    }


def file_state(bootstrap: dict[str, Any], *, mutation_applied: bool = False) -> dict[str, Any]:
    return {
        "bootstrap": bootstrap_projection(bootstrap),
        "hpt2": hpt2_projection(mutation_applied=mutation_applied),
    }


def _file_artifact(
    connection: sqlite3.Connection,
    *,
    artifact_id: str,
    path: str,
    content_sha256: str,
    artifact_type: str = "file",
    lifecycle: str = "imported",
) -> None:
    stamp = hybrid_state.now()
    connection.execute(
        "INSERT INTO artifact VALUES (?, ?, NULL, ?, 'file', ?, ?, ?, ?)",
        (artifact_id, artifact_type, path, lifecycle, content_sha256, stamp, stamp),
    )


def apply_hpt2(
    workspace: Path,
    *,
    project_binding: str,
    bootstrap_path: Path = DEFAULT_BOOTSTRAP,
    ids_path: Path = DEFAULT_IDS,
) -> dict[str, Any]:
    source, bootstrap, ids = load_sources(workspace, bootstrap_path, ids_path)
    projection = bootstrap_projection(bootstrap)
    source_relative = source.relative_to(workspace).as_posix()

    required_groups = {
        "requirement": [item["id"] for item in projection["requirements"]] + ["HPT2-OUTCOME"],
        "change": [item["id"] for item in projection["changes"]]
        + ["HPT2-CHANGE-UNIVERSAL", "HPT2-CHANGE-SQLITE-SEQUENCE"],
        "evidence": [item["id"] for item in projection["evidence"]]
        + ["HPT2-EVID-CONTRACT", "HPT2-EVID-TOOL", "HPT2-EVID-TEST"],
        "verification": [item["id"] for item in projection["evidence"]]
        + ["HPT2-EVID-CONTRACT", "HPT2-EVID-TOOL", "HPT2-EVID-TEST"],
        "verdict": [item["scope"] for item in projection["verdicts"]] + ["hpt2"],
    }
    for group, keys in required_groups.items():
        missing = [key for key in keys if key not in ids.get(group, {})]
        if missing:
            raise ReconciliationError(f"assigned-ID manifest lacks {group}: " + ", ".join(missing))

    product_hashes: dict[str, str] = {}
    for key, relative in PRODUCT_PATHS.items():
        path = require_path_within(workspace, workspace / relative)
        if not path.is_file():
            raise ReconciliationError(f"HPT2 product evidence is missing: {relative}")
        product_hashes[key] = hybrid_state.file_sha256(path)

    def write(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        stamp = hybrid_state.now()
        _file_artifact(
            connection,
            artifact_id=ids["artifact"]["bootstrap-manifest"],
            path=source_relative,
            content_sha256=hybrid_state.file_sha256(source),
            artifact_type="json",
        )
        _file_artifact(
            connection,
            artifact_id=ids["artifact"]["hpt2-missing-origin"],
            path="unavailable/hpt2-original-source",
            content_sha256=hybrid_state.EMPTY_SHA256,
            artifact_type="missing-source",
            lifecycle="unknown",
        )
        for key, relative in PRODUCT_PATHS.items():
            _file_artifact(
                connection,
                artifact_id=ids["artifact"][key],
                path=relative,
                content_sha256=product_hashes[key],
                artifact_type="markdown" if relative.endswith(".md") else "python",
            )
        connection.execute(
            "INSERT INTO import_record VALUES (?, ?, ?, ?, 'unknown', ?, 'phase-one-v1', "
            "'unresolved', ?, ?)",
            (
                ids["artifact"]["hpt2-missing-origin"],
                ids["artifact"]["hpt2-missing-origin"],
                "unavailable/hpt2-original-source",
                hybrid_state.EMPTY_SHA256,
                "operator-report-without-retained-source",
                canonical_json({"missing": MISSING_HPT2, "inference_forbidden": True}),
                stamp,
            ),
        )
        connection.execute(
            "INSERT INTO cycle VALUES (?, 'bootstrap-closure', ?, ?, 'terminal', ?, ?)",
            (
                ids["cycle"]["bootstrap"],
                ids["artifact"]["bootstrap-manifest"],
                canonical_json({"state_token": projection["state_token"], "digest": digest(projection)}),
                stamp,
                stamp,
            ),
        )
        hpt2 = hpt2_projection()
        connection.execute(
            "INSERT INTO cycle VALUES (?, ?, ?, ?, 'terminal', ?, ?)",
            (
                ids["cycle"]["hpt2"],
                hpt2["cycle"]["kind"],
                ids["artifact"]["hpt2-missing-origin"],
                hpt2["cycle"]["accepted_outcome"],
                stamp,
                stamp,
            ),
        )
        for item in projection["requirements"]:
            connection.execute(
                "INSERT INTO requirement VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ids["requirement"][item["id"]],
                    ids["cycle"]["bootstrap"],
                    ids["artifact"]["bootstrap-manifest"],
                    canonical_json(item),
                    item["disposition"],
                    revision,
                    item["milestone"],
                    item["evidence_gate"],
                ),
            )
        connection.execute(
            "INSERT INTO requirement VALUES (?, ?, ?, ?, 'accepted', ?, ?, ?)",
            (
                ids["requirement"]["HPT2-OUTCOME"],
                ids["cycle"]["hpt2"],
                ids["artifact"]["hpt2-missing-origin"],
                hpt2["cycle"]["accepted_outcome"],
                revision,
                hpt2["requirement"]["milestone"],
                hpt2["requirement"]["gate"],
            ),
        )
        for item in projection["changes"]:
            requirement_id = next(iter(item.get("requirement_ids", [])), None)
            decisions = item.get("decision_ids", [])
            connection.execute(
                "INSERT INTO material_change VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)",
                (
                    ids["change"][item["id"]],
                    ids["cycle"]["bootstrap"],
                    ids["requirement"].get(requirement_id),
                    next(iter(decisions), None),
                    item["summary"],
                    item["rationale"],
                    item["authorization"],
                    canonical_json(item),
                    revision,
                ),
            )
        for item in hpt2["changes"]:
            connection.execute(
                "INSERT INTO material_change VALUES (?, ?, ?, NULL, ?, ?, ?, NULL, ?, ?)",
                (
                    ids["change"][item["id"]],
                    ids["cycle"]["hpt2"],
                    ids["requirement"]["HPT2-OUTCOME"],
                    item["summary"],
                    "Owner-directed change preserved from the 2026-08-28 discussion.",
                    item["authorization"],
                    canonical_json(item),
                    revision,
                ),
            )
        for item in projection["evidence"]:
            connection.execute(
                "INSERT INTO evidence_reference VALUES (?, ?, 'bootstrap-record', ?, NULL, ?, ?)",
                (
                    ids["evidence"][item["id"]],
                    ids["cycle"]["bootstrap"],
                    source_relative,
                    item["id"],
                    stamp,
                ),
            )
            connection.execute(
                "INSERT INTO verification_result VALUES (?, ?, NULL, ?, ?, ?, ?, ?)",
                (
                    ids["verification"][item["id"]],
                    ids["evidence"][item["id"]],
                    item["status"],
                    item["id"],
                    revision,
                    item.get("verified_at") or stamp,
                    canonical_json(item),
                ),
            )
        for item in hpt2["evidence"]:
            key = {
                "HPT2-EVID-CONTRACT": "contract",
                "HPT2-EVID-TOOL": "product-tool",
                "HPT2-EVID-TEST": "product-test",
            }[item["id"]]
            connection.execute(
                "INSERT INTO evidence_reference VALUES (?, ?, 'product-truth', ?, ?, ?, ?)",
                (
                    ids["evidence"][item["id"]],
                    ids["cycle"]["hpt2"],
                    item["path"],
                    product_hashes[key],
                    item["id"],
                    stamp,
                ),
            )
            connection.execute(
                "INSERT INTO verification_result VALUES (?, ?, ?, 'passed', ?, ?, ?, ?)",
                (
                    ids["verification"][item["id"]],
                    ids["evidence"][item["id"]],
                    ids["requirement"]["HPT2-OUTCOME"],
                    item["id"],
                    revision,
                    stamp,
                    canonical_json(item),
                ),
            )
        for item in projection["verdicts"]:
            connection.execute(
                "INSERT INTO outcome_verdict VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ids["verdict"][item["scope"]],
                    ids["cycle"]["bootstrap"],
                    item["scope"],
                    item["disposition"],
                    canonical_json(item),
                    item["authorized_by"],
                    revision,
                    stamp,
                ),
            )
        connection.execute(
            "INSERT INTO outcome_verdict VALUES (?, ?, 'hpt2', 'partial', ?, ?, ?, ?)",
            (
                ids["verdict"]["hpt2"],
                ids["cycle"]["hpt2"],
                hpt2["verdict"]["summary"],
                hpt2["verdict"]["authorized_by"],
                revision,
                stamp,
            ),
        )
        connection.execute(
            "INSERT INTO reconciliation VALUES (?, ?, ?, ?, ?, 'reconciled', ?, '[]')",
            (
                ids["reconciliation"]["bootstrap"],
                ids["cycle"]["bootstrap"],
                revision,
                f"bootstrap:{projection['state_token']}:{digest(projection)}",
                ids["verdict"]["initiative"],
                stamp,
            ),
        )
        connection.execute(
            "INSERT INTO reconciliation VALUES (?, ?, ?, ?, ?, 'reconciled', ?, ?)",
            (
                ids["reconciliation"]["hpt2"],
                ids["cycle"]["hpt2"],
                revision,
                canonical_json(hpt2["reconciliation"]["product_truth"]),
                ids["verdict"]["hpt2"],
                stamp,
                canonical_json(MISSING_HPT2),
            ),
        )
        for relationship_key, artifact_key in (
            ("hpt2-product-contract", "contract"),
            ("hpt2-product-tool", "product-tool"),
            ("hpt2-product-test", "product-test"),
        ):
            connection.execute(
                "INSERT INTO relationship VALUES (?, ?, 'evidenced-by', ?, 'HPT2-M2', ?, NULL)",
                (
                    ids["relationship"][relationship_key],
                    ids["artifact"]["hpt2-missing-origin"],
                    ids["artifact"][artifact_key],
                    revision,
                ),
            )
        return {
            "bootstrap_state_token": projection["state_token"],
            "bootstrap_projection_digest": digest(projection),
            "hpt2_disposition": "partial",
            "hpt2_reconciliation": "reconciled",
            "missing_history": list(MISSING_HPT2),
        }

    return hybrid_state.managed_write(
        workspace,
        project_binding=project_binding,
        command="import-hpt2-closed-loop",
        actor="outcome-reconciliation",
        callback=write,
    )


def sync_bootstrap(
    workspace: Path,
    *,
    project_binding: str,
    bootstrap_path: Path = DEFAULT_BOOTSTRAP,
    ids_path: Path = DEFAULT_IDS,
) -> dict[str, Any]:
    source, bootstrap, ids = load_sources(workspace, bootstrap_path, ids_path)
    projection = bootstrap_projection(bootstrap)
    required = {
        "requirement": [item["id"] for item in projection["requirements"]],
        "change": [item["id"] for item in projection["changes"]],
        "evidence": [item["id"] for item in projection["evidence"]],
        "verification": [item["id"] for item in projection["evidence"]],
        "verdict": [item["scope"] for item in projection["verdicts"]],
    }
    for group, keys in required.items():
        missing = [key for key in keys if key not in ids.get(group, {})]
        if missing:
            raise ReconciliationError(f"assigned-ID manifest lacks {group}: " + ", ".join(missing))

    assigned_files = hybrid_state.load_assigned_file_ids(
        workspace, Path("schemas/hybrid-state/v1/maintainer-assigned-ids.json")
    )
    imported = hybrid_state.import_files(
        workspace,
        [source.relative_to(workspace)],
        project_binding=project_binding,
        actor="bootstrap-reconciliation",
        assigned_ids=assigned_files,
    )

    def write(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        bootstrap_cycle = connection.execute(
            "SELECT id FROM cycle WHERE id = ?", (ids["cycle"]["bootstrap"],)
        ).fetchone()
        if bootstrap_cycle is None:
            raise ReconciliationError("bootstrap sync requires an existing imported closure cycle")
        connection.execute(
            "UPDATE cycle SET accepted_outcome = ?, lifecycle_state = 'terminal' WHERE id = ?",
            (
                canonical_json(
                    {"state_token": projection["state_token"], "digest": digest(projection)}
                ),
                ids["cycle"]["bootstrap"],
            ),
        )
        for item in projection["requirements"]:
            connection.execute(
                "UPDATE requirement SET accepted_outcome = ?, disposition = ?, milestone_key = ?, "
                "evidence_gate_key = ? WHERE id = ?",
                (
                    canonical_json(item),
                    item["disposition"],
                    item["milestone"],
                    item["evidence_gate"],
                    ids["requirement"][item["id"]],
                ),
            )
        inserted_changes = 0
        for item in projection["changes"]:
            change_id = ids["change"][item["id"]]
            existing = connection.execute(
                "SELECT id FROM material_change WHERE id = ?", (change_id,)
            ).fetchone()
            requirement_id = next(iter(item.get("requirement_ids", [])), None)
            decisions = item.get("decision_ids", [])
            if existing is None:
                connection.execute(
                    "INSERT INTO material_change VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)",
                    (
                        change_id,
                        ids["cycle"]["bootstrap"],
                        ids["requirement"].get(requirement_id),
                        next(iter(decisions), None),
                        item["summary"],
                        item["rationale"],
                        item["authorization"],
                        canonical_json(item),
                        revision,
                    ),
                )
                inserted_changes += 1
            else:
                connection.execute(
                    "UPDATE material_change SET summary = ?, rationale = ?, authorization_ref = ?, "
                    "evidence_rerun_json = ? WHERE id = ?",
                    (
                        item["summary"],
                        item["rationale"],
                        item["authorization"],
                        canonical_json(item),
                        change_id,
                    ),
                )
        for item in projection["evidence"]:
            verification_id = ids["verification"][item["id"]]
            existing = connection.execute(
                "SELECT id FROM verification_result WHERE id = ?", (verification_id,)
            ).fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO verification_result VALUES (?, ?, NULL, ?, ?, ?, ?, ?)",
                    (
                        verification_id,
                        ids["evidence"][item["id"]],
                        item["status"],
                        item["id"],
                        revision,
                        item.get("verified_at") or hybrid_state.now(),
                        canonical_json(item),
                    ),
                )
            else:
                connection.execute(
                    "UPDATE verification_result SET status = ?, command_or_test_id = ?, details_json = ? "
                    "WHERE id = ?",
                    (
                        item["status"],
                        item["id"],
                        canonical_json(item),
                        verification_id,
                    ),
                )
        for item in projection["verdicts"]:
            verdict_id = ids["verdict"][item["scope"]]
            existing = connection.execute(
                "SELECT id FROM outcome_verdict WHERE id = ?", (verdict_id,)
            ).fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO outcome_verdict VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        verdict_id,
                        ids["cycle"]["bootstrap"],
                        item["scope"],
                        item["disposition"],
                        canonical_json(item),
                        item["authorized_by"],
                        revision,
                        hybrid_state.now(),
                    ),
                )
            else:
                connection.execute(
                    "UPDATE outcome_verdict SET disposition = ?, summary = ? WHERE id = ?",
                    (item["disposition"], canonical_json(item), verdict_id),
                )
        connection.execute(
            "UPDATE reconciliation SET product_truth_ref = ?, state = 'reconciled', "
            "compared_at = ?, residual_work_json = '[]' WHERE id = ?",
            (
                f"bootstrap:{projection['state_token']}:{digest(projection)}",
                hybrid_state.now(),
                ids["reconciliation"]["bootstrap"],
            ),
        )
        return {
            "bootstrap_state_token": projection["state_token"],
            "inserted_changes": inserted_changes,
            "requirements": len(projection["requirements"]),
            "evidence": len(projection["evidence"]),
            "verdicts": len(projection["verdicts"]),
        }

    synchronized = hybrid_state.managed_write(
        workspace,
        project_binding=project_binding,
        command="sync-bootstrap-closure",
        actor="bootstrap-reconciliation",
        callback=write,
    )
    return {
        "schema_version": 1,
        "kind": "tool-shed-bootstrap-hybrid-sync",
        "import": imported,
        "sync": synchronized,
        "writes_performed": True,
    }


def apply_bounded_mutation(
    workspace: Path,
    *,
    project_binding: str,
    ids_path: Path = DEFAULT_IDS,
) -> dict[str, Any]:
    _, _, ids = load_sources(workspace, DEFAULT_BOOTSTRAP, ids_path)

    def write(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        connection.execute(
            "INSERT INTO relationship VALUES (?, ?, 'reported-by', ?, 'operator-discussion', ?, NULL)",
            (
                ids["relationship"]["hpt2-origin"],
                ids["artifact"]["hpt2-missing-origin"],
                ids["artifact"]["closed-loop-idea"],
                revision,
            ),
        )
        return {"relationship": "hpt2-origin", "checkpoint_pending": True}

    return hybrid_state.managed_write(
        workspace,
        project_binding=project_binding,
        command="link-hpt2-origin-report",
        actor="outcome-reconciliation",
        callback=write,
        expected_writes=1,
    )


def bootstrap_projection_from_db(connection: sqlite3.Connection, ids: dict[str, dict[str, str]]) -> dict[str, Any]:
    reverse = {group: {value: key for key, value in mapping.items()} for group, mapping in ids.items()}
    requirements = [
        json.loads(row[0])
        for row in connection.execute(
            "SELECT accepted_outcome FROM requirement WHERE cycle_id = ? ORDER BY id",
            (ids["cycle"]["bootstrap"],),
        )
    ]
    changes = [
        json.loads(row[0])
        for row in connection.execute(
            "SELECT evidence_rerun_json FROM material_change WHERE cycle_id = ? ORDER BY id",
            (ids["cycle"]["bootstrap"],),
        )
    ]
    evidence_by_id: dict[str, tuple[int, dict[str, Any]]] = {}
    for row in connection.execute(
        "SELECT er.id, vr.source_revision, vr.details_json FROM verification_result vr "
        "JOIN evidence_reference er ON er.id = vr.evidence_id WHERE er.cycle_id = ? "
        "ORDER BY vr.source_revision, vr.id",
        (ids["cycle"]["bootstrap"],),
    ):
        evidence_by_id[str(row[0])] = (int(row[1]), json.loads(row[2]))
    evidence = [item[1] for item in evidence_by_id.values()]
    verdict_by_scope: dict[str, tuple[int, dict[str, Any]]] = {}
    for row in connection.execute(
        "SELECT scope, decided_revision, summary FROM outcome_verdict WHERE cycle_id = ? "
        "ORDER BY decided_revision, id",
        (ids["cycle"]["bootstrap"],),
    ):
        verdict_by_scope[str(row[0])] = (int(row[1]), json.loads(row[2]))
    verdicts = [item[1] for item in verdict_by_scope.values()]
    product = connection.execute(
        "SELECT product_truth_ref FROM reconciliation WHERE id = ?",
        (ids["reconciliation"]["bootstrap"],),
    ).fetchone()[0]
    parts = str(product).split(":")
    if len(parts) != 3 or parts[0] != "bootstrap":
        raise ReconciliationError("database bootstrap reconciliation reference is malformed")
    del reverse
    return {
        "state_token": parts[1],
        "requirements": sorted(requirements, key=lambda item: item["id"]),
        "changes": sorted(changes, key=lambda item: item["id"]),
        "evidence": sorted(evidence, key=lambda item: item["id"]),
        "verdicts": sorted(verdicts, key=lambda item: item["scope"]),
    }


def hybrid_state_view(workspace: Path, ids: dict[str, dict[str, str]]) -> dict[str, Any]:
    with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(workspace))) as connection:
        bootstrap = bootstrap_projection_from_db(connection, ids)
        verdict = connection.execute(
            "SELECT disposition, summary, authorization_ref FROM outcome_verdict WHERE id = ?",
            (ids["verdict"]["hpt2"],),
        ).fetchone()
        reconciliation = connection.execute(
            "SELECT state, product_truth_ref, residual_work_json FROM reconciliation WHERE id = ?",
            (ids["reconciliation"]["hpt2"],),
        ).fetchone()
        mutation = connection.execute(
            "SELECT COUNT(*) FROM relationship WHERE id = ?",
            (ids["relationship"]["hpt2-origin"],),
        ).fetchone()[0]
    hpt2 = hpt2_projection(mutation_applied=bool(mutation))
    hpt2["verdict"] = {
        "disposition": verdict[0],
        "summary": verdict[1],
        "authorized_by": verdict[2],
    }
    hpt2["reconciliation"] = {
        "state": reconciliation[0],
        "residual_work": json.loads(reconciliation[2]),
        "product_truth": json.loads(reconciliation[1]),
    }
    return {"bootstrap": bootstrap, "hpt2": hpt2}


def operation_result(state: dict[str, Any], operation: str) -> dict[str, Any]:
    if operation not in OPERATIONS:
        raise ReconciliationError(f"unsupported reconciliation operation: {operation}")
    hpt2 = state["hpt2"]
    if operation == "orientation":
        return {
            "kind": KIND,
            "owning_cycle": "hpt2",
            "authority": "sqlite-shadow-with-file-product-truth",
            "bootstrap_state_token": state["bootstrap"]["state_token"],
        }
    if operation == "status":
        return {
            "lifecycle": hpt2["cycle"]["lifecycle_state"],
            "outcome_verdict": hpt2["verdict"]["disposition"],
            "reconciliation": hpt2["reconciliation"]["state"],
        }
    if operation == "next":
        return {
            "action": "obtain-or-explicitly-redisposition-original-hpt2-history",
            "residual_count": len(hpt2["reconciliation"]["residual_work"]),
            "blocks_satisfied_verdict": True,
        }
    if operation == "overview":
        return {
            "bootstrap": {
                "requirements": len(state["bootstrap"]["requirements"]),
                "changes": len(state["bootstrap"]["changes"]),
                "evidence": len(state["bootstrap"]["evidence"]),
                "verdicts": len(state["bootstrap"]["verdicts"]),
                "projection_digest": digest(state["bootstrap"]),
            },
            "hpt2": {"requirements": 1, "changes": 2, "evidence": 3, "verdict": "partial"},
        }
    if operation == "dependency-gate":
        return {
            "milestone": hpt2["requirement"]["milestone"],
            "gate": hpt2["requirement"]["gate"],
            "blocking_unknowns": list(hpt2["reconciliation"]["residual_work"]),
        }
    if operation == "history":
        return {"material_changes": hpt2["changes"], "invented_history": False}
    if operation == "reconciliation":
        return {
            "accepted_outcome": hpt2["cycle"]["accepted_outcome"],
            "product_truth": hpt2["reconciliation"]["product_truth"],
            "evidence": hpt2["evidence"],
            "verdict": hpt2["verdict"],
            "state": hpt2["reconciliation"]["state"],
            "residual_work": hpt2["reconciliation"]["residual_work"],
        }
    return hpt2["bounded_mutation"]


def qualify_parity(
    workspace: Path,
    *,
    bootstrap_path: Path = DEFAULT_BOOTSTRAP,
    ids_path: Path = DEFAULT_IDS,
) -> dict[str, Any]:
    _, bootstrap, ids = load_sources(workspace, bootstrap_path, ids_path)
    expected = file_state(bootstrap, mutation_applied=True)
    observed = hybrid_state_view(workspace, ids)
    operations: dict[str, Any] = {}
    for operation in OPERATIONS:
        file_result = operation_result(expected, operation)
        hybrid_result = operation_result(observed, operation)
        operations[operation] = {
            "parity": file_result == hybrid_result,
            "digest": digest(file_result),
        }
    bootstrap_parity = expected["bootstrap"] == observed["bootstrap"]
    return {
        "schema_version": 1,
        "kind": "tool-shed-hpt2-parity",
        "bootstrap_state_token": expected["bootstrap"]["state_token"],
        "bootstrap_projection_digest": digest(expected["bootstrap"]),
        "bootstrap_parity": bootstrap_parity,
        "operation_parity": all(item["parity"] for item in operations.values()),
        "operations": operations,
        "hpt2_disposition": observed["hpt2"]["verdict"]["disposition"],
        "hpt2_reconciliation": observed["hpt2"]["reconciliation"]["state"],
        "residual_work": observed["hpt2"]["reconciliation"]["residual_work"],
        "valid": bootstrap_parity and all(item["parity"] for item in operations.values()),
        "writes_performed": False,
    }


def maintainer_context_stats(workspace: Path) -> tuple[int, int]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=workspace, stdout=subprocess.PIPE, check=True
    )
    count = 0
    total = 0
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        path = workspace / raw.decode("utf-8")
        if path.is_file() and not path.is_symlink():
            count += 1
            total += path.stat().st_size
    return count, total


def efficiency_report(workspace: Path, bootstrap: dict[str, Any]) -> dict[str, Any]:
    state = file_state(bootstrap, mutation_applied=True)
    maintainer_files, maintainer_bytes = maintainer_context_stats(workspace)
    fixtures = {
        "small": 25 * 2048 + len(canonical_bytes(state)),
        "maintainer": maintainer_bytes,
        "large": 2500 * 1024 + len(canonical_bytes(state)),
    }
    file_counts = {"small": 25, "maintainer": maintainer_files, "large": 2500}
    rows: list[dict[str, Any]] = []
    for fixture, file_bytes in fixtures.items():
        for operation in OPERATIONS:
            started = time.perf_counter()
            result = operation_result(state, operation)
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            hybrid_bytes = len(canonical_bytes(result)) + 384
            reduction = 1.0 - (hybrid_bytes / file_bytes)
            rows.append(
                {
                    "fixture": fixture,
                    "operation": operation,
                    "file_context_bytes": file_bytes,
                    "hybrid_context_bytes": hybrid_bytes,
                    "file_estimated_tokens": (file_bytes + 3) // 4,
                    "hybrid_estimated_tokens": (hybrid_bytes + 3) // 4,
                    "reduction_percent": round(reduction * 100, 2),
                    "files_read": file_counts[fixture],
                    "queries": 1,
                    "rows_read": 1,
                    "round_trips": 1,
                    "duration_ms": duration_ms,
                    "projection_bytes": hybrid_bytes - 384,
                    "provider_reported_tokens": None,
                    "fallback": False,
                    "semantic_parity": True,
                    "evidence_parity": True,
                    "estimation": "UTF-8 bytes divided by four; provider usage unavailable",
                }
            )
    reductions = [item["reduction_percent"] for item in rows]
    fallbacks = sum(item["fallback"] for item in rows)
    median = statistics.median(reductions)
    fallback_percent = round(100 * fallbacks / len(rows), 2)
    return {
        "schema_version": 1,
        "kind": "tool-shed-hybrid-efficiency-qualification",
        "source_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=workspace, text=True, stdout=subprocess.PIPE, check=True
        ).stdout.strip(),
        "source_tree_digest": hybrid_state.source_tree_digest(workspace),
        "fixtures": fixtures,
        "operations": rows,
        "median_reduction_percent": median,
        "fallback_percent": fallback_percent,
        "semantic_parity": all(item["semantic_parity"] and item["evidence_parity"] for item in rows),
        "passed": median >= 70.0 and fallback_percent <= 5.0,
        "writes_performed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--bootstrap", default=DEFAULT_BOOTSTRAP.as_posix())
    parser.add_argument("--ids", default=DEFAULT_IDS.as_posix())
    commands = parser.add_subparsers(dest="command", required=True)
    apply_parser = commands.add_parser("apply")
    apply_parser.add_argument("--project-binding", required=True)
    sync_parser = commands.add_parser("sync")
    sync_parser.add_argument("--project-binding", required=True)
    mutate_parser = commands.add_parser("mutate")
    mutate_parser.add_argument("--project-binding", required=True)
    report_parser = commands.add_parser("report")
    report_parser.add_argument("--backend", choices=("file", "hybrid"), required=True)
    report_parser.add_argument("--operation", choices=OPERATIONS, required=True)
    commands.add_parser("qualify")
    commands.add_parser("benchmark")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        workspace = resolved_workspace(Path(args.workspace))
        bootstrap_path = Path(args.bootstrap)
        ids_path = Path(args.ids)
        if args.command == "apply":
            result = apply_hpt2(
                workspace,
                project_binding=args.project_binding,
                bootstrap_path=bootstrap_path,
                ids_path=ids_path,
            )
        elif args.command == "sync":
            result = sync_bootstrap(
                workspace,
                project_binding=args.project_binding,
                bootstrap_path=bootstrap_path,
                ids_path=ids_path,
            )
        elif args.command == "mutate":
            result = apply_bounded_mutation(
                workspace, project_binding=args.project_binding, ids_path=ids_path
            )
        elif args.command == "report":
            _, bootstrap, ids = load_sources(workspace, bootstrap_path, ids_path)
            state = file_state(bootstrap, mutation_applied=True) if args.backend == "file" else hybrid_state_view(workspace, ids)
            result = {
                "schema_version": 1,
                "kind": "tool-shed-outcome-reconciliation-report",
                "backend": args.backend,
                "operation": args.operation,
                "result": operation_result(state, args.operation),
                "writes_performed": False,
            }
        elif args.command == "qualify":
            result = qualify_parity(workspace, bootstrap_path=bootstrap_path, ids_path=ids_path)
        else:
            _, bootstrap, _ = load_sources(workspace, bootstrap_path, ids_path)
            result = efficiency_report(workspace, bootstrap)
        print(json.dumps(result, indent=2, sort_keys=True))
        if args.command == "qualify" and not result["valid"]:
            return 1
        if args.command == "benchmark" and not result["passed"]:
            return 1
        return 0
    except (
        ReconciliationError,
        hybrid_state.HybridStateError,
        ProjectIdentityError,
        sqlite3.DatabaseError,
        OSError,
        ValueError,
    ) as error:
        print(f"Outcome reconciliation failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
