#!/usr/bin/env python3
"""Install or update one disconnected Tool Shed snapshot safely."""

from __future__ import annotations

import argparse
import hashlib
import inspect
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

from codex_skill_sync import CodexSkillError, inspect_codex_skill, synchronize_codex_skill


DEFAULT_REPOSITORY = "https://github.com/PC-Redemption/tool_shed.git"
UPDATER_PROTOCOL = 3
DEFAULT_NETWORK_TIMEOUT_SECONDS = 120.0
DEFAULT_VALIDATION_TIMEOUT_SECONDS = 300.0
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


class UpdateError(RuntimeError):
    pass


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
    if target.is_symlink() or not target.is_dir():
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


def clone_release(
    repository: str,
    destination: Path,
    network_timeout: float,
    validation_timeout: float,
) -> tuple[str, dict[str, Any], str, str]:
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
    emit_progress("release validation")
    run(
        [sys.executable, "-B", "scripts/validate_tool_shed.py"],
        cwd=destination,
        timeout=validation_timeout,
        timeout_option="--validation-timeout",
    )
    return selected, manifest, tag_commit, content_commit


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


def backup_fingerprint(workspace: Path, target: Path) -> dict[str, str]:
    expected: dict[str, str] = {}
    if target.is_dir():
        expected.update(
            {f"tool_shed/{relative}": digest for relative, digest in snapshot_fingerprint(target).items()}
        )
    for root_name in ("work", "q&a"):
        root = workspace / root_name
        expected.update(
            {f"{root_name}/{relative}": digest for relative, digest in fingerprint_tree(root).items()}
        )
    gitignore = workspace / ".gitignore"
    if gitignore.is_file():
        expected[".gitignore"] = hashlib.sha256(gitignore.read_bytes()).hexdigest()
    return expected


def create_backup(workspace: Path, target: Path, backup: Path) -> None:
    if backup.exists():
        raise UpdateError(f"backup path already exists: {backup}")
    expected = backup_fingerprint(workspace, target)

    def exclude_runtime_artifacts(member: tarfile.TarInfo) -> tarfile.TarInfo | None:
        relative = Path(member.name.replace("\\", "/"))
        if relative.parts and relative.parts[0] == "tool_shed":
            snapshot_relative = Path(*relative.parts[1:])
            if is_snapshot_runtime_artifact(snapshot_relative):
                return None
        return member

    with tarfile.open(backup, "w") as archive:
        for source, arcname in (
            (target, "tool_shed"),
            (workspace / "work", "work"),
            (workspace / "q&a", "q&a"),
            (workspace / ".gitignore", ".gitignore"),
        ):
            if source.exists() or source.is_symlink():
                archive.add(
                    source,
                    arcname=arcname,
                    recursive=True,
                    filter=exclude_runtime_artifacts,
                )
    observed: dict[str, str] = {}
    with tarfile.open(backup, "r") as archive:
        for member in archive.getmembers():
            normalized = member.name.replace("\\", "/")
            root_name = normalized.split("/", 1)[0]
            if root_name not in {"tool_shed", "work", "q&a", ".gitignore"}:
                raise UpdateError(f"backup contains out-of-scope member: {normalized}")
            if root_name == ".gitignore" and normalized != ".gitignore":
                raise UpdateError(f"backup contains invalid .gitignore member: {normalized}")
            if not member.isfile() and not member.isdir():
                raise UpdateError(f"backup contains unsupported member type: {normalized}")
            if member.isfile():
                handle = archive.extractfile(member)
                if handle is None:
                    raise UpdateError(f"cannot verify backup member: {normalized}")
                observed[normalized] = hashlib.sha256(handle.read()).hexdigest()
    if observed != expected:
        raise UpdateError("backup content verification failed")


def safe_extract_backup(backup: Path, workspace: Path) -> None:
    with tarfile.open(backup, "r") as archive:
        members = archive.getmembers()
        for member in members:
            normalized = member.name.replace("\\", "/")
            root_name = normalized.split("/", 1)[0]
            if root_name not in {"tool_shed", "work", "q&a", ".gitignore"}:
                raise UpdateError(f"unsafe backup member: {normalized}")
            if root_name == ".gitignore" and normalized != ".gitignore":
                raise UpdateError(f"unsafe backup member: {normalized}")
            if not member.isfile() and not member.isdir():
                raise UpdateError(f"unsafe backup member type: {normalized}")
            if ".." in Path(normalized).parts:
                raise UpdateError(f"unsafe backup member: {normalized}")
            destination = (workspace / normalized).resolve()
            destination.relative_to(workspace)
        options = (
            {"filter": "fully_trusted"}
            if "filter" in inspect.signature(archive.extractall).parameters
            else {}
        )
        archive.extractall(workspace, **options)


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def restore_backup(backup: Path, workspace: Path) -> None:
    for relative in ("tool_shed", "work", "q&a", ".gitignore"):
        path = workspace / relative
        if path.exists() or path.is_symlink():
            remove_path(path)
    safe_extract_backup(backup, workspace)


def owner_content_fingerprint(workspace: Path) -> Counter[str]:
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
            if root_name == "work" and relative in excluded:
                continue
            values.append(digest)
    return Counter(values)


def contents_preserved(before: Counter[str], after: Counter[str]) -> bool:
    return all(after[digest] >= count for digest, count in before.items())


