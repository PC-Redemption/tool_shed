#!/usr/bin/env python3
"""Generic project-bound closed-loop outcome reconciliation over hybrid state v1."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import contextlib
import hashlib
import json
import sqlite3
import tempfile
import uuid
from pathlib import Path
from typing import Any

import hybrid_state
from project_identity import load_project_identity, require_path_within, resolved_workspace


SCHEMA_VERSION = 1
SOURCE_KIND = "tool-shed-outcome-reconciliation-source"
MANIFEST_KIND = "tool-shed-outcome-reconciliation-manifest"
TRANSITION_KIND = "tool-shed-outcome-transition-manifest"
TERMINAL_STATES = {"terminal"}
VERDICT_DISPOSITIONS = {
    "open",
    "satisfied",
    "satisfied-with-approved-change",
    "partial",
    "failed",
    "rejected",
    "superseded",
    "parked",
    "not-applicable",
}
RECONCILIATION_STATES = {"open", "reconciliation-required", "reconciled"}
SUPPORTED_ORIGIN_KINDS = {
    "idea",
    "project-map",
    "program-roadmap",
    "milestone",
    "campaign",
    "workpackage",
    "ticket",
    "checklist",
    "spike",
    "adr",
    "inventory",
    "decision-matrix",
    "runbook",
    "direct-work",
    "historical-outcome",
}


class OutcomeLoopError(RuntimeError):
    pass


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def token(payload: dict[str, Any]) -> str:
    material = {key: value for key, value in payload.items() if key != "manifest_token"}
    return hashlib.sha256(canonical_bytes(material)).hexdigest()[:16]


def _uuid(value: object, label: str) -> str:
    try:
        parsed = uuid.UUID(str(value))
    except (ValueError, AttributeError) as error:
        raise OutcomeLoopError(f"{label} must be a canonical UUIDv4") from error
    if parsed.version != 4 or str(parsed) != value:
        raise OutcomeLoopError(f"{label} must be a canonical UUIDv4")
    return str(value)


def _new_uuid(value: object | None, label: str) -> str:
    return _uuid(value, label) if value else str(uuid.uuid4())


def _load_object(workspace: Path, supplied: Path, label: str) -> tuple[Path, dict[str, Any]]:
    path = require_path_within(workspace, supplied if supplied.is_absolute() else workspace / supplied)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise OutcomeLoopError(f"cannot load {label}: {error}") from error
    if not isinstance(payload, dict):
        raise OutcomeLoopError(f"{label} must be a JSON object")
    return path, payload


def _source_artifact(
    workspace: Path,
    connection: sqlite3.Connection,
    raw: dict[str, Any],
    *,
    key: str,
) -> dict[str, Any]:
    relative = str(raw.get("path", ""))
    inline = raw.get("inline")
    if inline is not None:
        artifact_id = _new_uuid(raw.get("id"), f"artifact {key} id")
        relative = relative or f"sqlite/outcome-capsules/{artifact_id}"
        content_sha256 = hashlib.sha256(canonical_bytes(inline)).hexdigest()
    else:
        if not relative:
            raise OutcomeLoopError(f"artifact {key} lacks path")
        path = require_path_within(workspace, workspace / relative)
        if not path.is_file():
            raise OutcomeLoopError(f"artifact {key} does not exist: {relative}")
        relative = path.relative_to(workspace).as_posix()
        content_sha256 = hybrid_state.file_sha256(path)
    existing = connection.execute(
        "SELECT * FROM artifact WHERE current_path = ?", (relative,)
    ).fetchone()
    if existing:
        artifact_id = str(existing["id"])
        supplied_id = raw.get("id")
        if supplied_id and supplied_id != artifact_id:
            raise OutcomeLoopError(f"artifact {key} path already belongs to another identity")
        action = "reference" if existing["content_sha256"] == content_sha256 else "update"
        created_at = str(existing["created_at"])
    else:
        artifact_id = artifact_id if inline is not None else _new_uuid(raw.get("id"), f"artifact {key} id")
        action = "create"
        created_at = str(raw.get("created_at") or hybrid_state.now())
    return {
        "key": key,
        "id": artifact_id,
        "action": action,
        "type": str(raw.get("type") or ("markdown" if relative.endswith(".md") else "file")),
        "display_number": raw.get("display_number"),
        "path": relative,
        "authority_mode": str(raw.get("authority_mode") or ("sqlite" if inline is not None else "file")),
        "lifecycle_state": str(raw.get("lifecycle_state") or "active"),
        "content_sha256": content_sha256,
        "created_at": created_at,
    }


def prepare(workspace: Path, source_path: Path, *, mode: str | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    _, source = _load_object(workspace, source_path, "reconciliation source")
    if source.get("schema_version") != SCHEMA_VERSION or source.get("kind") != SOURCE_KIND:
        raise OutcomeLoopError("unsupported reconciliation source")
    selected_mode = mode or str(source.get("mode") or "current")
    if selected_mode not in {"current", "historical-overlay", "direct"}:
        raise OutcomeLoopError(f"unsupported reconciliation mode: {selected_mode}")
    identity = load_project_identity(workspace)
    supplied_project = source.get("project_id")
    if supplied_project and supplied_project != identity["project_id"]:
        raise OutcomeLoopError("reconciliation source belongs to another Tool Shed project")
    audit = hybrid_state.audit(workspace)
    if audit["classification"] not in {"CLEAN", "VALID_DIRTY", "CHECKPOINT_DUE"}:
        raise OutcomeLoopError(f"cannot prepare from {audit['classification']} hybrid state")
    connection = hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)
    try:
        cycle_raw = source.get("cycle")
        if not isinstance(cycle_raw, dict):
            raise OutcomeLoopError("reconciliation source lacks cycle")
        origin_raw = cycle_raw.get("origin")
        if not isinstance(origin_raw, dict):
            raise OutcomeLoopError("cycle lacks origin artifact")
        artifacts = [_source_artifact(workspace, connection, origin_raw, key="origin")]
        for index, raw in enumerate(source.get("product_truth", []), start=1):
            if not isinstance(raw, dict):
                raise OutcomeLoopError("product_truth entries must be objects")
            artifacts.append(
                _source_artifact(workspace, connection, raw, key=str(raw.get("key") or f"product-{index}"))
            )
        keys = [item["key"] for item in artifacts]
        if len(set(keys)) != len(keys):
            raise OutcomeLoopError("artifact keys must be unique")

        requirements: list[dict[str, Any]] = []
        requirement_ids: dict[str, str] = {}
        for index, raw in enumerate(source.get("requirements", []), start=1):
            key = str(raw.get("key") or f"requirement-{index}")
            if key in requirement_ids:
                raise OutcomeLoopError(f"duplicate requirement key: {key}")
            requirement_id = _new_uuid(raw.get("id"), f"requirement {key} id")
            requirement_ids[key] = requirement_id
            requirements.append(
                {
                    "key": key,
                    "id": requirement_id,
                    "accepted_outcome": str(raw.get("accepted_outcome") or ""),
                    "disposition": str(raw.get("disposition") or "accepted"),
                    "milestone_key": str(raw.get("milestone_key") or "direct"),
                    "evidence_gate_key": str(raw.get("evidence_gate_key") or "direct"),
                }
            )

        changes: list[dict[str, Any]] = []
        for index, raw in enumerate(source.get("changes", []), start=1):
            requirement_key = raw.get("requirement_key")
            if requirement_key and requirement_key not in requirement_ids:
                raise OutcomeLoopError(f"change references unknown requirement: {requirement_key}")
            if not requirement_key and not raw.get("decision_id"):
                raise OutcomeLoopError("each material change needs a requirement_key or decision_id")
            changes.append(
                {
                    "key": str(raw.get("key") or f"change-{index}"),
                    "id": _new_uuid(raw.get("id"), f"change {index} id"),
                    "requirement_key": requirement_key,
                    "decision_id": raw.get("decision_id"),
                    "summary": str(raw.get("summary") or ""),
                    "rationale": str(raw.get("rationale") or ""),
                    "authorization_ref": str(raw.get("authorization_ref") or ""),
                    "supersedes_change_id": raw.get("supersedes_change_id"),
                    "evidence_rerun": list(raw.get("evidence_rerun", [])),
                }
            )

        evidence: list[dict[str, Any]] = []
        evidence_ids: dict[str, str] = {}
        for index, raw in enumerate(source.get("evidence", []), start=1):
            key = str(raw.get("key") or f"evidence-{index}")
            if key in evidence_ids:
                raise OutcomeLoopError(f"duplicate evidence key: {key}")
            evidence_id = _new_uuid(raw.get("id"), f"evidence {key} id")
            evidence_ids[key] = evidence_id
            reference = str(raw.get("reference") or "")
            evidence_hash = raw.get("sha256")
            candidate = workspace / reference
            if reference and candidate.is_file():
                candidate = require_path_within(workspace, candidate)
                evidence_hash = hybrid_state.file_sha256(candidate)
            evidence.append(
                {
                    "key": key,
                    "id": evidence_id,
                    "kind": str(raw.get("kind") or "verification"),
                    "reference": reference,
                    "sha256": evidence_hash,
                    "target_identity": str(raw.get("target_identity") or key),
                    "collected_at": str(raw.get("collected_at") or hybrid_state.now()),
                }
            )

        verifications: list[dict[str, Any]] = []
        for index, raw in enumerate(source.get("verifications", []), start=1):
            evidence_key = str(raw.get("evidence_key") or "")
            requirement_key = raw.get("requirement_key")
            if evidence_key not in evidence_ids:
                raise OutcomeLoopError(f"verification references unknown evidence: {evidence_key}")
            if requirement_key and requirement_key not in requirement_ids:
                raise OutcomeLoopError(f"verification references unknown requirement: {requirement_key}")
            verifications.append(
                {
                    "key": str(raw.get("key") or f"verification-{index}"),
                    "id": _new_uuid(raw.get("id"), f"verification {index} id"),
                    "evidence_key": evidence_key,
                    "requirement_key": requirement_key,
                    "status": str(raw.get("status") or "unknown"),
                    "command_or_test_id": str(raw.get("command_or_test_id") or evidence_key),
                    "verified_at": str(raw.get("verified_at") or hybrid_state.now()),
                    "details": raw.get("details"),
                }
            )

        artifact_by_key = {item["key"]: item for item in artifacts}
        relationships: list[dict[str, Any]] = []
        for index, raw in enumerate(source.get("relationships", []), start=1):
            from_key = str(raw.get("from_artifact_key") or "origin")
            to_key = str(raw.get("to_artifact_key") or "")
            if from_key not in artifact_by_key:
                raise OutcomeLoopError(f"relationship references unknown artifact: {from_key}")
            if to_key not in artifact_by_key:
                # A parent may already exist and be addressed by immutable artifact UUID.
                parent_id = raw.get("to_artifact_id")
                if not parent_id:
                    raise OutcomeLoopError(f"relationship references unknown artifact: {to_key}")
                _uuid(parent_id, f"relationship {index} target")
            else:
                parent_id = artifact_by_key[to_key]["id"]
            relationships.append(
                {
                    "key": str(raw.get("key") or f"relationship-{index}"),
                    "id": _new_uuid(raw.get("id"), f"relationship {index} id"),
                    "from_artifact_id": artifact_by_key[from_key]["id"],
                    "relation_type": str(raw.get("relation_type") or "evidenced-by"),
                    "to_artifact_id": parent_id,
                    "provenance": str(raw.get("provenance") or "outcome-reconciliation-v1"),
                }
            )

        stamp = hybrid_state.now()
        verdict_raw = source.get("verdict") or {}
        reconciliation_raw = source.get("reconciliation") or {}
        manifest: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "kind": MANIFEST_KIND,
            "mode": selected_mode,
            "project_id": identity["project_id"],
            "expected_revision": audit["current_revision"],
            "expected_domain_digest": audit["domain_digest"],
            "prepared_at": stamp,
            "authorization_ref": str(source.get("authorization_ref") or ""),
            "ambiguities": list(source.get("ambiguities", [])),
            "cycle": {
                "id": _new_uuid(cycle_raw.get("id"), "cycle id"),
                "kind": str(cycle_raw.get("kind") or "direct-work"),
                "origin_artifact_id": artifacts[0]["id"],
                "accepted_outcome": str(cycle_raw.get("accepted_outcome") or ""),
                "lifecycle_state": str(cycle_raw.get("lifecycle_state") or "working"),
                "opened_at": str(cycle_raw.get("opened_at") or stamp),
                "closed_at": cycle_raw.get("closed_at"),
            },
            "artifacts": artifacts,
            "requirements": requirements,
            "changes": changes,
            "evidence": evidence,
            "verifications": verifications,
            "relationships": relationships,
            "verdict": {
                "id": _new_uuid(verdict_raw.get("id"), "verdict id"),
                "scope": str(verdict_raw.get("scope") or "cycle"),
                "disposition": str(verdict_raw.get("disposition") or "open"),
                "summary": str(verdict_raw.get("summary") or ""),
                "authorization_ref": str(
                    verdict_raw.get("authorization_ref") or source.get("authorization_ref") or ""
                ),
                "decided_at": str(verdict_raw.get("decided_at") or stamp),
            },
            "reconciliation": {
                "id": _new_uuid(reconciliation_raw.get("id"), "reconciliation id"),
                "product_truth_artifact_ids": [item["id"] for item in artifacts[1:]],
                "state": str(reconciliation_raw.get("state") or "open"),
                "compared_at": str(reconciliation_raw.get("compared_at") or stamp),
                "residual_work": list(reconciliation_raw.get("residual_work", [])),
            },
        }
        manifest["manifest_token"] = token(manifest)
        return manifest
    finally:
        connection.close()


def _prepare_inline_source(workspace: Path, source: dict[str, Any]) -> dict[str, Any]:
    runtime = resolved_workspace(workspace) / ".tool-shed"
    runtime.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix="outcome-source-", suffix=".json", dir=runtime)
    path = Path(name)
    try:
        with open(descriptor, "w", encoding="utf-8", closefd=True) as handle:
            json.dump(source, handle, indent=2, sort_keys=True)
            handle.write("\n")
        return prepare(workspace, path, mode=str(source.get("mode") or "current"))
    finally:
        path.unlink(missing_ok=True)


def _checked_paths(workspace: Path, values: list[str], label: str) -> list[str]:
    if not values:
        raise OutcomeLoopError(f"{label} requires at least one path")
    result: list[str] = []
    for value in values:
        path = require_path_within(workspace, workspace / value)
        if not path.is_file():
            raise OutcomeLoopError(f"{label} path does not exist: {value}")
        result.append(path.relative_to(workspace).as_posix())
    return result


def plan_campaign_result(
    workspace: Path,
    campaign_path: Path,
    *,
    product_truth: list[str],
    evidence_paths: list[str],
    disposition: str,
    authorization_ref: str,
    residual_work: list[str] | None = None,
    historical: bool = False,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    path = require_path_within(
        workspace, campaign_path if campaign_path.is_absolute() else workspace / campaign_path
    )
    if not path.is_file() or path.parent.name != "completed":
        raise OutcomeLoopError("campaign result requires a completed campaign artifact")
    fields: dict[str, str] = {}
    title = path.stem
    for line in path.read_text(encoding="utf-8").splitlines()[:60]:
        if line.startswith("# "):
            title = line[2:].strip()
        elif ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    if fields.get("Status") != "complete" or fields.get("Disposition") != "completed":
        raise OutcomeLoopError("campaign result requires terminal completed lifecycle state")
    if not fields.get("Outcome") or not fields.get("Completion Gate") or not fields.get("Completion Evidence"):
        raise OutcomeLoopError("completed campaign lacks outcome, gate, or completion evidence")
    if disposition not in {"satisfied", "satisfied-with-approved-change"}:
        raise OutcomeLoopError("completed campaign disposition must be satisfied or satisfied-with-approved-change")
    products = _checked_paths(workspace, product_truth, "campaign product truth")
    evidence = _checked_paths(workspace, evidence_paths, "campaign evidence")
    relative = path.relative_to(workspace).as_posix()
    governance_paths = [relative]
    roadmap_id = fields.get("Roadmap", "none")
    if roadmap_id != "none":
        governance_paths.extend(
            candidate.relative_to(workspace).as_posix()
            for candidate in (workspace / "work" / "roadmaps").glob("*.md")
            if f"Roadmap ID: {roadmap_id}" in candidate.read_text(encoding="utf-8")
        )
    capsule = owning_outcome_capsule(workspace, origin_paths=governance_paths)
    parent = capsule.get("nearest_open_owning_loop")
    relationships: list[dict[str, Any]] = [
        {
            "key": f"product-{index}",
            "from_artifact_key": "origin",
            "to_artifact_key": f"product-{index}",
            "relation_type": "evidenced-by",
        }
        for index, _ in enumerate(products, start=1)
    ]
    if parent:
        connection = hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)
        try:
            row = connection.execute(
                "SELECT origin_artifact_id FROM cycle WHERE id = ?", (parent["cycle_id"],)
            ).fetchone()
        finally:
            connection.close()
        if row:
            for relation_type in ("outcome-parent", "outcome-result-propagated"):
                relationships.append(
                    {
                        "key": relation_type,
                        "from_artifact_key": "origin",
                        "to_artifact_id": str(row["origin_artifact_id"]),
                        "relation_type": relation_type,
                    }
                )
    source = {
        "schema_version": SCHEMA_VERSION,
        "kind": SOURCE_KIND,
        "mode": "historical-overlay" if historical else "current",
        "project_id": load_project_identity(workspace)["project_id"],
        "authorization_ref": authorization_ref,
        "ambiguities": [],
        "cycle": {
            "kind": "campaign",
            "origin": {"path": relative, "type": "campaign", "lifecycle_state": "complete"},
            "accepted_outcome": fields["Outcome"],
            "lifecycle_state": "terminal",
            "opened_at": fields.get("Updated") or hybrid_state.now(),
            "closed_at": fields.get("Completion Date") or hybrid_state.now(),
        },
        "product_truth": [
            {"key": f"product-{index}", "path": value}
            for index, value in enumerate(products, start=1)
        ],
        "requirements": [
            {
                "key": "campaign-outcome",
                "accepted_outcome": fields["Completion Gate"],
                "disposition": "accepted",
                "milestone_key": fields.get("Milestone") or "campaign",
                "evidence_gate_key": fields.get("Unlocks Gate") or "campaign-completion",
            }
        ],
        "changes": [],
        "evidence": [
            {
                "key": f"evidence-{index}",
                "kind": "campaign-completion",
                "reference": value,
                "target_identity": fields.get("Campaign ID") or title,
            }
            for index, value in enumerate(evidence, start=1)
        ],
        "verifications": [
            {
                "key": f"verification-{index}",
                "evidence_key": f"evidence-{index}",
                "requirement_key": "campaign-outcome",
                "status": "passed",
                "command_or_test_id": fields["Completion Gate"],
                "verified_at": fields.get("Completion Date") or hybrid_state.now(),
                "details": {"completion_evidence": fields["Completion Evidence"]},
            }
            for index, _ in enumerate(evidence, start=1)
        ],
        "relationships": relationships,
        "verdict": {
            "scope": fields.get("Campaign ID") or title,
            "disposition": disposition,
            "summary": fields["Completion Evidence"],
            "authorization_ref": authorization_ref,
            "decided_at": fields.get("Completion Date") or hybrid_state.now(),
        },
        "reconciliation": {
            "state": "reconciled",
            "compared_at": fields.get("Completion Date") or hybrid_state.now(),
            "residual_work": list(residual_work or []),
        },
    }
    return _prepare_inline_source(workspace, source)


def plan_direct_result(
    workspace: Path,
    *,
    origin_summary: str,
    accepted_outcome: str,
    product_truth: list[str],
    evidence_paths: list[str],
    disposition: str,
    authorization_ref: str,
    parent_cycle_id: str | None = None,
    residual_work: list[str] | None = None,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    if disposition not in VERDICT_DISPOSITIONS - {"open"}:
        raise OutcomeLoopError("direct result requires a terminal outcome disposition")
    products = _checked_paths(workspace, product_truth, "direct product truth")
    evidence = _checked_paths(workspace, evidence_paths, "direct evidence")
    origin_id = str(uuid.uuid4())
    relationships: list[dict[str, Any]] = [
        {
            "key": f"product-{index}",
            "from_artifact_key": "origin",
            "to_artifact_key": f"product-{index}",
            "relation_type": "evidenced-by",
        }
        for index, _ in enumerate(products, start=1)
    ]
    if parent_cycle_id:
        _uuid(parent_cycle_id, "parent cycle id")
        connection = hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)
        try:
            row = connection.execute(
                "SELECT origin_artifact_id FROM cycle WHERE id = ?", (parent_cycle_id,)
            ).fetchone()
        finally:
            connection.close()
        if not row:
            raise OutcomeLoopError(f"parent cycle does not exist: {parent_cycle_id}")
        for relation_type in ("outcome-parent", "outcome-result-propagated"):
            relationships.append(
                {
                    "key": relation_type,
                    "from_artifact_key": "origin",
                    "to_artifact_id": str(row["origin_artifact_id"]),
                    "relation_type": relation_type,
                }
            )
    stamp = hybrid_state.now()
    source = {
        "schema_version": SCHEMA_VERSION,
        "kind": SOURCE_KIND,
        "mode": "direct",
        "project_id": load_project_identity(workspace)["project_id"],
        "authorization_ref": authorization_ref,
        "ambiguities": [],
        "cycle": {
            "kind": "direct-work",
            "origin": {
                "id": origin_id,
                "inline": {"summary": origin_summary, "accepted_outcome": accepted_outcome},
                "type": "direct-capsule",
                "authority_mode": "sqlite",
                "lifecycle_state": "terminal",
            },
            "accepted_outcome": accepted_outcome,
            "lifecycle_state": "terminal",
            "opened_at": stamp,
            "closed_at": stamp,
        },
        "product_truth": [
            {"key": f"product-{index}", "path": value}
            for index, value in enumerate(products, start=1)
        ],
        "requirements": [
            {
                "key": "direct-outcome",
                "accepted_outcome": accepted_outcome,
                "disposition": "accepted",
                "milestone_key": "direct",
                "evidence_gate_key": "direct-evidence",
            }
        ],
        "changes": [],
        "evidence": [
            {
                "key": f"evidence-{index}",
                "kind": "direct-verification",
                "reference": value,
                "target_identity": origin_id,
            }
            for index, value in enumerate(evidence, start=1)
        ],
        "verifications": [
            {
                "key": f"verification-{index}",
                "evidence_key": f"evidence-{index}",
                "requirement_key": "direct-outcome",
                "status": "passed",
                "command_or_test_id": f"direct-evidence-{index}",
                "verified_at": stamp,
            }
            for index, _ in enumerate(evidence, start=1)
        ],
        "relationships": relationships,
        "verdict": {
            "scope": "direct-work",
            "disposition": disposition,
            "summary": origin_summary,
            "authorization_ref": authorization_ref,
            "decided_at": stamp,
        },
        "reconciliation": {
            "state": "reconciled",
            "compared_at": stamp,
            "residual_work": list(residual_work or []),
        },
    }
    return _prepare_inline_source(workspace, source)


def validate_manifest(workspace: Path, manifest: dict[str, Any], *, check_state: bool = True) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    errors: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("kind") != MANIFEST_KIND:
        errors.append("unsupported reconciliation manifest")
    if manifest.get("project_id") != load_project_identity(workspace)["project_id"]:
        errors.append("manifest belongs to another Tool Shed project")
    if manifest.get("manifest_token") != token(manifest):
        errors.append("manifest token does not match content")
    if manifest.get("mode") not in {"current", "historical-overlay", "direct"}:
        errors.append("manifest mode is invalid")
    cycle = manifest.get("cycle") or {}
    for label, value in (
        ("cycle id", cycle.get("id")),
        ("cycle origin_artifact_id", cycle.get("origin_artifact_id")),
        ("verdict id", (manifest.get("verdict") or {}).get("id")),
        ("reconciliation id", (manifest.get("reconciliation") or {}).get("id")),
    ):
        try:
            _uuid(value, label)
        except OutcomeLoopError as error:
            errors.append(str(error))
    if not cycle.get("accepted_outcome"):
        errors.append("cycle accepted_outcome is required")
    lifecycle = cycle.get("lifecycle_state")
    if cycle.get("kind") not in SUPPORTED_ORIGIN_KINDS:
        errors.append("cycle kind is not a supported durable origin class")
    verdict = manifest.get("verdict") or {}
    reconciliation = manifest.get("reconciliation") or {}
    if verdict.get("disposition") not in VERDICT_DISPOSITIONS:
        errors.append("verdict disposition is invalid")
    if reconciliation.get("state") not in RECONCILIATION_STATES:
        errors.append("reconciliation state is invalid")
    if lifecycle in TERMINAL_STATES and not cycle.get("closed_at"):
        errors.append("terminal cycle requires closed_at")
    if reconciliation.get("state") == "reconciled" and verdict.get("disposition") == "open":
        errors.append("reconciled cycle cannot have an open verdict")
    if verdict.get("disposition") != "open" and not verdict.get("authorization_ref"):
        errors.append("non-open verdict requires authorization_ref")

    identifiers: list[str] = []
    for group in ("artifacts", "requirements", "changes", "evidence", "verifications", "relationships"):
        for index, item in enumerate(manifest.get(group, []), start=1):
            try:
                identifiers.append(_uuid(item.get("id"), f"{group} item {index} id"))
            except OutcomeLoopError as error:
                errors.append(str(error))
    identifiers.extend(value for value in (cycle.get("id"), verdict.get("id"), reconciliation.get("id")) if value)
    if len(identifiers) != len(set(identifiers)):
        errors.append("manifest identities must be unique")
    artifact_ids: set[str] = set()
    artifact_paths: set[str] = set()
    for item in manifest.get("artifacts", []):
        if item.get("id") in artifact_ids:
            errors.append("artifact identities must be unique")
        artifact_ids.add(item.get("id"))
        if item.get("path") in artifact_paths:
            errors.append("artifact paths must be unique")
        artifact_paths.add(item.get("path"))
        if item.get("action") not in {"create", "reference", "update"}:
            errors.append(f"artifact {item.get('key')} action is invalid")
        if item.get("authority_mode") not in {"file", "sqlite", "projection"}:
            errors.append(f"artifact {item.get('key')} authority_mode is invalid")
        if len(str(item.get("content_sha256") or "")) != 64:
            errors.append(f"artifact {item.get('key')} content hash is invalid")
    requirement_keys = {item.get("key") for item in manifest.get("requirements", [])}
    evidence_keys = {item.get("key") for item in manifest.get("evidence", [])}
    if len(requirement_keys) != len(manifest.get("requirements", [])):
        errors.append("requirement keys must be unique")
    if len(evidence_keys) != len(manifest.get("evidence", [])):
        errors.append("evidence keys must be unique")
    for change in manifest.get("changes", []):
        if change.get("requirement_key") and change["requirement_key"] not in requirement_keys:
            errors.append(f"change references unknown requirement: {change['requirement_key']}")
        if not change.get("evidence_rerun"):
            errors.append(f"material change {change.get('key')} lacks evidence_rerun")
        unknown_reruns = sorted(set(change.get("evidence_rerun", [])) - evidence_keys)
        if unknown_reruns:
            errors.append(
                f"material change {change.get('key')} references unknown evidence: "
                + ", ".join(unknown_reruns)
            )
        if not change.get("authorization_ref"):
            errors.append(f"material change {change.get('key')} lacks authorization_ref")
    for verification in manifest.get("verifications", []):
        if verification.get("evidence_key") not in evidence_keys:
            errors.append(f"verification references unknown evidence: {verification.get('evidence_key')}")
    relationship_pairs: set[tuple[str, str, str]] = set()
    parent_pairs: set[tuple[str, str]] = set()
    propagated_pairs: set[tuple[str, str]] = set()
    for relationship in manifest.get("relationships", []):
        source = relationship.get("from_artifact_id")
        target = relationship.get("to_artifact_id")
        relation_type = relationship.get("relation_type")
        pair = (str(source), str(relation_type), str(target))
        if source == target:
            errors.append("relationship cannot point an artifact to itself")
        if pair in relationship_pairs:
            errors.append("manifest contains a duplicate relationship")
        relationship_pairs.add(pair)
        if relation_type == "outcome-parent":
            parent_pairs.add((str(source), str(target)))
        elif relation_type == "outcome-result-propagated":
            propagated_pairs.add((str(source), str(target)))
    if lifecycle in TERMINAL_STATES and reconciliation.get("state") == "reconciled":
        missing_propagation = sorted(parent_pairs - propagated_pairs)
        if missing_propagation:
            errors.append("terminal reconciled child lacks outcome-result-propagated relationship")
    if propagated_pairs - parent_pairs:
        errors.append("outcome-result-propagated relationship lacks matching outcome-parent")
    if reconciliation.get("state") == "reconciled":
        statuses = {item.get("status") for item in manifest.get("verifications", [])}
        if statuses - {"passed", "not-applicable"}:
            errors.append("reconciled cycle has non-passing verification")
        verified_requirements = {
            item.get("requirement_key") for item in manifest.get("verifications", []) if item.get("status") == "passed"
        }
        uncovered = sorted(key for key in requirement_keys if key not in verified_requirements)
        if uncovered:
            errors.append("requirements lack passing evidence: " + ", ".join(uncovered))
    if check_state and not errors:
        audit = hybrid_state.audit(workspace)
        if manifest.get("expected_revision") != audit["current_revision"]:
            errors.append("manifest expected_revision is stale")
        if manifest.get("expected_domain_digest") != audit["domain_digest"]:
            errors.append("manifest expected_domain_digest is stale")
        if not errors and manifest.get("relationships"):
            connection = hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)
            try:
                graph: dict[str, set[str]] = {}
                for row in connection.execute(
                    "SELECT from_artifact_id, to_artifact_id FROM relationship "
                    "WHERE relation_type = 'outcome-parent' AND retired_revision IS NULL"
                ).fetchall():
                    graph.setdefault(str(row["from_artifact_id"]), set()).add(str(row["to_artifact_id"]))
                for source, target in parent_pairs:
                    graph.setdefault(source, set()).add(target)
                manifest_artifacts = _artifact_ids(manifest)
                for relationship in manifest.get("relationships", []):
                    for artifact_id in (
                        relationship.get("from_artifact_id"), relationship.get("to_artifact_id")
                    ):
                        if artifact_id not in manifest_artifacts and not connection.execute(
                            "SELECT 1 FROM artifact WHERE id = ?", (artifact_id,)
                        ).fetchone():
                            errors.append(f"relationship artifact does not exist: {artifact_id}")
                for group in (
                    "requirements", "changes", "evidence", "verifications", "relationships"
                ):
                    table = {
                        "requirements": "requirement",
                        "changes": "material_change",
                        "evidence": "evidence_reference",
                        "verifications": "verification_result",
                        "relationships": "relationship",
                    }[group]
                    for item in manifest.get(group, []):
                        if connection.execute(
                            f"SELECT 1 FROM {table} WHERE id = ?", (item["id"],)
                        ).fetchone():
                            errors.append(f"{group} identity already exists: {item['id']}")
                for table, entity_id in (
                    ("cycle", cycle.get("id")),
                    ("outcome_verdict", verdict.get("id")),
                    ("reconciliation", reconciliation.get("id")),
                ):
                    if connection.execute(
                        f"SELECT 1 FROM {table} WHERE id = ?", (entity_id,)
                    ).fetchone():
                        errors.append(f"{table} identity already exists: {entity_id}")

                def cyclic(node: str, visiting: set[str], visited: set[str]) -> bool:
                    if node in visiting:
                        return True
                    if node in visited:
                        return False
                    visiting.add(node)
                    if any(cyclic(parent, visiting, visited) for parent in graph.get(node, set())):
                        return True
                    visiting.remove(node)
                    visited.add(node)
                    return False

                visited: set[str] = set()
                if parent_pairs and any(cyclic(node, set(), visited) for node in graph):
                    errors.append("outcome-parent graph contains a cycle")
            finally:
                connection.close()
    ambiguities = list(manifest.get("ambiguities", []))
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-outcome-reconciliation-validation",
        "manifest_token": manifest.get("manifest_token"),
        "valid": not errors,
        "applicable": not errors and not ambiguities,
        "errors": errors,
        "ambiguities": ambiguities,
        "writes_performed": False,
    }


def _artifact_ids(manifest: dict[str, Any]) -> set[str]:
    return {item["id"] for item in manifest.get("artifacts", [])}


def apply_manifest(
    workspace: Path,
    manifest: dict[str, Any],
    *,
    expected_token: str,
    project_binding: str,
    backfill: bool = False,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    validation = validate_manifest(workspace, manifest)
    if not validation["valid"]:
        raise OutcomeLoopError("manifest validation failed: " + "; ".join(validation["errors"]))
    if manifest.get("manifest_token") != expected_token:
        raise OutcomeLoopError("approved manifest token does not match")
    if validation["ambiguities"]:
        raise OutcomeLoopError("manifest retains unresolved ambiguities")
    if backfill != (manifest.get("mode") == "historical-overlay"):
        expected = "historical-overlay" if backfill else "current or direct"
        raise OutcomeLoopError(f"apply mode must be {expected}")

    requirements = {item["key"]: item for item in manifest.get("requirements", [])}
    evidence = {item["key"]: item for item in manifest.get("evidence", [])}
    cycle = manifest["cycle"]
    verdict = manifest["verdict"]
    reconciliation = manifest["reconciliation"]
    relationship_items = manifest.get("relationships", [])
    existing_relationships: dict[tuple[str, str, str], str] = {}
    with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)) as connection:
        for item in relationship_items:
            key = (
                item["from_artifact_id"], item["relation_type"], item["to_artifact_id"]
            )
            existing = hybrid_state.active_relationship(connection, *key)
            if existing is not None:
                existing_relationships[key] = str(existing["id"])

    def write(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        meta = hybrid_state.meta_row(connection)
        if meta["current_revision"] != manifest["expected_revision"]:
            raise OutcomeLoopError("manifest revision changed before transaction")
        if hybrid_state.domain_digest(connection) != manifest["expected_domain_digest"]:
            raise OutcomeLoopError("manifest domain digest changed before transaction")
        for item in manifest.get("artifacts", []):
            if item["action"] == "create":
                connection.execute(
                    "INSERT INTO artifact VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        item["id"], item["type"], item.get("display_number"), item["path"],
                        item["authority_mode"], item["lifecycle_state"], item["content_sha256"],
                        item["created_at"], manifest["prepared_at"],
                    ),
                )
            elif item["action"] == "update":
                connection.execute(
                    "UPDATE artifact SET type = ?, display_number = ?, authority_mode = ?, "
                    "lifecycle_state = ?, content_sha256 = ?, updated_at = ? WHERE id = ?",
                    (
                        item["type"], item.get("display_number"), item["authority_mode"],
                        item["lifecycle_state"], item["content_sha256"], manifest["prepared_at"], item["id"],
                    ),
                )
        connection.execute(
            "INSERT INTO cycle VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                cycle["id"], cycle["kind"], cycle["origin_artifact_id"], cycle["accepted_outcome"],
                cycle["lifecycle_state"], cycle["opened_at"], cycle.get("closed_at"),
            ),
        )
        for item in requirements.values():
            connection.execute(
                "INSERT INTO requirement VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item["id"], cycle["id"], cycle["origin_artifact_id"], item["accepted_outcome"],
                    item["disposition"], revision, item["milestone_key"], item["evidence_gate_key"],
                ),
            )
        for item in manifest.get("changes", []):
            requirement_id = requirements[item["requirement_key"]]["id"] if item.get("requirement_key") else None
            connection.execute(
                "INSERT INTO material_change VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item["id"], cycle["id"], requirement_id, item.get("decision_id"), item["summary"],
                    item["rationale"], item["authorization_ref"], item.get("supersedes_change_id"),
                    json.dumps(item["evidence_rerun"], sort_keys=True), revision,
                ),
            )
        for item in evidence.values():
            connection.execute(
                "INSERT INTO evidence_reference VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    item["id"], cycle["id"], item["kind"], item["reference"], item.get("sha256"),
                    item["target_identity"], item["collected_at"],
                ),
            )
        for item in manifest.get("verifications", []):
            requirement_id = requirements[item["requirement_key"]]["id"] if item.get("requirement_key") else None
            connection.execute(
                "INSERT INTO verification_result VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item["id"], evidence[item["evidence_key"]]["id"], requirement_id, item["status"],
                    item["command_or_test_id"], revision, item["verified_at"],
                    json.dumps(item.get("details"), sort_keys=True) if item.get("details") is not None else None,
                ),
            )
        connection.execute(
            "INSERT INTO outcome_verdict VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                verdict["id"], cycle["id"], verdict["scope"], verdict["disposition"], verdict["summary"],
                verdict["authorization_ref"], revision, verdict["decided_at"],
            ),
        )
        connection.execute(
            "INSERT INTO reconciliation VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                reconciliation["id"], cycle["id"], revision,
                json.dumps(reconciliation["product_truth_artifact_ids"], sort_keys=True), verdict["id"],
                reconciliation["state"], reconciliation["compared_at"],
                json.dumps(reconciliation["residual_work"], sort_keys=True),
            ),
        )
        known_artifacts = _artifact_ids(manifest)
        reused_relationship_ids: list[str] = []
        for item in relationship_items:
            for artifact_id in (item["from_artifact_id"], item["to_artifact_id"]):
                if artifact_id not in known_artifacts and not connection.execute(
                    "SELECT 1 FROM artifact WHERE id = ?", (artifact_id,)
                ).fetchone():
                    raise OutcomeLoopError(f"relationship artifact does not exist: {artifact_id}")
            key = (
                item["from_artifact_id"], item["relation_type"], item["to_artifact_id"]
            )
            if key in existing_relationships:
                reused_relationship_ids.append(existing_relationships[key])
                continue
            connection.execute(
                "INSERT INTO relationship VALUES (?, ?, ?, ?, ?, ?, NULL)",
                (
                    item["id"], item["from_artifact_id"], item["relation_type"],
                    item["to_artifact_id"], item["provenance"], revision,
                ),
            )
        return {
            "cycle_id": cycle["id"],
            "manifest_token": manifest["manifest_token"],
            "mode": manifest["mode"],
            "verdict": verdict["disposition"],
            "reconciliation": reconciliation["state"],
            "reused_relationship_ids": reused_relationship_ids,
        }

    expected_writes = (
        sum(item["action"] != "reference" for item in manifest.get("artifacts", []))
        + 1
        + len(requirements)
        + len(manifest.get("changes", []))
        + len(evidence)
        + len(manifest.get("verifications", []))
        + 1
        + 1
        + len(relationship_items)
        - len(existing_relationships)
    )
    return hybrid_state.managed_write(
        workspace,
        project_binding=project_binding,
        command="backfill-outcome-loop" if backfill else "apply-outcome-loop",
        actor="outcome-reconciliation",
        callback=write,
        expected_writes=expected_writes,
    )


def prepare_transition(
    workspace: Path,
    cycle_id: str,
    *,
    lifecycle_state: str,
    disposition: str,
    reconciliation_state: str,
    summary: str,
    authorization_ref: str,
    supporting_cycle_ids: list[str],
    residual_work: list[str] | None = None,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    _uuid(cycle_id, "cycle id")
    if lifecycle_state != "terminal":
        raise OutcomeLoopError("outcome transition v1 supports terminal closure only")
    if disposition not in VERDICT_DISPOSITIONS - {"open"}:
        raise OutcomeLoopError("transition requires a terminal outcome disposition")
    if reconciliation_state != "reconciled":
        raise OutcomeLoopError("terminal transition must explicitly reconcile the outcome")
    if not authorization_ref:
        raise OutcomeLoopError("transition requires authorization_ref")
    if not supporting_cycle_ids:
        raise OutcomeLoopError("transition requires at least one supporting cycle")
    for child_id in supporting_cycle_ids:
        _uuid(child_id, "supporting cycle id")
    state = hybrid_state.audit(workspace)
    connection = hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)
    try:
        cycle = connection.execute("SELECT * FROM cycle WHERE id = ?", (cycle_id,)).fetchone()
        if not cycle:
            raise OutcomeLoopError(f"cycle does not exist: {cycle_id}")
        if cycle["lifecycle_state"] == "terminal":
            raise OutcomeLoopError("cycle is already terminal")
        latest = connection.execute(
            "SELECT r.product_truth_ref FROM reconciliation r WHERE r.cycle_id = ? "
            "ORDER BY r.origin_revision DESC LIMIT 1", (cycle_id,)
        ).fetchone()
        if not latest:
            raise OutcomeLoopError("cycle has no reconciliation state to transition")
        children: list[dict[str, Any]] = []
        for child_id in supporting_cycle_ids:
            child = connection.execute(
                "SELECT c.id, c.lifecycle_state, c.origin_artifact_id, v.disposition, r.state "
                "FROM cycle c JOIN reconciliation r ON r.cycle_id = c.id AND r.origin_revision = "
                "(SELECT MAX(r2.origin_revision) FROM reconciliation r2 WHERE r2.cycle_id = c.id) "
                "JOIN outcome_verdict v ON v.id = r.verdict_id WHERE c.id = ?", (child_id,)
            ).fetchone()
            if not child:
                raise OutcomeLoopError(f"supporting cycle is incomplete or missing: {child_id}")
            propagated = connection.execute(
                "SELECT 1 FROM relationship WHERE from_artifact_id = ? AND to_artifact_id = ? "
                "AND relation_type = 'outcome-result-propagated' AND retired_revision IS NULL",
                (child["origin_artifact_id"], cycle["origin_artifact_id"]),
            ).fetchone()
            if not propagated:
                raise OutcomeLoopError(f"supporting cycle did not propagate to parent: {child_id}")
            if disposition in {"satisfied", "satisfied-with-approved-change"} and (
                child["lifecycle_state"] != "terminal"
                or child["state"] != "reconciled"
                or child["disposition"] not in {"satisfied", "satisfied-with-approved-change", "not-applicable"}
            ):
                raise OutcomeLoopError(f"supporting cycle cannot satisfy parent: {child_id}")
            children.append(dict(child))
        manifest: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "kind": TRANSITION_KIND,
            "project_id": load_project_identity(workspace)["project_id"],
            "expected_revision": state["current_revision"],
            "expected_domain_digest": state["domain_digest"],
            "prepared_at": hybrid_state.now(),
            "cycle_id": cycle_id,
            "origin_artifact_id": str(cycle["origin_artifact_id"]),
            "lifecycle_state": lifecycle_state,
            "closed_at": hybrid_state.now(),
            "verdict": {
                "id": str(uuid.uuid4()),
                "scope": "initiative",
                "disposition": disposition,
                "summary": summary,
                "authorization_ref": authorization_ref,
                "decided_at": hybrid_state.now(),
            },
            "reconciliation": {
                "id": str(uuid.uuid4()),
                "state": reconciliation_state,
                "product_truth_ref": str(latest["product_truth_ref"]),
                "compared_at": hybrid_state.now(),
                "residual_work": list(residual_work or []),
            },
            "supporting_cycle_ids": supporting_cycle_ids,
        }
        manifest["manifest_token"] = token(manifest)
        return manifest
    finally:
        connection.close()


def apply_transition(
    workspace: Path,
    manifest: dict[str, Any],
    *,
    expected_token: str,
    project_binding: str,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    if manifest.get("kind") != TRANSITION_KIND or manifest.get("schema_version") != SCHEMA_VERSION:
        raise OutcomeLoopError("unsupported outcome transition manifest")
    if manifest.get("project_id") != load_project_identity(workspace)["project_id"]:
        raise OutcomeLoopError("transition belongs to another Tool Shed project")
    if manifest.get("manifest_token") != token(manifest) or expected_token != manifest.get("manifest_token"):
        raise OutcomeLoopError("approved transition token does not match")
    audit = hybrid_state.audit(workspace)
    if manifest.get("expected_revision") != audit["current_revision"]:
        raise OutcomeLoopError("transition expected_revision is stale")
    if manifest.get("expected_domain_digest") != audit["domain_digest"]:
        raise OutcomeLoopError("transition expected_domain_digest is stale")

    def write(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        if hybrid_state.meta_row(connection)["current_revision"] != manifest["expected_revision"]:
            raise OutcomeLoopError("transition revision changed before transaction")
        if hybrid_state.domain_digest(connection) != manifest["expected_domain_digest"]:
            raise OutcomeLoopError("transition domain digest changed before transaction")
        verdict = manifest["verdict"]
        reconciliation = manifest["reconciliation"]
        cursor = connection.execute(
            "UPDATE cycle SET lifecycle_state = ?, closed_at = ? WHERE id = ? AND lifecycle_state <> 'terminal'",
            (manifest["lifecycle_state"], manifest["closed_at"], manifest["cycle_id"]),
        )
        if cursor.rowcount != 1:
            raise OutcomeLoopError("transition target is missing or already terminal")
        connection.execute(
            "INSERT INTO outcome_verdict VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                verdict["id"], manifest["cycle_id"], verdict["scope"], verdict["disposition"],
                verdict["summary"], verdict["authorization_ref"], revision, verdict["decided_at"],
            ),
        )
        connection.execute(
            "INSERT INTO reconciliation VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                reconciliation["id"], manifest["cycle_id"], revision,
                reconciliation["product_truth_ref"], verdict["id"], reconciliation["state"],
                reconciliation["compared_at"], json.dumps(reconciliation["residual_work"], sort_keys=True),
            ),
        )
        return {
            "cycle_id": manifest["cycle_id"],
            "manifest_token": manifest["manifest_token"],
            "lifecycle": manifest["lifecycle_state"],
            "verdict": verdict["disposition"],
            "reconciliation": reconciliation["state"],
            "supporting_cycle_ids": manifest["supporting_cycle_ids"],
        }

    return hybrid_state.managed_write(
        workspace,
        project_binding=project_binding,
        command="transition-outcome-loop",
        actor="outcome-reconciliation",
        callback=write,
        expected_writes=3,
    )


def audit_loops(workspace: Path) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    connection = hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)
    try:
        rows = connection.execute(
            "SELECT c.id, c.kind, c.lifecycle_state, c.origin_artifact_id, a.current_path, "
            "v.disposition, r.state FROM cycle c JOIN artifact a ON a.id = c.origin_artifact_id "
            "LEFT JOIN reconciliation r ON r.cycle_id = c.id AND r.origin_revision = "
            "(SELECT MAX(r2.origin_revision) FROM reconciliation r2 WHERE r2.cycle_id = c.id) "
            "LEFT JOIN outcome_verdict v ON v.id = r.verdict_id ORDER BY c.opened_at, c.id"
        ).fetchall()
        open_loops: list[str] = []
        terminal_unreconciled: list[str] = []
        invalid: list[str] = []
        cycles: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            cycles.append(item)
            if row["lifecycle_state"] not in TERMINAL_STATES or row["disposition"] == "open":
                open_loops.append(row["id"])
            if row["lifecycle_state"] in TERMINAL_STATES and row["state"] != "reconciled":
                terminal_unreconciled.append(row["id"])
            if row["state"] == "reconciled" and (row["disposition"] in {None, "open"}):
                invalid.append(row["id"])
        unpropagated = [
            row["cycle_id"]
            for row in connection.execute(
                "SELECT c.id AS cycle_id FROM cycle c JOIN relationship p "
                "ON p.from_artifact_id = c.origin_artifact_id AND p.relation_type = 'outcome-parent' "
                "WHERE c.lifecycle_state = 'terminal' AND p.retired_revision IS NULL "
                "AND COALESCE((SELECT r.state FROM reconciliation r WHERE r.cycle_id = c.id "
                "ORDER BY r.origin_revision DESC, r.id DESC LIMIT 1), 'open') = 'reconciled' "
                "AND NOT EXISTS (SELECT 1 FROM relationship x "
                "WHERE x.from_artifact_id = p.from_artifact_id AND x.to_artifact_id = p.to_artifact_id "
                "AND x.relation_type = 'outcome-result-propagated' AND x.retired_revision IS NULL)"
            ).fetchall()
        ]
        state = hybrid_state.audit(workspace)
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "tool-shed-outcome-loop-audit",
            "revision": state["current_revision"],
            "cycles": cycles,
            "open": open_loops,
            "terminal_unreconciled": terminal_unreconciled,
            "invalid": invalid,
            "unpropagated": unpropagated,
            "finding_count": len(open_loops) + len(terminal_unreconciled) + len(invalid) + len(unpropagated),
            "writes_performed": False,
        }
    finally:
        connection.close()


def owning_outcome_capsule(
    workspace: Path,
    *,
    origin_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Return compact local and nearest-open outcome state without changing lifecycle authority."""
    workspace = resolved_workspace(workspace)
    database = hybrid_state.database_path(workspace)
    if not database.is_file():
        return {
            "available": False,
            "governed": False,
            "authority": "file-only; no hybrid database",
            "local": None,
            "governing_loop": None,
            "nearest_open_owning_loop": None,
            "writes_performed": False,
        }
    connection = hybrid_state.connect(database, writable=False)
    try:
        rows = [dict(row) for row in connection.execute(
            "SELECT c.id AS cycle_id, c.kind, c.lifecycle_state, c.origin_artifact_id, "
            "a.current_path AS origin_path, v.disposition AS outcome_verdict, "
            "r.state AS reconciliation, r.residual_work_json, r.origin_revision "
            "FROM cycle c JOIN artifact a ON a.id = c.origin_artifact_id "
            "LEFT JOIN reconciliation r ON r.cycle_id = c.id AND r.origin_revision = "
            "(SELECT MAX(r2.origin_revision) FROM reconciliation r2 WHERE r2.cycle_id = c.id) "
            "LEFT JOIN outcome_verdict v ON v.id = r.verdict_id "
            "ORDER BY COALESCE(r.origin_revision, 0) DESC, c.opened_at DESC"
        ).fetchall()]
        by_origin = {item["origin_artifact_id"]: item for item in rows}
        global_query = origin_paths is None
        requested = set(origin_paths or [])
        requested_artifacts = {
            str(row["id"])
            for path in requested
            for row in connection.execute("SELECT id FROM artifact WHERE current_path = ?", (path,)).fetchall()
        }
        local = next((item for item in rows if item["origin_artifact_id"] in requested_artifacts), None)
        governed_roots: list[dict[str, Any]] = []
        if requested_artifacts:
            for item in rows:
                product_ids: list[str] = []
                if item.get("origin_revision") is not None:
                    row = connection.execute(
                        "SELECT product_truth_ref FROM reconciliation WHERE cycle_id = ? "
                        "ORDER BY origin_revision DESC LIMIT 1", (item["cycle_id"],)
                    ).fetchone()
                    if row:
                        try:
                            loaded = json.loads(row["product_truth_ref"])
                            if isinstance(loaded, list):
                                product_ids = [str(value) for value in loaded]
                        except json.JSONDecodeError:
                            product_ids = []
                if requested_artifacts.intersection(product_ids):
                    governed_roots.append(item)
        governed = (global_query and bool(rows)) or local is not None or bool(governed_roots)

        def is_open(item: dict[str, Any]) -> bool:
            return (
                item["lifecycle_state"] not in TERMINAL_STATES
                or item.get("outcome_verdict") == "open"
                or item.get("reconciliation") != "reconciled"
            )

        nearest = None
        if local:
            candidate = local
            visited: set[str] = set()
            while candidate and candidate["origin_artifact_id"] not in visited:
                visited.add(candidate["origin_artifact_id"])
                if is_open(candidate):
                    nearest = candidate
                    break
                parent = connection.execute(
                    "SELECT to_artifact_id FROM relationship WHERE from_artifact_id = ? "
                    "AND relation_type = 'outcome-parent' AND retired_revision IS NULL "
                    "ORDER BY created_revision DESC LIMIT 1", (candidate["origin_artifact_id"],)
                ).fetchone()
                candidate = by_origin.get(str(parent["to_artifact_id"])) if parent else None
        if nearest is None:
            nearest = next((item for item in governed_roots if is_open(item)), None)
        if nearest is None and global_query:
            nearest = next((item for item in rows if is_open(item)), None)

        def compact(item: dict[str, Any] | None) -> dict[str, Any] | None:
            if item is None:
                return None
            residuals: list[Any] = []
            try:
                loaded = json.loads(item.get("residual_work_json") or "[]")
                residuals = loaded if isinstance(loaded, list) else []
            except json.JSONDecodeError:
                pass
            return {
                "cycle_id": item["cycle_id"],
                "kind": item["kind"],
                "origin_path": item["origin_path"],
                "lifecycle": item["lifecycle_state"],
                "outcome_verdict": item.get("outcome_verdict"),
                "reconciliation": item.get("reconciliation"),
                "residual_work_count": len(residuals),
                "revision": item.get("origin_revision"),
            }

        state = hybrid_state.audit(workspace)
        return {
            "available": True,
            "governed": governed,
            "authority": "sqlite outcome state; file lifecycle remains authoritative",
            "revision": state["current_revision"],
            "local": compact(local),
            "governing_loop": compact(
                local or (governed_roots[0] if governed_roots else None) or (nearest if global_query else None)
            ),
            "nearest_open_owning_loop": compact(nearest),
            "writes_performed": False,
        }
    finally:
        connection.close()


