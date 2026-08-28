#!/usr/bin/env python3
"""Guarded phase-one SQLite operational-state substrate for Tool Shed."""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

from hybrid_state_schema import (
    APPLICATION_ID,
    DOMAIN_TABLES,
    EMPTY_SHA256,
    PORTABLE_TABLES,
    SCHEMA_VERSION,
    create_schema,
    create_triggers,
    migration_digest,
    schema_digest,
)
from project_identity import (
    ProjectIdentityError,
    load_project_identity,
    require_path_within,
    require_project_binding,
    resolved_workspace,
)


OPERATION = "hybrid-state"
CHECKPOINT_KIND = "tool-shed-hybrid-state-checkpoint"
CHECKPOINT_FORMAT = 1
LOCK_TIMEOUT_SECONDS = 5.0
CHECKPOINT_REVISION_LIMIT = 100
CHECKPOINT_AGE_SECONDS = 24 * 60 * 60
BACKUP_RETENTION = 3
DATABASE_RELATIVE = Path(".tool-shed/state.sqlite3")
LOCK_RELATIVE = Path(".tool-shed/state.lock")
BACKUP_RELATIVE = Path(".tool-shed/backups")
CHECKPOINT_RELATIVE = Path("work/state/checkpoints/state-v1.json")

DB_AUTHORITY_FIELDS = {
    "artifact.id",
    "artifact.current_path",
    "relationship",
    "revision",
    "event",
    "requirement",
    "material-change",
    "evidence-reference",
    "verification-result",
    "outcome-verdict",
    "reconciliation",
}


class HybridStateError(RuntimeError):
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


def stable_uuid(project_id: str, value: str) -> str:
    return str(uuid.uuid5(uuid.UUID(project_id), value))


def random_uuid() -> str:
    return str(uuid.uuid4())


def database_path(workspace: Path) -> Path:
    return require_path_within(workspace, workspace / DATABASE_RELATIVE)


def lock_path(workspace: Path) -> Path:
    return require_path_within(workspace, workspace / LOCK_RELATIVE)


def checkpoint_path(workspace: Path) -> Path:
    return require_path_within(workspace, workspace / CHECKPOINT_RELATIVE)


def git_output(workspace: Path, *arguments: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode:
        raise HybridStateError(result.stderr.strip() or "Git operation failed")
    return result.stdout.strip()


def ensure_runtime_ignored(workspace: Path) -> None:
    result = subprocess.run(
        ["git", "check-ignore", "-q", ".tool-shed/state.sqlite3"],
        cwd=workspace,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise HybridStateError(".tool-shed runtime state is not ignored; add '/.tool-shed/' before initialization")


class WorkspaceLock:
    def __init__(self, path: Path, timeout: float = LOCK_TIMEOUT_SECONDS) -> None:
        self.path = path
        self.timeout = timeout
        self.acquired = False

    def __enter__(self) -> "WorkspaceLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout
        payload = canonical_bytes(
            {"hostname": socket.gethostname(), "pid": os.getpid(), "started_at": now()}
        ) + b"\n"
        while True:
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                self.acquired = True
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise HybridStateError(f"state writer lock remained busy for {self.timeout:g} seconds")
                time.sleep(0.05)

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)
            self.acquired = False


def configure(connection: sqlite3.Connection, *, writable: bool = True) -> None:
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    if writable:
        mode = str(connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]).lower()
        if mode != "wal":
            raise HybridStateError(f"SQLite refused WAL journal mode: {mode}")
    connection.execute("PRAGMA synchronous = FULL")
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA trusted_schema = OFF")


def connect(path: Path, *, writable: bool = True) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=LOCK_TIMEOUT_SECONDS, isolation_level=None)
    try:
        configure(connection, writable=writable)
    except BaseException:
        connection.close()
        raise
    return connection


