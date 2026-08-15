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
    "Primary Focus Areas",
    "Supporting Focus Areas",
    "Depends On",
    "Decision",
    "Detour For",
    "Return To",
    "Completion Gate",
    "Completion Evidence",
    "Completion Date",
    "Completion Order",
    "Disposition",
    "Reactivate When",
)
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
QUEUE_LINK_RE = re.compile(
    r"^\d+\. (?:\*\*)?\[[^]]+\]\(active/([a-z0-9-]+)\.md\)(?:\*\*)?"
)
FOCUS_AREA_CATALOG = Path("work/focus-areas.md")
FOCUS_AREA_FIELDS = (
    "Name",
    "Purpose",
    "Includes",
    "Excludes",
    "Evidence",
    "Uncertainty",
)
OUTCOME_FOCUS_RE = re.compile(
    r"(?i)(?:\s*[—-]\s*|\s+)focus areas?:\s*([^.;]+)[.;]?"
)


class CampaignError(ValueError):
    pass


@dataclass(frozen=True)
class FocusArea:
    focus_area_id: str
    name: str
    purpose: str
    includes: str
    excludes: str
    evidence: str
    uncertainty: str


@dataclass(frozen=True)
class FocusAreaCatalog:
    path: Path
    status: str
    areas: dict[str, FocusArea]


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
        return _field_list(self.fields.get("Depends On", "none"))

    @property
    def primary_focus_areas(self) -> list[str]:
        return _field_list(self.fields.get("Primary Focus Areas", "none"))

    @property
    def supporting_focus_areas(self) -> list[str]:
        return _field_list(self.fields.get("Supporting Focus Areas", "none"))


def _field_list(value: str) -> list[str]:
    if value.lower() == "none" or not value.strip():
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def campaign_root(workspace: Path) -> Path:
    return workspace / "work" / ROOT_NAME


def focus_area_catalog_path(workspace: Path) -> Path:
    return workspace / FOCUS_AREA_CATALOG


