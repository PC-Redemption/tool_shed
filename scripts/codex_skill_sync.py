#!/usr/bin/env python3
"""Inspect and safely synchronize the user-level Codex Tool Shed skill."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Iterable


class CodexSkillError(RuntimeError):
    """Raised when the installed Codex skill cannot be inspected or replaced safely."""


RELEASE_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
TREE_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def codex_skill_path() -> Path:
    configured = os.environ.get("CODEX_HOME")
    codex_home = Path(configured).expanduser() if configured else Path.home() / ".codex"
    return codex_home.resolve() / "skills" / "tool-shed"


def fingerprint_skill(root: Path) -> dict[str, str]:
    if root.is_symlink():
        raise CodexSkillError(f"Codex skill must not be a symlink: {root}")
    if not root.exists():
        return {}
    if not root.is_dir():
        raise CodexSkillError(f"Codex skill must be a directory: {root}")
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise CodexSkillError(f"Codex skill must not contain symlinks: {path}")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if "SKILL.md" not in result:
        raise CodexSkillError(f"Codex skill has no SKILL.md: {root}")
    return result


def fingerprint_digest(fingerprint: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for relative, file_digest in sorted(fingerprint.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def load_release_skill_digests(catalog: Path) -> list[tuple[str, str]]:
    """Load compact, offline fingerprints for previously released Codex skills."""
    if not catalog.is_file():
        return []
    try:
        payload = json.loads(catalog.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CodexSkillError(f"invalid Codex skill release catalog: {error}") from error
    releases = payload.get("releases")
    if payload.get("schema_version") != 1 or not isinstance(releases, dict):
        raise CodexSkillError("invalid Codex skill release catalog schema")
    result: list[tuple[str, str]] = []
    for version, digest in releases.items():
        if not isinstance(version, str) or not RELEASE_TAG.fullmatch(version):
            raise CodexSkillError(f"invalid Codex skill release catalog version: {version!r}")
        if not isinstance(digest, str) or not TREE_DIGEST.fullmatch(digest):
            raise CodexSkillError(f"invalid Codex skill release catalog digest: {version}")
        result.append((version, digest))
    result.sort(
        key=lambda item: tuple(int(part) for part in item[0].removeprefix("v").split(".")),
        reverse=True,
    )
    return result


def inspect_codex_skill(
    source: Path,
    known_releases: Iterable[tuple[str, dict[str, str] | str]] = (),
) -> dict[str, object]:
    target = codex_skill_path()
    result: dict[str, object] = {
        "path": str(target),
        "source": str(source),
        "sync_command": (
            "python tool_shed/scripts/update_snapshot.py --workspace . "
            "--sync-codex-skill --json"
        ),
    }
    if not source.exists() or source.is_symlink() or not source.is_dir():
        result.update(
            {
                "state": "unsafe",
                "sync_safe": False,
                "detail": f"released Codex skill source is not a real directory: {source}",
            }
        )
        return result
    try:
        current = fingerprint_skill(source)
        if not target.exists() and not target.is_symlink():
            result.update({"state": "missing", "sync_safe": True})
            return result
        installed = fingerprint_skill(target)
    except (OSError, CodexSkillError) as error:
        result.update({"state": "unsafe", "sync_safe": False, "detail": str(error)})
        return result
    if installed == current:
        result.update(
            {
                "state": "current",
                "sync_safe": True,
                "tree_sha256": fingerprint_digest(installed),
            }
        )
        return result
    installed_digest = fingerprint_digest(installed)
    for version, fingerprint in known_releases:
        expected_digest = (
            fingerprint_digest(fingerprint) if isinstance(fingerprint, dict) else fingerprint
        )
        if installed_digest == expected_digest:
            result.update(
                {
                    "state": "stale-released",
                    "matched_release": version,
                    "sync_safe": True,
                    "tree_sha256": installed_digest,
                }
            )
            return result
    result.update(
        {
            "state": "modified-or-unmanaged",
            "sync_safe": False,
            "detail": "installed files do not exactly match the selected or a known released skill",
            "tree_sha256": installed_digest,
        }
    )
    return result


def synchronize_codex_skill(
    source: Path,
    inspection: dict[str, object],
    timestamp: str,
    inject_failure: bool = False,
) -> dict[str, object]:
    state = str(inspection.get("state"))
    if state == "current":
        if fingerprint_skill(source) != fingerprint_skill(Path(str(inspection["path"]))):
            raise CodexSkillError("Codex skill changed after inspection; refusing synchronization")
        return {**inspection, "changed": False, "restart_required": False}
    if state not in {"missing", "stale-released"} or not inspection.get("sync_safe"):
        detail = str(inspection.get("detail") or "installed skill is not safely replaceable")
        raise CodexSkillError(f"refusing Codex skill synchronization: {detail}")

    target = Path(str(inspection["path"]))
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    staged = parent / f".tool-shed.staged-{timestamp}"
    backup = parent.parent / "tool-shed-backups" / f"tool-shed-{timestamp}"
    if staged.exists() or staged.is_symlink():
        raise CodexSkillError(f"Codex skill staging path already exists: {staged}")
    if backup.exists() or backup.is_symlink():
        raise CodexSkillError(f"Codex skill backup path already exists: {backup}")

    source_fingerprint = fingerprint_skill(source)
    original_fingerprint = fingerprint_skill(target) if state == "stale-released" else None
    if original_fingerprint is not None and fingerprint_digest(original_fingerprint) != inspection.get(
        "tree_sha256"
    ):
        raise CodexSkillError("Codex skill changed after inspection; refusing synchronization")
    moved_to_backup = False
    installed = False
    try:
        shutil.copytree(source, staged)
        if fingerprint_skill(staged) != source_fingerprint:
            raise CodexSkillError("staged Codex skill does not match the released source")
        if state == "stale-released":
            backup.parent.mkdir(parents=True, exist_ok=True)
            target.rename(backup)
            moved_to_backup = True
            if fingerprint_skill(backup) != original_fingerprint:
                raise CodexSkillError("Codex skill backup verification failed")
        elif target.exists() or target.is_symlink():
            raise CodexSkillError(f"Codex skill target appeared during synchronization: {target}")
        staged.rename(target)
        installed = True
        if fingerprint_skill(target) != source_fingerprint:
            raise CodexSkillError("installed Codex skill does not match the released source")
        if inject_failure:
            raise CodexSkillError("injected Codex skill verification failure")
    except Exception as error:
        rollback_errors: list[str] = []
        try:
            if installed and target.exists():
                shutil.rmtree(target)
            if moved_to_backup and backup.exists():
                backup.rename(target)
                if fingerprint_skill(target) != original_fingerprint:
                    raise CodexSkillError("restored Codex skill does not match its backup")
                if backup.parent.exists() and not any(backup.parent.iterdir()):
                    backup.parent.rmdir()
        except Exception as rollback_error:
            rollback_errors.append(str(rollback_error))
        if staged.exists():
            shutil.rmtree(staged)
        message = str(error)
        if rollback_errors:
            message += "; rollback verification failed: " + "; ".join(rollback_errors)
        raise CodexSkillError(message) from error

    return {
        **inspection,
        "previous_state": state,
        "state": "current",
        "changed": True,
        "backup_path": str(backup) if moved_to_backup else None,
        "restart_required": True,
    }
