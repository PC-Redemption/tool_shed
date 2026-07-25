from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from repository_policy import POLICY_FILE, format_bytes, git_repository


BINARY_SUFFIXES = {
    ".7z", ".bin", ".bmp", ".bundle", ".bz2", ".cap", ".dmp", ".gif", ".gz",
    ".heic", ".ico", ".jpeg", ".jpg", ".mp4", ".pcap", ".pdf", ".png", ".slg",
    ".tar", ".tgz", ".wav", ".webp", ".xz", ".zip",
}
DEFAULT_COUNT_THRESHOLD = 50
DEFAULT_BYTES_THRESHOLD = 25 * 1024 * 1024
DEFAULT_DIFF_THRESHOLD = 1 * 1024 * 1024
DEFAULT_LARGE_FILE_THRESHOLD = 10 * 1024 * 1024
HARD_COUNT_LIMIT = 5000
HARD_BYTES_LIMIT = 1024 * 1024 * 1024
HARD_DIFF_LIMIT = 10 * 1024 * 1024
PROFILE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    severity: str = "warning"
    source: str = "general-default"
    mitigation: str = "review"


def run_git(repository: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )


def git_paths(repository: Path, *args: str) -> list[str]:
    result = run_git(repository, *args)
    if result.returncode != 0:
        return []
    return [os.fsdecode(item) for item in result.stdout.split(b"\0") if item]


def untracked_files(repository: Path) -> list[Path]:
    return [
        repository / item
        for item in git_paths(repository, "ls-files", "--others", "--exclude-standard", "-z")
    ]


def tracked_files(repository: Path) -> list[Path]:
    return [
        repository / item
        for item in git_paths(repository, "ls-files", "--cached", "-z")
    ]


def is_binary(path: Path) -> bool:
    if path.suffix.lower() in BINARY_SUFFIXES:
        return True
    try:
        with path.open("rb") as handle:
            return b"\0" in handle.read(8192)
    except OSError:
        return False


def safe_size(path: Path) -> int:
    try:
        return path.stat().st_size if path.is_file() else 0
    except OSError:
        return 0


def load_evidence_policy(repository: Path) -> tuple[dict[str, object], list[str]]:
    path = repository / POLICY_FILE
    if not path.exists():
        return {}, []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {}, [f"{POLICY_FILE} is not valid JSON: {error}"]
    policy = payload.get("evidence_policy", {})
    if not isinstance(policy, dict):
        return {}, [f"{POLICY_FILE} evidence_policy must be an object"]
    errors: list[str] = []
    if policy and payload.get("schema_version") != 1:
        errors.append(f"{POLICY_FILE} must set schema_version to 1")
    reason = policy.get("reason")
    if policy and (not isinstance(reason, str) or not reason.strip()):
        errors.append(f"{POLICY_FILE} evidence_policy requires a non-empty reason")
    generated_path = policy.get("generated_path")
    if generated_path is not None:
        candidate = Path(str(generated_path))
        if candidate.is_absolute() or ".." in candidate.parts:
            errors.append("evidence_policy.generated_path must be a repository-relative path")
    evidence_paths = policy.get("evidence_paths")
    if evidence_paths is not None:
        if not isinstance(evidence_paths, list) or not evidence_paths:
            errors.append("evidence_policy.evidence_paths must be a non-empty array")
        else:
            for value in evidence_paths:
                candidate = Path(str(value))
                if candidate.is_absolute() or ".." in candidate.parts or not str(value).strip("/"):
                    errors.append(
                        "evidence_policy.evidence_paths entries must be repository-relative paths"
                    )
                    break
    thresholds = policy.get("thresholds", {})
    if thresholds is not None and not isinstance(thresholds, dict):
        errors.append("evidence_policy.thresholds must be an object")
    return policy, errors


def evidence_path(policy: dict[str, object]) -> str:
    value = str(policy.get("generated_path", "work/evidence/generated")).strip("/")
    return value or "work/evidence/generated"


def evidence_roots(policy: dict[str, object]) -> list[str]:
    configured = policy.get("evidence_paths")
    values = configured if isinstance(configured, list) else ["work/evidence"]
    roots = {str(value).strip("/") for value in values if str(value).strip("/")}
    roots.add(evidence_path(policy))
    return sorted(roots)


def threshold(
    policy: dict[str, object],
    name: str,
    requested: int,
    relative: int,
    hard_limit: int,
) -> tuple[int, str]:
    thresholds = policy.get("thresholds", {})
    override = thresholds.get(name) if isinstance(thresholds, dict) else None
    if isinstance(override, int) and override >= 0:
        return min(override, hard_limit), "workspace-policy"
    return min(max(requested, relative), hard_limit), "adaptive-baseline"


def diff_bytes(repository: Path) -> int:
    result = run_git(repository, "diff", "--binary", "HEAD", "--")
    if result.returncode != 0:
        result = run_git(repository, "diff", "--binary", "--")
    return len(result.stdout)


