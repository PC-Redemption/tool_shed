#!/usr/bin/env python3
"""Protected user-local state for passive Tool Shed App Server dogfooding."""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping


PREFERENCE_SCHEMA_VERSION = 2
LEGACY_PREFERENCE_SCHEMA_VERSION = 1
OPERATOR_RUNTIME_TRUST = "operator-runtime"
EVENT_SCHEMA_VERSION = 1
LOCK_TIMEOUT_SECONDS = 10.0
STALE_LOCK_SECONDS = 30.0


class AppServerUserStateError(RuntimeError):
    pass


def default_app_server_preference_path(
    environment: Mapping[str, str] | None = None,
) -> Path:
    values = os.environ if environment is None else environment
    codex_root = values.get("CODEX_HOME")
    base = Path(codex_root).expanduser() if codex_root else Path.home() / ".codex"
    return base / "tool-shed" / "app-server-preference.json"


def default_app_server_event_path(
    environment: Mapping[str, str] | None = None,
) -> Path:
    values = os.environ if environment is None else environment
    codex_root = values.get("CODEX_HOME")
    base = Path(codex_root).expanduser() if codex_root else Path.home() / ".codex"
    return base / "tool-shed" / "app-server-events.jsonl"


def _reject_tool_shed_tree(path: Path, label: str) -> None:
    canonical = Path(__file__).resolve().parents[1]
    try:
        path.relative_to(canonical)
    except ValueError:
        pass
    else:
        raise AppServerUserStateError(f"{label} must remain outside Tool Shed")
    if any(parent.name == "tool_shed" for parent in path.parents):
        raise AppServerUserStateError(
            f"{label} must not be stored in an installed Tool Shed snapshot"
        )
    for parent in (path.parent, *path.parents):
        marker = parent / ".git"
        if marker.is_file() or (marker / "HEAD").is_file():
            raise AppServerUserStateError(f"{label} must not be stored in a repository")


@contextmanager
def _exclusive_lock(path: Path, label: str) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    lock = path.with_suffix(path.suffix + ".lock")
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            try:
                stale = time.time() - lock.stat().st_mtime > STALE_LOCK_SECONDS
            except OSError:
                stale = False
            if stale:
                try:
                    lock.unlink()
                except OSError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise AppServerUserStateError(f"timed out waiting for {label} lock")
            time.sleep(0.02)
    try:
        os.close(descriptor)
        yield
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


