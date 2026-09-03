#!/usr/bin/env python3
"""Guarded recursive lineage, closure rollups, proof records, and recovery operations."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Sequence

import document_store
import hybrid_state
from closure_lineage_schema import (
    CLOSURE_SCHEMA_VERSION,
    CLOSURE_TABLES,
    HYBRID_SCHEMA_VERSION,
    closure_migration_digest,
    create_closure_schema,
)
from project_identity import ProjectIdentityError, require_path_within, require_project_binding, resolved_workspace


SCHEMA_VERSION = 1
MANIFEST_KIND = "tool-shed-closure-lineage-migration-manifest"
EVALUATOR_VERSION = "recursive-closure-v1"
RELATIONSHIP_TYPES = {"fulfills", "contributes", "informs", "supersedes"}
GOVERNING_RELATIONSHIPS = {"fulfills", "contributes"}
PROTECTED_GATE_WORDS = {"production", "release", "security", "compliance"}
OPEN_RECOVERY_STATES = {"open", "retry-wait", "escalated"}


class ClosureLineageError(RuntimeError):
    pass


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def random_uuid() -> str:
    return str(uuid.uuid4())


def stable_uuid(*parts: object) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "tool-shed/closure/" + "/".join(map(str, parts))))


def _row_payload(row: sqlite3.Row, fields: Iterable[str]) -> dict[str, Any]:
    return {field: row[field] for field in fields}


def _subject_digest(row: sqlite3.Row, role: str) -> str:
    if role == "cycle":
        return digest(_row_payload(row, ("id", "kind", "origin_artifact_id", "accepted_outcome", "lifecycle_state", "opened_at", "closed_at")))
    return digest(_row_payload(row, ("id", "cycle_id", "origin_artifact_id", "accepted_outcome", "disposition", "accepted_revision", "milestone_key", "evidence_gate_key")))


def _requirement_digest(row: sqlite3.Row) -> str:
    return _subject_digest(row, "obligation")


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='table'")}


def _manifest_token(payload: dict[str, Any]) -> str:
    material = {key: value for key, value in payload.items() if key != "manifest_token"}
    return digest(material)[:16]


def _envelope(
    *,
    element_id: str,
    element_kind: str,
    element_revision: int,
    subject_digest: str,
    claims: list[dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    value = {
        "schema_version": CLOSURE_SCHEMA_VERSION,
        "element_id": element_id,
        "element_kind": element_kind,
        "element_revision": element_revision,
        "subject_digest": subject_digest,
        "lineage_claims": sorted(claims, key=lambda item: item["claim_id"]),
    }
    return value, digest(value)


def prepare_migration(workspace: Path) -> dict[str, Any]:
    """Build an exact non-mutating schema-2-to-3 manifest from explicit DB relationships."""
    workspace = resolved_workspace(workspace)
    with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)) as connection:
        audit = document_store.audit_connection(workspace, connection)
        if audit["classification"] not in {"CLEAN", "VALID_DIRTY"}:
            raise ClosureLineageError(f"migration plan refused from {audit['classification']}")
        if int(connection.execute("PRAGMA user_version").fetchone()[0]) != 2:
            raise ClosureLineageError("migration plan requires Hybrid schema 2")
        revision = int(audit["current_revision"])
        cycle_rows = list(connection.execute("SELECT * FROM cycle WHERE lifecycle_state<>'terminal' ORDER BY id"))
        cycle_by_id = {str(row["id"]): row for row in cycle_rows}
        cycle_by_artifact: dict[str, list[sqlite3.Row]] = {}
        for row in cycle_rows:
            cycle_by_artifact.setdefault(str(row["origin_artifact_id"]), []).append(row)
        requirement_rows = list(
            connection.execute(
                "SELECT * FROM requirement WHERE cycle_id IN (SELECT id FROM cycle WHERE lifecycle_state<>'terminal') ORDER BY id"
            )
        )
        requirements_by_cycle: dict[str, list[sqlite3.Row]] = {}
        for row in requirement_rows:
            requirements_by_cycle.setdefault(str(row["cycle_id"]), []).append(row)

        findings: list[dict[str, Any]] = []
        claims_by_child: dict[str, list[dict[str, Any]]] = {}

        # Every accepted requirement is an explicit closure-bearing obligation owned by its cycle.
        for row in requirement_rows:
            owner = cycle_by_id[str(row["cycle_id"])]
            claim = {
                "claim_id": stable_uuid("obligation-owner", row["id"]),
                "parent_element_id": str(owner["id"]),
                "parent_kind": str(owner["kind"]),
                "parent_visible_id": None,
                "parent_requirement_id": str(row["id"]),
                "relationship_type": "contributes",
                "observed_parent_revision": revision,
                "observed_requirement_digest": _requirement_digest(row),
            }
            claims_by_child.setdefault(str(row["id"]), []).append(claim)

        # Existing outcome-parent edges are explicit; requirement selection must be unambiguous.
        parent_edges = list(
            connection.execute(
                "SELECT from_artifact_id, to_artifact_id FROM relationship "
                "WHERE relation_type='outcome-parent' AND retired_revision IS NULL ORDER BY id"
            )
        )
        for edge in parent_edges:
            children = cycle_by_artifact.get(str(edge["from_artifact_id"]), [])
            parents = cycle_by_artifact.get(str(edge["to_artifact_id"]), [])
            if not children:
                continue
            if len(parents) != 1:
                findings.append(
                    {
                        "code": "MISSING_OR_AMBIGUOUS_PARENT_CYCLE",
                        "child_artifact_id": str(edge["from_artifact_id"]),
                        "parent_artifact_id": str(edge["to_artifact_id"]),
                        "candidate_count": len(parents),
                    }
                )
                continue
            parent = parents[0]
            obligations = requirements_by_cycle.get(str(parent["id"]), [])
            if len(obligations) != 1:
                findings.append(
                    {
                        "code": "AMBIGUOUS_PARENT_REQUIREMENT",
                        "parent_cycle_id": str(parent["id"]),
                        "candidate_count": len(obligations),
                    }
                )
                continue
            requirement = obligations[0]
            for child in children:
                claim = {
                    "claim_id": stable_uuid("cycle-parent", child["id"], parent["id"], requirement["id"]),
                    "parent_element_id": str(parent["id"]),
                    "parent_kind": str(parent["kind"]),
                    "parent_visible_id": None,
                    "parent_requirement_id": str(requirement["id"]),
                    "relationship_type": "fulfills",
                    "observed_parent_revision": revision,
                    "observed_requirement_digest": _requirement_digest(requirement),
                }
                claims_by_child.setdefault(str(child["id"]), []).append(claim)

        elements: list[dict[str, Any]] = []
        for row in cycle_rows:
            element_id = str(row["id"])
            subject = _subject_digest(row, "cycle")
            envelope, envelope_digest = _envelope(
                element_id=element_id,
                element_kind=str(row["kind"]),
                element_revision=revision,
                subject_digest=subject,
                claims=claims_by_child.get(element_id, []),
            )
            elements.append(
                {
                    "id": element_id,
                    "role": "cycle",
                    "element_kind": str(row["kind"]),
                    "artifact_id": str(row["origin_artifact_id"]),
                    "cycle_id": element_id,
                    "requirement_id": None,
                    "subject_revision": revision,
                    "subject_digest": subject,
                    "envelope": envelope,
                    "envelope_digest": envelope_digest,
                }
            )
        for row in requirement_rows:
            element_id = str(row["id"])
            subject = _subject_digest(row, "obligation")
            envelope, envelope_digest = _envelope(
                element_id=element_id,
                element_kind="requirement",
                element_revision=revision,
                subject_digest=subject,
                claims=claims_by_child.get(element_id, []),
            )
            elements.append(
                {
                    "id": element_id,
                    "role": "obligation",
                    "element_kind": "requirement",
                    "artifact_id": str(row["origin_artifact_id"]),
                    "cycle_id": None,
                    "requirement_id": element_id,
                    "subject_revision": revision,
                    "subject_digest": subject,
                    "envelope": envelope,
                    "envelope_digest": envelope_digest,
                }
            )
        envelope_by_id = {item["id"]: item["envelope_digest"] for item in elements}
        claims = []
        for child_id, child_claims in claims_by_child.items():
            if child_id not in envelope_by_id:
                continue
            for item in child_claims:
                claims.append(
                    {
                        "id": item["claim_id"],
                        "child_element_id": child_id,
                        "parent_element_id": item["parent_element_id"],
                        "parent_requirement_id": item["parent_requirement_id"],
                        "relationship_type": item["relationship_type"],
                        "observed_parent_revision": item["observed_parent_revision"],
                        "observed_requirement_digest": item["observed_requirement_digest"],
                        "envelope_digest": envelope_by_id[child_id],
                    }
                )
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "kind": MANIFEST_KIND,
            "project_id": hybrid_state.load_project_identity(workspace)["project_id"],
            "expected_revision": revision,
            "expected_domain_digest": audit["domain_digest"],
            "from_schema": 2,
            "to_schema": 3,
            "elements": sorted(elements, key=lambda item: item["id"]),
            "claims": sorted(claims, key=lambda item: item["id"]),
            "findings": findings,
            "applicable": not findings,
        }
        payload["manifest_token"] = _manifest_token(payload)
        return payload


def validate_manifest(workspace: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    errors: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("kind") != MANIFEST_KIND:
        errors.append("unsupported migration manifest")
    if manifest.get("manifest_token") != _manifest_token(manifest):
        errors.append("migration manifest token mismatch")
    identity = hybrid_state.load_project_identity(workspace)
    if manifest.get("project_id") != identity["project_id"]:
        errors.append("migration manifest belongs to another project")
    if manifest.get("from_schema") != 2 or manifest.get("to_schema") != 3:
        errors.append("migration manifest schema boundary is invalid")
    ids = {str(item.get("id")) for item in manifest.get("elements", [])}
    if len(ids) != len(manifest.get("elements", [])):
        errors.append("migration manifest repeats element ids")
    for item in manifest.get("elements", []):
        envelope = item.get("envelope")
        if not isinstance(envelope, dict) or digest(envelope) != item.get("envelope_digest"):
            errors.append(f"element envelope digest mismatch: {item.get('id')}")
        if envelope and envelope.get("element_id") != item.get("id"):
            errors.append(f"element envelope identity mismatch: {item.get('id')}")
    for claim in manifest.get("claims", []):
        if claim.get("child_element_id") not in ids or claim.get("parent_element_id") not in ids:
            errors.append(f"claim references unknown element: {claim.get('id')}")
        if claim.get("relationship_type") not in RELATIONSHIP_TYPES:
            errors.append(f"claim relationship type is invalid: {claim.get('id')}")
        matching = next((item for item in manifest.get("elements", []) if item["id"] == claim.get("child_element_id")), None)
        if matching and claim.get("envelope_digest") != matching.get("envelope_digest"):
            errors.append(f"claim envelope digest mismatch: {claim.get('id')}")
    if manifest.get("findings"):
        errors.append("migration manifest has unresolved lineage findings")
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-closure-lineage-migration-validation",
        "valid": not errors,
        "applicable": bool(manifest.get("applicable")) and not errors,
        "errors": errors,
        "writes_performed": False,
    }


def _replace_file(source: Path, destination: Path) -> None:
    with source.open("r+b") as handle:
        os.fsync(handle.fileno())
    os.replace(source, destination)


def _insert_manifest(connection: sqlite3.Connection, manifest: dict[str, Any], revision: int) -> None:
    stamp = hybrid_state.now()
    connection.execute(
        "INSERT INTO closure_graph_meta VALUES (1, ?, 1, ?, ?, ?)",
        (CLOSURE_SCHEMA_VERSION, EVALUATOR_VERSION, "0" * 64, stamp),
    )
    for item in manifest["elements"]:
        connection.execute(
            "INSERT INTO closure_element VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item["id"], item["role"], item["element_kind"], item["artifact_id"], item["cycle_id"],
                item["requirement_id"], item["subject_revision"], item["subject_digest"],
                json.dumps(item["envelope"], sort_keys=True), item["envelope_digest"], revision, revision,
            ),
        )
    for item in manifest["claims"]:
        connection.execute(
            "INSERT INTO lineage_claim VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (
                item["id"], item["child_element_id"], item["parent_element_id"],
                item["parent_requirement_id"], item["relationship_type"],
                item["observed_parent_revision"], item["observed_requirement_digest"],
                item["envelope_digest"], revision,
            ),
        )
    rebuild_projection(connection, revision=revision)


def synchronize_authority(connection: sqlite3.Connection, *, revision: int) -> dict[str, Any]:
    """Enroll current lifecycle authority and refresh only affected projection branches.

    This runs inside the same managed transaction as the lifecycle mutation.  Authority remains
    in cycle, requirement, relationship, verdict, and reconciliation rows; closure tables retain
    the recoverable element envelopes and append-only claim/closure history derived from them.
    """
    if int(connection.execute("PRAGMA user_version").fetchone()[0]) != HYBRID_SCHEMA_VERSION:
        return {"applicable": False, "element_count": 0, "claim_count": 0, "closed_count": 0}
    if not set(CLOSURE_TABLES) <= _tables(connection):
        raise ClosureLineageError("schema 3 is missing closure authority tables")

    cycles = {str(row["id"]): row for row in connection.execute("SELECT * FROM cycle ORDER BY id")}
    requirements = {str(row["id"]): row for row in connection.execute("SELECT * FROM requirement ORDER BY id")}
    requirements_by_cycle: dict[str, list[sqlite3.Row]] = {}
    for row in requirements.values():
        requirements_by_cycle.setdefault(str(row["cycle_id"]), []).append(row)

    desired_claims: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    changed_element_ids: set[str] = set()
    changed_claim_children: set[str] = set()
    for requirement in requirements.values():
        parent_id = str(requirement["cycle_id"])
        if parent_id not in cycles:
            continue
        key = (str(requirement["id"]), parent_id, str(requirement["id"]), "contributes")
        desired_claims[key] = {
            "observed_parent_revision": revision,
            "observed_requirement_digest": _requirement_digest(requirement),
        }

    latest_cycle_by_artifact: dict[str, sqlite3.Row] = {}
    for cycle in sorted(cycles.values(), key=lambda item: (str(item["opened_at"]), str(item["id"]))):
        latest_cycle_by_artifact[str(cycle["origin_artifact_id"])] = cycle
    for edge in connection.execute(
        "SELECT from_artifact_id,to_artifact_id FROM relationship "
        "WHERE relation_type='outcome-parent' AND retired_revision IS NULL ORDER BY id"
    ):
        child = latest_cycle_by_artifact.get(str(edge["from_artifact_id"]))
        parent = latest_cycle_by_artifact.get(str(edge["to_artifact_id"]))
        if child is None or parent is None:
            continue
        obligations = requirements_by_cycle.get(str(parent["id"]), [])
        if len(obligations) != 1:
            continue
        requirement = obligations[0]
        key = (str(child["id"]), str(parent["id"]), str(requirement["id"]), "fulfills")
        desired_claims[key] = {
            "observed_parent_revision": revision,
            "observed_requirement_digest": _requirement_digest(requirement),
        }

    claims_by_child: dict[str, list[dict[str, Any]]] = {}
    active_rows = list(connection.execute("SELECT * FROM lineage_claim WHERE retired_revision IS NULL ORDER BY id"))
    active_by_key = {
        (
            str(row["child_element_id"]), str(row["parent_element_id"]),
            str(row["parent_requirement_id"]), str(row["relationship_type"]),
        ): row
        for row in active_rows
    }
    selected_claim_ids: set[str] = set()
    for key, observed in desired_claims.items():
        current = active_by_key.get(key)
        if current is not None and current["observed_requirement_digest"] == observed["observed_requirement_digest"]:
            claim_id = str(current["id"])
            observed["observed_parent_revision"] = int(current["observed_parent_revision"])
        else:
            if current is not None:
                connection.execute("UPDATE lineage_claim SET retired_revision=? WHERE id=?", (revision, current["id"]))
                changed_claim_children.add(str(current["child_element_id"]))
                changed_element_ids.update(
                    (str(current["child_element_id"]), str(current["parent_element_id"]))
                )
            claim_id = stable_uuid("authority-claim", *key, observed["observed_requirement_digest"])
            changed_claim_children.add(key[0])
            changed_element_ids.update((key[0], key[1]))
        selected_claim_ids.add(claim_id)
        claims_by_child.setdefault(key[0], []).append(
            {
                "claim_id": claim_id,
                "parent_element_id": key[1],
                "parent_kind": str(cycles[key[1]]["kind"]),
                "parent_visible_id": None,
                "parent_requirement_id": key[2],
                "relationship_type": key[3],
                "observed_parent_revision": observed["observed_parent_revision"],
                "observed_requirement_digest": observed["observed_requirement_digest"],
            }
        )
    for row in active_rows:
        if str(row["id"]) not in selected_claim_ids and row["retired_revision"] is None:
            connection.execute("UPDATE lineage_claim SET retired_revision=? WHERE id=?", (revision, row["id"]))
            changed_claim_children.add(str(row["child_element_id"]))
            changed_element_ids.update(
                (str(row["child_element_id"]), str(row["parent_element_id"]))
            )

    desired_elements: list[dict[str, Any]] = []
    for cycle in cycles.values():
        desired_elements.append(
            {
                "id": str(cycle["id"]), "role": "cycle", "element_kind": str(cycle["kind"]),
                "artifact_id": str(cycle["origin_artifact_id"]), "cycle_id": str(cycle["id"]),
                "requirement_id": None, "subject_digest": _subject_digest(cycle, "cycle"),
            }
        )
    for requirement in requirements.values():
        desired_elements.append(
            {
                "id": str(requirement["id"]), "role": "obligation", "element_kind": "requirement",
                "artifact_id": str(requirement["origin_artifact_id"]), "cycle_id": None,
                "requirement_id": str(requirement["id"]), "subject_digest": _subject_digest(requirement, "obligation"),
            }
        )

    envelope_by_id: dict[str, str] = {}
    for item in desired_elements:
        current = connection.execute("SELECT * FROM closure_element WHERE id=?", (item["id"],)).fetchone()
        subject_revision = int(current["subject_revision"]) if current and current["subject_digest"] == item["subject_digest"] else revision
        element_revision = revision
        if current is not None:
            prior_envelope = json.loads(current["envelope_json"])
            unchanged_envelope, unchanged_digest = _envelope(
                element_id=item["id"], element_kind=item["element_kind"],
                element_revision=int(prior_envelope["element_revision"]),
                subject_digest=item["subject_digest"], claims=claims_by_child.get(item["id"], []),
            )
            if unchanged_digest == current["envelope_digest"]:
                element_revision = int(prior_envelope["element_revision"])
        envelope, envelope_digest = _envelope(
            element_id=item["id"], element_kind=item["element_kind"], element_revision=element_revision,
            subject_digest=item["subject_digest"], claims=claims_by_child.get(item["id"], []),
        )
        envelope_by_id[item["id"]] = envelope_digest
        values = (
            item["role"], item["element_kind"], item["artifact_id"], item["cycle_id"], item["requirement_id"],
            subject_revision, item["subject_digest"], json.dumps(envelope, sort_keys=True), envelope_digest, revision,
        )
        if current is None:
            connection.execute(
                "INSERT INTO closure_element VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (item["id"], *values[:-1], revision, revision),
            )
            changed_element_ids.add(item["id"])
        elif any(
            current[field] != expected for field, expected in (
                ("role", item["role"]), ("element_kind", item["element_kind"]),
                ("artifact_id", item["artifact_id"]), ("cycle_id", item["cycle_id"]),
                ("requirement_id", item["requirement_id"]), ("subject_revision", subject_revision),
                ("subject_digest", item["subject_digest"]), ("envelope_digest", envelope_digest),
            )
        ):
            connection.execute(
                "UPDATE closure_element SET role=?,element_kind=?,artifact_id=?,cycle_id=?,requirement_id=?,"
                "subject_revision=?,subject_digest=?,envelope_json=?,envelope_digest=?,updated_revision=? WHERE id=?",
                (*values, item["id"]),
            )
            changed_element_ids.add(item["id"])

    for key, observed in desired_claims.items():
        claim_id = next(item["claim_id"] for item in claims_by_child[key[0]] if item["parent_element_id"] == key[1] and item["parent_requirement_id"] == key[2] and item["relationship_type"] == key[3])
        claim = connection.execute(
            "SELECT envelope_digest FROM lineage_claim WHERE id=?", (claim_id,)
        ).fetchone()
        if claim is None:
            connection.execute(
                "INSERT INTO lineage_claim VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
                (claim_id, *key, observed["observed_parent_revision"], observed["observed_requirement_digest"], envelope_by_id[key[0]], revision),
            )
        elif str(claim["envelope_digest"]) != envelope_by_id[key[0]]:
            connection.execute("UPDATE lineage_claim SET envelope_digest=? WHERE id=?", (envelope_by_id[key[0]], claim_id))

    closed_count = 0
    for cycle_id, cycle in cycles.items():
        latest = connection.execute(
            "SELECT v.disposition,v.authorization_ref,r.state,r.residual_work_json "
            "FROM reconciliation r JOIN outcome_verdict v ON v.id=r.verdict_id "
            "WHERE r.cycle_id=? ORDER BY r.origin_revision DESC LIMIT 1",
            (cycle_id,),
        ).fetchone()
        proven = (
            cycle["lifecycle_state"] == "terminal" and latest is not None
            and latest["disposition"] in {"satisfied", "satisfied-with-approved-change", "not-applicable"}
            and latest["state"] == "reconciled" and json.loads(latest["residual_work_json"]) == []
        )
        element_ids = [cycle_id, *(str(item["id"]) for item in requirements_by_cycle.get(cycle_id, []))]
        for element_id in element_ids:
            element = connection.execute("SELECT * FROM closure_element WHERE id=?", (element_id,)).fetchone()
            current = _latest_closure(connection, element_id)
            current_matches = current is not None and current["subject_digest"] == element["subject_digest"] and int(current["subject_revision"]) == int(element["subject_revision"])
            if current is not None and not current_matches:
                connection.execute("UPDATE closure_record SET superseded_revision=? WHERE id=?", (revision, current["id"]))
                changed_element_ids.add(element_id)
                current = None
            if proven and current is None:
                connection.execute(
                    "INSERT INTO closure_record VALUES (?, ?, ?, ?, ?, 'closed-loop', 'current', ?, ?, ?, NULL)",
                    (
                        random_uuid(), element_id, element["requirement_id"], element["subject_revision"],
                        element["subject_digest"], str(latest["authorization_ref"]),
                        json.dumps([f"outcome-cycle:{cycle_id}"], sort_keys=True), revision,
                    ),
                )
                closed_count += 1
                changed_element_ids.add(element_id)

    if changed_claim_children:
        _refresh_ancestor_paths(
            connection,
            revision=revision,
            changed_child_ids=changed_claim_children,
        )
    rebuilt = refresh_projection(
        connection,
        revision=revision,
        changed_element_ids=changed_element_ids,
        refresh_graph_findings=bool(changed_claim_children),
    )
    return {
        "applicable": True,
        "element_count": len(desired_elements),
        "claim_count": len(desired_claims),
        "closed_count": closed_count,
        **rebuilt,
    }


def apply_migration(
    workspace: Path,
    manifest: dict[str, Any],
    *,
    expected_token: str,
    project_binding: str,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    require_project_binding(workspace, project_binding, operation="hybrid-state")
    validation = validate_manifest(workspace, manifest)
    if not validation["applicable"] or expected_token != manifest.get("manifest_token"):
        raise ClosureLineageError("migration requires the exact valid applicable manifest token")
    source = hybrid_state.database_path(workspace)
    shadow = source.with_name(source.name + ".schema3-next")
    if shadow.exists():
        raise ClosureLineageError(f"stale migration shadow requires review: {shadow.relative_to(workspace)}")
    backup_root = workspace / ".tool-shed/backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = backup_root / f"closure-schema2-r{manifest['expected_revision']}.sqlite3"
    if backup.exists():
        raise ClosureLineageError(f"migration backup already exists and requires review: {backup.relative_to(workspace)}")
    with hybrid_state.WorkspaceLock(hybrid_state.lock_path(workspace)):
        with contextlib.closing(hybrid_state.connect(source)) as live:
            entrance = document_store.audit_connection(workspace, live)
            if entrance["classification"] not in {"CLEAN", "VALID_DIRTY"}:
                raise ClosureLineageError(f"migration refused from {entrance['classification']}")
            if entrance["current_revision"] != manifest["expected_revision"] or entrance["domain_digest"] != manifest["expected_domain_digest"]:
                raise ClosureLineageError("migration manifest source state is stale")
            if int(live.execute("PRAGMA user_version").fetchone()[0]) != 2:
                raise ClosureLineageError("migration requires Hybrid schema 2")
            with contextlib.closing(sqlite3.connect(backup)) as backup_connection:
                live.backup(backup_connection)
                backup_connection.commit()
            with contextlib.closing(sqlite3.connect(shadow)) as target:
                live.backup(target)
                target.commit()
        try:
            with contextlib.closing(hybrid_state.connect(backup, writable=False)) as backup_connection:
                if document_store.audit_connection(workspace, backup_connection)["domain_digest"] != manifest["expected_domain_digest"]:
                    raise ClosureLineageError("verified migration backup domain digest mismatch")
            with contextlib.closing(hybrid_state.connect(shadow)) as target:
                target.execute("BEGIN IMMEDIATE")
                create_closure_schema(target, include_triggers=True)
                revision = int(manifest["expected_revision"]) + 1
                operation_id = random_uuid()
                stamp = hybrid_state.now()
                target.execute(
                    "INSERT INTO managed_operation VALUES (?, ?, 'closure-schema3-migrate', 'closure-lineage', ?, NULL, NULL, 0, 'active')",
                    (operation_id, revision, stamp),
                )
                target.execute("INSERT INTO active_operation VALUES (1, ?, ?)", (operation_id, revision))
                _insert_manifest(target, manifest, revision)
                graph_source_digest = document_store.domain_digest(target)
                target.execute(
                    "UPDATE closure_graph_meta SET source_digest=?, updated_at=? WHERE id=1",
                    (graph_source_digest, stamp),
                )
                target.execute(
                    "INSERT INTO migration_ledger VALUES (?, 2, 3, ?, ?, ?, 'complete', ?, ?)",
                    (
                        random_uuid(), closure_migration_digest(), manifest["expected_domain_digest"],
                        backup.relative_to(workspace).as_posix(), stamp, stamp,
                    ),
                )
                target.execute("DELETE FROM active_operation WHERE id=1")
                target.execute(
                    "UPDATE managed_operation SET status='complete', committed_at=? WHERE id=?",
                    (hybrid_state.now(), operation_id),
                )
                target.execute("UPDATE state_meta SET schema_version=3 WHERE id=1")
                target.execute("PRAGMA user_version=3")
                source_digest = document_store.domain_digest(target)
                target.execute(
                    "UPDATE state_meta SET current_revision=?, last_verified_revision=?, source_digest=?, "
                    "schema_trigger_digest=?, dirty=1, checkpoint_pending=1 WHERE id=1",
                    (revision, revision, source_digest, hybrid_state.schema_digest(target)),
                )
                target.commit()
                checked = audit_connection(workspace, target)
                if checked["classification"] not in {"VALID_DIRTY", "CHECKPOINT_DUE"}:
                    unmanaged_rows = [
                        f"{row['table_name']}:{row['row_id']}"
                        for row in target.execute(
                            "SELECT table_name, row_id FROM structural_change WHERE managed=0 ORDER BY revision DESC, id LIMIT 10"
                        )
                    ]
                    raise ClosureLineageError(
                        f"migration shadow failed audit: {checked['classification']}: "
                        + "; ".join(checked["findings"])
                        + ("; unmanaged=" + ",".join(unmanaged_rows) if unmanaged_rows else "")
                    )
                target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            _replace_file(shadow, source)
        except BaseException:
            shadow.unlink(missing_ok=True)
            raise
    result = audit(workspace)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-closure-lineage-migration",
        "from_schema": 2,
        "to_schema": 3,
        "backup": backup.relative_to(workspace).as_posix(),
        "backup_sha256": hybrid_state.file_sha256(backup),
        "revision": result["current_revision"],
        "classification": result["classification"],
        "domain_digest": result["domain_digest"],
        "writes_performed": True,
    }


def _latest_closure(connection: sqlite3.Connection, element_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM closure_record WHERE element_id=? AND superseded_revision IS NULL "
        "ORDER BY created_revision DESC, id DESC LIMIT 1",
        (element_id,),
    ).fetchone()


def _active_claims(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(connection.execute("SELECT * FROM lineage_claim WHERE retired_revision IS NULL ORDER BY id"))


def _recovery_reason_maps(
    connection: sqlite3.Connection,
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    active: dict[str, set[str]] = {}
    history: dict[str, set[str]] = {}
    for row in connection.execute(
        "SELECT element_id, reason_code, state FROM recovery_case WHERE element_id IS NOT NULL"
    ):
        element_id = str(row["element_id"])
        reason_code = str(row["reason_code"])
        history.setdefault(element_id, set()).add(reason_code)
        if str(row["state"]) in OPEN_RECOVERY_STATES:
            active.setdefault(element_id, set()).add(reason_code)
    return active, history


def _graph_findings(connection: sqlite3.Connection) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    elements = {str(row["id"]): row for row in connection.execute("SELECT * FROM closure_element")}
    requirements = {str(row["id"]): row for row in connection.execute("SELECT * FROM requirement")}
    claims = _active_claims(connection)
    findings: list[dict[str, Any]] = []
    parents: dict[str, list[str]] = {key: [] for key in elements}
    for claim in claims:
        child, parent = str(claim["child_element_id"]), str(claim["parent_element_id"])
        if child not in elements or parent not in elements:
            findings.append({"code": "MISSING_PARENT", "claim_id": claim["id"], "element_id": child})
            continue
        requirement = requirements.get(str(claim["parent_requirement_id"]))
        if requirement is None:
            findings.append({"code": "MISSING_REQUIREMENT", "claim_id": claim["id"], "element_id": child})
            continue
        if _requirement_digest(requirement) != claim["observed_requirement_digest"]:
            findings.append({"code": "CONFLICTING_LINEAGE", "claim_id": claim["id"], "element_id": child})
        parents[child].append(parent)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, trail: list[str]) -> None:
        if node in visiting:
            cycle = trail[trail.index(node):] + [node]
            findings.append({"code": "CYCLE", "element_id": node, "cycle": cycle})
            return
        if node in visited:
            return
        visiting.add(node)
        for parent in parents.get(node, []):
            visit(parent, trail + [parent])
        visiting.remove(node)
        visited.add(node)

    for element_id in elements:
        visit(element_id, [element_id])
    return findings, parents


def _children(connection: sqlite3.Connection, element: sqlite3.Row) -> list[tuple[str, str | None]]:
    if element["role"] == "cycle":
        rows = connection.execute(
            "SELECT ce.id, ce.requirement_id FROM closure_element ce JOIN requirement q ON q.id=ce.requirement_id "
            "WHERE ce.role='obligation' AND q.cycle_id=? AND q.disposition NOT IN ('not-applicable','retired','superseded') ORDER BY ce.id",
            (element["cycle_id"],),
        )
        return [(str(row["id"]), str(row["requirement_id"])) for row in rows]
    rows = connection.execute(
        "SELECT child_element_id FROM lineage_claim WHERE parent_requirement_id=? "
        "AND relationship_type IN ('fulfills','contributes') AND retired_revision IS NULL "
        "AND child_element_id<>? ORDER BY child_element_id",
        (element["requirement_id"], element["id"]),
    )
    return [(str(row["child_element_id"]), str(element["requirement_id"])) for row in rows]


def evaluate_recursive(connection: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    elements = {str(row["id"]): row for row in connection.execute("SELECT * FROM closure_element ORDER BY id")}
    children_by_element: dict[str, list[tuple[str, str | None]]] = {key: [] for key in elements}
    for row in connection.execute(
        "SELECT parent.id AS parent_id, child.id AS child_id, child.requirement_id "
        "FROM closure_element parent JOIN requirement q ON q.cycle_id=parent.cycle_id "
        "JOIN closure_element child ON child.requirement_id=q.id "
        "WHERE parent.role='cycle' AND child.role='obligation' "
        "AND q.disposition NOT IN ('not-applicable','retired','superseded')"
    ):
        children_by_element[str(row["parent_id"])].append(
            (str(row["child_id"]), str(row["requirement_id"]))
        )
    for row in connection.execute(
        "SELECT obligation.id AS parent_id, claim.child_element_id AS child_id, "
        "claim.parent_requirement_id FROM lineage_claim claim JOIN closure_element obligation "
        "ON obligation.requirement_id=claim.parent_requirement_id "
        "WHERE claim.relationship_type IN ('fulfills','contributes') "
        "AND claim.retired_revision IS NULL AND claim.child_element_id<>obligation.id"
    ):
        children_by_element[str(row["parent_id"])].append(
            (str(row["child_id"]), str(row["parent_requirement_id"]))
        )
    for value in children_by_element.values():
        value.sort()
    findings, _ = _graph_findings(connection)
    findings_by_element: dict[str, list[str]] = {}
    for item in findings:
        findings_by_element.setdefault(str(item.get("element_id")), []).append(str(item["code"]))
    recovery_reasons, _ = _recovery_reason_maps(connection)
    memo: dict[str, dict[str, Any]] = {}
    active: set[str] = set()

    def evaluate(element_id: str) -> dict[str, Any]:
        if element_id in memo:
            return memo[element_id]
        element = elements[element_id]
        if element_id in active:
            return {
                "local_closure": "open", "evidence_health": "not-required", "graph_health": "invalid",
                "effective_closed": False, "reasons": ["CYCLE"], "blockers": [(element_id, None, "CYCLE", 0)],
                "open_descendants": 0, "unknown_descendants": 0, "invalid_descendants": 1,
            }
        active.add(element_id)
        closure = _latest_closure(connection, element_id)
        local = str(closure["method"]) if closure else "open"
        evidence = str(closure["evidence_health"]) if closure else "not-required"
        local_reasons: list[str] = []
        graph_reasons = sorted(set([*findings_by_element.get(element_id, []), *recovery_reasons.get(element_id, set())]))
        graph_health = "invalid" if any(item in {"CYCLE", "CONFLICTING_LINEAGE"} for item in graph_reasons) else "valid"
        if element_id in recovery_reasons or any(item in {"MISSING_PARENT", "MISSING_REQUIREMENT"} for item in graph_reasons):
            graph_health = "recovery-required"
        if local == "open":
            local_reasons.append("LOCAL_OPEN")
        elif evidence == "missing":
            local_reasons.append("UNPROVEN")
        elif evidence == "stale":
            local_reasons.append("STALE_EVIDENCE")
        elif evidence == "checker-error":
            local_reasons.append("CHECKER_ERROR")

        children = children_by_element[element_id]
        # An obligation can be satisfied by its governing children even before a separate local record is emitted.
        child_results = [(child, requirement, evaluate(child)) for child, requirement in children if child in elements]
        obligation_derived = element["role"] == "obligation" and bool(child_results) and all(item[2]["effective_closed"] for item in child_results)
        locally_closed = local in {"closed-loop", "closed-manual"} or obligation_derived
        if obligation_derived and local == "open":
            local_reasons = []
            local = "closed-loop"
            evidence = "current"
        blockers: list[tuple[str | None, str | None, str, int]] = []
        open_descendants = unknown_descendants = invalid_descendants = 0
        for child, requirement, result in child_results:
            if not result["effective_closed"]:
                open_descendants += 1 + int(result["open_descendants"])
                unknown_descendants += int(result["unknown_descendants"])
                invalid_descendants += int(result["invalid_descendants"])
                blockers.extend((blocking, obligation or requirement, reason, depth + 1) for blocking, obligation, reason, depth in result["blockers"])
        if element["role"] == "obligation" and not children and not locally_closed:
            local_reasons.append("UNFULFILLED_REQUIREMENT")
            blockers.append((element_id, str(element["requirement_id"]), "UNFULFILLED_REQUIREMENT", 0))
        for reason in graph_reasons:
            blockers.append((element_id, str(element["requirement_id"]) if element["role"] == "obligation" else None, reason, 0))
        for reason in local_reasons:
            blockers.append((element_id, str(element["requirement_id"]) if element["role"] == "obligation" else None, reason, 0))
        if child_results and any(not item[2]["effective_closed"] for item in child_results):
            local_reasons.append("DESCENDANT_OPEN")
        effective = locally_closed and evidence in {"not-required", "current"} and graph_health == "valid" and all(item[2]["effective_closed"] for item in child_results)
        result = {
            "local_closure": local,
            "evidence_health": evidence,
            "graph_health": graph_health,
            "effective_closed": effective,
            "reasons": sorted(set([*local_reasons, *graph_reasons])),
            "blockers": sorted(set(blockers), key=lambda item: (item[3], item[2], item[0] or "", item[1] or "")),
            "open_descendants": open_descendants,
            "unknown_descendants": unknown_descendants,
            "invalid_descendants": invalid_descendants + (1 if graph_health != "valid" else 0),
        }
        active.remove(element_id)
        memo[element_id] = result
        return result

    for element_id in elements:
        evaluate(element_id)
    return memo


def _refresh_ancestor_paths(
    connection: sqlite3.Connection,
    *,
    revision: int,
    changed_child_ids: Iterable[str],
) -> int:
    """Refresh paths for graph branches affected by changed lineage claims.

    Existing paths identify descendants below a changed child before they are replaced.  Only
    those descendants can acquire or lose ancestors when that child's parent claims change.
    """
    changed = {str(value) for value in changed_child_ids}
    if not changed:
        return 0
    impacted = set(changed)
    placeholders = ",".join("?" for _ in changed)
    impacted.update(
        str(row["descendant_element_id"])
        for row in connection.execute(
            f"SELECT DISTINCT descendant_element_id FROM closure_ancestor_path "
            f"WHERE ancestor_element_id IN ({placeholders})",
            sorted(changed),
        )
    )
    findings, parents = _graph_findings(connection)
    for descendant in sorted(impacted):
        connection.execute(
            "DELETE FROM closure_ancestor_path WHERE descendant_element_id=?",
            (descendant,),
        )
        counts: dict[str, tuple[int, int]] = {}
        frontier: list[tuple[str, int, tuple[str, ...]]] = [
            (parent, 1, (descendant,)) for parent in parents.get(descendant, [])
        ]
        while frontier:
            ancestor, depth, trail = frontier.pop()
            if ancestor in trail:
                continue
            prior = counts.get(ancestor)
            counts[ancestor] = (
                depth if prior is None else min(depth, prior[0]),
                1 if prior is None else prior[1] + 1,
            )
            frontier.extend(
                (parent, depth + 1, (*trail, ancestor))
                for parent in parents.get(ancestor, [])
            )
        for ancestor, (depth, path_count) in sorted(counts.items()):
            connection.execute(
                "INSERT INTO closure_ancestor_path VALUES (?, ?, ?, ?, ?, ?)",
                (
                    stable_uuid("path", ancestor, descendant), ancestor, descendant,
                    depth, path_count, revision,
                ),
            )
    return len(findings)


def rebuild_projection(connection: sqlite3.Connection, *, revision: int) -> dict[str, Any]:
    """Rebuild paths, rollups, and blockers from envelopes/current claims in one transaction."""
    graph = connection.execute("SELECT * FROM closure_graph_meta WHERE id=1").fetchone()
    graph_revision = int(graph["graph_revision"]) + 1
    findings, parents = _graph_findings(connection)
    connection.execute("DELETE FROM closure_ancestor_path")
    connection.execute("DELETE FROM closure_blocker")
    connection.execute("DELETE FROM closure_rollup")

    for descendant in sorted(parents):
        counts: dict[str, tuple[int, int]] = {}
        frontier: list[tuple[str, int, tuple[str, ...]]] = [(parent, 1, (descendant,)) for parent in parents[descendant]]
        while frontier:
            ancestor, depth, trail = frontier.pop()
            if ancestor in trail:
                continue
            prior = counts.get(ancestor)
            counts[ancestor] = (depth if prior is None else min(depth, prior[0]), 1 if prior is None else prior[1] + 1)
            frontier.extend((parent, depth + 1, (*trail, ancestor)) for parent in parents.get(ancestor, []))
        for ancestor, (depth, path_count) in sorted(counts.items()):
            connection.execute(
                "INSERT INTO closure_ancestor_path VALUES (?, ?, ?, ?, ?, ?)",
                (stable_uuid("path", ancestor, descendant), ancestor, descendant, depth, path_count, graph_revision),
            )

    results = evaluate_recursive(connection)
    stamp = hybrid_state.now()
    for element_id, result in sorted(results.items()):
        element = connection.execute("SELECT * FROM closure_element WHERE id=?", (element_id,)).fetchone()
        connection.execute(
            "INSERT INTO closure_rollup VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_uuid("rollup", element_id), element_id, result["local_closure"], result["evidence_health"],
                result["graph_health"], int(result["effective_closed"]), json.dumps(result["reasons"]),
                result["open_descendants"], result["unknown_descendants"], result["invalid_descendants"],
                element["subject_revision"], graph_revision, EVALUATOR_VERSION, stamp,
            ),
        )
        for index, (blocking, obligation, reason, depth) in enumerate(result["blockers"]):
            connection.execute(
                "INSERT INTO closure_blocker VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    stable_uuid("blocker", graph_revision, element_id, index, blocking, obligation, reason, depth),
                    element_id, obligation, blocking, obligation, reason, depth, graph_revision,
                ),
            )
    source_digest = document_store.domain_digest(connection)
    connection.execute(
        "UPDATE closure_graph_meta SET graph_revision=?, evaluator_version=?, source_digest=?, updated_at=? WHERE id=1",
        (graph_revision, EVALUATOR_VERSION, source_digest, stamp),
    )
    return {"graph_revision": graph_revision, "element_count": len(results), "finding_count": len(findings)}


def refresh_projection(
    connection: sqlite3.Connection,
    *,
    revision: int,
    changed_element_ids: Iterable[str],
    refresh_graph_findings: bool = False,
) -> dict[str, Any]:
    """Refresh changed elements and their indexed ancestors without walking unrelated subtrees."""
    changed = {str(value) for value in changed_element_ids}
    if not changed:
        return {"graph_revision": 0, "element_count": 0, "finding_count": 0}
    affected = set(changed)
    elements: dict[str, sqlite3.Row] = {}
    frontier = list(changed)
    while frontier:
        element_id = frontier.pop()
        element = connection.execute("SELECT * FROM closure_element WHERE id=?", (element_id,)).fetchone()
        if element is None:
            raise ClosureLineageError("incremental projection references a missing closure element")
        elements[element_id] = element
        if element["role"] == "obligation":
            parent_rows = connection.execute(
                "SELECT parent.id FROM requirement q JOIN closure_element parent "
                "ON parent.cycle_id=q.cycle_id AND parent.role='cycle' WHERE q.id=?",
                (element["requirement_id"],),
            )
        else:
            parent_rows = connection.execute(
                "SELECT obligation.id FROM lineage_claim claim JOIN closure_element obligation "
                "ON obligation.requirement_id=claim.parent_requirement_id AND obligation.role='obligation' "
                "WHERE claim.child_element_id=? AND claim.relationship_type IN ('fulfills','contributes') "
                "AND claim.retired_revision IS NULL",
                (element_id,),
            )
        for row in parent_rows:
            parent_id = str(row["id"])
            if parent_id not in affected:
                affected.add(parent_id)
                frontier.append(parent_id)
    if set(elements) != affected:
        raise ClosureLineageError("incremental projection references a missing closure element")
    children_by_element = {
        element_id: _children(connection, element)
        for element_id, element in elements.items()
    }
    findings_by_element: dict[str, list[str]] = {}
    graph_reason_codes = {"CYCLE", "CONFLICTING_LINEAGE", "MISSING_PARENT", "MISSING_REQUIREMENT"}
    for element_id in affected:
        prior = connection.execute(
            "SELECT reason_codes_json FROM closure_rollup WHERE element_id=?", (element_id,)
        ).fetchone()
        if prior:
            findings_by_element[element_id] = [
                value for value in json.loads(prior["reason_codes_json"])
                if value in graph_reason_codes
            ]
    recovery_reasons, recovery_history = _recovery_reason_maps(connection)
    # Recovery reasons are projected into the same public reason-code field as structural graph
    # findings. When a recovery case closes, recompute structural findings once so a historical
    # recovery reason disappears without concealing a real finding that happens to share its code.
    refresh_static_findings = refresh_graph_findings or any(
        (set(findings_by_element.get(element_id, [])) & recovery_history.get(element_id, set()))
        - recovery_reasons.get(element_id, set())
        for element_id in affected
    )
    if refresh_static_findings:
        fresh_findings, _ = _graph_findings(connection)
        findings_by_element = {}
        for item in fresh_findings:
            findings_by_element.setdefault(str(item.get("element_id")), []).append(str(item["code"]))
    graph = connection.execute("SELECT * FROM closure_graph_meta WHERE id=1").fetchone()
    graph_revision = int(graph["graph_revision"]) + 1
    stamp = hybrid_state.now()

    def child_result(child_id: str) -> dict[str, Any]:
        rollup = connection.execute("SELECT * FROM closure_rollup WHERE element_id=?", (child_id,)).fetchone()
        if rollup is None:
            raise ClosureLineageError(f"incremental child rollup is unavailable: {child_id}")
        blockers = [
            (
                row["blocking_element_id"], row["blocking_obligation_id"],
                str(row["reason_code"]), int(row["depth"]),
            )
            for row in connection.execute(
                "SELECT blocking_element_id, blocking_obligation_id, reason_code, depth "
                "FROM closure_blocker WHERE ancestor_element_id=? ORDER BY depth, reason_code, id",
                (child_id,),
            )
        ]
        return {
            "effective_closed": bool(rollup["effective_closed"]),
            "open_descendants": int(rollup["open_descendants"]),
            "unknown_descendants": int(rollup["unknown_descendants"]),
            "invalid_descendants": int(rollup["invalid_descendants"]),
            "blockers": blockers,
        }

    def evaluate_one(element_id: str) -> dict[str, Any]:
        element = elements[element_id]
        closure = _latest_closure(connection, element_id)
        local = str(closure["method"]) if closure else "open"
        evidence = str(closure["evidence_health"]) if closure else "not-required"
        local_reasons: list[str] = []
        graph_reasons = sorted(
            set(
                [
                    *(
                        findings_by_element.get(element_id, [])
                        if refresh_static_findings
                        else [
                            reason
                            for reason in findings_by_element.get(element_id, [])
                            if reason not in recovery_history.get(element_id, set())
                        ]
                    ),
                    *recovery_reasons.get(element_id, set()),
                ]
            )
        )
        graph_health = "invalid" if any(
            item in {"CYCLE", "CONFLICTING_LINEAGE"} for item in graph_reasons
        ) else "valid"
        if element_id in recovery_reasons or any(
            item in {"MISSING_PARENT", "MISSING_REQUIREMENT"} for item in graph_reasons
        ):
            graph_health = "recovery-required"
        if local == "open":
            local_reasons.append("LOCAL_OPEN")
        elif evidence == "missing":
            local_reasons.append("UNPROVEN")
        elif evidence == "stale":
            local_reasons.append("STALE_EVIDENCE")
        elif evidence == "checker-error":
            local_reasons.append("CHECKER_ERROR")
        children = children_by_element[element_id]
        child_results = [(child, requirement, child_result(child)) for child, requirement in children]
        obligation_derived = (
            element["role"] == "obligation" and bool(child_results)
            and all(item[2]["effective_closed"] for item in child_results)
        )
        locally_closed = local in {"closed-loop", "closed-manual"} or obligation_derived
        if obligation_derived and local == "open":
            local_reasons = []
            local = "closed-loop"
            evidence = "current"
        blockers: list[tuple[str | None, str | None, str, int]] = []
        open_descendants = unknown_descendants = invalid_descendants = 0
        for child, requirement, result in child_results:
            if not result["effective_closed"]:
                open_descendants += 1 + int(result["open_descendants"])
                unknown_descendants += int(result["unknown_descendants"])
                invalid_descendants += int(result["invalid_descendants"])
                blockers.extend(
                    (blocking, obligation or requirement, reason, depth + 1)
                    for blocking, obligation, reason, depth in result["blockers"]
                )
        if element["role"] == "obligation" and not children and not locally_closed:
            local_reasons.append("UNFULFILLED_REQUIREMENT")
            blockers.append((element_id, str(element["requirement_id"]), "UNFULFILLED_REQUIREMENT", 0))
        for reason in graph_reasons:
            blockers.append((element_id, str(element["requirement_id"]) if element["role"] == "obligation" else None, reason, 0))
        for reason in local_reasons:
            blockers.append((element_id, str(element["requirement_id"]) if element["role"] == "obligation" else None, reason, 0))
        if child_results and any(not item[2]["effective_closed"] for item in child_results):
            local_reasons.append("DESCENDANT_OPEN")
        effective = (
            locally_closed and evidence in {"not-required", "current"} and graph_health == "valid"
            and all(item[2]["effective_closed"] for item in child_results)
        )
        return {
            "local_closure": local, "evidence_health": evidence, "graph_health": graph_health,
            "effective_closed": effective, "reasons": sorted(set([*local_reasons, *graph_reasons])),
            "blockers": sorted(set(blockers), key=lambda item: (item[3], item[2], item[0] or "", item[1] or "")),
            "open_descendants": open_descendants, "unknown_descendants": unknown_descendants,
            "invalid_descendants": invalid_descendants + (1 if graph_health != "valid" else 0),
        }

    pending = set(affected)
    processed: list[str] = []
    while pending:
        ready = sorted(
            element_id for element_id in pending
            if not ({child for child, _ in children_by_element[element_id]} & pending)
        )
        if not ready:
            raise ClosureLineageError("incremental projection cannot order cyclic affected elements")
        for element_id in ready:
            result = evaluate_one(element_id)
            element = elements[element_id]
            connection.execute("DELETE FROM closure_blocker WHERE ancestor_element_id=?", (element_id,))
            connection.execute(
                "INSERT INTO closure_rollup VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(element_id) DO UPDATE SET local_closure=excluded.local_closure, "
                "evidence_health=excluded.evidence_health, graph_health=excluded.graph_health, "
                "effective_closed=excluded.effective_closed, reason_codes_json=excluded.reason_codes_json, "
                "open_descendants=excluded.open_descendants, unknown_descendants=excluded.unknown_descendants, "
                "invalid_descendants=excluded.invalid_descendants, subject_revision=excluded.subject_revision, "
                "graph_revision=excluded.graph_revision, evaluator_version=excluded.evaluator_version, "
                "evaluated_at=excluded.evaluated_at",
                (
                    stable_uuid("rollup", element_id), element_id, result["local_closure"], result["evidence_health"],
                    result["graph_health"], int(result["effective_closed"]), json.dumps(result["reasons"]),
                    result["open_descendants"], result["unknown_descendants"], result["invalid_descendants"],
                    element["subject_revision"], graph_revision, EVALUATOR_VERSION, stamp,
                ),
            )
            for index, (blocking, obligation, reason, depth) in enumerate(result["blockers"]):
                connection.execute(
                    "INSERT INTO closure_blocker VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        stable_uuid("blocker", graph_revision, element_id, index, blocking, obligation, reason, depth),
                        element_id, obligation, blocking, obligation, reason, depth, graph_revision,
                    ),
                )
            pending.remove(element_id)
            processed.append(element_id)
    source_digest = digest(
        [graph["source_digest"], revision, sorted(changed), graph_revision, EVALUATOR_VERSION]
    )
    connection.execute(
        "UPDATE closure_graph_meta SET graph_revision=?, evaluator_version=?, source_digest=?, updated_at=? WHERE id=1",
        (graph_revision, EVALUATOR_VERSION, source_digest, stamp),
    )
    return {"graph_revision": graph_revision, "element_count": len(processed), "finding_count": 0}


def status(workspace: Path, identity: str) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)) as connection:
        if int(connection.execute("PRAGMA user_version").fetchone()[0]) != 3:
            raise ClosureLineageError("closure status requires Hybrid schema 3")
        row = connection.execute(
            "SELECT ce.*, cr.local_closure, cr.evidence_health, cr.graph_health, cr.effective_closed, "
            "cr.reason_codes_json, cr.open_descendants, cr.unknown_descendants, cr.invalid_descendants, "
            "cr.graph_revision, cr.evaluator_version, cr.evaluated_at "
            "FROM closure_element ce JOIN closure_rollup cr ON cr.element_id=ce.id "
            "WHERE ce.id=? OR ce.artifact_id=? OR ce.cycle_id=? OR ce.requirement_id=?",
            (identity, identity, identity, identity),
        ).fetchone()
        if row is None:
            artifact = connection.execute("SELECT id FROM artifact WHERE display_number=?", (identity,)).fetchone()
            if artifact:
                row = connection.execute(
                    "SELECT ce.*, cr.local_closure, cr.evidence_health, cr.graph_health, cr.effective_closed, "
                    "cr.reason_codes_json, cr.open_descendants, cr.unknown_descendants, cr.invalid_descendants, "
                    "cr.graph_revision, cr.evaluator_version, cr.evaluated_at "
                    "FROM closure_element ce JOIN closure_rollup cr ON cr.element_id=ce.id WHERE ce.artifact_id=?",
                    (artifact["id"],),
                ).fetchone()
        if row is None:
            raise ClosureLineageError(f"closure element not found: {identity}")
        blockers = [
            dict(item)
            for item in connection.execute(
                "SELECT governing_requirement_id, blocking_element_id, blocking_obligation_id, reason_code, depth "
                "FROM closure_blocker WHERE ancestor_element_id=? ORDER BY depth, reason_code, id LIMIT 100",
                (row["id"],),
            )
        ]
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "tool-shed-closure-status",
            "element_id": row["id"],
            "element_kind": row["element_kind"],
            "role": row["role"],
            "local_closure": row["local_closure"],
            "evidence_health": row["evidence_health"],
            "graph_health": row["graph_health"],
            "effective_closed": bool(row["effective_closed"]),
            "reason_codes": json.loads(row["reason_codes_json"]),
            "counts": {
                "open": row["open_descendants"], "unknown": row["unknown_descendants"], "invalid": row["invalid_descendants"]
            },
            "blockers": blockers,
            "subject_revision": row["subject_revision"],
            "subject_digest": row["subject_digest"],
            "graph_revision": row["graph_revision"],
            "evaluator_version": row["evaluator_version"],
            "evaluated_at": row["evaluated_at"],
            "writes_performed": False,
        }


def close_element(
    workspace: Path,
    *,
    project_binding: str,
    element_id: str,
    method: str,
    evidence_health: str,
    authorization_ref: str,
    evidence: list[str],
    actor: str,
    allow_protected_manual: bool = False,
) -> dict[str, Any]:
    if method not in {"closed-loop", "closed-manual"}:
        raise ClosureLineageError("closure method must be closed-loop or closed-manual")
    if evidence_health not in {"not-required", "current", "missing", "stale", "checker-error"}:
        raise ClosureLineageError("invalid evidence health")
    if method == "closed-loop" and evidence_health != "current":
        raise ClosureLineageError("closed-loop requires current evidence")
    if method == "closed-manual" and not authorization_ref.strip():
        raise ClosureLineageError("manual closure requires explicit authorization")

    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        element = connection.execute("SELECT * FROM closure_element WHERE id=?", (element_id,)).fetchone()
        if element is None:
            raise ClosureLineageError(f"closure element not found: {element_id}")
        if method == "closed-manual" and not allow_protected_manual:
            material = " ".join(
                str(value).casefold()
                for value in (element["element_kind"], connection.execute("SELECT accepted_outcome FROM cycle WHERE id=?", (element["cycle_id"],)).fetchone()[0] if element["cycle_id"] else "")
            )
            if any(word in material for word in PROTECTED_GATE_WORDS):
                raise ClosureLineageError("protected production/release/security/compliance closure cannot be manual")
        prior = connection.execute(
            "SELECT id FROM closure_record WHERE element_id=? AND superseded_revision IS NULL",
            (element_id,),
        ).fetchall()
        for row in prior:
            connection.execute("UPDATE closure_record SET superseded_revision=? WHERE id=?", (revision, row["id"]))
        record_id = random_uuid()
        connection.execute(
            "INSERT INTO closure_record VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (
                record_id, element_id, element["subject_revision"], element["subject_digest"], method,
                evidence_health, authorization_ref, json.dumps(sorted(set(evidence))), revision,
            ),
        )
        rebuilt = refresh_projection(connection, revision=revision, changed_element_ids=[element_id])
        return {"record_id": record_id, "element_id": element_id, **rebuilt}

    return document_store.managed_write(
        workspace,
        project_binding=project_binding,
        command="closure-element-close",
        actor=actor,
        callback=apply,
    )


RECIPE_REQUIRED_FIELDS = {
    "obligation_id", "target_identity", "read_class", "write_class", "network_class",
    "credential_class", "production_class", "cost_class", "workspace_boundary", "target_boundary",
    "timeout_seconds", "resource_limit", "retry_limit", "cooldown_seconds", "freshness_seconds",
    "output_schema", "redaction", "pass_semantics", "fail_semantics",
}


def register_recipe(
    workspace: Path,
    *,
    project_binding: str,
    recipe_id: str,
    version: int,
    checker_id: str,
    checker_digest: str,
    declaration: dict[str, Any],
    actor: str,
) -> dict[str, Any]:
    missing = sorted(RECIPE_REQUIRED_FIELDS - set(declaration))
    if missing:
        raise ClosureLineageError("proof recipe lacks: " + ", ".join(missing))
    if len(checker_digest) != 64:
        raise ClosureLineageError("checker digest must be SHA-256")
    recipe_digest = digest(declaration)

    def existing(connection: sqlite3.Connection) -> dict[str, Any] | None:
        row = connection.execute("SELECT * FROM proof_recipe WHERE id=?", (recipe_id,)).fetchone()
        if row is None:
            return None
        if int(row["version"]) == version and row["recipe_digest"] == recipe_digest and row["revoked_revision"] is None:
            return {"recipe_id": recipe_id, "version": version, "recipe_digest": recipe_digest, "idempotent": True}
        raise ClosureLineageError("recipe identity already exists with different immutable content")

    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        connection.execute(
            "INSERT INTO proof_recipe VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
            (recipe_id, version, recipe_digest, checker_id, checker_digest, json.dumps(declaration, sort_keys=True), revision),
        )
        return {"recipe_id": recipe_id, "version": version, "recipe_digest": recipe_digest, "idempotent": False}

    return document_store.managed_write(
        workspace, project_binding=project_binding, command="closure-proof-recipe-register", actor=actor,
        callback=apply, existing=existing,
    )


def record_proof_attempt(
    workspace: Path,
    *,
    project_binding: str,
    recipe_id: str,
    element_id: str,
    target_identity: str,
    state: str,
    result: dict[str, Any],
    actor: str,
    authority_ref: str | None = None,
) -> dict[str, Any]:
    allowed_states = {"passed", "failed", "blocked", "checker-error", "timed-out", "superseded"}
    if state not in allowed_states:
        raise ClosureLineageError("proof result state is invalid")

    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        recipe = connection.execute("SELECT * FROM proof_recipe WHERE id=? AND revoked_revision IS NULL", (recipe_id,)).fetchone()
        element = connection.execute("SELECT * FROM closure_element WHERE id=?", (element_id,)).fetchone()
        if recipe is None or element is None:
            raise ClosureLineageError("proof recipe or element is unavailable")
        declaration = json.loads(recipe["declaration_json"])
        protected = any(
            str(declaration[field]) not in {"none", "read-only", "local", "non-production", "zero"}
            for field in ("write_class", "network_class", "credential_class", "production_class", "cost_class")
        )
        expected_result = {
            "status": "passed",
            "checker_digest": recipe["checker_digest"],
            "recipe_digest": recipe["recipe_digest"],
            "target_identity": target_identity,
            "subject_digest": element["subject_digest"],
        }
        binding_errors = [
            field for field, expected in expected_result.items()
            if result.get(field) != expected
        ]
        if target_identity != declaration["target_identity"]:
            state_value = "blocked"
            result_value = {"reason": "target identity differs from immutable recipe declaration"}
        elif state == "passed" and (not authority_ref or binding_errors):
            state_value = "blocked"
            result_value = {
                "reason": "passed proof lacks exact authority or immutable subject bindings",
                "binding_errors": binding_errors,
            }
        elif protected and not authority_ref:
            state_value = "blocked"
            result_value = {"reason": "explicit current authority required"}
        else:
            state_value = state
            result_value = result
        key = digest(
            [element_id, declaration["obligation_id"], element["subject_revision"], element["subject_digest"], recipe["recipe_digest"], target_identity]
        )
        prior = connection.execute("SELECT * FROM proof_attempt WHERE idempotency_key=?", (key,)).fetchone()
        if prior:
            return {"attempt_id": prior["id"], "state": prior["state"], "idempotent": True}
        attempt_id = random_uuid()
        connection.execute(
            "INSERT INTO proof_attempt VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?)",
            (
                attempt_id, recipe_id, element_id, declaration["obligation_id"], element["subject_revision"],
                element["subject_digest"], target_identity, key, state_value,
                json.dumps(result_value, sort_keys=True), revision, revision,
            ),
        )
        if state_value == "passed":
            prior_records = connection.execute(
                "SELECT id FROM closure_record WHERE element_id=? AND superseded_revision IS NULL", (element_id,)
            ).fetchall()
            for row in prior_records:
                connection.execute("UPDATE closure_record SET superseded_revision=? WHERE id=?", (revision, row["id"]))
            connection.execute(
                "INSERT INTO closure_record VALUES (?, ?, ?, ?, ?, 'closed-loop', 'current', ?, ?, ?, NULL)",
                (
                    random_uuid(), element_id, declaration["obligation_id"], element["subject_revision"],
                    element["subject_digest"], authority_ref or "registered safe proof recipe",
                    json.dumps([f"proof-attempt:{attempt_id}"]), revision,
                ),
            )
        refresh_projection(connection, revision=revision, changed_element_ids=[element_id])
        return {"attempt_id": attempt_id, "state": state_value, "idempotent": False}

    return document_store.managed_write(
        workspace, project_binding=project_binding, command="closure-proof-attempt-record", actor=actor, callback=apply,
    )


def open_recovery_case(
    workspace: Path,
    *,
    project_binding: str,
    element_id: str,
    reason_code: str,
    detail: dict[str, Any],
    actor: str,
) -> dict[str, Any]:
    def existing(connection: sqlite3.Connection) -> dict[str, Any] | None:
        row = connection.execute(
            "SELECT * FROM recovery_case WHERE element_id=? AND reason_code=? "
            "AND state IN ('open','retry-wait','escalated') ORDER BY created_revision LIMIT 1",
            (element_id, reason_code),
        ).fetchone()
        return {"case_id": row["id"], "idempotent": True} if row else None

    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        if connection.execute("SELECT 1 FROM closure_element WHERE id=?", (element_id,)).fetchone() is None:
            raise ClosureLineageError("recovery element is unavailable")
        case_id = random_uuid()
        connection.execute(
            "INSERT INTO recovery_case VALUES (?, ?, ?, 'open', NULL, 0, NULL, ?, ?, ?, NULL)",
            (case_id, element_id, reason_code, json.dumps(detail, sort_keys=True), revision, revision),
        )
        refresh_projection(connection, revision=revision, changed_element_ids=[element_id])
        return {"case_id": case_id, "idempotent": False}

    return document_store.managed_write(
        workspace, project_binding=project_binding, command="closure-recovery-open", actor=actor,
        callback=apply, existing=existing,
    )


def retry_recovery_case(
    workspace: Path,
    *,
    project_binding: str,
    case_id: str,
    owner_ref: str,
    reason: str,
    max_attempts: int,
    cooldown_seconds: int,
    actor: str,
) -> dict[str, Any]:
    if not owner_ref.strip() or not reason.strip():
        raise ClosureLineageError("recovery retry requires an owner and reason")
    if max_attempts < 1 or cooldown_seconds < 0:
        raise ClosureLineageError("recovery retry bounds are invalid")

    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        case = connection.execute("SELECT * FROM recovery_case WHERE id=?", (case_id,)).fetchone()
        if case is None or case["state"] not in {"open", "retry-wait"}:
            raise ClosureLineageError("recovery case is not eligible for retry")
        attempt_count = int(case["attempt_count"]) + 1
        escalated = attempt_count >= max_attempts
        state_value = "escalated" if escalated else "retry-wait"
        next_retry_at = None
        if not escalated:
            next_retry_at = (
                datetime.now(timezone.utc) + timedelta(seconds=cooldown_seconds)
            ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        detail = json.loads(case["detail_json"])
        detail["last_retry"] = {
            "reason": reason,
            "attempt_count": attempt_count,
            "max_attempts": max_attempts,
            "cooldown_seconds": cooldown_seconds,
        }
        connection.execute(
            "UPDATE recovery_case SET state=?, owner_ref=?, attempt_count=?, next_retry_at=?, "
            "detail_json=?, updated_revision=? WHERE id=?",
            (
                state_value, owner_ref, attempt_count, next_retry_at,
                json.dumps(detail, sort_keys=True), revision, case_id,
            ),
        )
        refresh_projection(connection, revision=revision, changed_element_ids=[case["element_id"]])
        return {
            "case_id": case_id,
            "state": state_value,
            "owner_ref": owner_ref,
            "attempt_count": attempt_count,
            "next_retry_at": next_retry_at,
        }

    return document_store.managed_write(
        workspace, project_binding=project_binding, command="closure-recovery-retry", actor=actor,
        callback=apply,
    )


def resolve_recovery_case(
    workspace: Path,
    *,
    project_binding: str,
    case_id: str,
    disposition: str,
    authorization_ref: str,
    reason: str,
    actor: str,
) -> dict[str, Any]:
    mapping = {"restored": "resolved-restored", "reparented": "resolved-reparented", "retired": "resolved-retired"}
    if disposition not in mapping or not authorization_ref.strip() or not reason.strip():
        raise ClosureLineageError("recovery resolution requires an exact disposition, authorization, and reason")

    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        case = connection.execute("SELECT * FROM recovery_case WHERE id=?", (case_id,)).fetchone()
        if case is None or case["state"] not in OPEN_RECOVERY_STATES:
            raise ClosureLineageError("recovery case is not open")
        connection.execute(
            "UPDATE recovery_case SET state=?, detail_json=?, updated_revision=?, closed_revision=? WHERE id=?",
            (mapping[disposition], json.dumps({"reason": reason, "authorization_ref": authorization_ref}, sort_keys=True), revision, revision, case_id),
        )
        if disposition in {"reparented", "retired"}:
            connection.execute(
                "INSERT INTO lineage_tombstone VALUES (?, ?, NULL, ?, ?, ?, ?, ?)",
                (random_uuid(), case["element_id"], disposition, reason, authorization_ref, json.dumps({"case_id": case_id}), revision),
            )
        refresh_projection(connection, revision=revision, changed_element_ids=[case["element_id"]])
        return {"case_id": case_id, "state": mapping[disposition]}

    return document_store.managed_write(
        workspace, project_binding=project_binding, command="closure-recovery-resolve", actor=actor, callback=apply,
    )


def audit_connection(workspace: Path, connection: sqlite3.Connection) -> dict[str, Any]:
    findings: list[str] = []
    user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if user_version != HYBRID_SCHEMA_VERSION:
        findings.append(f"closure lineage requires Hybrid schema 3; found {user_version}")
    missing = set(CLOSURE_TABLES) - _tables(connection)
    if missing:
        findings.append("missing closure tables: " + ", ".join(sorted(missing)))
    base = document_store.audit_connection(workspace, connection)
    findings.extend(base["findings"])
    if not missing:
        for row in connection.execute("SELECT id, envelope_json, envelope_digest FROM closure_element"):
            try:
                envelope = json.loads(row["envelope_json"])
            except json.JSONDecodeError:
                findings.append(f"malformed lineage envelope: {row['id']}")
                continue
            if digest(envelope) != row["envelope_digest"] or envelope.get("element_id") != row["id"]:
                findings.append(f"lineage envelope digest/identity mismatch: {row['id']}")
        graph_findings, _ = _graph_findings(connection)
    else:
        graph_findings = []
    classification = "INVALID" if findings else base["classification"]
    return {
        "schema_version": SCHEMA_VERSION,
        "hybrid_schema": user_version,
        "kind": "tool-shed-closure-lineage-audit",
        "classification": classification,
        "findings": findings,
        "graph_findings": graph_findings,
        "graph_finding_count": len(graph_findings),
        "current_revision": base["current_revision"],
        "last_checkpoint_revision": base["last_checkpoint_revision"],
        "domain_digest": base["domain_digest"],
        "writes_performed": False,
    }


def audit(workspace: Path) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)) as connection:
        return audit_connection(workspace, connection)


def _read_json(workspace: Path, supplied: str) -> dict[str, Any]:
    path = require_path_within(workspace, workspace / supplied)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ClosureLineageError("JSON input must be an object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migration-plan")
    validate = commands.add_parser("migration-validate"); validate.add_argument("--manifest", required=True)
    migrate = commands.add_parser("migrate"); migrate.add_argument("--manifest", required=True); migrate.add_argument("--expect", required=True); migrate.add_argument("--project-binding", required=True)
    commands.add_parser("audit")
    status_parser = commands.add_parser("status"); status_parser.add_argument("identity")
    close = commands.add_parser("close"); close.add_argument("--project-binding", required=True); close.add_argument("--element", required=True); close.add_argument("--method", choices=("closed-loop", "closed-manual"), required=True); close.add_argument("--evidence-health", required=True); close.add_argument("--authorization", required=True); close.add_argument("--evidence", action="append", default=[]); close.add_argument("--actor", default="operator"); close.add_argument("--allow-protected-manual", action="store_true")
    recipe = commands.add_parser("recipe-register"); recipe.add_argument("--project-binding", required=True); recipe.add_argument("--recipe-id", required=True); recipe.add_argument("--version", type=int, required=True); recipe.add_argument("--checker-id", required=True); recipe.add_argument("--checker-digest", required=True); recipe.add_argument("--declaration", required=True); recipe.add_argument("--actor", default="operator")
    attempt = commands.add_parser("proof-record"); attempt.add_argument("--project-binding", required=True); attempt.add_argument("--recipe-id", required=True); attempt.add_argument("--element", required=True); attempt.add_argument("--target", required=True); attempt.add_argument("--state", required=True); attempt.add_argument("--result", required=True); attempt.add_argument("--authority"); attempt.add_argument("--actor", default="operator")
    recovery = commands.add_parser("recovery-open"); recovery.add_argument("--project-binding", required=True); recovery.add_argument("--element", required=True); recovery.add_argument("--reason", required=True); recovery.add_argument("--detail", required=True); recovery.add_argument("--actor", default="operator")
    retry = commands.add_parser("recovery-retry"); retry.add_argument("--project-binding", required=True); retry.add_argument("--case", required=True); retry.add_argument("--owner", required=True); retry.add_argument("--reason", required=True); retry.add_argument("--max-attempts", type=int, required=True); retry.add_argument("--cooldown-seconds", type=int, required=True); retry.add_argument("--actor", default="operator")
    resolve = commands.add_parser("recovery-resolve"); resolve.add_argument("--project-binding", required=True); resolve.add_argument("--case", required=True); resolve.add_argument("--disposition", choices=("restored", "reparented", "retired"), required=True); resolve.add_argument("--authorization", required=True); resolve.add_argument("--reason", required=True); resolve.add_argument("--actor", default="operator")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        workspace = resolved_workspace(Path(args.workspace))
        if args.command == "migration-plan": result = prepare_migration(workspace)
        elif args.command == "migration-validate": result = validate_manifest(workspace, _read_json(workspace, args.manifest))
        elif args.command == "migrate": result = apply_migration(workspace, _read_json(workspace, args.manifest), expected_token=args.expect, project_binding=args.project_binding)
        elif args.command == "audit": result = audit(workspace)
        elif args.command == "status": result = status(workspace, args.identity)
        elif args.command == "close": result = close_element(workspace, project_binding=args.project_binding, element_id=args.element, method=args.method, evidence_health=args.evidence_health, authorization_ref=args.authorization, evidence=args.evidence, actor=args.actor, allow_protected_manual=args.allow_protected_manual)
        elif args.command == "recipe-register": result = register_recipe(workspace, project_binding=args.project_binding, recipe_id=args.recipe_id, version=args.version, checker_id=args.checker_id, checker_digest=args.checker_digest, declaration=_read_json(workspace, args.declaration), actor=args.actor)
        elif args.command == "proof-record": result = record_proof_attempt(workspace, project_binding=args.project_binding, recipe_id=args.recipe_id, element_id=args.element, target_identity=args.target, state=args.state, result=_read_json(workspace, args.result), authority_ref=args.authority, actor=args.actor)
        elif args.command == "recovery-open": result = open_recovery_case(workspace, project_binding=args.project_binding, element_id=args.element, reason_code=args.reason, detail=_read_json(workspace, args.detail), actor=args.actor)
        elif args.command == "recovery-retry": result = retry_recovery_case(workspace, project_binding=args.project_binding, case_id=args.case, owner_ref=args.owner, reason=args.reason, max_attempts=args.max_attempts, cooldown_seconds=args.cooldown_seconds, actor=args.actor)
        else: result = resolve_recovery_case(workspace, project_binding=args.project_binding, case_id=args.case, disposition=args.disposition, authorization_ref=args.authorization, reason=args.reason, actor=args.actor)
        print(json.dumps(result, indent=2, sort_keys=True))
        if args.command in {"migration-validate", "audit"} and not (result.get("valid", True) and result.get("classification", "CLEAN") != "INVALID"):
            return 1
        return 0
    except (ClosureLineageError, document_store.DocumentStoreError, hybrid_state.HybridStateError, ProjectIdentityError, OSError, ValueError, sqlite3.DatabaseError, json.JSONDecodeError) as error:
        print(f"Closure lineage operation failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
