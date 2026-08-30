from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any


class ContractError(ValueError):
    pass


ROOT_FIELDS = {
    "schema_version",
    "idempotency_key",
    "project",
    "instance",
    "sequence",
    "observed_at",
    "state",
    "material_events",
    "app_server",
    "work_efficiency",
    "work_inventory",
    "lifecycle_events",
    "instance_health",
}
PROJECT_FIELDS = {"id", "name"}
INSTANCE_FIELDS = {"id", "platform", "client_version", "counter_epoch", "quiescent"}
STATE_FIELDS = {
    "working_count",
    "ready_count",
    "blocked_count",
    "active_idea_count",
    "open_outcome_count",
    "unreconciled_outcome_count",
    "last_completed_id",
}
EVENT_FIELDS = {"kind", "summary_code", "occurred_at"}
APP_SERVER_FIELDS = {
    "enabled",
    "availability_state",
    "attempts",
    "failures",
    "fallbacks",
    "last_success",
    "last_failure",
    "client_version",
    "failure_groups",
}
FAILURE_FIELDS = {"signature", "category", "count", "first_seen", "last_seen"}
EFFICIENCY_FIELDS = {
    "window_start",
    "window_end",
    "remedial_tokens_actual",
    "remedial_token_coverage",
    "remedial_interactions",
    "remedial_output_bytes",
    "remedial_duration_ms",
    "remedial_retries",
}
WORK_INVENTORY_FIELDS = {"total_count", "truncated", "artifacts"}
WORK_ARTIFACT_FIELDS = {
    "artifact_id",
    "visible_id",
    "artifact_type",
    "title",
    "document_lifecycle",
    "outcome_lifecycle",
    "outcome_disposition",
    "reconciliation_state",
    "parent_ids",
    "produces_ids",
    "planning_position",
    "planning_order_source",
    "planning_readiness",
    "updated_at",
}
LIFECYCLE_EVENT_FIELDS = {
    "event_key",
    "artifact_id",
    "visible_id",
    "artifact_type",
    "title",
    "transition",
    "from_state",
    "to_state",
    "occurred_at",
}
INSTANCE_HEALTH_FIELDS = {
    "reporter_state",
    "pending_event_count",
    "last_delivery_at",
    "semantic_digest",
    "release",
}
RELEASE_FIELDS = {
    "installed_version",
    "stable_version",
    "stable_source",
    "candidate_version",
    "pending_candidate_count",
    "production_version",
    "production_source",
    "observed_at",
    "compatibility_state",
    "qualification_state",
}
RELEASE_FIELDS_V5 = RELEASE_FIELDS | {
    "awaiting_work5_chain_count",
    "candidate_commit_count",
    "registration_count",
    "release_chains",
    "release_chains_truncated",
}
RELEASE_CHAIN_FIELDS = {
    "root_id",
    "idea_id",
    "map_id",
    "prm_id",
    "campaign_id",
    "stage",
    "latest_commit",
    "candidate_count",
}
EVENT_KINDS = {"state-change", "outcome-change", "campaign-change", "client-change"}
ATTENTION_STATES = {"healthy", "working", "attention", "blocked", "stale", "unknown"}
AVAILABILITY_STATES = {"available", "unavailable", "unqualified", "disabled", "unknown"}
FAILURE_CATEGORIES = {
    "startup",
    "authentication",
    "model",
    "transport",
    "qualification",
    "budget",
    "unsafe-boundary",
    "unknown",
}
SUMMARY_CODES = {
    "managed-document-update",
    "managed-update",
    "safety-convergence",
    "quiescent",
    "client-connected",
    "client-disconnected",
    "campaign-started",
    "campaign-completed",
    "outcome-reconciled",
}
ARTIFACT_TYPES = {"idea-brief", "project-map", "program-roadmap", "campaign"}
DOCUMENT_LIFECYCLES = {"active", "working", "blocked", "parked", "deferred", "completed", "abandoned", "superseded"}
OUTCOME_LIFECYCLES = {"proposed", "queued", "working", "blocked", "terminal", "unknown"}
OUTCOME_DISPOSITIONS = {
    "open",
    "satisfied",
    "satisfied-with-approved-change",
    "partial",
    "failed",
    "rejected",
    "superseded",
    "parked",
    "not-applicable",
    "unknown",
}
RECONCILIATION_STATES = {"open", "reconciliation-required", "reconciled", "unknown"}
TRANSITIONS = {"created", "document-lifecycle", "outcome-lifecycle", "outcome-disposition", "reconciliation"}
PLANNING_ORDER_SOURCES = {"derived", "owner", "not-applicable"}
PLANNING_READINESS_STATES = {"ready", "working", "waiting", "blocked", "terminal", "not-applicable"}
REPORTER_STATES = {"active", "quiescent", "delivery-delayed", "unknown"}
RELEASE_SOURCES = {"local-git-tag", "release-cohort", "unknown"}
COMPATIBILITY_STATES = {"compatible", "incompatible", "unsupported", "unknown"}
QUALIFICATION_STATES = {"qualified", "unqualified", "unknown"}
RELEASE_CHAIN_STAGES = {"awaiting-work5", "released", "reconciled"}