def table_rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    columns = [str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")]
    order = "id" if "id" in columns else ", ".join(columns)
    return [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY {order}")]


def domain_digest(connection: sqlite3.Connection) -> str:
    # Workspace lineage is deliberately local to one clone/worktree and is not part of the
    # portable semantic digest. Every other accounted domain table must reproduce exactly.
    tables = (table for table in DOMAIN_TABLES if table != "workspace")
    return sha256_bytes(canonical_bytes({table: table_rows(connection, table) for table in tables}))


def meta_row(connection: sqlite3.Connection) -> dict[str, Any]:
    row = connection.execute("SELECT * FROM state_meta WHERE id = 1").fetchone()
    if row is None:
        raise HybridStateError("state database lacks its singleton metadata row")
    return dict(row)


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def audit_connection(workspace: Path, connection: sqlite3.Connection) -> dict[str, Any]:
    findings: list[str] = []
    integrity = [str(row[0]) for row in connection.execute("PRAGMA integrity_check")]
    if integrity != ["ok"]:
        findings.extend(f"integrity: {item}" for item in integrity)
    foreign_keys = [tuple(row) for row in connection.execute("PRAGMA foreign_key_check")]
    if foreign_keys:
        findings.append(f"foreign-key violations: {len(foreign_keys)}")
    application_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
    user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if application_id != APPLICATION_ID:
        findings.append("application identity does not match Tool Shed hybrid state")
    if user_version != SCHEMA_VERSION:
        findings.append(f"unsupported schema version: {user_version}")

    try:
        meta = meta_row(connection)
    except (HybridStateError, sqlite3.DatabaseError) as error:
        findings.append(str(error))
        meta = {}
    identity = load_project_identity(workspace)
    expected_workspace_id = stable_uuid(identity["project_id"], f"workspace:{workspace.resolve()}")
    if meta.get("project_id") != identity["project_id"]:
        findings.append("database project identity does not match this workspace")
    if meta.get("workspace_id") != expected_workspace_id:
        findings.append("database worktree lineage does not match this workspace")
    current_schema_digest = schema_digest(connection)
    if meta.get("schema_trigger_digest") != current_schema_digest:
        findings.append("schema or accounting-trigger digest changed")
    active = int(connection.execute("SELECT COUNT(*) FROM active_operation").fetchone()[0])
    if active:
        findings.append("an incomplete managed operation context remains active")
    current_revision = int(meta.get("current_revision", 0) or 0)
    maximum_change = int(
        connection.execute("SELECT COALESCE(MAX(revision), 0) FROM structural_change").fetchone()[0]
    )
    if maximum_change > current_revision:
        findings.append("structural change revision exceeds current revision")
    mismatched = int(
        connection.execute(
            "SELECT COUNT(*) FROM managed_operation "
            "WHERE status = 'complete' AND expected_writes IS NOT NULL AND expected_writes <> actual_writes"
        ).fetchone()[0]
    )
    if mismatched:
        findings.append(f"managed operation write-count mismatches: {mismatched}")

    observed_digest = domain_digest(connection) if not findings else None
    digest_changed = observed_digest is not None and observed_digest != meta.get("source_digest")
    unmanaged = bool(meta.get("unmanaged_write_detected"))
    if findings:
        classification = "INVALID"
    elif digest_changed and not unmanaged:
        classification = "UNJOURNALED"
        findings.append("domain state changed without complete revision-ledger evidence")
    elif unmanaged:
        classification = "UNMANAGED_REVIEW"
        findings.append("unmanaged writes require an explicit material-change disposition")
    else:
        delta = current_revision - int(meta.get("last_checkpoint_revision", 0) or 0)
        last_checkpoint = connection.execute(
            "SELECT created_at FROM checkpoint_ledger WHERE status = 'complete' "
            "ORDER BY revision DESC, id DESC LIMIT 1"
        ).fetchone()
        age_due = False
        if last_checkpoint:
            parsed = _parse_timestamp(last_checkpoint[0])
            if parsed is not None:
                age_due = (datetime.now(timezone.utc) - parsed).total_seconds() >= CHECKPOINT_AGE_SECONDS
        if bool(meta.get("checkpoint_pending")) and (delta >= CHECKPOINT_REVISION_LIMIT or age_due):
            classification = "CHECKPOINT_DUE"
        elif current_revision > int(meta.get("last_checkpoint_revision", 0) or 0):
            classification = "VALID_DIRTY"
        else:
            classification = "CLEAN"
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-hybrid-state-audit",
        "database": DATABASE_RELATIVE.as_posix(),
        "classification": classification,
        "findings": findings,
        "project_id": meta.get("project_id"),
        "workspace_id": meta.get("workspace_id"),
        "storage_mode": meta.get("storage_mode"),
        "current_revision": current_revision,
        "last_checkpoint_revision": int(meta.get("last_checkpoint_revision", 0) or 0),
        "unmanaged_write_detected": unmanaged,
        "domain_digest": observed_digest,
        "schema_trigger_digest": current_schema_digest,
        "writes_performed": False,
    }


def audit(workspace: Path, path: Path | None = None) -> dict[str, Any]:
    target = path or database_path(workspace)
    if not target.is_file():
        raise HybridStateError(f"state database does not exist: {target.relative_to(workspace)}")
    with contextlib.closing(connect(target)) as connection:
        return audit_connection(workspace, connection)


def _atomic_promote(source: Path, destination: Path) -> None:
    # Windows rejects fsync on a read-only file descriptor.  Open the completed
    # SQLite shadow read/write so the durability barrier is portable.
    with source.open("r+b") as handle:
        os.fsync(handle.fileno())
    os.replace(source, destination)
    try:
        descriptor = os.open(destination.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def initialize(
    workspace: Path,
    *,
    project_binding: str,
    target: Path | None = None,
    storage_mode: str = "shadow",
) -> dict[str, Any]:
    require_project_binding(workspace, project_binding, operation=OPERATION)
    ensure_runtime_ignored(workspace)
    destination = require_path_within(workspace, target or database_path(workspace))
    if destination.exists():
        raise HybridStateError(f"state database already exists: {destination.relative_to(workspace)}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    next_path = destination.with_name(destination.name + ".next")
    if next_path.exists():
        raise HybridStateError(f"stale shadow database requires review: {next_path.relative_to(workspace)}")
    identity = load_project_identity(workspace)
    project_id = identity["project_id"]
    workspace_id = stable_uuid(project_id, f"workspace:{workspace.resolve()}")
    stamp = now()
    with WorkspaceLock(lock_path(workspace)):
        try:
            connection = sqlite3.connect(next_path, isolation_level=None)
            try:
                configure(connection)
                connection.execute("BEGIN IMMEDIATE")
                create_schema(connection, include_triggers=False)
                connection.execute(
                    "INSERT INTO state_meta VALUES (1, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, ?, NULL, ?)",
                    (SCHEMA_VERSION, project_id, workspace_id, storage_mode, EMPTY_SHA256, EMPTY_SHA256),
                )
                connection.execute(
                    "INSERT INTO workspace (id, project_id, name, created_at) VALUES (?, ?, ?, ?)",
                    (workspace_id, project_id, identity["project_name"], stamp),
                )
                connection.execute(
                    "INSERT INTO migration_ledger VALUES (?, 0, 1, ?, ?, NULL, 'complete', ?, ?)",
                    (random_uuid(), migration_digest(), EMPTY_SHA256, stamp, stamp),
                )
                create_triggers(connection)
                digest = domain_digest(connection)
                trigger_digest = schema_digest(connection)
                connection.execute(
                    "UPDATE state_meta SET source_digest = ?, schema_trigger_digest = ? WHERE id = 1",
                    (digest, trigger_digest),
                )
                if list(connection.execute("PRAGMA foreign_key_check")):
                    raise HybridStateError("new state database failed foreign-key validation")
                integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
                if integrity != "ok":
                    raise HybridStateError(f"new state database failed integrity validation: {integrity}")
                connection.commit()
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            finally:
                connection.close()
            _atomic_promote(next_path, destination)
        except BaseException:
            next_path.unlink(missing_ok=True)
            raise
    result = audit(workspace, destination)
    if result["classification"] != "CLEAN":
        raise HybridStateError("new state database did not enter CLEAN state")
    result["writes_performed"] = True
    result["initialized"] = destination.relative_to(workspace).as_posix()
    return result


ManagedCallback = Callable[[sqlite3.Connection, int], Any]


def managed_write(
    workspace: Path,
    *,
    project_binding: str,
    command: str,
    actor: str,
    callback: ManagedCallback,
    expected_writes: int | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    require_project_binding(workspace, project_binding, operation=OPERATION)
    target = path or database_path(workspace)
    with WorkspaceLock(lock_path(workspace)), contextlib.closing(connect(target)) as connection:
        entrance = audit_connection(workspace, connection)
        if entrance["classification"] not in {"CLEAN", "VALID_DIRTY", "CHECKPOINT_DUE"}:
            raise HybridStateError(
                f"managed mutation refused from {entrance['classification']}: "
                + "; ".join(entrance["findings"])
            )
        operation_id = random_uuid()
        stamp = now()
        try:
            connection.execute("BEGIN IMMEDIATE")
            revision = int(connection.execute("SELECT current_revision + 1 FROM state_meta WHERE id = 1").fetchone()[0])
            connection.execute(
                "INSERT INTO managed_operation VALUES (?, ?, ?, ?, ?, NULL, ?, 0, 'active')",
                (operation_id, revision, command, actor, stamp, expected_writes),
            )
            connection.execute(
                "INSERT INTO active_operation VALUES (1, ?, ?)", (operation_id, revision)
            )
            callback_result = callback(connection, revision)
            actual = int(
                connection.execute(
                    "SELECT actual_writes FROM managed_operation WHERE id = ?", (operation_id,)
                ).fetchone()[0]
            )
            if expected_writes is not None and actual != expected_writes:
                raise HybridStateError(
                    f"managed operation expected {expected_writes} accounted writes but observed {actual}"
                )
            connection.execute("DELETE FROM active_operation WHERE id = 1")
            digest = domain_digest(connection)
            committed = now()
            connection.execute(
                "UPDATE managed_operation SET status = 'complete', committed_at = ? WHERE id = ?",
                (committed, operation_id),
            )
            connection.execute(
                "UPDATE state_meta SET current_revision = ?, last_verified_revision = ?, "
                "source_digest = ?, dirty = 1, checkpoint_pending = 1 WHERE id = 1",
                (revision, revision, digest),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        exit_audit = audit_connection(workspace, connection)
        if exit_audit["classification"] not in {"VALID_DIRTY", "CHECKPOINT_DUE"}:
            raise HybridStateError(f"managed mutation left unexpected state: {exit_audit['classification']}")
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "tool-shed-hybrid-state-operation",
            "operation_id": operation_id,
            "revision": revision,
            "actual_writes": actual,
            "result": callback_result,
            "audit": exit_audit,
            "writes_performed": True,
        }


def tracked_state(workspace: Path, relative: str) -> str:
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative],
        cwd=workspace,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if tracked.returncode == 0:
        return "tracked"
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "--", relative],
        cwd=workspace,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return "ignored" if ignored.returncode == 0 else "untracked"


def import_files(
    workspace: Path,
    paths: Sequence[Path],
    *,
    project_binding: str,
    actor: str = "tool-shed",
    assigned_ids: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for supplied in paths:
        path = require_path_within(workspace, supplied if supplied.is_absolute() else workspace / supplied)
        if not path.is_file() or path.is_symlink():
            raise HybridStateError(f"import source must be a regular file: {path}")
        relative = path.relative_to(workspace).as_posix()
        digest = file_sha256(path)
        records.append(
            {
                "path": relative,
                "sha256": digest,
                "tracked_state": tracked_state(workspace, relative),
                "assigned": (assigned_ids or {}).get(relative),
            }
        )

    for record in records:
        assigned = record["assigned"]
        if assigned is None:
            continue
        if set(assigned) != {"artifact_id", "import_id"}:
            raise HybridStateError(f"assigned IDs for {record['path']} must name artifact_id and import_id")
        for key in ("artifact_id", "import_id"):
            try:
                parsed = uuid.UUID(str(assigned[key]))
            except ValueError as error:
                raise HybridStateError(f"assigned {key} for {record['path']} is not a UUID") from error
            if parsed.version != 4 or str(parsed) != assigned[key]:
                raise HybridStateError(f"assigned {key} for {record['path']} is not canonical UUIDv4")

    def apply(connection: sqlite3.Connection, revision: int) -> list[dict[str, str]]:
        stamp = now()
        results: list[dict[str, str]] = []
        for record in records:
            suffix = Path(record["path"]).suffix.lower()
            artifact_type = "markdown" if suffix == ".md" else "json" if suffix == ".json" else "file"
            existing = connection.execute(
                "SELECT id, content_sha256 FROM artifact WHERE current_path = ?", (record["path"],)
            ).fetchone()
            if existing is None:
                artifact_id = record["assigned"]["artifact_id"] if record["assigned"] else random_uuid()
                connection.execute(
                    "INSERT INTO artifact VALUES (?, ?, NULL, ?, 'file', 'imported', ?, ?, ?)",
                    (artifact_id, artifact_type, record["path"], record["sha256"], stamp, stamp),
                )
            else:
                artifact_id = str(existing["id"])
                if record["assigned"] and artifact_id != record["assigned"]["artifact_id"]:
                    raise HybridStateError(f"assigned artifact ID conflicts with existing {record['path']}")
            if existing is not None and existing["content_sha256"] != record["sha256"]:
                connection.execute(
                    "UPDATE artifact SET content_sha256 = ?, updated_at = ? WHERE id = ?",
                    (record["sha256"], stamp, artifact_id),
                )
            prior_import = connection.execute(
                "SELECT id FROM import_record WHERE artifact_id = ? AND source_sha256 = ?",
                (artifact_id, record["sha256"]),
            ).fetchone()
            if prior_import is None:
                import_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM import_record WHERE artifact_id = ?", (artifact_id,)
                    ).fetchone()[0]
                )
                import_id = (
                    record["assigned"]["import_id"]
                    if record["assigned"] and import_count == 0
                    else random_uuid()
                )
                connection.execute(
                    "INSERT INTO import_record VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        import_id,
                        artifact_id,
                        record["path"],
                        record["sha256"],
                        record["tracked_state"],
                        "retained-source-file",
                        "phase-one-v1",
                        "parsed" if suffix in {".md", ".json"} else "unsupported",
                        "{}" if suffix in {".md", ".json"} else json.dumps({"reason": "unsupported file type"}),
                        stamp,
                    ),
                )
            elif (
                record["assigned"]
                and str(prior_import["id"]) != record["assigned"]["import_id"]
                and int(
                    connection.execute(
                        "SELECT COUNT(*) FROM import_record WHERE artifact_id = ?", (artifact_id,)
                    ).fetchone()[0]
                ) == 1
            ):
                raise HybridStateError(f"assigned import ID conflicts with existing {record['path']}")
            results.append({"artifact_id": artifact_id, "path": record["path"], "sha256": record["sha256"]})
        return results

    return managed_write(
        workspace,
        project_binding=project_binding,
        command="import-files",
        actor=actor,
        callback=apply,
    )


