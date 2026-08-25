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

from project_identity import (
    ProjectIdentityError,
    bind_state_token,
    ensure_project_identity,
    require_project_binding,
    target_capsule,
)


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
    "Campaign Number",
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
    "Roadmap",
    "Roadmap Revision",
    "Milestone",
    "Unlocks Gate",
)
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CAMPAIGN_NUMBER_RE = re.compile(r"^[0-9]{3,}$")
NUMBERED_ID_RE = re.compile(r"^([0-9]{3,})-")
QUEUE_LINK_RE = re.compile(
    r"^\d+\. (?:\([0-9?]+\) )?(?:\*\*)?\[[^]]+\]\(active/([a-z0-9-]+)\.md\)(?:\*\*)?"
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
WORK_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\((work/[^)\s]+\.md(?:#[^)]+)?)\)")
WORK_REFERENCE_HEADER_KEYS = {
    "Parent",
    "Project Map",
    "Canonical Truth",
    "Supersedes",
    "Superseded By",
    "Source Project Map",
}
QUEUE_NUMBER_GUIDANCE = (
    "Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values "
    "are stable."
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
    def campaign_number(self) -> str:
        explicit = self.fields.get("Campaign Number", "")
        if explicit:
            return explicit
        match = NUMBERED_ID_RE.match(self.campaign_id)
        return match.group(1) if match else ""

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
        "Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.\n\n"
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


def set_campaign_header(text: str, key: str, value: str) -> str:
    lines = text.splitlines()
    prefix = f"{key}:"
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = f"{key}: {value}"
            return "\n".join(lines).rstrip() + "\n"
    after = "Campaign ID:" if key == "Campaign Number" else "Status:"
    insert_at = next(
        (index + 1 for index, line in enumerate(lines) if line.startswith(after)),
        1,
    )
    lines.insert(insert_at, f"{key}: {value}")
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
            linked_path = campaign_root(workspace) / "active" / f"{match.group(1)}.md"
            if linked_path.is_file():
                order.append(parse_campaign(linked_path).campaign_id)
            else:
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
    return bind_state_token(
        workspace,
        "campaign-queue",
        digest.hexdigest(),
        allow_unidentified=True,
    )


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


def next_campaign_number(campaigns: dict[str, Campaign]) -> str:
    used = [
        int(item.campaign_number)
        for item in campaigns.values()
        if CAMPAIGN_NUMBER_RE.fullmatch(item.campaign_number)
    ]
    return f"{max(used, default=0) + 1:03d}"


def campaign_filename(campaign_id: str, campaign_number: str) -> str:
    prefixed = NUMBERED_ID_RE.match(campaign_id)
    if prefixed and prefixed.group(1) == campaign_number:
        return f"{campaign_id}.md"
    if campaign_number:
        return f"{campaign_number}-{campaign_id}.md"
    return f"{campaign_id}.md"


def resolve_campaign_reference(
    reference: str,
    campaigns: dict[str, Campaign],
) -> str:
    if reference in campaigns:
        return reference
    if CAMPAIGN_NUMBER_RE.fullmatch(reference):
        match = next(
            (
                item.campaign_id
                for item in campaigns.values()
                if item.campaign_number == reference
            ),
            None,
        )
        if match is not None:
            return match
    raise CampaignError(f"unknown campaign: {reference}")


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
    include_campaign_numbers: bool | None = True,
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
        "Queue positions are mutable; parenthesized campaign numbers and full `Campaign ID` values are stable.",
        "",
    ]
    if not active:
        lines.append("No active campaigns.")
    for position, item in enumerate(active, start=1):
        if include_campaign_numbers is True:
            number = f"({item.campaign_number or '???'}) "
        elif include_campaign_numbers is None and item.campaign_number:
            number = f"({item.campaign_number}) "
        else:
            number = ""
        lines.append(
            f"{position}. {number}**[{item.title}](active/{item.path.name})**"
        )
        lines.append(f"   - 🆔 **CAMPAIGN ID:** `{item.campaign_id}`")
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
        if item.fields.get("Roadmap", "none") != "none":
            trace = item.fields["Roadmap"]
            if item.fields.get("Roadmap Revision", "none") != "none":
                trace += " r" + item.fields["Roadmap Revision"]
            if item.fields.get("Milestone", "none") != "none":
                trace += " / " + item.fields["Milestone"]
            if item.fields.get("Unlocks Gate", "none") != "none":
                trace += " / unlocks " + item.fields["Unlocks Gate"]
            lines.append("   - 🗺️ **ROADMAP:** " + trace)
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
            f"(completed/{item.path.name}) — {item.outcome} — evidence: {evidence}"
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
        raise CampaignError(
            f"stale campaign state or foreign-project token: expected {expected}, current {actual}"
        )


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


def validate(
    workspace: Path,
    *,
    allow_missing_campaign_numbers: bool = False,
    allow_legacy_queue: bool = False,
    allow_legacy_campaign_filenames: bool = False,
) -> list[str]:
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
    campaign_numbers: dict[int, str] = {}
    for item in campaigns.values():
        if not ID_RE.fullmatch(item.campaign_id):
            findings.append(f"invalid campaign ID: {item.campaign_id}")
        expected_filename = campaign_filename(item.campaign_id, item.campaign_number)
        if item.path.name != expected_filename and not (
            allow_legacy_campaign_filenames
            and item.path.name == f"{item.campaign_id}.md"
        ):
            findings.append(
                f"campaign filename does not match number and ID: {item.path.name}; "
                f"expected {expected_filename}"
            )
        explicit_number = item.fields.get("Campaign Number", "")
        prefixed_number = NUMBERED_ID_RE.match(item.campaign_id)
        if explicit_number and not CAMPAIGN_NUMBER_RE.fullmatch(explicit_number):
            findings.append(f"{item.campaign_id} has invalid Campaign Number")
        elif not item.campaign_number:
            if not allow_missing_campaign_numbers:
                findings.append(f"{item.campaign_id} is missing Campaign Number")
        else:
            number = int(item.campaign_number)
            if number < 1:
                findings.append(f"{item.campaign_id} has invalid Campaign Number")
            elif number in campaign_numbers:
                findings.append(
                    f"duplicate Campaign Number {item.campaign_number}: "
                    f"{campaign_numbers[number]}, {item.campaign_id}"
                )
            else:
                campaign_numbers[number] = item.campaign_id
        if (
            explicit_number
            and prefixed_number
            and explicit_number != prefixed_number.group(1)
        ):
            findings.append(
                f"{item.campaign_id} Campaign Number conflicts with its ID prefix"
            )
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

    actual_active = without_updated(active_path.read_text(encoding="utf-8"))
    expected_active = without_updated(render_active_queue(order, campaigns, catalog))
    legacy_active = without_updated(
        render_active_queue(
            order, campaigns, catalog, include_campaign_numbers=None
        )
    )
    older_legacy_active = legacy_active.replace(
        QUEUE_NUMBER_GUIDANCE,
        "Queue positions are mutable; each card's `Campaign ID` is stable.",
    )
    legacy_queue_variants = {legacy_active, older_legacy_active}
    if not order:
        legacy_queue_variants.add(legacy_active.replace(QUEUE_NUMBER_GUIDANCE + "\n\n", ""))
    if actual_active != expected_active and not (
        allow_legacy_queue
        and actual_active in legacy_queue_variants
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
    campaign_number: str | None = None,
) -> str:
    fields = {
        "Status": "queued",
        "Type": "campaign",
        "Updated": date.today().isoformat(),
        "Next Action": "execute when selected from the active campaign queue",
        "Campaign ID": campaign_id,
        "Campaign Number": campaign_number or "",
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
    prefixed_number = NUMBERED_ID_RE.match(args.campaign_id)
    campaign_number = (
        prefixed_number.group(1) if prefixed_number else next_campaign_number(campaigns)
    )
    path = (
        campaign_root(workspace)
        / "active"
        / campaign_filename(args.campaign_id, campaign_number)
    )
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
        campaign_number,
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


def _rewrite_work_references(
    text: str,
    replacements: dict[str, str],
) -> tuple[str, list[dict[str, str]]]:
    used: set[tuple[str, str]] = set()

    def replace_target(target: str) -> str:
        base, separator, anchor = target.partition("#")
        replacement = replacements.get(base)
        if replacement is None:
            return target
        used.add((base, replacement))
        return replacement + (separator + anchor if separator else "")

    def replace_link(match: re.Match[str]) -> str:
        target = match.group(1)
        replacement = replace_target(target)
        return match.group(0).replace(target, replacement, 1)

    rewritten: list[str] = []
    for line in text.splitlines(keepends=True):
        line = WORK_MARKDOWN_LINK_RE.sub(replace_link, line)
        if ":" in line:
            key, raw_value = line.split(":", 1)
            if key.strip() in WORK_REFERENCE_HEADER_KEYS:
                match = re.match(r"(\s*)(work/[^\s]+\.md(?:#[^\s]+)?)(.*)", raw_value)
                if match is not None:
                    target = match.group(2)
                    replacement = replace_target(target)
                    if replacement != target:
                        line = key + ":" + match.group(1) + replacement + match.group(3)
        rewritten.append(line)
    return "".join(rewritten), [
        {"from": source, "to": destination}
        for source, destination in sorted(used)
    ]


def _backfill_plan(
    workspace: Path,
) -> tuple[dict[Path, str | None], dict[str, object]]:
    findings = validate(
        workspace,
        allow_missing_campaign_numbers=True,
        allow_legacy_queue=True,
        allow_legacy_campaign_filenames=True,
    )
    if findings:
        raise CampaignError("campaign state is invalid: " + "; ".join(findings))
    campaigns = load_all(workspace)
    order = queue_order(workspace)
    used = {
        int(item.campaign_number)
        for item in campaigns.values()
        if CAMPAIGN_NUMBER_RE.fullmatch(item.campaign_number)
    }
    active_positions = {campaign_id: index for index, campaign_id in enumerate(order)}

    def migration_key(item: Campaign) -> tuple[int, int, str, str]:
        completion_order = _completion_order(item)
        if item.path.parent.name == "completed":
            return (
                0,
                completion_order,
                item.fields.get("Completion Date", ""),
                item.campaign_id,
            )
        if item.path.parent.name in {"deferred", "abandoned"}:
            folder_rank = 1 if item.path.parent.name == "deferred" else 2
            return (folder_rank, 0, item.fields.get("Updated", ""), item.campaign_id)
        if item.campaign_id in active_positions:
            return (3, active_positions[item.campaign_id], "", item.campaign_id)
        return (4, 0, item.fields.get("Updated", ""), item.campaign_id)

    changes: dict[Path, str | None] = {}
    changed_ids: set[str] = set()
    migrated_text: dict[str, str] = {
        item.campaign_id: item.body for item in campaigns.values()
    }
    candidate = 1
    for item in sorted(
        (entry for entry in campaigns.values() if not entry.campaign_number),
        key=migration_key,
    ):
        while candidate in used:
            candidate += 1
        item.fields["Campaign Number"] = f"{candidate:03d}"
        migrated_text[item.campaign_id] = set_campaign_header(
            migrated_text[item.campaign_id],
            "Campaign Number",
            item.fields["Campaign Number"],
        )
        used.add(candidate)
        candidate += 1
        changed_ids.add(item.campaign_id)
    original_paths = {item.campaign_id: item.path for item in campaigns.values()}
    renames: list[dict[str, str]] = []
    replacements: dict[str, str] = {}
    for item in campaigns.values():
        old_path = item.path
        new_path = old_path.parent / campaign_filename(
            item.campaign_id, item.campaign_number
        )
        if old_path != new_path:
            if new_path.exists():
                raise CampaignError(
                    "campaign filename migration target already exists: "
                    + new_path.relative_to(workspace).as_posix()
                )
            old_relative = old_path.relative_to(workspace).as_posix()
            new_relative = new_path.relative_to(workspace).as_posix()
            renames.append(
                {"campaign_id": item.campaign_id, "from": old_relative, "to": new_relative}
            )
            replacements[old_relative] = new_relative
            item.path = new_path
            changed_ids.add(item.campaign_id)
        if item.campaign_id in changed_ids:
            item.fields["Updated"] = date.today().isoformat()
            migrated_text[item.campaign_id] = set_campaign_header(
                migrated_text[item.campaign_id], "Updated", item.fields["Updated"]
            )
    try:
        from check_stale_paths import iter_markdown_files

        markdown_paths = iter_markdown_files(workspace)
    except ImportError:
        markdown_paths = sorted(workspace.rglob("*.md"))
    skipped = {
        "work/index.md",
        "work/00-campaigns/active-queue.md",
        "work/00-campaigns/completed-queue.md",
    }
    campaign_by_original = {
        original_paths[item.campaign_id]: item for item in campaigns.values()
    }
    reference_updates: list[dict[str, object]] = []
    seen_campaign_paths: set[Path] = set()
    for path in markdown_paths:
        relative = path.relative_to(workspace).as_posix()
        if (
            relative in skipped
            or relative.startswith("work/evidence/generated/")
            or not path.is_file()
        ):
            continue
        campaign = campaign_by_original.get(path)
        source_text = (
            migrated_text[campaign.campaign_id]
            if campaign is not None
            else path.read_text(encoding="utf-8")
        )
        rewritten, applied = _rewrite_work_references(source_text, replacements)
        if applied:
            reference_updates.append({"path": relative, "replacements": applied})
        if campaign is not None:
            seen_campaign_paths.add(path)
            if path != campaign.path:
                changes[path] = None
            if path != campaign.path or rewritten != path.read_text(encoding="utf-8"):
                changes[campaign.path] = rewritten
        elif rewritten != source_text:
            changes[path] = rewritten
    for item in campaigns.values():
        original = original_paths[item.campaign_id]
        if original in seen_campaign_paths:
            continue
        rewritten, applied = _rewrite_work_references(
            migrated_text[item.campaign_id], replacements
        )
        if applied:
            reference_updates.append(
                {
                    "path": original.relative_to(workspace).as_posix(),
                    "replacements": applied,
                }
            )
        if original != item.path:
            changes[original] = None
        if original != item.path or rewritten != original.read_text(encoding="utf-8"):
            changes[item.path] = rewritten
    for path, content in _refresh_changes(workspace, order, campaigns).items():
        if not path.exists() or content != path.read_text(encoding="utf-8"):
            changes[path] = content
    mutation_paths = sorted(
        {
            str(update["path"])
            for update in reference_updates
            if not str(update["path"]).startswith("work/00-campaigns/")
        }
    )
    payload: dict[str, object] = {
        "state_token": state_token(workspace),
        "needed": bool(changes),
        "renames": sorted(renames, key=lambda item: item["campaign_id"]),
        "reference_updates": sorted(reference_updates, key=lambda item: str(item["path"])),
        "mutation_paths": mutation_paths,
        "write_paths": sorted(path.relative_to(workspace).as_posix() for path in changes),
    }
    return changes, payload


def backfill_campaign_numbers(args: argparse.Namespace, workspace: Path) -> None:
    require_token(workspace, args.expect)
    changes, _ = _backfill_plan(workspace)
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
    campaign_id = resolve_campaign_reference(args.campaign_id, campaigns)
    item = campaigns[campaign_id]
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


def cycle_state_payload(
    workspace: Path,
    campaigns: dict[str, Campaign],
    order: list[str],
    dangler_resolution: dict[str, object] | None,
) -> dict[str, object]:
    # Import lazily because Program Roadmaps build on queue lifecycle primitives in this module.
    import program_roadmap

    return program_roadmap.cycle_state_capsule(
        workspace,
        campaigns=campaigns,
        order=order,
        dangler_resolution=dangler_resolution,
    )


def _selector_values(values: list[str]) -> list[str]:
    result = [
        item.strip()
        for value in values
        for item in value.split(",")
        if item.strip()
    ]
    if not result:
        raise CampaignError("next selection is empty")
    return result


def targeted_next_payload(
    workspace: Path,
    selection: list[str],
) -> dict[str, object]:
    campaigns = load_all(workspace)
    order = queue_order(workspace)
    findings = validate(workspace)
    if findings:
        raise CampaignError(
            "campaign queue validation failed: " + "; ".join(findings)
        )
    state = state_token(workspace)
    raw = list(selection)
    normalized = [value.lower() for value in raw]
    if "*" in raw:
        if raw != ["*"]:
            raise CampaignError("wildcard next selection cannot be combined with other targets")
        mode = "wildcard"
        target_ids = list(order)
    else:
        prefix = normalized[0]
        if prefix in {"que", "queue", "queues"}:
            mode = "queue-positions"
            values = _selector_values(raw[1:])
        elif prefix in {"camp", "camps", "campaign", "campaigns"}:
            mode = "campaign-references"
            values = _selector_values(raw[1:])
        else:
            values = _selector_values(raw)
            mode = (
                "queue-positions-shorthand"
                if all(value.isdigit() for value in values)
                else "campaign-references-shorthand"
            )
        if mode.startswith("queue-positions"):
            positions: list[int] = []
            for value in values:
                if not value.isdigit() or int(value) < 1:
                    raise CampaignError(f"invalid queue position: {value}")
                position = int(value)
                if position > len(order):
                    raise CampaignError(f"queue position is outside the active queue: {value}")
                positions.append(position)
            if len(positions) != len(set(positions)):
                raise CampaignError("next selection repeats a queue position")
            target_ids = [order[position - 1] for position in positions]
        else:
            target_ids = []
            for value in values:
                campaign_id = resolve_campaign_reference(value, campaigns)
                if campaign_id not in order:
                    raise CampaignError(f"next selection is not active: {value}")
                target_ids.append(campaign_id)
    if len(target_ids) != len(set(target_ids)):
        raise CampaignError("next selection resolves to duplicate campaigns")

    working = next(
        (campaign_id for campaign_id in order if campaigns[campaign_id].status == "working"),
        None,
    )
    adjustment = None
    working_stop = None
    if working is not None:
        if working not in target_ids:
            working_stop = f"working campaign is outside the selection: {working}"
        elif target_ids and target_ids[0] != working:
            target_ids.remove(working)
            target_ids.insert(0, working)
            adjustment = f"moved working campaign {working} to the front"

    completed = {
        campaign_id
        for campaign_id, item in campaigns.items()
        if item.status == "complete"
    }
    simulated_completed = set(completed)
    targets: list[dict[str, object]] = []
    for campaign_id in target_ids:
        item = campaigns[campaign_id]
        incomplete = [
            dependency
            for dependency in item.dependencies
            if dependency not in simulated_completed
        ]
        target_stop = None
        if item.status == "blocked" or item.fields.get("Decision", "none") != "none":
            target_stop = "campaign is blocked or needs a decision"
        elif incomplete:
            target_stop = "incomplete dependencies are not completed earlier in the batch: " + ", ".join(incomplete)
        targets.append(
            {
                "queue_position": order.index(campaign_id) + 1,
                "campaign_id": campaign_id,
                "campaign_number": item.campaign_number,
                "title": item.title,
                "path": item.path.relative_to(workspace).as_posix(),
                "status": item.status,
                "readiness": campaign_readiness(item, campaigns),
                "depends_on": item.dependencies,
                "planned_stop": target_stop,
            }
        )
        if target_stop is None:
            simulated_completed.add(campaign_id)
    first_planned_stop = next(
        (
            {
                "target_index": index,
                "campaign_id": target["campaign_id"],
                "reason": target["planned_stop"],
                "remaining_target_ids": target_ids[index - 1 :],
            }
            for index, target in enumerate(targets, start=1)
            if target["planned_stop"] is not None
        ),
        None,
    )
    if working_stop is not None:
        executable = False
        stop_reason = working_stop
    elif not targets:
        executable = False
        stop_reason = "active queue snapshot has no targets"
    elif first_planned_stop is not None and first_planned_stop["target_index"] == 1:
        executable = False
        stop_reason = (
            f"{first_planned_stop['campaign_id']}: {first_planned_stop['reason']}"
        )
    else:
        executable = True
        stop_reason = None
    digest = hashlib.sha256()
    digest.update(state.encode("ascii"))
    for campaign_id in target_ids:
        digest.update(b"\0")
        digest.update(campaign_id.encode("utf-8"))
    dangler_resolution = dangler_resolution_visibility(workspace, campaigns, order)
    payload: dict[str, object] = {
        "source": "campaign-queue-batch",
        "selection_mode": mode,
        "selection": raw,
        "snapshot_state_token": state,
        "batch_token": digest.hexdigest()[:16],
        "target_ids": target_ids,
        "targets": targets,
        "target_count": len(target_ids),
        "working_campaign": working,
        "selection_adjustment": adjustment,
        "executable": executable,
        "stop_reason": stop_reason,
        "planned_stop": first_planned_stop,
        "remaining_target_ids": list(target_ids),
        "execution": "sequential; refresh and validate state after every campaign completion",
        "stop_conditions": [
            "failed completion gate",
            "blocked campaign or unresolved decision",
            "stale queue state or changed target",
            "unsatisfied dependency",
            "protected, destructive, external, credential, deployment, or release action without authority",
        ],
        "authority": (
            "Batch selection defines execution scope only; it does not authorize work5, deployment, "
            "release, production promotion, destructive work, credentials, or other consequential "
            "external actions."
        ),
    }
    if dangler_resolution:
        payload["dangler_resolution"] = dangler_resolution
    payload["cycle_state"] = cycle_state_payload(
        workspace, campaigns, order, dangler_resolution
    )
    return payload


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
    payload: dict[str, object] = {
        "project": target_capsule(workspace, operation="campaign-queue"),
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
        "campaign_numbers": {
            item.campaign_number: item.campaign_id
            for item in sorted(
                campaigns.values(),
                key=lambda entry: (
                    not bool(entry.campaign_number),
                    int(entry.campaign_number) if entry.campaign_number else 0,
                ),
            )
            if item.campaign_number
        },
        "completed": [item.campaign_id for item in completed],
        "dangler_resolution": dangler_resolution,
        "findings": validate(workspace),
    }
    payload["cycle_state"] = cycle_state_payload(
        workspace, campaigns, order, dangler_resolution
    )
    return payload


def render_status_human(payload: dict[str, object]) -> str:
    import program_roadmap

    lines = [
        f"Campaign state token: {payload['state_token']}",
        "Working: " + (", ".join(payload["working"]) if payload["working"] else "none"),
        f"Next: {payload['next'] or 'none'}",
        "Blocked: " + (", ".join(payload["blocked"]) if payload["blocked"] else "none"),
        program_roadmap.render_cycle_state(payload["cycle_state"]),
    ]
    findings = payload.get("findings", [])
    if findings:
        lines.append("Findings: " + "; ".join(str(item) for item in findings))
    return "\n".join(lines)


def render_next_human(payload: dict[str, object]) -> str:
    import program_roadmap

    campaign_id = payload.get("campaign_id")
    if campaign_id is None:
        target_ids = payload.get("target_ids", [])
        if isinstance(target_ids, list) and target_ids:
            campaign_id = ", ".join(str(item) for item in target_ids)
    lines = [
        f"Selected campaign: {campaign_id or 'none'}",
        program_roadmap.render_cycle_state(payload["cycle_state"]),
    ]
    return "\n".join(lines)


def next_campaign_payload(workspace: Path) -> dict[str, object]:
    """Return the ordinary single-campaign `next` selection without mutation."""

    campaigns = load_all(workspace)
    order = queue_order(workspace)
    ordered = [campaigns[item] for item in order]
    candidate = next((item for item in ordered if item.status == "working"), None)
    if candidate is None:
        candidate = first_ready_campaign(order, campaigns)
    dangler_resolution = dangler_resolution_visibility(workspace, campaigns, order)
    if candidate is None and dangler_resolution:
        payload = dict(dangler_resolution)
        payload["cycle_state"] = cycle_state_payload(
            workspace, campaigns, order, dangler_resolution
        )
        return payload
    if candidate is None:
        return {
            "campaign_id": None,
            "campaign_number": None,
            "title": None,
            "status": None,
            "path": None,
            "source": "cycle-state",
            "cycle_state": cycle_state_payload(workspace, campaigns, order, None),
        }
    payload = {
        "campaign_id": candidate.campaign_id,
        "campaign_number": candidate.campaign_number,
        "title": candidate.title,
        "status": candidate.status,
        "path": candidate.path.relative_to(workspace).as_posix(),
        "source": "campaign-queue",
        "cycle_state": cycle_state_payload(
            workspace, campaigns, order, dangler_resolution
        ),
    }
    if dangler_resolution:
        payload["dangler_resolution"] = dangler_resolution
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Tool Shed owner-facing campaign queues.")
    parser.add_argument("--workspace", default=".", help="Project workspace root.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init")
    subparsers.add_parser("status")
    next_command = subparsers.add_parser(
        "next",
        help="select one campaign or resolve an explicit sequential batch",
    )
    next_command.add_argument(
        "selection",
        nargs="*",
        metavar="SELECTION",
        help="queue positions (1,2 or que 1,2), campaign references (camp 025,id), or *",
    )
    subparsers.add_parser("completed")
    subparsers.add_parser("validate")
    subparsers.add_parser("migrate-preview")
    subparsers.add_parser("backfill-plan")
    subparsers.add_parser("backfill-numbers")
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
        if child.prog.split()[-1] in {"add", "backfill-numbers", "reorder", "start", "block", "unblock", "defer", "abandon", "complete"}:
            child.add_argument("--expect", required=True)
            child.add_argument("--project-binding", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    try:
        root = campaign_root(workspace)
        if args.command == "init":
            ensure_project_identity(workspace)
            ensure_tree(workspace)
        elif not root.is_dir():
            raise CampaignError("campaign tree is not initialized; run init or the Tool Shed workspace installer")
        recovered = recover_if_needed(workspace)
        mutation_commands = {
            "add", "backfill-numbers", "reorder", "start", "block", "unblock",
            "defer", "abandon", "complete",
        }
        if args.command in mutation_commands:
            require_project_binding(
                workspace,
                args.project_binding,
                operation="campaign-queue",
            )
        if args.command == "init":
            payload: object = {"root": str(campaign_root(workspace)), "state_token": state_token(workspace), "recovered": recovered}
        elif args.command == "status":
            payload = status_payload(workspace)
        elif args.command == "validate":
            findings = validate(workspace)
            payload = {"valid": not findings, "findings": findings, "state_token": state_token(workspace)}
        elif args.command == "next":
            if args.selection:
                payload = targeted_next_payload(workspace, args.selection)
            else:
                payload = next_campaign_payload(workspace)
        elif args.command == "completed":
            campaigns = load_all(workspace)
            completed = sorted(
                (item for item in campaigns.values() if item.status == "complete"),
                key=_completion_sort_key,
                reverse=True,
            )
            payload = [{"campaign_id": item.campaign_id, "campaign_number": item.campaign_number, "title": item.title, "completed": item.fields.get("Completion Date"), "evidence": item.fields.get("Completion Evidence")} for item in completed]
        elif args.command == "migrate-preview":
            payload = migration_preview(workspace)
        elif args.command == "backfill-plan":
            _, payload = _backfill_plan(workspace)
        elif args.command == "add":
            add_campaign(args, workspace)
            payload = status_payload(workspace)
        elif args.command == "backfill-numbers":
            backfill_campaign_numbers(args, workspace)
            payload = status_payload(workspace)
        else:
            mutate_campaign(args, workspace)
            payload = status_payload(workspace)
    except (CampaignError, ProjectIdentityError, OSError, json.JSONDecodeError) as error:
        print(f"Campaign operation failed: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.command == "status" and isinstance(payload, dict):
        print(render_status_human(payload))
    elif args.command == "next" and isinstance(payload, dict):
        print(render_next_human(payload))
    else:
        if isinstance(payload, dict) and "state_token" in payload:
            print(f"Campaign state token: {payload['state_token']}")
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
