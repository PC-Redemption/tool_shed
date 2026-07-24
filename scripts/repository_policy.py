from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


POLICY_FILE = ".tool-shed-policy.json"


@dataclass(frozen=True)
class IgnoreMatch:
    source: str
    line: int
    rule: str
    path: str


@dataclass(frozen=True)
class WorkIgnoreState:
    repository: Path | None
    match: IgnoreMatch | None
    exception_reason: str | None
    exception_error: str | None
    file_count: int
    total_bytes: int


def git_repository(workspace: Path) -> Path | None:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=workspace,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return Path(result.stdout.strip()).resolve() if result.returncode == 0 else None


def ignore_match(repository: Path, *paths: str) -> IgnoreMatch | None:
    result = subprocess.run(
        ["git", "check-ignore", "-v", "--no-index", "--", *paths],
        cwd=repository,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    for output_line in result.stdout.splitlines():
        match = re.fullmatch(r"(.+):(\d+):(.*)\t(.*)", output_line)
        if match:
            source, line, rule, path = match.groups()
            if not rule.startswith("!"):
                return IgnoreMatch(source, int(line), rule, path)
    return None


def documented_exception(repository: Path) -> tuple[str | None, str | None]:
    policy_path = repository / POLICY_FILE
    if not policy_path.exists():
        return None, None
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return None, f"{POLICY_FILE} is not valid JSON: {error}"
    work_policy = policy.get("work_git_policy")
    if not isinstance(work_policy, dict) or work_policy.get("ignore") is not True:
        return None, f"{POLICY_FILE} must set work_git_policy.ignore to true"
    reason = work_policy.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return None, f"{POLICY_FILE} must document a non-empty work_git_policy.reason"
    if policy.get("schema_version") != 1:
        return None, f"{POLICY_FILE} must set schema_version to 1"
    return reason.strip(), None


def ignored_work_files(repository: Path) -> tuple[int, int]:
    work = repository / "work"
    if not work.exists():
        return 0, 0
    files = [path for path in work.rglob("*") if path.is_file()]
    if not files:
        return 0, 0
    relative = [path.relative_to(repository).as_posix() for path in files]
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--", *relative],
        cwd=repository,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    ignored = set(result.stdout.splitlines())
    ignored_files = [repository / item for item in ignored]
    return len(ignored_files), sum(path.stat().st_size for path in ignored_files)


def inspect_work_ignore(workspace: Path) -> WorkIgnoreState:
    repository = git_repository(workspace)
    if repository is None:
        return WorkIgnoreState(None, None, None, None, 0, 0)
    match = ignore_match(repository, "work/", "work/README.md", "work/index.md")
    if match is None:
        return WorkIgnoreState(repository, None, None, None, 0, 0)
    reason, exception_error = documented_exception(repository)
    file_count, total_bytes = ignored_work_files(repository)
    return WorkIgnoreState(repository, match, reason, exception_error, file_count, total_bytes)


def inspect_snapshot_ignore(workspace: Path) -> tuple[Path | None, IgnoreMatch | None]:
    repository = git_repository(workspace)
    if repository is None or not (repository / "tool_shed").exists():
        return repository, None
    return repository, ignore_match(repository, "tool_shed/", "tool_shed/README.md")


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")