def load_assigned_file_ids(workspace: Path, supplied: Path) -> dict[str, dict[str, str]]:
    path = require_path_within(workspace, supplied if supplied.is_absolute() else workspace / supplied)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HybridStateError(f"cannot load assigned-ID manifest: {error}") from error
    identity = load_project_identity(workspace)
    if (
        payload.get("schema_version") != 1
        or payload.get("kind") != "tool-shed-maintainer-assigned-ids"
        or payload.get("project_id") != identity["project_id"]
    ):
        raise HybridStateError("assigned-ID manifest does not match this project or schema")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not all(isinstance(item, dict) for item in sources):
        raise HybridStateError("assigned-ID manifest needs a sources list")
    result: dict[str, dict[str, str]] = {}
    for item in sources:
        relative = item.get("path")
        artifact_id = item.get("artifact_id")
        import_id = item.get("import_id")
        if not isinstance(relative, str) or not relative or relative in result:
            raise HybridStateError("assigned-ID manifest paths must be unique non-empty strings")
        result[relative] = {"artifact_id": str(artifact_id), "import_id": str(import_id)}
    return result


def activate_hybrid_mode(
    workspace: Path,
    *,
    project_binding: str,
    expected_checkpoint_digest: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_checkpoint_digest):
        raise HybridStateError("cutover requires a 64-character checkpoint digest")

    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, str]:
        meta = meta_row(connection)
        if meta["storage_mode"] != "shadow":
            raise HybridStateError(f"cutover requires shadow mode, found {meta['storage_mode']}")
        if meta["checkpoint_digest"] != expected_checkpoint_digest:
            raise HybridStateError("cutover checkpoint digest does not match the exact verified checkpoint")
        connection.execute("UPDATE state_meta SET storage_mode = 'hybrid' WHERE id = 1")
        return {"from": "shadow", "to": "hybrid", "checkpoint_digest": expected_checkpoint_digest}

    return managed_write(
        workspace,
        project_binding=project_binding,
        command="activate-hybrid-mode",
        actor="maintainer-conversion",
        callback=apply,
        expected_writes=0,
    )


