from __future__ import annotations

from collections import defaultdict
from typing import Iterable


TERMINAL_DOCUMENT_STATES = {"completed", "abandoned", "superseded", "terminal"}
TERMINAL_OUTCOME_DISPOSITIONS = {
    "satisfied",
    "satisfied-with-approved-change",
    "not-applicable",
    "superseded",
    "parked",
    "rejected",
    "failed",
    "administratively-reconciled",
    "not-satisfied",
}
ACTIVE_DOCUMENT_STATES = {
    "active",
    "blocked",
    "exploring",
    "promoted",
    "queued",
    "ready",
    "ready-for-prm",
    "waiting",
    "working",
}
ACTIVE_OUTCOME_STATES = {"blocked", "frozen", "working"}
READINESS_RANK = {"working": 0, "ready": 1, "active": 1, "waiting": 2, "blocked": 3, "terminal": 4}
TYPE_RANK = {"idea-brief": 0, "project-map": 1, "program-roadmap": 2, "campaign": 3}


def is_remaining(item: object) -> bool:
    """Return true only when the report carries an explicit unfinished obligation."""
    release = getattr(item, "release_chain", None) or {}
    if release.get("stage") in {"awaiting-work5", "released"}:
        return True

    document_lifecycle = str(getattr(item, "document_lifecycle", "unknown"))
    outcome_lifecycle = str(getattr(item, "outcome_lifecycle", "unknown"))
    outcome_disposition = str(getattr(item, "outcome_disposition", "unknown"))
    reconciliation = str(getattr(item, "reconciliation_state", "unknown"))
    closure = getattr(item, "closure_status", None) or {}
    counts = closure.get("counts") if isinstance(closure.get("counts"), dict) else {}
    closure_debt = any(
        int(counts.get(key) or 0) > 0
        for key in ("open", "invalid")
    )
    return (
        document_lifecycle in ACTIVE_DOCUMENT_STATES
        or outcome_lifecycle in ACTIVE_OUTCOME_STATES
        or outcome_disposition == "open"
        or reconciliation == "open"
        or closure_debt
    )


def _is_blocked(item: object) -> bool:
    states = {
        str(getattr(item, "document_lifecycle", "")),
        str(getattr(item, "outcome_lifecycle", "")),
        str(getattr(item, "planning_readiness", "")),
    }
    findings = getattr(item, "local_findings", []) or []
    return "blocked" in states or any(
        finding.severity == "blocked" or finding.reason_code == "OUTCOME_BLOCKED"
        for finding in findings
    )


def matches_scope(item: object, scope: str) -> bool:
    if scope == "all":
        return True
    if scope == "remaining":
        return is_remaining(item)
    if scope == "working":
        return "working" in {
            str(getattr(item, "document_lifecycle", "")),
            str(getattr(item, "outcome_lifecycle", "")),
            str(getattr(item, "planning_readiness", "")),
        }
    if scope == "blocked":
        return _is_blocked(item)
    if scope == "awaiting-work5":
        return (getattr(item, "release_chain", None) or {}).get("stage") == "awaiting-work5"
    return False


