#!/usr/bin/env python3
"""Prepare or apply a reversible generated-evidence migration."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from repository_policy import git_repository
from workspace_preflight import (
    BINARY_SUFFIXES,
    evidence_path,
    evidence_roots,
    is_binary,
    load_evidence_policy,
)


SCHEMA_VERSION = 1
DURABLE_SUFFIXES = {".md", ".json", ".csv", ".txt", ".sha256", ".yaml", ".yml"}
REVIEW_SUFFIXES = {".gif", ".heic", ".jpeg", ".jpg", ".pdf", ".png", ".webp"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(repository: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def tracked_evidence_paths(repository: Path, roots: list[str]) -> list[str]:
    result = run_git(repository, "ls-files", "--cached", "-z", "--", *roots)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace").strip() or "git ls-files failed")
    return sorted(os.fsdecode(item) for item in result.stdout.split(b"\0") if item)


def classify(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix in DURABLE_SUFFIXES and path.stat().st_size < 10 * 1024 * 1024:
        return "keep", "durable-summary-type"
    if suffix in REVIEW_SUFFIXES:
        return "review", "possibly-curated-visual"
    if suffix in BINARY_SUFFIXES or is_binary(path) or path.stat().st_size >= 10 * 1024 * 1024:
        return "migrate", "raw-binary-or-large"
    if suffix in {".log", ".trace", ".capture"}:
        return "migrate", "generated-log-or-capture"
    return "review", "unknown-workspace-specific-type"


def require_outside(repository: Path, path: Path) -> None:
    try:
        path.resolve().relative_to(repository.resolve())
    except ValueError:
        return
    raise SystemExit("output directory must be outside the repository")


def prepare(repository: Path, output: Path) -> Path:
    require_outside(repository, output)
    output.mkdir(parents=True, exist_ok=False)
    policy, errors = load_evidence_policy(repository)
    if errors:
        raise SystemExit("; ".join(errors))
    generated = evidence_path(policy)
    roots = evidence_roots(policy)
    candidates = []
    archive_paths = []
    for relative in tracked_evidence_paths(repository, roots):
        if relative.startswith(generated.rstrip("/") + "/"):
            continue
        path = repository / relative
        if not path.is_file() or path.is_symlink():
            continue
        classification, reason = classify(path)
        item = {
            "path": Path(relative).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "tracked": True,
            "classification": classification,
            "reason": reason,
            "action": "migrate" if classification == "migrate" else "none",
            "approved": False,
        }
        candidates.append(item)
        if classification == "migrate":
            archive_paths.append(item["path"])

    archive = output / "evidence-backup.tar"
    with tarfile.open(archive, "w") as handle:
        for relative in archive_paths:
            handle.add(repository / relative, arcname=relative, recursive=False)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "workspace": str(repository),
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "generated_path": generated,
        "evidence_paths": roots,
        "approved": False,
        "archive": {
            "path": archive.name,
            "sha256": sha256(archive),
            "members": archive_paths,
        },
        "candidates": candidates,
    }
    manifest_path = output / "evidence-migration.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def safe_destination(repository: Path, generated: str, roots: list[str], relative: str) -> Path:
    source_relative = Path(relative)
    tail = source_relative
    for root in sorted((Path(value) for value in roots), key=lambda value: len(value.parts), reverse=True):
        try:
            tail = source_relative.relative_to(root)
            break
        except ValueError:
            continue
    destination = (repository / generated / tail).resolve()
    destination.relative_to((repository / generated).resolve())
    return destination


def apply(repository: Path, manifest_path: Path) -> int:
    require_outside(repository, manifest_path.parent)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise SystemExit("unsupported migration manifest schema")
    if Path(str(manifest.get("workspace"))).resolve() != repository.resolve():
        raise SystemExit("manifest workspace does not match the requested repository")
    if manifest.get("approved") is not True:
        raise SystemExit("manifest top-level approved must be true")
    archive_info = manifest.get("archive", {})
    archive = manifest_path.parent / str(archive_info.get("path", ""))
    if not archive.is_file() or sha256(archive) != archive_info.get("sha256"):
        raise SystemExit("verified archive is missing or its SHA-256 does not match")

    generated = str(manifest.get("generated_path", "")).strip("/")
    roots = [str(value).strip("/") for value in manifest.get("evidence_paths", [])]
    if not generated:
        raise SystemExit("manifest generated_path is empty")
    if not roots:
        raise SystemExit("manifest evidence_paths is empty")
    selected = [
        item for item in manifest.get("candidates", [])
        if item.get("action") == "migrate" and item.get("approved") is True
    ]
    if not selected:
        raise SystemExit("manifest contains no individually approved migrate candidates")

    moves: list[tuple[Path, Path]] = []
    archived_members = set(archive_info.get("members", []))
    for item in selected:
        relative = str(item.get("path", ""))
        if relative not in archived_members:
            raise SystemExit(f"approved candidate is absent from the verified archive: {relative}")
        source = (repository / relative).resolve()
        source.relative_to(repository.resolve())
        if not source.is_file() or source.is_symlink() or sha256(source) != item.get("sha256"):
            raise SystemExit(f"candidate changed or is missing: {relative}")
        destination = safe_destination(repository, generated, roots, relative)
        if destination.exists():
            raise SystemExit(f"destination already exists: {destination.relative_to(repository)}")
        destination_relative = destination.relative_to(repository).as_posix()
        ignored = run_git(repository, "check-ignore", "-q", "--", destination_relative)
        if ignored.returncode != 0:
            raise SystemExit(
                f"generated destination is not ignored by repository policy: {destination_relative}"
            )
        moves.append((source, destination))

    completed: list[tuple[Path, Path]] = []
    try:
        for source, destination in moves:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            completed.append((source, destination))
    except OSError as error:
        rollback_errors = []
        for source, destination in reversed(completed):
            try:
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destination), str(source))
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        detail = f"; rollback errors: {rollback_errors}" if rollback_errors else "; moved files restored"
        raise SystemExit(f"migration apply failed: {error}{detail}") from error
    print(f"Moved {len(moves)} approved file(s) into {generated}.")
    print("The archive remains available for rollback; Git history was not rewritten.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare", help="Create a non-mutating manifest and archive.")
    prepare_parser.add_argument("--workspace", default=".")
    prepare_parser.add_argument("--output", required=True)
    apply_parser = subparsers.add_parser("apply", help="Apply only approved manifest entries.")
    apply_parser.add_argument("--workspace", default=".")
    apply_parser.add_argument("--manifest", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    repository = git_repository(workspace)
    if repository is None:
        raise SystemExit("no Git repository found")
    if args.command == "prepare":
        manifest = prepare(repository, Path(args.output).expanduser().resolve())
        print(manifest)
        return 0
    return apply(repository, Path(args.manifest).expanduser().resolve())


if __name__ == "__main__":
    raise SystemExit(main())
