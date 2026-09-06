#!/usr/bin/env python3
"""Protected user-local state for passive Tool Shed App Server dogfooding."""

from __future__ import annotations

import json
import hashlib
import os
import re
import tempfile
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping


PREFERENCE_SCHEMA_VERSION = 2
LEGACY_PREFERENCE_SCHEMA_VERSION = 1
OPERATOR_RUNTIME_TRUST = "operator-runtime"
EVENT_SCHEMA_VERSION = 3
DISPATCH_LEASE_SECONDS = 300
OWNER_PROFILE_SCHEMA_VERSION = 1
LOCK_TIMEOUT_SECONDS = 10.0
STALE_LOCK_SECONDS = 30.0


class AppServerUserStateError(RuntimeError):
    pass


def default_app_server_preference_path(
    environment: Mapping[str, str] | None = None,
) -> Path:
    values = os.environ if environment is None else environment
    state_root = values.get("TOOL_SHED_STATE_ROOT")
    if state_root:
        return Path(state_root).expanduser() / "tool-shed" / "app-server-preference.json"
    codex_root = values.get("CODEX_HOME")
    base = Path(codex_root).expanduser() if codex_root else Path.home() / ".codex"
    return base / "tool-shed" / "app-server-preference.json"


def default_app_server_event_path(
    environment: Mapping[str, str] | None = None,
) -> Path:
    values = os.environ if environment is None else environment
    state_root = values.get("TOOL_SHED_STATE_ROOT")
    if state_root:
        return Path(state_root).expanduser() / "tool-shed" / "app-server-events.jsonl"
    codex_root = values.get("CODEX_HOME")
    base = Path(codex_root).expanduser() if codex_root else Path.home() / ".codex"
    return base / "tool-shed" / "app-server-events.jsonl"


def default_app_server_profile_path(
    environment: Mapping[str, str] | None = None,
) -> Path:
    """Return the explicit recovery copy path, outside Codex home by default."""

    values = os.environ if environment is None else environment
    state_root = values.get("TOOL_SHED_STATE_ROOT")
    if state_root:
        return Path(state_root).expanduser() / "tool-shed-profile" / "app-server-owner-profile.json"
    config_root = values.get("XDG_CONFIG_HOME")
    base = Path(config_root).expanduser() if config_root else Path.home() / ".config"
    return base / "tool-shed" / "app-server-owner-profile.json"


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


