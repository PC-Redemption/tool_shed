#!/usr/bin/env python3
"""Manage and evaluate Tool Shed's project-bound autonomy authority envelope."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import json
import os
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator, Mapping

try:
    from scripts.project_identity import ProjectIdentityError, target_capsule
except ModuleNotFoundError:  # Direct execution: python scripts/autonomy_control.py
    from project_identity import ProjectIdentityError, target_capsule  # type: ignore[no-redef]


SCHEMA_VERSION = 1
LOCK_TIMEOUT_SECONDS = 10.0
STALE_LOCK_SECONDS = 30.0

LEVELS: dict[int, tuple[str, str]] = {
    0: ("Observe", "read and inspect"),
    1: ("Plan", "create and accept faithful reversible planning state"),
    2: ("Build", "edit source, validate, and build locally"),
    3: ("Checkpoint", "materialize campaigns, transition lifecycle state, and commit locally"),
    4: ("Collaborate", "push, update shared remotes, and deploy to known non-production targets"),
    5: ("Deliver", "merge, publish, release, and deploy to known production targets"),
}

ENDPOINT_RANK = {"none": 0, "work1": 1, "work2": 2, "work3": 3, "work4": 4, "work5": 5}


@dataclass(frozen=True)
class ActionPolicy:
    required_level: int
    required_endpoint: str
    impact: str
    blast_radius: str
    rollback: str


ACTION_POLICIES: dict[str, ActionPolicy] = {
    "observe": ActionPolicy(0, "none", "read-only inspection", "none", "none required"),
    "planning-state": ActionPolicy(1, "none", "reversible Tool Shed planning state changes", "current project planning artifacts", "restore the prior Git state"),
    "project-map-accept": ActionPolicy(1, "none", "accept faithful project direction derived from the stated outcome", "current project planning direction", "propose a superseding map revision"),
    "roadmap-accept": ActionPolicy(1, "none", "accept faithful milestones and evidence gates derived from approved direction", "current project roadmap", "propose a superseding roadmap revision"),
    "source-edit": ActionPolicy(2, "work1", "modify source or operator documentation", "requested workspace scope", "restore or revert the scoped changes"),
    "validation-build": ActionPolicy(2, "work1", "run project-local validation or builds", "local workspace resources", "stop the command and remove generated output through project tooling"),
    "campaign-materialize": ActionPolicy(3, "none", "create reversible campaign and queue state", "current project campaign queue", "defer, abandon, or supersede through guarded lifecycle operations"),
    "campaign-transition": ActionPolicy(3, "none", "start, complete, or evidence-gate an authorized campaign", "current project lifecycle state", "use guarded lifecycle recovery or a superseding evidence record"),
    "local-commit": ActionPolicy(3, "work1", "create a local Git checkpoint", "requested repository", "create a correcting commit or reset only with separate destructive authority"),
    "remote-collaboration": ActionPolicy(4, "work4", "update a known shared remote, branch, issue, or pull request", "configured collaboration target", "revert or supersede the remote update where supported"),
    "known-nonproduction-deploy": ActionPolicy(4, "work2", "deploy to a configured non-production target", "known development environment", "run the configured rollback or redeploy the prior candidate"),
    "known-production-delivery": ActionPolicy(5, "work5", "merge, publish, release, or deploy to configured production", "known production users and systems", "run the configured release rollback when supported"),
}

HARD_BOUNDARIES = {
    "scope-expansion": ("authority", "materially expands the authorized outcome or scope"),
    "material-decision": ("decision", "requires a product, architecture, sequencing, priority, or target choice not settled by current intent"),
    "unknown-target": ("authority", "targets an unresolved destination"),
    "credentials-auth": ("authority", "requires credentials, authentication, or account changes"),
    "cross-workspace": ("authority", "crosses the verified project identity boundary"),
    "purchase-legal": ("authority", "creates a purchase, financial, or legal commitment"),
    "destructive-irreversible": ("safety", "is broadly destructive or difficult to reverse"),
    "provider-protected": ("provider", "is controlled by a provider-native permission or protected-environment boundary"),
}


class AutonomyError(RuntimeError):
    pass


def default_preference_path(environment: Mapping[str, str] | None = None) -> Path:
    values = os.environ if environment is None else environment
    codex_root = values.get("CODEX_HOME")
    base = Path(codex_root).expanduser() if codex_root else Path.home() / ".codex"
    return base / "tool-shed" / "autonomy-preferences.json"


def _reject_workspace_state(path: Path) -> None:
    canonical = Path(__file__).resolve().parents[1]
    try:
        path.relative_to(canonical)
    except ValueError:
        pass
    else:
        raise AutonomyError("autonomy preference must remain outside Tool Shed")
    if any(parent.name == "tool_shed" for parent in path.parents):
        raise AutonomyError("autonomy preference must not be stored in an installed Tool Shed snapshot")
    for parent in (path.parent, *path.parents):
        marker = parent / ".git"
        if marker.is_file() or (marker / "HEAD").is_file():
            raise AutonomyError("autonomy preference must not be stored in a repository")


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
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
                lock.unlink(missing_ok=True)
                continue
            if time.monotonic() >= deadline:
                raise AutonomyError("timed out waiting for autonomy preference lock")
            time.sleep(0.02)
    try:
        os.close(descriptor)
        yield
    finally:
        lock.unlink(missing_ok=True)


def _read_payload(path: Path, *, for_write: bool = False) -> tuple[dict[str, Any], str | None]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"schema_version": SCHEMA_VERSION, "projects": {}}, "not-found"
    except OSError as error:
        if for_write:
            raise AutonomyError(f"cannot read autonomy preference: {error}") from error
        return {"schema_version": SCHEMA_VERSION, "projects": {}}, "unreadable-preference"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        if for_write:
            raise AutonomyError("refusing to overwrite malformed autonomy preference") from error
        return {"schema_version": SCHEMA_VERSION, "projects": {}}, "malformed-preference"
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != SCHEMA_VERSION
        or not isinstance(payload.get("projects"), dict)
    ):
        if for_write:
            raise AutonomyError("refusing to overwrite unsupported autonomy preference schema")
        return {"schema_version": SCHEMA_VERSION, "projects": {}}, "unsupported-preference-schema"
    return payload, None


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
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
        os.replace(temporary, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class AutonomyStatus:
    schema_version: int
    project_id: str
    project_name: str
    resolved_root: str
    repository_fingerprint: str | None
    level: int
    name: str
    summary: str
    source: str
    preference_path: str
    updated_at: str | None
    warning: str | None

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["covered_actions"] = [
            name for name, policy in ACTION_POLICIES.items() if policy.required_level <= self.level
        ]
        payload["hard_boundaries"] = sorted(HARD_BOUNDARIES)
        return payload


class AutonomyStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = (path or default_preference_path()).expanduser().resolve()
        _reject_workspace_state(self.path)

    def _capsule(self, workspace: Path) -> dict[str, Any]:
        return target_capsule(workspace.expanduser().resolve(), operation="autonomy-preference")

    def status(self, workspace: Path) -> AutonomyStatus:
        capsule = self._capsule(workspace)
        payload, warning = _read_payload(self.path)
        entry = payload["projects"].get(capsule["project_id"])
        level = 0
        source = "default-observe"
        updated_at: str | None = None
        if entry is not None:
            valid = (
                isinstance(entry, dict)
                and isinstance(entry.get("level"), int)
                and entry.get("level") in LEVELS
                and entry.get("resolved_root") == capsule["resolved_root"]
                and entry.get("repository_fingerprint") == capsule["repository_fingerprint"]
                and isinstance(entry.get("updated_at"), str)
            )
            if valid:
                level = int(entry["level"])
                updated_at = str(entry["updated_at"])
                source = "project-bound-user-preference"
            else:
                warning = "project-binding-mismatch-or-malformed-entry"
        name, summary = LEVELS[level]
        return AutonomyStatus(
            schema_version=SCHEMA_VERSION,
            project_id=capsule["project_id"],
            project_name=capsule["project_name"],
            resolved_root=capsule["resolved_root"],
            repository_fingerprint=capsule["repository_fingerprint"],
            level=level,
            name=name,
            summary=summary,
            source=source,
            preference_path=str(self.path),
            updated_at=updated_at,
            warning=warning,
        )

    def set(self, workspace: Path, level: int) -> AutonomyStatus:
        if level not in LEVELS:
            raise AutonomyError("autonomy level must be between 0 and 5")
        capsule = self._capsule(workspace)
        with _exclusive_lock(self.path):
            payload, _ = _read_payload(self.path, for_write=True)
            payload["projects"][capsule["project_id"]] = {
                "level": level,
                "project_name": capsule["project_name"],
                "resolved_root": capsule["resolved_root"],
                "repository_fingerprint": capsule["repository_fingerprint"],
                "updated_at": datetime.now(tz=UTC).isoformat(),
            }
            _atomic_write(self.path, payload)
        return self.status(workspace)

    def reset(self, workspace: Path) -> AutonomyStatus:
        capsule = self._capsule(workspace)
        with _exclusive_lock(self.path):
            payload, _ = _read_payload(self.path, for_write=True)
            payload["projects"].pop(capsule["project_id"], None)
            _atomic_write(self.path, payload)
        return self.status(workspace)


def evaluate(
    status: AutonomyStatus,
    action: str,
    *,
    endpoint: str,
    scope: str,
    target: str,
    decision: str,
    provider: str,
    override_level: int | None = None,
) -> dict[str, Any]:
    effective_level = status.level if override_level is None else override_level
    if effective_level not in LEVELS:
        raise AutonomyError("override level must be between 0 and 5")
    if action in HARD_BOUNDARIES:
        kind, reason = HARD_BOUNDARIES[action]
        return _interrupt(status, action, effective_level, kind, reason, "do not proceed without the named boundary being resolved")
    if action not in ACTION_POLICIES:
        return _interrupt(status, action, effective_level, "safety", "action category is unknown", "classify the action before proceeding")
    policy = ACTION_POLICIES[action]
    if provider == "denied":
        return _interrupt(status, action, effective_level, "provider", "provider policy denies the action", "stop; Tool Shed autonomy cannot override provider policy", policy)
    if provider == "approval-required":
        return _interrupt(status, action, effective_level, "provider", "provider-native approval is required", "use the provider's protected approval surface", policy)
    if scope != "in-scope":
        reason = "action materially expands scope" if scope == "expanded" else "action scope is unresolved"
        return _interrupt(status, action, effective_level, "authority", reason, "clarify or explicitly authorize the changed scope", policy)
    if target == "mismatch":
        return _interrupt(status, action, effective_level, "safety", "target conflicts with the verified project identity", "stop and use the explicit workspace-switch route", policy)
    if target == "unknown":
        return _interrupt(status, action, effective_level, "authority", "target is unresolved", "name and verify the target before proceeding", policy)
    if decision != "settled":
        reason = "material decision is unresolved" if decision == "material" else "multiple meaningful choices remain"
        return _interrupt(status, action, effective_level, "decision", reason, "present the alternatives and request one decision", policy)
    if ENDPOINT_RANK[endpoint] < ENDPOINT_RANK[policy.required_endpoint]:
        return _interrupt(
            status,
            action,
            effective_level,
            "authority",
            f"action requires {policy.required_endpoint} but the requested endpoint is {endpoint}",
            f"raise the requested endpoint to {policy.required_endpoint} or stop before this action",
            policy,
        )
    if effective_level < policy.required_level:
        return _interrupt(
            status,
            action,
            effective_level,
            "authority",
            f"action requires autonomy level {policy.required_level} but effective level is {effective_level}",
            f"explicitly authorize this action or set autonomy level {policy.required_level} or higher",
            policy,
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "outcome": "continue",
        "automatic": True,
        "action": action,
        "required_level": policy.required_level,
        "effective_level": effective_level,
        "endpoint": endpoint,
        "reason": "action is entailed by the active authority envelope",
        "state_tokens": "internal-concurrency-control",
        "project": {"project_id": status.project_id, "resolved_root": status.resolved_root},
    }


def _interrupt(
    status: AutonomyStatus,
    action: str,
    level: int,
    kind: str,
    reason: str,
    recommendation: str,
    policy: ActionPolicy | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "outcome": f"request_{kind}" if kind != "safety" else "fail_closed",
        "automatic": False,
        "action": action,
        "effective_level": level,
        "why": reason,
        "impact": policy.impact if policy else reason,
        "blast_radius": policy.blast_radius if policy else "cannot be safely bounded from current information",
        "rollback": policy.rollback if policy else "not established",
        "recommendation": recommendation,
        "project": {"project_id": status.project_id, "resolved_root": status.resolved_root},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--preference-path", type=Path)
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    set_parser = commands.add_parser("set")
    set_parser.add_argument("level", type=int)
    commands.add_parser("reset")
    evaluate_parser = commands.add_parser("evaluate")
    evaluate_parser.add_argument("action")
    evaluate_parser.add_argument("--endpoint", choices=sorted(ENDPOINT_RANK), default="none")
    evaluate_parser.add_argument("--scope", choices=("in-scope", "expanded", "unknown"), default="in-scope")
    evaluate_parser.add_argument("--target", choices=("none", "known", "unknown", "mismatch"), default="none")
    evaluate_parser.add_argument("--decision", choices=("settled", "ambiguous", "material"), default="settled")
    evaluate_parser.add_argument("--provider", choices=("allowed", "approval-required", "denied"), default="allowed")
    evaluate_parser.add_argument("--override-level", type=int)
    for child in commands.choices.values():
        child.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    try:
        store = AutonomyStore(args.preference_path)
        if args.command == "status":
            payload: object = store.status(workspace).as_dict()
        elif args.command == "set":
            payload = store.set(workspace, args.level).as_dict()
        elif args.command == "reset":
            payload = store.reset(workspace).as_dict()
        else:
            payload = evaluate(
                store.status(workspace),
                args.action,
                endpoint=args.endpoint,
                scope=args.scope,
                target=args.target,
                decision=args.decision,
                provider=args.provider,
                override_level=args.override_level,
            )
    except (AutonomyError, ProjectIdentityError, OSError, ValueError) as error:
        print(f"Autonomy control failed: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if isinstance(payload, dict) and "level" in payload:
            print(f"Autonomy {payload['level']} — {payload['name']}")
            print(f"Project: {payload['project_name']} ({payload['project_id']})")
            print(f"Root: {payload['resolved_root']}")
            print(f"Source: {payload['source']}")
            if payload.get("warning"):
                print(f"Warning: {payload['warning']}")
        else:
            print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
