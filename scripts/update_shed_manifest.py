#!/usr/bin/env python3
"""Refresh or verify SHED_VERSION.json content hashes."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "SHED_VERSION.json"
CODEX_SKILL_CATALOG = ROOT / "adapters" / "codex-skill-releases.json"
TRACKED_ROOT_FILES = (
    ".gitattributes",
    ".dockerignore",
    "README.md",
    "requirements-dashboard.txt",
    "selection.md",
    "conventions.md",
    "existing-projects.md",
)
TRACKED_GLOBS = (
    ".github/workflows/*.yml",
    "adapters/**/*.json",
    "adapters/**/*.md",
    "docs/*.md",
    "dashboard/**/*",
    "scripts/*.py",
    "scripts/*.js",
    "scripts/*.ps1",
    "scripts/*.sh",
    "schemas/**/*.json",
    "skills/tool-shed/SKILL.md",
    "skills/tool-shed/agents/*.yaml",
    "skills/tool-shed/references/**/*.md",
    "site/**/*",
    "templates/*.md",
    "templates/*.json",
)
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
CURRENT_UPDATER_PROTOCOL = 4
RELEASE_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
TREE_DIGEST = re.compile(r"^[0-9a-f]{64}$")
QUALIFICATION_PATHS = (
    "scripts/validate_tool_shed.py",
    "scripts/validate_snapshot_client.py",
    ".github/workflows/validate.yml",
    ".github/workflows/release.yml",
)


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tracked_paths() -> list[Path]:
    paths = {ROOT / relative for relative in TRACKED_ROOT_FILES}
    for pattern in TRACKED_GLOBS:
        paths.update(ROOT.glob(pattern))
    return sorted(
        path
        for path in paths
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )


def current_hashes(*, overrides: dict[Path, bytes] | None = None) -> dict[str, str]:
    replacements = overrides or {}
    return {
        path.relative_to(ROOT).as_posix(): (
            hashlib.sha256(replacements[path]).hexdigest()
            if path in replacements
            else hash_file(path)
        )
        for path in tracked_paths()
    }


def fingerprint_digest(fingerprint: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for relative, file_digest in sorted(fingerprint.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Git command failed")
    return result.stdout.strip()


def release_skill_catalog(*, exclude_tag: str | None = None) -> dict[str, object]:
    releases: dict[str, str] = {}
    for tag in git_output("tag", "--list").splitlines():
        tag = tag.strip()
        if tag == exclude_tag or not RELEASE_TAG.fullmatch(tag):
            continue
        try:
            manifest = json.loads(git_output("show", f"{tag}:SHED_VERSION.json"))
        except (RuntimeError, json.JSONDecodeError):
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
        if "SKILL.md" in fingerprint and all(
            TREE_DIGEST.fullmatch(digest) for digest in fingerprint.values()
        ):
            releases[tag] = fingerprint_digest(fingerprint)
    return {"schema_version": 1, "releases": dict(sorted(releases.items()))}


def load_skill_catalog() -> dict[str, object]:
    try:
        payload = json.loads(CODEX_SKILL_CATALOG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid Codex skill release catalog: {error}") from error
    releases = payload.get("releases")
    if payload.get("schema_version") != 1 or not isinstance(releases, dict):
        raise ValueError("invalid Codex skill release catalog schema")
    for tag, digest in releases.items():
        if not isinstance(tag, str) or not RELEASE_TAG.fullmatch(tag):
            raise ValueError(f"invalid Codex skill release catalog version: {tag!r}")
        if not isinstance(digest, str) or not TREE_DIGEST.fullmatch(digest):
            raise ValueError(f"invalid Codex skill release catalog digest: {tag}")
    return payload


def exact_git_root() -> bool:
    try:
        return Path(git_output("rev-parse", "--show-toplevel")).resolve() == ROOT
    except (RuntimeError, OSError):
        return False


def json_bytes(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def release_qualification(
    hashes: dict[str, str],
    *,
    release_commit: str | None,
    released_at: str | None,
) -> dict[str, object] | None:
    if not release_commit:
        return None
    missing = [path for path in QUALIFICATION_PATHS if path not in hashes]
    if missing:
        raise ValueError(
            "release qualification paths are missing from content hashes: "
            + ", ".join(missing)
        )
    return {
        "schema_version": 1,
        "subject_commit": release_commit,
        "attested_at": released_at,
        "full_validator": {
            "path": "scripts/validate_tool_shed.py",
            "sha256": hashes["scripts/validate_tool_shed.py"],
        },
        "client_smoke": {
            "path": "scripts/validate_snapshot_client.py",
            "sha256": hashes["scripts/validate_snapshot_client.py"],
        },
        "required_ci": [
            {
                "path": ".github/workflows/validate.yml",
                "sha256": hashes[".github/workflows/validate.yml"],
            },
            {
                "path": ".github/workflows/release.yml",
                "sha256": hashes[".github/workflows/release.yml"],
            },
        ],
    }


def stage_bytes(path: Path, payload: bytes) -> Path:
    descriptor, staged_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    staged = Path(staged_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(staged, path.stat().st_mode & 0o777)
    except BaseException:
        staged.unlink(missing_ok=True)
        raise
    return staged


def write_release_metadata(*, catalog: bytes, manifest: bytes) -> None:
    payloads = {
        CODEX_SKILL_CATALOG: catalog,
        MANIFEST: manifest,
    }
    originals = {path: path.read_bytes() for path in payloads}
    staged: dict[Path, Path] = {}
    replaced: list[Path] = []
    try:
        for path, payload in payloads.items():
            staged[path] = stage_bytes(path, payload)
        for path in payloads:
            staged[path].replace(path)
            replaced.append(path)
    except BaseException as error:
        rollback_errors: list[str] = []
        for path in reversed(replaced):
            restore: Path | None = None
            try:
                restore = stage_bytes(path, originals[path])
                restore.replace(path)
            except BaseException as rollback_error:
                rollback_errors.append(f"{path}: {rollback_error}")
            finally:
                if restore is not None:
                    restore.unlink(missing_ok=True)
        if rollback_errors:
            raise RuntimeError(
                "release metadata write failed and rollback was incomplete: "
                + "; ".join(rollback_errors)
            ) from error
        raise
    finally:
        for staged_path in staged.values():
            staged_path.unlink(missing_ok=True)


def load_manifest() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if recorded content hashes are stale.")
    parser.add_argument("--write", action="store_true", help="Write refreshed hashes to SHED_VERSION.json.")
    parser.add_argument("--version", help="Required for writes; set shed_version using MAJOR.MINOR.PATCH.")
    parser.add_argument("--notes", help="Set release notes while writing.")
    parser.add_argument(
        "--allow-same-version",
        action="store_true",
        help="Allow rebuilding an unpublished manifest without increasing its version.",
    )
    parser.add_argument("--release-commit", help="Content commit SHA represented by this release.")
    parser.add_argument("--release-tag", help="Release tag. Defaults to v<version>.")
    parser.add_argument("--released-at", help="Release timestamp or date. Omit for an unpublished manifest.")
    return parser.parse_args()


def parse_version(value: object) -> tuple[int, int, int]:
    match = VERSION.fullmatch(str(value))
    if not match:
        raise ValueError(f"invalid version {value!r}; expected MAJOR.MINOR.PATCH")
    return tuple(int(part) for part in match.groups())


def validate_manifest(manifest: dict[str, object]) -> list[str]:
    errors: list[str] = []
    try:
        parse_version(manifest.get("shed_version"))
    except ValueError as error:
        errors.append(str(error))
    commit = manifest.get("release_commit")
    if commit is not None and not COMMIT.fullmatch(str(commit)):
        errors.append("release_commit must be null or a 7-40 character lowercase hexadecimal SHA")
    tag = manifest.get("release_tag")
    if tag != f"v{manifest.get('shed_version')}":
        errors.append("release_tag must equal v<shed_version>")
    if commit and not manifest.get("released_at"):
        errors.append("released_at is required when release_commit is set")
    released_at = manifest.get("released_at")
    if released_at:
        try:
            datetime.fromisoformat(str(released_at).replace("Z", "+00:00"))
        except ValueError:
            errors.append("released_at must be an ISO 8601 timestamp or date")
    minimum_updater = manifest.get("minimum_updater_protocol", 1)
    if not isinstance(minimum_updater, int) or isinstance(minimum_updater, bool) or minimum_updater < 1:
        errors.append("minimum_updater_protocol must be a positive integer")
    hashes = manifest.get("content_hashes")
    if not isinstance(hashes, dict):
        errors.append("content_hashes must be an object")
    else:
        try:
            expected_qualification = release_qualification(
                {str(path): str(digest) for path, digest in hashes.items()},
                release_commit=str(commit) if commit else None,
                released_at=str(released_at) if released_at else None,
            )
        except ValueError as error:
            errors.append(str(error))
        else:
            if manifest.get("release_qualification") != expected_qualification:
                errors.append(
                    "release_qualification does not match release identity and shipped validator hashes"
                )
    return errors


def main() -> int:
    args = parse_args()
    if args.check == args.write:
        raise SystemExit("choose exactly one of --check or --write")
    manifest = load_manifest()
    if args.check:
        errors = validate_manifest(manifest)
        try:
            catalog = load_skill_catalog()
            if exact_git_root() and catalog != release_skill_catalog(
                exclude_tag=str(manifest.get("release_tag"))
            ):
                errors.append("Codex skill release catalog does not match stable Git tags")
        except ValueError as error:
            errors.append(str(error))
        if errors:
            print(json.dumps({"manifest_errors": errors}, indent=2))
            return 1
        hashes = current_hashes()
        recorded = manifest.get("content_hashes")
        if recorded != hashes:
            recorded_dict = recorded if isinstance(recorded, dict) else {}
            missing = sorted(set(hashes) - set(recorded_dict))
            removed = sorted(set(recorded_dict) - set(hashes))
            changed = sorted(
                path for path in set(hashes) & set(recorded_dict) if hashes[path] != recorded_dict[path]
            )
            print(json.dumps({"missing": missing, "removed": removed, "changed": changed}, indent=2))
            return 1
        print(f"SHED_VERSION.json matches {len(hashes)} tracked files.")
        return 0

    if not args.version:
        raise SystemExit("--version is required with --write")
    try:
        requested = parse_version(args.version)
        recorded = parse_version(manifest.get("shed_version"))
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if requested < recorded or (requested == recorded and not args.allow_same_version):
        raise SystemExit(
            "--version must be greater than the recorded version; "
            "use --allow-same-version only while rebuilding an unpublished release"
        )
    if args.release_commit and not COMMIT.fullmatch(args.release_commit):
        raise SystemExit("--release-commit must be a 7-40 character lowercase hexadecimal SHA")
    if args.release_commit and not args.released_at:
        raise SystemExit("--released-at is required with --release-commit")
    if args.released_at:
        try:
            datetime.fromisoformat(args.released_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise SystemExit("--released-at must be an ISO 8601 timestamp or date") from error

    release_tag = args.release_tag or f"v{args.version}"
    if release_tag != f"v{args.version}":
        raise SystemExit("--release-tag must equal v<version>")

    catalog = json_bytes(release_skill_catalog(exclude_tag=release_tag))
    hashes = current_hashes(overrides={CODEX_SKILL_CATALOG: catalog})
    manifest["shed_version"] = args.version
    if args.notes:
        manifest["notes"] = args.notes
    manifest["updated_at"] = date.today().isoformat()
    manifest["manifest_schema_version"] = 2
    manifest["minimum_updater_protocol"] = CURRENT_UPDATER_PROTOCOL
    manifest["canonical_manifest_url"] = (
        "https://raw.githubusercontent.com/PC-Redemption/tool_shed/main/SHED_VERSION.json"
    )
    manifest["content_hashes"] = hashes
    manifest["release_tag"] = release_tag
    manifest["release_commit"] = args.release_commit
    manifest["released_at"] = args.released_at
    manifest["release_qualification"] = release_qualification(
        hashes,
        release_commit=args.release_commit,
        released_at=args.released_at,
    )
    write_release_metadata(catalog=catalog, manifest=json_bytes(manifest))
    print(f"Updated {MANIFEST} with {len(hashes)} tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
