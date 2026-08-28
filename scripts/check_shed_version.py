#!/usr/bin/env python3
"""Report local Tool Shed integrity and whether canonical has a newer version."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_CANONICAL = "https://raw.githubusercontent.com/PC-Redemption/tool_shed/main/SHED_VERSION.json"
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
BYTECODE_SUFFIXES = (".pyc", ".pyo")
BOOTSTRAP_GUIDANCE = (
    "obtain a current released Tool Shed checkout outside the workspace, then run "
    "`python /path/to/current-release/scripts/update_snapshot.py --workspace .`"
)


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json_path(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_canonical(source: str, timeout: int) -> dict[str, Any]:
    if source.startswith("http://"):
        raise ValueError("canonical manifest URL must use HTTPS")
    if source.startswith("https://"):
        request = urllib.request.Request(source, headers={"User-Agent": "tool-shed-version-check"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    path = Path(source).expanduser()
    if path.is_dir():
        path = path / "SHED_VERSION.json"
    return read_json_path(path.resolve())


def parse_version(value: object) -> tuple[int, int, int]:
    match = VERSION.fullmatch(str(value))
    if not match:
        raise ValueError(f"invalid shed_version {value!r}; expected MAJOR.MINOR.PATCH")
    return tuple(int(part) for part in match.groups())


def validate_manifest(manifest: dict[str, Any], *, canonical: bool) -> None:
    label = "canonical" if canonical else "local"
    parse_version(manifest.get("shed_version"))
    if not isinstance(manifest.get("manifest_schema_version"), int):
        raise ValueError(f"{label} manifest_schema_version must be an integer")
    if not isinstance(manifest.get("content_hashes"), dict):
        raise ValueError(f"{label} content_hashes must be an object")
    if manifest.get("release_tag") != f"v{manifest.get('shed_version')}":
        raise ValueError(f"{label} release_tag must equal v<shed_version>")
    commit = manifest.get("release_commit")
    if commit is not None and not re.fullmatch(r"[0-9a-f]{7,40}", str(commit)):
        raise ValueError(f"{label} release_commit must be null or a hexadecimal Git SHA")
    released_at = manifest.get("released_at")
    if commit and not released_at:
        raise ValueError(f"{label} released_at is required when release_commit is set")
    if released_at:
        try:
            datetime.fromisoformat(str(released_at).replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"{label} released_at must be ISO 8601") from error
    minimum_updater = manifest.get("minimum_updater_protocol", 1)
    if not isinstance(minimum_updater, int) or isinstance(minimum_updater, bool) or minimum_updater < 1:
        raise ValueError(f"{label} minimum_updater_protocol must be a positive integer")
    qualification = manifest.get("release_qualification")
    if qualification is not None:
        if not isinstance(qualification, dict) or qualification.get("schema_version") != 1:
            raise ValueError(f"{label} release_qualification must use schema version 1")
        if qualification.get("subject_commit") != commit:
            raise ValueError(f"{label} release_qualification subject must equal release_commit")
        if qualification.get("attested_at") != released_at:
            raise ValueError(f"{label} release_qualification timestamp must equal released_at")
        hashes = manifest["content_hashes"]
        required = [qualification.get("full_validator"), qualification.get("client_smoke")]
        required_ci = qualification.get("required_ci")
        required.extend(required_ci if isinstance(required_ci, list) else [])
        if len(required) != 4:
            raise ValueError(
                f"{label} release_qualification must identify both validators and both CI workflows"
            )
        for item in required:
            if not isinstance(item, dict):
                raise ValueError(f"{label} release_qualification contains an invalid path identity")
            path = item.get("path")
            if not isinstance(path, str) or item.get("sha256") != hashes.get(path):
                raise ValueError(f"{label} release_qualification path hash does not match content_hashes")


def validate_updater_context(
    manifest: dict[str, Any],
    *,
    strict: bool,
    updater_protocol: int | None,
    verification_only: bool,
) -> None:
    minimum = int(manifest.get("minimum_updater_protocol", 1))
    if updater_protocol is not None and updater_protocol < minimum:
        raise ValueError(
            f"release requires updater protocol {minimum}, but updater protocol "
            f"{updater_protocol} was supplied; {BOOTSTRAP_GUIDANCE}"
        )
    if strict and minimum > 1 and updater_protocol is None and not verification_only:
        raise ValueError(
            f"release requires updater protocol {minimum}; legacy updater context is unsafe; "
            f"{BOOTSTRAP_GUIDANCE}; for standalone integrity verification, add --verification-only"
        )


def verify_local(root: Path, manifest: dict[str, Any]) -> tuple[list[str], list[str]]:
    hashes = manifest.get("content_hashes")
    if not isinstance(hashes, dict):
        return ["SHED_VERSION.json has no content_hashes"], []
    missing: list[str] = []
    modified: list[str] = []
    for relative, expected in sorted(hashes.items()):
        path = root / relative
        if not path.is_file():
            missing.append(relative)
        elif hash_file(path) != expected:
            modified.append(relative)
    return missing, modified


def exact_git_root(root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0 and Path(result.stdout.strip()).resolve() == root


def forbidden_snapshot_paths(root: Path, enforce_snapshot: bool) -> list[str]:
    forbidden: list[str] = []
    if enforce_snapshot and ((root / ".git").exists() or (root / ".git").is_symlink()):
        forbidden.append(".git")
    if (root / "work").exists() and (enforce_snapshot or not exact_git_root(root)):
        forbidden.append("work")
    if enforce_snapshot:
        runtime_artifacts: set[str] = set()
        for directory, names, files in os.walk(root, followlinks=False):
            current = Path(directory)
            for name in names:
                if name == "__pycache__":
                    runtime_artifacts.add((current / name).relative_to(root).as_posix())
            for name in files:
                if name.endswith(BYTECODE_SUFFIXES):
                    runtime_artifacts.add((current / name).relative_to(root).as_posix())
        forbidden.extend(sorted(runtime_artifacts))
    return forbidden


def relation(local: object, canonical: object) -> str:
    local_version = parse_version(local)
    canonical_version = parse_version(canonical)
    if local_version < canonical_version:
        return "older"
    if local_version > canonical_version:
        return "newer"
    return "current"


def manifests_match(local: dict[str, Any], canonical: dict[str, Any]) -> bool:
    return (
        local.get("content_hashes") == canonical.get("content_hashes")
        and local.get("artifact_model_version") == canonical.get("artifact_model_version")
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shed", default=str(Path(__file__).resolve().parents[1]), help="Local Tool Shed root.")
    parser.add_argument("--canonical", default=DEFAULT_CANONICAL, help="Canonical manifest URL, file, or directory.")
    parser.add_argument("--local-only", action="store_true", help="Report local version and integrity without network.")
    parser.add_argument("--timeout", type=int, default=10, help="Canonical fetch timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Write machine-readable output.")
    parser.add_argument("--strict", action="store_true", help="Fail when local is not current and unmodified.")
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Enforce disconnected-snapshot boundaries, including no embedded .git or work.",
    )
    context = parser.add_mutually_exclusive_group()
    context.add_argument(
        "--updater-protocol",
        type=int,
        help="Updater protocol supplied by the calling snapshot updater.",
    )
    context.add_argument(
        "--verification-only",
        action="store_true",
        help="Declare standalone integrity verification rather than an updater invocation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.shed).expanduser().resolve()
    try:
        local_manifest = read_json_path(root / "SHED_VERSION.json")
        validate_manifest(local_manifest, canonical=False)
        missing, modified = verify_local(root, local_manifest)
        forbidden = forbidden_snapshot_paths(root, args.snapshot)
        if not missing and not modified and not forbidden:
            validate_updater_context(
                local_manifest,
                strict=args.strict,
                updater_protocol=args.updater_protocol,
                verification_only=args.verification_only,
            )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        payload = {
            "local_version": None,
            "local_integrity": "unknown",
            "missing": [],
            "modified": [],
            "forbidden": [],
            "canonical_version": None,
            "canonical_release": None,
            "canonical_manifest_match": None,
            "version_relation": "not-checked",
            "state": "check-failed",
            "error": str(error),
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("Local Tool Shed check failed: " + str(error))
        return 2
    payload: dict[str, Any] = {
        "local_version": local_manifest.get("shed_version"),
        "local_integrity": "modified" if missing or modified or forbidden else "verified",
        "missing": missing,
        "modified": modified,
        "forbidden": forbidden,
        "canonical_version": None,
        "local_release": {
            "tag": local_manifest.get("release_tag"),
            "commit": local_manifest.get("release_commit"),
            "released_at": local_manifest.get("released_at"),
            "minimum_updater_protocol": local_manifest.get("minimum_updater_protocol", 1),
        },
        "canonical_release": None,
        "canonical_manifest_match": None,
        "version_relation": "not-checked",
        "state": "modified" if missing or modified or forbidden else "local-only",
    }

    if not args.local_only:
        try:
            canonical_manifest = read_canonical(args.canonical, args.timeout)
            validate_manifest(canonical_manifest, canonical=True)
            payload["canonical_version"] = canonical_manifest.get("shed_version")
            payload["canonical_release"] = {
                "tag": canonical_manifest.get("release_tag"),
                "commit": canonical_manifest.get("release_commit"),
                "released_at": canonical_manifest.get("released_at"),
                "minimum_updater_protocol": canonical_manifest.get("minimum_updater_protocol", 1),
            }
            payload["version_relation"] = relation(
                local_manifest.get("shed_version"), canonical_manifest.get("shed_version")
            )
            payload["canonical_manifest_match"] = manifests_match(local_manifest, canonical_manifest)
            if payload["local_integrity"] == "modified":
                payload["state"] = "modified"
            elif payload["version_relation"] == "current" and not payload["canonical_manifest_match"]:
                payload["state"] = "release-mismatch"
            else:
                payload["state"] = payload["version_relation"]
        except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as error:
            payload["state"] = "check-failed"
            payload["error"] = str(error)

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Local Tool Shed: {payload['local_version']} ({payload['local_integrity']})")
        if payload["canonical_version"]:
            print(f"Canonical Tool Shed: {payload['canonical_version']}")
            print(f"Version relation: {payload['version_relation']}")
            if payload["state"] == "release-mismatch":
                print("Release mismatch: equal versions have different canonical content manifests")
        local_release = payload["local_release"]
        if any(local_release.values()):
            print(
                "Local release: "
                + ", ".join(f"{key}={value}" for key, value in local_release.items() if value)
            )
        if missing:
            print("Missing tracked files: " + ", ".join(missing))
        if modified:
            print("Modified tracked files: " + ", ".join(modified))
        if forbidden:
            print("Forbidden snapshot paths: " + ", ".join(forbidden))
        if payload.get("error"):
            print("Canonical check failed: " + str(payload["error"]))

    if payload["state"] == "check-failed":
        return 2
    if args.strict and payload["state"] not in {"current", "local-only"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
