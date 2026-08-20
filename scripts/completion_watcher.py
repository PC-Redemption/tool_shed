#!/usr/bin/env python3
"""Local completion watcher CLI and runtime implementation for v1."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

if os.name == "nt":
    import msvcrt


WATCHER_FORMAT = "completion-watcher/v1"
MAX_CHECKER_OUTPUT_BYTES = 64 * 1024
CHECKER_TIMEOUT_TO_REASON = "SOURCE_UNAVAILABLE"
STDOUT_ENCODING = "utf-8"

SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
WATCH_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")

CHECKER_STATES = {"WAITING", "SATISFIED", "TERMINAL_UNSATISFIED", "CHECK_ERROR"}
RESULT_REASONS = {
    "WAITING": {"TARGET_NONTERMINAL"},
    "SATISFIED": {"TARGET_SUCCEEDED", "CONDITION_MET"},
    "TERMINAL_UNSATISFIED": {
        "TARGET_FAILED",
        "TARGET_CANCELLED",
        "TARGET_PREEMPTED",
        "TARGET_SUPERSEDED",
    },
    "CHECK_ERROR": {"TARGET_MISSING_TRANSIENT", "SOURCE_UNAVAILABLE", "CHECKER_INTERNAL"},
}

TERMINAL_REASONS = {
    "SATISFIED": {"TARGET_SUCCEEDED", "CONDITION_MET"},
    "TERMINAL_UNSATISFIED": {
        "TARGET_FAILED",
        "TARGET_CANCELLED",
        "TARGET_PREEMPTED",
        "TARGET_SUPERSEDED",
        "TARGET_MISSING_AFTER_GRACE",
    },
    "CHECK_ERROR_EXHAUSTED": {"CONSECUTIVE_CHECK_ERRORS_EXHAUSTED"},
    "WATCH_CANCELLED": {"OPERATOR_CANCELLED_WATCH"},
    "RETIRED_WITHOUT_CONCLUSION": {"ADMINISTRATIVE_RETIREMENT"},
}


@dataclass(frozen=True)
class WatcherPaths:
    root: Path
    format_json: Path
    singleton_lock: Path
    heartbeat_json: Path
    pending_dir: Path
    claimed_dir: Path
    cancel_dir: Path
    outbox_pending_dir: Path
    outbox_claimed_dir: Path
    outbox_receipts_dir: Path
    history_dir: Path
    tmp_dir: Path

    @classmethod
    def from_root(cls, root: Path) -> "WatcherPaths":
        return cls(
            root=root,
            format_json=root / "format.json",
            singleton_lock=root / "runner" / "singleton.lock",
            heartbeat_json=root / "runner" / "heartbeat.json",
            pending_dir=root / "watches" / "pending",
            claimed_dir=root / "watches" / "claimed",
            cancel_dir=root / "cancel",
            outbox_pending_dir=root / "outbox" / "pending",
            outbox_claimed_dir=root / "outbox" / "claimed",
            outbox_receipts_dir=root / "outbox" / "receipts",
            history_dir=root / "history",
            tmp_dir=root / "tmp",
        )

    def pending_path(self, watch_id: str) -> Path:
        return self.pending_dir / f"{watch_id}.json"

    def claimed_path(self, watch_id: str) -> Path:
        return self.claimed_dir / f"{watch_id}.json"

    def cancel_path(self, watch_id: str) -> Path:
        return self.cancel_dir / f"{watch_id}.json"

    def history_path(self, watch_id: str) -> Path:
        return self.history_dir / f"{watch_id}.json"


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc).replace(microsecond=0)


def _fmt_ts(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_ts(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be string")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fsync_fd(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_json_atomically(path: Path, payload: Any, *, tmp_dir: Path) -> None:
    tmp_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile("w", dir=tmp_dir, suffix=".tmp", encoding="utf-8", delete=False) as handle:
        handle.write(_canonical_json(payload))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temp_path = Path(handle.name)
    os.replace(temp_path, path)
    os.chmod(path, 0o600)
    _fsync_fd(path.parent)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    if path.is_symlink():
        raise ValueError(f"refusing symlink path: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.loads(handle.read())
    if not isinstance(payload, dict):
        raise ValueError(f"non-object payload: {path}")
    return payload


def _validate_safe_id(value: Any, *, minimum: int, maximum: int) -> str:
    if not isinstance(value, str) or not (minimum <= len(value) <= maximum):
        raise ValueError("invalid id length")
    if not SAFE_ID.fullmatch(value):
        raise ValueError("invalid safe identifier")
    return value


def _validate_watch_id(value: Any) -> str:
    if not isinstance(value, str) or not WATCH_ID.fullmatch(value):
        raise ValueError("invalid watch id")
    if str(uuid.UUID(value)) != value:
        raise ValueError("watch id must be canonical")
    if uuid.UUID(value).version != 4:
        raise ValueError("watch id must be UUIDv4")
    return value


def _validate_sha256(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise ValueError(f"invalid {label}")
    return value


def validate_descriptor(payload: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version",
        "watch_id",
        "created_at",
        "display_name",
        "workspace",
        "target",
        "checker",
        "policy",
        "notification",
    }
    if required - payload.keys():
        missing = sorted(required - payload.keys())
        raise ValueError(f"missing descriptor fields: {missing}")
    if set(payload) - required - {"review_url"}:
        unexpected = sorted(set(payload) - required - {"review_url"})
        raise ValueError(f"unexpected descriptor fields: {unexpected}")
    if payload["schema_version"] != 1:
        raise ValueError("unsupported descriptor schema")
    _validate_watch_id(payload["watch_id"])
    _parse_ts(payload["created_at"])
    if not isinstance(payload["display_name"], str) or not 1 <= len(payload["display_name"]) <= 120:
        raise ValueError("invalid display_name")

    workspace = payload["workspace"]
    if not isinstance(workspace, dict):
        raise ValueError("workspace must be object")
    if set(workspace.keys()) != {"id", "alias"}:
        raise ValueError("workspace has invalid fields")
    _validate_safe_id(workspace["id"], minimum=1, maximum=64)
    if not isinstance(workspace["alias"], str) or not 1 <= len(workspace["alias"]) <= 80:
        raise ValueError("invalid workspace alias")

    target = payload["target"]
    if not isinstance(target, dict):
        raise ValueError("target must be object")
    if set(target.keys()) not in ({"kind", "id"}, {"kind", "id", "generation"}):
        raise ValueError("target has invalid fields")
    _validate_safe_id(target["kind"], minimum=1, maximum=64)
    if not isinstance(target["id"], str) or not 1 <= len(target["id"]) <= 256:
        raise ValueError("invalid target id")
    if "generation" in target and (
        not isinstance(target["generation"], str) or not 1 <= len(target["generation"]) <= 128
    ):
        raise ValueError("invalid target generation")

    checker = payload["checker"]
    if not isinstance(checker, dict):
        raise ValueError("checker must be object")
    if set(checker) not in (
        {"argv", "timeout_seconds"},
        {"argv", "timeout_seconds", "working_directory"},
        {"argv", "timeout_seconds", "credential_profile"},
        {"argv", "timeout_seconds", "working_directory", "credential_profile"},
    ):
        raise ValueError("checker has invalid fields")
    argv = checker["argv"]
    if not isinstance(argv, list) or not 1 <= len(argv) <= 16:
        raise ValueError("checker argv invalid")
    for argument in argv:
        if not isinstance(argument, str) or not 1 <= len(argument) <= 2048:
            raise ValueError("checker argument invalid")
    if not isinstance(checker["timeout_seconds"], int) or not 1 <= checker["timeout_seconds"] <= 55:
        raise ValueError("invalid checker timeout")
    if "working_directory" in checker and (
        not isinstance(checker["working_directory"], str) or not 1 <= len(checker["working_directory"]) <= 4096
    ):
        raise ValueError("invalid working_directory")
    if "credential_profile" in checker:
        _validate_safe_id(checker["credential_profile"], minimum=1, maximum=64)

    policy = payload["policy"]
    if not isinstance(policy, dict):
        raise ValueError("policy must be object")
    if set(policy) not in (
        {
            "poll_interval_seconds",
            "missing_grace_checks",
            "max_consecutive_check_errors",
            "claim_lease_seconds",
            "idle_exit_scans",
            "review_after",
            "administrative_retire_after",
        },
        {
            "poll_interval_seconds",
            "missing_grace_checks",
            "max_consecutive_check_errors",
            "claim_lease_seconds",
            "idle_exit_scans",
        },
    ):
        raise ValueError("policy has invalid fields")
    if policy["poll_interval_seconds"] != 60 or policy["idle_exit_scans"] != 2:
        raise ValueError("unsupported poll policy")
    if not 1 <= policy["missing_grace_checks"] <= 10:
        raise ValueError("invalid missing_grace_checks")
    if not 1 <= policy["max_consecutive_check_errors"] <= 20:
        raise ValueError("invalid max_consecutive_check_errors")
    if not 60 <= policy["claim_lease_seconds"] <= 900:
        raise ValueError("invalid claim_lease_seconds")
    for field in ("review_after", "administrative_retire_after"):
        if field in policy:
            _parse_ts(policy[field])

    notification = payload["notification"]
    if not isinstance(notification, dict):
        raise ValueError("notification must be object")
    if set(notification) not in ({"adapter"}, {"adapter", "profile"}):
        raise ValueError("notification has invalid fields")
    if notification["adapter"] not in {"none", "project", "hosted"}:
        raise ValueError("invalid notification adapter")
    if notification["adapter"] == "none":
        if "profile" in notification:
            raise ValueError("none adapter cannot include profile")
    else:
        if "profile" not in notification:
            raise ValueError("notification profile required")
        _validate_safe_id(notification["profile"], minimum=1, maximum=64)

    if "review_url" in payload:
        review_url = payload["review_url"]
        if not isinstance(review_url, str) or not 1 <= len(review_url) <= 2048:
            raise ValueError("invalid review_url")
        if not review_url.startswith(("http://", "https://")):
            raise ValueError("review_url must be http(s)")

    return payload


def validate_checker_result(payload: dict[str, Any], descriptor: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version",
        "state",
        "observed_at",
        "target",
        "reason_code",
        "identity_confirmed",
        "target_exists",
        "authoritative_nonterminal",
    }
    if required - payload.keys():
        missing = sorted(required - payload.keys())
        raise ValueError(f"missing checker fields: {missing}")
    if set(payload) - required - {"progress_at", "detail"}:
        unknown = sorted(set(payload) - required - {"progress_at", "detail"})
        raise ValueError(f"unexpected checker fields: {unknown}")
    if payload["schema_version"] != 1:
        raise ValueError("unsupported checker schema")
    state = payload["state"]
    if state not in CHECKER_STATES:
        raise ValueError("invalid checker state")
    _parse_ts(payload["observed_at"])
    if not isinstance(payload["target"], dict):
        raise ValueError("target must be object")
    target = payload["target"]
    if set(target) not in ({"kind", "id"}, {"kind", "id", "generation"}):
        raise ValueError("target fields invalid")
    if target != descriptor["target"]:
        raise ValueError("target identity mismatch")
    reason = payload["reason_code"]
    if reason not in RESULT_REASONS[state]:
        raise ValueError("reason code does not match state")
    if not isinstance(payload["identity_confirmed"], bool):
        raise ValueError("identity_confirmed must be boolean")
    if not isinstance(payload["target_exists"], bool):
        raise ValueError("target_exists must be boolean")
    if not isinstance(payload["authoritative_nonterminal"], bool):
        raise ValueError("authoritative_nonterminal must be boolean")
    if "progress_at" in payload:
        _parse_ts(payload["progress_at"])
    if "detail" in payload and (not isinstance(payload["detail"], str) or len(payload["detail"]) > 512):
        raise ValueError("invalid detail")

    if state == "WAITING":
        if reason != "TARGET_NONTERMINAL":
            raise ValueError("waiting state must include TARGET_NONTERMINAL reason")
        if not (payload["identity_confirmed"] and payload["target_exists"] and payload["authoritative_nonterminal"]):
            raise ValueError("waiting requires authoritative live evidence")
    elif state in {"SATISFIED", "TERMINAL_UNSATISFIED"}:
        if not payload["identity_confirmed"] or payload["authoritative_nonterminal"]:
            raise ValueError("terminal result requires confirmed non-nonterminal evidence")
    elif state == "CHECK_ERROR" and payload["authoritative_nonterminal"]:
        raise ValueError("check error cannot be authoritative")

    return payload


def validate_watch_record(payload: dict[str, Any]) -> dict[str, Any]:
    required = {
        "record_version",
        "descriptor",
        "descriptor_sha256",
        "lifecycle_state",
        "due_at",
        "missing_streak",
        "error_streak",
        "checker_attempts",
    }
    optional = {"last_checked_at", "last_progress_at", "cancel_requested_at", "terminal_event_id", "claim"}
    if required - payload.keys():
        missing = sorted(required - payload.keys())
        raise ValueError(f"missing watch record fields: {missing}")
    if set(payload) - required - optional:
        unknown = sorted(set(payload) - required - optional)
        raise ValueError(f"unexpected watch record fields: {unknown}")
    if payload["record_version"] != 1:
        raise ValueError("unsupported watch record version")
    descriptor = validate_descriptor(payload["descriptor"])
    expected = hashlib.sha256(_canonical_json(descriptor).encode("utf-8")).hexdigest()
    if _validate_sha256(payload["descriptor_sha256"], label="descriptor_sha256") != expected:
        raise ValueError("descriptor digest mismatch")
    if payload["lifecycle_state"] not in {"PENDING", "CLAIMED", "RETIRING"}:
        raise ValueError("invalid lifecycle state")
    _parse_ts(payload["due_at"])
    for key in ("missing_streak", "error_streak", "checker_attempts"):
        if not isinstance(payload[key], int) or payload[key] < 0:
            raise ValueError(f"invalid {key}")
    if "last_checked_at" in payload:
        _parse_ts(payload["last_checked_at"])
    if "last_progress_at" in payload:
        _parse_ts(payload["last_progress_at"])
    if "cancel_requested_at" in payload:
        _parse_ts(payload["cancel_requested_at"])
    if "terminal_event_id" in payload:
        _validate_sha256(payload["terminal_event_id"], label="terminal_event_id")
    if payload["lifecycle_state"] == "CLAIMED":
        claim = payload.get("claim")
        if not isinstance(claim, dict):
            raise ValueError("claimed watch requires claim object")
        if set(claim) != {"runner_id", "claimed_at", "lease_until"}:
            raise ValueError("claim object malformed")
        _validate_watch_id(claim["runner_id"])
        _parse_ts(claim["claimed_at"])
        _parse_ts(claim["lease_until"])
    return payload


def validate_terminal_event(payload: dict[str, Any], descriptor: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version",
        "event_id",
        "idempotency_key",
        "watch_id",
        "workspace",
        "display_name",
        "target",
        "terminal_class",
        "reason_code",
        "occurred_at",
        "enqueued_at",
        "notification_adapter",
    }
    optional = {"sanitized_detail", "review_url"}
    if required - payload.keys():
        missing = sorted(required - payload.keys())
        raise ValueError(f"missing terminal event fields: {missing}")
    if set(payload) - required - optional:
        unknown = sorted(set(payload) - required - optional)
        raise ValueError(f"unexpected terminal event fields: {unknown}")
    if payload["schema_version"] != 1:
        raise ValueError("unsupported terminal schema")
    watch_id = _validate_watch_id(payload["watch_id"])
    expected_event_id = terminal_event_id(watch_id)
    if _validate_sha256(payload["event_id"], label="event_id") != expected_event_id:
        raise ValueError("unexpected terminal event id")
    if payload["idempotency_key"] != f"watch-terminal-v1:{expected_event_id}":
        raise ValueError("invalid terminal idempotency key")
    if payload["notification_adapter"] != descriptor["notification"]["adapter"]:
        raise ValueError("notification adapter changed")
    workspace = payload["workspace"]
    if workspace != descriptor["workspace"]:
        raise ValueError("workspace changed")
    if payload["display_name"] != descriptor["display_name"]:
        raise ValueError("display_name changed")
    if payload["target"] != descriptor["target"]:
        raise ValueError("target changed")
    if payload["terminal_class"] not in TERMINAL_REASONS:
        raise ValueError("invalid terminal class")
    if payload["reason_code"] not in TERMINAL_REASONS[payload["terminal_class"]]:
        raise ValueError("reason does not match terminal class")
    _parse_ts(payload["occurred_at"])
    _parse_ts(payload["enqueued_at"])
    occurred = datetime.fromisoformat(payload["occurred_at"].replace("Z", "+00:00"))
    enqueued = datetime.fromisoformat(payload["enqueued_at"].replace("Z", "+00:00"))
    if enqueued < occurred:
        raise ValueError("enqueued_at cannot be before occurred_at")
    if "sanitized_detail" in payload and (
        not isinstance(payload["sanitized_detail"], str) or len(payload["sanitized_detail"]) > 512
    ):
        raise ValueError("invalid sanitized_detail")
    if "review_url" in payload:
        if not isinstance(payload["review_url"], str) or not 1 <= len(payload["review_url"]) <= 2048:
            raise ValueError("invalid review_url")
        if not payload["review_url"].startswith(("http://", "https://")):
            raise ValueError("review_url must be HTTP(S)")
    return payload


def terminal_event_id(watch_id: str) -> str:
    return hashlib.sha256(f"tool-shed-watch-terminal-v1\0{watch_id}".encode("utf-8")).hexdigest()


def _checker_error_transition(previous: dict[str, Any], policy: dict[str, int], *, missing: bool) -> tuple[str, dict[str, int]]:
    missing_streak = int(previous["missing_streak"]) + (1 if missing else 0)
    error_streak = int(previous["error_streak"]) + 1
    if missing and missing_streak >= policy["missing_grace_checks"]:
        return "ENQUEUE_TERMINAL", {
            "terminal_class": "TERMINAL_UNSATISFIED",
            "reason_code": "TARGET_MISSING_AFTER_GRACE",
            "detail": "target could not be found after grace checks",
            "missing_streak": missing_streak,
            "error_streak": error_streak,
        }
    if error_streak >= policy["max_consecutive_check_errors"]:
        return "ENQUEUE_TERMINAL", {
            "terminal_class": "CHECK_ERROR_EXHAUSTED",
            "reason_code": "CONSECUTIVE_CHECK_ERRORS_EXHAUSTED",
            "detail": "checker error budget exhausted",
            "missing_streak": missing_streak,
            "error_streak": error_streak,
        }
    return "REQUEUE", {
        "state": "CHECK_ERROR",
        "missing_streak": missing_streak,
        "error_streak": error_streak,
    }


def evaluate_transition(
    case: dict[str, Any],
    descriptor: dict[str, Any],
    results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    previous = dict(case["previous"])
    observation = dict(case["observation"])
    if previous.get("outbox_has_terminal"):
        return {"action": "RETIRE_AFTER_ENQUEUE"}
    if previous.get("cancel_requested"):
        return {
            "action": "ENQUEUE_TERMINAL",
            "terminal_class": "WATCH_CANCELLED",
            "reason_code": "OPERATOR_CANCELLED_WATCH",
        }
    if previous.get("administrative_retire_requested"):
        return {
            "action": "ENQUEUE_TERMINAL",
            "terminal_class": "RETIRED_WITHOUT_CONCLUSION",
            "reason_code": "ADMINISTRATIVE_RETIREMENT",
        }
    if (
        previous.get("claim_owner")
        and previous.get("claim_owner") != previous.get("current_runner")
        and previous.get("current_runner_has_lock")
    ):
        return {"action": "RECOVER_CLAIM"}
    if observation.get("type") == "ensure_runner" and previous.get("runner_lock_held"):
        return {"action": "NO_START_LOCK_HELD"}

    policy = descriptor["policy"]
    obs_type = observation["type"]
    if obs_type in {"runner_fault", "identity_mismatch"}:
        action, payload = _checker_error_transition(previous, policy, missing=False)
        return {"action": action, **payload}
    if obs_type != "result":
        raise ValueError(f"unsupported observation: {obs_type}")
    result = results[str(observation["result"])]
    validate_checker_result(result, descriptor)
    state = result["state"]
    if state == "WAITING":
        review_due = bool(previous.get("review_due"))
        return {
            "action": "REQUEUE_REVIEW_DUE" if review_due else "REQUEUE",
            "state": "WAITING",
            "missing_streak": 0,
            "error_streak": 0,
        }
    if state == "SATISFIED":
        return {
            "action": "ENQUEUE_TERMINAL",
            "terminal_class": "SATISFIED",
            "reason_code": result["reason_code"],
        }
    if state == "TERMINAL_UNSATISFIED":
        return {
            "action": "ENQUEUE_TERMINAL",
            "terminal_class": "TERMINAL_UNSATISFIED",
            "reason_code": result["reason_code"],
        }
    action, payload = _checker_error_transition(previous, policy, missing=result["reason_code"] == "TARGET_MISSING_TRANSIENT")
    return {"action": action, **payload}


def _resolve_state_root(override: str | None) -> Path:
    if override is not None:
        root = Path(override).expanduser()
        if not root.is_absolute():
            raise ValueError("state-root must be absolute")
        return root
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if not base:
            raise ValueError("LOCALAPPDATA or APPDATA required for windows default state root")
        return Path(base) / "ToolShed" / "watchers" / "v1"
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "tool-shed" / "watchers" / "v1"


def _check_permissions(path: Path) -> None:
    if path.exists():
        if path.is_symlink():
            raise ValueError("state root cannot be symlink")
        st = path.stat()
        if os.name != "nt" and st.st_uid != os.getuid():
            raise ValueError("state root must be owned by current user")
        if os.name != "nt" and stat.S_IMODE(st.st_mode) != 0o700:
            raise ValueError("state root must be mode 0700")
    else:
        path.mkdir(parents=True, mode=0o700)
        os.chmod(path, 0o700)
    if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) != 0o700:
        raise ValueError("state root must be mode 0700")


def _ensure_state_layout(paths: WatcherPaths) -> None:
    _check_permissions(paths.root)
    for directory in (
        paths.pending_dir,
        paths.claimed_dir,
        paths.cancel_dir,
        paths.outbox_pending_dir,
        paths.outbox_claimed_dir,
        paths.outbox_receipts_dir,
        paths.history_dir,
        paths.tmp_dir,
        paths.singleton_lock.parent,
    ):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)


def _ensure_format(paths: WatcherPaths) -> None:
    if paths.format_json.exists():
        payload = _read_json(paths.format_json)
        if payload.get("format") != WATCHER_FORMAT or payload.get("major") != 1:
            raise ValueError("unsupported watcher format")
        return
    _write_json_atomically(
        paths.format_json,
        {
            "format": WATCHER_FORMAT,
            "major": 1,
            "minor": 0,
            "created_at": _fmt_ts(_utcnow()),
        },
        tmp_dir=paths.tmp_dir,
    )


class SingletonLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle = None

    def acquire(self, *, non_blocking: bool = True) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name == "nt":
            self.handle = open(self.path, "a+b", buffering=0)
            try:
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK if non_blocking else msvcrt.LK_LOCK, 1)
                return True
            except OSError:
                self.handle.close()
                self.handle = None
                return False
        import fcntl

        self.handle = open(self.path, "a+b", buffering=0)
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | (fcntl.LOCK_NB if non_blocking else 0))
            return True
        except OSError:
            self.handle.close()
            self.handle = None
            return False

    def release(self) -> None:
        if self.handle is None:
            return
        try:
            if os.name == "nt":
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None

    def __enter__(self) -> "SingletonLock":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


def _heartbeat(paths: WatcherPaths, runner_id: str) -> None:
    _write_json_atomically(
        paths.heartbeat_json,
        {
            "runner_id": runner_id,
            "pid": os.getpid(),
            "updated_at": _fmt_ts(_utcnow()),
        },
        tmp_dir=paths.tmp_dir,
    )


def _make_watch_record(descriptor: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_version": 1,
        "descriptor": descriptor,
        "descriptor_sha256": hashlib.sha256(_canonical_json(descriptor).encode("utf-8")).hexdigest(),
        "lifecycle_state": "PENDING",
        "due_at": _fmt_ts(_utcnow() + timedelta(seconds=descriptor["policy"]["poll_interval_seconds"])),
        "missing_streak": 0,
        "error_streak": 0,
        "checker_attempts": 0,
    }


def _load_record(path: Path) -> dict[str, Any]:
    return validate_watch_record(_read_json(path))


def _decode_checker_output(payload: bytes, descriptor: dict[str, Any], observed_at: datetime) -> dict[str, Any]:
    if not payload:
        return {
            "schema_version": 1,
            "state": "CHECK_ERROR",
            "observed_at": _fmt_ts(observed_at),
            "target": descriptor["target"],
            "reason_code": "CHECKER_INTERNAL",
            "identity_confirmed": False,
            "target_exists": False,
            "authoritative_nonterminal": False,
            "detail": "checker output empty",
        }
    if len(payload) > MAX_CHECKER_OUTPUT_BYTES:
        return {
            "schema_version": 1,
            "state": "CHECK_ERROR",
            "observed_at": _fmt_ts(observed_at),
            "target": descriptor["target"],
            "reason_code": "CHECKER_INTERNAL",
            "identity_confirmed": False,
            "target_exists": False,
            "authoritative_nonterminal": False,
            "detail": "checker output exceeds 64KiB",
        }
    try:
        text = payload.decode(STDOUT_ENCODING)
    except UnicodeDecodeError:
        return {
            "schema_version": 1,
            "state": "CHECK_ERROR",
            "observed_at": _fmt_ts(observed_at),
            "target": descriptor["target"],
            "reason_code": "CHECKER_INTERNAL",
            "identity_confirmed": False,
            "target_exists": False,
            "authoritative_nonterminal": False,
            "detail": "checker output invalid UTF-8",
        }
    cleaned = text.strip()
    if not cleaned:
        return {
            "schema_version": 1,
            "state": "CHECK_ERROR",
            "observed_at": _fmt_ts(observed_at),
            "target": descriptor["target"],
            "reason_code": "CHECKER_INTERNAL",
            "identity_confirmed": False,
            "target_exists": False,
            "authoritative_nonterminal": False,
            "detail": "checker output empty",
        }
    decoder = json.JSONDecoder()
    try:
        decoded, index = decoder.raw_decode(cleaned)
    except json.JSONDecodeError:
        return {
            "schema_version": 1,
            "state": "CHECK_ERROR",
            "observed_at": _fmt_ts(observed_at),
            "target": descriptor["target"],
            "reason_code": "CHECKER_INTERNAL",
            "identity_confirmed": False,
            "target_exists": False,
            "authoritative_nonterminal": False,
            "detail": "checker output malformed",
        }
    if cleaned[index:].strip():
        return {
            "schema_version": 1,
            "state": "CHECK_ERROR",
            "observed_at": _fmt_ts(observed_at),
            "target": descriptor["target"],
            "reason_code": "CHECKER_INTERNAL",
            "identity_confirmed": False,
            "target_exists": False,
            "authoritative_nonterminal": False,
            "detail": "checker output must be single JSON object",
        }
    if not isinstance(decoded, dict):
        return {
            "schema_version": 1,
            "state": "CHECK_ERROR",
            "observed_at": _fmt_ts(observed_at),
            "target": descriptor["target"],
            "reason_code": "CHECKER_INTERNAL",
            "identity_confirmed": False,
            "target_exists": False,
            "authoritative_nonterminal": False,
            "detail": "checker output must be object",
        }
    try:
        return validate_checker_result(decoded, descriptor)
    except ValueError as error:
        return {
            "schema_version": 1,
            "state": "CHECK_ERROR",
            "observed_at": _fmt_ts(observed_at),
            "target": descriptor["target"],
            "reason_code": "CHECKER_INTERNAL",
            "identity_confirmed": False,
            "target_exists": False,
            "authoritative_nonterminal": False,
            "detail": str(error),
        }


def _run_checker(descriptor: dict[str, Any]) -> dict[str, Any]:
    checker = descriptor["checker"]
    observed_at = _utcnow()
    try:
        process = subprocess.run(
            checker["argv"],
            input=b"",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=checker["timeout_seconds"],
            cwd=checker.get("working_directory"),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "schema_version": 1,
            "state": "CHECK_ERROR",
            "observed_at": _fmt_ts(observed_at),
            "target": descriptor["target"],
            "reason_code": "SOURCE_UNAVAILABLE",
            "identity_confirmed": False,
            "target_exists": False,
            "authoritative_nonterminal": False,
            "detail": "checker timed out",
        }
    except OSError as error:
        return {
            "schema_version": 1,
            "state": "CHECK_ERROR",
            "observed_at": _fmt_ts(observed_at),
            "target": descriptor["target"],
            "reason_code": "CHECKER_INTERNAL",
            "identity_confirmed": False,
            "target_exists": False,
            "authoritative_nonterminal": False,
            "detail": str(error),
        }

    parsed = _decode_checker_output(process.stdout, descriptor, observed_at)
    if process.returncode != 0 and parsed["state"] != "CHECK_ERROR":
        parsed = {
            "schema_version": 1,
            "state": "CHECK_ERROR",
            "observed_at": parsed["observed_at"],
            "target": descriptor["target"],
            "reason_code": "CHECKER_INTERNAL",
            "identity_confirmed": False,
            "target_exists": False,
            "authoritative_nonterminal": False,
            "detail": parsed.get("detail") or "checker command failed",
        }
    return parsed


def _has_terminal(paths: WatcherPaths, watch_id: str) -> tuple[bool, Path | None, dict[str, Any] | None]:
    event_id = terminal_event_id(watch_id)
    for directory in (paths.outbox_pending_dir, paths.outbox_claimed_dir, paths.outbox_receipts_dir):
        candidate = directory / f"{event_id}.json"
        if candidate.exists():
            payload = _read_json(candidate)
            return True, candidate, payload
    return False, None, None


def _request_cancel(paths: WatcherPaths, watch_id: str, reason: str) -> None:
    _write_json_atomically(
        paths.cancel_path(watch_id),
        {"watch_id": watch_id, "reason": reason, "requested_at": _fmt_ts(_utcnow())},
        tmp_dir=paths.tmp_dir,
    )


def _read_cancel(paths: WatcherPaths, watch_id: str) -> tuple[str | None, str | None]:
    path = paths.cancel_path(watch_id)
    if not path.is_file():
        return None, None
    payload = _read_json(path)
    reason = payload.get("reason")
    if reason not in {"operator", "administrative"}:
        raise ValueError(f"invalid cancel reason: {reason}")
    requested_at = payload.get("requested_at")
    if not isinstance(requested_at, str):
        requested_at = None
    return reason, requested_at


def _make_terminal_event(
    descriptor: dict[str, Any],
    terminal_class: str,
    reason_code: str,
    occurred_at: datetime,
    *,
    detail: str | None,
) -> dict[str, Any]:
    event_id = terminal_event_id(descriptor["watch_id"])
    payload = {
        "schema_version": 1,
        "event_id": event_id,
        "idempotency_key": f"watch-terminal-v1:{event_id}",
        "watch_id": descriptor["watch_id"],
        "workspace": descriptor["workspace"],
        "display_name": descriptor["display_name"],
        "target": descriptor["target"],
        "terminal_class": terminal_class,
        "reason_code": reason_code,
        "occurred_at": _fmt_ts(occurred_at),
        "enqueued_at": _fmt_ts(_utcnow()),
        "notification_adapter": descriptor["notification"]["adapter"],
    }
    if detail:
        payload["sanitized_detail"] = detail[:512]
    if "review_url" in descriptor:
        payload["review_url"] = descriptor["review_url"]
    return validate_terminal_event(payload, descriptor)


def _upsert_terminal_event(
    paths: WatcherPaths,
    descriptor: dict[str, Any],
    terminal_class: str,
    reason_code: str,
    occurred_at: datetime,
    detail: str | None = None,
) -> Path:
    event = _make_terminal_event(descriptor, terminal_class, reason_code, occurred_at, detail=detail)
    event_id = event["event_id"]
    for directory in (
        paths.outbox_pending_dir,
        paths.outbox_claimed_dir,
        paths.outbox_receipts_dir,
    ):
        candidate = directory / f"{event_id}.json"
        if candidate.exists():
            existing = _read_json(candidate)
            if existing != event:
                raise ValueError("conflicting terminal payload for watch")
            return candidate
    target = paths.outbox_pending_dir / f"{event_id}.json"
    _write_json_atomically(target, event, tmp_dir=paths.tmp_dir)
    return target


def _retire_watch(paths: WatcherPaths, record: dict[str, Any], terminal_event_id_value: str) -> None:
    watch_id = record["descriptor"]["watch_id"]
    retired = dict(record)
    retired["lifecycle_state"] = "RETIRING"
    retired["terminal_event_id"] = terminal_event_id_value
    retired["retired_at"] = _fmt_ts(_utcnow())
    _write_json_atomically(paths.history_path(watch_id), retired, tmp_dir=paths.tmp_dir)
    paths.pending_path(watch_id).unlink(missing_ok=True)
    paths.claimed_path(watch_id).unlink(missing_ok=True)
    cancel_path = paths.cancel_path(watch_id)
    if cancel_path.exists():
        try:
            cancel_path.unlink()
        except OSError:
            pass


def _requeue_watch(paths: WatcherPaths, record: dict[str, Any], *, now: datetime) -> None:
    watch_id = record["descriptor"]["watch_id"]
    record = dict(record)
    record["lifecycle_state"] = "PENDING"
    record.pop("claim", None)
    record["due_at"] = _fmt_ts(now + timedelta(seconds=record["descriptor"]["policy"]["poll_interval_seconds"]))
    _write_json_atomically(paths.pending_path(watch_id), record, tmp_dir=paths.tmp_dir)
    paths.claimed_path(watch_id).unlink(missing_ok=True)


def _claim_watch(paths: WatcherPaths, watch_path: Path, record: dict[str, Any], runner_id: str) -> tuple[Path, dict[str, Any]]:
    watch_id = record["descriptor"]["watch_id"]
    claimed_path = paths.claimed_path(watch_id)
    if claimed_path.exists():
        raise ValueError("watch already claimed")
    now = _utcnow()
    updated = dict(record)
    updated["lifecycle_state"] = "CLAIMED"
    updated["claim"] = {
        "runner_id": runner_id,
        "claimed_at": _fmt_ts(now),
        "lease_until": _fmt_ts(now + timedelta(seconds=record["descriptor"]["policy"]["claim_lease_seconds"])),
    }
    os.replace(watch_path, claimed_path)
    _write_json_atomically(claimed_path, updated, tmp_dir=paths.tmp_dir)
    return claimed_path, updated


def _recover_claim(record: dict[str, Any], *, runner_id: str, now: datetime) -> dict[str, Any]:
    updated = dict(record)
    updated["claim"] = {
        "runner_id": runner_id,
        "claimed_at": _fmt_ts(now),
        "lease_until": _fmt_ts(now + timedelta(seconds=record["descriptor"]["policy"]["claim_lease_seconds"])),
    }
    return updated


def _should_process_record(record: dict[str, Any], now: datetime) -> bool:
    return _parse_ts(record["due_at"]) <= now


def _decide_transition_for_record(
    record: dict[str, Any],
    result: dict[str, Any],
    *,
    cancel_requested: str | None,
    has_terminal_event: bool,
    admin_retire_requested: bool,
    review_due: bool,
) -> tuple[str, dict[str, Any] | None]:
    if has_terminal_event:
        return "RETIRE_AFTER_ENQUEUE", None
    if cancel_requested == "operator":
        return "ENQUEUE_TERMINAL", {
            "terminal_class": "WATCH_CANCELLED",
            "reason_code": "OPERATOR_CANCELLED_WATCH",
            "detail": "operator requested cancellation",
        }
    if cancel_requested == "administrative" or admin_retire_requested:
        return "ENQUEUE_TERMINAL", {
            "terminal_class": "RETIRED_WITHOUT_CONCLUSION",
            "reason_code": "ADMINISTRATIVE_RETIREMENT",
            "detail": "administrative retirement requested",
        }

    state = result["state"]
    if state == "WAITING":
        return (
            "REQUEUE_REVIEW_DUE" if review_due else "REQUEUE",
            {
                "state": "WAITING",
                "missing_streak": 0,
                "error_streak": 0,
                "last_progress_at": result.get("progress_at"),
            },
        )
    if state == "SATISFIED":
        return "ENQUEUE_TERMINAL", {
            "terminal_class": "SATISFIED",
            "reason_code": result["reason_code"],
            "detail": result.get("detail"),
        }
    if state == "TERMINAL_UNSATISFIED":
        return "ENQUEUE_TERMINAL", {
            "terminal_class": "TERMINAL_UNSATISFIED",
            "reason_code": result["reason_code"],
            "detail": result.get("detail"),
        }

    return _checker_error_transition(
        {
            "missing_streak": record["missing_streak"],
            "error_streak": record["error_streak"],
        },
        record["descriptor"]["policy"],
        missing=result["reason_code"] == "TARGET_MISSING_TRANSIENT",
    )


def _transition_admin_after_stale(record: dict[str, Any], now: datetime) -> bool:
    admin_after = record["descriptor"]["policy"].get("administrative_retire_after")
    if not admin_after:
        return False
    return now >= _parse_ts(admin_after)


def _process_record(paths: WatcherPaths, watch_path: Path, runner_id: str) -> bool:
    now = _utcnow()
    record = _load_record(watch_path)
    descriptor = record["descriptor"]
    watch_id = descriptor["watch_id"]

    if not _should_process_record(record, now):
        return False

    has_terminal, _, terminal_payload = _has_terminal(paths, watch_id)
    if has_terminal and terminal_payload is not None:
        _retire_watch(paths, record, terminal_payload["event_id"])
        return True

    if record["lifecycle_state"] == "PENDING":
        watch_path, record = _claim_watch(paths, watch_path, record, runner_id)
    elif record["lifecycle_state"] != "CLAIMED":
        raise ValueError("unexpected lifecycle state")

    if record["claim"]["runner_id"] != runner_id:
        record = _recover_claim(record, runner_id=runner_id, now=now)
        _write_json_atomically(watch_path, record, tmp_dir=paths.tmp_dir)

    lease_until = _parse_ts(record["claim"]["lease_until"])
    if lease_until <= now:
        record = _recover_claim(record, runner_id=runner_id, now=now)
        _write_json_atomically(watch_path, record, tmp_dir=paths.tmp_dir)

    result = _run_checker(descriptor)
    cancel_requested, _ = _read_cancel(paths, watch_id)
    action, transition = _decide_transition_for_record(
        record,
        result,
        cancel_requested=cancel_requested,
        has_terminal_event=False,
        admin_retire_requested=_transition_admin_after_stale(record, now),
        review_due=bool(descriptor["policy"].get("review_after") and now >= _parse_ts(descriptor["policy"]["review_after"])),
    )

    record["checker_attempts"] = int(record["checker_attempts"]) + 1
    record["last_checked_at"] = _fmt_ts(now)
    if "progress_at" in result:
        record["last_progress_at"] = result["progress_at"]

    if action == "RETIRE_AFTER_ENQUEUE":
        has_terminal, _, payload = _has_terminal(paths, watch_id)
        if has_terminal and payload is not None:
            _retire_watch(paths, record, payload["event_id"])
        return True

    if action == "ENQUEUE_TERMINAL":
        terminal_event = _upsert_terminal_event(
            paths,
            descriptor,
            transition["terminal_class"],
            transition["reason_code"],
            occurred_at=_parse_ts(result["observed_at"]),
            detail=transition.get("detail"),
        )
        _retire_watch(paths, record, terminal_event.stem)
        return True

    if action in {"REQUEUE", "REQUEUE_REVIEW_DUE"}:
        record["missing_streak"] = int(transition["missing_streak"])
        record["error_streak"] = int(transition["error_streak"])
        if transition.get("last_progress_at"):
            record["last_progress_at"] = transition["last_progress_at"]
        _requeue_watch(paths, record, now=now)
        return True

    raise ValueError(f"unknown action: {action}")


def _deliver_outbox(paths: WatcherPaths, *, max_events: int | None = None) -> int:
    delivered = 0
    for event_path in sorted(paths.outbox_pending_dir.glob("*.json")):
        if max_events is not None and delivered >= max_events:
            break
        payload = _read_json(event_path)
        _receipt_path = paths.outbox_receipts_dir / event_path.name
        if _receipt_path.exists():
            event_path.unlink(missing_ok=True)
            delivered += 1
            continue
        _write_json_atomically(
            _receipt_path,
            {
                "event_id": payload["event_id"],
                "dispatched_at": _fmt_ts(_utcnow()),
                "status": "local-alpha-noop",
            },
            tmp_dir=paths.tmp_dir,
        )
        event_path.unlink(missing_ok=True)
        delivered += 1
    return delivered


def _scan(paths: WatcherPaths, runner_id: str, *, max_events: int | None = None) -> bool:
    did_work = _deliver_outbox(paths, max_events=max_events) > 0

    for path in sorted(paths.claimed_dir.glob("*.json")):
        did_work = _process_record(paths, path, runner_id) or did_work
    for path in sorted(paths.pending_dir.glob("*.json")):
        did_work = _process_record(paths, path, runner_id) or did_work

    return did_work


def _run_loop(
    paths: WatcherPaths,
    *,
    max_cycles: int | None = None,
    max_idle_scans: int = 2,
    scan_sleep: float = 0.0,
) -> int:
    runner_id = str(uuid.uuid4())
    _heartbeat(paths, runner_id)
    cycles = 0
    idle_scans = 0
    while True:
        cycles += 1
        did_work = _scan(paths, runner_id)
        if did_work:
            idle_scans = 0
        else:
            idle_scans += 1
            if idle_scans >= max_idle_scans:
                return cycles
        if max_cycles is not None and cycles >= max_cycles:
            return cycles
        if not did_work and scan_sleep > 0:
            time.sleep(scan_sleep)
        _heartbeat(paths, runner_id)


def cmd_arm(args: argparse.Namespace) -> int:
    paths = WatcherPaths.from_root(_resolve_state_root(args.state_root))
    _ensure_state_layout(paths)
    _ensure_format(paths)
    descriptor = validate_descriptor(json.loads(Path(args.descriptor).read_text(encoding="utf-8")))
    record = _make_watch_record(descriptor)
    watch_id = descriptor["watch_id"]
    target = paths.pending_path(watch_id)
    _write_json_atomically(target, record, tmp_dir=paths.tmp_dir)
    if args.json:
        print(
            json.dumps(
                {"watch_id": watch_id, "state_root": str(paths.root), "state": "armed"},
                sort_keys=True,
            )
        )
    else:
        print(f"armed {watch_id}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    paths = WatcherPaths.from_root(_resolve_state_root(args.state_root))
    _check_permissions(paths.root)
    pending = [_load_record(path)["descriptor"]["watch_id"] for path in sorted(paths.pending_dir.glob("*.json"))]
    claimed = [_load_record(path)["descriptor"]["watch_id"] for path in sorted(paths.claimed_dir.glob("*.json"))]
    payload = {
        "state_root": str(paths.root),
        "pending": sorted(pending),
        "claimed": sorted(claimed),
        "outbox": {
            "pending": len(list(paths.outbox_pending_dir.glob("*.json"))),
            "claimed": len(list(paths.outbox_claimed_dir.glob("*.json"))),
            "receipts": len(list(paths.outbox_receipts_dir.glob("*.json"))),
        },
    }
    print(json.dumps(payload, sort_keys=True, indent=2 if args.json else None))
    return 0


def cmd_cancel(args: argparse.Namespace) -> int:
    paths = WatcherPaths.from_root(_resolve_state_root(args.state_root))
    _check_permissions(paths.root)
    _request_cancel(paths, args.watch_id, reason="operator")
    payload = {"watch_id": args.watch_id, "status": "cancellation_requested"}
    print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload))
    return 0


def cmd_retire(args: argparse.Namespace) -> int:
    paths = WatcherPaths.from_root(_resolve_state_root(args.state_root))
    _check_permissions(paths.root)
    _request_cancel(paths, args.watch_id, reason="administrative")
    payload = {"watch_id": args.watch_id, "status": "administrative_retirement_requested"}
    print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload))
    return 0


def cmd_ensure_runner(args: argparse.Namespace) -> int:
    paths = WatcherPaths.from_root(_resolve_state_root(args.state_root))
    _ensure_state_layout(paths)
    _ensure_format(paths)

    if not any(paths.pending_dir.glob("*.json")) and not any(paths.claimed_dir.glob("*.json")) and not any(
        paths.outbox_pending_dir.glob("*.json")
    ):
        return 0

    with SingletonLock(paths.singleton_lock) as lock:
        if not lock.acquire(non_blocking=True):
            payload = {"status": "already_running"}
            print(json.dumps(payload, sort_keys=True) if args.json else "runner already running")
            return 0
        _run_loop(
            paths,
            max_cycles=args.max_cycles,
            max_idle_scans=args.max_idle_scans,
            scan_sleep=args.scan_sleep,
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", dest="state_root", default=None)
    parser.add_argument("--json", action="store_true")
    subcommands = parser.add_subparsers(dest="command", required=True)

    arm = subcommands.add_parser("arm", help="Arm a watch descriptor")
    arm.add_argument("descriptor")
    arm.set_defaults(func=cmd_arm)

    status = subcommands.add_parser("status", help="List watch state")
    status.set_defaults(func=cmd_status)

    cancel = subcommands.add_parser("cancel", help="Request operator cancellation")
    cancel.add_argument("watch_id")
    cancel.set_defaults(func=cmd_cancel)

    retire = subcommands.add_parser("retire", help="Request administrative retirement")
    retire.add_argument("watch_id")
    retire.set_defaults(func=cmd_retire)

    ensure = subcommands.add_parser("ensure-runner", help="Run or continue singleton watcher")
    ensure.add_argument("--max-cycles", type=int, default=None)
    ensure.add_argument("--max-idle-scans", type=int, default=2)
    ensure.add_argument("--scan-sleep", type=float, default=0.0)
    ensure.set_defaults(func=cmd_ensure_runner)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