def add_relationship(
    workspace: Path,
    *,
    project_binding: str,
    from_artifact_id: str,
    relation_type: str,
    to_artifact_id: str,
    provenance: str,
) -> dict[str, Any]:
    relationship_id = random_uuid()

    def apply(connection: sqlite3.Connection, revision: int) -> dict[str, str]:
        connection.execute(
            "INSERT INTO relationship VALUES (?, ?, ?, ?, ?, ?, NULL)",
            (
                relationship_id,
                from_artifact_id,
                relation_type,
                to_artifact_id,
                provenance,
                revision,
            ),
        )
        return {"relationship_id": relationship_id}

    return managed_write(
        workspace,
        project_binding=project_binding,
        command="add-relationship",
        actor="tool-shed",
        callback=apply,
        expected_writes=1,
    )


def verified_backup(workspace: Path, *, project_binding: str) -> dict[str, Any]:
    require_project_binding(workspace, project_binding, operation=OPERATION)
    source = database_path(workspace)
    backup_root = require_path_within(workspace, workspace / BACKUP_RELATIVE)
    backup_root.mkdir(parents=True, exist_ok=True)
    name = datetime.now(timezone.utc).strftime("state-v1-%Y%m%dT%H%M%SZ.sqlite3")
    destination = backup_root / name
    sequence = 1
    while destination.exists():
        destination = backup_root / f"{Path(name).stem}-{sequence}.sqlite3"
        sequence += 1
    with WorkspaceLock(lock_path(workspace)), contextlib.closing(connect(source)) as live:
        live.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        entrance = audit_connection(workspace, live)
        if entrance["classification"] in {"INVALID", "UNJOURNALED"}:
            raise HybridStateError(f"backup refused from {entrance['classification']}")
        with contextlib.closing(sqlite3.connect(destination)) as backup:
            live.backup(backup)
            backup.commit()
        with contextlib.closing(connect(destination)) as check:
            copied = audit_connection(workspace, check)
        if copied["classification"] != entrance["classification"]:
            destination.unlink(missing_ok=True)
            raise HybridStateError("backup verification did not reproduce the live classification")
    backups = sorted(backup_root.glob("state-v1-*.sqlite3"), key=lambda item: item.stat().st_mtime, reverse=True)
    removed: list[str] = []
    for stale in backups[BACKUP_RETENTION:]:
        stale.unlink()
        removed.append(stale.relative_to(workspace).as_posix())
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-hybrid-state-backup",
        "backup": destination.relative_to(workspace).as_posix(),
        "sha256": file_sha256(destination),
        "classification": copied["classification"],
        "pruned": removed,
        "writes_performed": True,
    }


