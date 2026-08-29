#!/usr/bin/env python3
"""Inventory, archive, convert, qualify, and rollback Tool Shed work collateral."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any, Sequence

import document_store
import hybrid_state
from document_contract import GENERATED
from project_identity import ProjectIdentityError, load_project_identity, require_path_within, resolved_workspace


TYPE_ALIASES = {
    "idea": "idea-brief", "idea-brief": "idea-brief",
    "map": "project-map", "project-map": "project-map", "coordination-map": "project-map",
    "program-roadmap": "program-roadmap", "campaign": "campaign", "ticket": "ticket",
    "checklist": "checklist", "spike": "spike", "deep-research": "spike", "deep-research-spike": "spike",
    "adr": "adr", "decision": "decision", "decision-matrix": "decision",
    "inventory": "inventory", "project-inventory": "inventory", "existing-project-inventory": "inventory", "level-2-inventory": "inventory",
    "runbook": "runbook", "workpackage": "workpackage", "wp": "workpackage", "incident": "incident",
    "q-and-a": "q-and-a", "evidence": "evidence-summary", "focus-area": "focus-area",
}
PROJECTION_PATHS = {
    "work/index.md", "work/00-campaigns/active-queue.md", "work/00-campaigns/completed-queue.md",
}


class ConversionError(RuntimeError):
    pass


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def manifest_token(payload: dict[str, Any]) -> str:
    material = dict(payload)
    material.pop("manifest_token", None)
    return digest_bytes(json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())[:16]


def _header_value(text: str, field: str) -> str | None:
    prefix = field + ":"
    for line in text.splitlines()[:80]:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def _classification(relative: str, data: bytes) -> tuple[str, str | None, str | None]:
    if relative in PROJECTION_PATHS or relative.endswith("/index.md") or relative.endswith("-queue.md"):
        return "projection", None, None
    if relative.startswith("work/state/") or not relative.endswith(".md"):
        return "file-owned", None, None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "file-owned", None, "non-UTF-8 file"
    raw_type = (_header_value(text, "Type") or "").casefold()
    document_type = TYPE_ALIASES.get(raw_type)
    if document_type:
        return "generated", document_type, None
    return "unresolved", None, "Markdown lacks a recognized generated Type header"


def _lifecycle(value: str | None) -> str:
    normalized = (value or "active").casefold()
    aliases = {
        "complete": "completed", "passed": "completed", "queued": "active", "planned": "active",
        "approved": "active", "promoted": "active", "ready-for-prm": "active", "accepted": "active",
        "executing": "working",
    }
    result = aliases.get(normalized, normalized)
    return result if result in document_store.LIFECYCLES else "active"


def _git_state(workspace: Path, relative: str) -> str:
    return hybrid_state.tracked_state(workspace, relative)


def build_plan(workspace: Path, *, database: Path | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    identity = load_project_identity(workspace)
    existing_artifacts: dict[str, str] = {}
    existing_documents: dict[str, tuple[str, int]] = {}
    baseline: dict[str, list[dict[str, Any]]] = {"artifact_bindings": [], "relationships": [], "history_rows": []}
    if database and database.is_file():
        with contextlib.closing(hybrid_state.connect(database, writable=False)) as connection:
            tables = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='table'")}
            existing_artifacts = {str(row["current_path"]): str(row["id"]) for row in connection.execute("SELECT id, current_path FROM artifact")}
            baseline["artifact_bindings"] = [{"path": path, "artifact_id": artifact_id} for path, artifact_id in sorted(existing_artifacts.items())]
            baseline["relationships"] = hybrid_state.table_rows(connection, "relationship")
            for table in ("managed_operation", "structural_change", "event", "migration_ledger", "export_ledger", "checkpoint_ledger"):
                for row in hybrid_state.table_rows(connection, table):
                    baseline["history_rows"].append({"table": table, "id": row["id"], "sha256": digest_bytes(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())})
            if "document" in tables:
                existing_documents = {str(row["id"]): (str(row["namespace"]), int(row["display_number"])) for row in connection.execute("SELECT id, namespace, display_number FROM document")}
    entries: list[dict[str, Any]] = []
    for path in sorted((workspace / "work").rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(workspace).as_posix()
        data = path.read_bytes()
        classification, document_type, warning = _classification(relative, data)
        artifact_id = existing_artifacts.get(relative)
        if classification == "generated" and artifact_id is None:
            artifact_id = str(uuid.uuid5(uuid.UUID(identity["project_id"]), f"document:{relative}"))
        namespace = GENERATED.get(document_type) if document_type else None
        assigned_number = None
        if artifact_id in existing_documents:
            namespace, assigned_number = existing_documents[artifact_id]
        if document_type == "campaign":
            try:
                assigned_number = int(_header_value(data.decode("utf-8"), "Campaign Number") or "")
            except ValueError:
                warning = "campaign lacks a valid Campaign Number"
                classification, document_type, namespace, artifact_id = "unresolved", None, None, None
        entries.append({
            "path": relative, "size": len(data), "sha256": digest_bytes(data), "git_state": _git_state(workspace, relative),
            "classification": classification, "document_type": document_type, "namespace": namespace,
            "assigned_number": assigned_number, "artifact_id": artifact_id, "warning": warning,
        })
    used: dict[str, set[int]] = {}
    for entry in entries:
        if entry["namespace"] and entry["assigned_number"]:
            if entry["assigned_number"] in used.setdefault(entry["namespace"], set()):
                raise ConversionError(f"duplicate assigned ID {entry['namespace']}-{entry['assigned_number']:04d}")
            used[entry["namespace"]].add(entry["assigned_number"])
    for entry in entries:
        namespace = entry["namespace"]
        if not namespace or entry["assigned_number"] is not None:
            continue
        number = 1
        while number in used.setdefault(namespace, set()):
            number += 1
        entry["assigned_number"] = number
        used[namespace].add(number)
    payload = {
        "schema_version": 1, "kind": "tool-shed-document-conversion-manifest", "project_id": identity["project_id"],
        "prepared_at": hybrid_state.now(), "baseline": baseline, "entries": entries, "manifest_token": "",
    }
    payload["manifest_token"] = manifest_token(payload)
    return payload


def load_plan(workspace: Path, supplied: Path) -> dict[str, Any]:
    path = require_path_within(workspace, supplied if supplied.is_absolute() else workspace / supplied)
    payload = json.loads(path.read_text(encoding="utf-8"))
    identity = load_project_identity(workspace)
    if payload.get("schema_version") != 1 or payload.get("kind") != "tool-shed-document-conversion-manifest" or payload.get("project_id") != identity["project_id"]:
        raise ConversionError("conversion manifest identity does not match this project")
    if payload.get("manifest_token") != manifest_token(payload):
        raise ConversionError("conversion manifest token is invalid")
    if not isinstance(payload.get("entries"), list):
        raise ConversionError("conversion manifest needs entries")
    return payload


def create_archive(workspace: Path, *, manifest: dict[str, Any], destination: Path) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    destination = destination.resolve()
    if workspace == destination or workspace in destination.parents or destination in workspace.parents:
        raise ConversionError("retained-source archive must be outside the workspace")
    if destination.exists():
        raise ConversionError(f"archive destination exists: {destination}")
    destination.mkdir(parents=True)
    copied = []
    try:
        for entry in manifest["entries"]:
            source = require_path_within(workspace, workspace / entry["path"])
            if digest_bytes(source.read_bytes()) != entry["sha256"]:
                raise ConversionError(f"source changed before archive: {entry['path']}")
            target = destination / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if digest_bytes(target.read_bytes()) != entry["sha256"]:
                raise ConversionError(f"archive copy failed parity: {entry['path']}")
            copied.append(entry["path"])
        archive_manifest = {"schema_version": 1, "kind": "tool-shed-retained-source-archive", "project_id": manifest["project_id"], "conversion_manifest_token": manifest["manifest_token"], "created_at": hybrid_state.now(), "entries": [{"path": entry["path"], "sha256": entry["sha256"], "size": entry["size"]} for entry in manifest["entries"]]}
        (destination / "archive-manifest.json").write_text(json.dumps(archive_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return {"schema_version": 1, "kind": "tool-shed-retained-source-archive-result", "path": str(destination), "files": len(copied), "manifest_token": manifest["manifest_token"], "writes_performed": True}


def apply_plan(workspace: Path, *, project_binding: str, manifest: dict[str, Any], database: Path, actor: str, fail_after: int | None = None) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    imported, idempotent = [], []
    processed = 0
    for entry in manifest["entries"]:
        if entry["classification"] != "generated":
            continue
        source = workspace / entry["path"]
        if digest_bytes(source.read_bytes()) != entry["sha256"]:
            raise ConversionError(f"source changed after inventory: {entry['path']}")
        if fail_after is not None and processed >= fail_after:
            raise ConversionError("simulated conversion interruption")
        result = document_store.import_document(
            workspace, project_binding=project_binding, source=Path(entry["path"]), document_type=entry["document_type"],
            lifecycle=_lifecycle(_header_value(source.read_text(encoding="utf-8"), "Status")), actor=actor,
            reason=f"conversion manifest {manifest['manifest_token']}", assigned_number=entry["assigned_number"], artifact_id=entry["artifact_id"], database=database,
        )["result"]
        (idempotent if result["idempotent"] else imported).append(entry["path"])
        processed += 1
    return {"schema_version": 1, "kind": "tool-shed-document-conversion-apply", "manifest_token": manifest["manifest_token"], "imported": imported, "idempotent": idempotent, "writes_performed": bool(imported)}


def qualify(workspace: Path, *, manifest: dict[str, Any], database: Path) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    findings = []
    checked = document_store.audit(workspace, database)
    if checked["classification"] not in {"CLEAN", "VALID_DIRTY"}:
        findings.append(f"database classification is {checked['classification']}")
    with contextlib.closing(hybrid_state.connect(database, writable=False)) as connection:
        for binding in manifest["baseline"]["artifact_bindings"]:
            row = connection.execute("SELECT id FROM artifact WHERE current_path=?", (binding["path"],)).fetchone()
            if row is None or row["id"] != binding["artifact_id"]:
                findings.append(f"baseline artifact identity changed: {binding['path']}")
        for expected in manifest["baseline"]["relationships"]:
            row = connection.execute("SELECT * FROM relationship WHERE id=?", (expected["id"],)).fetchone()
            if row is None or dict(row) != expected:
                findings.append(f"baseline relationship changed: {expected['id']}")
        for expected in manifest["baseline"]["history_rows"]:
            row = connection.execute(f"SELECT * FROM {expected['table']} WHERE id=?", (expected["id"],)).fetchone()
            observed = digest_bytes(json.dumps(dict(row), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()) if row else None
            if observed != expected["sha256"]:
                findings.append(f"baseline history changed: {expected['table']}:{expected['id']}")
        for entry in manifest["entries"]:
            source = workspace / entry["path"]
            if not source.is_file() or digest_bytes(source.read_bytes()) != entry["sha256"]:
                findings.append(f"retained source parity failed: {entry['path']}")
                continue
            if entry["classification"] != "generated":
                continue
            conversion = connection.execute("SELECT * FROM document_conversion WHERE source_path=?", (entry["path"],)).fetchone()
            if conversion is None or conversion["artifact_id"] != entry["artifact_id"] or conversion["visible_id"] != f"{entry['namespace']}-{entry['assigned_number']:04d}":
                findings.append(f"identity parity failed: {entry['path']}")
                continue
            revision = connection.execute("SELECT body_markdown, body_sha256 FROM document_revision WHERE document_id=? AND revision_number=1", (entry["artifact_id"],)).fetchone()
            if revision is None or revision["body_sha256"] != entry["sha256"] or digest_bytes(revision["body_markdown"].encode()) != entry["sha256"]:
                findings.append(f"initial revision byte parity failed: {entry['path']}")
    counts = {classification: sum(1 for entry in manifest["entries"] if entry["classification"] == classification) for classification in ("generated", "file-owned", "projection", "unresolved")}
    return {"schema_version": 1, "kind": "tool-shed-document-conversion-qualification", "manifest_token": manifest["manifest_token"], "counts": counts, "baseline": {"artifact_bindings": len(manifest["baseline"]["artifact_bindings"]), "relationships": len(manifest["baseline"]["relationships"]), "history_rows": len(manifest["baseline"]["history_rows"])}, "findings": findings, "passed": not findings, "database_digest": checked["domain_digest"], "writes_performed": False}


def rollback_export(workspace: Path, *, manifest: dict[str, Any], database: Path, output: Path) -> dict[str, Any]:
    workspace = resolved_workspace(workspace)
    target = require_path_within(workspace, output if output.is_absolute() else workspace / output)
    if target.exists():
        raise ConversionError(f"rollback export exists: {target.relative_to(workspace)}")
    generated = [entry for entry in manifest["entries"] if entry["classification"] == "generated"]
    records = []
    try:
        for entry in generated:
            document = document_store.show(workspace, entry["artifact_id"], database=database)
            path = target / entry["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(document["body_markdown"], encoding="utf-8", newline="\n")
            records.append({"path": entry["path"], "artifact_id": entry["artifact_id"], "visible_id": document["visible_id"], "document_revision": document["document_revision"], "sha256": digest_bytes(path.read_bytes())})
        (target / "rollback-manifest.json").write_text(json.dumps({"schema_version": 1, "kind": "tool-shed-document-rollback-export", "conversion_manifest_token": manifest["manifest_token"], "created_at": hybrid_state.now(), "documents": records}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise
    return {"schema_version": 1, "kind": "tool-shed-document-rollback-export-result", "path": target.relative_to(workspace).as_posix(), "documents": len(records), "writes_performed": True}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory"); inventory.add_argument("--database")
    archive = commands.add_parser("archive"); archive.add_argument("--manifest", required=True); archive.add_argument("--output", required=True)
    apply = commands.add_parser("apply"); apply.add_argument("--manifest", required=True); apply.add_argument("--database", required=True); apply.add_argument("--project-binding", required=True); apply.add_argument("--actor", required=True)
    qualify_parser = commands.add_parser("qualify"); qualify_parser.add_argument("--manifest", required=True); qualify_parser.add_argument("--database", required=True)
    rollback = commands.add_parser("rollback-export"); rollback.add_argument("--manifest", required=True); rollback.add_argument("--database", required=True); rollback.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        workspace = resolved_workspace(Path(args.workspace))
        if args.command == "inventory":
            result = build_plan(workspace, database=(workspace / args.database) if args.database else None)
        else:
            manifest = load_plan(workspace, Path(args.manifest))
            if args.command == "archive": result = create_archive(workspace, manifest=manifest, destination=Path(args.output))
            elif args.command == "apply": result = apply_plan(workspace, project_binding=args.project_binding, manifest=manifest, database=workspace / args.database, actor=args.actor)
            elif args.command == "qualify": result = qualify(workspace, manifest=manifest, database=workspace / args.database)
            else: result = rollback_export(workspace, manifest=manifest, database=workspace / args.database, output=Path(args.output))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1 if args.command == "qualify" and not result["passed"] else 0
    except (ConversionError, document_store.DocumentStoreError, hybrid_state.HybridStateError, ProjectIdentityError, OSError, ValueError, sqlite3.DatabaseError, json.JSONDecodeError) as error:
        print(f"Document conversion failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