class AppServerOwnerProfileStore:
    """Protected recovery evidence that never acts as live runtime consent."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = (path or default_app_server_profile_path()).expanduser().resolve()
        _reject_tool_shed_tree(self.path, "App Server owner profile")

    def status(self) -> PreferenceState:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return self._default("not-found")
        except (OSError, json.JSONDecodeError):
            return self._default("malformed-owner-profile")
        if not isinstance(payload, dict) or payload.get("schema_version") != OWNER_PROFILE_SCHEMA_VERSION:
            return self._default("unsupported-owner-profile-schema")
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
            return self._default("malformed-owner-profile")
        return PreferenceState(
            schema_version=OWNER_PROFILE_SCHEMA_VERSION,
            mode=str(mode).upper(),
            enabled=mode == "on",
            source="owner-profile-recovery-evidence",
            path=str(self.path),
            trust_policy=str(trust_policy),
            operator_trust=False,
            updated_at=updated_at,
            consented_at=consented_at,
            warning="explicit-restore-required",
        )

    def save(self, preference: PreferenceState) -> PreferenceState:
        if (
            preference.schema_version != PREFERENCE_SCHEMA_VERSION
            or preference.mode not in {"ON", "OFF"}
            or preference.source != "user-local-preference"
            or not isinstance(preference.updated_at, str)
        ):
            raise AppServerUserStateError("only a current explicit preference can update the owner profile")
        payload: dict[str, Any] = {
            "schema_version": OWNER_PROFILE_SCHEMA_VERSION,
            "kind": "app-server-owner-profile-recovery",
            "mode": preference.mode.lower(),
            "trust_policy": OPERATOR_RUNTIME_TRUST if preference.enabled else "off",
            "updated_at": preference.updated_at,
        }
        if preference.enabled:
            payload["consented_at"] = preference.consented_at
        with _exclusive_lock(self.path, "App Server owner profile"):
            self._atomic_write(payload)
        return self.status()

    def restore(self, preference_store: AppServerPreferenceStore) -> PreferenceState:
        profile = self.status()
        if profile.warning != "explicit-restore-required":
            raise AppServerUserStateError("a valid owner profile is required for explicit restore")
        restored = preference_store.set(profile.enabled)
        self.save(restored)
        return restored

    def _default(self, warning: str) -> PreferenceState:
        return PreferenceState(
            schema_version=OWNER_PROFILE_SCHEMA_VERSION,
            mode="UNAVAILABLE",
            enabled=False,
            source="owner-profile-recovery-evidence",
            path=str(self.path),
            trust_policy="recovery-only",
            operator_trust=False,
            warning=warning,
        )

    def _atomic_write(self, payload: dict[str, Any]) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
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
        source: str = "legacy-unknown",
        event_type: str = "execution",
        role: str | None = None,
        correlation_id: str | None = None,
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
            "source": self._token(source, "unknown"),
            "event_type": self._token(event_type, "unknown"),
            "role": self._token(role or command, "unknown"),
            "correlation_id": self._token(correlation_id or uuid.uuid4().hex, "unknown"),
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

    def report(self, *, hours: float = 24.0) -> dict[str, Any]:
        if hours <= 0 or hours > 24 * 365:
            raise AppServerUserStateError("report hours must be greater than zero and at most 8760")
        cutoff = float(self.now()) - hours * 3600
        counters: dict[str, Counter[str]] = {
            key: Counter() for key in ("source", "event_type", "role", "outcome", "category")
        }
        included = legacy = malformed = malformed_current = 0
        included_events: list[dict[str, Any]] = []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            lines = []
        except OSError as error:
            raise AppServerUserStateError(f"cannot read App Server event log: {error}") from error
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not isinstance(event, dict):
                malformed += 1
                continue
            if event.get("schema_version") != EVENT_SCHEMA_VERSION:
                legacy += 1
                continue
            try:
                recorded = datetime.fromisoformat(str(event["recorded_at"]).replace("Z", "+00:00")).timestamp()
            except (KeyError, TypeError, ValueError):
                malformed += 1
                malformed_current += 1
                continue
            if recorded < cutoff:
                continue
            included += 1
            included_events.append(event)
            for key, counter in counters.items():
                counter[str(event.get(key, "unknown"))] += 1
        outcomes = counters["outcome"]
        types = counters["event_type"]
        successes = [
            str(event["recorded_at"])
            for event in included_events
            if event.get("outcome") == "completed"
        ]
        failures = [
            event for event in included_events if event.get("outcome") == "failed"
        ]
        grouped_failures: dict[tuple[str, str], dict[str, Any]] = {}
        for event in failures:
            raw_category = str(event.get("category", "unknown"))
            lowered = raw_category.lower()
            category = next(
                (
                    candidate
                    for candidate, markers in (
                        ("authentication", ("auth", "credential", "login")),
                        ("startup", ("startup", "executable", "spawn")),
                        ("model", ("model",)),
                        ("transport", ("transport", "network", "timeout", "protocol")),
                        ("qualification", ("qualif", "version", "denylist")),
                        ("budget", ("budget", "limit")),
                        ("unsafe-boundary", ("unsafe", "mutation", "boundary", "journal")),
                    )
                    if any(marker in lowered for marker in markers)
                ),
                "unknown",
            )
            role = str(event.get("role", "unknown"))
            key = (category, raw_category + ":" + role)
            recorded_at = str(event["recorded_at"])
            group = grouped_failures.setdefault(
                key,
                {
                    "signature": hashlib.sha256(key[1].encode()).hexdigest()[:32],
                    "category": category,
                    "count": 0,
                    "first_seen": recorded_at,
                    "last_seen": recorded_at,
                },
            )
            group["count"] += 1
            group["first_seen"] = min(group["first_seen"], recorded_at)
            group["last_seen"] = max(group["last_seen"], recorded_at)
        dispatch = self._dispatch_report(
            included_events,
            now_epoch=float(self.now()),
            malformed_current=malformed_current,
        )
        return {
            "schema_version": 1,
            "kind": "tool-shed-app-server-opportunity-report",
            "window_hours": hours,
            "included_runtime_events": included,
            "excluded_legacy_events": legacy,
            "excluded_malformed_events": malformed,
            "opportunities": types["opportunity"],
            "app_server_selections": outcomes["selected"],
            "execution_attempts": outcomes["attempted"],
            "completions": outcomes["completed"],
            "gui_fallbacks": outcomes["gui_fallback"],
            "reconciliations": outcomes["gui_reconciliation"],
            "skipped_opportunities": outcomes["gui"],
            "dispatch_debt": dispatch["debt_count"],
            "dispatch_ready": dispatch["debt_count"] == 0,
            "dispatch_lifecycles": dispatch,
            "counts": {key: dict(sorted(counter.items())) for key, counter in counters.items()},
            "last_success": max(successes) if successes else None,
            "last_failure": max((str(event["recorded_at"]) for event in failures), default=None),
            "failure_groups": sorted(
                grouped_failures.values(), key=lambda item: (-item["count"], item["signature"])
            )[:20],
            "usage": {
                "input_tokens": None,
                "output_tokens": None,
                "duration_seconds": None,
                "coverage": "not-recorded-by-opportunity-events",
            },
            "privacy": "content-free-controlled-fields-only",
        }

    @staticmethod
    def _dispatch_report(
        events: list[dict[str, Any]],
        *,
        now_epoch: float,
        malformed_current: int,
    ) -> dict[str, Any]:
        terminal_outcomes = AppServerDispatchLifecycle.TERMINAL_OUTCOMES
        lifecycle_events = [
            event
            for event in events
            if event.get("outcome") in {"selected", "attempted"}
            or (
                event.get("event_type") == "terminal"
                and event.get("outcome") in terminal_outcomes
            )
        ]
        grouped: dict[str, list[dict[str, Any]]] = {}
        for event in lifecycle_events:
            correlation = str(event.get("correlation_id", "unknown"))
            grouped.setdefault(correlation, []).append(event)

        findings: list[dict[str, Any]] = []
        completed = pending = expired = 0
        command_roles = {
            "plan": "planning",
            "verify": "verification",
            "camp-run": "camp_execution",
            "next": "camp_execution",
        }
        for correlation, chain in sorted(grouped.items()):
            codes: set[str] = set()
            selections = [event for event in chain if event.get("outcome") == "selected"]
            attempts = [event for event in chain if event.get("outcome") == "attempted"]
            terminals = [
                event
                for event in chain
                if event.get("event_type") == "terminal"
                and event.get("outcome") in terminal_outcomes
            ]
            pre_mutation_recovery = (
                len(terminals) == 1
                and not attempts
                and terminals[0].get("category") == "process_loss_pre_mutation"
                and terminals[0].get("mutation_state") == "none"
                and terminals[0].get("outcome") in {"gui_fallback", "failed"}
            )
            if len(selections) != 1:
                codes.add("missing_selection" if not selections else "duplicate_selection")
            if len(attempts) != 1 and not pre_mutation_recovery:
                codes.add("missing_attempt" if not attempts else "duplicate_attempt")
            if len(terminals) != 1:
                codes.add("missing_terminal" if not terminals else "duplicate_terminal")

            anchor = selections[0] if selections else chain[0]
            command = str(anchor.get("command", "unknown"))
            role = str(anchor.get("role", "unknown"))
            if command_roles.get(command) != role:
                codes.add("role_command_mismatch")
            identity_fields = (
                "command",
                "role",
                "preference_mode",
                "strict_request",
                "source",
            )
            if any(
                any(event.get(field) != anchor.get(field) for field in identity_fields)
                for event in chain[1:]
            ):
                codes.add("metadata_mismatch")
            expected_sequence = ["selected"]
            if not pre_mutation_recovery:
                expected_sequence.append("attempted")
            if len(terminals) == 1:
                expected_sequence.append(str(terminals[0].get("outcome")))
            if [event.get("outcome") for event in chain] != expected_sequence:
                codes.add("sequence_invalid")

            if len(terminals) == 1:
                terminal = terminals[0]
                outcome = terminal.get("outcome")
                backend = terminal.get("backend")
                mutation = terminal.get("mutation_state")
                strict = bool(anchor.get("strict_request"))
                valid_terminal = (
                    outcome == "completed"
                    and backend == "app_server"
                    and mutation in {"none", "verified"}
                ) or (
                    outcome == "gui_fallback"
                    and not strict
                    and backend == "gui"
                    and mutation == "none"
                ) or (
                    outcome == "reconciliation_required"
                    and backend == "gui"
                    and mutation in {"possible", "unknown"}
                ) or (
                    outcome == "failed"
                    and strict
                    and backend == "app_server"
                    and mutation == "none"
                )
                if not valid_terminal:
                    codes.add("terminal_contract_invalid")

            try:
                anchor_epoch = datetime.fromisoformat(
                    str(anchor["recorded_at"]).replace("Z", "+00:00")
                ).timestamp()
            except (KeyError, TypeError, ValueError):
                anchor_epoch = now_epoch
                codes.add("malformed_event")
            age_seconds = max(0, int(now_epoch - anchor_epoch))
            incomplete = bool(
                {"missing_attempt", "missing_terminal"}.intersection(codes)
            )
            pending_shape = (
                len(selections) == 1
                and not terminals
                and len(attempts) <= 1
                and codes <= {"missing_attempt", "missing_terminal", "sequence_invalid"}
            )
            if not codes:
                status = "complete"
                completed += 1
            elif incomplete and pending_shape and age_seconds <= DISPATCH_LEASE_SECONDS:
                status = "pending"
                pending += 1
            elif incomplete and pending_shape:
                status = "expired"
                expired += 1
                codes.add("lease_expired")
            else:
                status = "invalid"
            findings.append(
                {
                    "correlation_id": correlation,
                    "status": status,
                    "codes": sorted(codes),
                    "command": command,
                    "role": role,
                    "age_seconds": age_seconds,
                }
            )

        debt = [item for item in findings if item["status"] != "complete"]
        if malformed_current:
            debt.append(
                {
                    "correlation_id": "malformed",
                    "status": "invalid",
                    "codes": ["malformed_current_event"],
                    "command": "unknown",
                    "role": "unknown",
                    "age_seconds": 0,
                }
            )
        return {
            "schema_version": 1,
            "lease_seconds": DISPATCH_LEASE_SECONDS,
            "observed_count": len(grouped),
            "complete_count": completed,
            "pending_count": pending,
            "expired_count": expired,
            "invalid_count": sum(item["status"] == "invalid" for item in debt),
            "malformed_current_events": malformed_current,
            "debt_count": len(debt),
            "findings": debt[:50],
            "truncated": len(debt) > 50,
        }

    def correlation_events(self, correlation_id: str) -> list[dict[str, Any]]:
        token = self._token(correlation_id, "unknown")
        if token == "unknown":
            raise AppServerUserStateError("dispatch correlation ID is invalid")
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        except OSError as error:
            raise AppServerUserStateError(
                f"cannot read App Server event log: {error}"
            ) from error
        events: list[dict[str, Any]] = []
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                isinstance(event, dict)
                and event.get("schema_version") == EVENT_SCHEMA_VERSION
                and event.get("correlation_id") == token
            ):
                events.append(event)
        return events


class AppServerDispatchLifecycle:
    """Record one in-process eligible dispatch under one correlation identity."""

    TERMINAL_OUTCOMES = frozenset(
        {"completed", "gui_fallback", "reconciliation_required", "failed"}
    )

    def __init__(
        self,
        *,
        command: str,
        role: str,
        preference_mode: str,
        strict_request: bool,
        source: str,
        path: Path | None = None,
        correlation_id: str | None = None,
    ) -> None:
        self.store = AppServerEventStore(path)
        self.command = command
        self.role = role
        self.preference_mode = preference_mode
        self.strict_request = strict_request
        self.source = source
        self.correlation_id = AppServerEventStore._token(
            correlation_id or uuid.uuid4().hex, "unknown"
        )
        if self.correlation_id == "unknown":
            raise AppServerUserStateError("dispatch correlation ID is invalid")
        self._selected = False
        self._attempted = False
        self._terminal = False

    @property
    def selection_recorded(self) -> bool:
        return self._selected

    @property
    def attempt_recorded(self) -> bool:
        return self._attempted

    @property
    def terminal_recorded(self) -> bool:
        return self._terminal

    @classmethod
    def resume(
        cls,
        correlation_id: str,
        *,
        path: Path | None = None,
    ) -> AppServerDispatchLifecycle:
        store = AppServerEventStore(path)
        events = store.correlation_events(correlation_id)
        selections = [event for event in events if event.get("outcome") == "selected"]
        attempts = [event for event in events if event.get("outcome") == "attempted"]
        terminals = [
            event for event in events if event.get("outcome") in cls.TERMINAL_OUTCOMES
        ]
        if len(selections) != 1:
            raise AppServerUserStateError(
                "dispatch correlation must resolve exactly one eligible selection"
            )
        if attempts or terminals:
            raise AppServerUserStateError(
                "dispatch correlation was already consumed; reconcile instead of replaying"
            )
        selected = selections[0]
        try:
            selected_epoch = datetime.fromisoformat(
                str(selected["recorded_at"]).replace("Z", "+00:00")
            ).timestamp()
        except (KeyError, TypeError, ValueError) as error:
            raise AppServerUserStateError(
                "dispatch selection timestamp is malformed"
            ) from error
        if float(store.now()) - selected_epoch > DISPATCH_LEASE_SECONDS:
            raise AppServerUserStateError(
                "dispatch selection lease expired before execution"
            )
        lifecycle = cls(
            command=str(selected.get("command", "unknown")),
            role=str(selected.get("role", "unknown")),
            preference_mode=str(selected.get("preference_mode", "UNKNOWN")),
            strict_request=bool(selected.get("strict_request")),
            source=str(selected.get("source", "unknown")),
            path=path,
            correlation_id=correlation_id,
        )
        lifecycle._selected = True
        return lifecycle

    @classmethod
    def recover(
        cls,
        correlation_id: str,
        *,
        disposition: str,
        path: Path | None = None,
    ) -> dict[str, Any]:
        if disposition not in {"pre-mutation", "mutation-uncertain"}:
            raise AppServerUserStateError("unsupported dispatch recovery disposition")
        store = AppServerEventStore(path)
        events = store.correlation_events(correlation_id)
        selections = [event for event in events if event.get("outcome") == "selected"]
        attempts = [event for event in events if event.get("outcome") == "attempted"]
        terminals = [
            event for event in events if event.get("outcome") in cls.TERMINAL_OUTCOMES
        ]
        if len(selections) != 1 or len(attempts) > 1 or len(terminals) > 1:
            raise AppServerUserStateError(
                "dispatch recovery requires one unambiguous current-schema lifecycle"
            )
        selected = selections[0]
        if disposition == "pre-mutation" and attempts:
            raise AppServerUserStateError(
                "an attempted dispatch requires mutation-uncertain reconciliation"
            )
        if disposition == "mutation-uncertain" and not attempts:
            raise AppServerUserStateError(
                "mutation-uncertain recovery requires a recorded execution attempt"
            )
        strict = bool(selected.get("strict_request"))
        expected_outcome = (
            "reconciliation_required"
            if disposition == "mutation-uncertain"
            else "failed"
            if strict
            else "gui_fallback"
        )
        if terminals:
            terminal = terminals[0]
            if terminal.get("outcome") != expected_outcome:
                raise AppServerUserStateError(
                    "dispatch recovery conflicts with the existing terminal disposition"
                )
            return {
                "correlation_id": correlation_id,
                "outcome": expected_outcome,
                "idempotent": True,
                "writes_performed": False,
            }
        lifecycle = cls(
            command=str(selected.get("command", "unknown")),
            role=str(selected.get("role", "unknown")),
            preference_mode=str(selected.get("preference_mode", "UNKNOWN")),
            strict_request=strict,
            source=str(selected.get("source", "unknown")),
            path=path,
            correlation_id=correlation_id,
        )
        lifecycle._selected = True
        lifecycle._attempted = bool(attempts)
        lifecycle.terminal(
            expected_outcome,
            category=(
                "process_loss_mutation_uncertain"
                if disposition == "mutation-uncertain"
                else "process_loss_pre_mutation"
            ),
            mutation_state="possible" if disposition == "mutation-uncertain" else "none",
            backend=(
                "gui"
                if disposition == "mutation-uncertain" or not strict
                else "app_server"
            ),
        )
        return {
            "correlation_id": correlation_id,
            "outcome": expected_outcome,
            "idempotent": False,
            "writes_performed": True,
        }

    def _record(
        self,
        *,
        outcome: str,
        category: str,
        mutation_state: str,
        backend: str,
        event_type: str,
    ) -> dict[str, Any]:
        return self.store.record(
            command=self.command,
            outcome=outcome,
            category=category,
            mutation_state=mutation_state,
            backend=backend,
            preference_mode=self.preference_mode,
            strict_request=self.strict_request,
            source=self.source,
            event_type=event_type,
            role=self.role,
            correlation_id=self.correlation_id,
        )

    def selected(self, category: str) -> dict[str, Any]:
        if self._selected or self._attempted or self._terminal:
            raise AppServerUserStateError("dispatch selection was already recorded")
        event = self._record(
            outcome="selected",
            category=category,
            mutation_state="none",
            backend="app_server",
            event_type="opportunity",
        )
        self._selected = True
        return event

    def attempted(self, category: str = "dispatch") -> dict[str, Any]:
        if not self._selected:
            raise AppServerUserStateError("dispatch attempt requires a recorded selection")
        if self._attempted or self._terminal:
            raise AppServerUserStateError("dispatch attempt was already recorded")
        event = self._record(
            outcome="attempted",
            category=category,
            mutation_state="none",
            backend="app_server",
            event_type="execution",
        )
        self._attempted = True
        return event

    def terminal(
        self,
        outcome: str,
        *,
        category: str,
        mutation_state: str,
        backend: str,
    ) -> dict[str, Any]:
        if outcome not in self.TERMINAL_OUTCOMES:
            raise AppServerUserStateError(f"unsupported dispatch terminal outcome: {outcome}")
        if self._terminal:
            raise AppServerUserStateError("dispatch terminal result was already recorded")
        event = self._record(
            outcome=outcome,
            category=category,
            mutation_state=mutation_state,
            backend=backend,
            event_type="terminal",
        )
        self._terminal = True
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


def require_no_app_server_dispatch_debt(
    *,
    path: Path | None = None,
    operation: str,
) -> dict[str, Any]:
    """Fail a closure boundary while a current-schema eligible dispatch is unresolved."""

    report = AppServerEventStore(path).report(hours=24 * 365)
    debt = int(report.get("dispatch_debt", 0))
    if debt:
        findings = report.get("dispatch_lifecycles", {}).get("findings", [])
        codes = sorted(
            {
                str(code)
                for finding in findings
                for code in (finding.get("codes") or [])
            }
        )
        summary = ", ".join(codes[:8]) or "unknown"
        raise AppServerUserStateError(
            f"{operation} is blocked by {debt} unresolved App Server dispatch "
            f"lifecycle(s): {summary}"
        )
    return report
