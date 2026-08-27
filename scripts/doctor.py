#!/usr/bin/env python3
"""Audit a Tool Shed workspace for cross-surface consistency and integrity."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import campaign_queue
import check_shed_version
import check_stale_paths
import check_work_tree
import reconcile_campaign_queue
import review_work_state
import update_work_index
import workspace_preflight
from project_identity import (
    ProjectIdentityError,
    bind_state_token,
    require_path_within,
    require_project_binding,
    resolved_workspace,
    target_capsule,
)


SCHEMA_VERSION = 1
OPERATION = "doctor-repair"
FINDING_CLASSES = (
    "error",
    "warning",
    "owner-decision-required",
    "external-evidence-required",
)
RUNTIME_CLAIM_RE = re.compile(
    r"\b(?:deployed?|production|runtime|live site|public (?:route|url|site)|"
    r"browser|container|https?://|github (?:run|issue|workflow)|release)\b",
    re.IGNORECASE,
)
EVIDENCE_PATH_RE = re.compile(
    r"(?<![\w/])(work/(?:evidence|incidents|runbooks|spikes)/[A-Za-z0-9_./-]+\.(?:md|json))"
)
CAMPAIGN_DIR = "work/00-campaigns/"
RELEVANT_ROOT_PATHS = {
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".github/copilot-instructions.md",
    ".cursor/rules/tool-shed.mdc",
    "SHED_VERSION.json",
}


@dataclass(frozen=True)
class Finding:
    code: str
    classification: str
    summary: str
    next_action: str
    affected_count: int = 1
    sample_paths: tuple[str, ...] = ()


class DoctorError(ValueError):
    pass


def _git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _compact_paths(paths: list[str], limit: int = 5) -> tuple[str, ...]:
    return tuple(sorted(dict.fromkeys(paths))[:limit])


def locate_shed(workspace: Path) -> Path:
    installed = workspace / "tool_shed"
    canonical_markers = (
        workspace / "selection.md",
        workspace / "conventions.md",
        workspace / "scripts",
        workspace / "templates",
    )
    if installed.is_dir():
        shed = installed
    elif all(path.exists() for path in canonical_markers):
        shed = workspace
    else:
        raise DoctorError("Tool Shed is not installed in the resolved workspace")
    return require_path_within(workspace, shed)


def git_state(workspace: Path, shed: Path) -> dict[str, Any]:
    top = _git(workspace, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        raise DoctorError("workspace is not a Git repository")
    git_root = Path(os.fsdecode(top.stdout).strip()).resolve()
    if git_root != workspace:
        raise DoctorError(f"WORKSPACE_MISMATCH: Git root {git_root} differs from {workspace}")
    branch_result = _git(workspace, "symbolic-ref", "--quiet", "--short", "HEAD")
    head_result = _git(workspace, "rev-parse", "--verify", "HEAD")
    status_result = _git(workspace, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if status_result.returncode != 0:
        raise DoctorError("Git status failed")
    entries: list[dict[str, str]] = []
    parts = [item for item in status_result.stdout.split(b"\0") if item]
    index = 0
    while index < len(parts):
        raw = os.fsdecode(parts[index])
        status = raw[:2]
        path = raw[3:]
        if status[0] in {"R", "C"} and index + 1 < len(parts):
            index += 1
            path = os.fsdecode(parts[index])
        entries.append({"status": status, "path": path})
        index += 1
    shed_relative = shed.relative_to(workspace).as_posix()
    relevant = []
    for entry in entries:
        path = entry["path"]
        if (
            path.startswith("work/")
            or path in RELEVANT_ROOT_PATHS
            or shed == workspace
            or path == shed_relative
            or path.startswith(shed_relative + "/")
        ):
            relevant.append(entry)
    campaign_dirty = [item for item in entries if item["path"].startswith(CAMPAIGN_DIR)]
    return {
        "root": str(git_root),
        "branch": os.fsdecode(branch_result.stdout).strip() if branch_result.returncode == 0 else None,
        "head": os.fsdecode(head_result.stdout).strip() if head_result.returncode == 0 else None,
        "detached": branch_result.returncode != 0 and head_result.returncode == 0,
        "dirty_count": len(entries),
        "relevant_dirty_count": len(relevant),
        "relevant_dirty_sample": [item["path"] for item in relevant[:5]],
        "campaign_dirty_count": len(campaign_dirty),
        "campaign_dirty_sample": [item["path"] for item in campaign_dirty[:5]],
        "status_digest": hashlib.sha256(status_result.stdout).hexdigest()[:16],
    }


def version_state(shed: Path, *, installed_snapshot: bool) -> dict[str, Any]:
    try:
        manifest = check_shed_version.read_json_path(shed / "SHED_VERSION.json")
        check_shed_version.validate_manifest(manifest, canonical=False)
        missing, modified = check_shed_version.verify_local(shed, manifest)
        forbidden = check_shed_version.forbidden_snapshot_paths(
            shed, enforce_snapshot=installed_snapshot
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return {
            "local_version": None,
            "local_integrity": "unknown",
            "version_relation": "not-checked",
            "external_truth_observed": False,
            "missing_count": 0,
            "modified_count": 0,
            "forbidden_count": 0,
            "sample_paths": [],
            "error": str(error),
        }
    changed = [*missing, *modified, *forbidden]
    return {
        "local_version": manifest.get("shed_version"),
        "local_integrity": "modified" if changed else "verified",
        "version_relation": "not-checked",
        "external_truth_observed": False,
        "missing_count": len(missing),
        "modified_count": len(modified),
        "forbidden_count": len(forbidden),
        "sample_paths": list(_compact_paths(changed)),
        "error": None,
    }


def index_state(workspace: Path) -> dict[str, Any]:
    work = workspace / "work"
    artifacts = update_work_index.discover_artifacts(work) if work.is_dir() else []
    expected_markdown = update_work_index.render(artifacts)
    expected_json = update_work_index.render_json(artifacts)
    markdown = work / "index.md"
    json_path = work / "index.json"
    markdown_fresh = markdown.is_file() and markdown.read_text(encoding="utf-8") == expected_markdown
    json_fresh = json_path.is_file() and json_path.read_text(encoding="utf-8") == expected_json
    stale = []
    if not markdown_fresh:
        stale.append("work/index.md")
    if not json_fresh:
        stale.append("work/index.json")
    return {
        "fresh": not stale,
        "artifact_count": len(artifacts),
        "stale_paths": stale,
        "expected_markdown": expected_markdown,
        "expected_json": expected_json,
    }


def external_evidence_state(workspace: Path) -> dict[str, Any]:
    unsupported: list[dict[str, Any]] = []
    campaigns = campaign_queue.load_all(workspace)
    for item in sorted(campaigns.values(), key=lambda entry: entry.path.as_posix()):
        if item.status != "complete":
            continue
        evidence = item.fields.get("Completion Evidence", "")
        if not evidence or not RUNTIME_CLAIM_RE.search(evidence):
            continue
        references = EVIDENCE_PATH_RE.findall(evidence)
        durable = [path for path in references if (workspace / path).is_file()]
        if not durable:
            unsupported.append(
                {
                    "campaign_id": item.campaign_id,
                    "path": item.path.relative_to(workspace).as_posix(),
                    "claim_scope": "external-runtime",
                }
            )
    return {
        "external_truth_observed": False,
        "unsupported_claim_count": len(unsupported),
        "unsupported_claims": unsupported[:5],
        "meaning": (
            "The doctor verifies durable workspace structure only; it does not independently "
            "observe current external or runtime truth."
        ),
    }


def doctor_state_token(workspace: Path, git: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    for path in sorted((workspace / "work").rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(workspace).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    for value in (git.get("head"), git.get("status_digest")):
        digest.update(str(value).encode("utf-8"))
        digest.update(b"\0")
    return bind_state_token(workspace, "doctor", digest.hexdigest())


def _finding(
    code: str,
    classification: str,
    summary: str,
    next_action: str,
    *,
    paths: list[str] | None = None,
    count: int | None = None,
) -> Finding:
    if classification not in FINDING_CLASSES:
        raise AssertionError(classification)
    samples = _compact_paths(paths or [])
    return Finding(code, classification, summary, next_action, count or max(1, len(paths or [])), samples)


def inspect(workspace: Path) -> dict[str, Any]:
    root = resolved_workspace(workspace)
    shed = locate_shed(root)
    project = target_capsule(root, operation=OPERATION)
    git = git_state(root, shed)
    version = version_state(shed, installed_snapshot=shed != root)
    repository, preflight_findings, metrics, profile = workspace_preflight.inspect(root)
    topology = check_work_tree.inspect_work_tree(root)
    campaign_status = campaign_queue.status_payload(root)
    reconciliation = reconcile_campaign_queue.inspect_queue(root, stalled_days=30)
    indexes = index_state(root)
    stale_paths = check_stale_paths.scan(root)
    work_findings = review_work_state.review(root, stale_days=30, today=date.today())
    external_evidence = external_evidence_state(root)
    findings: list[Finding] = []

    if repository is None or repository.resolve() != root:
        findings.append(_finding(
            "WORKSPACE_BOUNDARY_INVALID", "error",
            "The workspace and Git repository boundaries do not match.",
            "Run `ts: identity`; do not mutate or switch workspaces implicitly.",
        ))
    if version["error"] or version["local_integrity"] != "verified":
        findings.append(_finding(
            "SNAPSHOT_INTEGRITY_INVALID", "error",
            "The local Tool Shed manifest is unreadable or does not match installed content.",
            "Run `ts: version`; for an installed snapshot use the guarded update route.",
            paths=list(version["sample_paths"]),
            count=(version["missing_count"] + version["modified_count"] + version["forbidden_count"]) or 1,
        ))
    for item in preflight_findings:
        classification = "error" if item.severity == "action_required" else "warning"
        findings.append(_finding(
            f"PREFLIGHT_{item.code}", classification, item.message,
            f"Run `python3 {shed.relative_to(root).as_posix() + '/' if shed != root else ''}scripts/workspace_preflight.py --workspace .` and apply mitigation `{item.mitigation}`.",
        ))
    if not topology["converged"]:
        findings.append(_finding(
            "WORK_TOPOLOGY_INVALID", "error",
            f"Canonical work topology has {len(topology['findings'])} finding(s).",
            "Run the guarded Tool Shed installer or updater; do not create lifecycle truth manually.",
            paths=[*topology["missing_directories"], *topology["missing_files"], *topology["legacy_paths"]],
            count=len(topology["findings"]),
        ))
    campaign_findings = list(campaign_status["findings"])
    if campaign_findings:
        findings.append(_finding(
            "CAMPAIGN_STATE_INVALID", "error",
            f"Campaign lifecycle validation has {len(campaign_findings)} finding(s).",
            "Run `ts: status` and correct the named lifecycle invariant before continuing.",
            count=len(campaign_findings),
        ))
    if not indexes["fresh"]:
        findings.append(_finding(
            "WORK_INDEX_STALE", "error",
            "Generated work indexes do not match current artifact headers.",
            "Run `ts: doctor --repair --expect <state-token> --project-binding <doctor-repair-binding>` to regenerate indexes only.",
            paths=list(indexes["stale_paths"]), count=len(indexes["stale_paths"]),
        ))
    if git["campaign_dirty_count"]:
        findings.append(_finding(
            "DIRTY_CAMPAIGN_STATE", "error",
            "Campaign lifecycle or queue state differs from the committed checkpoint.",
            "Review the active campaign transition and checkpoint it only after its completion gate passes.",
            paths=list(git["campaign_dirty_sample"]), count=git["campaign_dirty_count"],
        ))
    elif git["relevant_dirty_count"]:
        findings.append(_finding(
            "DIRTY_TOOL_SHED_STATE", "warning",
            "Tool Shed-managed source or work state differs from the committed checkpoint.",
            "Review and checkpoint the intended Tool Shed changes before treating the workspace as frozen.",
            paths=list(git["relevant_dirty_sample"]), count=git["relevant_dirty_count"],
        ))
    if stale_paths:
        findings.append(_finding(
            "STALE_WORK_PATHS", "error",
            f"Markdown contains {len(stale_paths)} stale work-artifact path reference(s).",
            "Run `python3 scripts/check_stale_paths.py --workspace .` and update the named references.",
            paths=[item.source for item in stale_paths], count=len(stale_paths),
        ))
    if work_findings:
        errors = [item for item in work_findings if item.severity == "error"]
        findings.append(_finding(
            "WORK_STATE_DRIFT", "error" if errors else "warning",
            f"Work-state review has {len(work_findings)} finding(s).",
            "Run `python3 scripts/review_work_state.py --workspace . --strict` and resolve the reported drift.",
            paths=[item.path for item in work_findings], count=len(work_findings),
        ))
    reconciliation_count = (
        len(reconciliation["validation_findings"])
        + len(reconciliation["whole_work"]["findings"])
        + int(bool(reconciliation["order_change_proposed"]))
    )
    if reconciliation["owner_action_required"]:
        findings.append(_finding(
            "CAMPAIGN_RECONCILIATION_DECISION", "owner-decision-required",
            f"Whole-work reconciliation requires owner action ({reconciliation_count} compact finding(s)).",
            "Run `ts: reconcile campaigns`; apply semantic changes only from an exact current manifest, fresh state token, and resolved authority envelope.",
            count=max(1, reconciliation_count),
        ))
    elif reconciliation["changes_required"]:
        findings.append(_finding(
            "CAMPAIGN_PROJECTION_STALE", "error",
            "Campaign queue projections differ from canonical campaign artifacts.",
            "Run `ts: reconcile campaigns`; evaluate and apply the exact repair manifest under the active authority envelope.",
        ))
    unsupported = external_evidence["unsupported_claims"]
    if external_evidence["unsupported_claim_count"]:
        findings.append(_finding(
            "EXTERNAL_EVIDENCE_MISSING", "external-evidence-required",
            "Completed campaign claims depend on runtime or external observations without a referenced durable workspace evidence record.",
            "Capture a sanitized `work/evidence/` record and reference its path from Completion Evidence; re-observe external truth when currency matters.",
            paths=[item["path"] for item in unsupported],
            count=external_evidence["unsupported_claim_count"],
        ))

    classes = {item.classification for item in findings}
    if "error" in classes:
        verdict = "INVALID"
    elif "owner-decision-required" in classes:
        verdict = "NEEDS_DECISION"
    elif findings:
        verdict = "DEGRADED"
    else:
        verdict = "HEALTHY"
    checks = {
        "workspace_boundary": {"healthy": repository is not None and repository.resolve() == root},
        "snapshot_integrity": version,
        "workspace_preflight": {
            "healthy": not preflight_findings,
            "finding_count": len(preflight_findings),
            "metrics": metrics,
            "policy_configured": bool(profile.get("policy")) if profile else False,
        },
        "git": git,
        "work_topology": {"converged": topology["converged"], "finding_count": len(topology["findings"])},
        "campaigns": {
            "valid": not campaign_findings,
            "finding_count": len(campaign_findings),
            "working": campaign_status["working"],
            "blocked": campaign_status["blocked"],
            "decisions_needed": campaign_status["decisions_needed"],
        },
        "indexes": {key: value for key, value in indexes.items() if not key.startswith("expected_")},
        "stale_paths": {"finding_count": len(stale_paths)},
        "work_state": {
            "finding_count": len(work_findings),
            "error_count": sum(item.severity == "error" for item in work_findings),
            "warning_count": sum(item.severity == "warning" for item in work_findings),
        },
        "reconciliation": {
            "changes_required": reconciliation["changes_required"],
            "owner_action_required": reconciliation["owner_action_required"],
            "validation_finding_count": len(reconciliation["validation_findings"]),
            "whole_work_finding_count": len(reconciliation["whole_work"]["findings"]),
            "coverage": reconciliation["coverage"],
        },
        "external_evidence": external_evidence,
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "command": "tool-shed-doctor",
        "read_only": True,
        "verdict": verdict,
        "fully_healthy": verdict == "HEALTHY",
        "internal_consistency_verified": verdict not in {"INVALID", "NEEDS_DECISION"},
        "external_truth_observed": False,
        "project": project,
        "state_token": doctor_state_token(root, git),
        "summary": {
            "finding_count": len(findings),
            **{classification.replace("-", "_"): sum(item.classification == classification for item in findings) for classification in FINDING_CLASSES},
        },
        "findings": [asdict(item) for item in findings],
        "checks": checks,
        "repair": {
            "supported": ["deterministic-work-index-regeneration"],
            "not_supported": [
                "campaign-lifecycle-changes",
                "semantic-truth-selection",
                "reconciliation-apply",
                "owner-authored-artifact-rewrites",
                "external-evidence-fabrication",
            ],
            "writes_performed": False,
        },
    }
    return report


def _atomic_write(path: Path, content: str) -> None:
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def repair_indexes(
    workspace: Path,
    report: dict[str, Any],
    *,
    expected: str | None,
    project_binding: str | None,
) -> dict[str, Any]:
    require_project_binding(workspace, project_binding, operation=OPERATION)
    if not expected or expected != report["state_token"]:
        raise DoctorError("--repair requires the exact current --expect state token")
    if not report["checks"]["campaigns"]["valid"]:
        raise DoctorError("cannot repair indexes until campaign source artifacts validate")
    indexes = index_state(workspace)
    repaired: list[str] = []
    if "work/index.md" in indexes["stale_paths"]:
        _atomic_write(workspace / "work" / "index.md", indexes["expected_markdown"])
        repaired.append("work/index.md")
    if "work/index.json" in indexes["stale_paths"]:
        _atomic_write(workspace / "work" / "index.json", indexes["expected_json"])
        repaired.append("work/index.json")
    refreshed = inspect(workspace)
    refreshed["read_only"] = False
    refreshed["repair"] = {
        **refreshed["repair"],
        "writes_performed": bool(repaired),
        "repaired_paths": repaired,
        "source_state_token": report["state_token"],
    }
    return refreshed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".", help="Exact project workspace root.")
    parser.add_argument("--json", action="store_true", help="Emit stable structured output.")
    parser.add_argument("--strict", action="store_true", help="Exit 1 unless the verdict is HEALTHY.")
    parser.add_argument("--repair", action="store_true", help="Regenerate stale deterministic work indexes only.")
    parser.add_argument("--expect", help="Exact state token from the latest doctor report.")
    parser.add_argument("--project-binding", help="doctor-repair binding from project identity.")
    return parser


def render_human(report: dict[str, Any]) -> str:
    lines = [
        f"Tool Shed doctor: {report['verdict']}",
        f"Project: {report['project']['project_name']} ({report['project']['project_id']})",
        f"Root: {report['project']['resolved_root']}",
        f"Branch/HEAD: {report['checks']['git']['branch'] or '(detached)'} / {report['checks']['git']['head'] or '(unborn)'}",
        f"Internal consistency verified: {'yes' if report['internal_consistency_verified'] else 'no'}",
        "External/runtime truth observed: no",
        f"State token: {report['state_token']}",
    ]
    if report["findings"]:
        lines.append("Findings:")
        for item in report["findings"]:
            suffix = f" [{', '.join(item['sample_paths'])}]" if item["sample_paths"] else ""
            lines.append(
                f"- {item['classification'].upper()} {item['code']}: {item['summary']} "
                f"Next: {item['next_action']}{suffix}"
            )
    else:
        lines.append("No findings. All supported internal checks are healthy.")
    if report["repair"].get("writes_performed"):
        lines.append("Repaired: " + ", ".join(report["repair"].get("repaired_paths", [])))
    return "\n".join(lines)


def main() -> int:
    args = build_parser().parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    try:
        if not args.repair and (args.expect or args.project_binding):
            raise DoctorError("--expect and --project-binding are valid only with --repair")
        report = inspect(workspace)
        if args.repair:
            report = repair_indexes(
                workspace,
                report,
                expected=args.expect,
                project_binding=args.project_binding,
            )
    except (
        DoctorError,
        ProjectIdentityError,
        campaign_queue.CampaignError,
        OSError,
        json.JSONDecodeError,
    ) as error:
        print(f"Tool Shed doctor failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render_human(report))
    return 1 if args.strict and report["verdict"] != "HEALTHY" else 0


if __name__ == "__main__":
    raise SystemExit(main())