def source_tree_digest(workspace: Path, *, exclude: Path | None = None) -> str:
    raw = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"],
        cwd=workspace,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if raw.returncode:
        raise HybridStateError(raw.stderr.decode("utf-8", errors="replace").strip() or "cannot inventory source tree")
    digest = hashlib.sha256()
    excluded = exclude.resolve() if exclude else None
    for value in sorted(item for item in raw.stdout.split(b"\0") if item):
        relative = value.decode("utf-8", errors="strict")
        path = require_path_within(workspace, workspace / relative)
        if excluded is not None and path.resolve() == excluded:
            continue
        if path.is_file() and not path.is_symlink():
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(bytes.fromhex(file_sha256(path)))
            digest.update(b"\0")
    return digest.hexdigest()


def checkpoint_digest(payload: dict[str, Any]) -> str:
    material = copy.deepcopy(payload)
    envelope = material.get("envelope", {})
    if isinstance(envelope, dict):
        envelope.pop("digest", None)
    return sha256_bytes(canonical_bytes(material))


def write_checkpoint(
    workspace: Path,
    *,
    project_binding: str,
    output: Path | None = None,
) -> dict[str, Any]:
    require_project_binding(workspace, project_binding, operation=OPERATION)
    target = require_path_within(workspace, output or checkpoint_path(workspace))
    target.parent.mkdir(parents=True, exist_ok=True)
    database = database_path(workspace)
    with WorkspaceLock(lock_path(workspace)), contextlib.closing(connect(database)) as connection:
        entrance = audit_connection(workspace, connection)
        if entrance["classification"] not in {"CLEAN", "VALID_DIRTY", "CHECKPOINT_DUE"}:
            raise HybridStateError(f"checkpoint refused from {entrance['classification']}")
        meta = meta_row(connection)
        revision = int(meta["current_revision"])
        stamp = now()
        source_commit = git_output(workspace, "rev-parse", "HEAD")
        relative = target.relative_to(workspace).as_posix()
        checkpoint_ledger_id = random_uuid()
        export_ledger_id = random_uuid()
        tables = {table: table_rows(connection, table) for table in PORTABLE_TABLES}
        payload: dict[str, Any] = {
            "schema_version": CHECKPOINT_FORMAT,
            "kind": CHECKPOINT_KIND,
            "envelope": {
                "format_version": CHECKPOINT_FORMAT,
                "project_id": meta["project_id"],
                "workspace_id": meta["workspace_id"],
                "storage_mode": meta["storage_mode"],
                "schema_version": SCHEMA_VERSION,
                "database_revision": revision,
                "source_commit": source_commit,
                "source_tree_digest": source_tree_digest(workspace, exclude=target),
                "previous_checkpoint_digest": meta["checkpoint_digest"],
                "checkpoint_path": relative,
                "checkpoint_ledger_id": checkpoint_ledger_id,
                "export_ledger_id": export_ledger_id,
                "created_at": stamp,
                "digest": None,
            },
            "tables": tables,
        }
        digest = checkpoint_digest(payload)
        payload["envelope"]["digest"] = digest
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            reparsed = json.loads(temporary.read_text(encoding="utf-8"))
            if checkpoint_digest(reparsed) != digest:
                raise HybridStateError("checkpoint failed deterministic reparse validation")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO checkpoint_ledger VALUES (?, ?, ?, ?, ?, 'complete', ?)",
                (checkpoint_ledger_id, revision, relative, digest, source_commit, stamp),
            )
            connection.execute(
                "INSERT INTO export_ledger VALUES (?, ?, ?, ?, ?, 'complete', ?)",
                (export_ledger_id, revision, CHECKPOINT_FORMAT, relative, digest, stamp),
            )
            connection.execute(
                "UPDATE state_meta SET last_checkpoint_revision = ?, checkpoint_digest = ?, "
                "dirty = 0, checkpoint_pending = 0 WHERE id = 1",
                (revision, digest),
            )
            _atomic_promote(temporary, target)
            connection.commit()
        except BaseException:
            connection.rollback()
            temporary.unlink(missing_ok=True)
            raise
    return {
        "schema_version": CHECKPOINT_FORMAT,
        "kind": "tool-shed-hybrid-state-checkpoint-result",
        "path": target.relative_to(workspace).as_posix(),
        "digest": digest,
        "revision": revision,
        "writes_performed": True,
    }