def visible_backups(repository: Path) -> list[str]:
    visible = []
    for path in repository.glob("tool_shed.backup-*.tar"):
        relative = path.relative_to(repository).as_posix()
        ignored = run_git(repository, "check-ignore", "-q", "--", relative)
        tracked = run_git(repository, "ls-files", "--error-unmatch", "--", relative)
        if ignored.returncode != 0 or tracked.returncode == 0:
            visible.append(relative)
    return visible


def workspace_profile(repository: Path, policy: dict[str, object]) -> dict[str, object]:
    tracked = [path for path in tracked_files(repository) if path.is_file()]
    untracked = [path for path in untracked_files(repository) if path.is_file()]
    generated = evidence_path(policy)
    evidence_prefixes = [root.rstrip("/") + "/" for root in evidence_roots(policy)]
    tracked_evidence = [
        path for path in tracked
        if any(
            path.relative_to(repository).as_posix().startswith(prefix)
            for prefix in evidence_prefixes
        )
    ]
    untracked_evidence = [
        path for path in untracked
        if any(
            path.relative_to(repository).as_posix().startswith(prefix)
            for prefix in evidence_prefixes
        )
    ]
    suffixes = Counter(
        (path.suffix.lower() or "<none>")
        for path in tracked_evidence + untracked_evidence
    )
    large_files = [
        {
            "path": path.relative_to(repository).as_posix(),
            "bytes": safe_size(path),
            "tracked": path in tracked,
        }
        for path in tracked + untracked
        if safe_size(path) >= DEFAULT_LARGE_FILE_THRESHOLD
    ]
    status = run_git(repository, "status", "--porcelain=v1", "-z")
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "generated_path": generated,
        "evidence_paths": evidence_roots(policy),
        "repository": {
            "tracked_count": len(tracked),
            "tracked_bytes": sum(safe_size(path) for path in tracked),
            "untracked_count": len(untracked),
            "untracked_bytes": sum(safe_size(path) for path in untracked),
            "dirty_entries": len([item for item in status.stdout.split(b"\0") if item]),
        },
        "evidence": {
            "tracked_count": len(tracked_evidence),
            "tracked_bytes": sum(safe_size(path) for path in tracked_evidence),
            "untracked_count": len(untracked_evidence),
            "untracked_bytes": sum(safe_size(path) for path in untracked_evidence),
            "dominant_suffixes": [
                {"suffix": suffix, "count": count}
                for suffix, count in suffixes.most_common(10)
            ],
        },
        "large_files": sorted(large_files, key=lambda item: (-int(item["bytes"]), str(item["path"])))[:20],
        "policy": policy,
    }


