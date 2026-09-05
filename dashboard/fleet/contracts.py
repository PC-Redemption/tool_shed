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
    "loop_findings",
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
    "active_loop_finding_count",
    "last_completed_id",
}
STATE_FIELDS_V9 = STATE_FIELDS | {"queued_count", "closure_debt_count"}
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
APP_SERVER_FIELDS_V6 = APP_SERVER_FIELDS | {"readiness_observed_at", "performance"}
PERFORMANCE_FIELDS = {"default_window", "windows"}
PERFORMANCE_WINDOW_FIELDS = {
    "schema_version",
    "window_start",
    "window_end",
    "attempts",
    "completions",
    "failures",
    "interruptions",
    "fallbacks",
    "duration_p50_ms",
    "duration_p95_ms",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "weighted_usage_milliunits",
    "weighted_usage_version",
    "last_execution",
    "last_success",
    "last_failure",
    "client_version",
    "role_metrics",
    "excluded_malformed_records",
    "privacy",
}
ROLE_METRIC_FIELDS = PERFORMANCE_WINDOW_FIELDS - {
    "schema_version",
    "window_start",
    "window_end",
    "last_execution",
    "last_success",
    "last_failure",
    "client_version",
    "role_metrics",
    "excluded_malformed_records",
    "privacy",
    "fallbacks",
}
PERFORMANCE_WINDOWS = {"24h", "7d", "30d"}
PERFORMANCE_ROLES = {"planning", "verification", "camp_execution"}
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
LOOP_FINDING_PROJECTION_FIELDS = {"total_active_count", "total_resolved_count", "truncated", "findings"}
LOOP_FINDING_FIELDS = {
    "finding_id", "category", "severity", "reason_code", "subject_id", "observed_state",
    "expected_state", "state", "source_revision", "first_observed_at", "last_observed_at",
    "resolved_at", "recurrence_count", "command",
}
LOOP_FINDING_CATEGORIES = {
    "semantic-lifecycle-drift", "outcome-health", "outcome-reconciliation",
    "outcome-propagation", "lineage-health", "evidence-health", "semantic-body-drift",
    "closure-debt",
}
LOOP_FINDING_REASON_CODES = {
    "PROMOTED_IDEA_LIFECYCLE_STALE", "OUTCOME_BLOCKED", "OUTCOME_STALLED",
    "PROMOTED_IDEA_MISSING_OUTCOME", "TERMINAL_DOCUMENT_LIFECYCLE_STALE",
    "TERMINAL_DOCUMENT_BODY_STATUS_STALE", "TERMINAL_DOCUMENT_DESCENDANTS_OPEN",
    "COMPLETED_DOCUMENT_CLOSURE_OPEN",
    "TERMINAL_OUTCOME_UNRECONCILED", "INVALID_RECONCILED_DISPOSITION",
    "OUTCOME_RESULT_UNPROPAGATED", "LINEAGE_INVALID", "LINEAGE_RECOVERY_REQUIRED",
    "CLOSURE_EVIDENCE_MISSING", "CLOSURE_EVIDENCE_STALE",
    "CLOSURE_EVIDENCE_CHECKER_ERROR",
}
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
WORK_ARTIFACT_FIELDS_V7 = WORK_ARTIFACT_FIELDS | {"closure_status"}
CLOSURE_STATUS_FIELDS = {
    "local_closure", "evidence_health", "graph_health", "effective_closed", "reason_codes",
    "counts", "blockers", "subject_revision", "graph_revision", "evaluator_version", "evaluated_at",
}
CLOSURE_COUNT_FIELDS = {"open", "unknown", "invalid"}
CLOSURE_BLOCKER_FIELDS = {
    "blocking_element_id", "blocking_obligation_id", "reason_code", "depth",
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
    "verification",
    "interrupted",
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
DOCUMENT_LIFECYCLES = {
    "active",
    "working",
    "blocked",
    "parked",
    "deferred",
    "completed",
    "abandoned",
    "superseded",
    "terminal",
}
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


def _optional_counter(value: Any, label: str) -> int | None:
    return None if value is None else _counter(value, label)


def _performance_metrics(value: Any, label: str, *, role: bool = False) -> dict[str, Any]:
    fields = ROLE_METRIC_FIELDS if role else PERFORMANCE_WINDOW_FIELDS
    item = _object(value, label, fields)
    result = {
        "attempts": _counter(item.get("attempts"), f"{label}.attempts"),
        "completions": _counter(item.get("completions"), f"{label}.completions"),
        "failures": _counter(item.get("failures"), f"{label}.failures"),
        "interruptions": _counter(item.get("interruptions"), f"{label}.interruptions"),
        "duration_p50_ms": _optional_counter(item.get("duration_p50_ms"), f"{label}.duration_p50_ms"),
        "duration_p95_ms": _optional_counter(item.get("duration_p95_ms"), f"{label}.duration_p95_ms"),
        "input_tokens": _counter(item.get("input_tokens"), f"{label}.input_tokens"),
        "cached_input_tokens": _counter(item.get("cached_input_tokens"), f"{label}.cached_input_tokens"),
        "output_tokens": _counter(item.get("output_tokens"), f"{label}.output_tokens"),
        "reasoning_tokens": _counter(item.get("reasoning_tokens"), f"{label}.reasoning_tokens"),
        "weighted_usage_milliunits": _optional_counter(
            item.get("weighted_usage_milliunits"), f"{label}.weighted_usage_milliunits"
        ),
        "weighted_usage_version": _optional_string(
            item.get("weighted_usage_version"), f"{label}.weighted_usage_version", 64
        ),
    }
    if result["completions"] + result["failures"] + result["interruptions"] != result["attempts"]:
        raise ContractError(f"{label} outcome counts must equal attempts")
    if role:
        return result
    result["fallbacks"] = _counter(item.get("fallbacks"), f"{label}.fallbacks")
    roles = _object(item.get("role_metrics"), f"{label}.role_metrics", PERFORMANCE_ROLES)
    if set(roles) != PERFORMANCE_ROLES:
        raise ContractError(f"{label}.role_metrics must include every supported role")
    parsed_roles = {
        key: _performance_metrics(roles[key], f"{label}.role_metrics.{key}", role=True)
        for key in sorted(PERFORMANCE_ROLES)
    }
    for counter in ("attempts", "completions", "failures", "interruptions"):
        if sum(role_metrics[counter] for role_metrics in parsed_roles.values()) != result[counter]:
            raise ContractError(f"{label}.{counter} must equal the role metric total")
    timestamps = {
        key: _timestamp(item.get(key), f"{label}.{key}", optional=key.startswith("last_"))
        for key in ("window_start", "window_end", "last_execution", "last_success", "last_failure")
    }
    result.update(
        {
            "schema_version": _bounded_counter(item.get("schema_version"), f"{label}.schema_version", 1),
            "window_start": timestamps["window_start"].isoformat(),
            "window_end": timestamps["window_end"].isoformat(),
            "last_execution": timestamps["last_execution"].isoformat() if timestamps["last_execution"] else None,
            "last_success": timestamps["last_success"].isoformat() if timestamps["last_success"] else None,
            "last_failure": timestamps["last_failure"].isoformat() if timestamps["last_failure"] else None,
            "client_version": _optional_string(item.get("client_version"), f"{label}.client_version", 64),
            "role_metrics": parsed_roles,
            "excluded_malformed_records": _bounded_counter(
                item.get("excluded_malformed_records"), f"{label}.excluded_malformed_records", 10_000
            ),
            "privacy": _choice(
                item.get("privacy"), f"{label}.privacy", {"content-free-controlled-aggregate-only"}, 64
            ),
        }
    )
    if result["schema_version"] != 1:
        raise ContractError(f"{label}.schema_version must be 1")
    return result


def _performance(value: Any) -> dict[str, Any]:
    supplied = _object(value, "app_server.performance", PERFORMANCE_FIELDS)
    default_window = _choice(
        supplied.get("default_window"), "app_server.performance.default_window", PERFORMANCE_WINDOWS, 8
    )
    windows = _object(supplied.get("windows"), "app_server.performance.windows", PERFORMANCE_WINDOWS)
    if set(windows) != PERFORMANCE_WINDOWS:
        raise ContractError("app_server.performance.windows must include 24h, 7d, and 30d")
    return {
        "default_window": default_window,
        "windows": {
            key: _performance_metrics(windows[key], f"app_server.performance.windows.{key}")
            for key in ("24h", "7d", "30d")
        },
    }


def _choice(value: Any, label: str, choices: set[str], limit: int = 48) -> str:
    selected = _required_string(value, label, limit)
    if selected not in choices:
        raise ContractError(f"{label} is unsupported")
    return selected


def _string_list(value: Any, label: str, *, limit: int = 16) -> list[str]:
    if not isinstance(value, list) or len(value) > limit:
        raise ContractError(f"{label} must be a list of at most {limit} items")
    return [_required_string(item, f"{label} item", 64) for item in value]


def _closure_status(value: Any, label: str) -> dict[str, Any]:
    item = _object(value, label, CLOSURE_STATUS_FIELDS)
    counts = _object(item.get("counts"), f"{label}.counts", CLOSURE_COUNT_FIELDS)
    raw_blockers = item.get("blockers")
    if not isinstance(raw_blockers, list) or len(raw_blockers) > 20:
        raise ContractError(f"{label}.blockers must be a list of at most 20 items")
    blockers = []
    for index, raw in enumerate(raw_blockers, start=1):
        blocker = _object(raw, f"{label}.blocker {index}", CLOSURE_BLOCKER_FIELDS)
        blockers.append(
            {
                "blocking_element_id": _optional_string(
                    blocker.get("blocking_element_id"), f"{label}.blocker {index}.blocking_element_id", 64
                ),
                "blocking_obligation_id": _optional_string(
                    blocker.get("blocking_obligation_id"), f"{label}.blocker {index}.blocking_obligation_id", 64
                ),
                "reason_code": _required_string(
                    blocker.get("reason_code"), f"{label}.blocker {index}.reason_code", 64
                ),
                "depth": _bounded_counter(blocker.get("depth"), f"{label}.blocker {index}.depth", 10_000),
            }
        )
    return {
        "local_closure": _choice(
            item.get("local_closure"), f"{label}.local_closure",
            {"open", "closed-loop", "closed-manual", "unknown"}, 24,
        ),
        "evidence_health": _choice(
            item.get("evidence_health"), f"{label}.evidence_health",
            {"current", "stale", "missing", "checker-error", "not-required", "unknown"}, 24,
        ),
        "graph_health": _choice(
            item.get("graph_health"), f"{label}.graph_health",
            {"valid", "invalid", "recovery-required", "unknown"}, 24,
        ),
        "effective_closed": _boolean(item.get("effective_closed"), f"{label}.effective_closed"),
        "reason_codes": _string_list(item.get("reason_codes", []), f"{label}.reason_codes", limit=32),
        "counts": {
            field: _bounded_counter(counts.get(field), f"{label}.counts.{field}", 1_000_000)
            for field in CLOSURE_COUNT_FIELDS
        },
        "blockers": blockers,
        "subject_revision": _counter(item.get("subject_revision"), f"{label}.subject_revision"),
        "graph_revision": _counter(item.get("graph_revision"), f"{label}.graph_revision"),
        "evaluator_version": _required_string(item.get("evaluator_version"), f"{label}.evaluator_version", 64),
        "evaluated_at": _timestamp(item.get("evaluated_at"), f"{label}.evaluated_at"),
    }


def _work_inventory(value: Any, *, schema_version: int) -> dict[str, Any]:
    supplied = _object(value, "work_inventory", WORK_INVENTORY_FIELDS)
    raw_artifacts = supplied.get("artifacts", [])
    if not isinstance(raw_artifacts, list) or len(raw_artifacts) > 500:
        raise ContractError("work_inventory.artifacts must be a list of at most 500 items")
    artifacts = []
    seen: set[uuid.UUID] = set()
    for index, raw in enumerate(raw_artifacts, start=1):
        label = f"work artifact {index}"
        item = _object(raw, label, WORK_ARTIFACT_FIELDS_V7 if schema_version >= 7 else WORK_ARTIFACT_FIELDS)
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
                "closure_status": _closure_status(
                    item.get("closure_status"), f"{label}.closure_status"
                ) if schema_version >= 7 else {},
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


def _loop_findings(value: Any) -> dict[str, Any]:
    supplied = _object(value, "loop_findings", LOOP_FINDING_PROJECTION_FIELDS)
    raw_findings = supplied.get("findings", [])
    if not isinstance(raw_findings, list) or len(raw_findings) > 100:
        raise ContractError("loop_findings.findings must be a list of at most 100 items")
    findings = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_findings, start=1):
        label = f"loop finding {index}"
        item = _object(raw, label, LOOP_FINDING_FIELDS)
        finding_id = _required_string(item.get("finding_id"), f"{label}.finding_id", 32)
        if finding_id in seen or not finding_id.startswith("LOOP-"):
            raise ContractError("loop findings must have unique LOOP- identifiers")
        seen.add(finding_id)
        command = _required_string(item.get("command"), f"{label}.command", 64)
        if command != f"ts: resolve loop {finding_id}":
            raise ContractError(f"{label}.command must contain only its stable local Tool Shed route")
        source_revision = _counter(item.get("source_revision"), f"{label}.source_revision")
        if source_revision < 1:
            raise ContractError(f"{label}.source_revision must be positive")
        state = _choice(item.get("state"), f"{label}.state", {"active", "resolved"}, 16)
        resolved_at = _timestamp(item.get("resolved_at"), f"{label}.resolved_at", optional=True)
        if (state == "resolved") != (resolved_at is not None):
            raise ContractError(f"{label}.resolved_at must match state")
        findings.append(
            {
                "finding_id": finding_id,
                "category": _choice(item.get("category"), f"{label}.category", LOOP_FINDING_CATEGORIES, 48),
                "severity": _choice(item.get("severity"), f"{label}.severity", {"attention"}, 16),
                "reason_code": _choice(item.get("reason_code"), f"{label}.reason_code", LOOP_FINDING_REASON_CODES, 64),
                "subject_id": _required_string(item.get("subject_id"), f"{label}.subject_id", 64),
                "observed_state": _required_string(item.get("observed_state"), f"{label}.observed_state", 32),
                "expected_state": _required_string(item.get("expected_state"), f"{label}.expected_state", 32),
                "state": state,
                "source_revision": source_revision,
                "first_observed_at": _timestamp(item.get("first_observed_at"), f"{label}.first_observed_at"),
                "last_observed_at": _timestamp(item.get("last_observed_at"), f"{label}.last_observed_at"),
                "resolved_at": resolved_at,
                "recurrence_count": _bounded_counter(item.get("recurrence_count"), f"{label}.recurrence_count", 1_000_000),
                "command": command,
            }
        )
    active = _bounded_counter(supplied.get("total_active_count"), "loop_findings.total_active_count", 1_000_000)
    resolved = _bounded_counter(supplied.get("total_resolved_count"), "loop_findings.total_resolved_count", 1_000_000)
    truncated = _boolean(supplied.get("truncated"), "loop_findings.truncated")
    reported_active = sum(item["state"] == "active" for item in findings)
    reported_resolved = sum(item["state"] == "resolved" for item in findings)
    if active < reported_active or resolved < reported_resolved:
        raise ContractError("loop finding totals cannot be smaller than the bounded list")
    if not truncated and (active != reported_active or resolved != reported_resolved):
        raise ContractError("untruncated loop finding totals must match the bounded list")
    return {"total_active_count": active, "total_resolved_count": resolved, "truncated": truncated, "findings": findings}