def _object(value: Any, label: str, fields: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    unknown = sorted(set(value) - fields)
    if unknown:
        raise ContractError(f"{label} contains unsupported fields: {', '.join(unknown)}")
    return value


def _required_string(value: Any, label: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ContractError(f"{label} must be a non-empty string no longer than {limit} characters")
    return value.strip()


def _optional_string(value: Any, label: str, limit: int) -> str | None:
    if value is None:
        return None
    return _required_string(value, label, limit)


def _uuid(value: Any, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise ContractError(f"{label} must be a UUID") from error


def _timestamp(value: Any, label: str, *, optional: bool = False) -> datetime | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise ContractError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractError(f"{label} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ContractError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _counter(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContractError(f"{label} must be a non-negative integer")
    return value


def _bounded_counter(value: Any, label: str, limit: int) -> int:
    result = _counter(value, label)
    if result > limit:
        raise ContractError(f"{label} must be no greater than {limit}")
    return result


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ContractError(f"{label} must be a boolean")
    return value


def _choice(value: Any, label: str, choices: set[str], limit: int = 48) -> str:
    selected = _required_string(value, label, limit)
    if selected not in choices:
        raise ContractError(f"{label} is unsupported")
    return selected


def _string_list(value: Any, label: str, *, limit: int = 16) -> list[str]:
    if not isinstance(value, list) or len(value) > limit:
        raise ContractError(f"{label} must be a list of at most {limit} items")
    return [_required_string(item, f"{label} item", 64) for item in value]


def _work_inventory(value: Any, *, schema_version: int) -> dict[str, Any]:
    supplied = _object(value, "work_inventory", WORK_INVENTORY_FIELDS)
    raw_artifacts = supplied.get("artifacts", [])
    if not isinstance(raw_artifacts, list) or len(raw_artifacts) > 500:
        raise ContractError("work_inventory.artifacts must be a list of at most 500 items")
    artifacts = []
    seen: set[uuid.UUID] = set()
    for index, raw in enumerate(raw_artifacts, start=1):
        label = f"work artifact {index}"
        item = _object(raw, label, WORK_ARTIFACT_FIELDS)
        artifact_id = _uuid(item.get("artifact_id"), f"{label}.artifact_id")
        if artifact_id in seen:
            raise ContractError("work_inventory.artifacts contains duplicate artifact_id values")
        seen.add(artifact_id)
        planning_position = item.get("planning_position")
        if planning_position is not None:
            planning_position = _counter(planning_position, f"{label}.planning_position")
            if planning_position < 1:
                raise ContractError(f"{label}.planning_position must be positive")
        if schema_version >= 3:
            planning_source = _choice(
                item.get("planning_order_source"),
                f"{label}.planning_order_source",
                PLANNING_ORDER_SOURCES,
                24,
            )
            planning_readiness = _choice(
                item.get("planning_readiness"),
                f"{label}.planning_readiness",
                PLANNING_READINESS_STATES,
                24,
            )
        else:
            planning_position = None
            planning_source = "not-applicable"
            planning_readiness = "not-applicable"
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "visible_id": _required_string(item.get("visible_id"), f"{label}.visible_id", 64),
                "artifact_type": _choice(item.get("artifact_type"), f"{label}.artifact_type", ARTIFACT_TYPES, 32),
                "title": _required_string(item.get("title"), f"{label}.title", 160),
                "document_lifecycle": _choice(item.get("document_lifecycle"), f"{label}.document_lifecycle", DOCUMENT_LIFECYCLES, 32),
                "outcome_lifecycle": _choice(item.get("outcome_lifecycle", "unknown"), f"{label}.outcome_lifecycle", OUTCOME_LIFECYCLES, 32),
                "outcome_disposition": _choice(item.get("outcome_disposition", "unknown"), f"{label}.outcome_disposition", OUTCOME_DISPOSITIONS),
                "reconciliation_state": _choice(item.get("reconciliation_state", "unknown"), f"{label}.reconciliation_state", RECONCILIATION_STATES, 32),
                "parent_ids": _string_list(item.get("parent_ids", []), f"{label}.parent_ids"),
                "produces_ids": _string_list(item.get("produces_ids", []), f"{label}.produces_ids"),
                "planning_position": planning_position,
                "planning_order_source": planning_source,
                "planning_readiness": planning_readiness,
                "updated_at": _timestamp(item.get("updated_at"), f"{label}.updated_at"),
            }
        )
    total = _counter(supplied.get("total_count"), "work_inventory.total_count")
    truncated = _boolean(supplied.get("truncated", False), "work_inventory.truncated")
    if total < len(artifacts) or (not truncated and total != len(artifacts)):
        raise ContractError("work_inventory.total_count does not match the bounded artifact list")
    return {"total_count": total, "truncated": truncated, "artifacts": artifacts}


def _lifecycle_events(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > 50:
        raise ContractError("lifecycle_events must be a list of at most 50 items")
    result = []
    for index, raw in enumerate(value, start=1):
        label = f"lifecycle event {index}"
        item = _object(raw, label, LIFECYCLE_EVENT_FIELDS)
        result.append(
            {
                "event_key": _required_string(item.get("event_key"), f"{label}.event_key", 64),
                "artifact_id": _uuid(item.get("artifact_id"), f"{label}.artifact_id"),
                "visible_id": _required_string(item.get("visible_id"), f"{label}.visible_id", 64),
                "artifact_type": _choice(item.get("artifact_type"), f"{label}.artifact_type", ARTIFACT_TYPES, 32),
                "title": _required_string(item.get("title"), f"{label}.title", 160),
                "transition": _choice(item.get("transition"), f"{label}.transition", TRANSITIONS, 32),
                "from_state": _required_string(item.get("from_state"), f"{label}.from_state", 48),
                "to_state": _required_string(item.get("to_state"), f"{label}.to_state", 48),
                "occurred_at": _timestamp(item.get("occurred_at"), f"{label}.occurred_at"),
            }
        )
    return result


def _state(value: Any) -> dict[str, Any]:
    supplied = _object(value, "state", STATE_FIELDS)
    result = {field: _counter(supplied.get(field, 0), f"state.{field}") for field in STATE_FIELDS if field.endswith("_count")}
    result["last_completed_id"] = _optional_string(supplied.get("last_completed_id"), "state.last_completed_id", 64)
    blocked = result["blocked_count"]
    unreconciled = result["unreconciled_outcome_count"]
    working = result["working_count"]
    result["attention_state"] = "blocked" if blocked else "attention" if unreconciled else "working" if working else "healthy"
    return result


def _instance_health(value: Any, *, schema_version: int) -> dict[str, Any]:
    supplied = _object(value, "instance_health", INSTANCE_HEALTH_FIELDS)
    release = _object(
        supplied.get("release"),
        "instance_health.release",
        RELEASE_FIELDS_V5 if schema_version >= 5 else RELEASE_FIELDS,
    )
    digest = _required_string(supplied.get("semantic_digest"), "instance_health.semantic_digest", 64)
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ContractError("instance_health.semantic_digest must be a lowercase SHA-256")
    release_result = {
        "installed_version": _required_string(
            release.get("installed_version"), "instance_health.release.installed_version", 64
        ),
        "stable_version": _optional_string(
            release.get("stable_version"), "instance_health.release.stable_version", 64
        ),
        "stable_source": _choice(
            release.get("stable_source"),
            "instance_health.release.stable_source",
            RELEASE_SOURCES,
            24,
        ),
        "candidate_version": _optional_string(
            release.get("candidate_version"), "instance_health.release.candidate_version", 64
        ),
        "pending_candidate_count": _bounded_counter(
            release.get("pending_candidate_count"),
            "instance_health.release.pending_candidate_count",
            10_000,
        ),
        "production_version": _optional_string(
            release.get("production_version"), "instance_health.release.production_version", 64
        ),
        "production_source": _choice(
            release.get("production_source"),
            "instance_health.release.production_source",
            RELEASE_SOURCES,
            24,
        ),
        "observed_at": _timestamp(
            release.get("observed_at"), "instance_health.release.observed_at"
        ),
        "compatibility_state": _choice(
            release.get("compatibility_state"),
            "instance_health.release.compatibility_state",
            COMPATIBILITY_STATES,
            24,
        ),
        "qualification_state": _choice(
            release.get("qualification_state"),
            "instance_health.release.qualification_state",
            QUALIFICATION_STATES,
            24,
        ),
    }
    if schema_version >= 5:
        raw_chains = release.get("release_chains")
        if not isinstance(raw_chains, list) or len(raw_chains) > 50:
            raise ContractError("instance_health.release.release_chains must be a list of at most 50 items")
        chains = []
        for index, raw_chain in enumerate(raw_chains, start=1):
            label = f"release chain {index}"
            chain = _object(raw_chain, label, RELEASE_CHAIN_FIELDS)
            commit = _required_string(chain.get("latest_commit"), f"{label}.latest_commit", 40)
            if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
                raise ContractError(f"{label}.latest_commit must be a lowercase Git commit")
            chains.append(
                {
                    "root_id": _required_string(chain.get("root_id"), f"{label}.root_id", 64),
                    "idea_id": _optional_string(chain.get("idea_id"), f"{label}.idea_id", 64),
                    "map_id": _optional_string(chain.get("map_id"), f"{label}.map_id", 64),
                    "prm_id": _optional_string(chain.get("prm_id"), f"{label}.prm_id", 64),
                    "campaign_id": _optional_string(chain.get("campaign_id"), f"{label}.campaign_id", 64),
                    "stage": _choice(chain.get("stage"), f"{label}.stage", RELEASE_CHAIN_STAGES, 24),
                    "latest_commit": commit,
                    "candidate_count": _bounded_counter(chain.get("candidate_count"), f"{label}.candidate_count", 100),
                }
            )
        chain_count = _bounded_counter(
            release.get("awaiting_work5_chain_count"),
            "instance_health.release.awaiting_work5_chain_count",
            10_000,
        )
        truncated = _boolean(
            release.get("release_chains_truncated"),
            "instance_health.release.release_chains_truncated",
        )
        if chain_count < len(chains) or (not truncated and chain_count != len(chains)):
            raise ContractError("instance_health.release.awaiting_work5_chain_count does not match release_chains")
        release_result.update(
            {
                "awaiting_work5_chain_count": chain_count,
                "candidate_commit_count": _bounded_counter(
                    release.get("candidate_commit_count"),
                    "instance_health.release.candidate_commit_count",
                    10_000,
                ),
                "registration_count": _bounded_counter(
                    release.get("registration_count"),
                    "instance_health.release.registration_count",
                    10_000,
                ),
                "release_chains": chains,
                "release_chains_truncated": truncated,
            }
        )
    return {
        "reporter_state": _choice(
            supplied.get("reporter_state"), "instance_health.reporter_state", REPORTER_STATES, 24
        ),
        "pending_event_count": _bounded_counter(
            supplied.get("pending_event_count"), "instance_health.pending_event_count", 10_000
        ),
        "last_delivery_at": _timestamp(
            supplied.get("last_delivery_at"), "instance_health.last_delivery_at", optional=True
        ),
        "semantic_digest": digest,
        "release": release_result,
    }


def validate_report(payload: Any) -> dict[str, Any]:
    root = _object(payload, "report", ROOT_FIELDS)
    schema_version = root.get("schema_version")
    if schema_version not in {1, 2, 3, 4, 5}:
        raise ContractError("report.schema_version must be 1, 2, 3, 4, or 5")
    if schema_version == 1 and ({"work_inventory", "lifecycle_events"} & set(root)):
        raise ContractError("report schema 1 does not support lifecycle projection fields")
    if schema_version < 4 and "instance_health" in root:
        raise ContractError("report schemas before 4 do not support instance health")
    project = _object(root.get("project"), "project", PROJECT_FIELDS)
    instance = _object(root.get("instance"), "instance", INSTANCE_FIELDS)
    app_server = _object(root.get("app_server"), "app_server", APP_SERVER_FIELDS)
    failure_values = app_server.get("failure_groups", [])
    if not isinstance(failure_values, list) or len(failure_values) > 20:
        raise ContractError("app_server.failure_groups must be a list of at most 20 items")
    failures = []
    for index, raw in enumerate(failure_values, start=1):
        item = _object(raw, f"failure group {index}", FAILURE_FIELDS)
        category = _required_string(item.get("category"), f"failure group {index}.category", 64)
        if category not in FAILURE_CATEGORIES:
            raise ContractError(f"failure group {index}.category is unsupported")
        failures.append(
            {
                "signature": _required_string(item.get("signature"), f"failure group {index}.signature", 64),
                "category": category,
                "count": _counter(item.get("count"), f"failure group {index}.count"),
                "first_seen": _timestamp(item.get("first_seen"), f"failure group {index}.first_seen"),
                "last_seen": _timestamp(item.get("last_seen"), f"failure group {index}.last_seen"),
            }
        )
    events_value = root.get("material_events", [])
    if not isinstance(events_value, list) or len(events_value) > 50:
        raise ContractError("material_events must be a list of at most 50 items")
    events = []
    for index, raw in enumerate(events_value, start=1):
        item = _object(raw, f"material event {index}", EVENT_FIELDS)
        kind = _required_string(item.get("kind"), f"material event {index}.kind", 64)
        if kind not in EVENT_KINDS:
            raise ContractError(f"material event {index}.kind is unsupported")
        events.append(
            {
                "kind": kind,
                "summary_code": _required_string(item.get("summary_code"), f"material event {index}.summary_code", 96),
                "occurred_at": _timestamp(item.get("occurred_at"), f"material event {index}.occurred_at"),
            }
        )
        if events[-1]["summary_code"] not in SUMMARY_CODES:
            raise ContractError(f"material event {index}.summary_code is unsupported")
    efficiency = _object(root.get("work_efficiency"), "work_efficiency", EFFICIENCY_FIELDS)
    try:
        coverage = Decimal(str(efficiency.get("remedial_token_coverage")))
    except (InvalidOperation, TypeError) as error:
        raise ContractError("work_efficiency.remedial_token_coverage must be numeric") from error
    if not coverage.is_finite() or coverage < 0 or coverage > 1:
        raise ContractError("work_efficiency.remedial_token_coverage must be between 0 and 1")
    actual = efficiency.get("remedial_tokens_actual")
    availability = _required_string(app_server.get("availability_state", "unknown"), "app_server.availability_state", 32)
    if availability not in AVAILABILITY_STATES:
        raise ContractError("app_server.availability_state is unsupported")
    return {
        "schema_version": schema_version,
        "idempotency_key": _uuid(root.get("idempotency_key"), "idempotency_key"),
        "sequence": _counter(root.get("sequence"), "sequence"),
        "observed_at": _timestamp(root.get("observed_at"), "observed_at"),
        "project": {"id": _uuid(project.get("id"), "project.id"), "name": _required_string(project.get("name"), "project.name", 160)},
        "instance": {
            "id": _uuid(instance.get("id"), "instance.id"),
            "platform": _required_string(instance.get("platform"), "instance.platform", 64),
            "client_version": _required_string(instance.get("client_version"), "instance.client_version", 64),
            "counter_epoch": _uuid(instance.get("counter_epoch"), "instance.counter_epoch"),
            "quiescent": _boolean(instance.get("quiescent", False), "instance.quiescent"),
        },
        "state": _state(root.get("state")),
        "material_events": events,
        "app_server": {
            "enabled": _boolean(app_server.get("enabled", False), "app_server.enabled"),
            "availability_state": availability,
            "attempts": _counter(app_server.get("attempts", 0), "app_server.attempts"),
            "failures": _counter(app_server.get("failures", 0), "app_server.failures"),
            "fallbacks": _counter(app_server.get("fallbacks", 0), "app_server.fallbacks"),
            "last_success": _timestamp(app_server.get("last_success"), "app_server.last_success", optional=True),
            "last_failure": _timestamp(app_server.get("last_failure"), "app_server.last_failure", optional=True),
            "client_version": _optional_string(app_server.get("client_version"), "app_server.client_version", 64) or "",
            "failure_groups": failures,
        },
        "work_efficiency": {
            "window_start": _timestamp(efficiency.get("window_start"), "work_efficiency.window_start"),
            "window_end": _timestamp(efficiency.get("window_end"), "work_efficiency.window_end"),
            "remedial_tokens_actual": None if actual is None else _counter(actual, "work_efficiency.remedial_tokens_actual"),
            "remedial_token_coverage": coverage,
            "remedial_interactions": _counter(efficiency.get("remedial_interactions", 0), "work_efficiency.remedial_interactions"),
            "remedial_output_bytes": _counter(efficiency.get("remedial_output_bytes", 0), "work_efficiency.remedial_output_bytes"),
            "remedial_duration_ms": _counter(efficiency.get("remedial_duration_ms", 0), "work_efficiency.remedial_duration_ms"),
            "remedial_retries": _counter(efficiency.get("remedial_retries", 0), "work_efficiency.remedial_retries"),
        },
        "work_inventory": _work_inventory(root.get("work_inventory"), schema_version=schema_version) if schema_version >= 2 else None,
        "lifecycle_events": _lifecycle_events(root.get("lifecycle_events", [])) if schema_version >= 2 else [],
        "instance_health": _instance_health(
            root.get("instance_health"), schema_version=schema_version
        ) if schema_version >= 4 else None,
    }
