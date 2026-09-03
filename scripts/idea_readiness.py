#!/usr/bin/env python3
"""Prepare, persist, inspect, and transfer versioned Idea Brief readiness reviews."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import contextlib
import copy
import hashlib
import json
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any, Sequence

import hybrid_state
from project_identity import ProjectIdentityError, require_path_within, resolved_workspace


SCHEMA_VERSION = 1
CONTRACT_VERSION = 1
INPUT_KIND = "tool-shed-idea-readiness-input"
MANIFEST_KIND = "tool-shed-idea-readiness-manifest"
REVIEW_KIND = "tool-shed-idea-readiness-review"
STATUS_KIND = "tool-shed-idea-readiness-status"
TRANSFER_KIND = "tool-shed-idea-readiness-transfer"
EVENT_KIND = "idea-readiness-review-v1"
EVENT_ENTITY_TYPE = "idea-brief"
SUPPORTED_HYBRID_SCHEMAS = {2, 3}
VERDICTS = {"READY", "READY-WITH-PRM-GATES", "NOT-READY"}
READY_VERDICTS = {"READY", "READY-WITH-PRM-GATES"}
LIST_FIELDS = (
    "adaptive_modules",
    "promotion_blockers",
    "prm_gates",
    "deferred_items",
    "contradictions",
    "complexity_findings",
    "recommended_updates",
)
INPUT_FIELDS = {
    "schema_version",
    "kind",
    "review_contract_version",
    "verdict",
    "reviewer",
    *LIST_FIELDS,
    "resumes_result_digest",
}


class IdeaReadinessError(RuntimeError):
    def __init__(self, message: str, *, code: str = "invalid-review", unavailable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.unavailable = unavailable


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def token(value: dict[str, Any]) -> str:
    material = copy.deepcopy(value)
    material.pop("manifest_token", None)
    return digest(material)[:16]


def _database(workspace: Path, database: Path | None) -> Path:
    candidate = database or hybrid_state.database_path(workspace)
    return require_path_within(workspace, candidate if candidate.is_absolute() else workspace / candidate)


def _connection(workspace: Path, database: Path | None = None) -> sqlite3.Connection:
    path = _database(workspace, database)
    if not path.is_file():
        raise IdeaReadinessError("Hybrid database is not available", code="database-unavailable", unavailable=True)
    connection = hybrid_state.connect(path, writable=False)
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version not in SUPPORTED_HYBRID_SCHEMAS:
        connection.close()
        raise IdeaReadinessError(
            f"Idea readiness requires Hybrid schema 2 or 3; found {version}",
            code="unsupported-hybrid-schema",
            unavailable=True,
        )
    return connection


def _document(
    connection: sqlite3.Connection,
    identity: str,
    *,
    require_idea: bool = True,
) -> dict[str, Any]:
    row = connection.execute(
        "SELECT a.id AS artifact_id, a.type, d.visible_id, d.current_revision, d.body_sha256, "
        "d.metadata_json, d.title, d.lifecycle_state FROM artifact a JOIN document d ON d.id=a.id "
        "WHERE a.id=? OR d.visible_id=?",
        (identity, identity),
    ).fetchone()
    if row is None:
        alias = connection.execute(
            "SELECT d.id FROM document_path_alias p JOIN document d ON d.id=p.document_id "
            "WHERE p.path=? AND p.retired_revision IS NULL",
            (identity,),
        ).fetchone()
        if alias is not None:
            return _document(connection, str(alias["id"]), require_idea=require_idea)
        raise IdeaReadinessError(f"Idea Brief does not exist: {identity}", code="idea-not-found")
    document = dict(row)
    if require_idea and document["type"] != "idea-brief":
        raise IdeaReadinessError(f"readiness review requires an Idea Brief, found {document['type']}", code="wrong-document-type")
    document["metadata"] = json.loads(document.pop("metadata_json"))
    return document


def _review_events(connection: sqlite3.Connection, artifact_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT id, revision, payload_json, recorded_at FROM event "
        "WHERE kind=? AND entity_type=? AND entity_id=? ORDER BY revision DESC, id DESC",
        (EVENT_KIND, EVENT_ENTITY_TYPE, artifact_id),
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        payload["event_id"] = str(row["id"])
        payload["stored_revision"] = int(row["revision"])
        payload["stored_at"] = str(row["recorded_at"])
        result.append(payload)
    return result


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IdeaReadinessError(f"{label} must be a non-empty string")
    return value.strip()


def _object_list(values: object, label: str, required: tuple[str, ...]) -> list[dict[str, str]]:
    if not isinstance(values, list):
        raise IdeaReadinessError(f"{label} must be a list")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict) or set(value) != set(required):
            raise IdeaReadinessError(f"{label} item {index} must contain exactly: {', '.join(required)}")
        item = {field: _string(value[field], f"{label} item {index} {field}") for field in required}
        if item["id"] in seen:
            raise IdeaReadinessError(f"duplicate {label} id: {item['id']}")
        seen.add(item["id"])
        result.append(item)
    return result


def _string_list(values: object, label: str) -> list[str]:
    if not isinstance(values, list):
        raise IdeaReadinessError(f"{label} must be a list")
    result = [_string(value, f"{label} item {index}") for index, value in enumerate(values, start=1)]
    if len(result) != len(set(result)):
        raise IdeaReadinessError(f"{label} contains duplicates")
    return result


def validate_input(payload: dict[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(payload) - INPUT_FIELDS)
    if unknown:
        raise IdeaReadinessError("unknown review input fields: " + ", ".join(unknown))
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("kind") != INPUT_KIND:
        raise IdeaReadinessError("unsupported review input envelope", code="unsupported-input")
    if payload.get("review_contract_version") != CONTRACT_VERSION:
        raise IdeaReadinessError(
            f"unknown readiness contract version: {payload.get('review_contract_version')}",
            code="unknown-contract-version",
        )
    verdict = str(payload.get("verdict") or "")
    if verdict not in VERDICTS:
        raise IdeaReadinessError(f"unknown readiness verdict: {verdict}", code="unknown-verdict")
    reviewer = _string(payload.get("reviewer"), "reviewer")
    modules = _object_list(payload.get("adaptive_modules", []), "adaptive_modules", ("id", "reason"))
    blockers = _object_list(
        payload.get("promotion_blockers", []),
        "promotion_blockers",
        ("id", "summary", "decision_owner", "why_prm_cannot_infer", "recommendation"),
    )
    gates = _object_list(payload.get("prm_gates", []), "prm_gates", ("id", "title", "requirement"))
    deferred = _object_list(payload.get("deferred_items", []), "deferred_items", ("id", "summary"))
    contradictions = _string_list(payload.get("contradictions", []), "contradictions")
    complexity = _string_list(payload.get("complexity_findings", []), "complexity_findings")
    updates = _string_list(payload.get("recommended_updates", []), "recommended_updates")
    if verdict in READY_VERDICTS and blockers:
        raise IdeaReadinessError(f"{verdict} cannot retain promotion blockers")
    if verdict == "READY" and gates:
        raise IdeaReadinessError("READY cannot retain PRM gates")
    if verdict == "READY-WITH-PRM-GATES" and not gates:
        raise IdeaReadinessError("READY-WITH-PRM-GATES requires at least one PRM gate")
    if verdict == "NOT-READY" and not blockers:
        raise IdeaReadinessError("NOT-READY requires at least one promotion blocker")
    resumes = payload.get("resumes_result_digest")
    if resumes is not None and (not isinstance(resumes, str) or len(resumes) != 64):
        raise IdeaReadinessError("resumes_result_digest must be a lowercase SHA-256 or null")
    return {
        "review_contract_version": CONTRACT_VERSION,
        "verdict": verdict,
        "reviewer": reviewer,
        "adaptive_modules": modules,
        "promotion_blockers": blockers,
        "prm_gates": gates,
        "deferred_items": deferred,
        "contradictions": contradictions,
        "complexity_findings": complexity,
        "recommended_updates": updates,
        "resumes_result_digest": resumes,
    }


def _load_json(workspace: Path, supplied: Path, label: str) -> dict[str, Any]:
    path = require_path_within(workspace, supplied if supplied.is_absolute() else workspace / supplied)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise IdeaReadinessError(f"cannot load {label}: {error}", code="invalid-json") from error
    if not isinstance(value, dict):
        raise IdeaReadinessError(f"{label} must be a JSON object")
    return value


def prepare(workspace: Path, identity: str, source: Path, *, database: Path | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    review_input = validate_input(_load_json(workspace, source, "readiness input"))
    import document_store

    audit = document_store.audit(workspace, database)
    if audit["classification"] not in {"CLEAN", "VALID_DIRTY"}:
        raise IdeaReadinessError(
            f"readiness review is unavailable from {audit['classification']}",
            code="database-not-writable",
            unavailable=True,
        )
    with contextlib.closing(_connection(workspace, database)) as connection:
        idea = _document(connection, identity)
        history = _review_events(connection, idea["artifact_id"])
    resumes = review_input.get("resumes_result_digest")
    if resumes and resumes not in {item.get("result_digest") for item in history}:
        raise IdeaReadinessError("resumes_result_digest does not identify prior review history", code="unknown-resume-review")
    result = {
        "schema_version": SCHEMA_VERSION,
        "kind": REVIEW_KIND,
        "review_contract_version": CONTRACT_VERSION,
        "idea": {
            "artifact_id": idea["artifact_id"],
            "visible_id": idea["visible_id"],
            "document_revision": int(idea["current_revision"]),
            "body_sha256": idea["body_sha256"],
        },
        "reviewed_at": hybrid_state.now(),
        **review_input,
    }
    result["result_digest"] = digest(result)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": MANIFEST_KIND,
        "expected_database_revision": audit["current_revision"],
        "expected_domain_digest": audit["domain_digest"],
        "review": result,
    }
    manifest["manifest_token"] = token(manifest)
    return manifest


def validate_manifest(
    workspace: Path,
    manifest: dict[str, Any],
    *,
    check_state: bool = True,
    database: Path | None = None,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    errors: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("kind") != MANIFEST_KIND:
        errors.append("unsupported readiness manifest")
    if manifest.get("manifest_token") != token(manifest):
        errors.append("readiness manifest token is invalid")
    review = manifest.get("review")
    if not isinstance(review, dict):
        errors.append("readiness manifest lacks review")
    else:
        try:
            normalized = validate_input(
                {
                    "schema_version": SCHEMA_VERSION,
                    "kind": INPUT_KIND,
                    **{field: review.get(field) for field in INPUT_FIELDS if field not in {"schema_version", "kind"}},
                }
            )
            if any(review.get(key) != value for key, value in normalized.items()):
                errors.append("readiness review payload is not normalized")
            material = copy.deepcopy(review)
            supplied_digest = material.pop("result_digest", None)
            if supplied_digest != digest(material):
                errors.append("readiness result digest is invalid")
            idea = review.get("idea") or {}
            if set(idea) != {"artifact_id", "visible_id", "document_revision", "body_sha256"}:
                errors.append("readiness review idea binding is invalid")
        except IdeaReadinessError as error:
            errors.append(str(error))
    if check_state and not errors:
        import document_store

        audit = document_store.audit(workspace, database)
        if audit["classification"] not in {"CLEAN", "VALID_DIRTY"}:
            errors.append(f"readiness database state is {audit['classification']}")
        if manifest.get("expected_database_revision") != audit["current_revision"]:
            errors.append("readiness manifest database revision is stale")
        if manifest.get("expected_domain_digest") != audit["domain_digest"]:
            errors.append("readiness manifest domain digest is stale")
        if not errors:
            with contextlib.closing(_connection(workspace, database)) as connection:
                current = _document(connection, review["idea"]["artifact_id"])
            if current["visible_id"] != review["idea"]["visible_id"]:
                errors.append("readiness Idea visible ID changed")
            if int(current["current_revision"]) != review["idea"]["document_revision"]:
                errors.append("readiness Idea document revision changed during review")
            if current["body_sha256"] != review["idea"]["body_sha256"]:
                errors.append("readiness Idea body hash changed during review")
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-idea-readiness-validation",
        "valid": not errors,
        "errors": errors,
        "manifest_token": manifest.get("manifest_token"),
        "writes_performed": False,
    }


def apply(
    workspace: Path,
    manifest: dict[str, Any],
    *,
    expected_token: str,
    project_binding: str,
    database: Path | None = None,
) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    validation = validate_manifest(workspace, manifest, database=database)
    if not validation["valid"]:
        raise IdeaReadinessError("; ".join(validation["errors"]), code="stale-or-invalid-review")
    if manifest["manifest_token"] != expected_token:
        raise IdeaReadinessError("approved readiness token does not match", code="token-mismatch")
    review = manifest["review"]
    import document_store

    def write(connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        meta = hybrid_state.meta_row(connection)
        if int(meta["current_revision"]) != manifest["expected_database_revision"]:
            raise IdeaReadinessError("database changed before readiness write", code="stale-database")
        if document_store.domain_digest(connection) != manifest["expected_domain_digest"]:
            raise IdeaReadinessError("database digest changed before readiness write", code="stale-database")
        idea = _document(connection, review["idea"]["artifact_id"])
        if int(idea["current_revision"]) != review["idea"]["document_revision"] or idea["body_sha256"] != review["idea"]["body_sha256"]:
            raise IdeaReadinessError("Idea changed during readiness review", code="stale-idea")
        operation = connection.execute("SELECT operation_id FROM active_operation WHERE id=1").fetchone()
        if operation is None:
            raise IdeaReadinessError("managed readiness operation is unavailable", code="missing-operation", unavailable=True)
        event_id = str(uuid.uuid4())
        stamp = hybrid_state.now()
        connection.execute(
            "INSERT INTO event VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event_id,
                revision,
                operation["operation_id"],
                EVENT_KIND,
                EVENT_ENTITY_TYPE,
                idea["artifact_id"],
                canonical_bytes(review).decode("utf-8"),
                stamp,
            ),
        )
        return {
            "event_id": event_id,
            "idea": idea["visible_id"],
            "reviewed_document_revision": review["idea"]["document_revision"],
            "result_digest": review["result_digest"],
            "verdict": review["verdict"],
            "promotion_allowed": review["verdict"] in READY_VERDICTS,
        }

    return document_store.managed_write(
        workspace,
        project_binding=project_binding,
        command="idea-readiness-review-apply",
        actor=review["reviewer"],
        callback=write,
        database=database,
    )


def status(workspace: Path, identity: str, *, database: Path | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    with contextlib.closing(_connection(workspace, database)) as connection:
        idea = _document(connection, identity)
        events = _review_events(connection, idea["artifact_id"])
    base = {
        "schema_version": SCHEMA_VERSION,
        "kind": STATUS_KIND,
        "idea": {
            "artifact_id": idea["artifact_id"],
            "visible_id": idea["visible_id"],
            "document_revision": int(idea["current_revision"]),
            "body_sha256": idea["body_sha256"],
        },
        "review_contract_version": CONTRACT_VERSION,
        "writes_performed": False,
    }
    if not events:
        return {**base, "state": "ABSENT", "verdict": None, "promotion_allowed": False, "review_required": True, "latest_review": None}
    latest = events[0]
    binding = latest.get("idea") or {}
    stale_reasons: list[str] = []
    if latest.get("review_contract_version") != CONTRACT_VERSION:
        stale_reasons.append("review-contract-version")
    if binding.get("artifact_id") != idea["artifact_id"]:
        stale_reasons.append("idea-artifact-id")
    if binding.get("document_revision") != int(idea["current_revision"]):
        stale_reasons.append("idea-document-revision")
    if binding.get("body_sha256") != idea["body_sha256"]:
        stale_reasons.append("idea-body-hash")
    verdict = latest.get("verdict")
    if stale_reasons:
        state = "STALE"
    elif verdict == "NOT-READY":
        state = "CURRENT-NOT-READY"
    else:
        state = "CURRENT-READY"
    allowed = state == "CURRENT-READY" and verdict in READY_VERDICTS
    return {
        **base,
        "state": state,
        "verdict": verdict,
        "promotion_allowed": allowed,
        "review_required": not allowed,
        "stale_reasons": stale_reasons,
        "latest_review": latest,
        "review_count": len(events),
    }


def transfer_check(workspace: Path, idea_identity: str, target_identity: str, *, database: Path | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    current = status(workspace, idea_identity, database=database)
    errors: list[str] = []
    if not current["promotion_allowed"]:
        errors.append("Idea lacks a current ready review")
    with contextlib.closing(_connection(workspace, database)) as connection:
        target = _document(connection, target_identity, require_idea=False)
    if target["type"] not in {"project-map", "program-roadmap"}:
        errors.append("transfer target must be a project map or Program Roadmap")
    review = current.get("latest_review") or {}
    idea = current["idea"]
    metadata = target["metadata"]
    expected_gates = sorted(item["id"] for item in review.get("prm_gates", []))
    observed_gates = metadata.get("readiness_gate_ids")
    checks = {
        "result_digest": metadata.get("readiness_review_digest") == review.get("result_digest"),
        "idea_artifact_id": metadata.get("reviewed_idea_artifact_id") == idea["artifact_id"],
        "idea_document_revision": metadata.get("reviewed_idea_document_revision") == idea["document_revision"],
        "idea_body_sha256": metadata.get("reviewed_idea_body_sha256") == idea["body_sha256"],
        "gate_ids": isinstance(observed_gates, list) and sorted(observed_gates) == expected_gates,
    }
    errors.extend(name.replace("_", " ") + " mismatch" for name, passed in checks.items() if not passed)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": TRANSFER_KIND,
        "idea": idea["visible_id"],
        "target": target["visible_id"],
        "review_result_digest": review.get("result_digest"),
        "expected_gate_ids": expected_gates,
        "observed_gate_ids": observed_gates,
        "checks": checks,
        "valid": not errors,
        "errors": errors,
        "transfer_count": len(expected_gates) if not errors else 0,
        "writes_performed": False,
    }


def render_projection(connection: sqlite3.Connection, document: sqlite3.Row | dict[str, Any]) -> str:
    row = dict(document)
    if row.get("type") != "idea-brief":
        return ""
    events = _review_events(connection, str(row["id"]))
    lines = ["## Readiness Review", ""]
    if not events:
        return "\n".join(lines + ["State: ABSENT", f"Contract Version: {CONTRACT_VERSION}", "Semantic Review Performed: no"])
    latest = events[0]
    binding = latest.get("idea") or {}
    stale = (
        latest.get("review_contract_version") != CONTRACT_VERSION
        or binding.get("document_revision") != int(row["current_revision"])
        or binding.get("body_sha256") != row["body_sha256"]
    )
    state = "STALE" if stale else ("CURRENT-NOT-READY" if latest.get("verdict") == "NOT-READY" else "CURRENT-READY")
    gates = ", ".join(item["id"] for item in latest.get("prm_gates", [])) or "none"
    return "\n".join(
        lines
        + [
            f"State: {state}",
            f"Verdict: {latest.get('verdict')}",
            f"Contract Version: {latest.get('review_contract_version')}",
            f"Reviewed Document Revision: {binding.get('document_revision')}",
            f"Result Digest: {latest.get('result_digest')}",
            f"PRM Gates: {gates}",
            "Semantic Review Performed: no (projection only)",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--database")
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    status_parser = commands.add_parser("status")
    status_parser.add_argument("idea")
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("idea")
    prepare_parser.add_argument("--input", required=True)
    validate_parser = commands.add_parser("validate")
    validate_parser.add_argument("--manifest", required=True)
    apply_parser = commands.add_parser("apply")
    apply_parser.add_argument("--manifest", required=True)
    apply_parser.add_argument("--expect", required=True)
    apply_parser.add_argument("--project-binding", required=True)
    transfer_parser = commands.add_parser("transfer-check")
    transfer_parser.add_argument("--idea", required=True)
    transfer_parser.add_argument("--target", required=True)
    return parser


def _print(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        workspace = resolved_workspace(Path(args.workspace))
        database = Path(args.database) if args.database else None
        if database is not None and not database.is_absolute():
            database = workspace / database
        if args.command == "status":
            result = status(workspace, args.idea, database=database)
        elif args.command == "prepare":
            result = prepare(workspace, args.idea, Path(args.input), database=database)
        elif args.command == "validate":
            manifest = _load_json(workspace, Path(args.manifest), "readiness manifest")
            result = validate_manifest(workspace, manifest, database=database)
        elif args.command == "apply":
            manifest = _load_json(workspace, Path(args.manifest), "readiness manifest")
            result = apply(
                workspace,
                manifest,
                expected_token=args.expect,
                project_binding=args.project_binding,
                database=database,
            )
        else:
            result = transfer_check(workspace, args.idea, args.target, database=database)
        _print(result)
        if args.command in {"validate", "transfer-check"} and not result["valid"]:
            return 1
        return 0
    except IdeaReadinessError as error:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "kind": "tool-shed-idea-readiness-error",
            "status": "REVIEW-UNAVAILABLE" if error.unavailable else "REVIEW-ERROR",
            "code": error.code,
            "message": str(error),
            "promotion_allowed": False,
            "writes_performed": False,
        }
        if args.json:
            _print(payload)
        else:
            print(f"{payload['status']}: {error}", file=sys.stderr)
        return 2
    except (ProjectIdentityError, hybrid_state.HybridStateError, sqlite3.DatabaseError, OSError, ValueError) as error:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "kind": "tool-shed-idea-readiness-error",
            "status": "REVIEW-UNAVAILABLE",
            "code": "runtime-unavailable",
            "message": str(error),
            "promotion_allowed": False,
            "writes_performed": False,
        }
        if args.json:
            _print(payload)
        else:
            print(f"REVIEW-UNAVAILABLE: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