def load_checkpoint(workspace: Path, path: Path) -> dict[str, Any]:
    source = require_path_within(workspace, path if path.is_absolute() else workspace / path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HybridStateError(f"cannot load checkpoint: {error}") from error
    if payload.get("schema_version") != CHECKPOINT_FORMAT or payload.get("kind") != CHECKPOINT_KIND:
        raise HybridStateError("unsupported hybrid-state checkpoint")
    envelope = payload.get("envelope")
    tables = payload.get("tables")
    if not isinstance(envelope, dict) or not isinstance(tables, dict):
        raise HybridStateError("checkpoint needs envelope and tables objects")
    digest = envelope.get("digest")
    if not isinstance(digest, str) or digest != checkpoint_digest(payload):
        raise HybridStateError("checkpoint digest is missing or invalid")
    identity = load_project_identity(workspace)
    if envelope.get("project_id") != identity["project_id"]:
        raise HybridStateError("checkpoint belongs to another project")
    if envelope.get("schema_version") != SCHEMA_VERSION:
        raise HybridStateError("checkpoint requires an unsupported database schema")
    for field in ("checkpoint_path", "checkpoint_ledger_id", "export_ledger_id"):
        if not isinstance(envelope.get(field), str) or not envelope[field]:
            raise HybridStateError(f"checkpoint lacks required envelope field: {field}")
    for table in PORTABLE_TABLES:
        if not isinstance(tables.get(table), list):
            raise HybridStateError(f"checkpoint lacks portable table rows: {table}")
    payload["_path"] = source
    return payload


def rebuild_from_checkpoint(
    workspace: Path,
    *,
    project_binding: str,
    checkpoint: Path,
    output: Path,
) -> dict[str, Any]:
    require_project_binding(workspace, project_binding, operation=OPERATION)
    ensure_runtime_ignored(workspace)
    payload = load_checkpoint(workspace, checkpoint)
    destination = require_path_within(workspace, output if output.is_absolute() else workspace / output)
    if destination.exists():
        raise HybridStateError(f"rebuild output already exists: {destination.relative_to(workspace)}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".next")
    if temporary.exists():
        raise HybridStateError(f"stale rebuild shadow requires review: {temporary.relative_to(workspace)}")
    envelope = payload["envelope"]
    tables = payload["tables"]
    identity = load_project_identity(workspace)
    local_workspace_id = stable_uuid(identity["project_id"], f"workspace:{workspace.resolve()}")
    with WorkspaceLock(lock_path(workspace)):
        try:
            connection = sqlite3.connect(temporary, isolation_level=None)
            try:
                configure(connection)
                connection.execute("PRAGMA foreign_keys = OFF")
                connection.execute("BEGIN IMMEDIATE")
                create_schema(connection, include_triggers=False)
                connection.execute(
                    "INSERT INTO state_meta VALUES (1, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?)",
                    (
                        SCHEMA_VERSION,
                        envelope["project_id"],
                        local_workspace_id,
                        envelope["storage_mode"],
                        envelope["database_revision"],
                        envelope["database_revision"],
                        envelope["database_revision"],
                        EMPTY_SHA256,
                        envelope["digest"],
                        EMPTY_SHA256,
                    ),
                )
                for table in PORTABLE_TABLES:
                    if table == "workspace":
                        continue
                    for row in tables[table]:
                        if not isinstance(row, dict) or not row:
                            raise HybridStateError(f"checkpoint {table} row is malformed")
                        columns = list(row)
                        placeholders = ", ".join("?" for _ in columns)
                        connection.execute(
                            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                            tuple(row[column] for column in columns),
                        )
                connection.execute(
                    "INSERT INTO workspace (id, project_id, name, created_at) VALUES (?, ?, ?, ?)",
                    (local_workspace_id, identity["project_id"], identity["project_name"], envelope["created_at"]),
                )
                if not any(item.get("id") == envelope["checkpoint_ledger_id"] for item in tables["checkpoint_ledger"]):
                    connection.execute(
                        "INSERT INTO checkpoint_ledger VALUES (?, ?, ?, ?, ?, 'complete', ?)",
                        (
                            envelope["checkpoint_ledger_id"],
                            envelope["database_revision"],
                            envelope["checkpoint_path"],
                            envelope["digest"],
                            envelope["source_commit"],
                            envelope["created_at"],
                        ),
                    )
                if not any(item.get("id") == envelope["export_ledger_id"] for item in tables["export_ledger"]):
                    connection.execute(
                        "INSERT INTO export_ledger VALUES (?, ?, ?, ?, ?, 'complete', ?)",
                        (
                            envelope["export_ledger_id"],
                            envelope["database_revision"],
                            CHECKPOINT_FORMAT,
                            envelope["checkpoint_path"],
                            envelope["digest"],
                            envelope["created_at"],
                        ),
                    )
                create_triggers(connection)
                digest = domain_digest(connection)
                connection.execute(
                    "UPDATE state_meta SET source_digest = ?, schema_trigger_digest = ? WHERE id = 1",
                    (digest, schema_digest(connection)),
                )
                connection.commit()
                connection.execute("PRAGMA foreign_keys = ON")
                violations = list(connection.execute("PRAGMA foreign_key_check"))
                if violations:
                    raise HybridStateError(f"rebuilt database has {len(violations)} foreign-key violations")
                integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
                if integrity != "ok":
                    raise HybridStateError(f"rebuilt database failed integrity validation: {integrity}")
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            finally:
                connection.close()
            _atomic_promote(temporary, destination)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    rebuilt = audit(workspace, destination)
    if rebuilt["classification"] != "CLEAN":
        destination.unlink(missing_ok=True)
        raise HybridStateError(f"rebuilt database did not enter CLEAN state: {rebuilt['classification']}")
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-hybrid-state-rebuild",
        "output": destination.relative_to(workspace).as_posix(),
        "checkpoint_digest": envelope["digest"],
        "domain_digest": rebuilt["domain_digest"],
        "writes_performed": True,
    }


def legacy_write_check(workspace: Path, field: str, path: Path | None = None) -> dict[str, Any]:
    target = path or database_path(workspace)
    with contextlib.closing(connect(target)) as connection:
        entrance = audit_connection(workspace, connection)
        if entrance["classification"] in {"INVALID", "UNJOURNALED"}:
            raise HybridStateError(f"legacy authority check refused from {entrance['classification']}")
        mode = str(meta_row(connection)["storage_mode"])
    allowed = mode != "hybrid" or field not in DB_AUTHORITY_FIELDS
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-hybrid-state-legacy-authority",
        "field": field,
        "storage_mode": mode,
        "allowed": allowed,
        "reason": "file authority retained" if allowed else "field authority moved to SQLite",
        "writes_performed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)

    initialize_parser = commands.add_parser("init", help="initialize a new shadow-mode database")
    initialize_parser.add_argument("--project-binding", required=True)
    initialize_parser.add_argument("--output")

    audit_parser = commands.add_parser("audit", help="audit state without semantic mutation")
    audit_parser.add_argument("--database")

    import_parser = commands.add_parser("import", help="import retained source-file identity and provenance")
    import_parser.add_argument("--project-binding", required=True)
    import_parser.add_argument("--path", action="append", required=True)
    import_parser.add_argument("--actor", default="tool-shed")
    import_parser.add_argument("--assigned-ids")

    relationship_parser = commands.add_parser("relate", help="add one typed artifact relationship")
    relationship_parser.add_argument("--project-binding", required=True)
    relationship_parser.add_argument("--from-artifact", required=True)
    relationship_parser.add_argument("--relation", required=True)
    relationship_parser.add_argument("--to-artifact", required=True)
    relationship_parser.add_argument("--provenance", required=True)

    backup_parser = commands.add_parser("backup", help="create and verify one rolling SQLite backup")
    backup_parser.add_argument("--project-binding", required=True)

    checkpoint_parser = commands.add_parser("checkpoint", help="write a deterministic tracked logical checkpoint")
    checkpoint_parser.add_argument("--project-binding", required=True)
    checkpoint_parser.add_argument("--output")

    cutover_parser = commands.add_parser("cutover", help="activate hybrid authority from an exact clean shadow checkpoint")
    cutover_parser.add_argument("--project-binding", required=True)
    cutover_parser.add_argument("--expect-checkpoint", required=True)

    rebuild_parser = commands.add_parser("rebuild", help="rebuild a new database from a logical checkpoint")
    rebuild_parser.add_argument("--project-binding", required=True)
    rebuild_parser.add_argument("--checkpoint", required=True)
    rebuild_parser.add_argument("--output", required=True)

    legacy_parser = commands.add_parser("legacy-check", help="check whether a legacy file writer owns one field")
    legacy_parser.add_argument("--field", required=True)
    legacy_parser.add_argument("--database")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        workspace = resolved_workspace(Path(args.workspace))
        if args.command == "init":
            output = Path(args.output) if args.output else None
            result = initialize(
                workspace,
                project_binding=args.project_binding,
                target=(workspace / output) if output and not output.is_absolute() else output,
            )
        elif args.command == "audit":
            supplied = Path(args.database) if args.database else None
            result = audit(workspace, (workspace / supplied) if supplied and not supplied.is_absolute() else supplied)
        elif args.command == "import":
            assignments = (
                load_assigned_file_ids(workspace, Path(args.assigned_ids))
                if args.assigned_ids
                else None
            )
            result = import_files(
                workspace,
                [Path(value) for value in args.path],
                project_binding=args.project_binding,
                actor=args.actor,
                assigned_ids=assignments,
            )
        elif args.command == "relate":
            result = add_relationship(
                workspace,
                project_binding=args.project_binding,
                from_artifact_id=args.from_artifact,
                relation_type=args.relation,
                to_artifact_id=args.to_artifact,
                provenance=args.provenance,
            )
        elif args.command == "backup":
            result = verified_backup(workspace, project_binding=args.project_binding)
        elif args.command == "checkpoint":
            output = Path(args.output) if args.output else None
            result = write_checkpoint(
                workspace,
                project_binding=args.project_binding,
                output=(workspace / output) if output and not output.is_absolute() else output,
            )
        elif args.command == "cutover":
            result = activate_hybrid_mode(
                workspace,
                project_binding=args.project_binding,
                expected_checkpoint_digest=args.expect_checkpoint,
            )
        elif args.command == "rebuild":
            result = rebuild_from_checkpoint(
                workspace,
                project_binding=args.project_binding,
                checkpoint=Path(args.checkpoint),
                output=Path(args.output),
            )
        else:
            supplied = Path(args.database) if args.database else None
            result = legacy_write_check(
                workspace,
                args.field,
                (workspace / supplied) if supplied and not supplied.is_absolute() else supplied,
            )
        print(json.dumps(result, indent=2, sort_keys=True))
        if args.command == "audit" and result["classification"] in {"INVALID", "UNJOURNALED"}:
            return 1
        if args.command == "legacy-check" and not result["allowed"]:
            return 1
        return 0
    except (HybridStateError, ProjectIdentityError, sqlite3.DatabaseError, OSError, ValueError) as error:
        print(f"Hybrid state operation failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
