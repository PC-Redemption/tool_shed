#!/usr/bin/env python3
"""Validate a tagged Tool Shed release and prepare its GitHub Release notes."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


STABLE_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


class ReleasePreparationError(ValueError):
    """Raised when a tag is not safe to publish as a GitHub Release."""


def git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise ReleasePreparationError(result.stderr.strip() or "Git command failed")
    return result.stdout.strip()


def version_key(tag: str) -> tuple[int, int, int]:
    match = STABLE_TAG.fullmatch(tag)
    if not match:
        raise ReleasePreparationError(f"invalid stable release tag: {tag!r}")
    return tuple(int(part) for part in match.groups())


def prepare_release(repository: Path, tag: str) -> dict[str, object]:
    requested_version = version_key(tag)
    repository = repository.resolve()
    manifest_path = repository / "SHED_VERSION.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleasePreparationError(f"invalid SHED_VERSION.json: {error}") from error

    if manifest.get("shed_version") != tag.removeprefix("v"):
        raise ReleasePreparationError("manifest shed_version does not match the requested tag")
    if manifest.get("release_tag") != tag:
        raise ReleasePreparationError("manifest release_tag does not match the requested tag")
    if not manifest.get("released_at"):
        raise ReleasePreparationError("manifest has no release timestamp")

    head = git(repository, "rev-parse", "HEAD")
    tag_commit = git(repository, "rev-parse", f"{tag}^{{commit}}")
    if head != tag_commit:
        raise ReleasePreparationError("checkout HEAD is not the requested tag commit")
    content_commit = git(repository, "rev-parse", f"{tag_commit}^")
    if manifest.get("release_commit") != content_commit:
        raise ReleasePreparationError("manifest release_commit does not match the provenance parent")
    changed = git(repository, "diff", "--name-only", content_commit, tag_commit).splitlines()
    if changed != ["SHED_VERSION.json"]:
        raise ReleasePreparationError(
            "provenance commit must change exactly SHED_VERSION.json"
        )

    stable_tags = [
        candidate.strip()
        for candidate in git(repository, "tag", "--list").splitlines()
        if STABLE_TAG.fullmatch(candidate.strip())
    ]
    if not stable_tags:
        raise ReleasePreparationError("repository contains no stable release tags")
    highest = max(stable_tags, key=version_key)
    if requested_version != version_key(highest):
        raise ReleasePreparationError(
            f"refusing to mark {tag} latest because the highest stable tag is {highest}"
        )

    notes = manifest.get("notes")
    if not isinstance(notes, str) or not notes.strip():
        raise ReleasePreparationError("manifest notes must be a non-empty string")
    body = (
        "## What changed\n\n"
        f"- {notes.strip().rstrip('.')}\n\n"
        "## Verified provenance\n\n"
        f"- Content commit: `{content_commit}`\n"
        f"- Provenance tag: `{tag}`\n"
        f"- Released at: `{manifest['released_at']}`\n"
        "- Tool Shed validates the release manifest and content hashes before installation.\n"
    )
    return {
        "valid": True,
        "tag": tag,
        "version": tag.removeprefix("v"),
        "title": f"Tool Shed {tag}",
        "content_commit": content_commit,
        "tag_commit": tag_commit,
        "released_at": manifest["released_at"],
        "latest": True,
        "notes": body,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=".", help="Canonical checkout root.")
    parser.add_argument("--tag", required=True, help="Exact vMAJOR.MINOR.PATCH tag to publish.")
    parser.add_argument("--notes-file", help="Write deterministic GitHub Release notes here.")
    parser.add_argument("--json", action="store_true", help="Emit the validated release payload.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = prepare_release(Path(args.repository), args.tag)
        if args.notes_file:
            notes_path = Path(args.notes_file)
            notes_path.parent.mkdir(parents=True, exist_ok=True)
            notes_path.write_text(str(payload["notes"]), encoding="utf-8", newline="\n")
    except ReleasePreparationError as error:
        if args.json:
            print(json.dumps({"valid": False, "error": str(error)}, indent=2, sort_keys=True))
        else:
            print(f"GitHub Release preparation failed: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"GitHub Release preparation passed for {payload['tag']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
