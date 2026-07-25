from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from repository_policy import format_bytes, git_repository


BINARY_SUFFIXES = {
    ".7z", ".bin", ".bmp", ".bz2", ".cap", ".dmp", ".gif", ".gz", ".ico",
    ".jpeg", ".jpg", ".mp4", ".pcap", ".pdf", ".png", ".tar", ".tgz", ".wav",
    ".webp", ".xz", ".zip",
}
DEFAULT_COUNT_THRESHOLD = 50
DEFAULT_BYTES_THRESHOLD = 25 * 1024 * 1024
DEFAULT_DIFF_THRESHOLD = 1 * 1024 * 1024


@dataclass(frozen=True)
class Finding:
    code: str
    message: str


def run_git(repository: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )


def untracked_files(repository: Path) -> list[Path]:
    result = run_git(repository, "ls-files", "--others", "--exclude-standard", "-z")
    if result.returncode != 0:
        return []
    return [
        repository / os.fsdecode(item)
        for item in result.stdout.split(b"\0")
        if item
    ]


def is_binary(path: Path) -> bool:
    if path.suffix.lower() in BINARY_SUFFIXES:
        return True
    try:
        with path.open("rb") as handle:
            return b"\0" in handle.read(8192)
    except OSError:
        return False


def versioned_work_binaries(repository: Path) -> list[str]:
    result = run_git(
        repository,
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "-z",
        "--",
        "work",
    )
    if result.returncode != 0:
        return []
    paths = []
    for item in result.stdout.split(b"\0"):
        if not item:
            continue
        relative = os.fsdecode(item)
        if relative.startswith("work/evidence/generated/"):
            continue
        path = repository / relative
        if path.is_file() and is_binary(path):
            paths.append(Path(relative).as_posix())
    return paths


def visible_backups(repository: Path) -> list[str]:
    visible = []
    for path in repository.glob("tool_shed.backup-*.tar"):
        relative = path.relative_to(repository).as_posix()
        ignored = run_git(repository, "check-ignore", "-q", "--", relative)
        tracked = run_git(repository, "ls-files", "--error-unmatch", "--", relative)
        if ignored.returncode != 0 or tracked.returncode == 0:
            visible.append(relative)
    return visible


def diff_bytes(repository: Path) -> int:
    result = run_git(repository, "diff", "--binary", "HEAD", "--")
    if result.returncode != 0:
        result = run_git(repository, "diff", "--binary", "--")
    return len(result.stdout)


def inspect(
    workspace: Path,
    *,
    count_threshold: int = DEFAULT_COUNT_THRESHOLD,
    bytes_threshold: int = DEFAULT_BYTES_THRESHOLD,
    diff_threshold: int = DEFAULT_DIFF_THRESHOLD,
) -> tuple[Path | None, list[Finding], dict[str, int]]:
    repository = git_repository(workspace)
    if repository is None:
        return None, [], {"untracked_count": 0, "untracked_bytes": 0, "diff_bytes": 0}

    untracked = untracked_files(repository)
    untracked_bytes = sum(path.stat().st_size for path in untracked if path.is_file())
    proposed_diff_bytes = diff_bytes(repository)
    metrics = {
        "untracked_count": len(untracked),
        "untracked_bytes": untracked_bytes,
        "diff_bytes": proposed_diff_bytes,
    }
    findings: list[Finding] = []
    if len(untracked) > count_threshold:
        findings.append(Finding(
            "UNTRACKED_COUNT",
            f"{len(untracked)} untracked files exceed the threshold of {count_threshold}",
        ))
    if untracked_bytes > bytes_threshold:
        findings.append(Finding(
            "UNTRACKED_BYTES",
            f"untracked files total {format_bytes(untracked_bytes)}, exceeding {format_bytes(bytes_threshold)}",
        ))
    binaries = versioned_work_binaries(repository)
    if binaries:
        preview = ", ".join(binaries[:5])
        suffix = f" (and {len(binaries) - 5} more)" if len(binaries) > 5 else ""
        findings.append(Finding(
            "BINARY_IN_VERSIONED_WORK",
            f"binary files appear beneath versioned work/ paths: {preview}{suffix}",
        ))
    if proposed_diff_bytes > diff_threshold:
        findings.append(Finding(
            "DIFF_BYTES",
            f"proposed tracked diff is {format_bytes(proposed_diff_bytes)}, exceeding {format_bytes(diff_threshold)}",
        ))
    backups = visible_backups(repository)
    if backups:
        findings.append(Finding(
            "VISIBLE_TOOL_SHED_BACKUP",
            "Tool Shed backup archives are visible to Git: " + ", ".join(backups),
        ))
    return repository, findings, metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Warn about Git hydration risks in a Tool Shed workspace.")
    parser.add_argument("--workspace", default=".", help="Project workspace root.")
    parser.add_argument("--untracked-count", type=int, default=DEFAULT_COUNT_THRESHOLD)
    parser.add_argument("--untracked-bytes", type=int, default=DEFAULT_BYTES_THRESHOLD)
    parser.add_argument("--diff-bytes", type=int, default=DEFAULT_DIFF_THRESHOLD)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when warnings are found.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository, findings, metrics = inspect(
        Path(args.workspace).expanduser().resolve(),
        count_threshold=args.untracked_count,
        bytes_threshold=args.untracked_bytes,
        diff_threshold=args.diff_bytes,
    )
    if args.json:
        print(json.dumps({
            "schema_version": 1,
            "repository": str(repository) if repository else None,
            "metrics": metrics,
            "findings": [asdict(finding) for finding in findings],
        }, indent=2, sort_keys=True))
    elif repository is None:
        print("Workspace preflight skipped: no Git repository found.")
    elif findings:
        print("Workspace preflight warnings:")
        for finding in findings:
            print(f"- [{finding.code}] {finding.message}")
        print("Store raw outputs in work/evidence/generated/ and summarize them with a small versioned manifest.")
    else:
        print(
            "Workspace preflight passed: "
            f"{metrics['untracked_count']} untracked file(s), "
            f"{format_bytes(metrics['untracked_bytes'])} untracked, "
            f"{format_bytes(metrics['diff_bytes'])} tracked diff."
        )
    return 1 if args.strict and findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