def inspect(
    workspace: Path,
    *,
    count_threshold: int = DEFAULT_COUNT_THRESHOLD,
    bytes_threshold: int = DEFAULT_BYTES_THRESHOLD,
    diff_threshold: int = DEFAULT_DIFF_THRESHOLD,
) -> tuple[Path | None, list[Finding], dict[str, int], dict[str, object]]:
    repository = git_repository(workspace)
    empty_metrics = {
        "untracked_count": 0,
        "untracked_bytes": 0,
        "tracked_evidence_count": 0,
        "tracked_evidence_bytes": 0,
        "untracked_evidence_count": 0,
        "untracked_evidence_bytes": 0,
        "diff_bytes": 0,
    }
    if repository is None:
        return None, [], empty_metrics, {}

    policy, policy_errors = load_evidence_policy(repository)
    profile = workspace_profile(repository, policy)
    repository_metrics = profile["repository"]
    evidence_metrics = profile["evidence"]
    proposed_diff_bytes = diff_bytes(repository)
    metrics = {
        "untracked_count": int(repository_metrics["untracked_count"]),
        "untracked_bytes": int(repository_metrics["untracked_bytes"]),
        "tracked_evidence_count": int(evidence_metrics["tracked_count"]),
        "tracked_evidence_bytes": int(evidence_metrics["tracked_bytes"]),
        "untracked_evidence_count": int(evidence_metrics["untracked_count"]),
        "untracked_evidence_bytes": int(evidence_metrics["untracked_bytes"]),
        "diff_bytes": proposed_diff_bytes,
    }
    effective_count, count_source = threshold(
        policy,
        "untracked_count",
        count_threshold,
        max(1, int(repository_metrics["tracked_count"]) // 20),
        HARD_COUNT_LIMIT,
    )
    effective_bytes, bytes_source = threshold(
        policy,
        "untracked_bytes",
        bytes_threshold,
        int(repository_metrics["tracked_bytes"]) // 20,
        HARD_BYTES_LIMIT,
    )
    effective_diff, diff_source = threshold(
        policy,
        "diff_bytes",
        diff_threshold,
        int(repository_metrics["tracked_bytes"]) // 50,
        HARD_DIFF_LIMIT,
    )
    profile["risk_budget"] = {
        "untracked_count": {"value": effective_count, "source": count_source, "hard_limit": HARD_COUNT_LIMIT},
        "untracked_bytes": {"value": effective_bytes, "source": bytes_source, "hard_limit": HARD_BYTES_LIMIT},
        "diff_bytes": {"value": effective_diff, "source": diff_source, "hard_limit": HARD_DIFF_LIMIT},
    }

    findings = [
        Finding("INVALID_EVIDENCE_POLICY", error, "action_required", "workspace-policy", "fix-policy")
        for error in policy_errors
    ]
    if metrics["untracked_count"] > effective_count:
        findings.append(Finding(
            "UNTRACKED_COUNT",
            f"{metrics['untracked_count']} untracked files exceed the workspace budget of {effective_count}",
            source=count_source,
            mitigation="prepare",
        ))
    if metrics["untracked_bytes"] > effective_bytes:
        findings.append(Finding(
            "UNTRACKED_BYTES",
            f"untracked files total {format_bytes(metrics['untracked_bytes'])}, exceeding "
            f"the workspace budget of {format_bytes(effective_bytes)}",
            source=bytes_source,
            mitigation="prepare",
        ))

    generated_prefix = evidence_path(policy).rstrip("/") + "/"
    binaries = []
    for relative in git_paths(repository, "ls-files", "--cached", "-z", "--", "work"):
        path = repository / relative
        if relative.startswith(generated_prefix):
            continue
        if path.is_file() and is_binary(path):
            binaries.append(Path(relative).as_posix())
    if binaries:
        preview = ", ".join(binaries[:5])
        suffix = f" (and {len(binaries) - 5} more)" if len(binaries) > 5 else ""
        findings.append(Finding(
            "BINARY_IN_VERSIONED_WORK",
            f"binary files appear beneath versioned work/ paths: {preview}{suffix}",
            source="repository-composition",
            mitigation="prepare",
        ))
    if proposed_diff_bytes > effective_diff:
        findings.append(Finding(
            "DIFF_BYTES",
            f"proposed tracked diff is {format_bytes(proposed_diff_bytes)}, exceeding "
            f"the workspace budget of {format_bytes(effective_diff)}",
            source=diff_source,
            mitigation="fresh-handoff",
        ))
    if metrics["untracked_count"] > HARD_COUNT_LIMIT or metrics["untracked_bytes"] > HARD_BYTES_LIMIT:
        findings.append(Finding(
            "HARD_WORKSPACE_LIMIT",
            "workspace exceeds a non-overridable generated-state safety limit",
            "action_required",
            "hard-safety-limit",
            "prepare",
        ))
    if proposed_diff_bytes > HARD_DIFF_LIMIT:
        findings.append(Finding(
            "HARD_DIFF_LIMIT",
            f"tracked diff exceeds the non-overridable {format_bytes(HARD_DIFF_LIMIT)} safety limit",
            "action_required",
            "hard-safety-limit",
            "fresh-handoff",
        ))
    backups = visible_backups(repository)
    if backups:
        findings.append(Finding(
            "VISIBLE_TOOL_SHED_BACKUP",
            "Tool Shed backup archives are visible to Git: " + ", ".join(backups),
            source="repository-policy",
            mitigation="ignore-or-relocate",
        ))
    return repository, findings, metrics, profile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile a workspace and warn about Git hydration risks.")
    parser.add_argument("--workspace", default=".", help="Project workspace root.")
    parser.add_argument("--untracked-count", type=int, default=DEFAULT_COUNT_THRESHOLD)
    parser.add_argument("--untracked-bytes", type=int, default=DEFAULT_BYTES_THRESHOLD)
    parser.add_argument("--diff-bytes", type=int, default=DEFAULT_DIFF_THRESHOLD)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when warnings are found.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository, findings, metrics, profile = inspect(
        Path(args.workspace).expanduser().resolve(),
        count_threshold=args.untracked_count,
        bytes_threshold=args.untracked_bytes,
        diff_threshold=args.diff_bytes,
    )
    if args.json:
        print(json.dumps({
            "schema_version": 2,
            "repository": str(repository) if repository else None,
            "profile": profile,
            "metrics": metrics,
            "findings": [asdict(finding) for finding in findings],
        }, indent=2, sort_keys=True))
    elif repository is None:
        print("Workspace preflight skipped: no Git repository found.")
    elif findings:
        print("Workspace preflight warnings:")
        for finding in findings:
            print(
                f"- [{finding.code}] {finding.message} "
                f"(source: {finding.source}; mitigation: {finding.mitigation})"
            )
        print(
            "Store raw outputs in the profile's generated path and summarize them "
            "with a small versioned manifest."
        )
    else:
        print(
            "Workspace preflight passed: "
            f"{metrics['untracked_count']} untracked file(s), "
            f"{format_bytes(metrics['untracked_bytes'])} untracked, "
            f"{metrics['tracked_evidence_count']} tracked evidence file(s), "
            f"{format_bytes(metrics['diff_bytes'])} tracked diff."
        )
    return 1 if args.strict and findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
