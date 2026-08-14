from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


ROOT_NAME = "00-campaigns"
ACTIVE_STATES = {"queued", "working", "blocked"}
TERMINAL_STATES = {"complete", "deferred", "abandoned"}
LIFECYCLE_DIRS = ("active", "completed", "deferred", "abandoned")
HEADER_KEYS = (
    "Status",
    "Type",
    "Updated",
    "Next Action",
    "Campaign ID",
    "Outcome",
    "Depends On",
    "Decision",
    "Detour For",
    "Return To",
    "Completion Gate",
    "Completion Evidence",
    "Completion Date",
    "Disposition",
    "Reactivate When",
)
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
QUEUE_LINK_RE = re.compile(r"^\d+\. \[[^]]+\]\(active/([a-z0-9-]+)\.md\)")


class CampaignError(ValueError):
    pass


@dataclass
class Campaign:
    path: Path
    title: str
    fields: dict[str, str]
    body: str

    @property
    def campaign_id(self) -> str:
        return self.fields.get("Campaign ID", "")

    @property
    def status(self) -> str:
        return self.fields.get("Status", "")

    @property
    def outcome(self) -> str:
        return self.fields.get("Outcome", "")

    @property
    def dependencies(self) -> list[str]:
        value = self.fields.get("Depends On", "none")
        if value.lower() == "none" or not value.strip():
            return []
        return [item.strip() for item in value.split(",") if item.strip()]


def campaign_root(workspace: Path) -> Path:
    return workspace / "work" / ROOT_NAME


def _default_active_queue() -> str:
    return (
        "# Active Campaign Queue\n\n"
        f"Updated: {date.today().isoformat()}\n\n"
        "## Owner State\n\n"
        "- Last completed: none\n"
        "- Working now: none\n"
        "- Next: none\n"
        "- Blocker or decision needed: none\n"
        "- Detour and return point: none\n\n"
        "## Ordered Queue\n\n"
        "No active campaigns.\n"
    )


def _default_completed_queue() -> str:
    return (
        "# Completed Campaign Queue\n\n"
        f"Updated: {date.today().isoformat()}\n\n"
        "Newest completion first.\n\n"
        "No completed campaigns.\n"
    )


def ensure_tree(workspace: Path) -> list[Path]:
    root = campaign_root(workspace)
    created: list[Path] = []
    for name in LIFECYCLE_DIRS:
        path = root / name
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)
    defaults = {
        root / "active-queue.md": _default_active_queue(),
        root / "completed-queue.md": _default_completed_queue(),
    }
    for path, content in defaults.items():
        if not path.exists():
            path.write_text(content, encoding="utf-8", newline="\n")
            created.append(path)
    return created


def parse_campaign(path: Path) -> Campaign:
    text = path.read_text(encoding="utf-8")
    title = path.stem
    fields: dict[str, str] = {}
    for raw in text.splitlines()[:40]:
        if raw.startswith("# "):
            title = raw[2:].strip()
            continue
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        if key.strip() in HEADER_KEYS:
            fields[key.strip()] = value.strip()
    return Campaign(path=path, title=title, fields=fields, body=text)


def render_campaign(campaign: Campaign) -> str:
    lines = [f"# {campaign.title}", ""]
    for key in HEADER_KEYS:
        if key in campaign.fields:
            lines.append(f"{key}: {campaign.fields[key]}")
    remainder = campaign.body.splitlines()
    body_start = next((index for index, line in enumerate(remainder) if line.startswith("## ")), len(remainder))
    tail = remainder[body_start:]
    if tail:
        lines.extend(["", *tail])
    return "\n".join(lines).rstrip() + "\n"


def load_all(workspace: Path) -> dict[str, Campaign]:
    root = campaign_root(workspace)
    result: dict[str, Campaign] = {}
    for folder in LIFECYCLE_DIRS:
        for path in sorted((root / folder).glob("*.md")):
            campaign = parse_campaign(path)
            campaign_id = campaign.campaign_id
            if not campaign_id:
                raise CampaignError(f"missing Campaign ID: {path.relative_to(workspace)}")
            if campaign_id in result:
                raise CampaignError(f"duplicate Campaign ID: {campaign_id}")
            result[campaign_id] = campaign
    return result


