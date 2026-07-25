#!/usr/bin/env python3
"""Refresh or verify SHED_VERSION.json content hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "SHED_VERSION.json"
TRACKED_ROOT_FILES = ("README.md", "selection.md", "conventions.md", "existing-projects.md")
TRACKED_GLOBS = (
    "docs/*.md",
    "scripts/*.py",
    "skills/tool-shed/SKILL.md",
    "skills/tool-shed/agents/*.yaml",
    "templates/*.md",
    "templates/*.json",
)
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
COMMIT = re.compile(r"^[0-9a-f]{7,40}$")


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
    return sorted(path for path in paths if path.is_file())


def current_hashes() -> dict[str, str]:
    return {path.relative_to(ROOT).as_posix(): hash_file(path) for path in tracked_paths()}


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
    return errors


def main() -> int:
    args = parse_args()
    if args.check == args.write:
        raise SystemExit("choose exactly one of --check or --write")
    manifest = load_manifest()
    hashes = current_hashes()
    if args.check:
        errors = validate_manifest(manifest)
        if errors:
            print(json.dumps({"manifest_errors": errors}, indent=2))
            return 1
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

    manifest["shed_version"] = args.version
    if args.notes:
        manifest["notes"] = args.notes
    manifest["updated_at"] = date.today().isoformat()
    manifest["manifest_schema_version"] = 2
    manifest["canonical_manifest_url"] = (
        "https://raw.githubusercontent.com/PC-Redemption/tool_shed/main/SHED_VERSION.json"
    )
    manifest["content_hashes"] = hashes
    manifest["release_tag"] = args.release_tag or f"v{args.version}"
    if manifest["release_tag"] != f"v{args.version}":
        raise SystemExit("--release-tag must equal v<version>")
    manifest["release_commit"] = args.release_commit
    manifest["released_at"] = args.released_at
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Updated {MANIFEST} with {len(hashes)} tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
