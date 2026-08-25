#!/usr/bin/env python3
"""Protected local state for observable, retry-safe snapshot upgrades."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO


SCHEMA_VERSION = 1
LOCK_WAIT_SECONDS = 5.0
MALFORMED_LOCK_GRACE_SECONDS = 300.0
MAX_VALIDATION_RECORDS = 64
ISSUE_CODE = re.compile(r"^TSU-[0-9]{3}$")

ISSUE_CODE_REGISTRY: dict[str, dict[str, str]] = {
    "TSU-000": {
        "name": "no-issue",
        "summary": "The snapshot operation completed without a reportable failure.",
    },
    "TSU-101": {
        "name": "concurrent-upgrade",
        "summary": "Another upgrade already owns the workspace transaction lock.",
    },
    "TSU-201": {
        "name": "timeout",
        "summary": "A bounded upgrade phase exceeded its configured timeout.",
    },
    "TSU-301": {
        "name": "network",
        "summary": "Release acquisition failed at a bounded network operation.",
    },
    "TSU-401": {
        "name": "integrity",
        "summary": "Release provenance, manifest, or content integrity validation failed.",
    },
    "TSU-501": {
        "name": "validation",
        "summary": "Release or post-install validation failed.",
    },
    "TSU-601": {
        "name": "permission",
        "summary": "The updater lacked permission for a required local operation.",
    },
    "TSU-701": {
        "name": "filesystem",
        "summary": "A local filesystem operation failed.",
    },
    "TSU-801": {
        "name": "unknown",
        "summary": "The updater failed without a more specific sanitized classification.",
    },
    "TSU-901": {
        "name": "rollback-incomplete",
        "summary": "The previous snapshot was not verified as restored after failure.",
    },
}

ERROR_CLASS_ISSUE_CODES = {
    "concurrent-upgrade": "TSU-101",
    "timeout": "TSU-201",
    "network": "TSU-301",
    "integrity": "TSU-401",
    "validation": "TSU-501",
    "permission": "TSU-601",
    "filesystem": "TSU-701",
    "unknown": "TSU-801",
}


class SnapshotStateError(RuntimeError):
    pass


class ConcurrentUpgradeError(SnapshotStateError):
    pass


def issue_code_for(
    *,
    state: str,
    error_class: str | None,
    rollback_outcome: str | None,
) -> str:
    if state in {"installed", "current", "prune-preview"}:
        return "TSU-000"
    if rollback_outcome == "not-restored":
        return "TSU-901"
    return ERROR_CLASS_ISSUE_CODES.get(error_class or "unknown", "TSU-801")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def state_root(*, create: bool = True) -> Path:
    override = os.environ.get("TOOL_SHED_STATE_ROOT")
    if override:
        root = Path(override).expanduser()
    else:
        codex_home = os.environ.get("CODEX_HOME")
        codex_root = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
        root = codex_root / "tool-shed"
    root = root.absolute()
    if root.exists():
        if root.is_symlink() or not root.is_dir():
            raise SnapshotStateError(f"Tool Shed state root must be a real directory: {root}")
    elif create:
        root.mkdir(parents=True, exist_ok=True)
    if create and os.name != "nt":
        os.chmod(root, 0o700)
    return root


def _ensure_directory(path: Path) -> None:
    if path.exists() and (path.is_symlink() or not path.is_dir()):
        raise SnapshotStateError(f"Tool Shed state path must be a real directory: {path}")
    path.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(path, 0o700)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    _ensure_directory(path.parent)
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise SnapshotStateError(f"Tool Shed state file must be a regular file: {path}")
    descriptor, staged_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    staged = Path(staged_name)
    try:
        if os.name != "nt":
            os.chmod(staged, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        staged.replace(path)
        if os.name != "nt":
            os.chmod(path, 0o600)
    except BaseException:
        staged.unlink(missing_ok=True)
        raise


def _process_alive(pid: object) -> bool:
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class _ExclusiveFileLock:
    def __init__(self, path: Path, payload: dict[str, Any], *, wait: bool) -> None:
        self.path = path
        self.payload = payload
        self.wait = wait
        self.acquired = False

    def _stale_snapshot(self) -> tuple[bytes, int, int] | None:
        try:
            raw = self.path.read_bytes()
            stat = self.path.stat()
            existing = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            try:
                stat = self.path.stat()
                raw = self.path.read_bytes()
                stale = time.time() - stat.st_mtime > MALFORMED_LOCK_GRACE_SECONDS
            except OSError:
                return b"", 0, 0
            return (raw, stat.st_mtime_ns, stat.st_size) if stale else None
        return (
            (raw, stat.st_mtime_ns, stat.st_size)
            if not _process_alive(existing.get("pid"))
            else None
        )

    def acquire(self) -> None:
        _ensure_directory(self.path.parent)
        deadline = time.monotonic() + (LOCK_WAIT_SECONDS if self.wait else 0.0)
        while True:
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                stale = self._stale_snapshot()
                if stale is not None:
                    try:
                        current_stat = self.path.stat()
                        current = (
                            self.path.read_bytes(),
                            current_stat.st_mtime_ns,
                            current_stat.st_size,
                        )
                        if current == stale:
                            self.path.unlink()
                    except (FileNotFoundError, OSError):
                        pass
                    continue
                if self.wait and time.monotonic() < deadline:
                    time.sleep(0.05)
                    continue
                raise ConcurrentUpgradeError(
                    "another Tool Shed snapshot upgrade is already active"
                )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                    json.dump(self.payload, handle, sort_keys=True)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                if os.name != "nt":
                    os.chmod(self.path, 0o600)
                self.acquired = True
                return
            except BaseException:
                self.path.unlink(missing_ok=True)
                raise

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            existing = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        if existing.get("owner") == self.payload.get("owner"):
            self.path.unlink(missing_ok=True)
        self.acquired = False

    def __enter__(self) -> _ExclusiveFileLock:
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()


class WorkspaceTransactionLock:
    def __init__(self, workspace: Path, transaction_id: str) -> None:
        workspace_hash = hashlib.sha256(str(workspace.resolve()).encode("utf-8")).hexdigest()
        path = state_root() / "snapshot-upgrade-locks" / f"{workspace_hash}.json"
        self._lock = _ExclusiveFileLock(
            path,
            {
                "schema_version": SCHEMA_VERSION,
                "kind": "tool-shed-snapshot-upgrade-lock",
                "owner": transaction_id,
                "pid": os.getpid(),
                "created_at": utc_now(),
                "workspace_sha256": workspace_hash,
            },
            wait=False,
        )

    def acquire(self) -> None:
        self._lock.acquire()

    def release(self) -> None:
        self._lock.release()


def validation_identity(*, release_commit: str, validator_sha256: str) -> dict[str, str]:
    return {
        "release_commit": release_commit,
        "validator_sha256": validator_sha256,
        "platform": platform.system().lower(),
        "architecture": platform.machine().lower(),
        "python": f"{platform.python_implementation()}-{platform.python_version()}",
    }


class ValidationCache:
    def __init__(self) -> None:
        self.path = state_root() / "snapshot-validation-cache.json"
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    @staticmethod
    def _key(identity: dict[str, str]) -> str:
        encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": SCHEMA_VERSION, "records": {}}
        if self.path.is_symlink() or not self.path.is_file():
            return {"schema_version": SCHEMA_VERSION, "records": {}}
        if os.name != "nt" and self.path.stat().st_mode & 0o077:
            return {"schema_version": SCHEMA_VERSION, "records": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"schema_version": SCHEMA_VERSION, "records": {}}
        if payload.get("schema_version") != SCHEMA_VERSION or not isinstance(payload.get("records"), dict):
            return {"schema_version": SCHEMA_VERSION, "records": {}}
        return payload

    def lookup(self, identity: dict[str, str]) -> bool:
        payload = self._load()
        record = payload["records"].get(self._key(identity))
        return bool(
            isinstance(record, dict)
            and record.get("identity") == identity
            and record.get("outcome") == "passed"
        )

    def store_success(self, identity: dict[str, str], *, mode: str) -> None:
        lock = _ExclusiveFileLock(
            self.lock_path,
            {
                "schema_version": SCHEMA_VERSION,
                "kind": "tool-shed-validation-cache-lock",
                "owner": f"{os.getpid()}-{time.time_ns()}",
                "pid": os.getpid(),
                "created_at": utc_now(),
            },
            wait=True,
        )
        with lock:
            payload = self._load()
            records = payload["records"]
            records[self._key(identity)] = {
                "identity": identity,
                "mode": mode,
                "outcome": "passed",
                "recorded_at": utc_now(),
            }
            ordered = sorted(
                records.items(),
                key=lambda item: str(item[1].get("recorded_at", "")),
                reverse=True,
            )[:MAX_VALIDATION_RECORDS]
            payload["records"] = dict(ordered)
            _atomic_json(self.path, payload)


class TransactionRecorder:
    def __init__(self, transaction_id: str, *, updater: dict[str, Any] | None = None) -> None:
        self.transaction_id = transaction_id
        self.updater = dict(updater) if updater else None
        self.path = state_root() / "snapshot-upgrade-transactions" / f"{transaction_id}.json"
        self.started_wall = utc_now()
        self.started_monotonic = time.monotonic()
        self.phase_started = self.started_monotonic
        self.current_phase = "initialization"
        self.durations: dict[str, float] = {}
        self._finished = False
        self._write("running")

    def phase(self, name: str) -> None:
        now = time.monotonic()
        self.durations[self.current_phase] = self.durations.get(self.current_phase, 0.0) + (
            now - self.phase_started
        )
        self.current_phase = name
        self.phase_started = now

    def _payload(
        self,
        state: str,
        *,
        failed_stage: str | None = None,
        error_class: str | None = None,
        rollback_outcome: str | None = None,
        metadata: dict[str, Any] | None = None,
        issue_code: str | None = None,
    ) -> dict[str, Any]:
        now = time.monotonic()
        durations = dict(self.durations)
        durations[self.current_phase] = durations.get(self.current_phase, 0.0) + (
            now - self.phase_started
        )
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "kind": "tool-shed-snapshot-upgrade-transaction",
            "transaction_id": self.transaction_id,
            "state": state,
            "started_at": self.started_wall,
            "updated_at": utc_now(),
            "elapsed_seconds": round(now - self.started_monotonic, 3),
            "stage_durations_seconds": {
                key: round(value, 3) for key, value in sorted(durations.items())
            },
            "platform": platform.system().lower(),
            "architecture": platform.machine().lower(),
            "python": f"{platform.python_implementation()}-{platform.python_version()}",
        }
        if failed_stage:
            payload["failed_stage"] = failed_stage
        if error_class:
            payload["error_class"] = error_class
        if rollback_outcome:
            payload["rollback_outcome"] = rollback_outcome
        if issue_code:
            if issue_code not in ISSUE_CODE_REGISTRY:
                raise SnapshotStateError(f"unknown snapshot upgrade issue code: {issue_code}")
            payload["issue_code"] = issue_code
        if self.updater:
            payload["updater"] = self.updater
        if metadata:
            payload["release"] = metadata
        return payload

    def _write(self, state: str, **kwargs: Any) -> None:
        _atomic_json(self.path, self._payload(state, **kwargs))

    def finish(self, state: str, **kwargs: Any) -> None:
        if self._finished:
            return
        kwargs.setdefault(
            "issue_code",
            issue_code_for(
                state=state,
                error_class=kwargs.get("error_class"),
                rollback_outcome=kwargs.get("rollback_outcome"),
            ),
        )
        self._write(state, **kwargs)
        self._finished = True


def classify_error(error: BaseException, *, stage: str | None = None) -> str:
    if isinstance(error, ConcurrentUpgradeError):
        return "concurrent-upgrade"
    text = str(error).lower()
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if "permission" in text or "access is denied" in text:
        return "permission"
    if "validation" in text or "validator" in text:
        return "validation"
    if "manifest" in text or "hash" in text or "integrity" in text or "provenance" in text:
        return "integrity"
    if "clone" in text or "fetch" in text or "network" in text:
        return "network"
    if isinstance(error, OSError):
        return "filesystem"
    if stage in {"release-validation", "post-install-validation"}:
        return "validation"
    return "unknown"


class ProgressHeartbeat:
    def __init__(self, stream: TextIO, interval_seconds: float = 20.0) -> None:
        self.stream = stream
        self.interval_seconds = interval_seconds
        self.phase_name = "initialization"
        self.phase_started = time.monotonic()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = threading.Thread(
            target=self._loop,
            name="tool-shed-upgrade-heartbeat",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def update(self, phase: str) -> None:
        with self._lock:
            self.phase_name = phase
            self.phase_started = time.monotonic()

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            with self._lock:
                phase = self.phase_name
                elapsed = int(time.monotonic() - self.phase_started)
            print(
                f"Tool Shed update: still working: {phase} ({elapsed}s in phase)",
                file=self.stream,
                flush=True,
            )

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=max(1.0, self.interval_seconds + 1.0))
