#!/usr/bin/env python3
"""Inspect and safely reconcile Tool Shed campaign queue projections."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import campaign_queue


REPAIRABLE_FINDINGS = (
    "active queue contains duplicate campaign IDs",
    "active campaigns missing from queue:",
    "queue entries missing active request files:",
    "active-queue.md is stale or manually inconsistent",
    "completed-queue.md is stale or manually inconsistent",
)


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
    return {
        "schema_version": 1,
        "workspace": str(workspace),
        "state_token": campaign_queue.state_token(workspace),
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
        "changes_required": changes_required,
        "owner_action_required": bool(
            order_change_proposed or stalled or blocked or invalid_updated or unsupported_findings
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


def apply_repairs(
    workspace: Path,
    expected: str | None,
    report: dict[str, Any],
) -> dict[str, Any]:
    campaign_queue.require_token(workspace, expected)
    if report["unsupported_findings"]:
        raise campaign_queue.CampaignError(
            "reconciliation refuses unsupported findings: "
            + "; ".join(report["unsupported_findings"])
        )
    campaigns = campaign_queue.load_all(workspace)
    root = campaign_queue.campaign_root(workspace)
    changes = {
        root / "active-queue.md": campaign_queue.render_active_queue(
            list(report["repair_order"]), campaigns
        ),
        root / "completed-queue.md": campaign_queue.render_completed_queue(campaigns),
    }
    campaign_queue.apply_transaction(workspace, changes)
    checks = run_post_apply_checks(workspace)
    refreshed = inspect_queue(workspace, int(report["stalled_days"]))
    refreshed["writes_performed"] = True
    refreshed["post_apply_checks"] = checks
    return refreshed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and reconcile Tool Shed campaign queue projections."
    )
    parser.add_argument("--workspace", default=".", help="Project workspace root.")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON.")
    parser.add_argument(
        "--stalled-days",
        type=int,
        default=30,
        help="Age threshold for an active campaign with a pending next action (default: 30).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Repair deterministic projection drift; never apply proposed reprioritization.",
    )
    parser.add_argument(
        "--expect",
        help="Current state token from dry-run output; required with --apply.",
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
        if args.apply:
            if not args.expect:
                raise campaign_queue.CampaignError(
                    "--apply requires --expect TOKEN from the latest dry run"
                )
            report = apply_repairs(workspace, args.expect, report)
    except (campaign_queue.CampaignError, OSError, json.JSONDecodeError) as error:
        print(f"Campaign reconciliation failed: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Campaign state token: {report['state_token']}")
        print(f"Repairable changes required: {report['changes_required']}")
        print(f"Owner action required: {report['owner_action_required']}")
        print("Proposed execution order: " + ", ".join(report["proposed_execution_order"]))
        if report["stalled"]:
            print(
                "Stalled campaigns: "
                + ", ".join(item["campaign_id"] for item in report["stalled"])
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
