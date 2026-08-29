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


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ContractError(f"{label} must be a boolean")
    return value


def _state(value: Any) -> dict[str, Any]:
    supplied = _object(value, "state", STATE_FIELDS)
    result = {field: _counter(supplied.get(field, 0), f"state.{field}") for field in STATE_FIELDS if field.endswith("_count")}
    result["last_completed_id"] = _optional_string(supplied.get("last_completed_id"), "state.last_completed_id", 64)
    blocked = result["blocked_count"]
    unreconciled = result["unreconciled_outcome_count"]
    working = result["working_count"]
    result["attention_state"] = "blocked" if blocked else "attention" if unreconciled else "working" if working else "healthy"
    return result


def validate_report(payload: Any) -> dict[str, Any]:
    root = _object(payload, "report", ROOT_FIELDS)
    if root.get("schema_version") != 1:
        raise ContractError("report.schema_version must be 1")
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
        "schema_version": 1,
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
    }
