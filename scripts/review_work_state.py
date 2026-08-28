from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from repository_policy import POLICY_FILE, format_bytes, inspect_snapshot_ignore, inspect_work_ignore
from update_work_index import Artifact, discover_artifacts


ACTIVE_STATUSES = {"active", "blocked", "exploring", "proposed", "queued", "ready-for-prm", "working"}
FINISHED_STATUSES = {"accepted", "complete", "completed", "decided", "done", "promoted", "superseded"}
PLACEHOLDER_VALUES = {"", "-", "...", "none", "work/...", "work/maps/..."}
WORK_PATH = re.compile(r"(?<![\w/])(work/[A-Za-z0-9_./-]+\.md)")


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    path: str
    message: str


def normalized(value: str | None) -> str:
    return (value or "").strip().lower()


def planning_references(artifact: Artifact, workspace: Path) -> set[str]:
    lines = (workspace / artifact.path).read_text(encoding="utf-8").splitlines()
    references = set(WORK_PATH.findall(artifact.fields.get("Next Action", "")))
    for key in ("Parent", "Project Map", "Depends On"):
        references.update(WORK_PATH.findall(artifact.fields.get(key, "")))

    section = ""
    in_do_next = False
    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith("## "):
            section = line[3:].strip().lower()
            in_do_next = False
            continue
        if line.lower() == "do next:":
            in_do_next = True
            continue
        if in_do_next and line.lower().endswith(":") and not line.startswith(("-", "*")):
            in_do_next = False
        if re.match(r"^[-*]\s+\[ \]\s+", line) or in_do_next:
            references.update(WORK_PATH.findall(line))
        if section == "workstreams" and line.startswith("|") and "---" not in line:
            cells = [cell.strip().lower() for cell in line.strip("|").split("|")]
            if len(cells) >= 2 and cells[1] in ACTIVE_STATUSES:
                references.update(WORK_PATH.findall(line))
    return references


def add_header_findings(
    artifact: Artifact,
    *,
    artifacts_by_path: dict[str, Artifact],
    stale_days: int,
    today: date,
) -> list[Finding]:
    findings: list[Finding] = []
    path = artifact.path.as_posix()
    status = normalized(artifact.status())
    kind = normalized(artifact.kind())

    if status in ACTIVE_STATUSES:
        if normalized(artifact.fields.get("Next Action")) in PLACEHOLDER_VALUES:
            findings.append(Finding("EMPTY_NEXT_ACTION", "error", path, "active artifact needs a concrete Next Action"))

        updated = artifact.fields.get("Updated", "")
        try:
            age = (today - datetime.strptime(updated, "%Y-%m-%d").date()).days
        except ValueError:
            findings.append(Finding("INVALID_UPDATED", "error", path, "Updated must use YYYY-MM-DD"))
        else:
            if age > stale_days:
                findings.append(
                    Finding("STALE_ACTIVE", "warning", path, f"active artifact has not been updated for {age} days")
                )

        if kind not in {"idea-brief", "project-map", "campaign", "focus-area-catalog", "program-roadmap"}:
            parent = artifact.fields.get("Parent") or artifact.fields.get("Project Map") or ""
            if normalized(parent) in PLACEHOLDER_VALUES:
                findings.append(
                    Finding("ORPHAN_ACTIVE", "warning", path, "active artifact has no concrete Parent or Project Map")
                )
            else:
                parent_paths = WORK_PATH.findall(parent)
                if not parent_paths:
                    findings.append(
                        Finding("INVALID_PARENT", "error", path, "Parent or Project Map does not contain a work/*.md path")
                    )
                for candidate in parent_paths:
                    if candidate not in artifacts_by_path:
                        findings.append(
                            Finding("BROKEN_PARENT", "error", path, f"parent artifact does not exist: {candidate}")
                        )

    if kind == "spike" and status in FINISHED_STATUSES:
        disposition = normalized(artifact.fields.get("Disposition"))
        allowed = {"documented", "no-action", "planned", "superseded"}
        if disposition not in allowed:
            findings.append(
                Finding(
                    "UNDISPOSED_SPIKE",
                    "error",
                    path,
                    "finished spike needs Disposition: documented, no-action, planned, or superseded",
                )
            )
        if disposition == "planned":
            produces = WORK_PATH.findall(artifact.fields.get("Produces", ""))
            if not produces:
                findings.append(
                    Finding("MISSING_SPIKE_OUTPUT", "error", path, "planned spike needs Produces: work/...md")
                )
            for candidate in produces:
                if candidate not in artifacts_by_path:
                    findings.append(
                        Finding("BROKEN_SPIKE_OUTPUT", "error", path, f"produced artifact does not exist: {candidate}")
                    )
    return findings


