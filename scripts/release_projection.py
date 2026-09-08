"""Build the privacy-safe, complete release-obligation projection."""

from __future__ import annotations

import hashlib
import json
from typing import Any


PROJECTION_CONTRACT_VERSION = 1
MAX_DISPLAY_GROUPS = 50
DOCUMENT_PREFIX = "sqlite/documents/"
DIRECT_PREFIX = "sqlite/outcome-capsules/"


class ReleaseProjectionError(RuntimeError):
    pass


def build(
    status: dict[str, Any], inventory: dict[str, Any], *, limit: int = MAX_DISPLAY_GROUPS
) -> dict[str, Any]:
    """Partition every registration before bounding the operator-facing rows."""
    if limit < 1:
        raise ReleaseProjectionError("release projection limit must be positive")

    registrations: list[dict[str, Any]] = []
    for cohort_position, cohort in enumerate(status.get("active", [])):
        stage = (
            "released"
            if cohort.get("lifecycle_state") == "released-pending-reconciliation"
            else "awaiting-work5"
        )
        cohort_key = str(cohort.get("cycle_id") or cohort_position)
        for candidate in cohort.get("candidates", []):
            origin_path = candidate.get("origin_path")
            commit = candidate.get("commit")
            origin_cycle = candidate.get("origin_cycle_id")
            if not isinstance(origin_path, str):
                raise ReleaseProjectionError("release registration has no controlled origin path")
            if not isinstance(commit, str) or len(commit) != 40 or any(
                character not in "0123456789abcdef" for character in commit
            ):
                raise ReleaseProjectionError("release registration has an invalid Git commit")
            if not isinstance(origin_cycle, str) or not origin_cycle:
                # Older test fixtures did not carry cycle IDs. The ordinal remains unique and
                # keeps their direct registrations independently auditable.
                origin_cycle = f"registration:{len(registrations)}"
            if origin_path.startswith(DOCUMENT_PREFIX):
                visible_id = origin_path.removeprefix(DOCUMENT_PREFIX)
                if not visible_id or "/" in visible_id or len(visible_id) > 64:
                    raise ReleaseProjectionError("release registration has an invalid document origin")
                origin_kind = "document"
            elif origin_path.startswith(DIRECT_PREFIX):
                visible_id = None
                origin_kind = "direct"
            else:
                raise ReleaseProjectionError("release registration has an unsupported origin kind")
            registrations.append(
                {
                    "ordinal": len(registrations),
                    "cohort": cohort_key,
                    "stage": stage,
                    "origin_kind": origin_kind,
                    "origin_cycle": origin_cycle,
                    "visible_id": visible_id,
                    "commit": commit,
                }
            )

    artifacts = {
        str(item.get("visible_id")): item
        for item in inventory.get("artifacts", [])
        if isinstance(item, dict) and item.get("visible_id")
    }
    graph = {visible_id: set() for visible_id in artifacts}
    for visible_id, artifact in artifacts.items():
        for related_id in [*artifact.get("parent_ids", []), *artifact.get("produces_ids", [])]:
            if related_id in graph:
                graph[visible_id].add(related_id)
                graph[related_id].add(visible_id)

    component_by_id: dict[str, frozenset[str]] = {}
    visited: set[str] = set()
    for visible_id in graph:
        if visible_id in visited:
            continue
        component: set[str] = set()
        pending = [visible_id]
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            pending.extend(graph[current] - visited)
        frozen = frozenset(component)
        for member in component:
            component_by_id[member] = frozen

    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    components: dict[tuple[str, str, str], frozenset[str]] = {}
    for registration in registrations:
        if registration["origin_kind"] == "direct":
            key = (registration["cohort"], registration["stage"], "direct")
        else:
            visible_id = str(registration["visible_id"])
            component = component_by_id.get(visible_id, frozenset({visible_id}))
            component_key = min(component)
            key = (registration["cohort"], registration["stage"], f"document:{component_key}")
            components[key] = component
        buckets.setdefault(key, []).append(registration)

    artifact_type_fields = {
        "idea-brief": "idea_id",
        "project-map": "map_id",
        "program-roadmap": "prm_id",
        "campaign": "campaign_id",
    }
    prefix_fields = {
        "IDEA-": "idea_id",
        "MAP-": "map_id",
        "PRM-": "prm_id",
        "CAMP-": "campaign_id",
    }
    groups: list[tuple[int, dict[str, Any], set[int]]] = []
    for key, members in buckets.items():
        latest = max(members, key=lambda item: int(item["ordinal"]))
        ordinals = {int(item["ordinal"]) for item in members}
        common = {
            "stage": key[1],
            "latest_commit": str(latest["commit"]),
            "candidate_count": len({str(item["commit"]) for item in members}),
            "registration_count": len(members),
        }
        if key[2] == "direct":
            row = {
                "group_kind": "direct-work2",
                "root_id": "DIRECT-WORK2",
                "idea_id": None,
                "map_id": None,
                "prm_id": None,
                "campaign_id": None,
                "owning_chain_count": len({str(item["origin_cycle"]) for item in members}),
                **common,
            }
        else:
            component = components[key]
            ids: dict[str, str | None] = {
                "idea_id": None,
                "map_id": None,
                "prm_id": None,
                "campaign_id": None,
            }
            for visible_id in sorted(component):
                artifact = artifacts.get(visible_id)
                field = artifact_type_fields.get(str(artifact.get("artifact_type"))) if artifact else None
                if field is None:
                    field = next(
                        (candidate for prefix, candidate in prefix_fields.items() if visible_id.startswith(prefix)),
                        None,
                    )
                if field and ids[field] is None:
                    ids[field] = visible_id
            root_id = next(
                (ids[field] for field in ("idea_id", "map_id", "prm_id", "campaign_id") if ids[field]),
                str(latest["visible_id"]),
            )
            row = {
                "group_kind": "document-chain",
                "root_id": root_id,
                **ids,
                "owning_chain_count": 1,
                **common,
            }
        groups.append((int(latest["ordinal"]), row, ordinals))

    groups.sort(key=lambda item: (item[0], str(item[1]["root_id"])), reverse=True)
    all_ordinals = set(range(len(registrations)))
    assigned = set().union(*(item[2] for item in groups)) if groups else set()
    assigned_total = sum(len(item[2]) for item in groups)
    if assigned != all_ordinals or assigned_total != len(registrations):
        raise ReleaseProjectionError("release projection is not a complete disjoint partition")

    truncated = len(groups) > limit
    if truncated:
        stage_count = len({str(item[1]["stage"]) for item in groups})
        detailed = groups[: max(0, limit - stage_count)]
        remainder = groups[len(detailed) :]
        overflow_rows = []
        for stage in sorted({str(item[1]["stage"]) for item in remainder}):
            stage_remainder = [item for item in remainder if item[1]["stage"] == stage]
            remainder_rows = [item[1] for item in stage_remainder]
            remainder_ordinals = set().union(*(item[2] for item in stage_remainder))
            latest = max(stage_remainder, key=lambda item: item[0])
            overflow_rows.append(
                {
                    "group_kind": "additional-obligations",
                    "root_id": "ADDITIONAL-OBLIGATIONS",
                    "idea_id": None,
                    "map_id": None,
                    "prm_id": None,
                    "campaign_id": None,
                    "stage": stage,
                    "latest_commit": str(latest[1]["latest_commit"]),
                    "candidate_count": len(
                        {
                            str(registration["commit"])
                            for registration in registrations
                            if int(registration["ordinal"]) in remainder_ordinals
                        }
                    ),
                    "registration_count": sum(int(item["registration_count"]) for item in remainder_rows),
                    "owning_chain_count": sum(int(item["owning_chain_count"]) for item in remainder_rows),
                }
            )
        displayed = [item[1] for item in detailed] + overflow_rows
    else:
        displayed = [item[1] for item in groups]

    registration_count = len(registrations)
    owning_chain_count = sum(int(item[1]["owning_chain_count"]) for item in groups)
    if registration_count != sum(int(item["registration_count"]) for item in displayed):
        raise ReleaseProjectionError("displayed release registration total is incomplete")
    if owning_chain_count != sum(int(item["owning_chain_count"]) for item in displayed):
        raise ReleaseProjectionError("displayed owning-chain total is incomplete")
    return {
        "projection_contract_version": PROJECTION_CONTRACT_VERSION,
        "projection_state": "complete",
        "projection_source_revision": max(0, int(status.get("revision") or 0)),
        "projection_source_digest": (
            str(status["domain_digest"])
            if isinstance(status.get("domain_digest"), str)
            and len(str(status["domain_digest"])) == 64
            else hashlib.sha256(
                json.dumps(
                    registrations, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest()
        ),
        "awaiting_work5_chain_count": sum(
            int(item[1]["owning_chain_count"])
            for item in groups
            if item[1]["stage"] == "awaiting-work5"
        ),
        "candidate_commit_count": len({str(item["commit"]) for item in registrations}),
        "registration_count": registration_count,
        "owning_chain_count": owning_chain_count,
        "display_group_count": len(displayed),
        "release_chains": displayed,
        "release_chains_truncated": truncated,
    }
