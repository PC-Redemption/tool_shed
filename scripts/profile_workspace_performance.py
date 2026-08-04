#!/usr/bin/env python3
"""Measure privacy-safe workspace scale and read-only operation timings."""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import statistics
import subprocess
import sys
import time
import uuid
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from check_stale_paths import scan as scan_stale_paths
from repository_policy import git_repository
from review_work_state import review as review_work_state
from update_work_index import discover_artifacts
from workspace_preflight import inspect as inspect_preflight


SCHEMA_VERSION = 1
PROFILER_VERSION = 1
PROBE_NAMES = (
    "git_tracked_inventory",
    "git_status_tracked_only",
    "git_status_with_untracked",
    "filesystem_inventory",
    "work_artifact_parse",
    "stale_path_review",
    "work_state_review",
)
PROBE_STATUSES = {"ok", "timeout", "unsupported", "error"}
ACTIVE_STATUSES = {"active", "blocked", "proposed"}
FINISHED_STATUSES = {"accepted", "complete", "completed", "decided", "done"}
KNOWN_KINDS = (
    "adr",
    "checklist",
    "decision-matrix",
    "evidence",
    "incident",
    "inventory",
    "project-map",
    "runbook",
    "spike",
    "ticket",
    "workpackage",
    "other",
)
TEXT_SUFFIXES = {
    ".c", ".cc", ".cfg", ".conf", ".cpp", ".css", ".csv", ".go", ".h", ".hpp",
    ".html", ".ini", ".java", ".js", ".json", ".jsx", ".md", ".py", ".rb", ".rs",
    ".sh", ".sql", ".toml", ".ts", ".tsx", ".txt", ".xml", ".yaml", ".yml",
}
ARCHIVE_SUFFIXES = {".7z", ".bz2", ".gz", ".rar", ".tar", ".tgz", ".xz", ".zip"}
BINARY_SUFFIXES = {
    ".bin", ".bmp", ".cap", ".dll", ".dmp", ".exe", ".gif", ".heic", ".ico", ".jpeg",
    ".jpg", ".mp3", ".mp4", ".o", ".obj", ".pcap", ".pdf", ".png", ".slg", ".so",
    ".wav", ".webp",
}
WARNING_CODE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def normalized(value: str | None) -> str:
    return (value or "").strip().lower()


