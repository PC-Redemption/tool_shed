#!/usr/bin/env python3
"""Guarded maintainer-only rehearsal, archive, cutover, and soak for hybrid state."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import contextlib
import hashlib
import io
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

import hybrid_state
import outcome_reconciliation
from project_identity import (
    ProjectIdentityError,
    binding_token,
    load_project_identity,
    resolved_workspace,
)


KIND_INVENTORY = "tool-shed-maintainer-conversion-inventory"
KIND_REHEARSAL = "tool-shed-maintainer-hybrid-rehearsal"
KIND_CUTOVER = "tool-shed-maintainer-hybrid-cutover"
KIND_SOAK = "tool-shed-maintainer-hybrid-soak"
ASSIGNED_IDS = Path("schemas/hybrid-state/v1/maintainer-assigned-ids.json")
ARCHIVE_INVENTORY = ".tool-shed-archive/conversion-inventory.json"
CHECKPOINT = Path("work/state/checkpoints/state-v1.json")


class ConversionError(RuntimeError):
    pass


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def run_git(workspace: Path, *arguments: str, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", *arguments],
        cwd=workspace,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode:
        raise ConversionError(result.stderr.decode("utf-8", errors="replace").strip() or "Git operation failed")
    return result.stdout


def git_paths(workspace: Path, *arguments: str) -> set[str]:
    return {
        item.decode("utf-8", errors="strict")
        for item in run_git(workspace, *arguments).split(b"\0")
        if item
    }


def source_status(workspace: Path) -> str:
    return run_git(workspace, "status", "--porcelain=v1", "--untracked-files=all").decode(
        "utf-8", errors="replace"
    ).strip()


def require_clean_source(workspace: Path) -> None:
    observed = source_status(workspace)
    if observed:
        raise ConversionError("maintainer conversion requires a clean tracked and untracked source state")


def file_material(path: Path) -> tuple[str, bytes]:
    if path.is_symlink():
        return "symlink", os.readlink(path).encode("utf-8")
    if path.is_file():
        return "file", path.read_bytes()
    raise ConversionError(f"inventory path is not a file or symlink: {path}")


def header_identity(path: Path) -> tuple[str | None, str | None]:
    if path.suffix.lower() != ".md" or path.is_symlink():
        return None, None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[:45]
    except UnicodeDecodeError:
        return None, None
    number = next(
        (line.split(":", 1)[1].strip() for line in lines if line.startswith("Campaign Number:")),
        None,
    )
    stable_id = next(
        (
            line.split(":", 1)[1].strip()
            for line in lines
            if line.startswith(("Campaign ID:", "Roadmap ID:", "Idea ID:", "Map ID:"))
        ),
        None,
    )
    return number, stable_id


def build_inventory(workspace: Path, assignments_path: Path = ASSIGNED_IDS) -> dict[str, Any]:
    tracked = git_paths(workspace, "ls-files", "-z")
    untracked = git_paths(workspace, "ls-files", "--others", "--exclude-standard", "-z")
    ignored = git_paths(workspace, "ls-files", "--others", "--ignored", "--exclude-standard", "-z")
    overlap = (tracked & untracked) | (tracked & ignored) | (untracked & ignored)
    if overlap:
        raise ConversionError("Git inventory classifications overlap: " + ", ".join(sorted(overlap)))
    assignments = hybrid_state.load_assigned_file_ids(workspace, assignments_path)
    entries: list[dict[str, Any]] = []
    for relative in sorted(tracked | untracked | ignored):
        path = workspace / relative
        kind, material = file_material(path)
        number, stable_id = header_identity(path)
        git_state = "tracked" if relative in tracked else "untracked" if relative in untracked else "ignored"
        assignment = assignments.get(relative)
        entries.append(
            {
                "path": relative,
                "kind": kind,
                "mode": stat.S_IMODE(path.lstat().st_mode),
                "size": len(material),
                "sha256": hashlib.sha256(material).hexdigest(),
                "git_state": git_state,
                "existing_number": number,
                "existing_id": stable_id,
                "assigned_artifact_id": assignment["artifact_id"] if assignment else None,
                "assigned_import_id": assignment["import_id"] if assignment else None,
                "owner_extension": path.suffix.lower() or None,
                "disposition": "retained-source-import" if assignment else "retain-unchanged",
                "unknown_fields": [],
                "warnings": [],
            }
        )
    missing_assignments = sorted(set(assignments) - {item["path"] for item in entries})
    if missing_assignments:
        raise ConversionError("assigned-ID sources are missing: " + ", ".join(missing_assignments))
    identity = load_project_identity(workspace)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "kind": KIND_INVENTORY,
        "project_id": identity["project_id"],
        "source_commit": run_git(workspace, "rev-parse", "HEAD").decode().strip(),
        "branch": run_git(workspace, "branch", "--show-current").decode().strip() or "detached",
        "counts": {
            "tracked": len(tracked),
            "untracked": len(untracked),
            "ignored": len(ignored),
            "assigned": len(assignments),
        },
        "entries": entries,
    }
    payload["inventory_digest"] = digest(payload)
    return payload


def require_external_path(workspace: Path, supplied: Path) -> Path:
    workspace = workspace.expanduser().resolve()
    target = supplied.expanduser().resolve()
    try:
        target.relative_to(workspace)
    except ValueError:
        pass
    else:
        raise ConversionError("conversion archives and reports must live outside the maintainer workspace")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def create_archive(workspace: Path, output: Path) -> dict[str, Any]:
    require_clean_source(workspace)
    if hybrid_state.database_path(workspace).exists():
        raise ConversionError("archive preparation refuses an existing live database; use the SQLite backup API")
    target = require_external_path(workspace, output)
    if target.exists():
        raise ConversionError(f"archive already exists: {target}")
    inventory = build_inventory(workspace)
    with tarfile.open(target, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        encoded = json.dumps(inventory, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        info = tarfile.TarInfo(ARCHIVE_INVENTORY)
        info.size = len(encoded)
        info.mode = 0o600
        info.mtime = 0
        archive.addfile(info, io.BytesIO(encoded))
        for entry in inventory["entries"]:
            archive.add(workspace / entry["path"], arcname=entry["path"], recursive=False)
    verified = verify_archive(target)
    if verified["inventory_digest"] != inventory["inventory_digest"]:
        target.unlink(missing_ok=True)
        raise ConversionError("archive verification changed the inventory digest")
    return {
        "schema_version": 1,
        "kind": "tool-shed-maintainer-conversion-archive",
        "archive": str(target),
        "archive_sha256": hybrid_state.file_sha256(target),
        "inventory_digest": inventory["inventory_digest"],
        "source_commit": inventory["source_commit"],
        "counts": inventory["counts"],
        "writes_performed": True,
    }


def archive_inventory(archive_path: Path) -> dict[str, Any]:
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            member = archive.getmember(ARCHIVE_INVENTORY)
            handle = archive.extractfile(member)
            if handle is None:
                raise ConversionError("archive inventory is unreadable")
            payload = json.loads(handle.read().decode("utf-8"))
    except (OSError, tarfile.TarError, KeyError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ConversionError(f"cannot read conversion archive: {error}") from error
    if payload.get("schema_version") != 1 or payload.get("kind") != KIND_INVENTORY:
        raise ConversionError("unsupported conversion inventory")
    expected = payload.get("inventory_digest")
    material = dict(payload)
    material.pop("inventory_digest", None)
    if not isinstance(expected, str) or digest(material) != expected:
        raise ConversionError("conversion inventory digest is invalid")
    return payload


def verify_archive(archive_path: Path) -> dict[str, Any]:
    target = archive_path.expanduser().resolve()
    inventory = archive_inventory(target)
    expected_names = {ARCHIVE_INVENTORY, *(item["path"] for item in inventory["entries"])}
    with tarfile.open(target, "r:gz") as archive:
        names = {item.name for item in archive.getmembers() if item.isfile() or item.issym()}
        if names != expected_names:
            raise ConversionError("archive membership does not exactly match its inventory")
        for entry in inventory["entries"]:
            member = archive.getmember(entry["path"])
            if member.issym():
                material = member.linkname.encode("utf-8")
            else:
                handle = archive.extractfile(member)
                if handle is None:
                    raise ConversionError(f"archive member is unreadable: {entry['path']}")
                material = handle.read()
            if len(material) != entry["size"] or hashlib.sha256(material).hexdigest() != entry["sha256"]:
                raise ConversionError(f"archive member failed byte verification: {entry['path']}")
    return {
        "schema_version": 1,
        "kind": "tool-shed-maintainer-conversion-archive-verification",
        "archive": str(target),
        "archive_sha256": hybrid_state.file_sha256(target),
        "inventory_digest": inventory["inventory_digest"],
        "source_commit": inventory["source_commit"],
        "counts": inventory["counts"],
        "valid": True,
        "writes_performed": False,
    }


def restore_archive(archive_path: Path, destination: Path) -> dict[str, Any]:
    inventory = archive_inventory(archive_path)
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as archive:
        for entry in inventory["entries"]:
            relative = Path(entry["path"])
            if relative.is_absolute() or ".." in relative.parts or relative.parts[0] == ".git":
                raise ConversionError(f"unsafe archive member: {entry['path']}")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink() or target.exists():
                if target.is_dir() and not target.is_symlink():
                    raise ConversionError(f"archive file collides with a directory: {entry['path']}")
                target.unlink()
            member = archive.getmember(entry["path"])
            if member.issym():
                link = member.linkname
                if Path(link).is_absolute() or ".." in Path(link).parts:
                    raise ConversionError(f"unsafe archived symlink: {entry['path']}")
                target.symlink_to(link)
            else:
                handle = archive.extractfile(member)
                if handle is None:
                    raise ConversionError(f"archive member is unreadable: {entry['path']}")
                target.write_bytes(handle.read())
                target.chmod(entry["mode"])
    return {"inventory_digest": inventory["inventory_digest"], "restored": len(inventory["entries"])}


def assigned_source_fingerprint(workspace: Path) -> str:
    assignments = hybrid_state.load_assigned_file_ids(workspace, ASSIGNED_IDS)
    rows = []
    for relative in sorted(assignments):
        path = workspace / relative
        rows.append((relative, hybrid_state.file_sha256(path)))
    return digest(rows)


def semantic_projection(workspace: Path) -> dict[str, Any]:
    database = hybrid_state.database_path(workspace)
    with contextlib.closing(hybrid_state.connect(database, writable=False)) as connection:
        return {
            "artifacts": [
                {key: row[key] for key in ("id", "type", "current_path", "authority_mode", "lifecycle_state", "content_sha256")}
                for row in hybrid_state.table_rows(connection, "artifact")
            ],
            "imports": [
                {key: row[key] for key in ("id", "artifact_id", "source_path", "source_sha256", "tracked_state", "parse_status")}
                for row in hybrid_state.table_rows(connection, "import_record")
            ],
            "cycles": [
                {key: row[key] for key in ("id", "kind", "origin_artifact_id", "accepted_outcome", "lifecycle_state")}
                for row in hybrid_state.table_rows(connection, "cycle")
            ],
            "requirements": [
                {
                    key: row[key]
                    for key in (
                        "id",
                        "cycle_id",
                        "accepted_outcome",
                        "disposition",
                        "milestone_key",
                        "evidence_gate_key",
                    )
                }
                for row in hybrid_state.table_rows(connection, "requirement")
            ],
            "changes": [
                {
                    key: row[key]
                    for key in (
                        "id",
                        "cycle_id",
                        "requirement_id",
                        "decision_id",
                        "summary",
                        "rationale",
                        "authorization_ref",
                        "supersedes_change_id",
                        "evidence_rerun_json",
                        "recorded_revision",
                    )
                }
                for row in hybrid_state.table_rows(connection, "material_change")
            ],
            "relationships": [
                {
                    key: row[key]
                    for key in (
                        "id",
                        "from_artifact_id",
                        "relation_type",
                        "to_artifact_id",
                        "provenance",
                        "created_revision",
                        "retired_revision",
                    )
                }
                for row in hybrid_state.table_rows(connection, "relationship")
            ],
            "evidence": [
                {
                    key: row[key]
                    for key in ("id", "cycle_id", "kind", "reference", "sha256", "target_identity")
                }
                for row in hybrid_state.table_rows(connection, "evidence_reference")
            ],
            "verifications": [
                {
                    key: row[key]
                    for key in (
                        "id",
                        "evidence_id",
                        "requirement_id",
                        "status",
                        "command_or_test_id",
                        "source_revision",
                        "details_json",
                    )
                }
                for row in hybrid_state.table_rows(connection, "verification_result")
            ],
            "verdicts": [
                {key: row[key] for key in ("id", "cycle_id", "scope", "disposition", "summary", "authorization_ref")}
                for row in hybrid_state.table_rows(connection, "outcome_verdict")
            ],
            "reconciliations": [
                {
                    key: row[key]
                    for key in (
                        "id",
                        "cycle_id",
                        "origin_revision",
                        "product_truth_ref",
                        "verdict_id",
                        "state",
                        "residual_work_json",
                    )
                }
                for row in hybrid_state.table_rows(connection, "reconciliation")
            ],
        }


def verify_assigned_imports(workspace: Path) -> None:
    assignments = hybrid_state.load_assigned_file_ids(workspace, ASSIGNED_IDS)
    with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(workspace), writable=False)) as connection:
        for relative, assigned in assignments.items():
            artifact = connection.execute(
                "SELECT id, content_sha256 FROM artifact WHERE current_path = ?", (relative,)
            ).fetchone()
            imported = connection.execute(
                "SELECT id FROM import_record WHERE artifact_id = ? AND source_sha256 = ?",
                (assigned["artifact_id"], hybrid_state.file_sha256(workspace / relative)),
            ).fetchone()
            if artifact is None or artifact["id"] != assigned["artifact_id"]:
                raise ConversionError(f"assigned artifact was not preserved: {relative}")
            if imported is None or imported["id"] != assigned["import_id"]:
                raise ConversionError(f"assigned import was not preserved: {relative}")


def perform_conversion(workspace: Path, *, rehearsal: bool) -> dict[str, Any]:
    if hybrid_state.database_path(workspace).exists():
        raise ConversionError("conversion refuses to overwrite an existing state database")
    binding = binding_token(workspace, operation=hybrid_state.OPERATION)
    before = assigned_source_fingerprint(workspace)
    hybrid_state.initialize(workspace, project_binding=binding)
    outcome_reconciliation.apply_hpt2(workspace, project_binding=binding)
    outcome_reconciliation.apply_bounded_mutation(workspace, project_binding=binding)
    assignments = hybrid_state.load_assigned_file_ids(workspace, ASSIGNED_IDS)
    hybrid_state.import_files(
        workspace,
        [Path(item) for item in assignments],
        project_binding=binding,
        actor="maintainer-conversion",
        assigned_ids=assignments,
    )
    parity = outcome_reconciliation.qualify_parity(workspace)
    if not parity["valid"]:
        raise ConversionError("HPT2 file/hybrid parity failed during conversion")
    shadow_checkpoint = hybrid_state.write_checkpoint(workspace, project_binding=binding)
    shadow_rebuild = hybrid_state.rebuild_from_checkpoint(
        workspace,
        project_binding=binding,
        checkpoint=CHECKPOINT,
        output=Path(".tool-shed/rebuilt-shadow.sqlite3"),
    )
    backup = hybrid_state.verified_backup(workspace, project_binding=binding)
    hybrid_state.activate_hybrid_mode(
        workspace,
        project_binding=binding,
        expected_checkpoint_digest=shadow_checkpoint["digest"],
    )
    checkpoint = hybrid_state.write_checkpoint(workspace, project_binding=binding)
    hybrid_rebuild = hybrid_state.rebuild_from_checkpoint(
        workspace,
        project_binding=binding,
        checkpoint=CHECKPOINT,
        output=Path(".tool-shed/rebuilt-hybrid.sqlite3"),
    )
    audit = hybrid_state.audit(workspace)
    rebuilt_audit = hybrid_state.audit(workspace, workspace / ".tool-shed/rebuilt-hybrid.sqlite3")
    if audit["classification"] != "CLEAN" or rebuilt_audit["classification"] != "CLEAN":
        raise ConversionError("cutover or rebuilt database did not enter CLEAN state")
    if audit["domain_digest"] != rebuilt_audit["domain_digest"]:
        raise ConversionError("hybrid rebuild does not match live semantic state")
    if hybrid_state.legacy_write_check(workspace, "artifact.id")["allowed"]:
        raise ConversionError("legacy SQLite-owned field writer was not refused")
    if not hybrid_state.legacy_write_check(workspace, "docs.body")["allowed"]:
        raise ConversionError("file-owned body writer was incorrectly refused")
    verify_assigned_imports(workspace)
    after = assigned_source_fingerprint(workspace)
    if before != after:
        raise ConversionError("assigned retained source changed during the no-write window")
    semantic = semantic_projection(workspace)
    rehearsal_checks: dict[str, Any] = {}
    if rehearsal:
        rebuilt = workspace / ".tool-shed/rebuilt-hybrid.sqlite3"
        with contextlib.closing(hybrid_state.connect(rebuilt)) as connection:
            first = connection.execute("SELECT id FROM artifact ORDER BY id LIMIT 1").fetchone()[0]
            connection.execute("UPDATE artifact SET lifecycle_state = 'direct-sql-test' WHERE id = ?", (first,))
            connection.commit()
        direct = hybrid_state.audit(workspace, rebuilt)
        if direct["classification"] != "UNMANAGED_REVIEW":
            raise ConversionError("direct SQL rehearsal did not enter UNMANAGED_REVIEW")
        reconciled_direct = hybrid_state.reconcile_unmanaged(
            workspace,
            project_binding=binding,
            expected_revision=direct["current_revision"],
            expected_domain_digest=direct["domain_digest"],
            authorization_ref="maintainer conversion rehearsal",
            summary="Accept the bounded direct-SQL rehearsal mutation before disposable rebuild.",
            path=rebuilt,
        )
        if reconciled_direct["audit"]["classification"] != "VALID_DIRTY":
            raise ConversionError("direct SQL rehearsal did not reconcile into managed review state")
        rebuilt.unlink()
        recovered = hybrid_state.rebuild_from_checkpoint(
            workspace,
            project_binding=binding,
            checkpoint=CHECKPOINT,
            output=Path(".tool-shed/rebuilt-hybrid.sqlite3"),
        )
        interrupted_before = hybrid_state.audit(workspace)["domain_digest"]

        def interrupted(connection: sqlite3.Connection, revision: int) -> None:
            raise RuntimeError("simulated conversion interruption")

        try:
            hybrid_state.managed_write(
                workspace,
                project_binding=binding,
                command="conversion-interruption-rehearsal",
                actor="maintainer-conversion",
                callback=interrupted,
            )
        except RuntimeError as error:
            if str(error) != "simulated conversion interruption":
                raise
        else:
            raise ConversionError("interruption rehearsal unexpectedly committed")
        interruption_audit = hybrid_state.audit(workspace)
        if interruption_audit["classification"] != "CLEAN" or interruption_audit["domain_digest"] != interrupted_before:
            raise ConversionError("interruption rehearsal did not roll back completely")
        rehearsal_checks = {
            "direct_sql_classification": direct["classification"],
            "direct_sql_reconciled_classification": reconciled_direct["audit"]["classification"],
            "direct_sql_rebuild_digest": recovered["domain_digest"],
            "interruption_classification": interruption_audit["classification"],
        }
    return {
        "source_fingerprint": before,
        "parity": parity,
        "shadow_checkpoint": shadow_checkpoint,
        "shadow_rebuild": shadow_rebuild,
        "backup": backup,
        "checkpoint": checkpoint,
        "hybrid_rebuild": hybrid_rebuild,
        "audit": audit,
        "assigned_imports": len(hybrid_state.load_assigned_file_ids(workspace, ASSIGNED_IDS)),
        "semantic_digest": digest(semantic),
        "rehearsal_checks": rehearsal_checks,
    }


def clone_and_restore(workspace: Path, archive_path: Path, destination: Path) -> None:
    result = subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(workspace), str(destination)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise ConversionError(result.stderr.decode("utf-8", errors="replace").strip() or "disposable clone failed")
    restore_archive(archive_path, destination)


def rehearsal(workspace: Path, archive_path: Path, runs: int) -> dict[str, Any]:
    if runs < 2:
        raise ConversionError("maintainer conversion requires at least two disposable rehearsals")
    verified = verify_archive(archive_path)
    inventory = archive_inventory(archive_path)
    if inventory["source_commit"] != run_git(workspace, "rev-parse", "HEAD").decode().strip():
        raise ConversionError("rehearsal archive does not match the current source commit")
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="tool-shed-hybrid-rehearsal-") as parent_text:
        parent = Path(parent_text)
        for index in range(runs):
            clone = parent / f"run-{index + 1}"
            clone_and_restore(workspace, archive_path, clone)
            result = perform_conversion(clone, rehearsal=True)
            rollback = parent / f"rollback-{index + 1}"
            restored = restore_archive(archive_path, rollback)
            if restored["inventory_digest"] != inventory["inventory_digest"]:
                raise ConversionError("rollback restore did not reproduce the archived inventory")
            foreign = parent / f"worktree-{index + 1}"
            worktree = subprocess.run(
                ["git", "worktree", "add", "--detach", str(foreign), "HEAD"],
                cwd=clone,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if worktree.returncode:
                raise ConversionError(
                    worktree.stderr.decode("utf-8", errors="replace").strip()
                    or "disposable worktree creation failed"
                )
            try:
                restore_archive(archive_path, foreign)
                (foreign / ".tool-shed").mkdir(exist_ok=True)
                shutil.copy2(clone / ".tool-shed/state.sqlite3", foreign / ".tool-shed/state.sqlite3")
                lineage = hybrid_state.audit(foreign)
                if lineage["classification"] != "INVALID" or not any(
                    "worktree lineage" in item for item in lineage["findings"]
                ):
                    raise ConversionError("foreign worktree lineage rehearsal did not fail closed")
            finally:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(foreign)],
                    cwd=clone,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
            result["rollback_restore"] = restored
            result["foreign_lineage_classification"] = lineage["classification"]
            results.append(result)
    semantic_digests = {item["semantic_digest"] for item in results}
    source_fingerprints = {item["source_fingerprint"] for item in results}
    payload = {
        "schema_version": 1,
        "kind": KIND_REHEARSAL,
        "source_commit": inventory["source_commit"],
        "archive_sha256": verified["archive_sha256"],
        "inventory_digest": inventory["inventory_digest"],
        "runs": runs,
        "semantic_digests": sorted(semantic_digests),
        "source_fingerprints": sorted(source_fingerprints),
        "deterministic": len(semantic_digests) == 1 and len(source_fingerprints) == 1,
        "results": results,
        "writes_performed": False,
    }
    if not payload["deterministic"]:
        raise ConversionError("disposable conversion rehearsals were not semantically deterministic")
    payload["rehearsal_token"] = digest(payload)
    return payload


def load_rehearsal(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConversionError(f"cannot load rehearsal report: {error}") from error
    token = payload.get("rehearsal_token")
    material = dict(payload)
    material.pop("rehearsal_token", None)
    if payload.get("kind") != KIND_REHEARSAL or not payload.get("deterministic") or digest(material) != token:
        raise ConversionError("rehearsal report is invalid or unsuccessful")
    return payload


def cutover(
    workspace: Path,
    archive_path: Path,
    rehearsal_path: Path,
    project_binding: str,
) -> dict[str, Any]:
    require_clean_source(workspace)
    expected_binding = binding_token(workspace, operation=hybrid_state.OPERATION)
    if project_binding != expected_binding:
        raise ConversionError("live cutover project binding does not match this maintainer workspace")
    inventory = archive_inventory(archive_path)
    verified = verify_archive(archive_path)
    report = load_rehearsal(rehearsal_path)
    commit = run_git(workspace, "rev-parse", "HEAD").decode().strip()
    if report["source_commit"] != commit or inventory["source_commit"] != commit:
        raise ConversionError("live cutover inputs do not match the exact current source commit")
    if report["archive_sha256"] != verified["archive_sha256"]:
        raise ConversionError("live cutover archive differs from the rehearsed archive")
    current = build_inventory(workspace)
    if current["inventory_digest"] != inventory["inventory_digest"]:
        raise ConversionError("live maintainer inventory differs from the archived rehearsal source")
    result = perform_conversion(workspace, rehearsal=False)
    return {
        "schema_version": 1,
        "kind": KIND_CUTOVER,
        "source_commit": commit,
        "archive_sha256": verified["archive_sha256"],
        "inventory_digest": inventory["inventory_digest"],
        "rehearsal_token": report["rehearsal_token"],
        "result": result,
        "writes_performed": True,
    }


def soak(workspace: Path, minimum_seconds: float) -> dict[str, Any]:
    if minimum_seconds < 0 or minimum_seconds > 3600:
        raise ConversionError("soak duration must be between 0 and 3600 seconds")
    started = time.monotonic()
    first = hybrid_state.audit(workspace)
    if first["classification"] != "CLEAN" or first["storage_mode"] != "hybrid":
        raise ConversionError("soak requires a clean hybrid database")
    if minimum_seconds:
        time.sleep(minimum_seconds)
    second = hybrid_state.audit(workspace)
    elapsed = time.monotonic() - started
    if second["classification"] != "CLEAN" or second["domain_digest"] != first["domain_digest"]:
        raise ConversionError("hybrid state changed or degraded during soak")
    return {
        "schema_version": 1,
        "kind": KIND_SOAK,
        "minimum_seconds": minimum_seconds,
        "observed_seconds": round(elapsed, 3),
        "first": first,
        "second": second,
        "passed": True,
        "writes_performed": False,
    }


def write_external_json(workspace: Path, output: Path, payload: dict[str, Any]) -> Path:
    target = require_external_path(workspace, output)
    if target.exists():
        raise ConversionError(f"report already exists: {target}")
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory")
    inventory.add_argument("--output")
    archive = commands.add_parser("archive")
    archive.add_argument("--output", required=True)
    verify = commands.add_parser("verify-archive")
    verify.add_argument("--archive", required=True)
    rehearse = commands.add_parser("rehearse")
    rehearse.add_argument("--archive", required=True)
    rehearse.add_argument("--runs", type=int, default=2)
    rehearse.add_argument("--report", required=True)
    live = commands.add_parser("cutover")
    live.add_argument("--archive", required=True)
    live.add_argument("--rehearsal-report", required=True)
    live.add_argument("--project-binding", required=True)
    live.add_argument("--report", required=True)
    soak_parser = commands.add_parser("soak")
    soak_parser.add_argument("--minimum-seconds", type=float, default=5.0)
    soak_parser.add_argument("--report")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        workspace = resolved_workspace(Path(args.workspace))
        if args.command == "inventory":
            result = build_inventory(workspace)
            if args.output:
                write_external_json(workspace, Path(args.output), result)
        elif args.command == "archive":
            result = create_archive(workspace, Path(args.output))
        elif args.command == "verify-archive":
            result = verify_archive(Path(args.archive))
        elif args.command == "rehearse":
            result = rehearsal(workspace, Path(args.archive), args.runs)
            result["report"] = str(write_external_json(workspace, Path(args.report), result))
        elif args.command == "cutover":
            result = cutover(
                workspace,
                Path(args.archive),
                Path(args.rehearsal_report),
                args.project_binding,
            )
            result["report"] = str(write_external_json(workspace, Path(args.report), result))
        else:
            result = soak(workspace, args.minimum_seconds)
            if args.report:
                result["report"] = str(write_external_json(workspace, Path(args.report), result))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (
        ConversionError,
        hybrid_state.HybridStateError,
        outcome_reconciliation.ReconciliationError,
        ProjectIdentityError,
        OSError,
        sqlite3.DatabaseError,
        ValueError,
    ) as error:
        print(f"Maintainer hybrid conversion failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