def _state(value: Any, *, schema_version: int) -> dict[str, Any]:
    fields = STATE_FIELDS_V9 if schema_version >= 9 else STATE_FIELDS
    supplied = _object(value, "state", fields)
    result = {field: _counter(supplied.get(field, 0), f"state.{field}") for field in fields if field.endswith("_count")}
    result["last_completed_id"] = _optional_string(supplied.get("last_completed_id"), "state.last_completed_id", 64)
    blocked = result["blocked_count"]
    unreconciled = result["unreconciled_outcome_count"]
    working = result["working_count"]
    findings = result["active_loop_finding_count"]
    result["attention_state"] = "blocked" if blocked else "attention" if unreconciled or findings else "working" if working else "healthy"
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
        reported_awaiting = sum(item["stage"] == "awaiting-work5" for item in chains)
        if chain_count < reported_awaiting or (not truncated and chain_count != reported_awaiting):
            raise ContractError("instance_health.release.awaiting_work5_chain_count does not match awaiting chains")
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
    if schema_version not in {1, 2, 3, 4, 5, 6, 7, 8, 9}:
        raise ContractError("report.schema_version must be between 1 and 9")
    if schema_version == 1 and ({"work_inventory", "lifecycle_events"} & set(root)):
        raise ContractError("report schema 1 does not support lifecycle projection fields")
    if schema_version < 4 and "instance_health" in root:
        raise ContractError("report schemas before 4 do not support instance health")
    if schema_version < 8 and "loop_findings" in root:
        raise ContractError("report schemas before 8 do not support loop findings")
    if schema_version >= 8 and "loop_findings" not in root:
        raise ContractError("report schema 8 requires loop findings")
    project = _object(root.get("project"), "project", PROJECT_FIELDS)
    instance = _object(root.get("instance"), "instance", INSTANCE_FIELDS)
    app_server = _object(
        root.get("app_server"),
        "app_server",
        APP_SERVER_FIELDS_V6 if schema_version >= 6 else APP_SERVER_FIELDS,
    )
    if schema_version >= 6 and not {"readiness_observed_at", "performance"} <= set(app_server):
        raise ContractError("report schema 6 requires App Server readiness and performance fields")
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
        "state": _state(root.get("state"), schema_version=schema_version),
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
            "readiness_observed_at": _timestamp(
                app_server.get("readiness_observed_at"),
                "app_server.readiness_observed_at",
                optional=True,
            ) if schema_version >= 6 else None,
            "performance": _performance(app_server.get("performance")) if schema_version >= 6 else {},
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
        "loop_findings": _loop_findings(root.get("loop_findings")) if schema_version >= 8 else None,
    }