def queue_order(workspace: Path) -> list[str]:
    path = campaign_root(workspace) / "active-queue.md"
    if not path.exists():
        return []
    order: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = QUEUE_LINK_RE.match(line)
        if match:
            order.append(match.group(1))
    return order


def state_token(workspace: Path) -> str:
    root = campaign_root(workspace)
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.md")):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def _short(campaign: Campaign | None) -> str:
    return "none" if campaign is None else f"{campaign.campaign_id} — {campaign.title}"


def render_active_queue(order: list[str], campaigns: dict[str, Campaign]) -> str:
    active = [campaigns[item] for item in order if item in campaigns]
    completed = sorted(
        (item for item in campaigns.values() if item.status == "complete"),
        key=lambda item: item.fields.get("Completion Date", ""),
        reverse=True,
    )
    working = next((item for item in active if item.status == "working"), None)
    next_item = next((item for item in active if item.status == "queued"), None)
    blocked = [item for item in active if item.status == "blocked" or item.fields.get("Decision", "none") != "none"]
    detours = [item for item in active if item.fields.get("Detour For", "none") != "none" or item.fields.get("Return To", "none") != "none"]
    lines = [
        "# Active Campaign Queue",
        "",
        f"Updated: {date.today().isoformat()}",
        "",
        "## Owner State",
        "",
        f"- Last completed: {_short(completed[0] if completed else None)}",
        f"- Working now: {_short(working)}",
        f"- Next: {_short(next_item)}",
        "- Blocker or decision needed: " + ("; ".join(_short(item) for item in blocked) if blocked else "none"),
        "- Detour and return point: " + ("; ".join(_short(item) for item in detours) if detours else "none"),
        "",
        "## Ordered Queue",
        "",
    ]
    if not active:
        lines.append("No active campaigns.")
    for position, item in enumerate(active, start=1):
        details = [f"state: {item.status}", f"outcome: {item.outcome}"]
        if item.dependencies:
            details.append("depends: " + ", ".join(item.dependencies))
        if item.fields.get("Decision", "none") != "none":
            details.append("decision: " + item.fields["Decision"])
        if item.fields.get("Return To", "none") != "none":
            details.append("return: " + item.fields["Return To"])
        lines.append(f"{position}. [{item.title}](active/{item.campaign_id}.md) — " + " — ".join(details))
    return "\n".join(lines).rstrip() + "\n"


def render_completed_queue(campaigns: dict[str, Campaign]) -> str:
    completed = sorted(
        (item for item in campaigns.values() if item.status == "complete"),
        key=lambda item: (item.fields.get("Completion Date", ""), item.campaign_id),
        reverse=True,
    )
    lines = [
        "# Completed Campaign Queue",
        "",
        f"Updated: {date.today().isoformat()}",
        "",
        "Newest completion first.",
        "",
    ]
    if not completed:
        lines.append("No completed campaigns.")
    for item in completed:
        evidence = item.fields.get("Completion Evidence", "none")
        lines.append(
            f"- {item.fields.get('Completion Date', 'unknown')} — [{item.title}]"
            f"(completed/{item.campaign_id}.md) — {item.outcome} — evidence: {evidence}"
        )
    return "\n".join(lines).rstrip() + "\n"


