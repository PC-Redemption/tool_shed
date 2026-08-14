#!/usr/bin/env python3
"""Inspect and safely reconcile Tool Shed campaign queue projections."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import campaign_queue
from update_work_index import Artifact, discover_artifacts


REPAIRABLE_FINDINGS = (
    "active queue contains duplicate campaign IDs",
    "active campaigns missing from queue:",
    "queue entries missing active request files:",
    "active-queue.md is stale or manually inconsistent",
    "completed-queue.md is stale or manually inconsistent",
)

ACTIVE_ARTIFACT_STATUSES = {"active", "blocked", "proposed", "queued", "working"}
TERMINAL_ARTIFACT_STATUSES = {"accepted", "abandoned", "complete", "completed", "decided", "done", "superseded"}
SUPPORTED_ARTIFACT_TYPES = {
    "adr", "campaign", "checklist", "decision-matrix", "evidence", "incident",
    "inventory", "project-map", "runbook", "spike", "ticket", "workpackage",
}
PLACEHOLDER_VALUES = {"", "-", "...", "none", "work/...", "work/maps/..."}
RELATIONSHIP_FIELDS = ("Parent", "Project Map", "Depends On", "Produces", "Supersedes", "Superseded By")
WORK_PATH_RE = re.compile(r"(?<![\w/])(work/[A-Za-z0-9_./-]+\.md)")
UNCHECKED_TASK_RE = re.compile(r"^\s*[-*]\s+\[ \]\s+", re.MULTILINE)
MANIFEST_KIND = "tool-shed-campaign-reconciliation"
DANGLER_CAMPAIGN_BASE_ID = "resolve-unclassified-work"
DANGLER_CAMPAIGN_TITLE = "Resolve Unclassified Work"


def without_updated(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.startswith("Updated: ")
    )


def unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def normalized(value: str | None) -> str:
    return (value or "").strip().lower()


def is_campaign_request(path: str) -> bool:
    parts = Path(path).parts
    return (
        len(parts) >= 4
        and parts[:2] == ("work", campaign_queue.ROOT_NAME)
        and parts[2] in campaign_queue.LIFECYCLE_DIRS
    )


def whole_work_state_token(workspace: Path) -> str:
    """Hash every Markdown file that the whole-work discovery can inspect."""
    digest = hashlib.sha256()
    work = workspace / "work"
    if not work.exists():
        return digest.hexdigest()[:16]
    for path in sorted(work.rglob("*.md")):
        relative = path.relative_to(workspace).as_posix()
        if relative.startswith("work/evidence/generated/"):
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def artifact_relationships(artifact: Artifact) -> list[str]:
    targets: list[str] = []
    for field in RELATIONSHIP_FIELDS:
        targets.extend(WORK_PATH_RE.findall(artifact.fields.get(field, "")))
    return unique(targets)


def artifact_signals(artifact: Artifact, text: str) -> list[str]:
    status = normalized(artifact.status())
    signals: list[str] = []
    if status in ACTIVE_ARTIFACT_STATUSES:
        signals.append(f"status:{status}")
    if status == "deferred":
        signals.append("status:deferred")
    next_action = normalized(artifact.fields.get("Next Action"))
    if next_action not in PLACEHOLDER_VALUES and status not in TERMINAL_ARTIFACT_STATUSES:
        signals.append("concrete-next-action")
    if UNCHECKED_TASK_RE.search(text):
        signals.append("unchecked-tasks")
    return signals


def finding(
    code: str,
    classification: str,
    paths: list[str],
    message: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "code": code,
        "classification": classification,
        "paths": paths,
        "message": message,
        **extra,
    }


def discover_whole_work(
    workspace: Path,
    campaigns: dict[str, campaign_queue.Campaign],
) -> dict[str, Any]:
    work = workspace / "work"
    artifacts = discover_artifacts(work) if work.exists() else []
    records: dict[str, dict[str, Any]] = {}
    exclusions: list[dict[str, str]] = []
    findings: list[dict[str, Any]] = []
    discovered_paths = {artifact.path.as_posix() for artifact in artifacts}
    all_markdown = sorted(work.rglob("*.md")) if work.exists() else []
    for path in all_markdown:
        relative = path.relative_to(workspace).as_posix()
        if relative in discovered_paths:
            continue
        if relative.startswith("work/evidence/generated/"):
            reason = "generated-evidence"
        elif path.name in {"index.md", "active-queue.md", "completed-queue.md"}:
            reason = "generated-projection"
        elif path.name == "README.md":
            reason = "work-guidance"
        else:
            reason = "unsupported-markdown"
        exclusions.append({"path": relative, "reason": reason})

    for artifact in artifacts:
        path = artifact.path.as_posix()
        if is_campaign_request(path):
            exclusions.append({"path": path, "reason": "campaign-lifecycle-source"})
            continue
        if path.startswith("work/evidence/generated/"):
            exclusions.append({"path": path, "reason": "generated-evidence"})
            continue
        text = (workspace / artifact.path).read_text(encoding="utf-8")
        signals = artifact_signals(artifact, text)
        status = normalized(artifact.status())
        kind = normalized(artifact.kind())
        raw_campaign = artifact.fields.get("Campaign", "").strip()
        association = normalized(raw_campaign)
        reason = artifact.fields.get("Campaign Reason", "").strip()
        campaign_ids = [] if association in {"", "standalone", "excluded"} else [
            item.strip() for item in raw_campaign.split(",") if item.strip()
        ]
        unresolved = bool(signals)
        relationships = artifact_relationships(artifact)
        records[path] = {
            "path": path,
            "type": kind or None,
            "status": status or None,
            "unresolved": unresolved,
            "signals": signals,
            "relationships": relationships,
            "campaign": raw_campaign or None,
            "campaign_reason": reason or None,
        }
        if unresolved and (not status or not kind or kind not in SUPPORTED_ARTIFACT_TYPES):
            findings.append(
                finding(
                    "unstructured_candidate",
                    "owner-decision-required",
                    [path],
                    "unresolved signals exist without a complete supported artifact header",
                )
            )
        if association in {"standalone", "excluded"} and not reason:
            findings.append(
                finding(
                    "scope_conflict",
                    "owner-decision-required",
                    [path],
                    f"Campaign: {association} requires Campaign Reason",
                )
            )
        if len(campaign_ids) > 1:
            findings.append(
                finding(
                    "scope_conflict",
                    "owner-decision-required",
                    [path],
                    "an artifact must declare one campaign, standalone, or excluded",
                    campaigns=campaign_ids,
                )
            )
        for campaign_id in campaign_ids:
            campaign = campaigns.get(campaign_id)
            if campaign is None:
                findings.append(
                    finding(
                        "unlinked_artifact",
                        "high-confidence",
                        [path],
                        f"declared campaign does not exist: {campaign_id}",
                        campaign=campaign_id,
                    )
                )
                continue
            campaign_status = campaign.status
            if unresolved and campaign_status in {"complete", "abandoned"}:
                findings.append(
                    finding(
                        "lifecycle_mismatch",
                        "high-confidence",
                        [path],
                        f"unresolved artifact is linked to {campaign_status} campaign {campaign_id}",
                        campaign=campaign_id,
                    )
                )
            if unresolved and campaign_status == "complete":
                findings.append(
                    finding(
                        "stale_completion",
                        "high-confidence",
                        [path],
                        f"completed campaign {campaign_id} still covers unresolved work",
                        campaign=campaign_id,
                    )
                )
            if not unresolved and status in TERMINAL_ARTIFACT_STATUSES and campaign_status in campaign_queue.ACTIVE_STATES:
                findings.append(
                    finding(
                        "stale_completion",
                        "high-confidence",
                        [path],
                        f"terminal artifact is linked to active campaign {campaign_id}",
                        campaign=campaign_id,
                    )
                )

    for path, record in records.items():
        if record["status"] not in ACTIVE_ARTIFACT_STATUSES:
            continue
        for target in record["relationships"]:
            related = records.get(target)
            if related and related["status"] in TERMINAL_ARTIFACT_STATUSES:
                findings.append(
                    finding(
                        "lifecycle_mismatch",
                        "high-confidence",
                        [path, target],
                        "active artifact depends on or descends from a terminal artifact",
                    )
                )

    adjacency = {path: set() for path in records}
    for path, record in records.items():
        for target in record["relationships"]:
            if target in records:
                adjacency[path].add(target)
                adjacency[target].add(path)

    clusters: list[dict[str, Any]] = []
    visited: set[str] = set()
    unresolved_paths = {path for path, record in records.items() if record["unresolved"]}
    for seed in sorted(unresolved_paths):
        if seed in visited:
            continue
        pending = [seed]
        component: set[str] = set()
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            pending.extend(adjacency[current] - component)
        unresolved_component = sorted(component & unresolved_paths)
        visited.update(unresolved_component)
        associations = sorted(
            {
                item.strip()
                for path in unresolved_component
                for item in (records[path]["campaign"] or "").split(",")
                if item.strip() and normalized(item) not in {"standalone", "excluded"}
            }
        )
        modes = sorted(
            {
                normalized(records[path]["campaign"])
                for path in unresolved_component
                if normalized(records[path]["campaign"]) in {"standalone", "excluded"}
            }
        )
        cluster = {
            "cluster_id": f"cluster-{len(clusters) + 1}",
            "paths": unresolved_component,
            "campaigns": associations,
            "modes": modes,
        }
        clusters.append(cluster)
        if len(associations) > 1:
            findings.append(
                finding(
                    "duplicate_coverage",
                    "owner-decision-required",
                    unresolved_component,
                    "related unresolved artifacts declare multiple campaigns",
                    campaigns=associations,
                )
            )
        if associations and modes:
            findings.append(
                finding(
                    "scope_conflict",
                    "owner-decision-required",
                    unresolved_component,
                    "related unresolved artifacts mix campaign coverage with standalone or excluded scope",
                    campaigns=associations,
                    modes=modes,
                )
            )
        if not associations and not modes:
            findings.append(
                finding(
                    "missing_campaign",
                    "owner-decision-required",
                    unresolved_component,
                    "unresolved artifact cluster has no Campaign declaration",
                )
            )

    findings.sort(key=lambda item: (item["code"], item["paths"], item["message"]))
    by_code = {
        code: [item for item in findings if item["code"] == code]
        for code in (
            "missing_campaign", "unlinked_artifact", "duplicate_coverage",
            "lifecycle_mismatch", "scope_conflict", "stale_completion",
            "unstructured_candidate",
        )
    }
    unresolved_records = [record for record in records.values() if record["unresolved"]]
    covered = [
        record for record in unresolved_records
        if record["campaign"] and normalized(record["campaign"]) not in {"standalone", "excluded"}
    ]
    standalone = [record for record in unresolved_records if normalized(record["campaign"]) == "standalone"]
    excluded = [record for record in unresolved_records if normalized(record["campaign"]) == "excluded"]
    unclassified = [record for record in unresolved_records if not record["campaign"]]
    return {
        "coverage": {
            "markdown_discovered": len(all_markdown),
            "artifacts_scanned": len(records),
            "artifacts_excluded": len(exclusions),
            "unresolved_artifacts": len(unresolved_records),
            "campaign_associated": len(covered),
            "standalone": len(standalone),
            "explicitly_excluded": len(excluded),
            "unclassified": len(unclassified),
        },
        "exclusions": exclusions,
        "artifacts": sorted(records.values(), key=lambda item: item["path"]),
        "clusters": clusters,
        "findings": findings,
        **by_code,
    }


def _is_dangler_campaign_id(campaign_id: str) -> bool:
    return campaign_id == DANGLER_CAMPAIGN_BASE_ID or bool(
        re.fullmatch(rf"{re.escape(DANGLER_CAMPAIGN_BASE_ID)}-[2-9][0-9]*", campaign_id)
    )


def _next_dangler_campaign_id(campaigns: dict[str, campaign_queue.Campaign]) -> str:
    if DANGLER_CAMPAIGN_BASE_ID not in campaigns:
        return DANGLER_CAMPAIGN_BASE_ID
    suffix = 2
    while f"{DANGLER_CAMPAIGN_BASE_ID}-{suffix}" in campaigns:
        suffix += 1
    return f"{DANGLER_CAMPAIGN_BASE_ID}-{suffix}"


def _dangler_campaign_content(paths: list[str]) -> tuple[str, str, str]:
    outcome = (
        "Every unresolved work artifact is associated with a campaign, explicitly standalone "
        "or excluded with a reason, or repaired so it no longer signals unresolved work."
    )
    gate = (
        "Campaign reconciliation reports zero unclassified unresolved artifacts and no "
        "missing_campaign findings."
    )
    request = (
        "Triage each unresolved artifact. Associate it with the correct execution campaign, "
        "mark it standalone or excluded with a reason, or repair stale completion state.\n\n"
        "Unresolved artifacts:\n\n"
        + "\n".join(f"- `{path}`" for path in paths)
    )
    return outcome, gate, request


def _campaign_section(body: str, heading: str) -> str:
    match = re.search(
        rf"(?ms)^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", body
    )
    return match.group(1).strip() if match else ""


def _first_queued_position(
    active_order: list[str],
    campaigns: dict[str, campaign_queue.Campaign],
    campaign_id: str | None = None,
) -> int:
    remaining = [item_id for item_id in active_order if item_id != campaign_id]
    working_positions = [
        index
        for index, item_id in enumerate(remaining)
        if item_id in campaigns and campaigns[item_id].status == "working"
    ]
    return working_positions[0] + 2 if working_positions else 1


def dangler_resolution_proposal(
    workspace: Path,
    campaigns: dict[str, campaign_queue.Campaign],
    active_order: list[str],
    whole_work: dict[str, Any],
) -> dict[str, Any] | None:
    paths = sorted(
        record["path"]
        for record in whole_work["artifacts"]
        if record["unresolved"] and not record["campaign"]
    )
    if not paths:
        return None

    outcome, gate, request = _dangler_campaign_content(paths)

    active = sorted(
        (
            item
            for item in campaigns.values()
            if item.path.parent.name == "active"
            and _is_dangler_campaign_id(item.campaign_id)
        ),
        key=lambda item: item.campaign_id,
    )
    if active:
        item = active[0]
        position = _first_queued_position(
            active_order, campaigns, campaign_id=item.campaign_id
        )
        current_position = (
            active_order.index(item.campaign_id) + 1
            if item.campaign_id in active_order
            else None
        )
        refresh_required = bool(
            item.title != DANGLER_CAMPAIGN_TITLE
            or item.outcome != outcome
            or item.fields.get("Completion Gate") != gate
            or _campaign_section(item.body, "Request") != request
            or current_position != position
        )
        result = {
            "campaign_id": item.campaign_id,
            "title": item.title,
            "status": item.status,
            "path": item.path.relative_to(workspace).as_posix(),
            "unresolved_count": len(paths),
            "unresolved_paths": paths,
            "requires_manifest_approval": False,
            "source": "campaign-reconciliation",
            "next_action": item.fields.get("Next Action", "triage unresolved artifacts"),
            "automatic_update_required": refresh_required,
        }
        if refresh_required:
            result["manifest_operation"] = {
                "op": "refresh_dangler_campaign",
                "campaign_id": item.campaign_id,
                "title": DANGLER_CAMPAIGN_TITLE,
                "outcome": outcome,
                "completion_gate": gate,
                "request": request,
                "position": position,
            }
        return result

    campaign_id = _next_dangler_campaign_id(campaigns)
    position = _first_queued_position(active_order, campaigns)
    operation = {
        "op": "create_campaign",
        "campaign_id": campaign_id,
        "title": DANGLER_CAMPAIGN_TITLE,
        "outcome": outcome,
        "completion_gate": gate,
        "request": request,
        "position": position,
    }
    return {
        "campaign_id": campaign_id,
        "title": DANGLER_CAMPAIGN_TITLE,
        "status": "proposed",
        "path": None,
        "unresolved_count": len(paths),
        "unresolved_paths": paths,
        "requires_manifest_approval": False,
        "source": "campaign-reconciliation",
        "reconciliation_state_token": whole_work_state_token(workspace),
        "next_action": "run ts: reconcile campaigns to add it to the active queue",
        "automatic_update_required": True,
        "manifest_operation": operation,
    }


def manifest_for_report(
    state_token: str,
    repair_order: list[str],
    changes_required: bool,
    dangler_resolution: dict[str, Any] | None,
) -> dict[str, Any]:
    operations: list[dict[str, Any]] = []
    if changes_required:
        operations.append({"op": "repair_projections", "active_order": repair_order})
    if dangler_resolution and dangler_resolution.get("manifest_operation"):
        operations.append(dangler_resolution["manifest_operation"])
    return {
        "schema_version": 1,
        "kind": MANIFEST_KIND,
        "state_token": state_token,
        "operations": operations,
    }


def order_reason(
    item: campaign_queue.Campaign,
    campaigns: dict[str, campaign_queue.Campaign],
) -> tuple[int, str]:
    if item.status == "working":
        return 0, "working campaign remains first"
    if item.status == "queued":
        incomplete = [
            dependency
            for dependency in item.dependencies
            if dependency not in campaigns or campaigns[dependency].status != "complete"
        ]
        if not incomplete:
            return 1, "queued and dependency-ready"
        return 2, "queued with incomplete dependencies: " + ", ".join(incomplete)
    if item.status == "blocked":
        return 3, "blocked or awaiting an owner decision"
    return 4, f"unexpected active status: {item.status or 'missing'}"


def inspect_queue(workspace: Path, stalled_days: int) -> dict[str, Any]:
    campaigns = campaign_queue.load_all(workspace)
    raw_order = campaign_queue.queue_order(workspace)
    active = {
        item.campaign_id: item
        for item in campaigns.values()
        if item.path.parent.name == "active"
    }
    active_ids = set(active)
    missing_from_queue = sorted(active_ids - set(raw_order))
    missing_active_files = unique([item for item in raw_order if item not in active_ids])
    duplicate_queue_ids = sorted(
        item for item in set(raw_order) if raw_order.count(item) > 1
    )
    repair_order = unique([item for item in raw_order if item in active_ids])
    repair_order.extend(item for item in missing_from_queue if item not in repair_order)

    root = campaign_queue.campaign_root(workspace)
    expected_active = campaign_queue.render_active_queue(repair_order, campaigns)
    expected_completed = campaign_queue.render_completed_queue(campaigns)
    active_projection_stale = without_updated(
        (root / "active-queue.md").read_text(encoding="utf-8")
    ) != without_updated(expected_active)
    completed_projection_stale = without_updated(
        (root / "completed-queue.md").read_text(encoding="utf-8")
    ) != without_updated(expected_completed)

    ready: list[str] = []
    dependency_constrained: list[dict[str, Any]] = []
    blocked: list[str] = []
    working: list[str] = []
    stalled: list[dict[str, Any]] = []
    invalid_updated: list[str] = []
    cutoff = date.today() - timedelta(days=stalled_days)
    for campaign_id in repair_order:
        item = active[campaign_id]
        if item.status == "working":
            working.append(campaign_id)
        elif item.status == "blocked":
            blocked.append(campaign_id)
        elif item.status == "queued":
            incomplete = [
                dependency
                for dependency in item.dependencies
                if dependency not in campaigns or campaigns[dependency].status != "complete"
            ]
            if incomplete:
                dependency_constrained.append(
                    {"campaign_id": campaign_id, "dependencies": incomplete}
                )
            else:
                ready.append(campaign_id)
        updated_text = item.fields.get("Updated", "")
        try:
            updated = date.fromisoformat(updated_text)
        except ValueError:
            invalid_updated.append(campaign_id)
            continue
        if updated <= cutoff and item.fields.get("Next Action", "none").lower() != "none":
            stalled.append(
                {
                    "campaign_id": campaign_id,
                    "status": item.status,
                    "updated": updated_text,
                    "age_days": (date.today() - updated).days,
                    "next_action": item.fields.get("Next Action", "none"),
                }
            )

    ranked = sorted(
        enumerate(repair_order),
        key=lambda entry: (*order_reason(active[entry[1]], campaigns)[:1], entry[0]),
    )
    proposed_order = [campaign_id for _, campaign_id in ranked]
    order_reasons = {
        campaign_id: order_reason(active[campaign_id], campaigns)[1]
        for campaign_id in proposed_order
    }
    validation_findings = campaign_queue.validate(workspace)
    unsupported_findings = [
        finding
        for finding in validation_findings
        if not any(finding.startswith(prefix) for prefix in REPAIRABLE_FINDINGS)
    ]
    changes_required = bool(
        raw_order != repair_order
        or active_projection_stale
        or completed_projection_stale
    )
    order_change_proposed = proposed_order != repair_order
    whole_work = discover_whole_work(workspace, campaigns)
    state_token = whole_work_state_token(workspace)
    dangler_resolution = dangler_resolution_proposal(
        workspace, campaigns, repair_order, whole_work
    )
    reconciliation_manifest = manifest_for_report(
        state_token, repair_order, changes_required, dangler_resolution
    )
    return {
        "schema_version": 2,
        "workspace": str(workspace),
        "state_token": state_token,
        "campaign_state_token": campaign_queue.state_token(workspace),
        "stalled_days": stalled_days,
        "active_order": raw_order,
        "repair_order": repair_order,
        "proposed_execution_order": proposed_order,
        "order_reasons": order_reasons,
        "order_change_proposed": order_change_proposed,
        "orphaned_active": missing_from_queue,
        "missing_active_files": missing_active_files,
        "duplicate_queue_ids": duplicate_queue_ids,
        "active_projection_stale": active_projection_stale,
        "completed_projection_stale": completed_projection_stale,
        "working": working,
        "ready": ready,
        "dependency_constrained": dependency_constrained,
        "blocked": blocked,
        "stalled": stalled,
        "invalid_updated": invalid_updated,
        "validation_findings": validation_findings,
        "unsupported_findings": unsupported_findings,
        "whole_work": whole_work,
        "coverage": whole_work["coverage"],
        "missing_campaign": whole_work["missing_campaign"],
        "unlinked_artifact": whole_work["unlinked_artifact"],
        "duplicate_coverage": whole_work["duplicate_coverage"],
        "lifecycle_mismatch": whole_work["lifecycle_mismatch"],
        "scope_conflict": whole_work["scope_conflict"],
        "stale_completion": whole_work["stale_completion"],
        "unstructured_candidate": whole_work["unstructured_candidate"],
        "dangler_resolution": dangler_resolution,
        "reconciliation_manifest": reconciliation_manifest,
        "changes_required": changes_required,
        "owner_action_required": bool(
            order_change_proposed
            or stalled
            or blocked
            or invalid_updated
            or unsupported_findings
            or whole_work["findings"]
        ),
        "writes_performed": False,
    }


def run_post_apply_checks(workspace: Path) -> dict[str, str]:
    scripts = Path(__file__).resolve().parent
    commands = (
        ("update_work_index.py", "--workspace", str(workspace), "--no-preflight"),
        ("check_stale_paths.py", "--workspace", str(workspace)),
        ("review_work_state.py", "--workspace", str(workspace)),
    )
    results: dict[str, str] = {}
    for script, *arguments in commands:
        path = scripts / script
        if not path.is_file():
            continue
        result = subprocess.run(
            [sys.executable, str(path), *arguments],
            cwd=str(workspace),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip()
            raise campaign_queue.CampaignError(
                f"post-reconciliation check failed: {script}: {detail}"
            )
        results[script] = result.stdout.strip()
    return results


def require_whole_work_token(workspace: Path, expected: str | None) -> None:
    if not expected:
        raise campaign_queue.CampaignError(
            "mutation requires --expect TOKEN from the latest dry run"
        )
    actual = whole_work_state_token(workspace)
    if expected != actual:
        raise campaign_queue.CampaignError(
            f"stale whole-work state: expected {expected}, current {actual}"
        )


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise campaign_queue.CampaignError("reconciliation manifest must be a JSON object")
    if payload.get("schema_version") != 1 or payload.get("kind") != MANIFEST_KIND:
        raise campaign_queue.CampaignError("unsupported reconciliation manifest")
    if not isinstance(payload.get("operations"), list):
        raise campaign_queue.CampaignError("manifest operations must be a list")
    return payload


def safe_artifact_path(workspace: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value.startswith("work/"):
        raise campaign_queue.CampaignError("manifest artifact path must start with work/")
    path = (workspace / value).resolve()
    work = (workspace / "work").resolve()
    try:
        path.relative_to(work)
    except ValueError as error:
        raise campaign_queue.CampaignError("manifest artifact path escapes work/") from error
    if not path.is_file() or path.is_symlink():
        raise campaign_queue.CampaignError(f"manifest artifact is not a regular file: {value}")
    if is_campaign_request(path.relative_to(workspace).as_posix()):
        raise campaign_queue.CampaignError("set_association cannot edit campaign requests")
    return path


def set_header(text: str, key: str, value: str) -> str:
    lines = text.splitlines()
    replacement = f"{key}: {value}"
    for index, line in enumerate(lines[:40]):
        if line.startswith(f"{key}:"):
            lines[index] = replacement
            return "\n".join(lines).rstrip() + "\n"
    insert_at = next(
        (index + 1 for index, line in enumerate(lines[:40]) if line.startswith("Next Action:")),
        next((index for index, line in enumerate(lines) if line.startswith("## ")), len(lines)),
    )
    lines.insert(insert_at, replacement)
    return "\n".join(lines).rstrip() + "\n"


def prepare_manifest_changes(
    workspace: Path,
    manifest: dict[str, Any],
    report: dict[str, Any],
) -> dict[Path, str | None]:
    campaigns = campaign_queue.load_all(workspace)
    order = campaign_queue.queue_order(workspace)
    root = campaign_queue.campaign_root(workspace)
    changes: dict[Path, str | None] = {}
    campaign_changed = False

    for operation in manifest["operations"]:
        if not isinstance(operation, dict):
            raise campaign_queue.CampaignError("manifest operation must be an object")
        kind = operation.get("op")
        if kind == "repair_projections":
            requested = operation.get("active_order")
            if requested != report["repair_order"]:
                raise campaign_queue.CampaignError(
                    "repair_projections must exactly match the current deterministic repair order"
                )
            order = list(requested)
            campaign_changed = True
        elif kind == "set_association":
            path = safe_artifact_path(workspace, operation.get("path"))
            association = operation.get("campaign")
            reason = operation.get("reason", "")
            if not isinstance(association, str) or not association.strip():
                raise campaign_queue.CampaignError("set_association requires campaign")
            association = association.strip()
            if association not in {"standalone", "excluded"} and association not in campaigns:
                raise campaign_queue.CampaignError(
                    f"set_association references unknown campaign: {association}"
                )
            if association in {"standalone", "excluded"} and not str(reason).strip():
                raise campaign_queue.CampaignError(
                    f"Campaign: {association} requires a reason"
                )
            text = path.read_text(encoding="utf-8")
            text = set_header(text, "Campaign", association)
            if str(reason).strip():
                text = set_header(text, "Campaign Reason", str(reason).strip())
            changes[path] = text
        elif kind == "create_campaign":
            campaign_id = operation.get("campaign_id")
            title = operation.get("title")
            outcome = operation.get("outcome")
            gate = operation.get("completion_gate")
            request = operation.get("request", "Add detailed execution context here.")
            dependencies = operation.get("depends_on", [])
            if not isinstance(campaign_id, str) or not campaign_queue.ID_RE.fullmatch(campaign_id):
                raise campaign_queue.CampaignError("create_campaign requires a lowercase kebab-case campaign_id")
            if campaign_id in campaigns:
                raise campaign_queue.CampaignError(f"campaign already exists: {campaign_id}")
            if not all(isinstance(value, str) and value.strip() for value in (title, outcome, gate, request)):
                raise campaign_queue.CampaignError("create_campaign requires title, outcome, completion_gate, and request")
            if not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
                raise campaign_queue.CampaignError("create_campaign depends_on must be a list of campaign IDs")
            missing = sorted(set(dependencies) - set(campaigns))
            if missing:
                raise campaign_queue.CampaignError("missing dependencies: " + ", ".join(missing))
            path = root / "active" / f"{campaign_id}.md"
            text = campaign_queue._campaign_text(
                campaign_id, title.strip(), outcome.strip(), gate.strip(), dependencies,
                str(operation.get("decision", "none")),
                str(operation.get("detour_for", "none")),
                str(operation.get("return_to", "none")),
            ).replace("Add detailed execution context here.", request.strip())
            item = campaign_queue.parse_campaign_text(path, text)
            campaigns[campaign_id] = item
            position = operation.get("position", len(order) + 1)
            if not isinstance(position, int) or position < 1 or position > len(order) + 1:
                raise campaign_queue.CampaignError("create_campaign position is outside the active queue")
            order.insert(position - 1, campaign_id)
            changes[path] = text
            campaign_changed = True
        elif kind == "refresh_dangler_campaign":
            expected = (report.get("dangler_resolution") or {}).get("manifest_operation")
            if operation != expected:
                raise campaign_queue.CampaignError(
                    "refresh_dangler_campaign must exactly match the deterministic current proposal"
                )
            campaign_id = operation.get("campaign_id")
            if campaign_id not in campaigns or not _is_dangler_campaign_id(str(campaign_id)):
                raise campaign_queue.CampaignError(
                    "refresh_dangler_campaign requires an active Dangler Resolution campaign"
                )
            item = campaigns[str(campaign_id)]
            if item.path.parent.name != "active":
                raise campaign_queue.CampaignError(
                    "refresh_dangler_campaign requires an active Dangler Resolution campaign"
                )
            position = operation.get("position")
            if not isinstance(position, int) or position < 1 or position > len(order):
                raise campaign_queue.CampaignError(
                    "refresh_dangler_campaign position is outside the active queue"
                )
            item.title = str(operation["title"])
            item.fields["Outcome"] = str(operation["outcome"])
            item.fields["Completion Gate"] = str(operation["completion_gate"])
            item.fields["Updated"] = date.today().isoformat()
            item.body = (
                "## Request\n\n"
                + str(operation["request"]).strip()
                + "\n\n## Completion Check\n\n"
                + str(operation["completion_gate"]).strip()
                + "\n"
            )
            order.remove(item.campaign_id)
            order.insert(position - 1, item.campaign_id)
            changes[item.path] = campaign_queue.render_campaign(item)
            campaign_changed = True
        elif kind == "transition_campaign":
            campaign_id = operation.get("campaign_id")
            action = operation.get("action")
            if campaign_id not in campaigns:
                raise campaign_queue.CampaignError(f"unknown campaign: {campaign_id}")
            item = campaigns[campaign_id]
            source = item.path
            if action == "complete":
                if source.parent.name != "active" or operation.get("gate_passed") is not True:
                    raise campaign_queue.CampaignError("completion requires an active campaign and gate_passed: true")
                evidence = operation.get("evidence")
                if not isinstance(evidence, str) or not evidence.strip():
                    raise campaign_queue.CampaignError("completion requires evidence")
                item.fields.update({
                    "Status": "complete", "Completion Evidence": evidence.strip(),
                    "Completion Date": date.today().isoformat(),
                    "Completion Order": str(max((campaign_queue._completion_order(other) for other in campaigns.values()), default=0) + 1),
                    "Disposition": "completed", "Next Action": "none",
                })
                order.remove(campaign_id)
                item.path = root / "completed" / source.name
            elif action == "defer":
                reason = operation.get("reason")
                reactivate = operation.get("reactivate_when")
                if source.parent.name != "active" or not isinstance(reason, str) or not isinstance(reactivate, str) or not reason.strip() or not reactivate.strip():
                    raise campaign_queue.CampaignError("deferral requires active campaign, reason, and reactivate_when")
                item.fields.update({
                    "Status": "deferred", "Disposition": reason.strip(),
                    "Reactivate When": reactivate.strip(),
                    "Next Action": "reactivate when " + reactivate.strip(),
                })
                order.remove(campaign_id)
                item.path = root / "deferred" / source.name
            elif action == "abandon":
                reason = operation.get("reason")
                if source.parent.name not in {"active", "deferred"} or not isinstance(reason, str) or not reason.strip():
                    raise campaign_queue.CampaignError("abandonment requires active/deferred campaign and reason")
                replacement = operation.get("replacement")
                disposition = reason.strip() + (f"; replacement: {replacement}" if replacement else "")
                item.fields.update({"Status": "abandoned", "Disposition": disposition, "Next Action": "none"})
                if campaign_id in order:
                    order.remove(campaign_id)
                item.path = root / "abandoned" / source.name
            else:
                raise campaign_queue.CampaignError(
                    "transition_campaign action must be complete, defer, or abandon"
                )
            item.fields["Updated"] = date.today().isoformat()
            changes[source] = None
            changes[item.path] = campaign_queue.render_campaign(item)
            campaign_changed = True
        else:
            raise campaign_queue.CampaignError(f"unsupported manifest operation: {kind}")

    if campaign_changed:
        changes.update(campaign_queue._refresh_changes(workspace, order, campaigns))
    return changes


def apply_repairs(
    workspace: Path,
    expected: str | None,
    report: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    require_whole_work_token(workspace, expected)
    if manifest.get("state_token") != expected:
        raise campaign_queue.CampaignError(
            "manifest state_token must exactly match --expect"
        )
    if report["unsupported_findings"]:
        raise campaign_queue.CampaignError(
            "reconciliation refuses unsupported findings: "
            + "; ".join(report["unsupported_findings"])
        )
    changes = prepare_manifest_changes(workspace, manifest, report)
    if changes:
        campaign_queue.apply_transaction(workspace, changes)
    checks = run_post_apply_checks(workspace)
    refreshed = inspect_queue(workspace, int(report["stalled_days"]))
    refreshed["writes_performed"] = True
    refreshed["post_apply_checks"] = checks
    return refreshed


def automatic_dangler_manifest(report: dict[str, Any]) -> dict[str, Any] | None:
    dangler = report.get("dangler_resolution") or {}
    operation = dangler.get("manifest_operation")
    if not isinstance(operation, dict):
        return None
    if operation.get("op") not in {"create_campaign", "refresh_dangler_campaign"}:
        return None
    if not _is_dangler_campaign_id(str(operation.get("campaign_id", ""))):
        return None
    return {
        "schema_version": 1,
        "kind": MANIFEST_KIND,
        "state_token": report["state_token"],
        "operations": [operation],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and reconcile Tool Shed campaign queue projections."
    )
    parser.add_argument("--workspace", default=".", help="Project workspace root.")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect without automatically creating or refreshing Dangler Resolution.",
    )
    parser.add_argument(
        "--stalled-days",
        type=int,
        default=30,
        help="Age threshold for an active campaign with a pending next action (default: 30).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply only operations from an exact approved reconciliation manifest.",
    )
    parser.add_argument(
        "--expect",
        help="Current state token from dry-run output; required with --apply.",
    )
    parser.add_argument(
        "--manifest",
        help="Exact approved JSON manifest; required with --apply.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    try:
        if args.stalled_days < 1:
            raise campaign_queue.CampaignError("--stalled-days must be a positive integer")
        root = campaign_queue.campaign_root(workspace)
        if not root.is_dir():
            raise campaign_queue.CampaignError("campaign tree is not initialized")
        campaign_queue.recover_if_needed(workspace)
        report = inspect_queue(workspace, args.stalled_days)
        if args.dry_run and (args.apply or args.expect or args.manifest):
            raise campaign_queue.CampaignError(
                "--dry-run cannot be combined with --apply, --expect, or --manifest"
            )
        if args.apply:
            if not args.expect:
                raise campaign_queue.CampaignError(
                    "--apply requires --expect TOKEN from the latest dry run"
                )
            if not args.manifest:
                raise campaign_queue.CampaignError(
                    "--apply requires --manifest PATH"
                )
            manifest = load_manifest(Path(args.manifest).expanduser().resolve())
            report = apply_repairs(workspace, args.expect, report, manifest)
        elif not args.dry_run:
            manifest = automatic_dangler_manifest(report)
            if manifest is not None:
                operation = manifest["operations"][0]
                report = apply_repairs(
                    workspace, report["state_token"], report, manifest
                )
                report["automatic_dangler_resolution"] = {
                    "campaign_id": operation["campaign_id"],
                    "operation": operation["op"],
                }
    except (campaign_queue.CampaignError, OSError, json.JSONDecodeError) as error:
        print(f"Campaign reconciliation failed: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        automatic = report.get("automatic_dangler_resolution")
        if automatic:
            print(
                "Dangler Resolution: "
                f"{automatic['operation']} {automatic['campaign_id']}"
            )
        print(f"Campaign state token: {report['state_token']}")
        print(f"Repairable changes required: {report['changes_required']}")
        print(f"Owner action required: {report['owner_action_required']}")
        coverage = report["coverage"]
        print(
            "Whole-work coverage: "
            f"{coverage['artifacts_scanned']} scanned, "
            f"{coverage['artifacts_excluded']} excluded, "
            f"{coverage['unresolved_artifacts']} unresolved, "
            f"{coverage['unclassified']} unclassified"
        )
        codes = [item["code"] for item in report["whole_work"]["findings"]]
        if codes:
            print("Whole-work findings: " + ", ".join(sorted(set(codes))))
        print("Proposed execution order: " + ", ".join(report["proposed_execution_order"]))
        if report["stalled"]:
            print(
                "Stalled campaigns: "
                + ", ".join(item["campaign_id"] for item in report["stalled"])
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