def load_focus_area_catalog(workspace: Path) -> FocusAreaCatalog | None:
    path = focus_area_catalog_path(workspace)
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    headers: dict[str, str] = {}
    for raw in lines[:40]:
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        if key.strip() in {"Status", "Type"}:
            headers[key.strip()] = value.strip()
    status = headers.get("Status", "").lower()
    if headers.get("Type") != "focus-area-catalog":
        raise CampaignError("focus-area catalog Type must be focus-area-catalog")
    if status not in {"proposed", "approved"}:
        raise CampaignError("focus-area catalog Status must be proposed or approved")

    records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in lines:
        if raw.startswith("Focus Area ID:"):
            if current is not None:
                records.append(current)
            current = {"Focus Area ID": raw.split(":", 1)[1].strip()}
            continue
        if current is None or ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        if key.strip() in FOCUS_AREA_FIELDS:
            current[key.strip()] = value.strip()
    if current is not None:
        records.append(current)

    areas: dict[str, FocusArea] = {}
    for record in records:
        focus_area_id = record.get("Focus Area ID", "")
        if not ID_RE.fullmatch(focus_area_id):
            raise CampaignError(
                f"focus-area catalog has invalid stable ID: {focus_area_id or 'missing'}"
            )
        if focus_area_id in areas:
            raise CampaignError(f"focus-area catalog has duplicate ID: {focus_area_id}")
        missing = [key for key in FOCUS_AREA_FIELDS if not record.get(key, "").strip()]
        if missing:
            raise CampaignError(
                f"focus area {focus_area_id} is missing: " + ", ".join(missing)
            )
        areas[focus_area_id] = FocusArea(
            focus_area_id=focus_area_id,
            name=record["Name"],
            purpose=record["Purpose"],
            includes=record["Includes"],
            excludes=record["Excludes"],
            evidence=record["Evidence"],
            uncertainty=record["Uncertainty"],
        )
    if status == "approved" and not areas:
        raise CampaignError("approved focus-area catalog must define at least one area")
    return FocusAreaCatalog(path=path, status=status, areas=areas)


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
    paths = list(root.rglob("*.md"))
    catalog_path = focus_area_catalog_path(workspace)
    if catalog_path.is_file():
        paths.append(catalog_path)
    for path in sorted(paths):
        digest.update(path.relative_to(workspace).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def _short(campaign: Campaign | None) -> str:
    return "none" if campaign is None else f"{campaign.campaign_id} — {campaign.title}"


def _completion_order(campaign: Campaign) -> int:
    try:
        return int(campaign.fields.get("Completion Order", "0"))
    except ValueError:
        return 0


def _completion_sort_key(campaign: Campaign) -> tuple[int, str, str]:
    return (
        _completion_order(campaign),
        campaign.fields.get("Completion Date", ""),
        campaign.campaign_id,
    )


def first_ready_campaign(
    order: list[str],
    campaigns: dict[str, Campaign],
) -> Campaign | None:
    for campaign_id in order:
        item = campaigns.get(campaign_id)
        if item is not None and campaign_readiness(item, campaigns) == "ready":
            return item
    return None


def campaign_readiness(item: Campaign, campaigns: dict[str, Campaign]) -> str:
    if item.status == "working":
        return "working"
    if item.status == "blocked" or item.fields.get("Decision", "none") != "none":
        return "blocked"
    if item.status == "complete":
        return "complete"
    if item.status == "queued":
        incomplete = any(
            dependency not in campaigns or campaigns[dependency].status != "complete"
            for dependency in item.dependencies
        )
        return "waiting" if incomplete else "ready"
    return item.status or "unknown"


def _readiness_display(readiness: str) -> str:
    return {
        "working": "🔵 **WORKING**",
        "ready": "🟢 **READY**",
        "waiting": "🟡 **WAITING**",
        "blocked": "🔴 **BLOCKED**",
        "complete": "✅ **COMPLETE**",
    }.get(readiness, f"**{readiness.upper()}**")


def _focus_area_names(
    identifiers: list[str],
    catalog: FocusAreaCatalog | None,
) -> list[str]:
    if catalog is None or catalog.status != "approved":
        return identifiers
    return [
        catalog.areas[identifier].name if identifier in catalog.areas else identifier
        for identifier in identifiers
    ]


def render_active_queue(
    order: list[str],
    campaigns: dict[str, Campaign],
    catalog: FocusAreaCatalog | None = None,
) -> str:
    active = [campaigns[item] for item in order if item in campaigns]
    completed = sorted(
        (item for item in campaigns.values() if item.status == "complete"),
        key=_completion_sort_key,
        reverse=True,
    )
    working = next((item for item in active if item.status == "working"), None)
    next_item = first_ready_campaign(order, campaigns)
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
        lines.append(
            f"{position}. **[{item.title}](active/{item.campaign_id}.md)**"
        )
        lines.append(
            f"   - 🚦 **STATE:** {_readiness_display(campaign_readiness(item, campaigns))}"
        )
        primary = _focus_area_names(item.primary_focus_areas, catalog)
        supporting = _focus_area_names(item.supporting_focus_areas, catalog)
        if primary:
            lines.append("   - 🎯 **PRIMARY FOCUS AREAS:** " + "; ".join(primary))
        if supporting:
            lines.append("   - 🧩 **SUPPORTING FOCUS AREAS:** " + "; ".join(supporting))
        if item.dependencies:
            for dependency in item.dependencies:
                dependency_item = campaigns.get(dependency)
                dependency_state = (
                    campaign_readiness(dependency_item, campaigns)
                    if dependency_item is not None
                    else "missing"
                )
                lines.append(
                    f"   - 🔗 **DEPENDS ON:** `{dependency}` — "
                    + _readiness_display(dependency_state)
                )
        if item.fields.get("Decision", "none") != "none":
            lines.append("   - ⚠️ **DECISION NEEDED:** " + item.fields["Decision"])
        if item.fields.get("Detour For", "none") != "none":
            lines.append("   - ↪️ **DETOUR FOR:** " + item.fields["Detour For"])
        if item.fields.get("Return To", "none") != "none":
            lines.append("   - ↩️ **RETURN TO:** " + item.fields["Return To"])
        lines.append("   - 🏁 **OUTCOME:** " + item.outcome)
    return "\n".join(lines).rstrip() + "\n"


def render_completed_queue(campaigns: dict[str, Campaign]) -> str:
    completed = sorted(
        (item for item in campaigns.values() if item.status == "complete"),
        key=_completion_sort_key,
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
    catalog: FocusAreaCatalog | None = None
    try:
        catalog = load_focus_area_catalog(workspace)
    except CampaignError as error:
        findings.append(f"focus-area catalog is invalid: {error}")
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
    completion_orders: dict[int, str] = {}
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
        primary = item.primary_focus_areas
        supporting = item.supporting_focus_areas
        assigned = [*primary, *supporting]
        if len(assigned) != len(set(assigned)):
            findings.append(
                f"focus-area campaign {item.campaign_id} repeats a primary/supporting assignment"
            )
        if assigned and (catalog is None or catalog.status != "approved"):
            findings.append(
                f"focus-area campaign {item.campaign_id} assigns areas without an approved catalog"
            )
        if catalog is not None and catalog.status == "approved":
            unknown = sorted(set(assigned) - set(catalog.areas))
            if unknown:
                findings.append(
                    f"focus-area campaign {item.campaign_id} references unknown IDs: "
                    + ", ".join(unknown)
                )
            is_dangler = item.campaign_id == "resolve-unclassified-work" or bool(
                re.fullmatch(r"resolve-unclassified-work-[2-9][0-9]*", item.campaign_id)
            )
            if item.path.parent.name == "active" and not primary and not is_dangler:
                findings.append(
                    f"focus-area active campaign {item.campaign_id} has no Primary Focus Areas"
                )
        raw_completion_order = item.fields.get("Completion Order")
        if raw_completion_order is not None:
            try:
                completion_order = int(raw_completion_order)
            except ValueError:
                findings.append(f"{item.campaign_id} has invalid Completion Order")
            else:
                if completion_order < 1:
                    findings.append(f"{item.campaign_id} has invalid Completion Order")
                elif completion_order in completion_orders:
                    findings.append(
                        f"duplicate Completion Order {completion_order}: "
                        f"{completion_orders[completion_order]}, {item.campaign_id}"
                    )
                else:
                    completion_orders[completion_order] = item.campaign_id
    if working > 1:
        findings.append("more than one campaign is working")
    findings.extend(_validate_graph(campaigns))
    active_path = campaign_root(workspace) / "active-queue.md"
    completed_path = campaign_root(workspace) / "completed-queue.md"
    def without_updated(text: str) -> str:
        return "\n".join(line for line in text.splitlines() if not line.startswith("Updated: "))

    if without_updated(active_path.read_text(encoding="utf-8")) != without_updated(
        render_active_queue(order, campaigns, catalog)
    ):
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
    primary_focus_areas: list[str] | None = None,
    supporting_focus_areas: list[str] | None = None,
) -> str:
    fields = {
        "Status": "queued",
        "Type": "campaign",
        "Updated": date.today().isoformat(),
        "Next Action": "execute when selected from the active campaign queue",
        "Campaign ID": campaign_id,
        "Outcome": outcome,
        "Primary Focus Areas": ", ".join(primary_focus_areas or []) or "none",
        "Supporting Focus Areas": ", ".join(supporting_focus_areas or []) or "none",
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
        root / "active-queue.md": render_active_queue(
            order, campaigns, load_focus_area_catalog(workspace)
        ),
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
        args.primary_focus_area,
        args.supporting_focus_area,
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
        if item.fields.get("Decision", "none") != "none":
            raise CampaignError("campaign has an unresolved decision")
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
    elif args.command == "unblock":
        if item.status != "blocked":
            raise CampaignError("only a blocked campaign can be unblocked")
        item.fields["Status"] = "queued"
        item.fields["Decision"] = "none"
        item.fields["Next Action"] = "execute when selected from the active campaign queue"
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
        item.fields["Completion Order"] = str(
            max((_completion_order(other) for other in campaigns.values()), default=0) + 1
        )
        item.fields["Disposition"] = "completed"
        item.fields["Next Action"] = "none"
        order.remove(item.campaign_id)
        destination = root / "completed" / item.path.name
        changes[item.path] = None
        item.path = destination
        if not any(other.status == "working" and other.campaign_id != item.campaign_id for other in campaigns.values()):
            candidate = first_ready_campaign(order, campaigns)
            if candidate is not None:
                candidate.fields["Status"] = "working"
                candidate.fields["Next Action"] = "execute the campaign completion gate"
                changes[candidate.path] = render_campaign(candidate)
    else:
        raise CampaignError(f"unsupported mutation: {args.command}")
    item.fields["Updated"] = date.today().isoformat()
    changes[item.path] = render_campaign(item)
    changes.update(_refresh_changes(workspace, order, campaigns))
    apply_transaction(workspace, changes)


def migration_preview(workspace: Path) -> dict[str, object]:
    inbox_roots = (workspace / "work" / "01-q&a", workspace / "work" / "q&a")
    linked_requests = sorted(
        path.relative_to(workspace).as_posix()
        for qa in inbox_roots
        if qa.exists()
        for path in qa.glob("*.md")
    )
    inbox_sources = []
    for qa in inbox_roots:
        inbox = qa / "ask.txt"
        if not inbox.is_file():
            continue
        actionable = [
            line.strip()
            for line in inbox.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if actionable:
            inbox_sources.append(
                {"path": inbox.relative_to(workspace).as_posix(), "entries": actionable}
            )
    campaigns = load_all(workspace)
    catalog = load_focus_area_catalog(workspace)
    focus_candidates: list[dict[str, object]] = []
    focus_operations: list[dict[str, object]] = []
    name_ids = {
        re.sub(r"[^a-z0-9]+", "-", area.name.lower()).strip("-"): area_id
        for area_id, area in (catalog.areas.items() if catalog else [])
    }
    for item in sorted(campaigns.values(), key=lambda campaign: campaign.campaign_id):
        match = OUTCOME_FOCUS_RE.search(item.outcome)
        if match is None:
            continue
        raw_values = [
            value.strip()
            for value in re.split(r"[,;]", match.group(1))
            if value.strip()
        ]
        matched: list[str] = []
        unresolved: list[str] = []
        for value in raw_values:
            normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
            if catalog and normalized in catalog.areas:
                matched.append(normalized)
            elif normalized in name_ids:
                matched.append(name_ids[normalized])
            else:
                unresolved.append(value)
        outcome_after = OUTCOME_FOCUS_RE.sub("", item.outcome).strip(" —-;.")
        candidate: dict[str, object] = {
            "campaign_id": item.campaign_id,
            "raw_focus_areas": raw_values,
            "matched_ids": matched,
            "unresolved_values": unresolved,
            "outcome_before": item.outcome,
            "outcome_after": outcome_after,
            "requires_owner_review": True,
        }
        if catalog and catalog.status == "approved" and matched and not unresolved:
            operation = {
                "op": "set_focus_areas",
                "campaign_id": item.campaign_id,
                "primary": matched,
                "supporting": [],
                "remove_outcome_focus_clause": True,
            }
            candidate["manifest_operation"] = operation
            focus_operations.append(operation)
        focus_candidates.append(candidate)
    import reconcile_campaign_queue

    focus_state_token = reconcile_campaign_queue.whole_work_state_token(workspace)
    return {
        "mode": "preview-only",
        "source_requests": linked_requests,
        "inbox_sources": inbox_sources,
        "inbox_entries": [entry for source in inbox_sources for entry in source["entries"]],
        "target_root": "work/00-campaigns/active",
        "writes_performed": False,
        "requires_exact_approved_manifest_to_apply": True,
        "focus_area_migration": {
            "catalog_path": FOCUS_AREA_CATALOG.as_posix(),
            "catalog_status": catalog.status if catalog else "missing",
            "candidates": focus_candidates,
            "suggested_manifest": {
                "schema_version": 1,
                "kind": "tool-shed-campaign-reconciliation",
                "state_token": focus_state_token,
                "operations": focus_operations,
            },
            "writes_performed": False,
            "requires_owner_review": True,
        },
    }


def dangler_resolution_visibility(
    workspace: Path,
    campaigns: dict[str, Campaign],
    order: list[str],
) -> dict[str, object] | None:
    # Import lazily because reconciliation builds on the queue lifecycle primitives in this module.
    import reconcile_campaign_queue

    whole_work = reconcile_campaign_queue.discover_whole_work(workspace, campaigns)
    return reconcile_campaign_queue.dangler_resolution_proposal(
        workspace, campaigns, order, whole_work
    )


def status_payload(workspace: Path) -> dict[str, object]:
    campaigns = load_all(workspace)
    order = queue_order(workspace)
    ordered = [campaigns[item] for item in order]
    completed = sorted(
        (item for item in campaigns.values() if item.status == "complete"),
        key=_completion_sort_key,
        reverse=True,
    )
    working = [item for item in ordered if item.status == "working"]
    ready = first_ready_campaign(order, campaigns)
    blocked = [item for item in ordered if item.status == "blocked"]
    decisions = [item for item in ordered if item.fields.get("Decision", "none") != "none"]
    detours = [
        item
        for item in ordered
        if item.fields.get("Detour For", "none") != "none"
        or item.fields.get("Return To", "none") != "none"
    ]
    dangler_resolution = dangler_resolution_visibility(workspace, campaigns, order)
    next_campaign = ready.campaign_id if ready else None
    return {
        "state_token": state_token(workspace),
        "active_order": order,
        "last_completed": completed[0].campaign_id if completed else None,
        "working": [item.campaign_id for item in working],
        "next": next_campaign or (
            str(dangler_resolution["campaign_id"]) if dangler_resolution else None
        ),
        "next_source": "campaign-queue" if next_campaign else (
            "campaign-reconciliation" if dangler_resolution else None
        ),
        "blocked": [item.campaign_id for item in blocked],
        "decisions_needed": [item.campaign_id for item in decisions],
        "detours": [item.campaign_id for item in detours],
        "readiness": {
            item.campaign_id: campaign_readiness(item, campaigns) for item in ordered
        },
        "completed": [item.campaign_id for item in completed],
        "dangler_resolution": dangler_resolution,
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
    add.add_argument("--primary-focus-area", action="append")
    add.add_argument("--supporting-focus-area", action="append")
    add.add_argument("--decision", default="none")
    add.add_argument("--detour-for", default="none")
    add.add_argument("--return-to", default="none")
    add.add_argument("--position", type=int)
    for command in ("reorder", "start", "block", "unblock", "defer", "abandon", "complete"):
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
        if child.prog.split()[-1] in {"add", "reorder", "start", "block", "unblock", "defer", "abandon", "complete"}:
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
            order = queue_order(workspace)
            ordered = [campaigns[item] for item in order]
            candidate = next((item for item in ordered if item.status == "working"), None)
            if candidate is None:
                candidate = first_ready_campaign(order, campaigns)
            dangler_resolution = dangler_resolution_visibility(workspace, campaigns, order)
            if candidate is None and dangler_resolution:
                payload = dict(dangler_resolution)
            elif candidate is None:
                payload = None
            else:
                payload = {
                    "campaign_id": candidate.campaign_id,
                    "title": candidate.title,
                    "status": candidate.status,
                    "path": candidate.path.relative_to(workspace).as_posix(),
                    "source": "campaign-queue",
                }
                if dangler_resolution:
                    payload["dangler_resolution"] = dangler_resolution
        elif args.command == "completed":
            campaigns = load_all(workspace)
            completed = sorted(
                (item for item in campaigns.values() if item.status == "complete"),
                key=_completion_sort_key,
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