def report_cycle(workspace: Path, cycle_id: str, *, as_of: int | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    _uuid(cycle_id, "cycle id")
    connection = hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)
    try:
        current_revision = int(hybrid_state.meta_row(connection)["current_revision"])
        boundary = current_revision if as_of is None else as_of
        if boundary < 0 or boundary > current_revision:
            raise OutcomeLoopError(f"as-of revision must be between 0 and {current_revision}")
        cycle_row = connection.execute(
            "SELECT c.*, a.current_path AS origin_path FROM cycle c JOIN artifact a "
            "ON a.id = c.origin_artifact_id WHERE c.id = ?", (cycle_id,)
        ).fetchone()
        if not cycle_row:
            raise OutcomeLoopError(f"cycle does not exist: {cycle_id}")
        available = bool(connection.execute(
            "SELECT 1 FROM structural_change WHERE table_name = 'cycle' AND row_id = ? "
            "AND operation = 'insert' AND revision <= ?", (cycle_id, boundary),
        ).fetchone())
        cycle = cycle_row if available else None
        requirements = [dict(row) for row in connection.execute(
            "SELECT * FROM requirement WHERE cycle_id = ? AND accepted_revision <= ? ORDER BY id",
            (cycle_id, boundary),
        ).fetchall()]
        changes = [dict(row) for row in connection.execute(
            "SELECT * FROM material_change WHERE cycle_id = ? AND recorded_revision <= ? ORDER BY id",
            (cycle_id, boundary),
        ).fetchall()]
        evidence = [dict(row) for row in connection.execute(
            "SELECT e.*, v.status, v.command_or_test_id, v.source_revision FROM evidence_reference e "
            "LEFT JOIN verification_result v ON v.evidence_id = e.id AND v.source_revision <= ? "
            "WHERE e.cycle_id = ? AND EXISTS (SELECT 1 FROM structural_change s "
            "WHERE s.table_name = 'evidence_reference' AND s.row_id = e.id "
            "AND s.operation = 'insert' AND s.revision <= ?) ORDER BY e.id", (boundary, cycle_id, boundary),
        ).fetchall()]
        reconciliation = connection.execute(
            "SELECT * FROM reconciliation WHERE cycle_id = ? AND origin_revision <= ? "
            "ORDER BY origin_revision DESC LIMIT 1", (cycle_id, boundary),
        ).fetchone()
        verdict = connection.execute(
            "SELECT * FROM outcome_verdict WHERE id = ? AND decided_revision <= ?",
            (reconciliation["verdict_id"], boundary),
        ).fetchone() if reconciliation else None
        overlays = [dict(row) for row in connection.execute(
            "SELECT r.*, o.disposition FROM reconciliation r JOIN outcome_verdict o ON o.id = r.verdict_id "
            "WHERE r.cycle_id = ? AND r.origin_revision > ? ORDER BY r.origin_revision",
            (cycle_id, boundary),
        ).fetchall()]
        relationships = [dict(row) for row in connection.execute(
            "SELECT * FROM relationship WHERE from_artifact_id = ? AND created_revision <= ? "
            "AND (retired_revision IS NULL OR retired_revision > ?) ORDER BY id",
            (cycle_row["origin_artifact_id"], boundary, boundary),
        ).fetchall()]
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "tool-shed-outcome-loop-report",
            "as_of_revision": boundary,
            "current_revision": current_revision,
            "cycle": dict(cycle) if cycle else None,
            "requirements": requirements,
            "changes": changes,
            "evidence": evidence,
            "verdict": dict(verdict) if verdict else None,
            "reconciliation": dict(reconciliation) if reconciliation else None,
            "relationships": relationships,
            "later_overlays": overlays,
            "writes_performed": False,
        }
    finally:
        connection.close()