def command_actions(item: object) -> list[dict[str, str]]:
    """Build commands only from product-defined templates and stable public IDs."""
    visible_id = str(getattr(item, "visible_id", ""))
    artifact_type = str(getattr(item, "artifact_type", ""))
    actions = [
        {
            "label": "Review project status",
            "description": "Show current queues, outcomes, release work, and blockers.",
            "command": "ts: status",
            "feedback": "Status command copied",
        }
    ]
    if (
        artifact_type == "campaign"
        and visible_id.startswith("CAMP-")
        and is_remaining(item)
        and str(getattr(item, "document_lifecycle", "")) not in TERMINAL_DOCUMENT_STATES
        and str(getattr(item, "outcome_disposition", "")) not in TERMINAL_OUTCOME_DISPOSITIONS
    ):
        number = visible_id.removeprefix("CAMP-")
        actions.insert(
            0,
            {
                "label": "Continue this campaign",
                "description": "Resume this exact campaign at its configured work endpoint.",
                "command": f"ts: next camp {number}",
                "feedback": "Continue campaign command copied",
            },
        )
        if _is_blocked(item):
            actions.insert(
                1,
                {
                    "label": "Return it to the queue",
                    "description": "Clear a valid blocker without starting execution.",
                    "command": f"ts: unblock {visible_id}",
                    "feedback": "Unblock campaign command copied",
                },
            )
    elif artifact_type == "idea-brief" and visible_id.startswith("IDEA-") and not getattr(item, "produces_ids", []):
        actions.insert(
            0,
            {
                "label": "Carry this Idea into planning",
                "description": "Review readiness and create the approved PRM chain if appropriate.",
                "command": f"ts: prm idea {visible_id}",
                "feedback": "Idea planning command copied",
            },
        )
    for finding in getattr(item, "local_findings", []) or []:
        command = str(getattr(finding, "command", ""))
        if command.startswith("ts: resolve loop LOOP-"):
            actions.append(
                {
                    "label": "Resolve this loop finding",
                    "description": "Recheck current local authority and apply the finding's bounded recovery route.",
                    "command": command,
                    "feedback": "Loop resolution command copied",
                }
            )
    return actions


def _sort_key(item: object) -> tuple[object, ...]:
    position = getattr(item, "planning_position", None)
    readiness = str(getattr(item, "planning_readiness", ""))
    if readiness == "not-applicable":
        readiness = str(getattr(item, "document_lifecycle", "active"))
    return (
        position is None,
        position if position is not None else 1_000_000,
        READINESS_RANK.get(readiness, 2),
        TYPE_RANK.get(str(getattr(item, "artifact_type", "")), 9),
        str(getattr(item, "visible_id", "")),
    )


def _executable(item: object) -> bool:
    if not is_remaining(item) or _is_blocked(item):
        return False
    readiness = str(getattr(item, "planning_readiness", ""))
    lifecycle = str(getattr(item, "document_lifecycle", ""))
    return readiness not in {"waiting", "terminal"} and lifecycle not in {
        "deferred",
        "parked",
        "completed",
        "abandoned",
        "superseded",
        "terminal",
    }


