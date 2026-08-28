#!/usr/bin/env python3
"""Maintain an independent file/Git bootstrap outcome-closure ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from project_identity import (
    ProjectIdentityError,
    bind_state_token,
    load_project_identity,
    require_path_within,
    require_project_binding,
    resolved_workspace,
)


SCHEMA_VERSION = 1
KIND = "tool-shed-bootstrap-closure"
OPERATION = "bootstrap-closure"
ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")
INITIATIVE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DISPOSITIONS = {"accepted", "rejected", "superseded", "not-applicable"}
EVIDENCE_STATUSES = {"pending", "passed", "failed", "stale", "not-applicable"}
ITEM_STATUSES = {"planned", "active", "complete", "blocked", "not-applicable"}
VERDICTS = {
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
TERMINAL_VERDICTS = VERDICTS - {"open"}
ROOT_KEYS = {
    "schema_version",
    "kind",
    "initiative",
    "project",
    "bindings",
    "authority_contract",
    "requirements",
    "decisions",
    "changes",
    "evidence",
    "migration_items",
    "upgrade_targets",
    "verdicts",
    "release_gate",
    "baseline",
    "state_token",
}


class ClosureError(ValueError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit(workspace: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise ClosureError(result.stderr.strip() or "bootstrap baseline requires a Git commit")
    value = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ClosureError("bootstrap baseline resolved an invalid Git commit")
    return value


def relative_file(workspace: Path, value: object, *, label: str) -> tuple[str, Path]:
    if not isinstance(value, str) or not value or value.startswith("/"):
        raise ClosureError(f"{label} must be a repository-relative path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ClosureError(f"{label} must stay inside the workspace")
    path = require_path_within(workspace, workspace / relative)
    if not path.is_file() or path.is_symlink():
        raise ClosureError(f"{label} must reference a regular file: {value}")
    return relative.as_posix(), path


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ClosureError(f"cannot read bootstrap closure manifest: {error}") from error
    except json.JSONDecodeError as error:
        raise ClosureError(f"bootstrap closure manifest is malformed JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ClosureError("bootstrap closure manifest must be a JSON object")
    return payload


def token_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "state_token"}


def manifest_token(workspace: Path, payload: dict[str, Any]) -> str:
    digest = sha256_bytes(canonical_bytes(token_payload(payload)))
    project_id = load_project_identity(workspace)["project_id"]
    material = ("tool-shed-bootstrap-closure-state-v1", project_id, digest)
    token = hashlib.sha256()
    for value in material:
        token.update(value.encode("utf-8"))
        token.update(b"\0")
    return token.hexdigest()[:16]


def legacy_manifest_token(workspace: Path, payload: dict[str, Any]) -> str:
    """Return the path-bound token emitted before portable checkout support."""
    digest = sha256_bytes(canonical_bytes(token_payload(payload)))
    return bind_state_token(workspace, "bootstrap-closure", digest)


def source_digest(payload: dict[str, Any]) -> str:
    material = {
        "project_id": payload.get("project", {}).get("project_id"),
        "bindings": [
            {"role": item.get("role"), "path": item.get("path"), "sha256": item.get("sha256")}
            for item in payload.get("bindings", [])
        ],
    }
    return sha256_bytes(canonical_bytes(material))


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def require_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ClosureError(f"bootstrap closure {key} must be a list")
    return value


def require_objects(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = require_list(payload, key)
    if not all(isinstance(item, dict) for item in value):
        raise ClosureError(f"bootstrap closure {key} entries must be objects")
    return value  # type: ignore[return-value]


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def check_exact_keys(item: dict[str, Any], allowed: set[str], label: str, findings: list[str]) -> None:
    unknown = sorted(set(item) - allowed)
    if unknown:
        findings.append(f"{label} has unsupported fields: {', '.join(unknown)}")


def duplicate_ids(items: Iterable[dict[str, Any]]) -> list[str]:
    values = [str(item.get("id")) for item in items if isinstance(item.get("id"), str)]
    return sorted({value for value in values if values.count(value) > 1})


def validate_manifest(
    workspace: Path,
    payload: dict[str, Any],
    *,
    gate: str | None = None,
    require_final: bool = False,
) -> list[str]:
    findings: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        findings.append("unsupported bootstrap closure schema_version")
    if payload.get("kind") != KIND:
        findings.append("bootstrap closure kind is invalid")
    unknown_root = sorted(set(payload) - ROOT_KEYS)
    if unknown_root:
        findings.append("bootstrap closure has unsupported fields: " + ", ".join(unknown_root))

    initiative = payload.get("initiative")
    if not isinstance(initiative, dict):
        findings.append("bootstrap closure initiative must be an object")
        initiative = {}
    else:
        check_exact_keys(initiative, {"id", "title", "status"}, "initiative", findings)
    if not isinstance(initiative.get("id"), str) or not INITIATIVE_RE.fullmatch(str(initiative.get("id"))):
        findings.append("initiative id must be lowercase kebab-case")
    if not nonempty(initiative.get("title")):
        findings.append("initiative title is required")
    if initiative.get("status") not in {"active", "complete", "superseded", "parked"}:
        findings.append("initiative status is invalid")

    project = payload.get("project")
    if not isinstance(project, dict):
        findings.append("bootstrap closure project must be an object")
        project = {}
    else:
        check_exact_keys(project, {"project_id"}, "project", findings)
    try:
        current_identity = load_project_identity(workspace)
        if project.get("project_id") != current_identity["project_id"]:
            findings.append("bootstrap closure belongs to another project identity")
    except ProjectIdentityError as error:
        findings.append(str(error))

    try:
        bindings = require_objects(payload, "bindings")
    except ClosureError as error:
        findings.append(str(error))
        bindings = []
    roles: list[str] = []
    for index, binding in enumerate(bindings):
        label = f"binding {index + 1}"
        check_exact_keys(binding, {"role", "path", "sha256"}, label, findings)
        role = binding.get("role")
        if not nonempty(role):
            findings.append(f"{label} needs a role")
        else:
            roles.append(str(role))
        try:
            relative, path = relative_file(workspace, binding.get("path"), label=f"{label} path")
            if binding.get("path") != relative:
                findings.append(f"{label} path is not normalized")
            current = file_sha256(path)
            if binding.get("sha256") != current:
                findings.append(f"{label} is stale: {relative}")
        except (ClosureError, ProjectIdentityError) as error:
            findings.append(str(error))
        if not isinstance(binding.get("sha256"), str) or not SHA256_RE.fullmatch(str(binding.get("sha256"))):
            findings.append(f"{label} needs a SHA-256 digest")
    repeated_roles = sorted({role for role in roles if roles.count(role) > 1})
    if repeated_roles:
        findings.append("bootstrap closure repeats binding roles: " + ", ".join(repeated_roles))
    required_roles = {"idea", "project-map", "program-roadmap", "authority-contract"}
    missing_roles = sorted(required_roles - set(roles))
    if missing_roles:
        findings.append("bootstrap closure lacks required bindings: " + ", ".join(missing_roles))
    if payload.get("authority_contract") not in {
        item.get("path") for item in bindings if item.get("role") == "authority-contract"
    }:
        findings.append("authority_contract must match the authority-contract binding")

    collections: dict[str, list[dict[str, Any]]] = {}
    for key in (
        "requirements",
        "decisions",
        "changes",
        "evidence",
        "migration_items",
        "upgrade_targets",
        "verdicts",
    ):
        try:
            collections[key] = require_objects(payload, key)
        except ClosureError as error:
            findings.append(str(error))
            collections[key] = []
    for key in ("requirements", "decisions", "evidence", "migration_items", "upgrade_targets", "verdicts"):
        if not collections[key]:
            findings.append(f"bootstrap closure {key} must not be empty")
    for key in ("requirements", "decisions", "changes", "evidence", "migration_items", "upgrade_targets"):
        repeats = duplicate_ids(collections[key])
        if repeats:
            findings.append(f"bootstrap closure repeats {key} IDs: " + ", ".join(repeats))

    requirements = collections["requirements"]
    requirement_ids = {str(item.get("id")) for item in requirements if isinstance(item.get("id"), str)}
    evidence = collections["evidence"]
    evidence_ids = {str(item.get("id")) for item in evidence if isinstance(item.get("id"), str)}
    decision_ids = {str(item.get("id")) for item in collections["decisions"] if isinstance(item.get("id"), str)}
    change_ids = {str(item.get("id")) for item in collections["changes"] if isinstance(item.get("id"), str)}

    for item in requirements:
        item_id = item.get("id")
        label = f"requirement {item_id or 'missing'}"
        check_exact_keys(
            item,
            {"id", "summary", "origin", "milestone", "evidence_gate", "disposition", "evidence_ids"},
            label,
            findings,
        )
        if not isinstance(item_id, str) or not ID_RE.fullmatch(item_id):
            findings.append(f"{label} has an invalid stable ID")
        for key in ("summary", "milestone", "evidence_gate"):
            if not nonempty(item.get(key)):
                findings.append(f"{label} needs {key}")
        if item.get("disposition") not in DISPOSITIONS:
            findings.append(f"{label} has an invalid disposition")
        origin = item.get("origin")
        if not isinstance(origin, dict) or set(origin) != {"path", "section"}:
            findings.append(f"{label} needs exact origin path and section")
        else:
            try:
                relative_file(workspace, origin.get("path"), label=f"{label} origin")
            except (ClosureError, ProjectIdentityError) as error:
                findings.append(str(error))
            if not nonempty(origin.get("section")):
                findings.append(f"{label} origin section is required")
        refs = item.get("evidence_ids")
        if not isinstance(refs, list) or not all(isinstance(value, str) for value in refs):
            findings.append(f"{label} evidence_ids must be strings")
            refs = []
        missing = sorted(set(refs) - evidence_ids)
        if missing:
            findings.append(f"{label} references unknown evidence: " + ", ".join(missing))

    for item in collections["decisions"]:
        item_id = item.get("id")
        label = f"decision {item_id or 'missing'}"
        check_exact_keys(item, {"id", "summary", "status", "rationale"}, label, findings)
        if not isinstance(item_id, str) or not ID_RE.fullmatch(item_id):
            findings.append(f"{label} has an invalid stable ID")
        if item.get("status") not in {"settled", "superseded"}:
            findings.append(f"{label} must be settled or superseded")
        for key in ("summary", "rationale"):
            if not nonempty(item.get(key)):
                findings.append(f"{label} needs {key}")

    preceding_change_ids: set[str] = set()
    for item in collections["changes"]:
        item_id = item.get("id")
        label = f"change {item_id or 'missing'}"
        check_exact_keys(
            item,
            {
                "id", "recorded_at", "summary", "rationale", "authorization", "requirement_ids",
                "decision_ids", "supersedes", "evidence_to_rerun", "source_commit",
            },
            label,
            findings,
        )
        if not isinstance(item_id, str) or not ID_RE.fullmatch(item_id):
            findings.append(f"{label} has an invalid stable ID")
        for key in ("recorded_at", "summary", "rationale", "authorization", "source_commit"):
            if not nonempty(item.get(key)):
                findings.append(f"{label} needs {key}")
        change_targets: list[str] = []
        rerun_evidence: list[str] = []
        for key, known in (("requirement_ids", requirement_ids), ("decision_ids", decision_ids), ("evidence_to_rerun", evidence_ids)):
            values = item.get(key)
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                findings.append(f"{label} {key} must be strings")
                values = []
            if key in {"requirement_ids", "decision_ids"}:
                change_targets.extend(values)
            else:
                rerun_evidence.extend(values)
            missing = sorted(set(values) - known)
            if missing:
                findings.append(f"{label} {key} references unknown IDs: " + ", ".join(missing))
        if not change_targets:
            findings.append(f"{label} must identify at least one affected requirement or decision")
        if not rerun_evidence:
            findings.append(f"{label} must identify at least one evidence result to rerun")
        supersedes = item.get("supersedes")
        if not isinstance(supersedes, list) or not all(isinstance(value, str) for value in supersedes):
            findings.append(f"{label} supersedes must be strings")
            supersedes = []
        unknown_superseded = sorted(set(supersedes) - preceding_change_ids)
        if unknown_superseded:
            findings.append(f"{label} supersedes unknown or later changes: " + ", ".join(unknown_superseded))
        if isinstance(item_id, str):
            preceding_change_ids.add(item_id)

    evidence_by_id: dict[str, dict[str, Any]] = {}
    for item in evidence:
        item_id = item.get("id")
        label = f"evidence {item_id or 'missing'}"
        check_exact_keys(
            item,
            {"id", "gate", "status", "references", "covers_change_ids", "verified_at"},
            label,
            findings,
        )
        if not isinstance(item_id, str) or not ID_RE.fullmatch(item_id):
            findings.append(f"{label} has an invalid stable ID")
        else:
            evidence_by_id[item_id] = item
        if not nonempty(item.get("gate")):
            findings.append(f"{label} needs a gate")
        if item.get("status") not in EVIDENCE_STATUSES:
            findings.append(f"{label} has an invalid status")
        references = item.get("references")
        if not isinstance(references, list) or not references:
            findings.append(f"{label} needs at least one reference")
            references = []
        for index, reference in enumerate(references):
            reference_label = f"{label} reference {index + 1}"
            if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
                findings.append(f"{reference_label} needs exact path and sha256 fields")
                continue
            try:
                relative, path = relative_file(workspace, reference.get("path"), label=reference_label)
                if reference.get("sha256") != file_sha256(path):
                    findings.append(f"{reference_label} is stale: {relative}")
            except (ClosureError, ProjectIdentityError) as error:
                findings.append(str(error))
            if not isinstance(reference.get("sha256"), str) or not SHA256_RE.fullmatch(str(reference.get("sha256"))):
                findings.append(f"{reference_label} needs a SHA-256 digest")
        covered = item.get("covers_change_ids")
        if not isinstance(covered, list) or not all(isinstance(value, str) for value in covered):
            findings.append(f"{label} covers_change_ids must be strings")
            covered = []
        missing = sorted(set(covered) - change_ids)
        if missing:
            findings.append(f"{label} covers unknown changes: " + ", ".join(missing))
        if item.get("status") in {"passed", "failed", "not-applicable"} and not nonempty(item.get("verified_at")):
            findings.append(f"{label} terminal status needs verified_at")

    for key in ("migration_items", "upgrade_targets"):
        allowed = {"id", "summary", "milestone", "status"}
        if key == "upgrade_targets":
            allowed |= {"kind", "minimum_updater_protocol"}
        for item in collections[key]:
            item_id = item.get("id")
            label = f"{key[:-1].replace('_', ' ')} {item_id or 'missing'}"
            check_exact_keys(item, allowed, label, findings)
            if not isinstance(item_id, str) or not ID_RE.fullmatch(item_id):
                findings.append(f"{label} has an invalid stable ID")
            for field in ("summary", "milestone"):
                if not nonempty(item.get(field)):
                    findings.append(f"{label} needs {field}")
            if item.get("status") not in ITEM_STATUSES:
                findings.append(f"{label} has an invalid status")
            if key == "upgrade_targets":
                if not nonempty(item.get("kind")):
                    findings.append(f"{label} needs kind")
                protocol = item.get("minimum_updater_protocol")
                if not isinstance(protocol, int) or protocol < 1:
                    findings.append(f"{label} needs a positive minimum_updater_protocol")

    verdicts = collections["verdicts"]
    scopes: list[str] = []
    verdict_by_scope: dict[str, dict[str, Any]] = {}
    for item in verdicts:
        scope = item.get("scope")
        label = f"verdict {scope or 'missing'}"
        check_exact_keys(item, {"scope", "disposition", "summary", "evidence_ids", "authorized_by"}, label, findings)
        if not nonempty(scope):
            findings.append(f"{label} needs scope")
        else:
            scopes.append(str(scope))
            verdict_by_scope[str(scope)] = item
        if item.get("disposition") not in VERDICTS:
            findings.append(f"{label} has an invalid disposition")
        for field in ("summary", "authorized_by"):
            if not nonempty(item.get(field)):
                findings.append(f"{label} needs {field}")
        refs = item.get("evidence_ids")
        if not isinstance(refs, list) or not all(isinstance(value, str) for value in refs):
            findings.append(f"{label} evidence_ids must be strings")
            refs = []
        missing = sorted(set(refs) - evidence_ids)
        if missing:
            findings.append(f"{label} references unknown evidence: " + ", ".join(missing))
    repeated_scopes = sorted({scope for scope in scopes if scopes.count(scope) > 1})
    if repeated_scopes:
        findings.append("bootstrap closure repeats verdict scopes: " + ", ".join(repeated_scopes))
    if "initiative" not in verdict_by_scope:
        findings.append("bootstrap closure needs an initiative verdict")

    for change in collections["changes"]:
        change_id = change.get("id")
        if not isinstance(change_id, str):
            continue
        for evidence_id in change.get("evidence_to_rerun", []):
            record = evidence_by_id.get(str(evidence_id), {})
            status = record.get("status")
            covered = change_id in record.get("covers_change_ids", [])
            evidence_gate = record.get("gate")
            gate_disposition = verdict_by_scope.get(str(evidence_gate), {}).get("disposition")
            pending_future_gate = (
                status == "pending"
                and covered
                and gate_disposition in VERDICTS - TERMINAL_VERDICTS
            )
            if (
                status not in {"passed", "not-applicable"}
                or not covered
            ) and not pending_future_gate:
                findings.append(
                    f"change {change_id} still requires evidence {evidence_id} to be rerun"
                )

    release_gate = payload.get("release_gate")
    if not isinstance(release_gate, dict):
        findings.append("bootstrap closure release_gate must be an object")
        release_gate = {}
    else:
        check_exact_keys(
            release_gate,
            {"mode", "required_scopes", "required_milestones"},
            "release_gate",
            findings,
        )
    if release_gate.get("mode") != "blocking":
        findings.append("bootstrap closure release_gate mode must be blocking")
    required_scopes = release_gate.get("required_scopes")
    if not isinstance(required_scopes, list) or not required_scopes or not all(isinstance(value, str) for value in required_scopes):
        findings.append("release_gate required_scopes must be a non-empty string list")
        required_scopes = []
    missing_scopes = sorted(set(required_scopes) - set(scopes))
    if missing_scopes:
        findings.append("release_gate references unknown verdict scopes: " + ", ".join(missing_scopes))
    known_milestones = {
        str(item.get("milestone"))
        for key in ("requirements", "migration_items", "upgrade_targets")
        for item in collections[key]
        if nonempty(item.get("milestone"))
    }
    required_milestones = release_gate.get("required_milestones")
    if required_milestones is None:
        # Schema-v1 manifests created before staged release gates remain fail-closed.
        required_milestones = sorted(known_milestones)
    elif (
        not isinstance(required_milestones, list)
        or not required_milestones
        or not all(isinstance(value, str) and value for value in required_milestones)
    ):
        findings.append("release_gate required_milestones must be a non-empty string list")
        required_milestones = []
    missing_milestones = sorted(set(required_milestones) - known_milestones)
    if missing_milestones:
        findings.append(
            "release_gate references unknown milestones: " + ", ".join(missing_milestones)
        )

    baseline = payload.get("baseline")
    if not isinstance(baseline, dict):
        findings.append("bootstrap closure baseline must be an object")
        baseline = {}
    else:
        check_exact_keys(baseline, {"created_at", "updated_at", "source_commit", "source_digest"}, "baseline", findings)
    for field in ("created_at", "updated_at"):
        if not nonempty(baseline.get(field)):
            findings.append(f"bootstrap closure baseline needs {field}")
    if not isinstance(baseline.get("source_commit"), str) or not re.fullmatch(r"[0-9a-f]{40}", str(baseline.get("source_commit"))):
        findings.append("bootstrap closure baseline needs a 40-character source_commit")
    if baseline.get("source_digest") != source_digest(payload):
        findings.append("bootstrap closure baseline source_digest is stale")
    expected_token = manifest_token(workspace, payload)
    if payload.get("state_token") != expected_token:
        findings.append("bootstrap closure state_token is stale or invalid")

    if gate:
        selected = verdict_by_scope.get(gate)
        if selected is None:
            findings.append(f"bootstrap closure has no verdict for gate {gate}")
        elif selected.get("disposition") not in TERMINAL_VERDICTS:
            findings.append(f"gate {gate} is not terminal")
        for item in requirements:
            if item.get("evidence_gate") != gate or item.get("disposition") != "accepted":
                continue
            for evidence_id in item.get("evidence_ids", []):
                if evidence_by_id.get(str(evidence_id), {}).get("status") not in {"passed", "not-applicable"}:
                    findings.append(f"gate {gate} requirement {item.get('id')} lacks passing evidence {evidence_id}")

    if require_final:
        for scope in required_scopes:
            if verdict_by_scope.get(str(scope), {}).get("disposition") not in TERMINAL_VERDICTS:
                findings.append(f"release gate scope {scope} is not terminal")
        release_evidence_gates = set(required_scopes)
        require_all_evidence = "initiative" in release_evidence_gates
        for item in requirements:
            if (
                item.get("disposition") != "accepted"
                or (
                    not require_all_evidence
                    and item.get("evidence_gate") not in release_evidence_gates
                )
            ):
                continue
            for evidence_id in item.get("evidence_ids", []):
                if evidence_by_id.get(str(evidence_id), {}).get("status") not in {"passed", "not-applicable"}:
                    findings.append(f"release gate requirement {item.get('id')} lacks passing evidence {evidence_id}")
        for key in ("migration_items", "upgrade_targets"):
            for item in collections[key]:
                if item.get("milestone") not in required_milestones:
                    continue
                if item.get("status") not in {"complete", "not-applicable"}:
                    findings.append(f"release gate {key[:-1]} {item.get('id')} is not complete")
    return sorted(set(findings))


def refresh_bindings(workspace: Path, payload: dict[str, Any]) -> None:
    for binding in require_objects(payload, "bindings"):
        relative, path = relative_file(workspace, binding.get("path"), label="binding path")
        binding["path"] = relative
        binding["sha256"] = file_sha256(path)


def refresh_evidence_references(workspace: Path, payload: dict[str, Any]) -> None:
    for evidence in require_objects(payload, "evidence"):
        references = evidence.get("references")
        if not isinstance(references, list):
            raise ClosureError(f"evidence {evidence.get('id', 'missing')} references must be a list")
        for reference in references:
            if not isinstance(reference, dict):
                raise ClosureError(f"evidence {evidence.get('id', 'missing')} reference must be an object")
            relative, path = relative_file(workspace, reference.get("path"), label="evidence reference")
            reference["path"] = relative
            reference["sha256"] = file_sha256(path)


def finalize(
    workspace: Path,
    payload: dict[str, Any],
    *,
    created_at: str | None = None,
    update_bindings: bool = False,
    update_all_evidence: bool = False,
) -> None:
    stamp = now()
    if update_bindings:
        refresh_bindings(workspace, payload)
    if update_all_evidence:
        refresh_evidence_references(workspace, payload)
    baseline = payload.setdefault("baseline", {})
    if not isinstance(baseline, dict):
        raise ClosureError("bootstrap closure baseline must be an object")
    baseline["created_at"] = created_at or baseline.get("created_at") or stamp
    baseline["updated_at"] = stamp
    baseline["source_commit"] = git_commit(workspace)
    baseline["source_digest"] = source_digest(payload)
    payload["state_token"] = manifest_token(workspace, payload)


def baseline_command(workspace: Path, path: Path, project_binding: str | None) -> dict[str, Any]:
    require_project_binding(workspace, project_binding, operation=OPERATION)
    path = require_path_within(workspace, path)
    payload = load_manifest(path)
    if payload.get("state_token"):
        raise ClosureError("baseline already exists; record a material change instead of silently rebasing it")
    identity = load_project_identity(workspace)
    payload["project"] = {"project_id": identity["project_id"]}
    finalize(workspace, payload, update_bindings=True, update_all_evidence=True)
    findings = validate_manifest(workspace, payload)
    if findings:
        raise ClosureError("invalid bootstrap closure baseline: " + "; ".join(findings))
    atomic_write(path, payload)
    return {"path": path.relative_to(workspace).as_posix(), "state_token": payload["state_token"], "valid": True}


def require_current(workspace: Path, payload: dict[str, Any], expected: str | None) -> None:
    current = manifest_token(workspace, payload)
    recorded = payload.get("state_token")
    accepted = {current, legacy_manifest_token(workspace, payload)}
    if recorded not in accepted:
        raise ClosureError("bootstrap closure manifest has a stale or invalid state_token")
    if expected != recorded:
        raise ClosureError(
            f"stale bootstrap closure state: expected {expected or 'missing'}, current {recorded}"
        )


def record_change_command(workspace: Path, path: Path, args: argparse.Namespace) -> dict[str, Any]:
    require_project_binding(workspace, args.project_binding, operation=OPERATION)
    path = require_path_within(workspace, path)
    payload = load_manifest(path)
    require_current(workspace, payload, args.expect)
    changes = require_objects(payload, "changes")
    if any(item.get("id") == args.change_id for item in changes):
        raise ClosureError(f"change ID already exists: {args.change_id}")
    if not args.requirement and not args.decision:
        raise ClosureError("record-change requires at least one affected requirement or decision")
    if not args.rerun_evidence:
        raise ClosureError("record-change requires at least one evidence result to rerun")
    known_requirements = {item.get("id") for item in require_objects(payload, "requirements")}
    known_decisions = {item.get("id") for item in require_objects(payload, "decisions")}
    known_evidence = {item.get("id") for item in require_objects(payload, "evidence")}
    for values, known, label in (
        (args.requirement, known_requirements, "requirement"),
        (args.decision, known_decisions, "decision"),
        (args.rerun_evidence, known_evidence, "evidence"),
    ):
        missing = sorted(set(values) - known)
        if missing:
            raise ClosureError(f"record-change references unknown {label} IDs: " + ", ".join(missing))
    known_changes = {item.get("id") for item in changes}
    missing_superseded = sorted(set(args.supersedes) - known_changes)
    if missing_superseded:
        raise ClosureError("record-change supersedes unknown changes: " + ", ".join(missing_superseded))
    release_gate = payload.get("release_gate")
    if not isinstance(release_gate, dict):
        raise ClosureError("bootstrap closure release_gate must be an object")
    if bool(args.release_scope) != bool(args.release_milestone):
        raise ClosureError(
            "record-change release-stage updates require both --release-scope and --release-milestone"
        )
    if args.release_scope:
        known_scopes = {item.get("scope") for item in require_objects(payload, "verdicts")}
        missing = sorted(set(args.release_scope) - known_scopes)
        if missing:
            raise ClosureError("record-change references unknown release scopes: " + ", ".join(missing))
        known_milestones = {
            item.get("milestone")
            for key in ("requirements", "migration_items", "upgrade_targets")
            for item in require_objects(payload, key)
        }
        missing = sorted(set(args.release_milestone) - known_milestones)
        if missing:
            raise ClosureError(
                "record-change references unknown release milestones: " + ", ".join(missing)
            )
        release_gate["required_scopes"] = list(dict.fromkeys(args.release_scope))
        release_gate["required_milestones"] = list(dict.fromkeys(args.release_milestone))
    for key, selected, label in (
        ("migration_items", args.complete_migration, "migration"),
        ("upgrade_targets", args.complete_upgrade_target, "upgrade target"),
    ):
        records = require_objects(payload, key)
        by_id = {item.get("id"): item for item in records}
        missing = sorted(set(selected) - set(by_id))
        if missing:
            raise ClosureError(
                f"record-change references unknown {label} IDs: " + ", ".join(missing)
            )
        for item_id in selected:
            by_id[item_id]["status"] = "complete"
    changes.append(
        {
            "id": args.change_id,
            "recorded_at": now(),
            "summary": args.summary,
            "rationale": args.rationale,
            "authorization": args.authorization,
            "requirement_ids": sorted(set(args.requirement)),
            "decision_ids": sorted(set(args.decision)),
            "supersedes": sorted(set(args.supersedes)),
            "evidence_to_rerun": sorted(set(args.rerun_evidence)),
            "source_commit": git_commit(workspace),
        }
    )
    for evidence in require_objects(payload, "evidence"):
        if evidence.get("id") in args.rerun_evidence:
            evidence["status"] = "stale"
            evidence["verified_at"] = None
    created_at = payload.get("baseline", {}).get("created_at")
    finalize(
        workspace,
        payload,
        created_at=created_at if isinstance(created_at, str) else None,
        update_bindings=True,
    )
    atomic_write(path, payload)
    return {"change_id": args.change_id, "path": path.relative_to(workspace).as_posix(), "state_token": payload["state_token"]}


def record_evidence_command(workspace: Path, path: Path, args: argparse.Namespace) -> dict[str, Any]:
    require_project_binding(workspace, args.project_binding, operation=OPERATION)
    path = require_path_within(workspace, path)
    payload = load_manifest(path)
    require_current(workspace, payload, args.expect)
    records = require_objects(payload, "evidence")
    record = next((item for item in records if item.get("id") == args.evidence_id), None)
    if record is None:
        raise ClosureError(f"unknown evidence ID: {args.evidence_id}")
    known_changes = {item.get("id") for item in require_objects(payload, "changes")}
    missing = sorted(set(args.covers_change) - known_changes)
    if missing:
        raise ClosureError("record-evidence references unknown changes: " + ", ".join(missing))
    references: list[dict[str, str]] = []
    for value in args.reference:
        relative, reference_path = relative_file(workspace, value, label="evidence reference")
        references.append({"path": relative, "sha256": file_sha256(reference_path)})
    record.update(
        {
            "status": args.status,
            "references": references,
            "covers_change_ids": sorted(set(args.covers_change)),
            "verified_at": now() if args.status in {"passed", "failed", "not-applicable"} else None,
        }
    )
    created_at = payload.get("baseline", {}).get("created_at")
    finalize(workspace, payload, created_at=created_at if isinstance(created_at, str) else None)
    atomic_write(path, payload)
    return {"evidence_id": args.evidence_id, "path": path.relative_to(workspace).as_posix(), "state_token": payload["state_token"]}


def record_verdict_command(workspace: Path, path: Path, args: argparse.Namespace) -> dict[str, Any]:
    require_project_binding(workspace, args.project_binding, operation=OPERATION)
    path = require_path_within(workspace, path)
    payload = load_manifest(path)
    require_current(workspace, payload, args.expect)
    known_evidence = {item.get("id") for item in require_objects(payload, "evidence")}
    missing = sorted(set(args.evidence) - known_evidence)
    if missing:
        raise ClosureError("record-verdict references unknown evidence: " + ", ".join(missing))
    verdicts = require_objects(payload, "verdicts")
    verdict = next((item for item in verdicts if item.get("scope") == args.scope), None)
    replacement = {
        "scope": args.scope,
        "disposition": args.disposition,
        "summary": args.summary,
        "evidence_ids": sorted(set(args.evidence)),
        "authorized_by": args.authorization,
    }
    if verdict is None:
        verdicts.append(replacement)
    else:
        verdict.clear()
        verdict.update(replacement)
    created_at = payload.get("baseline", {}).get("created_at")
    finalize(workspace, payload, created_at=created_at if isinstance(created_at, str) else None)
    findings = validate_manifest(workspace, payload)
    if findings:
        raise ClosureError("verdict update would leave an invalid manifest: " + "; ".join(findings))
    atomic_write(path, payload)
    return {"scope": args.scope, "path": path.relative_to(workspace).as_posix(), "state_token": payload["state_token"]}


def result_payload(workspace: Path, path: Path, payload: dict[str, Any], *, gate: str | None, require_final: bool) -> dict[str, Any]:
    findings = validate_manifest(workspace, payload, gate=gate, require_final=require_final)
    evidence_counts = {
        status: sum(item.get("status") == status for item in payload.get("evidence", []))
        for status in sorted(EVIDENCE_STATUSES)
    }
    verdicts = {str(item.get("scope")): item.get("disposition") for item in payload.get("verdicts", [])}
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-bootstrap-closure-result",
        "path": path.relative_to(workspace).as_posix(),
        "initiative_id": payload.get("initiative", {}).get("id"),
        "state_token": payload.get("state_token"),
        "gate": gate,
        "require_final": require_final,
        "valid": not findings,
        "findings": findings,
        "requirements": len(payload.get("requirements", [])),
        "changes": len(payload.get("changes", [])),
        "evidence": evidence_counts,
        "verdicts": verdicts,
        "release_ready": not validate_manifest(workspace, payload, require_final=True),
        "writes_performed": False,
    }


def render_report(result: dict[str, Any], payload: dict[str, Any]) -> str:
    initiative = payload.get("initiative", {})
    lines = [
        f"# Bootstrap Closure Report: {initiative.get('title', 'Unknown')}",
        "",
        f"- Initiative ID: `{initiative.get('id', 'unknown')}`",
        f"- Manifest state: `{'VALID' if result['valid'] else 'INVALID'}`",
        f"- Release ready: `{'yes' if result['release_ready'] else 'no'}`",
        f"- State token: `{result.get('state_token') or 'none'}`",
        f"- Requirements: {result['requirements']}",
        f"- Material changes: {result['changes']}",
        "",
        "## Verdicts",
        "",
    ]
    for scope, disposition in sorted(result["verdicts"].items()):
        lines.append(f"- `{scope}`: `{disposition}`")
    lines.extend(["", "## Evidence", ""])
    for status, count in result["evidence"].items():
        lines.append(f"- `{status}`: {count}")
    lines.extend(["", "## Findings", ""])
    if result["findings"]:
        lines.extend(f"- {finding}" for finding in result["findings"])
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    baseline = subparsers.add_parser("baseline", help="finalize a new authored closure manifest")
    baseline.add_argument("--manifest", required=True)
    baseline.add_argument("--project-binding", required=True)

    change = subparsers.add_parser("record-change", help="append one guarded material-change record")
    change.add_argument("--manifest", required=True)
    change.add_argument("--expect", required=True)
    change.add_argument("--project-binding", required=True)
    change.add_argument("--change-id", required=True, type=lambda value: stable_id(value, "change"))
    change.add_argument("--summary", required=True)
    change.add_argument("--rationale", required=True)
    change.add_argument("--authorization", required=True)
    change.add_argument("--requirement", action="append", default=[])
    change.add_argument("--decision", action="append", default=[])
    change.add_argument("--supersedes", action="append", default=[])
    change.add_argument("--rerun-evidence", action="append", default=[])
    change.add_argument("--release-scope", action="append", default=[])
    change.add_argument("--release-milestone", action="append", default=[])
    change.add_argument("--complete-migration", action="append", default=[])
    change.add_argument("--complete-upgrade-target", action="append", default=[])

    evidence = subparsers.add_parser("record-evidence", help="record or replace one evidence result")
    evidence.add_argument("--manifest", required=True)
    evidence.add_argument("--expect", required=True)
    evidence.add_argument("--project-binding", required=True)
    evidence.add_argument("--evidence-id", required=True, type=lambda value: stable_id(value, "evidence"))
    evidence.add_argument("--status", required=True, choices=sorted(EVIDENCE_STATUSES - {"stale"}))
    evidence.add_argument("--reference", action="append", required=True)
    evidence.add_argument("--covers-change", action="append", default=[])

    verdict = subparsers.add_parser("record-verdict", help="record an exact guarded gate or initiative verdict")
    verdict.add_argument("--manifest", required=True)
    verdict.add_argument("--expect", required=True)
    verdict.add_argument("--project-binding", required=True)
    verdict.add_argument("--scope", required=True)
    verdict.add_argument("--disposition", required=True, choices=sorted(VERDICTS))
    verdict.add_argument("--summary", required=True)
    verdict.add_argument("--authorization", required=True)
    verdict.add_argument("--evidence", action="append", default=[])

    verify = subparsers.add_parser("verify", help="validate a manifest without writing")
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--gate")
    verify.add_argument("--require-final", action="store_true")

    report = subparsers.add_parser("report", help="render a concise read-only closure report")
    report.add_argument("--manifest", required=True)
    report.add_argument("--gate")
    report.add_argument("--require-final", action="store_true")
    return parser


def stable_id(value: str, label: str) -> str:
    if not ID_RE.fullmatch(value):
        raise argparse.ArgumentTypeError(f"{label} ID must use stable uppercase kebab-case")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        workspace = resolved_workspace(Path(args.workspace))
        manifest_path = require_path_within(workspace, Path(args.manifest).expanduser() if Path(args.manifest).is_absolute() else workspace / args.manifest)
        if args.command == "baseline":
            result = baseline_command(workspace, manifest_path, args.project_binding)
        elif args.command == "record-change":
            result = record_change_command(workspace, manifest_path, args)
        elif args.command == "record-evidence":
            result = record_evidence_command(workspace, manifest_path, args)
        elif args.command == "record-verdict":
            result = record_verdict_command(workspace, manifest_path, args)
        else:
            payload = load_manifest(manifest_path)
            result = result_payload(
                workspace,
                manifest_path,
                payload,
                gate=args.gate,
                require_final=args.require_final,
            )
            if args.command == "report" and not args.json:
                print(render_report(result, payload), end="")
                return 0 if result["valid"] else 1
        print(json.dumps(result, indent=2, sort_keys=True))
        if args.command == "verify" and not result.get("valid", False):
            return 1
        return 0
    except (ClosureError, ProjectIdentityError, OSError, json.JSONDecodeError) as error:
        print(f"Bootstrap closure operation failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