def _atomic_write(path: Path, content: bytes | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if content is None:
        path.unlink(missing_ok=True)
        return
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def _journal_path(workspace: Path) -> Path:
    return campaign_root(workspace) / ".transaction.json"


def recover_if_needed(workspace: Path) -> bool:
    journal = _journal_path(workspace)
    if not journal.exists():
        return False
    payload = json.loads(journal.read_text(encoding="utf-8"))
    for relative, encoded in payload["originals"].items():
        path = workspace / relative
        content = None if encoded is None else base64.b64decode(encoded)
        _atomic_write(path, content)
    journal.unlink()
    return True


def apply_transaction(workspace: Path, changes: dict[Path, str | None]) -> None:
    journal = _journal_path(workspace)
    if journal.exists():
        raise CampaignError("unfinished campaign transaction exists; rerun any command to recover it")
    originals: dict[str, str | None] = {}
    for path in changes:
        relative = path.relative_to(workspace).as_posix()
        originals[relative] = base64.b64encode(path.read_bytes()).decode("ascii") if path.exists() else None
    payload = {"schema_version": 1, "originals": originals}
    _atomic_write(journal, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    try:
        for path, content in changes.items():
            _atomic_write(path, None if content is None else content.encode("utf-8"))
        findings = validate(workspace)
        if findings:
            raise CampaignError("transaction would violate campaign invariants: " + "; ".join(findings))
    except Exception:
        recover_if_needed(workspace)
        raise
    journal.unlink()


def require_token(workspace: Path, expected: str | None) -> None:
    if not expected:
        raise CampaignError("mutation requires --expect TOKEN from status")
    actual = state_token(workspace)
    if expected != actual:
        raise CampaignError(f"stale campaign state: expected {expected}, current {actual}")


def _validate_graph(campaigns: dict[str, Campaign]) -> list[str]:
    findings: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(campaign_id: str, chain: list[str]) -> None:
        if campaign_id in visiting:
            findings.append("dependency cycle: " + " -> ".join([*chain, campaign_id]))
            return
        if campaign_id in visited:
            return
        visiting.add(campaign_id)
        item = campaigns[campaign_id]
        for dependency in item.dependencies:
            if dependency not in campaigns:
                findings.append(f"{campaign_id} has missing dependency {dependency}")
            elif campaigns[dependency].status == "abandoned":
                findings.append(f"{campaign_id} depends on abandoned campaign {dependency}")
            else:
                visit(dependency, [*chain, campaign_id])
        visiting.remove(campaign_id)
        visited.add(campaign_id)

    for campaign_id in campaigns:
        visit(campaign_id, [])
    return findings


def validate(workspace: Path) -> list[str]:
    findings: list[str] = []
    campaigns = load_all(workspace)
    order = queue_order(workspace)
    active_ids = {item.campaign_id for item in campaigns.values() if item.path.parent.name == "active"}
    if len(order) != len(set(order)):
        findings.append("active queue contains duplicate campaign IDs")
    missing = sorted(active_ids - set(order))
    extra = sorted(set(order) - active_ids)
    if missing:
        findings.append("active campaigns missing from queue: " + ", ".join(missing))
    if extra:
        findings.append("queue entries missing active request files: " + ", ".join(extra))
    working = 0
    folder_states = {
        "active": ACTIVE_STATES,
        "completed": {"complete"},
        "deferred": {"deferred"},
        "abandoned": {"abandoned"},
    }
    for item in campaigns.values():
        if not ID_RE.fullmatch(item.campaign_id):
            findings.append(f"invalid campaign ID: {item.campaign_id}")
        if item.path.stem != item.campaign_id:
            findings.append(f"campaign filename does not match ID: {item.path.name}")
        folder = item.path.parent.name
        if item.status not in folder_states[folder]:
            findings.append(f"{item.campaign_id} state {item.status!r} conflicts with {folder}/")
        if item.status == "working":
            working += 1
        if item.status == "complete" and not item.fields.get("Completion Date"):
            findings.append(f"{item.campaign_id} is complete without Completion Date")
    if working > 1:
        findings.append("more than one campaign is working")
    findings.extend(_validate_graph(campaigns))
    active_path = campaign_root(workspace) / "active-queue.md"
    completed_path = campaign_root(workspace) / "completed-queue.md"
    def without_updated(text: str) -> str:
        return "\n".join(line for line in text.splitlines() if not line.startswith("Updated: "))

    if without_updated(active_path.read_text(encoding="utf-8")) != without_updated(render_active_queue(order, campaigns)):
        findings.append("active-queue.md is stale or manually inconsistent")
    if without_updated(completed_path.read_text(encoding="utf-8")) != without_updated(render_completed_queue(campaigns)):
        findings.append("completed-queue.md is stale or manually inconsistent")
    return findings


def require_valid(workspace: Path) -> None:
    findings = validate(workspace)
    if findings:
        raise CampaignError("campaign state is invalid: " + "; ".join(findings))


def _campaign_text(
    campaign_id: str,
    title: str,
    outcome: str,
    gate: str,
    dependencies: list[str],
    decision: str,
    detour_for: str,
    return_to: str,
) -> str:
    fields = {
        "Status": "queued",
        "Type": "campaign",
        "Updated": date.today().isoformat(),
        "Next Action": "execute when selected from the active campaign queue",
        "Campaign ID": campaign_id,
        "Outcome": outcome,
        "Depends On": ", ".join(dependencies) if dependencies else "none",
        "Decision": decision,
        "Detour For": detour_for,
        "Return To": return_to,
        "Completion Gate": gate,
        "Completion Evidence": "none",
        "Disposition": "none",
    }
    campaign = Campaign(Path(), title, fields, "## Request\n\nAdd detailed execution context here.\n\n## Completion Check\n\n" + gate + "\n")
    return render_campaign(campaign)


def _refresh_changes(workspace: Path, order: list[str], campaigns: dict[str, Campaign]) -> dict[Path, str | None]:
    root = campaign_root(workspace)
    return {
        root / "active-queue.md": render_active_queue(order, campaigns),
        root / "completed-queue.md": render_completed_queue(campaigns),
    }


def add_campaign(args: argparse.Namespace, workspace: Path) -> None:
    require_token(workspace, args.expect)
    require_valid(workspace)
    if not ID_RE.fullmatch(args.campaign_id):
        raise CampaignError("campaign ID must be lowercase kebab-case")
    campaigns = load_all(workspace)
    if args.campaign_id in campaigns:
        raise CampaignError(f"campaign already exists: {args.campaign_id}")
    normalized_title = " ".join(args.title.lower().split())
    normalized_outcome = " ".join(args.outcome.lower().split())
    overlap = next(
        (
            item
            for item in campaigns.values()
            if " ".join(item.title.lower().split()) == normalized_title
            or " ".join(item.outcome.lower().split()) == normalized_outcome
        ),
        None,
    )
    if overlap is not None:
        raise CampaignError(f"campaign overlaps existing {overlap.campaign_id}; resolve duplication before adding")
    dependencies = args.depends_on or []
    missing = sorted(set(dependencies) - set(campaigns))
    if missing:
        raise CampaignError("missing dependencies: " + ", ".join(missing))
    path = campaign_root(workspace) / "active" / f"{args.campaign_id}.md"
    text = _campaign_text(
        args.campaign_id,
        args.title,
        args.outcome,
        args.completion_gate,
        dependencies,
        args.decision,
        args.detour_for,
        args.return_to,
    )
    new_item = parse_campaign_text(path, text)
    campaigns[args.campaign_id] = new_item
    order = queue_order(workspace)
    position = len(order) if args.position is None else args.position - 1
    if position < 0 or position > len(order):
        raise CampaignError("position is outside the active queue")
    order.insert(position, args.campaign_id)
    changes = {path: text, **_refresh_changes(workspace, order, campaigns)}
    apply_transaction(workspace, changes)


def parse_campaign_text(path: Path, text: str) -> Campaign:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    try:
        parsed = parse_campaign(temporary)
    finally:
        temporary.unlink(missing_ok=True)
    parsed.path = path
    return parsed


def mutate_campaign(args: argparse.Namespace, workspace: Path) -> None:
    require_token(workspace, args.expect)
    require_valid(workspace)
    campaigns = load_all(workspace)
    if args.campaign_id not in campaigns:
        raise CampaignError(f"unknown campaign: {args.campaign_id}")
    item = campaigns[args.campaign_id]
    order = queue_order(workspace)
    root = campaign_root(workspace)
    changes: dict[Path, str | None] = {}
    if args.command == "reorder":
        if item.path.parent.name != "active":
            raise CampaignError("only active campaigns can be reordered")
        order.remove(item.campaign_id)
        position = args.position - 1
        if position < 0 or position > len(order):
            raise CampaignError("position is outside the active queue")
        order.insert(position, item.campaign_id)
    elif args.command == "start":
        if item.status != "queued":
            raise CampaignError("only a queued campaign can start")
        if any(other.status == "working" for other in campaigns.values()):
            raise CampaignError("another campaign is already working")
        incomplete = [dep for dep in item.dependencies if campaigns[dep].status != "complete"]
        if incomplete:
            raise CampaignError("campaign has incomplete dependencies: " + ", ".join(incomplete))
        item.fields["Status"] = "working"
        item.fields["Next Action"] = "execute the campaign completion gate"
    elif args.command == "block":
        if item.status not in {"queued", "working"}:
            raise CampaignError("only queued or working campaigns can be blocked")
        item.fields["Status"] = "blocked"
        item.fields["Decision"] = args.reason
        item.fields["Next Action"] = "resolve blocker or decision: " + args.reason
    elif args.command == "defer":
        if item.path.parent.name != "active":
            raise CampaignError("only active campaigns can be deferred")
        item.fields["Status"] = "deferred"
        item.fields["Disposition"] = args.reason
        item.fields["Reactivate When"] = args.reactivate_when
        item.fields["Next Action"] = "reactivate when " + args.reactivate_when
        order.remove(item.campaign_id)
        destination = root / "deferred" / item.path.name
        changes[item.path] = None
        item.path = destination
    elif args.command == "abandon":
        if item.path.parent.name not in {"active", "deferred"}:
            raise CampaignError("only active or deferred campaigns can be abandoned")
        item.fields["Status"] = "abandoned"
        item.fields["Disposition"] = args.reason + (f"; replacement: {args.replacement}" if args.replacement else "")
        item.fields["Next Action"] = "none"
        if item.campaign_id in order:
            order.remove(item.campaign_id)
        destination = root / "abandoned" / item.path.name
        changes[item.path] = None
        item.path = destination
    elif args.command == "complete":
        if item.path.parent.name != "active":
            raise CampaignError("only an active campaign can complete")
        if not args.gate_passed:
            raise CampaignError("completion requires --gate-passed")
        item.fields["Status"] = "complete"
        item.fields["Completion Evidence"] = args.evidence
        item.fields["Completion Date"] = date.today().isoformat()
        item.fields["Disposition"] = "completed"
        item.fields["Next Action"] = "none"
        order.remove(item.campaign_id)
        destination = root / "completed" / item.path.name
        changes[item.path] = None
        item.path = destination
        if not any(other.status == "working" and other.campaign_id != item.campaign_id for other in campaigns.values()):
            for candidate_id in order:
                candidate = campaigns[candidate_id]
                if candidate.status == "queued" and all(campaigns[dep].status == "complete" for dep in candidate.dependencies):
                    candidate.fields["Status"] = "working"
                    candidate.fields["Next Action"] = "execute the campaign completion gate"
                    changes[candidate.path] = render_campaign(candidate)
                    break
    else:
        raise CampaignError(f"unsupported mutation: {args.command}")
    item.fields["Updated"] = date.today().isoformat()
    changes[item.path] = render_campaign(item)
    changes.update(_refresh_changes(workspace, order, campaigns))
    apply_transaction(workspace, changes)


def migration_preview(workspace: Path) -> dict[str, object]:
    qa = workspace / "work" / "q&a"
    linked_requests = sorted(path.relative_to(workspace).as_posix() for path in qa.glob("*.md")) if qa.exists() else []
    inbox = qa / "ask.txt"
    actionable = []
    if inbox.is_file():
        actionable = [line.strip() for line in inbox.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    return {
        "mode": "preview-only",
        "source_requests": linked_requests,
        "inbox_entries": actionable,
        "target_root": "work/00-campaigns/active",
        "writes_performed": False,
        "requires_exact_approved_manifest_to_apply": True,
    }


def status_payload(workspace: Path) -> dict[str, object]:
    campaigns = load_all(workspace)
    order = queue_order(workspace)
    ordered = [campaigns[item] for item in order]
    completed = sorted(
        (item for item in campaigns.values() if item.status == "complete"),
        key=lambda item: (item.fields.get("Completion Date", ""), item.campaign_id),
        reverse=True,
    )
    working = [item for item in ordered if item.status == "working"]
    ready = [
        item
        for item in ordered
        if item.status == "queued"
        and all(campaigns[dependency].status == "complete" for dependency in item.dependencies)
    ]
    blocked = [item for item in ordered if item.status == "blocked"]
    decisions = [item for item in ordered if item.fields.get("Decision", "none") != "none"]
    detours = [
        item
        for item in ordered
        if item.fields.get("Detour For", "none") != "none"
        or item.fields.get("Return To", "none") != "none"
    ]
    return {
        "state_token": state_token(workspace),
        "active_order": order,
        "last_completed": completed[0].campaign_id if completed else None,
        "working": [item.campaign_id for item in working],
        "next": ready[0].campaign_id if ready else None,
        "blocked": [item.campaign_id for item in blocked],
        "decisions_needed": [item.campaign_id for item in decisions],
        "detours": [item.campaign_id for item in detours],
        "completed": [item.campaign_id for item in completed],
        "findings": validate(workspace),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Tool Shed owner-facing campaign queues.")
    parser.add_argument("--workspace", default=".", help="Project workspace root.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init")
    subparsers.add_parser("status")
    subparsers.add_parser("next")
    subparsers.add_parser("completed")
    subparsers.add_parser("validate")
    subparsers.add_parser("migrate-preview")
    add = subparsers.add_parser("add")
    add.add_argument("campaign_id")
    add.add_argument("title")
    add.add_argument("--outcome", required=True)
    add.add_argument("--completion-gate", required=True)
    add.add_argument("--depends-on", action="append")
    add.add_argument("--decision", default="none")
    add.add_argument("--detour-for", default="none")
    add.add_argument("--return-to", default="none")
    add.add_argument("--position", type=int)
    for command in ("reorder", "start", "block", "defer", "abandon", "complete"):
        child = subparsers.add_parser(command)
        child.add_argument("campaign_id")
        if command == "reorder":
            child.add_argument("--position", type=int, required=True)
        if command in {"block", "defer", "abandon"}:
            child.add_argument("--reason", required=True)
        if command == "defer":
            child.add_argument("--reactivate-when", required=True)
        if command == "abandon":
            child.add_argument("--replacement")
        if command == "complete":
            child.add_argument("--evidence", required=True)
            child.add_argument("--gate-passed", action="store_true")
    for child in subparsers.choices.values():
        child.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
        if child.prog.split()[-1] in {"add", "reorder", "start", "block", "defer", "abandon", "complete"}:
            child.add_argument("--expect", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    try:
        root = campaign_root(workspace)
        if args.command == "init":
            ensure_tree(workspace)
        elif not root.is_dir():
            raise CampaignError("campaign tree is not initialized; run init or the Tool Shed workspace installer")
        recovered = recover_if_needed(workspace)
        if args.command == "init":
            payload: object = {"root": str(campaign_root(workspace)), "state_token": state_token(workspace), "recovered": recovered}
        elif args.command == "status":
            payload = status_payload(workspace)
        elif args.command == "validate":
            findings = validate(workspace)
            payload = {"valid": not findings, "findings": findings, "state_token": state_token(workspace)}
        elif args.command == "next":
            campaigns = load_all(workspace)
            ordered = [campaigns[item] for item in queue_order(workspace)]
            candidate = next((item for item in ordered if item.status == "working"), None)
            if candidate is None:
                candidate = next(
                    (
                        item
                        for item in ordered
                        if item.status == "queued"
                        and all(campaigns[dependency].status == "complete" for dependency in item.dependencies)
                    ),
                    None,
                )
            payload = None if candidate is None else {"campaign_id": candidate.campaign_id, "title": candidate.title, "status": candidate.status, "path": candidate.path.relative_to(workspace).as_posix()}
        elif args.command == "completed":
            campaigns = load_all(workspace)
            completed = sorted(
                (item for item in campaigns.values() if item.status == "complete"),
                key=lambda item: (item.fields.get("Completion Date", ""), item.campaign_id),
                reverse=True,
            )
            payload = [{"campaign_id": item.campaign_id, "title": item.title, "completed": item.fields.get("Completion Date"), "evidence": item.fields.get("Completion Evidence")} for item in completed]
        elif args.command == "migrate-preview":
            payload = migration_preview(workspace)
        elif args.command == "add":
            add_campaign(args, workspace)
            payload = status_payload(workspace)
        else:
            mutate_campaign(args, workspace)
            payload = status_payload(workspace)
    except (CampaignError, OSError, json.JSONDecodeError) as error:
        print(f"Campaign operation failed: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if isinstance(payload, dict) and "state_token" in payload:
            print(f"Campaign state token: {payload['state_token']}")
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