def build_tree(
    items: Iterable[object],
    *,
    scope: str,
    artifact_type: str = "",
    status: str = "",
    release_stage: str = "",
) -> dict[str, object]:
    rows = list(items)
    by_visible: dict[str, object] = {}
    duplicate_ids: set[str] = set()
    for item in rows:
        visible_id = str(getattr(item, "visible_id", ""))
        if visible_id in by_visible:
            duplicate_ids.add(visible_id)
        else:
            by_visible[visible_id] = item

    invalid: set[str] = set(duplicate_ids)
    parent_by_id: dict[str, str | None] = {}
    placement_reason: dict[str, str] = {value: "duplicate visible ID" for value in duplicate_ids}
    for visible_id, item in by_visible.items():
        parents = list(dict.fromkeys(str(value) for value in (getattr(item, "parent_ids", []) or [])))
        if not parents:
            parent_by_id[visible_id] = None
        elif len(parents) > 1:
            invalid.add(visible_id)
            placement_reason[visible_id] = "multiple owning parents"
        elif parents[0] == visible_id:
            invalid.add(visible_id)
            placement_reason[visible_id] = "self-parent relationship"
        elif parents[0] not in by_visible:
            invalid.add(visible_id)
            placement_reason[visible_id] = f"missing parent {parents[0]}"
        else:
            parent_by_id[visible_id] = parents[0]

    for start in list(parent_by_id):
        path: list[str] = []
        positions: dict[str, int] = {}
        current: str | None = start
        while current is not None and current not in invalid:
            if current in positions:
                for cycle_id in path[positions[current] :]:
                    invalid.add(cycle_id)
                    placement_reason[cycle_id] = "cyclic parent relationship"
                break
            positions[current] = len(path)
            path.append(current)
            current = parent_by_id.get(current)
        if current in invalid:
            for child_id in path:
                invalid.add(child_id)
                placement_reason.setdefault(child_id, "ancestor has invalid placement")

    children: dict[str, list[object]] = defaultdict(list)
    roots: list[object] = []
    for visible_id, item in by_visible.items():
        if visible_id in invalid:
            continue
        parent = parent_by_id.get(visible_id)
        if parent is None:
            roots.append(item)
        else:
            children[parent].append(item)
    roots.sort(key=_sort_key)
    for values in children.values():
        values.sort(key=_sort_key)

    def matches(item: object) -> bool:
        if not matches_scope(item, scope):
            return False
        if artifact_type and getattr(item, "artifact_type", "") != artifact_type:
            return False
        if status and status not in {
            str(getattr(item, "document_lifecycle", "")),
            str(getattr(item, "outcome_lifecycle", "")),
            str(getattr(item, "outcome_disposition", "")),
            str(getattr(item, "reconciliation_state", "")),
        }:
            return False
        if release_stage and (getattr(item, "release_chain", None) or {}).get("stage") != release_stage:
            return False
        return True

    matching = {visible_id for visible_id, item in by_visible.items() if matches(item)}
    included = set(matching)
    for visible_id in list(matching - invalid):
        parent = parent_by_id.get(visible_id)
        while parent is not None and parent not in invalid:
            included.add(parent)
            parent = parent_by_id.get(parent)

    flattened: list[object] = []
    root_groups: list[dict[str, object]] = []

    def append_branch(item: object, depth: int, root_id: str) -> None:
        visible_id = str(getattr(item, "visible_id"))
        if visible_id not in included:
            return
        selected_children = [child for child in children.get(visible_id, []) if str(child.visible_id) in included]
        item.tree_depth = depth
        item.tree_parent_id = parent_by_id.get(visible_id) or ""
        item.tree_root_id = root_id
        item.tree_has_children = bool(selected_children)
        item.tree_context = visible_id not in matching
        item.tree_placement_reason = ""
        item.tree_actions = command_actions(item)
        item.tree_next = False
        flattened.append(item)
        for child in selected_children:
            append_branch(child, depth + 1, root_id)

    for root in roots:
        visible_id = str(root.visible_id)
        if visible_id not in included:
            continue
        before = len(flattened)
        append_branch(root, 0, visible_id)
        root_groups.append({"id": visible_id, "rows": flattened[before:], "needs_placement": False})

    placement_rows = sorted(
        (by_visible[visible_id] for visible_id in matching & invalid if visible_id in by_visible),
        key=_sort_key,
    )
    if placement_rows:
        for item in placement_rows:
            item.tree_depth = 0
            item.tree_parent_id = ""
            item.tree_root_id = "needs-placement"
            item.tree_has_children = False
            item.tree_context = False
            item.tree_placement_reason = placement_reason.get(str(item.visible_id), "invalid placement")
            item.tree_actions = command_actions(item)
            item.tree_next = False
        flattened.extend(placement_rows)
        root_groups.append({"id": "needs-placement", "rows": placement_rows, "needs_placement": True})

    traversal = {str(item.visible_id): index for index, item in enumerate(flattened)}
    candidates = [
        item
        for item in flattened
        if str(item.visible_id) in matching
        and not getattr(item, "tree_placement_reason", "")
        and _executable(item)
    ]
    if scope == "remaining" and candidates:
        candidates.sort(
            key=lambda item: (
                0 if getattr(item, "artifact_type", "") == "campaign" else 1,
                READINESS_RANK.get(str(getattr(item, "planning_readiness", "")), 2),
                traversal[str(item.visible_id)],
            )
        )
        candidates[0].tree_next = True

    return {
        "rows": flattened,
        "root_groups": root_groups,
        "match_count": len(matching),
        "root_count": len(root_groups),
        "placement_count": len(placement_rows),
    }
