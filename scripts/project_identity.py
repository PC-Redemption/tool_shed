#!/usr/bin/env python3
"""Create, inspect, and verify a stable Tool Shed project identity."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

try:
    from scripts import subprocess_launch
except ModuleNotFoundError:  # Direct execution: python scripts/project_identity.py
    import subprocess_launch  # type: ignore[no-redef]


SCHEMA_VERSION = 1
IDENTITY_RELATIVE_PATH = Path("work/tool-shed-project.json")
LEGACY_IDENTITY_PATHS = (Path(".tool-shed-project.json"), Path("tool_shed/project-identity.json"))


class ProjectIdentityError(ValueError):
    pass


def _git(workspace: Path, *arguments: str) -> str | None:
    result = subprocess_launch.run(
        ["git", *arguments],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def resolved_workspace(workspace: Path) -> Path:
    root = workspace.expanduser().resolve()
    if not root.is_dir():
        raise ProjectIdentityError(f"workspace does not exist: {root}")
    git_root = _git(root, "rev-parse", "--show-toplevel")
    if git_root is not None and Path(git_root).resolve() != root:
        raise ProjectIdentityError(
            f"WORKSPACE_MISMATCH: requested root {root} resolves inside Git workspace {Path(git_root).resolve()}"
        )
    return root


def identity_path(workspace: Path) -> Path:
    return resolved_workspace(workspace) / IDENTITY_RELATIVE_PATH


def _repository_fingerprint(workspace: Path) -> str | None:
    remote = _git(workspace, "config", "--get", "remote.origin.url")
    if remote:
        normalized = remote.removesuffix(".git").rstrip("/")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    git_dir = _git(workspace, "rev-parse", "--git-dir")
    if git_dir is None:
        return None
    return hashlib.sha256(str(workspace).encode("utf-8")).hexdigest()[:16]


def _validate_payload(payload: object, path: Path) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ProjectIdentityError(f"project identity must be a JSON object: {path}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ProjectIdentityError(f"unsupported project identity schema: {path}")
    project_id = payload.get("project_id")
    project_name = payload.get("project_name")
    if not isinstance(project_id, str):
        raise ProjectIdentityError(f"project identity has no project_id: {path}")
    try:
        parsed = uuid.UUID(project_id)
    except ValueError as error:
        raise ProjectIdentityError(f"project identity has malformed project_id: {path}") from error
    if str(parsed) != project_id.lower() or parsed.version != 4:
        raise ProjectIdentityError(f"project identity project_id must be a canonical UUIDv4: {path}")
    if not isinstance(project_name, str) or not project_name.strip():
        raise ProjectIdentityError(f"project identity has no project_name: {path}")
    allowed = {"schema_version", "project_id", "project_name"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ProjectIdentityError(
            f"project identity has unsupported fields ({', '.join(unknown)}): {path}"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": project_id.lower(),
        "project_name": project_name.strip(),
    }


def load_project_identity(workspace: Path) -> dict[str, Any]:
    root = resolved_workspace(workspace)
    path = root / IDENTITY_RELATIVE_PATH
    conflicts = [root / relative for relative in LEGACY_IDENTITY_PATHS if (root / relative).exists()]
    if conflicts:
        raise ProjectIdentityError(
            "conflicting project identity path(s): " + ", ".join(str(item) for item in conflicts)
        )
    if not path.is_file() or path.is_symlink():
        raise ProjectIdentityError(
            f"project identity is missing: {path}; run the workspace installer to create it"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ProjectIdentityError(f"project identity is malformed JSON: {path}: {error}") from error
    return _validate_payload(payload, path)


def _atomic_create(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            raise ProjectIdentityError(f"project identity appeared during creation: {path}")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def ensure_project_identity(workspace: Path, *, project_name: str | None = None) -> tuple[dict[str, Any], bool]:
    root = resolved_workspace(workspace)
    path = root / IDENTITY_RELATIVE_PATH
    if path.exists():
        return load_project_identity(root), False
    conflicts = [root / relative for relative in LEGACY_IDENTITY_PATHS if (root / relative).exists()]
    if conflicts:
        raise ProjectIdentityError(
            "conflicting project identity path(s): " + ", ".join(str(item) for item in conflicts)
        )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "project_id": str(uuid.uuid4()),
        "project_name": (project_name or root.name).strip() or root.name,
    }
    _atomic_create(path, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return load_project_identity(root), True


def active_campaign(workspace: Path) -> str | None:
    root = workspace / "work" / "00-campaigns" / "active"
    if not root.is_dir():
        return None
    working: list[str] = []
    for path in sorted(root.glob("*.md")):
        fields: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines()[:30]:
            if ":" in line:
                key, value = line.split(":", 1)
                fields[key.strip()] = value.strip()
        if fields.get("Status") == "working" and fields.get("Campaign ID"):
            working.append(fields["Campaign ID"])
    if len(working) > 1:
        raise ProjectIdentityError("project has multiple working campaigns")
    return working[0] if working else None


def binding_token(workspace: Path, *, operation: str = "inspection") -> str:
    root = resolved_workspace(workspace)
    identity = load_project_identity(root)
    digest = hashlib.sha256()
    for value in ("tool-shed-binding-v1", identity["project_id"], str(root), operation):
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:24]


def require_project_binding(workspace: Path, expected: str | None, *, operation: str) -> None:
    if not expected:
        raise ProjectIdentityError(
            f"mutation requires --project-binding from project_identity.py identity --operation {operation}"
        )
    actual = binding_token(workspace, operation=operation)
    if expected != actual:
        capsule = target_capsule(workspace, operation=operation)
        raise ProjectIdentityError(
            "WORKSPACE_MISMATCH: project binding does not match "
            f"{capsule['project_name']} ({capsule['project_id']}) at {capsule['resolved_root']}"
        )


def bind_state_token(
    workspace: Path,
    purpose: str,
    state_digest: str,
    *,
    allow_unidentified: bool = False,
) -> str:
    root = resolved_workspace(workspace)
    canonical = root / IDENTITY_RELATIVE_PATH
    candidates = canonical.exists() or any((root / item).exists() for item in LEGACY_IDENTITY_PATHS)
    if allow_unidentified and not candidates:
        identity = {"project_id": "unidentified"}
    else:
        identity = load_project_identity(root)
    digest = hashlib.sha256()
    for value in ("tool-shed-state-v1", identity["project_id"], str(root), purpose, state_digest):
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def target_capsule(workspace: Path, *, operation: str = "inspection") -> dict[str, Any]:
    root = resolved_workspace(workspace)
    identity = load_project_identity(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": identity["project_id"],
        "project_name": identity["project_name"],
        "resolved_root": str(root),
        "repository_fingerprint": _repository_fingerprint(root),
        "active_campaign": active_campaign(root),
        "operation": operation,
        "session_binding": binding_token(root, operation=operation),
        "identity_path": IDENTITY_RELATIVE_PATH.as_posix(),
    }


def require_path_within(workspace: Path, candidate: Path) -> Path:
    root = resolved_workspace(workspace)
    resolved = candidate.expanduser().resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ProjectIdentityError(
            f"WORKSPACE_MISMATCH: {resolved} is outside bound workspace {root}; use an explicit ts: use route"
        ) from error
    return resolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    identity = commands.add_parser("identity", help="Inspect the current project identity.")
    identity.add_argument("--operation", default="inspection")
    identity.add_argument(
        "--path",
        action="append",
        help="Verify that a referenced path remains inside the bound workspace. Repeat as needed.",
    )
    use = commands.add_parser("use", help="Verify an explicit workspace switch target.")
    use.add_argument("target")
    use.add_argument("--operation", default="workspace-switch")
    for child in commands.choices.values():
        child.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "identity":
            for value in args.path or []:
                require_path_within(Path(args.workspace), Path(value))
            payload = target_capsule(Path(args.workspace), operation=args.operation)
        else:
            target = Path(args.target).expanduser().resolve()
            payload = target_capsule(target, operation=args.operation)
            payload["switch"] = {
                "explicit": True,
                "reload_required": True,
                "fresh_target_state_required": True,
            }
    except (OSError, ProjectIdentityError) as error:
        print(f"Project identity failed: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Project: {payload['project_name']} ({payload['project_id']})")
        print(f"Resolved root: {payload['resolved_root']}")
        print(f"Repository fingerprint: {payload['repository_fingerprint'] or 'unavailable'}")
        print(f"Active campaign: {payload['active_campaign'] or 'none'}")
        print(f"Operation: {payload['operation']}")
        print(f"Session binding: {payload['session_binding']}")
        if args.command == "use":
            print("Reload the target workspace instructions and Tool Shed skill before acting.")
            print("Obtain fresh target-bound state before any mutation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