def exact_keys(value: object, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(f"{label} fields mismatch; missing={missing}, unknown={unknown}")
    return value


def require_nonnegative_int(value: object, label: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")


def require_number(value: object, label: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} must be a non-negative number")


def validate_report(report: object) -> dict[str, Any]:
    """Reject unknown or malformed saved-report fields before serialization."""
    root = exact_keys(
        report,
        {
            "schema_version", "profile_id", "collected_at", "collector", "environment",
            "repository", "tool_shed_work", "benchmarks", "limits", "warnings",
        },
        "report",
    )
    if root["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported report schema_version")
    try:
        uuid.UUID(str(root["profile_id"]))
    except (ValueError, AttributeError) as error:
        raise ValueError("profile_id must be a UUID") from error
    if not isinstance(root["collected_at"], str) or not root["collected_at"].endswith("Z"):
        raise ValueError("collected_at must be an RFC3339 UTC timestamp")

    collector = exact_keys(root["collector"], {"tool_shed_version", "profiler_version"}, "collector")
    if not isinstance(collector["tool_shed_version"], str) or collector["profiler_version"] != PROFILER_VERSION:
        raise ValueError("collector version fields are invalid")
    environment = exact_keys(
        root["environment"], {"os_family", "python", "filesystem_family", "git_version"}, "environment"
    )
    if any(not isinstance(value, str) for value in environment.values()):
        raise ValueError("environment values must be strings")

    repository = exact_keys(
        root["repository"],
        {
            "tracked", "untracked", "ignored", "dirty_entries", "diff_bytes", "directory_count",
            "maximum_depth", "size_buckets", "content_classes",
        },
        "repository",
    )
    for name in ("tracked", "untracked"):
        bucket = exact_keys(repository[name], {"files", "bytes"}, f"repository.{name}")
        require_nonnegative_int(bucket["files"], f"repository.{name}.files")
        require_nonnegative_int(bucket["bytes"], f"repository.{name}.bytes")
    ignored = exact_keys(repository["ignored"], {"files", "bytes", "sampled"}, "repository.ignored")
    require_nonnegative_int(ignored["files"], "repository.ignored.files")
    require_nonnegative_int(ignored["bytes"], "repository.ignored.bytes")
    if not isinstance(ignored["sampled"], bool):
        raise ValueError("repository.ignored.sampled must be boolean")
    for name in ("dirty_entries", "diff_bytes", "directory_count", "maximum_depth"):
        require_nonnegative_int(repository[name], f"repository.{name}")
    sizes = exact_keys(
        repository["size_buckets"], {"under_4k", "4k_to_1m", "1m_to_10m", "over_10m"},
        "repository.size_buckets",
    )
    classes = exact_keys(
        repository["content_classes"], {"text", "binary", "archive", "unknown"},
        "repository.content_classes",
    )
    for label, bucket in (("size_buckets", sizes), ("content_classes", classes)):
        for name, value in bucket.items():
            require_nonnegative_int(value, f"repository.{label}.{name}")

    work = exact_keys(
        root["tool_shed_work"],
        {"files", "bytes", "by_lifecycle", "by_kind", "age_buckets_days", "generated_evidence"},
        "tool_shed_work",
    )
    require_nonnegative_int(work["files"], "tool_shed_work.files")
    require_nonnegative_int(work["bytes"], "tool_shed_work.bytes")
    lifecycle = exact_keys(work["by_lifecycle"], {"active", "finished", "superseded", "other"}, "by_lifecycle")
    kinds = exact_keys(work["by_kind"], set(KNOWN_KINDS), "by_kind")
    ages = exact_keys(
        work["age_buckets_days"], {"0_to_30", "31_to_90", "91_to_365", "over_365", "unknown"},
        "age_buckets_days",
    )
    generated = exact_keys(
        work["generated_evidence"],
        {"tracked_files", "tracked_bytes", "untracked_files", "untracked_bytes"},
        "generated_evidence",
    )
    for label, bucket in (("by_lifecycle", lifecycle), ("by_kind", kinds), ("age_buckets_days", ages), ("generated_evidence", generated)):
        for name, value in bucket.items():
            require_nonnegative_int(value, f"tool_shed_work.{label}.{name}")

    benchmarks = exact_keys(root["benchmarks"], set(PROBE_NAMES), "benchmarks")
    for name, raw_probe in benchmarks.items():
        probe = exact_keys(
            raw_probe, {"first_observed_ms", "samples_ms", "median_ms", "p95_ms", "status"},
            f"benchmarks.{name}",
        )
        require_number(probe["first_observed_ms"], f"benchmarks.{name}.first_observed_ms")
        if not isinstance(probe["samples_ms"], list):
            raise ValueError(f"benchmarks.{name}.samples_ms must be an array")
        for index, sample in enumerate(probe["samples_ms"]):
            require_number(sample, f"benchmarks.{name}.samples_ms[{index}]")
        require_number(probe["median_ms"], f"benchmarks.{name}.median_ms")
        require_number(probe["p95_ms"], f"benchmarks.{name}.p95_ms")
        if probe["status"] not in PROBE_STATUSES:
            raise ValueError(f"benchmarks.{name}.status is invalid")

    limits = exact_keys(root["limits"], {"rounds", "per_probe_timeout_seconds", "random_seed"}, "limits")
    for name in limits:
        require_nonnegative_int(limits[name], f"limits.{name}")
    if not isinstance(root["warnings"], list) or any(
        not isinstance(code, str) or WARNING_CODE.fullmatch(code) is None for code in root["warnings"]
    ):
        raise ValueError("warnings must contain stable uppercase codes")
    return root


def version_fields(root: Path) -> tuple[str, str]:
    shed_version = "unknown"
    try:
        payload = json.loads((root / "SHED_VERSION.json").read_text(encoding="utf-8"))
        candidate = payload.get("shed_version")
        if isinstance(candidate, str) and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", candidate):
            shed_version = candidate
    except (OSError, json.JSONDecodeError):
        pass
    result = subprocess.run(
        ["git", "--version"], check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    match = re.search(r"([0-9]+\.[0-9]+)", result.stdout)
    return shed_version, match.group(1) if match else "unknown"


def filesystem_family(root: Path) -> str:
    if sys.platform.startswith("linux"):
        try:
            lines = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
            candidates: list[tuple[int, str]] = []
            resolved = root.resolve().as_posix()
            for line in lines:
                left, right = line.split(" - ", 1)
                fields = left.split()
                mountpoint = fields[4].replace("\\040", " ")
                fs_type = right.split()[0]
                if resolved == mountpoint or resolved.startswith(mountpoint.rstrip("/") + "/"):
                    candidates.append((len(mountpoint), fs_type))
            if candidates:
                fs_type = max(candidates)[1]
                if fs_type == "overlay":
                    return "container-overlay"
                if fs_type in {"nfs", "nfs4", "cifs", "fuse.sshfs", "9p"}:
                    return "network"
                return "local"
        except (OSError, ValueError, IndexError):
            pass
    return "local" if os.name in {"nt", "posix"} else "unknown"


def classify_suffix(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in ARCHIVE_SUFFIXES:
        return "archive"
    if suffix in BINARY_SUFFIXES:
        return "binary"
    if suffix in TEXT_SUFFIXES or not suffix:
        return "text"
    return "unknown"


def filesystem_summary(root: Path) -> dict[str, Any]:
    root_device = root.stat().st_dev
    directory_count = 0
    maximum_depth = 0
    skipped_boundaries = 0
    size_buckets: Counter[str] = Counter()
    content_classes: Counter[str] = Counter()
    for current_text, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current = Path(current_text)
        if current == root:
            dirs[:] = [name for name in dirs if name != ".git"]
        retained = []
        for name in dirs:
            candidate = current / name
            try:
                if candidate.is_symlink() or candidate.stat().st_dev != root_device:
                    skipped_boundaries += 1
                    continue
            except OSError:
                skipped_boundaries += 1
                continue
            retained.append(name)
        dirs[:] = retained
        directory_count += len(dirs)
        try:
            depth = len(current.relative_to(root).parts)
        except ValueError:
            depth = 0
        maximum_depth = max(maximum_depth, depth)
        for name in files:
            path = current / name
            try:
                if path.is_symlink() or path.stat().st_dev != root_device:
                    skipped_boundaries += 1
                    continue
                size = path.stat().st_size
            except OSError:
                skipped_boundaries += 1
                continue
            if size < 4 * 1024:
                size_buckets["under_4k"] += 1
            elif size < 1024 * 1024:
                size_buckets["4k_to_1m"] += 1
            elif size < 10 * 1024 * 1024:
                size_buckets["1m_to_10m"] += 1
            else:
                size_buckets["over_10m"] += 1
            content_classes[classify_suffix(path)] += 1
    return {
        "directory_count": directory_count,
        "maximum_depth": maximum_depth,
        "size_buckets": {name: size_buckets[name] for name in ("under_4k", "4k_to_1m", "1m_to_10m", "over_10m")},
        "content_classes": {name: content_classes[name] for name in ("text", "binary", "archive", "unknown")},
        "skipped_boundaries": skipped_boundaries,
    }


def ignored_summary(root: Path, timeout: int) -> tuple[dict[str, Any], str | None]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "-z"],
            cwd=root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"files": 0, "bytes": 0, "sampled": True}, "IGNORED_INVENTORY_TIMEOUT"
    if result.returncode:
        return {"files": 0, "bytes": 0, "sampled": True}, "IGNORED_INVENTORY_ERROR"
    count = 0
    total = 0
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        path = root / os.fsdecode(raw)
        try:
            if path.is_symlink() or not path.is_file():
                continue
            total += path.stat().st_size
            count += 1
        except OSError:
            continue
    return {"files": count, "bytes": total, "sampled": False}, None


def lifecycle_name(status: str) -> str:
    status = normalized(status)
    if status == "superseded":
        return "superseded"
    if status in ACTIVE_STATUSES:
        return "active"
    if status in FINISHED_STATUSES:
        return "finished"
    return "other"


def artifact_summary(root: Path, today: date) -> dict[str, Any]:
    work = root / "work"
    artifacts = discover_artifacts(work) if work.exists() else []
    lifecycles: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    ages: Counter[str] = Counter()
    total_bytes = 0
    for artifact in artifacts:
        lifecycles[lifecycle_name(artifact.status())] += 1
        kind = normalized(artifact.kind())
        kinds[kind if kind in KNOWN_KINDS else "other"] += 1
        try:
            total_bytes += (root / artifact.path).stat().st_size
        except OSError:
            pass
        try:
            updated = datetime.strptime(artifact.fields.get("Updated", ""), "%Y-%m-%d").date()
            age = max(0, (today - updated).days)
        except ValueError:
            ages["unknown"] += 1
        else:
            if age <= 30:
                ages["0_to_30"] += 1
            elif age <= 90:
                ages["31_to_90"] += 1
            elif age <= 365:
                ages["91_to_365"] += 1
            else:
                ages["over_365"] += 1
    return {
        "files": len(artifacts),
        "bytes": total_bytes,
        "by_lifecycle": {name: lifecycles[name] for name in ("active", "finished", "superseded", "other")},
        "by_kind": {name: kinds[name] for name in KNOWN_KINDS},
        "age_buckets_days": {name: ages[name] for name in ("0_to_30", "31_to_90", "91_to_365", "over_365", "unknown")},
    }


def internal_probe(name: str, root: Path) -> None:
    if name == "filesystem_inventory":
        filesystem_summary(root)
    elif name == "work_artifact_parse":
        discover_artifacts(root / "work") if (root / "work").exists() else []
    elif name == "stale_path_review":
        scan_stale_paths(root)
    elif name == "work_state_review":
        review_work_state(root, stale_days=30, today=date.today())
    else:
        raise ValueError(f"not an internal probe: {name}")


def probe_command(name: str, root: Path) -> list[str]:
    if name == "git_tracked_inventory":
        return ["git", "ls-files", "-z"]
    if name == "git_status_tracked_only":
        return ["git", "status", "--porcelain=v1", "--untracked-files=no", "-z"]
    if name == "git_status_with_untracked":
        return ["git", "status", "--porcelain=v1", "-z"]
    return [sys.executable, str(Path(__file__).resolve()), "--workspace", str(root), "--probe", name]


def one_probe(name: str, root: Path, timeout: int) -> tuple[float, str]:
    started = time.perf_counter_ns()
    try:
        result = subprocess.run(
            probe_command(name, root),
            cwd=root,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return round((time.perf_counter_ns() - started) / 1_000_000, 3), "timeout"
    except OSError:
        return round((time.perf_counter_ns() - started) / 1_000_000, 3), "unsupported"
    duration = round((time.perf_counter_ns() - started) / 1_000_000, 3)
    return duration, "ok" if result.returncode == 0 else "error"


def nearest_rank_p95(samples: list[float]) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def benchmark_probes(root: Path, rounds: int, timeout: int, seed: int) -> dict[str, Any]:
    first: dict[str, tuple[float, str]] = {name: one_probe(name, root, timeout) for name in PROBE_NAMES}
    samples: dict[str, list[float]] = {name: [] for name in PROBE_NAMES}
    statuses = {name: status for name, (_duration, status) in first.items()}
    generator = random.Random(seed)
    for _round in range(rounds):
        order = list(PROBE_NAMES)
        generator.shuffle(order)
        for name in order:
            if statuses[name] != "ok":
                continue
            duration, status = one_probe(name, root, timeout)
            if status == "ok":
                samples[name].append(duration)
            else:
                statuses[name] = status
    result = {}
    for name in PROBE_NAMES:
        repeated = samples[name]
        result[name] = {
            "first_observed_ms": first[name][0],
            "samples_ms": repeated,
            "median_ms": round(statistics.median(repeated), 3) if repeated else 0.0,
            "p95_ms": round(nearest_rank_p95(repeated), 3),
            "status": statuses[name],
        }
    return result


def _build_report(root: Path, *, profile_id: str, rounds: int, timeout: int, seed: int) -> dict[str, Any]:
    repository, findings, metrics, profile = inspect_preflight(root)
    if repository is None or repository.resolve() != root.resolve():
        raise ValueError("workspace must be the Git repository root")
    filesystem = filesystem_summary(root)
    ignored, ignored_warning = ignored_summary(root, timeout)
    work = artifact_summary(root, date.today())
    evidence = profile.get("evidence", {})
    work["generated_evidence"] = {
        "tracked_files": int(evidence.get("tracked_count", 0)),
        "tracked_bytes": int(evidence.get("tracked_bytes", 0)),
        "untracked_files": int(evidence.get("untracked_count", 0)),
        "untracked_bytes": int(evidence.get("untracked_bytes", 0)),
    }
    repository_profile = profile.get("repository", {})
    warnings = {finding.code for finding in findings}
    if ignored_warning:
        warnings.add(ignored_warning)
    if filesystem["skipped_boundaries"]:
        warnings.add("FILESYSTEM_BOUNDARY_SKIPPED")
    benchmarks = benchmark_probes(root, rounds, timeout, seed)
    for name, probe in benchmarks.items():
        if probe["status"] != "ok":
            warnings.add(f"PROBE_{name.upper()}_{probe['status'].upper()}")
    shed_version, git_version = version_fields(Path(__file__).resolve().parents[1])
    os_family = "windows" if os.name == "nt" else "macos" if sys.platform == "darwin" else "linux" if sys.platform.startswith("linux") else "other"
    report = {
        "schema_version": SCHEMA_VERSION,
        "profile_id": profile_id,
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "collector": {"tool_shed_version": shed_version, "profiler_version": PROFILER_VERSION},
        "environment": {
            "os_family": os_family,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
            "filesystem_family": filesystem_family(root),
            "git_version": git_version,
        },
        "repository": {
            "tracked": {
                "files": int(repository_profile.get("tracked_count", 0)),
                "bytes": int(repository_profile.get("tracked_bytes", 0)),
            },
            "untracked": {
                "files": int(repository_profile.get("untracked_count", 0)),
                "bytes": int(repository_profile.get("untracked_bytes", 0)),
            },
            "ignored": ignored,
            "dirty_entries": int(repository_profile.get("dirty_entries", 0)),
            "diff_bytes": int(metrics.get("diff_bytes", 0)),
            "directory_count": int(filesystem["directory_count"]),
            "maximum_depth": int(filesystem["maximum_depth"]),
            "size_buckets": filesystem["size_buckets"],
            "content_classes": filesystem["content_classes"],
        },
        "tool_shed_work": work,
        "benchmarks": benchmarks,
        "limits": {"rounds": rounds, "per_probe_timeout_seconds": timeout, "random_seed": seed},
        "warnings": sorted(warnings),
    }
    return validate_report(report)


def build_report(root: Path, *, profile_id: str, rounds: int, timeout: int, seed: int) -> dict[str, Any]:
    previous = os.environ.get("GIT_OPTIONAL_LOCKS")
    os.environ["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        return _build_report(root, profile_id=profile_id, rounds=rounds, timeout=timeout, seed=seed)
    finally:
        if previous is None:
            os.environ.pop("GIT_OPTIONAL_LOCKS", None)
        else:
            os.environ["GIT_OPTIONAL_LOCKS"] = previous


def render_human(report: dict[str, Any], workspace: Path) -> str:
    repository = report["repository"]
    work = report["tool_shed_work"]
    lines = [
        f"Workspace performance profile: {workspace}",
        f"Profile ID: {report['profile_id']}",
        (
            f"Repository: {repository['tracked']['files']} tracked file(s), "
            f"{repository['untracked']['files']} untracked, {repository['ignored']['files']} ignored"
        ),
        (
            f"Tool Shed work: {work['files']} artifact(s); "
            f"{work['by_lifecycle']['active']} active, {work['by_lifecycle']['finished']} finished, "
            f"{work['by_lifecycle']['superseded']} superseded"
        ),
        "Benchmarks (first observed / median / p95 ms):",
    ]
    for name in PROBE_NAMES:
        probe = report["benchmarks"][name]
        lines.append(
            f"- {name}: {probe['first_observed_ms']:.3f} / {probe['median_ms']:.3f} / "
            f"{probe['p95_ms']:.3f} [{probe['status']}]"
        )
    lines.append("Warnings: " + (", ".join(report["warnings"]) if report["warnings"] else "none"))
    lines.append("This report measures correlation surfaces; it cannot prove undocumented Codex hashing or indexing.")
    return "\n".join(lines)


def write_report(path: Path, report: dict[str, Any], *, force: bool) -> None:
    validate_report(report)
    path = path.expanduser()
    if not path.parent.is_dir():
        raise ValueError("output parent directory must already exist")
    mode = "w" if force else "x"
    with path.open(mode, encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".", help="Git repository root to measure")
    parser.add_argument("--profile-id", help="UUID used to correlate explicitly approved reports")
    parser.add_argument("--rounds", type=int, default=5, help="Repeated samples per probe after the first observation")
    parser.add_argument("--timeout", type=int, default=30, help="Per-probe timeout in seconds")
    parser.add_argument("--seed", type=int, help="Random seed for repeated probe ordering")
    parser.add_argument("--json", action="store_true", help="Print the sanitized JSON report")
    parser.add_argument("--output", help="Explicit path for a sanitized JSON report")
    parser.add_argument("--force", action="store_true", help="Overwrite an explicitly supplied output path")
    parser.add_argument("--probe", choices=PROBE_NAMES, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.workspace).expanduser().resolve()
    if args.probe:
        if args.probe in {"git_tracked_inventory", "git_status_tracked_only", "git_status_with_untracked"}:
            raise SystemExit("Git probes are executed directly")
        internal_probe(args.probe, root)
        return 0
    if args.rounds < 1:
        raise SystemExit("--rounds must be at least 1")
    if args.timeout < 1:
        raise SystemExit("--timeout must be at least 1")
    try:
        profile_id = str(uuid.UUID(args.profile_id)) if args.profile_id else str(uuid.uuid4())
        seed = args.seed if args.seed is not None else random.SystemRandom().randrange(0, 2**32)
        report = build_report(root, profile_id=profile_id, rounds=args.rounds, timeout=args.timeout, seed=seed)
        if args.output:
            write_report(Path(args.output), report, force=args.force)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render_human(report, root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