def post_install_checks(
    workspace: Path,
    target: Path,
    inject_failure: bool,
    providers: tuple[str, ...],
    provider_paths: dict[str, str],
    protocol: int,
    validation_timeout: float,
) -> dict[str, str]:
    if target.is_symlink() or not target.is_dir():
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
    results = {"version": version_result.stdout.strip()}
    installer = target / "scripts" / "install_into_workspace.py"
    if providers and not installer.is_file():
        raise UpdateError("selected release has provider metadata but no workspace installer")
    if installer.is_file():
        arguments = [
            sys.executable,
            "-B",
            str(installer),
            str(workspace),
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
        if current.is_symlink():
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
            if path.exists() or path.is_symlink():
                raise UpdateError(f"provider instruction rollback left a created path: {path}")
        elif path.is_symlink() or not path.is_file() or path.read_bytes() != content:
            raise UpdateError(f"provider instruction rollback mismatch: {path}")


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
        help="Timeout for each release or post-install validation command (default: 300 seconds).",
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    target = workspace / "tool_shed"
    work_before = fingerprint_tree(workspace / "work")
    owner_content_before = owner_content_fingerprint(workspace)
    initial_status = ""
    backup: Path | None = None
    rollback_backup: Path | None = None
    backup_before: dict[str, str] = {}
    retired: Path | None = None
    instruction_files_before: dict[str, bytes | None] = {}
    snapshot_before: dict[str, str] = {}
    installed = False
    payload: dict[str, Any] = {
        "workspace": str(workspace),
        "snapshot_path": str(target),
        "snapshot_relative_path": "tool_shed",
        "state": "failed",
    }
    try:
        if not workspace.is_dir():
            raise UpdateError(f"workspace does not exist: {workspace}")
        ensure_workspace_repository(workspace)
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
            selected, manifest, tag_commit, content_commit = clone_release(
                args.repository,
                clone,
                args.network_timeout,
                args.validation_timeout,
            )
            selected_version = str(manifest["shed_version"])
            if previous_version and version_tuple(previous_version) > version_tuple(selected_version):
                raise UpdateError(
                    f"refusing downgrade from {previous_version} to {selected_version}"
                )
            selected_protocol = minimum_updater_protocol(manifest)
            emit_progress("staging")
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
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            if mode == "existing-update":
                backup = workspace / f"tool_shed.backup-{timestamp}.tar"
                backup_before = backup_fingerprint(workspace, target)
                create_backup(workspace, target, backup)
                rollback_backup = backup
                payload["backup_path"] = str(backup)
                retired = workspace / f".tool_shed.retired-{timestamp}"
                if retired.exists():
                    raise UpdateError(f"retirement path already exists: {retired}")
                target.rename(retired)
            else:
                rollback_backup = temp / "workspace-before.tar"
                backup_before = backup_fingerprint(workspace, target)
                create_backup(workspace, target, rollback_backup)
            try:
                shutil.move(str(staged), str(target))
                installed = True
                emit_progress("post-install validation")
                payload["post_install"] = post_install_checks(
                    workspace,
                    target,
                    args.inject_post_install_failure,
                    providers,
                    provider_paths,
                    selected_protocol,
                    args.validation_timeout,
                )
                if not contents_preserved(
                    owner_content_before, owner_content_fingerprint(workspace)
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
                        )
                    codex_skill["source"] = str(installed_skill)
                    payload["codex_skill"] = codex_skill
            except Exception as install_error:
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
                        if backup_fingerprint(workspace, target) != backup_before:
                            raise UpdateError("restored workspace does not match the pre-update backup")
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
            owner_content_before, owner_content_fingerprint(workspace)
        )
        payload["work_changed"] = work_after != work_before
        check_work_tree = payload.get("post_install", {}).get("check_work_tree.py")
        payload["work_converged"] = (
            bool(json.loads(check_work_tree).get("converged"))
            if isinstance(check_work_tree, str) and check_work_tree
            else None
        )
        payload["git_status_changed"] = git(workspace, "status", "--short") != initial_status
        payload["state"] = "installed"
        emit_progress("completion")
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Tool Shed {selected_version} installed from {selected}.")
            print(f"Mode: {mode}")
            if backup:
                print(f"Verified backup retained at {backup}")
            codex_skill = payload.get("codex_skill")
            if isinstance(codex_skill, dict):
                print(f"Codex skill: {codex_skill.get('state')} at {codex_skill.get('path')}")
                if codex_skill.get("state") not in {"current", None}:
                    print(f"Safe synchronization command: {codex_skill.get('sync_command')}")
                if codex_skill.get("restart_required"):
                    print("Start a fresh Codex session to load the synchronized skill.")
            if payload.get("work_converged"):
                print("Root work/ converged to the selected release structure with owner content preserved.")
            else:
                print("Root work/ preserved; selected release did not provide a structure check.")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, UpdateError, CodexSkillError) as error:
        payload["error"] = str(error)
        payload["rollback"] = bool(rollback_backup and not installed)
        if fingerprint_tree(workspace / "work") != work_before:
            payload["work_preserved"] = False
        else:
            payload["work_preserved"] = True
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Tool Shed update failed: {error}", file=sys.stderr)
            if payload["rollback"]:
                print("Previous snapshot restored from the verified backup.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