def gitignore_findings(workspace: Path) -> list[Finding]:
    state = inspect_work_ignore(workspace)
    findings: list[Finding] = []
    if state.repository is not None and state.match is not None and not state.exception_reason:
        match = state.match
        exception = f" Invalid exception: {state.exception_error}" if state.exception_error else ""
        findings.append(
            Finding(
                "UNDOCUMENTED_WORK_IGNORE",
                "error",
                "work/",
                (
                    f"root work/ is ignored by {match.source}:{match.line}: {match.rule!r} "
                    f"(matched {match.path}); {state.file_count} file(s), {format_bytes(state.total_bytes)}, "
                    f"are currently ignored. Remove only that root rule or document an intentional "
                    f"exception in {POLICY_FILE}.{exception}"
                ),
            )
        )
    repository, snapshot_match = inspect_snapshot_ignore(workspace)
    if repository is not None and (repository / "tool_shed").exists() and snapshot_match is None:
        findings.append(
            Finding(
                "TOOL_SHED_NOT_IGNORED",
                "error",
                "tool_shed/",
                "disconnected snapshot is trackable; add /tool_shed/ to the repository-root .gitignore",
            )
        )
    return findings


def review(workspace: Path, *, stale_days: int, today: date) -> list[Finding]:
    work_dir = workspace / "work"
    artifacts = discover_artifacts(work_dir) if work_dir.exists() else []
    artifacts_by_path = {artifact.path.as_posix(): artifact for artifact in artifacts}
    findings = gitignore_findings(workspace)
    references = {
        artifact.path.as_posix(): planning_references(artifact, workspace) for artifact in artifacts
    }
    for artifact in artifacts:
        findings.extend(
            add_header_findings(
                artifact,
                artifacts_by_path=artifacts_by_path,
                stale_days=stale_days,
                today=today,
            )
        )

    active_paths = {
        artifact.path.as_posix()
        for artifact in artifacts
        if normalized(artifact.status()) in ACTIVE_STATUSES
    }
    for source, targets in references.items():
        if source not in active_paths:
            continue
        for target in sorted(targets):
            linked = artifacts_by_path.get(target)
            if linked and normalized(linked.status()) in FINISHED_STATUSES:
                findings.append(
                    Finding("PLAN_DRIFT", "warning", source, f"active artifact references finished artifact: {target}")
                )

    return sorted(set(findings), key=lambda item: (item.severity, item.code, item.path, item.message))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review work artifacts for planning and lifecycle drift.")
    parser.add_argument("--workspace", default=".", help="Project workspace root. Defaults to current directory.")
    parser.add_argument("--stale-days", type=int, default=30, help="Warn when active work is older than this.")
    parser.add_argument("--today", help="Override today's date as YYYY-MM-DD for deterministic checks.")
    parser.add_argument("--json", action="store_true", help="Write a machine-readable report.")
    parser.add_argument("--strict", action="store_true", help="Return exit status 1 when any finding exists.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.stale_days < 0:
        raise SystemExit("--stale-days must be zero or greater")
    workspace = Path(args.workspace).expanduser().resolve()
    today = datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else date.today()
    findings = review(workspace, stale_days=args.stale_days, today=today)
    if args.json:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "workspace": str(workspace),
                    "stale_days": args.stale_days,
                    "findings": [asdict(finding) for finding in findings],
                    "summary": {
                        "total": len(findings),
                        "errors": sum(item.severity == "error" for item in findings),
                        "warnings": sum(item.severity == "warning" for item in findings),
                    },
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif findings:
        for finding in findings:
            print(f"{finding.severity.upper():7} {finding.code:20} {finding.path}: {finding.message}")
        print(f"{len(findings)} work-state finding(s).")
    else:
        print("Work state is reconciled.")
    return 1 if args.strict and findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