@dataclass(frozen=True)
class PreferenceState:
    schema_version: int
    mode: str
    enabled: bool
    source: str
    path: str
    trust_policy: str
    operator_trust: bool
    updated_at: str | None = None
    consented_at: str | None = None
    warning: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class AppServerPreferenceStore:
    """Read and atomically update one fail-safe user-local preference."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        now: Callable[[], float] | None = None,
    ) -> None:
        self.path = (path or default_app_server_preference_path()).expanduser().resolve()
        self.now = now or time.time
        _reject_tool_shed_tree(self.path, "App Server preference")

    def status(self) -> PreferenceState:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return self._default("not-found")
        except OSError:
            return self._default("unreadable-preference")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return self._default("malformed-preference")
        if not isinstance(payload, dict):
            return self._default("malformed-preference")
        schema_version = payload.get("schema_version")
        if schema_version == LEGACY_PREFERENCE_SCHEMA_VERSION:
            return self._legacy_status(payload)
        if schema_version != PREFERENCE_SCHEMA_VERSION:
            return self._default("unsupported-preference-schema")
        mode = payload.get("mode")
        updated_at = payload.get("updated_at")
        trust_policy = payload.get("trust_policy")
        consented_at = payload.get("consented_at")
        expected_trust = OPERATOR_RUNTIME_TRUST if mode == "on" else "off"
        if (
            mode not in {"on", "off"}
            or not isinstance(updated_at, str)
            or trust_policy != expected_trust
            or (mode == "on" and not isinstance(consented_at, str))
            or (mode == "off" and consented_at is not None)
        ):
            return self._default("malformed-preference")
        return PreferenceState(
            schema_version=PREFERENCE_SCHEMA_VERSION,
            mode=str(mode).upper(),
            enabled=mode == "on",
            source="user-local-preference",
            path=str(self.path),
            trust_policy=str(trust_policy),
            operator_trust=mode == "on",
            updated_at=updated_at,
            consented_at=consented_at,
        )

    def _legacy_status(self, payload: dict[str, Any]) -> PreferenceState:
        mode = payload.get("mode")
        updated_at = payload.get("updated_at")
        if mode not in {"on", "off"} or not isinstance(updated_at, str):
            return self._default("malformed-preference")
        enabled = mode == "on"
        return PreferenceState(
            schema_version=LEGACY_PREFERENCE_SCHEMA_VERSION,
            mode=str(mode).upper(),
            enabled=enabled,
            source="legacy-user-local-preference",
            path=str(self.path),
            trust_policy="legacy-read-only" if enabled else "off",
            operator_trust=False,
            updated_at=updated_at,
            warning="legacy-on-camp-trust-not-confirmed" if enabled else None,
        )

    def set(self, enabled: bool) -> PreferenceState:
        epoch = float(self.now())
        payload = {
            "schema_version": PREFERENCE_SCHEMA_VERSION,
            "mode": "on" if enabled else "off",
            "trust_policy": OPERATOR_RUNTIME_TRUST if enabled else "off",
            "updated_at": datetime.fromtimestamp(epoch, tz=UTC).isoformat(),
        }
        if enabled:
            payload["consented_at"] = payload["updated_at"]
        with self._locked():
            self._atomic_write(payload)
        return self.status()

    def _default(self, warning: str) -> PreferenceState:
        return PreferenceState(
            schema_version=PREFERENCE_SCHEMA_VERSION,
            mode="OFF",
            enabled=False,
            source="default-off",
            path=str(self.path),
            trust_policy="off",
            operator_trust=False,
            warning=warning,
        )

    @contextmanager
    def _locked(self) -> Iterator[None]:
        with _exclusive_lock(self.path, "App Server preference"):
            yield

    def _atomic_write(self, payload: dict[str, Any]) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.chmod(temporary, 0o600)
            except OSError:
                pass
            os.replace(temporary, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


class AppServerEventStore:
    """Append sanitized operational events without retaining request content."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        now: Callable[[], float] | None = None,
    ) -> None:
        self.path = (path or default_app_server_event_path()).expanduser().resolve()
        self.now = now or time.time
        _reject_tool_shed_tree(self.path, "App Server event log")

    @staticmethod
    def _token(value: str, fallback: str) -> str:
        return value if re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", value) else fallback

    def record(
        self,
        *,
        command: str,
        outcome: str,
        category: str,
        mutation_state: str,
        backend: str,
        preference_mode: str,
        strict_request: bool,
    ) -> dict[str, Any]:
        epoch = float(self.now())
        event = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "recorded_at": datetime.fromtimestamp(epoch, tz=UTC).isoformat(),
            "command": self._token(command, "unknown"),
            "outcome": self._token(outcome, "unknown"),
            "category": self._token(category, "unknown"),
            "mutation_state": self._token(mutation_state, "unknown"),
            "backend": self._token(backend, "unknown"),
            "preference_mode": preference_mode if preference_mode in {"ON", "OFF"} else "UNKNOWN",
            "strict_request": bool(strict_request),
        }
        line = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
        with _exclusive_lock(self.path, "App Server event log"):
            descriptor = os.open(self.path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "a", encoding="utf-8", newline="\n") as stream:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        return event


def record_app_server_event_best_effort(
    *,
    path: Path | None = None,
    **fields: Any,
) -> bool:
    try:
        AppServerEventStore(path).record(**fields)
    except (AppServerUserStateError, OSError, TypeError, ValueError):
        return False
    return True
