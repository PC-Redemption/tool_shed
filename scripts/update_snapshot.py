#!/usr/bin/env python3
"""Install or update one disconnected Tool Shed snapshot safely."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from codex_cli_resolver import CodexCliResolver, CodexReadiness
from codex_skill_sync import (
    CodexSkillError,
    SKILL_BACKUP_MANIFEST_SUFFIX,
    codex_skill_path,
    fingerprint_digest,
    fingerprint_skill,
    inspect_codex_skill,
    synchronize_codex_skill,
)
from project_identity import (
    IDENTITY_RELATIVE_PATH,
    LEGACY_IDENTITY_PATHS,
    ProjectIdentityError,
    binding_token,
    ensure_project_identity,
    load_project_identity,
    require_project_binding,
)
from snapshot_upgrade_state import (
    ProgressHeartbeat,
    SnapshotStateError,
    TransactionRecorder,
    ValidationCache,
    WorkspaceTransactionLock,
    classify_error,
    issue_code_for,
    validation_identity,
)


DEFAULT_REPOSITORY = "https://github.com/PC-Redemption/tool_shed.git"
UPDATER_PROTOCOL = 3
DEFAULT_NETWORK_TIMEOUT_SECONDS = 120.0
DEFAULT_VALIDATION_TIMEOUT_SECONDS = 900.0
STABLE_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
REQUIRED_PATHS = (
    "SHED_VERSION.json",
    "selection.md",
    "conventions.md",
    "existing-projects.md",
    "templates",
    "scripts",
)
IGNORED_NAMES = {".git", "work", "__pycache__", ".pytest_cache"}
BYTECODE_SUFFIXES = (".pyc", ".pyo")
BACKUP_MANIFEST_NAME = ".tool-shed-backup-manifest.json"
BACKUP_KIND = "tool-shed-workspace-backup"
DEFAULT_BACKUP_RETENTION = 2
BACKUP_NAME = re.compile(r"^tool_shed\.backup-(\d{8}T\d{6}Z(?:-[1-9][0-9]*)?)\.tar$")
WORK_DIRECTORY_MARKERS = (
    "work",
    "work/maps",
    "work/wp",
    "work/wp/active",
    "work/wp/completed",
    "work/tickets",
    "work/adr",
    "work/incidents",
    "work/runbooks",
    "work/spikes",
    "work/checklists",
    "work/inventories",
    "work/decisions",
    "work/evidence",
    "work/evidence/generated",
    "work/00-campaigns",
    "work/00-campaigns/active",
    "work/00-campaigns/completed",
    "work/00-campaigns/deferred",
    "work/00-campaigns/abandoned",
)
WORK_MUTABLE_FILES = (
    "work/tool-shed-project.json",
    "work/README.md",
    "work/index.md",
    "work/index.json",
    "work/00-campaigns/active-queue.md",
    "work/00-campaigns/completed-queue.md",
)
WORK_MUTABLE_TREES = ("work/01-q&a", "work/q&a", "q&a")


class UpdateError(RuntimeError):
    pass


_ACTIVE_PROGRESS: ProgressHeartbeat | None = None


def updater_identity() -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "SHED_VERSION.json").read_text(encoding="utf-8"))
    version = manifest.get("shed_version")
    if not isinstance(version, str) or not STABLE_TAG.fullmatch(f"v{version}"):
        raise UpdateError("updater manifest has an invalid shed_version")
    return {
        "schema_version": 1,
        "shed_version": version,
        "protocol": UPDATER_PROTOCOL,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def minimum_updater_protocol(manifest: dict[str, Any]) -> int:
    value = manifest.get("minimum_updater_protocol", 1)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise UpdateError("manifest minimum_updater_protocol must be a positive integer")
    return value


def version_check_command(script: str, shed: str, protocol: int, *, snapshot: bool) -> list[str]:
    command = [sys.executable, "-B", script, "--shed", shed, "--local-only", "--strict"]
    if protocol >= 2:
        command.extend(("--updater-protocol", str(UPDATER_PROTOCOL)))
        if snapshot:
            command.append("--snapshot")
    return command


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    timeout: float | None = None,
    timeout_option: str | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
            env=environment,
        )
    except subprocess.TimeoutExpired as error:
        option = f"; retry or increase {timeout_option}" if timeout_option else ""
        raise UpdateError(
            f"command timed out after {timeout:g} seconds{option}: {' '.join(args)}"
        ) from error
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise UpdateError(f"command failed ({result.returncode}): {' '.join(args)}\n{detail}")
    return result


def emit_progress(phase: str) -> None:
    if _ACTIVE_PROGRESS is not None:
        _ACTIVE_PROGRESS.update(phase)
    print(f"Tool Shed update: {phase}", file=sys.stderr, flush=True)


def positive_timeout(value: str) -> float:
    try:
        timeout = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("timeout must be a number of seconds") from error
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("timeout must be a positive finite number of seconds")
    return timeout


def git(cwd: Path, *args: str, check: bool = True) -> str:
    return run(["git", *args], cwd=cwd, check=check).stdout.strip()


def fingerprint_tree(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    result: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        result[path.relative_to(root).as_posix()] = digest
    return result


def is_snapshot_runtime_artifact(relative: Path) -> bool:
    return "__pycache__" in relative.parts or relative.name.endswith(BYTECODE_SUFFIXES)


def snapshot_runtime_artifacts(root: Path) -> list[str]:
    if not root.exists():
        return []
    artifacts: set[str] = set()
    for directory, names, files in os.walk(root, followlinks=False):
        current = Path(directory)
        for name in names:
            relative = (current / name).relative_to(root)
            if name == "__pycache__":
                artifacts.add(relative.as_posix())
        for name in files:
            relative = (current / name).relative_to(root)
            if is_snapshot_runtime_artifact(relative):
                artifacts.add(relative.as_posix())
    return sorted(artifacts)


def snapshot_fingerprint(root: Path) -> dict[str, str]:
    return {
        relative: digest
        for relative, digest in fingerprint_tree(root).items()
        if not is_snapshot_runtime_artifact(Path(relative))
    }


def ensure_workspace_repository(workspace: Path) -> None:
    result = run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=workspace,
        check=False,
    )
    if result.returncode:
        raise UpdateError("workspace must be inside a Git repository")
    repository = Path(result.stdout.strip()).resolve()
    if repository != workspace:
        raise UpdateError(f"workspace must be the repository root: {repository}")


def snapshot_boundary(workspace: Path, target: Path) -> str:
    if not target.exists():
        return "new-installation"
    if is_filesystem_link(target) or not target.is_dir():
        raise UpdateError(f"existing snapshot must be a real directory: {target}")
    if any(path.name == ".git" for path in target.rglob(".git")):
        raise UpdateError(f"existing snapshot contains embedded Git metadata: {target}")
    if (target / "work").exists():
        raise UpdateError(f"existing snapshot contains embedded project work: {target / 'work'}")
    relative = target.relative_to(workspace).as_posix()
    submodule = git(workspace, "ls-files", "--stage", "--", relative, check=False)
    if any(line.startswith("160000 ") for line in submodule.splitlines()):
        raise UpdateError(f"existing snapshot is registered as a Git submodule: {target}")
    return "existing-update"


def require_ignored(workspace: Path) -> None:
    for relative in ("tool_shed/", "tool_shed/README.md"):
        result = run(
            ["git", "check-ignore", "--no-index", "--", relative],
            cwd=workspace,
            check=False,
        )
        if result.returncode:
            raise UpdateError("parent repository must ignore the exact root /tool_shed/ path")


def release_validation_plan(
    repository: str,
    release: Path,
    manifest: dict[str, Any],
    content_commit: str,
) -> tuple[str, Path, str, str]:
    """Select focused validation only for an exact official attested release."""
    hashes = manifest.get("content_hashes")
    qualification = manifest.get("release_qualification")
    if (
        repository.rstrip("/") == DEFAULT_REPOSITORY.rstrip("/")
        and isinstance(hashes, dict)
        and isinstance(qualification, dict)
    ):
        full = qualification.get("full_validator")
        smoke = qualification.get("client_smoke")
        required_ci = qualification.get("required_ci")
        expected_ci = {".github/workflows/validate.yml", ".github/workflows/release.yml"}
        ci_paths = (
            {
                str(item.get("path"))
                for item in required_ci
                if isinstance(item, dict)
            }
            if isinstance(required_ci, list)
            else set()
        )
        identities = [full, smoke, *(required_ci if isinstance(required_ci, list) else [])]
        identities_valid = all(
            isinstance(item, dict)
            and isinstance(item.get("path"), str)
            and item.get("sha256") == hashes.get(item.get("path"))
            for item in identities
        )
        if (
            qualification.get("schema_version") == 1
            and qualification.get("subject_commit") == content_commit
            and qualification.get("attested_at") == manifest.get("released_at")
            and isinstance(full, dict)
            and full.get("path") == "scripts/validate_tool_shed.py"
            and isinstance(smoke, dict)
            and smoke.get("path") == "scripts/validate_snapshot_client.py"
            and ci_paths == expected_ci
            and len(required_ci) == 2
            and identities_valid
        ):
            validator = release / str(smoke["path"])
            return (
                "attested-focused-smoke",
                validator,
                str(smoke["sha256"]),
                "official-attestation",
            )

    validator = release / "scripts" / "validate_tool_shed.py"
    validator_hash = hashlib.sha256(validator.read_bytes()).hexdigest()
    reason = (
        "repository-override"
        if repository.rstrip("/") != DEFAULT_REPOSITORY.rstrip("/")
        else "missing-or-invalid-attestation"
    )
    return "full-local-validation", validator, validator_hash, reason


def clone_release(
    repository: str,
    destination: Path,
    network_timeout: float,
    validation_timeout: float,
    validation_cache: ValidationCache,
    recorder: TransactionRecorder,
) -> tuple[str, dict[str, Any], str, str, dict[str, Any]]:
    recorder.phase("clone-fetch")
    emit_progress("clone/fetch")
    run(
        [
            "git",
            "-c",
            "core.autocrlf=false",
            "clone",
            "--quiet",
            "--no-checkout",
            repository,
            str(destination),
        ],
        timeout=network_timeout,
        timeout_option="--network-timeout",
    )
    git(destination, "config", "core.autocrlf", "false")
    run(
        ["git", "fetch", "--quiet", "--tags", "--force", "origin"],
        cwd=destination,
        timeout=network_timeout,
        timeout_option="--network-timeout",
    )
    candidates: list[tuple[tuple[int, int, int], str]] = []
    for tag in git(destination, "tag", "--list").splitlines():
        match = STABLE_TAG.fullmatch(tag.strip())
        if match:
            candidates.append((tuple(int(part) for part in match.groups()), tag.strip()))
    if not candidates:
        raise UpdateError("canonical repository has no stable vMAJOR.MINOR.PATCH tag")
    _, selected = max(candidates)
    git(destination, "-c", "core.autocrlf=false", "checkout", "--quiet", "--detach", selected)
    recorder.phase("manifest-verification")
    emit_progress("manifest verification")
    manifest = json.loads((destination / "SHED_VERSION.json").read_text(encoding="utf-8"))
    version = selected.removeprefix("v")
    if manifest.get("shed_version") != version:
        raise UpdateError("manifest shed_version does not match selected release tag")
    if manifest.get("release_tag") != selected:
        raise UpdateError("manifest release_tag does not match selected release tag")
    if not manifest.get("released_at"):
        raise UpdateError("release manifest has no release timestamp")
    required_protocol = minimum_updater_protocol(manifest)
    if required_protocol > UPDATER_PROTOCOL:
        raise UpdateError(
            f"release requires updater protocol {required_protocol}, but this updater supports "
            f"protocol {UPDATER_PROTOCOL}; obtain a newer released Tool Shed updater"
        )
    tag_commit = git(destination, "rev-parse", f"{selected}^{{commit}}")
    content_commit = git(destination, "rev-parse", f"{tag_commit}^")
    if manifest.get("release_commit") != content_commit:
        raise UpdateError("manifest release_commit does not match the provenance commit parent")
    changed = git(destination, "diff", "--name-only", content_commit, tag_commit).splitlines()
    if changed != ["SHED_VERSION.json"]:
        raise UpdateError("provenance commit must change exactly SHED_VERSION.json")
    run(
        version_check_command(
            "scripts/check_shed_version.py",
            ".",
            required_protocol,
            snapshot=False,
        ),
        cwd=destination,
    )
    validation_mode, validator, validator_hash, selection_reason = release_validation_plan(
        repository,
        destination,
        manifest,
        content_commit,
    )
    cache_identity = validation_identity(
        release_commit=content_commit,
        validator_sha256=validator_hash,
    )
    cache_hit = validation_cache.lookup(cache_identity)
    recorder.phase("release-validation")
    if cache_hit:
        emit_progress(f"release validation cache hit ({validation_mode})")
    else:
        emit_progress(f"release validation ({validation_mode})")
        run(
            [sys.executable, "-B", str(validator.relative_to(destination))],
            cwd=destination,
            timeout=validation_timeout,
            timeout_option="--validation-timeout",
        )
        validation_cache.store_success(cache_identity, mode=validation_mode)
    validation_report = {
        "mode": validation_mode,
        "selection_reason": selection_reason,
        "cache": "hit" if cache_hit else "stored",
        "identity": cache_identity,
    }
    return selected, manifest, tag_commit, content_commit, validation_report


def released_skill_fingerprints(repository: Path) -> list[tuple[str, dict[str, str]]]:
    """Return exact skill fingerprints recorded by stable release manifests."""
    releases: list[tuple[str, dict[str, str]]] = []
    for tag in git(repository, "tag", "--list").splitlines():
        tag = tag.strip()
        if not STABLE_TAG.fullmatch(tag):
            continue
        manifest_result = run(
            ["git", "show", f"{tag}:SHED_VERSION.json"],
            cwd=repository,
            check=False,
        )
        if manifest_result.returncode:
            continue
        try:
            manifest = json.loads(manifest_result.stdout)
        except json.JSONDecodeError:
            continue
        if manifest.get("shed_version") != tag.removeprefix("v"):
            continue
        if manifest.get("release_tag") != tag:
            continue
        hashes = manifest.get("content_hashes")
        if not isinstance(hashes, dict):
            continue
        prefix = "skills/tool-shed/"
        fingerprint = {
            str(path).removeprefix(prefix): str(digest)
            for path, digest in hashes.items()
            if str(path).startswith(prefix)
        }
        if "SKILL.md" in fingerprint:
            releases.append((tag, fingerprint))
    releases.sort(
        key=lambda item: tuple(int(part) for part in item[0].removeprefix("v").split(".")),
        reverse=True,
    )
    return releases


def ignore_snapshot_copy(directory: str, names: list[str]) -> set[str]:
    ignored = {name for name in names if name in IGNORED_NAMES}
    ignored.update(name for name in names if name.endswith(BYTECODE_SUFFIXES))
    return ignored


def prepare_snapshot(
    source: Path,
    staged: Path,
    protocol: int,
    validation_timeout: float,
) -> None:
    shutil.copytree(source, staged, ignore=ignore_snapshot_copy)
    for relative in REQUIRED_PATHS:
        if not (staged / relative).exists():
            raise UpdateError(f"staged snapshot is missing required path: {relative}")
    if (staged / ".git").exists() or (staged / "work").exists():
        raise UpdateError("staged snapshot contains forbidden .git or work content")
    run(
        version_check_command(
            str(staged / "scripts" / "check_shed_version.py"),
            str(staged),
            protocol,
            snapshot=True,
        ),
        timeout=validation_timeout,
        timeout_option="--validation-timeout",
    )


def installed_version(target: Path) -> str | None:
    manifest = target / "SHED_VERSION.json"
    if not manifest.is_file():
        return None
    try:
        value = json.loads(manifest.read_text(encoding="utf-8")).get("shed_version")
    except (OSError, json.JSONDecodeError):
        return None
    return str(value) if STABLE_TAG.fullmatch(f"v{value}") else None


def version_tuple(value: str) -> tuple[int, int, int]:
    match = STABLE_TAG.fullmatch(f"v{value}")
    if not match:
        raise UpdateError(f"invalid installed version: {value}")
    return tuple(int(part) for part in match.groups())


def difference_summary(old: Path, new: Path) -> dict[str, dict[str, object]]:
    old_files = snapshot_fingerprint(old)
    new_files = snapshot_fingerprint(new)
    groups = {
        "added": sorted(set(new_files) - set(old_files)),
        "removed": sorted(set(old_files) - set(new_files)),
        "changed": sorted(path for path in set(old_files) & set(new_files) if old_files[path] != new_files[path]),
    }
    return {
        name: {"count": len(paths), "paths": paths[:20]}
        for name, paths in groups.items()
    }


def safe_relative_path(value: str) -> Path:
    path = Path(value.replace("\\", "/"))
    if not value or path.is_absolute() or ".." in path.parts or path.as_posix() in {"", "."}:
        raise UpdateError(f"unsafe backup scope path: {value!r}")
    return path


def is_filesystem_link(path: Path) -> bool:
    is_junction = getattr(os.path, "isjunction", lambda _: False)
    return path.is_symlink() or bool(is_junction(path))


def safe_tree_fingerprint(root: Path, *, skip_runtime: bool = False) -> dict[str, str]:
    if is_filesystem_link(root):
        raise UpdateError(f"backup scope must not be a symlink: {root}")
    if not root.exists():
        return {}
    if not root.is_dir():
        raise UpdateError(f"backup tree scope must be a directory: {root}")
    result: dict[str, str] = {}
    for directory, names, files in os.walk(root, followlinks=False):
        current = Path(directory)
        for name in names:
            path = current / name
            if is_filesystem_link(path):
                raise UpdateError(f"backup scope must not contain symlinks or junctions: {path}")
        for name in files:
            path = current / name
            if is_filesystem_link(path):
                raise UpdateError(f"backup scope must not contain symlinks or junctions: {path}")
            relative = path.relative_to(root)
            if skip_runtime and is_snapshot_runtime_artifact(relative):
                continue
            result[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def fingerprint_summary(root: Path) -> dict[str, object]:
    files = safe_tree_fingerprint(root) if root.exists() or is_filesystem_link(root) else {}
    digest = hashlib.sha256()
    size = 0
    for relative, file_digest in sorted(files.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\0")
        size += (root / relative).stat().st_size
    return {
        "file_count": len(files),
        "size_bytes": size,
        "tree_sha256": digest.hexdigest(),
    }


def work_complement_fingerprint(
    workspace: Path,
    included: list[dict[str, object]],
    excluded_roots: list[str],
) -> dict[str, str]:
    work = workspace / "work"
    files = safe_tree_fingerprint(work) if work.exists() or is_filesystem_link(work) else {}
    mutable_files = {
        str(item["path"])
        for item in included
        if item["mode"] == "file" and str(item["path"]).startswith("work/")
    }
    mutable_trees = [
        str(item["path"])
        for item in included
        if item["mode"] == "tree" and str(item["path"]).startswith("work/")
    ]
    selected: dict[str, str] = {}
    for child, digest in files.items():
        relative = f"work/{child}"
        if relative in mutable_files or any(
            relative == root or relative.startswith(root + "/")
            for root in [*mutable_trees, *excluded_roots]
        ):
            continue
        selected[relative] = digest
    return selected


def work_complement_summary(
    workspace: Path,
    included: list[dict[str, object]],
    excluded_roots: list[str],
) -> dict[str, object]:
    work = workspace / "work"
    selected = work_complement_fingerprint(workspace, included, excluded_roots)
    size = sum((workspace / relative).stat().st_size for relative in selected)
    aggregate = hashlib.sha256()
    for relative, digest in sorted(selected.items()):
        aggregate.update(relative.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(digest.encode("ascii"))
        aggregate.update(b"\0")
    return {
        "exists": work.exists(),
        "file_count": len(selected),
        "size_bytes": size,
        "tree_sha256": aggregate.hexdigest(),
    }


def generated_output_paths(workspace: Path) -> list[str]:
    paths = ["work/evidence/generated"]
    policy = workspace / ".tool-shed-policy.json"
    if policy.is_file():
        try:
            payload = json.loads(policy.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise UpdateError(f"invalid .tool-shed-policy.json: {error}") from error
        raw = (payload.get("evidence_policy") or {}).get("generated_path")
        if raw is not None:
            if not isinstance(raw, str):
                raise UpdateError("evidence_policy.generated_path must be a relative path")
            paths.append(safe_relative_path(raw).as_posix())
    return list(dict.fromkeys(paths))


def build_backup_scope(
    workspace: Path,
    target: Path,
    providers: tuple[str, ...],
    provider_paths: dict[str, str],
    *,
    source_version: str | None,
    target_version: str,
    protocol: int,
    transaction_id: str,
    additional_paths: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    if additional_paths is not None and not isinstance(additional_paths, list):
        raise UpdateError("updater_mutation_paths must be a list")
    requested: list[tuple[str, str, str]] = [
        ("tool_shed", "tree", "snapshot replacement"),
        (".gitignore", "file", "installer repository-policy convergence"),
        *[(path, "file", f"provider guidance: {provider_id}") for provider_id, path in (
            (provider_id, provider_paths[provider_id]) for provider_id in providers
        )],
        *[(path, "file", "generated work projection or guidance") for path in WORK_MUTABLE_FILES],
        *[(path, "tree", "Q&A inbox creation or legacy migration") for path in WORK_MUTABLE_TREES],
        *[(path, "directory-marker", "canonical work-tree directory creation") for path in WORK_DIRECTORY_MARKERS],
    ]
    for item in additional_paths or []:
        if not isinstance(item, dict):
            raise UpdateError("updater_mutation_paths entries must be objects")
        path = item.get("path")
        mode = item.get("mode")
        reason = item.get("reason")
        if (
            not isinstance(path, str)
            or mode not in {"file", "tree", "directory-marker"}
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            raise UpdateError(
                "updater_mutation_paths entries require path, supported mode, and reason"
            )
        requested.append((path, mode, f"release-declared expansion: {reason.strip()}"))
    priority = {"directory-marker": 0, "file": 1, "tree": 2}
    selected: dict[str, tuple[str, str]] = {}
    for raw_path, mode, reason in requested:
        relative = safe_relative_path(raw_path).as_posix()
        existing = selected.get(relative)
        if existing is None or priority[mode] > priority[existing[0]]:
            selected[relative] = (mode, reason)

    included: list[dict[str, object]] = []
    entries: dict[str, str] = {}
    estimated_size = 0
    for relative, (mode, reason) in sorted(selected.items()):
        path = workspace / relative
        if is_filesystem_link(path):
            raise UpdateError(f"backup mutation path must not be a symlink: {path}")
        existed = path.exists()
        existing_type = "absent"
        item_entries: dict[str, str] = {}
        if existed:
            if mode == "file":
                if not path.is_file():
                    raise UpdateError(f"backup file scope is not a regular file: {path}")
                existing_type = "file"
                item_entries[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
                estimated_size += path.stat().st_size
            elif mode == "tree":
                if not path.is_dir():
                    raise UpdateError(f"backup tree scope is not a directory: {path}")
                existing_type = "directory"
                tree = safe_tree_fingerprint(path, skip_runtime=relative == "tool_shed")
                for child, digest in tree.items():
                    archived = f"{relative}/{child}"
                    item_entries[archived] = digest
                    estimated_size += (path / child).stat().st_size
            else:
                if not path.is_dir():
                    raise UpdateError(f"backup directory marker is not a directory: {path}")
                existing_type = "directory"
        entries.update(item_entries)
        included.append(
            {
                "path": relative,
                "mode": mode,
                "reason": reason,
                "pre_update_type": existing_type,
                "file_count": len(item_entries),
                "size_bytes": sum((workspace / name).stat().st_size for name in item_entries),
            }
        )

    excluded: list[dict[str, object]] = []
    for relative in generated_output_paths(workspace):
        if any(
            item["mode"] == "tree"
            and (relative == item["path"] or relative.startswith(str(item["path"]) + "/"))
            for item in included
        ):
            continue
        excluded.append(
            {
                "path": relative,
                "reason": "policy-declared generated output outside installer mutation surface",
                **fingerprint_summary(workspace / relative),
            }
        )
    excluded_roots = [str(item["path"]) for item in excluded]
    excluded.append(
        {
            "path": "work",
            "selection": "outside-declared-mutation-surface",
            "reason": "owner-authored work outside installer mutation surface",
            **work_complement_summary(workspace, included, excluded_roots),
        }
    )
    return {
        "schema_version": 1,
        "kind": BACKUP_KIND,
        "transaction_id": transaction_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_version": source_version,
        "target_version": target_version,
        "updater_protocol": protocol,
        "workspace_sha256": hashlib.sha256(str(workspace.resolve()).encode("utf-8")).hexdigest(),
        "included": included,
        "excluded": excluded,
        "entries": entries,
        "estimated_archive_bytes": estimated_size,
    }


def backup_fingerprint(workspace: Path, scope: dict[str, object]) -> dict[str, object]:
    observed: dict[str, object] = {"included": {}, "excluded": {}}
    for raw in scope["included"]:
        item = dict(raw)
        relative = str(item["path"])
        mode = str(item["mode"])
        path = workspace / safe_relative_path(relative)
        if is_filesystem_link(path):
            raise UpdateError(f"backup mutation path must not be a symlink: {path}")
        if not path.exists():
            value: object = {"type": "absent"}
        elif mode == "file":
            value = {"type": "file", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        elif mode == "tree":
            value = {
                "type": "directory",
                "files": safe_tree_fingerprint(path, skip_runtime=relative == "tool_shed"),
            }
        else:
            value = {"type": "directory" if path.is_dir() else "other"}
        observed["included"][relative] = value
    for raw in scope["excluded"]:
        item = dict(raw)
        relative = str(item["path"])
        key = relative + (
            f"#{item['selection']}" if item.get("selection") else ""
        )
        if item.get("selection") == "outside-declared-mutation-surface":
            explicit_roots = [
                str(other["path"])
                for other in scope["excluded"]
                if dict(other).get("selection") is None
            ]
            observed["excluded"][key] = work_complement_fingerprint(
                workspace,
                [dict(included) for included in scope["included"]],
                explicit_roots,
            )
        else:
            observed["excluded"][key] = fingerprint_summary(workspace / relative)
    return observed


def verify_workspace_backup(backup: Path, workspace: Path | None = None) -> dict[str, object]:
    if is_filesystem_link(backup) or not backup.is_file():
        raise UpdateError(f"backup must be a regular file: {backup}")
    try:
        with tarfile.open(backup, "r") as archive:
            manifest_member = archive.getmember(BACKUP_MANIFEST_NAME)
            handle = archive.extractfile(manifest_member)
            if handle is None:
                raise UpdateError("backup manifest cannot be read")
            manifest = json.loads(handle.read().decode("utf-8"))
            if manifest.get("schema_version") != 1 or manifest.get("kind") != BACKUP_KIND:
                raise UpdateError("unsupported workspace backup manifest")
            if manifest.get("backup_name") != backup.name:
                raise UpdateError("workspace backup manifest name mismatch")
            if workspace is not None:
                expected_workspace = hashlib.sha256(
                    str(workspace.resolve()).encode("utf-8")
                ).hexdigest()
                if manifest.get("workspace_sha256") != expected_workspace:
                    raise UpdateError("workspace backup belongs to another workspace")
            expected = manifest.get("entries")
            if not isinstance(expected, dict) or not all(
                isinstance(path, str) and isinstance(digest, str)
                for path, digest in expected.items()
            ):
                raise UpdateError("workspace backup has invalid entry hashes")
            archived_roots = [
                str(item["path"])
                for item in manifest.get("included", [])
                if isinstance(item, dict)
                and item.get("pre_update_type") != "absent"
                and item.get("mode") in {"file", "tree"}
            ]
            observed: dict[str, str] = {}
            for member in archive.getmembers():
                normalized = member.name.replace("\\", "/")
                safe_relative_path(normalized)
                if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                    raise UpdateError(f"workspace backup has unsafe member type: {normalized}")
                if normalized != BACKUP_MANIFEST_NAME and not any(
                    normalized == root or normalized.startswith(root + "/")
                    for root in archived_roots
                ):
                    raise UpdateError(f"workspace backup has undeclared member: {normalized}")
                if ".git" in Path(normalized).parts:
                    raise UpdateError(f"workspace backup contains Git metadata: {normalized}")
                if member.isfile() and normalized != BACKUP_MANIFEST_NAME:
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise UpdateError(f"workspace backup member cannot be read: {normalized}")
                    observed[normalized] = hashlib.sha256(stream.read()).hexdigest()
            if observed != expected:
                raise UpdateError("workspace backup content verification failed")
            return manifest
    except (KeyError, tarfile.TarError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UpdateError(f"invalid workspace backup: {error}") from error


def create_backup(
    workspace: Path,
    backup: Path,
    scope: dict[str, object],
) -> dict[str, object]:
    if backup.exists() or is_filesystem_link(backup):
        raise UpdateError(f"backup path already exists: {backup}")
    manifest = {**scope, "backup_name": backup.name}
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")

    def archive_filter(member: tarfile.TarInfo) -> tarfile.TarInfo | None:
        relative = Path(member.name.replace("\\", "/"))
        if relative.parts and relative.parts[0] == "tool_shed":
            snapshot_relative = Path(*relative.parts[1:])
            if is_snapshot_runtime_artifact(snapshot_relative):
                return None
        return member

    try:
        with tarfile.open(backup, "w", dereference=True) as archive:
            info = tarfile.TarInfo(BACKUP_MANIFEST_NAME)
            info.size = len(manifest_bytes)
            info.mtime = int(datetime.now(timezone.utc).timestamp())
            archive.addfile(info, io.BytesIO(manifest_bytes))
            for raw in scope["included"]:
                item = dict(raw)
                if item["pre_update_type"] == "absent" or item["mode"] == "directory-marker":
                    continue
                relative = str(item["path"])
                archive.add(
                    workspace / relative,
                    arcname=relative,
                    recursive=item["mode"] == "tree",
                    filter=archive_filter,
                )
        return verify_workspace_backup(backup, workspace)
    except Exception:
        backup.unlink(missing_ok=True)
        raise


def safe_extract_backup(backup: Path, workspace: Path) -> dict[str, object]:
    manifest = verify_workspace_backup(backup, workspace)
    with tarfile.open(backup, "r") as archive:
        members = [member for member in archive.getmembers() if member.name != BACKUP_MANIFEST_NAME]
        for member in members:
            normalized = member.name.replace("\\", "/")
            destination = (workspace / safe_relative_path(normalized)).resolve()
            destination.relative_to(workspace.resolve())
        options = (
            {"filter": "fully_trusted"}
            if "filter" in inspect.signature(archive.extractall).parameters
            else {}
        )
        archive.extractall(workspace, members=members, **options)
    return manifest


def remove_path(path: Path) -> None:
    is_junction = getattr(os.path, "isjunction", lambda _: False)
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif is_junction(path):
        path.rmdir()
    elif path.is_dir():
        shutil.rmtree(path)


def restore_backup(backup: Path, workspace: Path) -> dict[str, object]:
    manifest = verify_workspace_backup(backup, workspace)
    included = [dict(item) for item in manifest["included"]]
    for item in sorted(included, key=lambda value: len(Path(str(value["path"])).parts), reverse=True):
        path = workspace / safe_relative_path(str(item["path"]))
        if item["mode"] == "directory-marker" and item["pre_update_type"] == "directory":
            continue
        if path.exists() or is_filesystem_link(path):
            remove_path(path)
    safe_extract_backup(backup, workspace)
    for item in sorted(included, key=lambda value: len(Path(str(value["path"])).parts), reverse=True):
        if item["mode"] != "directory-marker":
            continue
        path = workspace / safe_relative_path(str(item["path"]))
        if item["pre_update_type"] == "directory":
            path.mkdir(parents=True, exist_ok=True)
        elif path.exists() and path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    return manifest


def owner_content_fingerprint(
    workspace: Path,
    excluded_paths: set[str] | None = None,
) -> Counter[str]:
    excluded = {
        "index.md",
        "index.json",
        "00-campaigns/active-queue.md",
        "00-campaigns/completed-queue.md",
    }
    values: list[str] = []
    for root_name in ("work", "q&a"):
        root = workspace / root_name
        for relative, digest in fingerprint_tree(root).items():
            workspace_relative = f"{root_name}/{relative}"
            if workspace_relative in (excluded_paths or set()):
                continue
            if root_name == "work" and relative in excluded:
                continue
            if (
                root_name == "work"
                and re.fullmatch(
                    r"00-campaigns/(?:active|completed|deferred|abandoned)/[^/]+\.md",
                    relative,
                )
            ):
                text = (root / relative).read_text(encoding="utf-8")
                normalized = "\n".join(
                    line
                    for line in text.splitlines()
                    if not line.startswith("Campaign Number:")
                    and not line.startswith("Updated:")
                ).rstrip() + "\n"
                digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            values.append(digest)
    return Counter(values)


def contents_preserved(before: Counter[str], after: Counter[str]) -> bool:
    return all(after[digest] >= count for digest, count in before.items())


def campaign_convergence_report(
    workspace: Path,
    target: Path,
    *,
    include_plan: bool = False,
) -> dict[str, object]:
    campaign_root = workspace / "work" / "00-campaigns"
    command = target / "scripts" / "campaign_queue.py"
    if not campaign_root.is_dir() or not command.is_file():
        return {"supported": False, "needed": False, "findings": []}
    result = run(
        [
            sys.executable,
            "-B",
            str(command),
            "--workspace",
            str(workspace),
            "validate",
            "--json",
        ]
    )
    payload = json.loads(result.stdout)
    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise UpdateError("campaign convergence validation returned invalid findings")
    report: dict[str, object] = {
        "supported": True,
        "needed": bool(findings),
        "findings": findings,
        "state_token": payload.get("state_token"),
    }
    if include_plan and findings:
        plan_result = run(
            [
                sys.executable,
                "-B",
                str(command),
                "--workspace",
                str(workspace),
                "backfill-plan",
                "--json",
            ]
        )
        plan = json.loads(plan_result.stdout)
        mutation_paths = plan.get("mutation_paths")
        if not isinstance(mutation_paths, list) or not all(
            isinstance(path, str) and path for path in mutation_paths
        ):
            raise UpdateError("campaign convergence plan returned invalid mutation paths")
        report["plan"] = plan
    return report


def post_install_checks(
    workspace: Path,
    target: Path,
    inject_failure: bool,
    providers: tuple[str, ...],
    provider_paths: dict[str, str],
    protocol: int,
    validation_timeout: float,
) -> dict[str, object]:
    if is_filesystem_link(target) or not target.is_dir():
        raise UpdateError("installed snapshot is not a real directory")
    if (target / ".git").exists() or (target / "work").exists():
        raise UpdateError("installed snapshot contains forbidden .git or work content")
    require_ignored(workspace)
    version_result = run(
        version_check_command(
            str(target / "scripts" / "check_shed_version.py"),
            str(target),
            protocol,
            snapshot=True,
        ),
        timeout=validation_timeout,
        timeout_option="--validation-timeout",
    )
    results: dict[str, object] = {"version": version_result.stdout.strip()}
    installer = target / "scripts" / "install_into_workspace.py"
    if providers and not installer.is_file():
        raise UpdateError("selected release has provider metadata but no workspace installer")
    if installer.is_file():
        arguments = [
            sys.executable,
            "-B",
            str(installer),
            str(workspace),
            "--project-binding",
            binding_token(workspace, operation="workspace-install"),
        ]
        for provider_id in providers:
            arguments.extend(("--provider", provider_id))
        install_result = run(
            arguments,
            cwd=workspace,
            timeout=validation_timeout,
            timeout_option="--validation-timeout",
        )
        results["workspace_convergence"] = install_result.stdout.strip()
        results["provider_guidance"] = install_result.stdout.strip()
        for provider_id in providers:
            guidance_path = workspace / provider_paths[provider_id]
            if not guidance_path.is_file():
                raise UpdateError(f"provider guidance was not created: {guidance_path}")
            guidance = guidance_path.read_text(encoding="utf-8")
            if "BEGIN TOOL SHED ROUTING GUIDANCE" not in guidance:
                raise UpdateError(f"provider guidance is missing portable routing: {guidance_path}")
    campaign_before = campaign_convergence_report(workspace, target)
    campaign_result: dict[str, object] = {"before": campaign_before, "applied": False}
    if campaign_before["needed"]:
        state_token = campaign_before.get("state_token")
        if not isinstance(state_token, str) or not state_token:
            raise UpdateError("campaign convergence requires a valid pre-migration state token")
        migration = run(
            [
                sys.executable,
                "-B",
                str(target / "scripts" / "campaign_queue.py"),
                "--workspace",
                str(workspace),
                "backfill-numbers",
                "--expect",
                state_token,
                "--project-binding",
                binding_token(workspace, operation="campaign-queue"),
                "--json",
            ],
            timeout=validation_timeout,
            timeout_option="--validation-timeout",
        )
        campaign_result["applied"] = True
        campaign_result["migration"] = json.loads(migration.stdout)
        indexer = target / "scripts" / "update_work_index.py"
        if indexer.is_file():
            run(
                [sys.executable, "-B", str(indexer), "--workspace", str(workspace), "--no-preflight"],
                timeout=validation_timeout,
                timeout_option="--validation-timeout",
            )
    campaign_after = campaign_convergence_report(workspace, target)
    campaign_result["after"] = campaign_after
    if campaign_after["needed"]:
        raise UpdateError(
            "campaign convergence remains incomplete: "
            + "; ".join(str(item) for item in campaign_after["findings"])
        )
    results["campaign_convergence"] = campaign_result
    if inject_failure:
        raise UpdateError("injected post-install verification failure")
    optional_checks = (
        ("workspace_preflight.py", "--workspace", str(workspace), "--json"),
        ("check_work_tree.py", "--workspace", str(workspace), "--json"),
        ("check_stale_paths.py", "--workspace", str(workspace)),
        ("review_work_state.py", "--workspace", str(workspace)),
    )
    for script, *arguments in optional_checks:
        path = target / "scripts" / script
        if path.is_file():
            result = run(
                [sys.executable, "-B", str(path), *arguments],
                cwd=workspace,
                timeout=validation_timeout,
                timeout_option="--validation-timeout",
            )
            results[script] = result.stdout.strip()
    if "check_work_tree.py" in results:
        convergence = json.loads(results["check_work_tree.py"])
        if not convergence.get("converged"):
            raise UpdateError(
                "workspace work structure did not converge: "
                + "; ".join(convergence.get("findings") or ["unknown finding"])
            )
    runtime_artifacts = snapshot_runtime_artifacts(target)
    if runtime_artifacts:
        raise UpdateError(
            "post-install validation generated Python runtime artifacts: "
            + ", ".join(runtime_artifacts[:20])
        )
    return results


def load_staged_providers(staged: Path) -> dict[str, dict[str, Any]]:
    path = staged / "adapters" / "providers.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise UpdateError(f"invalid staged provider manifest: {error}") from error
    if payload.get("schema_version") != 1 or not isinstance(payload.get("providers"), dict):
        raise UpdateError("invalid staged provider manifest schema")
    providers: dict[str, dict[str, Any]] = {}
    seen_paths: set[str] = set()
    for provider_id, raw_config in payload["providers"].items():
        if not isinstance(provider_id, str) or not provider_id or not isinstance(raw_config, dict):
            raise UpdateError("invalid staged provider entry")
        relative = str(raw_config.get("instruction_path") or "")
        relative_path = Path(relative)
        if not relative or relative_path.is_absolute() or ".." in relative_path.parts:
            raise UpdateError(f"unsafe staged provider instruction path: {provider_id}")
        normalized = relative_path.as_posix()
        if normalized in seen_paths:
            raise UpdateError(f"duplicate staged provider instruction path: {normalized}")
        seen_paths.add(normalized)
        providers[provider_id] = dict(raw_config)
    return providers


def safe_instruction_path(workspace: Path, relative: str) -> Path:
    path = workspace / relative
    current = path
    while current != workspace:
        if is_filesystem_link(current):
            raise UpdateError(f"provider instruction path must not traverse a symlink: {current}")
        current = current.parent
    try:
        path.resolve(strict=False).relative_to(workspace.resolve())
    except ValueError as error:
        raise UpdateError(f"provider instruction path escapes the workspace: {path}") from error
    if path.exists() and not path.is_file():
        raise UpdateError(f"provider instruction target is not a regular file: {path}")
    return path


def select_providers(
    workspace: Path,
    available: dict[str, dict[str, Any]],
    requested: list[str] | None,
) -> tuple[str, ...]:
    if not available:
        if requested and requested != ["auto"]:
            raise UpdateError("selected release does not support provider adapters")
        return ()
    values = requested or ["auto"]
    if "all" in values:
        if len(values) != 1:
            raise UpdateError("--provider all cannot be combined with another provider")
        return tuple(sorted(available))
    if "auto" in values:
        if len(values) != 1:
            raise UpdateError("--provider auto cannot be combined with another provider")
        detected: list[str] = []
        for provider_id, config in available.items():
            path = safe_instruction_path(workspace, str(config["instruction_path"]))
            if path.is_file() and "BEGIN TOOL SHED" in path.read_text(encoding="utf-8"):
                detected.append(provider_id)
        if detected:
            return tuple(sorted(detected))
        if "codex" not in available:
            raise UpdateError("provider auto-detection found no existing guidance and no codex default")
        return ("codex",)
    unknown = sorted(set(values) - set(available))
    if unknown:
        raise UpdateError("unknown provider adapter(s): " + ", ".join(unknown))
    return tuple(dict.fromkeys(values))


def capture_instruction_files(
    workspace: Path,
    providers: tuple[str, ...],
    provider_paths: dict[str, str],
) -> dict[str, bytes | None]:
    captured: dict[str, bytes | None] = {}
    for provider_id in providers:
        relative = provider_paths[provider_id]
        path = safe_instruction_path(workspace, relative)
        captured[relative] = path.read_bytes() if path.is_file() else None
    return captured


def restore_instruction_files(workspace: Path, captured: dict[str, bytes | None]) -> None:
    for relative, content in captured.items():
        path = workspace / relative
        if content is None:
            path.unlink(missing_ok=True)
            parent = path.parent
            while parent != workspace and parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)


def verify_instruction_files(workspace: Path, captured: dict[str, bytes | None]) -> None:
    for relative, content in captured.items():
        path = workspace / relative
        if content is None:
            if path.exists() or is_filesystem_link(path):
                raise UpdateError(f"provider instruction rollback left a created path: {path}")
        elif is_filesystem_link(path) or not path.is_file() or path.read_bytes() != content:
            raise UpdateError(f"provider instruction rollback mismatch: {path}")


def positive_integer(value: str) -> int:
    try:
        result = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must be a positive integer") from error
    if result < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return result


def backup_retention_policy(workspace: Path, requested: int | None) -> tuple[int, str]:
    if requested is not None:
        return requested, "command-line"
    policy_path = workspace / ".tool-shed-policy.json"
    if policy_path.is_file():
        try:
            payload = json.loads(policy_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise UpdateError(f"invalid .tool-shed-policy.json: {error}") from error
        backup_policy = payload.get("backup_policy")
        if backup_policy is not None:
            if not isinstance(backup_policy, dict):
                raise UpdateError("backup_policy must be an object")
            retention = backup_policy.get("retention", DEFAULT_BACKUP_RETENTION)
            if not isinstance(retention, int) or isinstance(retention, bool) or retention < 1:
                raise UpdateError("backup_policy.retention must be an integer of at least 1")
            return retention, "workspace-policy"
    return DEFAULT_BACKUP_RETENTION, "default"


def parse_manifest_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise UpdateError("backup manifest has no creation timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise UpdateError("backup manifest has invalid creation timestamp") from error
    if parsed.tzinfo is None:
        raise UpdateError("backup manifest creation timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def verify_skill_backup(backup: Path) -> dict[str, object]:
    if is_filesystem_link(backup) or not backup.is_dir():
        raise UpdateError(f"skill backup must be a real directory: {backup}")
    manifest_path = backup.with_suffix(SKILL_BACKUP_MANIFEST_SUFFIX)
    if is_filesystem_link(manifest_path) or not manifest_path.is_file():
        raise UpdateError("skill backup has no verified sidecar manifest")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise UpdateError(f"invalid skill backup manifest: {error}") from error
    if manifest.get("schema_version") != 1 or manifest.get("kind") != "tool-shed-skill-backup":
        raise UpdateError("unsupported skill backup manifest")
    if manifest.get("backup_name") != backup.name:
        raise UpdateError("skill backup manifest name mismatch")
    parse_manifest_timestamp(manifest.get("created_at"))
    if manifest.get("tree_sha256") != fingerprint_digest(fingerprint_skill(backup)):
        raise UpdateError("skill backup content verification failed")
    return manifest


def retention_partition(
    verified: list[dict[str, object]],
    retention: int,
    current: Path | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    ordered = sorted(
        verified,
        key=lambda item: (parse_manifest_timestamp(item["manifest"]["created_at"]), str(item["path"])),
        reverse=True,
    )
    protected: list[dict[str, object]] = []
    if current is not None:
        current_resolved = current.resolve()
        protected = [item for item in ordered if Path(str(item["path"])).resolve() == current_resolved]
        if len(protected) != 1:
            raise UpdateError("current transaction backup was not uniquely verified")
    retained = list(protected)
    for item in ordered:
        if item in retained:
            continue
        if len(retained) >= retention:
            break
        retained.append(item)
    removable = [item for item in ordered if item not in retained]
    return retained, removable


def inventory_workspace_backups(
    workspace: Path,
    *,
    retention: int,
    current: Path | None,
    prune: bool,
    preview: bool,
) -> dict[str, object]:
    verified: list[dict[str, object]] = []
    unknown: list[dict[str, object]] = []
    for path in sorted(workspace.glob("tool_shed.backup-*.tar")):
        item = {"path": str(path), "bytes": path.stat().st_size if path.is_file() else 0}
        if not BACKUP_NAME.fullmatch(path.name):
            unknown.append({**item, "reason": "noncanonical filename"})
            continue
        try:
            manifest = verify_workspace_backup(path, workspace)
            parse_manifest_timestamp(manifest.get("created_at"))
        except (OSError, UpdateError) as error:
            unknown.append({**item, "reason": str(error)})
            continue
        verified.append({**item, "manifest": manifest})
    retained, removable = retention_partition(verified, retention, current)
    pruned: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    if prune and not preview:
        for item in removable:
            path = Path(str(item["path"]))
            try:
                if is_filesystem_link(path) or path.resolve().parent != workspace.resolve():
                    raise UpdateError(f"refusing out-of-root backup deletion: {path}")
                path.unlink()
                pruned.append({"path": str(path), "bytes": int(item["bytes"])})
            except (OSError, UpdateError) as error:
                errors.append({"path": str(path), "error": str(error)})
    retained_paths = [
        {"path": str(item["path"]), "bytes": int(item["bytes"])} for item in retained
    ]
    protected = [] if current is None else [str(current)]
    return {
        "retention": retention,
        "preview": preview,
        "pruning_enabled": prune,
        "deletion_is_irreversible": True,
        "protected": protected,
        "retained": retained_paths,
        "removable": [
            {"path": str(item["path"]), "bytes": int(item["bytes"])} for item in removable
        ],
        "pruned": pruned,
        "unknown": unknown,
        "errors": errors,
        "reclaimed_bytes": sum(int(item["bytes"]) for item in pruned),
    }


def inventory_skill_backups(
    *,
    retention: int,
    current: Path | None,
    prune: bool,
    preview: bool,
) -> dict[str, object]:
    root = codex_skill_path().parents[1] / "tool-shed-backups"
    verified: list[dict[str, object]] = []
    unknown: list[dict[str, object]] = []
    if root.exists() and (is_filesystem_link(root) or not root.is_dir()):
        raise UpdateError(f"skill backup root must be a real directory: {root}")
    if root.is_dir():
        for path in sorted(root.iterdir()):
            if path.suffix == SKILL_BACKUP_MANIFEST_SUFFIX:
                continue
            item = {
                "path": str(path),
                "bytes": 0,
            }
            if not re.fullmatch(r"tool-shed-\d{8}T\d{6}Z(?:-[1-9][0-9]*)?", path.name):
                unknown.append({**item, "reason": "noncanonical skill backup name"})
                continue
            try:
                manifest = verify_skill_backup(path)
            except (OSError, CodexSkillError, UpdateError) as error:
                unknown.append({**item, "reason": str(error)})
                continue
            item["bytes"] = sum(
                    child.stat().st_size
                    for child in path.rglob("*")
                    if child.is_file() and not is_filesystem_link(child)
            ) + path.with_suffix(SKILL_BACKUP_MANIFEST_SUFFIX).stat().st_size
            verified.append({**item, "manifest": manifest})
        for manifest_path in sorted(root.glob(f"*{SKILL_BACKUP_MANIFEST_SUFFIX}")):
            backup_path = manifest_path.with_suffix("")
            if not backup_path.exists():
                unknown.append(
                    {
                        "path": str(manifest_path),
                        "bytes": manifest_path.stat().st_size,
                        "reason": "orphaned skill backup manifest",
                    }
                )
    retained, removable = retention_partition(verified, retention, current)
    pruned: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    if prune and not preview:
        for item in removable:
            path = Path(str(item["path"]))
            manifest_path = path.with_suffix(SKILL_BACKUP_MANIFEST_SUFFIX)
            try:
                if is_filesystem_link(path) or path.resolve().parent != root.resolve():
                    raise UpdateError(f"refusing out-of-root skill backup deletion: {path}")
                shutil.rmtree(path)
                manifest_path.unlink()
                pruned.append({"path": str(path), "bytes": int(item["bytes"])})
            except (OSError, UpdateError) as error:
                errors.append({"path": str(path), "error": str(error)})
    return {
        "backup_root": str(root),
        "retention": retention,
        "preview": preview,
        "pruning_enabled": prune,
        "deletion_is_irreversible": True,
        "protected": [] if current is None else [str(current)],
        "retained": [
            {"path": str(item["path"]), "bytes": int(item["bytes"])} for item in retained
        ],
        "removable": [
            {"path": str(item["path"]), "bytes": int(item["bytes"])} for item in removable
        ],
        "pruned": pruned,
        "unknown": unknown,
        "errors": errors,
        "reclaimed_bytes": sum(int(item["bytes"]) for item in pruned),
    }


def unique_transaction_timestamp(workspace: Path) -> str:
    base = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    skill_root = codex_skill_path().parents[1] / "tool-shed-backups"
    for suffix in range(0, 10_000):
        value = base if suffix == 0 else f"{base}-{suffix}"
        workspace_backup = workspace / f"tool_shed.backup-{value}.tar"
        skill_backup = skill_root / f"tool-shed-{value}"
        if not workspace_backup.exists() and not skill_backup.exists() and not skill_backup.with_suffix(
            SKILL_BACKUP_MANIFEST_SUFFIX
        ).exists():
            return value
    raise UpdateError("cannot allocate a unique updater transaction timestamp")


def codex_cli_readiness_report() -> dict[str, Any]:
    """Return install-compatible, non-blocking local Codex readiness."""

    resolution = CodexCliResolver().resolve()
    report = resolution.as_dict()
    report["codex_cli"] = (
        "INVALID" if resolution.readiness is CodexReadiness.INVALID_EXECUTABLE
        else ("AVAILABLE" if resolution.found else "NOT FOUND")
    )
    report["discovery"] = (
        "OpenAI VS Code extension"
        if resolution.source and resolution.source.value == "openai_vscode_extension"
        else (resolution.source.value.replace("_", " ").title() if resolution.source else "not found")
    )
    report["compatibility"] = {
        CodexReadiness.AVAILABLE_QUALIFIED: "QUALIFIED VERSION",
        CodexReadiness.AVAILABLE_UNQUALIFIED: "UNQUALIFIED VERSION",
        CodexReadiness.APP_SERVER_UNAVAILABLE: "APP SERVER UNAVAILABLE",
        CodexReadiness.INVALID_EXECUTABLE: "INVALID EXECUTABLE",
        CodexReadiness.NOT_FOUND: "NOT INSTALLED OR NOT FOUND",
    }[resolution.readiness]
    return report


def print_codex_cli_readiness(report: dict[str, Any]) -> None:
    print(f"Codex CLI: {report['codex_cli']}")
    print(f"Discovery: {report['discovery']}")
    print(f"Executable: {report['executable'] or 'not detected'}")
    print(f"Installed Codex: {report['version'] or 'not detected'}")
    print(
        "App Server: "
        f"{'AVAILABLE' if report['readiness'] in {'available_qualified', 'available_unqualified'} else 'UNAVAILABLE'}"
    )
    print(f"Compatibility: {report['compatibility']}")
    if report["readiness"] not in {"available_qualified", "available_unqualified"}:
        print("Normal GUI Tool Shed operation remains available; only App Server execution is unavailable.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".", help="Exact project repository root.")
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY, help="Canonical Git repository URL or path.")
    parser.add_argument("--json", action="store_true", help="Write a structured result.")
    parser.add_argument(
        "--network-timeout",
        type=positive_timeout,
        default=DEFAULT_NETWORK_TIMEOUT_SECONDS,
        metavar="SECONDS",
        help="Timeout for each clone or fetch command (default: 120 seconds).",
    )
    parser.add_argument(
        "--validation-timeout",
        type=positive_timeout,
        default=DEFAULT_VALIDATION_TIMEOUT_SECONDS,
        metavar="SECONDS",
        help="Timeout for each release or post-install validation command (default: 900 seconds).",
    )
    parser.add_argument(
        "--provider",
        action="append",
        help=(
            "Refresh this provider's native Tool Shed guidance. Repeat, use 'all', or use the "
            "default 'auto' to detect existing Tool Shed guidance and otherwise select codex."
        ),
    )
    parser.add_argument(
        "--inject-post-install-failure",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--inject-after-replacement-failure",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--inject-codex-sync-failure",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--sync-codex-skill",
        action="store_true",
        help=(
            "Synchronize the user-level Codex skill when it is missing or exactly matches a "
            "known Tool Shed release. Modified or unmanaged skills are never overwritten."
        ),
    )
    parser.add_argument(
        "--backup-retention",
        type=positive_integer,
        default=None,
        metavar="COUNT",
        help=(
            "Retain COUNT newest verified updater-owned backups after success, including the "
            "current rollback archive (default: 2 or workspace policy)."
        ),
    )
    parser.add_argument(
        "--no-prune-backups",
        action="store_true",
        help="Classify backups after success but do not remove obsolete verified archives.",
    )
    parser.add_argument(
        "--prune-preview",
        action="store_true",
        help="Read-only backup inventory showing exact retention and removal sets; do not update.",
    )
    parser.add_argument(
        "--project-binding",
        help="Current binding from project_identity.py identity --operation update-snapshot.",
    )
    return parser.parse_args()


def main() -> int:
    global _ACTIVE_PROGRESS
    args = parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    target = workspace / "tool_shed"
    transaction_id = os.urandom(12).hex()
    recorder = TransactionRecorder(transaction_id, updater=updater_identity())
    progress = ProgressHeartbeat(sys.stderr)
    transaction_lock: WorkspaceTransactionLock | None = None
    progress.start()
    _ACTIVE_PROGRESS = progress
    work_before = fingerprint_tree(workspace / "work")
    owner_content_exclusions: set[str] = set()
    owner_content_before = owner_content_fingerprint(workspace)
    initial_status = ""
    backup: Path | None = None
    rollback_backup: Path | None = None
    backup_before: dict[str, object] = {}
    backup_scope: dict[str, object] | None = None
    retired: Path | None = None
    instruction_files_before: dict[str, bytes | None] = {}
    snapshot_before: dict[str, str] = {}
    current_skill_backup: Path | None = None
    installed = False
    payload: dict[str, Any] = {
        "workspace": str(workspace),
        "snapshot_path": str(target),
        "snapshot_relative_path": "tool_shed",
        "state": "failed",
        "stage": "workspace-preflight",
        "transaction_id": transaction_id,
        "transaction_report": str(recorder.path),
    }
    try:
        recorder.phase("workspace-preflight")
        if not workspace.is_dir():
            raise UpdateError(f"workspace does not exist: {workspace}")
        ensure_workspace_repository(workspace)
        retention, retention_source = backup_retention_policy(
            workspace, args.backup_retention
        )
        payload["backup_retention_policy"] = {
            "retention": retention,
            "source": retention_source,
        }
        if args.prune_preview:
            payload["backup_retention"] = {
                "workspace": inventory_workspace_backups(
                    workspace,
                    retention=retention,
                    current=None,
                    prune=True,
                    preview=True,
                ),
                "codex_skill": inventory_skill_backups(
                    retention=retention,
                    current=None,
                    prune=True,
                    preview=True,
                ),
            }
            payload["state"] = "prune-preview"
            if args.json:
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                workspace_report = payload["backup_retention"]["workspace"]
                skill_report = payload["backup_retention"]["codex_skill"]
                print("Backup pruning preview; no files were changed.")
                print(
                    f"Workspace: {len(workspace_report['retained'])} retained, "
                    f"{len(workspace_report['removable'])} removable, "
                    f"{len(workspace_report['unknown'])} preserved unknown."
                )
                print(
                    f"Codex skill: {len(skill_report['retained'])} retained, "
                    f"{len(skill_report['removable'])} removable, "
                    f"{len(skill_report['unknown'])} preserved unknown."
                )
            return 0
        transaction_lock = WorkspaceTransactionLock(workspace, transaction_id)
        transaction_lock.acquire()
        payload["transaction_lock"] = "acquired"
        identity_exists = (workspace / IDENTITY_RELATIVE_PATH).exists() or any(
            (workspace / relative).exists() for relative in LEGACY_IDENTITY_PATHS
        )
        if identity_exists:
            load_project_identity(workspace)
            require_project_binding(
                workspace,
                args.project_binding,
                operation="update-snapshot",
            )
        payload["project_identity_preexisting"] = identity_exists
        initial_status = git(workspace, "status", "--short")
        mode = snapshot_boundary(workspace, target)
        snapshot_before = snapshot_fingerprint(target)
        require_ignored(workspace)
        payload["mode"] = mode
        previous_version = installed_version(target) if target.exists() else None
        payload["previous_version"] = previous_version
        with tempfile.TemporaryDirectory(prefix="tool-shed-update-") as temporary:
            temp = Path(temporary)
            clone = temp / "release"
            staged = temp / "staged"
            payload["stage"] = "release-selection"
            recorder.phase("release-selection")
            selected, manifest, tag_commit, content_commit, release_validation = clone_release(
                args.repository,
                clone,
                args.network_timeout,
                args.validation_timeout,
                ValidationCache(),
                recorder,
            )
            payload["release_validation"] = release_validation
            selected_version = str(manifest["shed_version"])
            if previous_version and version_tuple(previous_version) > version_tuple(selected_version):
                raise UpdateError(
                    f"refusing downgrade from {previous_version} to {selected_version}"
                )
            selected_protocol = minimum_updater_protocol(manifest)
            emit_progress("staging")
            payload["stage"] = "staging"
            recorder.phase("staging")
            prepare_snapshot(clone, staged, selected_protocol, args.validation_timeout)
            staged_providers = load_staged_providers(staged)
            providers = select_providers(workspace, staged_providers, args.provider)
            known_skill_releases = released_skill_fingerprints(clone)
            provider_paths = {
                provider_id: str(config["instruction_path"])
                for provider_id, config in staged_providers.items()
            }
            instruction_files_before = capture_instruction_files(
                workspace, providers, provider_paths
            )
            payload.update(
                {
                    "selected_tag": selected,
                    "selected_version": selected_version,
                    "tag_commit": tag_commit,
                    "content_commit": content_commit,
                    "difference": difference_summary(target, staged) if target.exists() else None,
                    "providers": list(providers),
                }
            )
            inspect_codex = args.sync_codex_skill or "codex" in providers
            if "codex" in providers:
                payload["codex_cli_readiness"] = codex_cli_readiness_report()
            if inspect_codex:
                staged_skill = staged / "skills" / "tool-shed"
                codex_skill = inspect_codex_skill(staged_skill, known_skill_releases)
                codex_skill["source"] = str(target / "skills" / "tool-shed")
                payload["codex_skill"] = codex_skill
                if args.sync_codex_skill and not codex_skill.get("sync_safe"):
                    raise UpdateError(
                        "Codex skill synchronization was requested but is unsafe: "
                        + str(codex_skill.get("detail") or codex_skill.get("state"))
                    )
            current_campaigns = campaign_convergence_report(workspace, target)
            if (
                previous_version == selected_version
                and target.is_dir()
                and snapshot_fingerprint(target) == snapshot_fingerprint(staged)
                and not args.sync_codex_skill
                and not current_campaigns["needed"]
                and identity_exists
            ):
                payload["installed_version"] = selected_version
                payload["canonical_manifest_match"] = True
                payload["work_preserved"] = True
                payload["excluded_paths_preserved"] = True
                payload["work_changed"] = False
                payload["work_converged"] = None
                payload["git_status_changed"] = False
                payload["state"] = "current"
                payload["stage"] = "complete"
                recorder.phase("complete")
                payload["backup_retention"] = {
                    "workspace": inventory_workspace_backups(
                        workspace,
                        retention=retention,
                        current=None,
                        prune=not args.no_prune_backups,
                        preview=False,
                    ),
                    "codex_skill": inventory_skill_backups(
                        retention=retention,
                        current=None,
                        prune=not args.no_prune_backups,
                        preview=False,
                    ),
                }
                emit_progress("completion")
                if args.json:
                    print(json.dumps(payload, indent=2, sort_keys=True))
                else:
                    print(f"Tool Shed {selected_version} is already current; no backup was created.")
                    if "codex_cli_readiness" in payload:
                        print_codex_cli_readiness(payload["codex_cli_readiness"])
                return 0
            timestamp = unique_transaction_timestamp(workspace)
            payload["stage"] = "campaign-convergence-plan"
            recorder.phase("campaign-convergence-plan")
            staged_campaigns = campaign_convergence_report(
                workspace,
                staged,
                include_plan=True,
            )
            payload["campaign_convergence_plan"] = staged_campaigns
            dynamic_mutation_paths: list[dict[str, str]] = []
            raw_plan = staged_campaigns.get("plan")
            if isinstance(raw_plan, dict):
                for relative in raw_plan.get("mutation_paths", []):
                    owner_content_exclusions.add(str(relative))
                    dynamic_mutation_paths.append(
                        {
                            "path": str(relative),
                            "mode": "file",
                            "reason": "campaign-number inbound reference convergence",
                        }
                    )
            owner_content_before = owner_content_fingerprint(
                workspace,
                owner_content_exclusions,
            )
            declared_mutation_paths = manifest.get("updater_mutation_paths")
            if declared_mutation_paths is None:
                declared_mutation_paths = []
            if not isinstance(declared_mutation_paths, list):
                raise UpdateError("updater_mutation_paths must be a list")
            payload["stage"] = "backup"
            recorder.phase("backup")
            backup_scope = build_backup_scope(
                workspace,
                target,
                providers,
                provider_paths,
                source_version=previous_version,
                target_version=selected_version,
                protocol=selected_protocol,
                transaction_id=transaction_id,
                additional_paths=[*declared_mutation_paths, *dynamic_mutation_paths],
            )
            payload["backup_scope"] = backup_scope
            emit_progress(
                "backup scope: "
                f"{len(backup_scope['included'])} included path(s), "
                f"{len(backup_scope['excluded'])} excluded path(s), "
                f"estimated {backup_scope['estimated_archive_bytes']} bytes"
            )
            if mode == "existing-update":
                backup = workspace / f"tool_shed.backup-{timestamp}.tar"
                backup_before = backup_fingerprint(workspace, backup_scope)
                create_backup(workspace, backup, backup_scope)
                rollback_backup = backup
                payload["backup_path"] = str(backup)
                retired = workspace / f".tool_shed.retired-{timestamp}"
                if retired.exists():
                    raise UpdateError(f"retirement path already exists: {retired}")
                target.rename(retired)
            else:
                rollback_backup = temp / "workspace-before.tar"
                temporary_scope = {**backup_scope, "workspace_sha256": hashlib.sha256(
                    str(workspace.resolve()).encode("utf-8")
                ).hexdigest()}
                backup_before = backup_fingerprint(workspace, temporary_scope)
                create_backup(workspace, rollback_backup, temporary_scope)
            try:
                identity, identity_created = ensure_project_identity(workspace)
                payload["project_identity"] = {
                    **identity,
                    "created": identity_created,
                    "path": IDENTITY_RELATIVE_PATH.as_posix(),
                }
                payload["stage"] = "snapshot-replacement"
                recorder.phase("snapshot-replacement")
                shutil.move(str(staged), str(target))
                installed = True
                if args.inject_after_replacement_failure:
                    raise UpdateError("injected failure after snapshot replacement")
                emit_progress("post-install validation")
                payload["stage"] = "post-install-validation"
                recorder.phase("post-install-validation")
                payload["post_install"] = post_install_checks(
                    workspace,
                    target,
                    args.inject_post_install_failure,
                    providers,
                    provider_paths,
                    selected_protocol,
                    args.validation_timeout,
                )
                if backup_scope is None:
                    raise UpdateError("post-install verification has no declared backup scope")
                scope_after = backup_fingerprint(workspace, backup_scope)
                if scope_after["excluded"] != backup_before["excluded"]:
                    before_excluded = dict(backup_before["excluded"])
                    after_excluded = dict(scope_after["excluded"])
                    changed = sorted(
                        key
                        for key in set(before_excluded) | set(after_excluded)
                        if before_excluded.get(key) != after_excluded.get(key)
                    )
                    complement_key = "work#outside-declared-mutation-surface"
                    before_complement = before_excluded.get(complement_key)
                    after_complement = after_excluded.get(complement_key)
                    if (
                        isinstance(before_complement, dict)
                        and isinstance(after_complement, dict)
                        and before_complement != after_complement
                    ):
                        changed = sorted(
                            path
                            for path in set(before_complement) | set(after_complement)
                            if before_complement.get(path) != after_complement.get(path)
                        )
                    raise UpdateError(
                        "post-install transaction changed paths outside the declared mutation surface: "
                        + ", ".join(changed[:5])
                    )
                payload["excluded_paths_preserved"] = True
                if not contents_preserved(
                    owner_content_before,
                    owner_content_fingerprint(workspace, owner_content_exclusions),
                ):
                    raise UpdateError(
                        "owner-authored work content was not preserved during convergence"
                    )
                if inspect_codex:
                    installed_skill = target / "skills" / "tool-shed"
                    codex_skill = inspect_codex_skill(installed_skill, known_skill_releases)
                    if args.sync_codex_skill:
                        codex_skill = synchronize_codex_skill(
                            installed_skill,
                            codex_skill,
                            timestamp,
                            args.inject_codex_sync_failure,
                            transaction_id=transaction_id,
                            target_version=selected_version,
                        )
                        raw_skill_backup = codex_skill.get("backup_path")
                        if raw_skill_backup:
                            current_skill_backup = Path(str(raw_skill_backup))
                    codex_skill["source"] = str(installed_skill)
                    payload["codex_skill"] = codex_skill
            except Exception as install_error:
                failed_stage = str(payload.get("stage", "unknown"))
                payload["failed_stage"] = failed_stage
                payload["stage"] = "rollback"
                recorder.phase("rollback")
                rollback_errors: list[str] = []
                try:
                    restore_instruction_files(workspace, instruction_files_before)
                    verify_instruction_files(workspace, instruction_files_before)
                except Exception as error:
                    rollback_errors.append(f"provider guidance: {error}")
                try:
                    installed = False
                    if rollback_backup is not None:
                        restore_backup(rollback_backup, workspace)
                        if backup_scope is None:
                            raise UpdateError("rollback has no declared backup scope")
                        if backup_fingerprint(workspace, backup_scope) != backup_before:
                            raise UpdateError("restored workspace does not match the pre-update backup")
                        if fingerprint_tree(workspace / "work") != work_before:
                            raise UpdateError(
                                "rollback changed work outside the declared mutation surface"
                            )
                    if retired is not None and retired.exists():
                        shutil.rmtree(retired)
                except Exception as error:
                    rollback_errors.append(f"workspace: {error}")
                if rollback_errors:
                    raise UpdateError(
                        f"{install_error}; rollback verification failed: " + "; ".join(rollback_errors)
                    ) from install_error
                raise
            if retired is not None and retired.exists():
                shutil.rmtree(retired)
        payload["installed_version"] = selected_version
        payload["canonical_manifest_match"] = True
        work_after = fingerprint_tree(workspace / "work")
        payload["work_preserved"] = contents_preserved(
            owner_content_before,
            owner_content_fingerprint(workspace, owner_content_exclusions),
        )
        payload["work_changed"] = work_after != work_before
        check_work_tree = payload.get("post_install", {}).get("check_work_tree.py")
        payload["work_converged"] = (
            bool(json.loads(check_work_tree).get("converged"))
            if isinstance(check_work_tree, str) and check_work_tree
            else None
        )
        payload["git_status_changed"] = git(workspace, "status", "--short") != initial_status
        payload["backup_retention"] = {
            "workspace": inventory_workspace_backups(
                workspace,
                retention=retention,
                current=backup,
                prune=not args.no_prune_backups,
                preview=False,
            ),
            "codex_skill": inventory_skill_backups(
                retention=retention,
                current=current_skill_backup,
                prune=not args.no_prune_backups,
                preview=False,
            ),
        }
        payload["state"] = "installed"
        payload["stage"] = "complete"
        recorder.phase("complete")
        emit_progress("completion")
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Tool Shed {selected_version} installed from {selected}.")
            print(f"Mode: {mode}")
            if backup:
                print(f"Verified immediate rollback backup retained at {backup}")
            retention_report = payload["backup_retention"]
            workspace_retention = retention_report["workspace"]
            skill_retention = retention_report["codex_skill"]
            print(
                "Backup retention: "
                f"workspace retained {len(workspace_retention['retained'])}, "
                f"pruned {len(workspace_retention['pruned'])}; "
                f"Codex skill retained {len(skill_retention['retained'])}, "
                f"pruned {len(skill_retention['pruned'])}; "
                f"{workspace_retention['reclaimed_bytes'] + skill_retention['reclaimed_bytes']} "
                "bytes reclaimed. Backup deletion is irreversible."
            )
            codex_skill = payload.get("codex_skill")
            if isinstance(codex_skill, dict):
                print(f"Codex skill: {codex_skill.get('state')} at {codex_skill.get('path')}")
                if codex_skill.get("state") not in {"current", None}:
                    print(f"Safe synchronization command: {codex_skill.get('sync_command')}")
                if codex_skill.get("restart_required"):
                    print("Start a fresh Codex session to load the synchronized skill.")
            if "codex_cli_readiness" in payload:
                print_codex_cli_readiness(payload["codex_cli_readiness"])
            if payload.get("work_converged"):
                print("Root work/ converged to the selected release structure with owner content preserved.")
            else:
                print("Root work/ preserved; selected release did not provide a structure check.")
        return 0
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        UpdateError,
        ProjectIdentityError,
        CodexSkillError,
        SnapshotStateError,
    ) as error:
        payload["error"] = str(error)
        payload["error_class"] = classify_error(error)
        if "failed_stage" not in payload:
            payload["failed_stage"] = recorder.current_phase or str(
                payload.get("stage", "unknown")
            )
        payload["rollback"] = bool(rollback_backup and not installed)
        if fingerprint_tree(workspace / "work") != work_before:
            payload["work_preserved"] = False
        else:
            payload["work_preserved"] = True
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Tool Shed update failed: {error}", file=sys.stderr)
            print(f"Failure stage: {payload['failed_stage']}", file=sys.stderr)
            if payload["rollback"]:
                print("Previous snapshot restored from the verified backup.", file=sys.stderr)
        return 1
    finally:
        metadata = {
            key: payload[key]
            for key in ("selected_tag", "selected_version", "content_commit", "release_validation")
            if key in payload
        }
        if payload.get("state") in {"installed", "current", "prune-preview"}:
            rollback_outcome = "not-required"
        elif payload.get("rollback"):
            rollback_outcome = "restored"
        elif rollback_backup is None:
            rollback_outcome = "not-started"
        else:
            rollback_outcome = "not-restored"
        try:
            issue_code = issue_code_for(
                state=str(payload.get("state", "failed")),
                error_class=str(payload.get("error_class")) if payload.get("error_class") else None,
                rollback_outcome=rollback_outcome,
            )
            payload["issue_code"] = issue_code
            recorder.finish(
                str(payload.get("state", "failed")),
                failed_stage=str(payload.get("failed_stage")) if payload.get("failed_stage") else None,
                error_class=str(payload.get("error_class")) if payload.get("error_class") else None,
                rollback_outcome=rollback_outcome,
                metadata=metadata or None,
                issue_code=issue_code,
            )
            if payload.get("state") not in {"installed", "current", "prune-preview"} and not args.json:
                print(f"Issue code: {issue_code}", file=sys.stderr)
                print(f"Sanitized transaction report: {recorder.path}", file=sys.stderr)
        finally:
            if transaction_lock is not None:
                transaction_lock.release()
            progress.stop()
            _ACTIVE_PROGRESS = None


if __name__ == "__main__":
    raise SystemExit(main())
