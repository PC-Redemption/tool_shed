#!/usr/bin/env python3
"""Track and verify this project's web, Windows, and Linux release lanes."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

try:
    from scripts import subprocess_launch
except ModuleNotFoundError:  # Direct execution: python work/runbooks/release_lanes.py
    import subprocess_launch  # type: ignore[no-redef]

from project_identity import require_project_binding, resolved_workspace


SCHEMA_VERSION = 1
KIND = "tool-shed-project-release-lanes"
OPERATION = "release-lanes"
LANES = ("web", "windows", "linux")
STAGES = ("development", "production")
TERMINAL_STATUSES = {"verified", "manual-closed"}
RELEASE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
FULL_COMMIT = re.compile(r"[0-9a-f]{40}")
TARGETS = {
    "web": {
        "development": "tsrookarocom-dev@sup.local:/home/jon/docker/ts.rookaro.com-dev",
        "production": "tsrookarocom@sup.local:/home/jon/docker/ts.rookaro.com",
    },
    "windows": {
        "development": r"PC-Redemption/ts_windows_test_bed@GOGETTER:E:\dev\ts_windows_test_bed",
        "production": "github-release:tool-shed-windows-install-client",
    },
    "linux": {
        "development": "PC-Redemption/ts_linux_test_bed@sup.local:/home/jon/dev/ts_linux_test_bed",
        "production": "github-release:tool-shed-linux-install-client",
    },
}


class ReleaseLaneError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _git(workspace: Path, *arguments: str) -> str:
    result = subprocess_launch.run(
        ["git", *arguments],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise ReleaseLaneError(result.stderr.strip() or "Git operation failed")
    return result.stdout.strip()


def resolve_commit(workspace: Path, value: str) -> str:
    commit = _git(workspace, "rev-parse", "--verify", f"{value}^{{commit}}")
    if not FULL_COMMIT.fullmatch(commit):
        raise ReleaseLaneError(f"Git did not resolve a full commit for {value}")
    return commit


def _is_ancestor(workspace: Path, older: str, newer: str) -> bool:
    result = subprocess_launch.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        cwd=workspace,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def manifest_path(workspace: Path, release_id: str, supplied: str | None = None) -> Path:
    root = resolved_workspace(workspace)
    if not RELEASE_ID.fullmatch(release_id):
        raise ReleaseLaneError("release ID must use only letters, numbers, dot, underscore, or dash")
    evidence_root = root / "work" / "evidence" / "release-lanes"
    candidate = Path(supplied) if supplied else evidence_root / f"{release_id}.json"
    if not candidate.is_absolute():
        candidate = root / candidate
    for parent in (candidate, *candidate.parents):
        if parent == root.parent:
            break
        if parent.is_symlink():
            raise ReleaseLaneError(f"release-lane path cannot use symlinks: {parent}")
        if parent == root:
            break
    resolved = candidate.resolve()
    try:
        resolved.relative_to(evidence_root.resolve())
    except ValueError as error:
        raise ReleaseLaneError(
            f"release-lane manifest must remain under {evidence_root}"
        ) from error
    if resolved.suffix != ".json":
        raise ReleaseLaneError("release-lane manifest must use a .json suffix")
    return resolved


def _empty_stage(target: str) -> dict[str, Any]:
    return {
        "status": "open",
        "target": target,
        "source_commit": None,
        "artifact": None,
        "evidence": [],
        "actor": None,
        "recorded_at": None,
        "authorization_ref": None,
        "reason": None,
    }


def new_manifest(release_id: str) -> dict[str, Any]:
    required = list(LANES)
    stamp = _now()
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "release_id": release_id,
        "candidate_commit": None,
        "required_lanes": required,
        "revision": 1,
        "created_at": stamp,
        "updated_at": stamp,
        "lanes": {
            lane: {stage: _empty_stage(TARGETS[lane][stage]) for stage in STAGES}
            for lane in LANES
        },
    }


def _validate_stage(value: object, *, lane: str, stage: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReleaseLaneError(f"{lane}.{stage} must be an object")
    allowed = {
        "status",
        "target",
        "source_commit",
        "artifact",
        "evidence",
        "actor",
        "recorded_at",
        "authorization_ref",
        "reason",
    }
    if set(value) != allowed:
        raise ReleaseLaneError(f"{lane}.{stage} has missing or unsupported fields")
    status = value["status"]
    if status not in {"open", *TERMINAL_STATUSES}:
        raise ReleaseLaneError(f"{lane}.{stage} has unsupported status {status!r}")
    if value["target"] != TARGETS[lane][stage]:
        raise ReleaseLaneError(f"{lane}.{stage} target does not match the project contract")
    if not isinstance(value["evidence"], list) or not all(
        isinstance(item, str) and item.strip() for item in value["evidence"]
    ):
        raise ReleaseLaneError(f"{lane}.{stage} evidence must be a list of non-empty strings")
    nullable_strings = (
        "source_commit",
        "artifact",
        "actor",
        "recorded_at",
        "authorization_ref",
        "reason",
    )
    if any(value[key] is not None and not isinstance(value[key], str) for key in nullable_strings):
        raise ReleaseLaneError(f"{lane}.{stage} contains a malformed scalar")
    if status == "open":
        if any(value[key] is not None for key in nullable_strings) or value["evidence"]:
            raise ReleaseLaneError(f"open lane {lane}.{stage} cannot contain closure evidence")
    else:
        commit = value["source_commit"]
        if not isinstance(commit, str) or not FULL_COMMIT.fullmatch(commit):
            raise ReleaseLaneError(f"{lane}.{stage} must name a full source commit")
        for key in ("artifact", "actor", "recorded_at"):
            if not isinstance(value[key], str) or not value[key].strip():
                raise ReleaseLaneError(f"{lane}.{stage} terminal record requires {key}")
        if not value["evidence"]:
            raise ReleaseLaneError(f"{lane}.{stage} terminal record requires evidence")
        if status == "manual-closed" and (
            not value["authorization_ref"] or not value["reason"]
        ):
            raise ReleaseLaneError(
                f"manual closure of {lane}.{stage} requires authorization_ref and reason"
            )
        if status == "verified" and (value["authorization_ref"] or value["reason"]):
            raise ReleaseLaneError(
                f"verified lane {lane}.{stage} cannot carry manual-closure fields"
            )
    return dict(value)


def validate_manifest(value: object, *, expected_release_id: str | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReleaseLaneError("release-lane manifest must be an object")
    allowed = {
        "schema_version",
        "kind",
        "release_id",
        "candidate_commit",
        "required_lanes",
        "revision",
        "created_at",
        "updated_at",
        "lanes",
    }
    if set(value) != allowed:
        raise ReleaseLaneError("release-lane manifest has missing or unsupported fields")
    if value["schema_version"] != SCHEMA_VERSION or value["kind"] != KIND:
        raise ReleaseLaneError("unsupported release-lane manifest schema")
    release_id = value["release_id"]
    if not isinstance(release_id, str) or not RELEASE_ID.fullmatch(release_id):
        raise ReleaseLaneError("release-lane manifest has an invalid release ID")
    if expected_release_id is not None and release_id != expected_release_id:
        raise ReleaseLaneError("manifest release ID does not match the requested release ID")
    candidate = value["candidate_commit"]
    if candidate is not None and (not isinstance(candidate, str) or not FULL_COMMIT.fullmatch(candidate)):
        raise ReleaseLaneError("candidate_commit must be null or a full commit")
    required = value["required_lanes"]
    if (
        not isinstance(required, list)
        or not required
        or len(required) != len(set(required))
        or any(item not in LANES for item in required)
    ):
        raise ReleaseLaneError("required_lanes must be a unique non-empty subset of known lanes")
    if not isinstance(value["revision"], int) or value["revision"] < 1:
        raise ReleaseLaneError("revision must be a positive integer")
    if not all(isinstance(value[key], str) and value[key] for key in ("created_at", "updated_at")):
        raise ReleaseLaneError("manifest timestamps must be non-empty strings")
    lanes = value["lanes"]
    if not isinstance(lanes, dict) or set(lanes) != set(LANES):
        raise ReleaseLaneError("manifest must contain exactly web, windows, and linux lanes")
    normalized_lanes: dict[str, Any] = {}
    for lane in LANES:
        if not isinstance(lanes[lane], dict) or set(lanes[lane]) != set(STAGES):
            raise ReleaseLaneError(f"lane {lane} must contain development and production")
        normalized_lanes[lane] = {
            stage: _validate_stage(lanes[lane][stage], lane=lane, stage=stage)
            for stage in STAGES
        }
    normalized = dict(value)
    normalized["lanes"] = normalized_lanes
    return normalized


def load(path: Path, *, release_id: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ReleaseLaneError(f"release-lane manifest does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ReleaseLaneError(f"release-lane manifest is malformed JSON: {error}") from error
    return validate_manifest(value, expected_release_id=release_id)


def _write(path: Path, value: dict[str, Any], *, expected: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(f".{path.name}.lock")
    try:
        lock_descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise ReleaseLaneError(f"CONCURRENT_WRITE: manifest lock already exists: {lock}") from error
    try:
        with os.fdopen(lock_descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"pid={os.getpid()}\n")
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            current = load(path, release_id=value["release_id"])
            current_digest = digest(current)
            if expected is None:
                raise ReleaseLaneError(f"mutation requires --expect {current_digest}")
            if expected != current_digest:
                raise ReleaseLaneError(
                    f"STALE_WRITE: expected {expected}, current manifest digest is {current_digest}"
                )
        elif expected is not None:
            raise ReleaseLaneError("STALE_WRITE: manifest does not exist but --expect was supplied")
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    finally:
        lock.unlink(missing_ok=True)


def _touch(value: dict[str, Any]) -> None:
    value["revision"] += 1
    value["updated_at"] = _now()


def _blockers(
    workspace: Path,
    value: dict[str, Any],
    *,
    phase: str,
    release_commit: str | None = None,
) -> tuple[list[str], str | None]:
    blockers: list[str] = []
    candidate = value["candidate_commit"]
    if candidate is None:
        blockers.append("candidate commit is not bound")
    for lane in value["required_lanes"]:
        development = value["lanes"][lane]["development"]
        if development["status"] not in TERMINAL_STATUSES:
            blockers.append(f"{lane}.development is open")
        elif candidate is not None and development["source_commit"] != candidate:
            blockers.append(f"{lane}.development source commit does not match candidate")
    resolved_release: str | None = None
    if phase in {"work5-preflight", "work5-complete"}:
        if release_commit is None:
            blockers.append("release commit is required for Work5 verification")
        else:
            resolved_release = resolve_commit(workspace, release_commit)
            if candidate is not None and not _is_ancestor(workspace, candidate, resolved_release):
                blockers.append("candidate commit is not an ancestor of the release commit")
    if phase in {"status", "work5-complete"}:
        for lane in value["required_lanes"]:
            production = value["lanes"][lane]["production"]
            if production["status"] not in TERMINAL_STATUSES:
                blockers.append(f"{lane}.production is open")
            elif resolved_release is not None and production["source_commit"] != resolved_release:
                blockers.append(f"{lane}.production source commit does not match release commit")
            elif (
                phase == "status"
                and candidate is not None
                and not _is_ancestor(workspace, candidate, production["source_commit"])
            ):
                blockers.append(f"{lane}.production source commit does not descend from candidate")
    return blockers, resolved_release


def report(
    workspace: Path,
    value: dict[str, Any],
    *,
    phase: str = "status",
    release_commit: str | None = None,
) -> dict[str, Any]:
    blockers, resolved_release = _blockers(
        workspace, value, phase=phase, release_commit=release_commit
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-project-release-lane-status",
        "release_id": value["release_id"],
        "manifest_digest": digest(value),
        "manifest_revision": value["revision"],
        "candidate_commit": value["candidate_commit"],
        "release_commit": resolved_release,
        "phase": phase,
        "ready": not blockers,
        "blockers": blockers,
        "required_lanes": {
            lane: {
                stage: value["lanes"][lane][stage]["status"] for stage in STAGES
            }
            for lane in value["required_lanes"]
        },
    }


def initialize(
    workspace: Path,
    *,
    release_id: str,
    supplied_path: str | None,
    project_binding: str | None,
) -> tuple[Path, dict[str, Any]]:
    root = resolved_workspace(workspace)
    require_project_binding(root, project_binding, operation=OPERATION)
    path = manifest_path(root, release_id, supplied_path)
    if path.exists():
        raise ReleaseLaneError(f"release-lane manifest already exists: {path}")
    value = new_manifest(release_id)
    _write(path, value, expected=None)
    return path, value


def bind_candidate(
    workspace: Path,
    value: dict[str, Any],
    *,
    commitish: str,
    expected: str | None,
    project_binding: str | None,
    path: Path,
) -> dict[str, Any]:
    root = resolved_workspace(workspace)
    require_project_binding(root, project_binding, operation=OPERATION)
    commit = resolve_commit(root, commitish)
    if value["candidate_commit"] not in {None, commit}:
        raise ReleaseLaneError(
            "manifest is already bound to a different candidate; initialize a new release ID"
        )
    if value["candidate_commit"] == commit:
        current = load(path, release_id=value["release_id"])
        if expected != digest(current):
            raise ReleaseLaneError(
                f"STALE_WRITE: expected {expected}, current manifest digest is {digest(current)}"
            )
        return value
    updated = copy.deepcopy(value)
    updated["candidate_commit"] = commit
    _touch(updated)
    _write(path, updated, expected=expected)
    return updated


def record_lane(
    workspace: Path,
    value: dict[str, Any],
    *,
    lane: str,
    stage: str,
    status: str,
    source_commitish: str,
    artifact: str,
    evidence: list[str],
    actor: str,
    authorization_ref: str | None,
    reason: str | None,
    expected: str | None,
    project_binding: str | None,
    path: Path,
) -> dict[str, Any]:
    root = resolved_workspace(workspace)
    require_project_binding(root, project_binding, operation=OPERATION)
    if lane not in value["required_lanes"]:
        raise ReleaseLaneError(f"lane {lane} is not required by this manifest")
    commit = resolve_commit(root, source_commitish)
    if stage == "development" and commit != value["candidate_commit"]:
        raise ReleaseLaneError("development source commit must equal the bound candidate commit")
    if not artifact.strip() or not actor.strip() or not evidence or any(not item.strip() for item in evidence):
        raise ReleaseLaneError("terminal lane records require artifact, actor, and evidence")
    if status == "manual-closed" and (not authorization_ref or not reason):
        raise ReleaseLaneError("manual closure requires --authorization-ref and --reason")
    if status == "verified" and (authorization_ref or reason):
        raise ReleaseLaneError("verified records cannot use manual-closure fields")
    updated = copy.deepcopy(value)
    updated["lanes"][lane][stage] = {
        "status": status,
        "target": TARGETS[lane][stage],
        "source_commit": commit,
        "artifact": artifact.strip(),
        "evidence": [item.strip() for item in evidence],
        "actor": actor.strip(),
        "recorded_at": _now(),
        "authorization_ref": authorization_ref.strip() if authorization_ref else None,
        "reason": reason.strip() if reason else None,
    }
    _touch(updated)
    validate_manifest(updated, expected_release_id=updated["release_id"])
    _write(path, updated, expected=expected)
    return updated


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)

    def common(child: argparse.ArgumentParser) -> None:
        child.add_argument("--release-id", required=True)
        child.add_argument("--manifest")
        child.add_argument("--json", action="store_true", default=argparse.SUPPRESS)

    init = commands.add_parser("init", help="Create one release-lane manifest.")
    common(init)
    init.add_argument("--project-binding", required=True)

    status = commands.add_parser("status", help="Report current lane state.")
    common(status)

    bind = commands.add_parser("bind", help="Bind the post-Work3 candidate commit.")
    common(bind)
    bind.add_argument("--commit", required=True)
    bind.add_argument("--expect", required=True)
    bind.add_argument("--project-binding", required=True)

    record = commands.add_parser("record", help="Record verified or manual lane closure.")
    common(record)
    record.add_argument("--lane", choices=LANES, required=True)
    record.add_argument("--stage", choices=STAGES, required=True)
    record.add_argument("--status", choices=sorted(TERMINAL_STATUSES), required=True)
    record.add_argument("--source-commit", required=True)
    record.add_argument("--artifact", required=True)
    record.add_argument("--evidence", action="append", required=True)
    record.add_argument("--actor", required=True)
    record.add_argument("--authorization-ref")
    record.add_argument("--reason")
    record.add_argument("--expect", required=True)
    record.add_argument("--project-binding", required=True)

    verify = commands.add_parser("verify", help="Fail closed unless the selected phase is ready.")
    common(verify)
    verify.add_argument("--phase", choices=("work3", "work5-preflight", "work5-complete"), required=True)
    verify.add_argument("--release-commit")
    return parser


def _print(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"Release lanes: {payload['release_id']} (revision {payload['manifest_revision']})")
    print(f"Manifest digest: {payload['manifest_digest']}")
    print(f"Ready: {'yes' if payload['ready'] else 'no'}")
    for lane, states in payload["required_lanes"].items():
        print(f"{lane}: development={states['development']}, production={states['production']}")
    for blocker in payload["blockers"]:
        print(f"BLOCKED: {blocker}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.workspace)
    try:
        path = manifest_path(root, args.release_id, args.manifest)
        if args.command == "init":
            path, value = initialize(
                root,
                release_id=args.release_id,
                supplied_path=args.manifest,
                project_binding=args.project_binding,
            )
        else:
            value = load(path, release_id=args.release_id)
            if args.command == "bind":
                value = bind_candidate(
                    root,
                    value,
                    commitish=args.commit,
                    expected=args.expect,
                    project_binding=args.project_binding,
                    path=path,
                )
            elif args.command == "record":
                value = record_lane(
                    root,
                    value,
                    lane=args.lane,
                    stage=args.stage,
                    status=args.status,
                    source_commitish=args.source_commit,
                    artifact=args.artifact,
                    evidence=args.evidence,
                    actor=args.actor,
                    authorization_ref=args.authorization_ref,
                    reason=args.reason,
                    expected=args.expect,
                    project_binding=args.project_binding,
                    path=path,
                )
        phase = args.phase if args.command == "verify" else "status"
        release_commit = args.release_commit if args.command == "verify" else None
        payload = report(root, value, phase=phase, release_commit=release_commit)
        payload["manifest"] = str(path.relative_to(resolved_workspace(root)))
    except (OSError, ReleaseLaneError, ValueError) as error:
        print(f"Release lanes failed: {error}", file=sys.stderr)
        return 2
    _print(payload, as_json=args.json)
    if args.command == "verify" and not payload["ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
