from __future__ import annotations

import hashlib
import json

from .models import (
    AppServerAggregate,
    AttentionCondition,
    Enrollment,
    FailureGroup,
    Instance,
    LifecycleEvent,
    LoopFindingSnapshot,
    MaterialEvent,
    Project,
    ReporterCredential,
    WorkArtifactSnapshot,
    WorkEfficiencyAggregate,
)


def _semantic_health(value: object) -> object:
    if not isinstance(value, dict):
        return value
    normalized = json.loads(json.dumps(value))
    normalized.pop("last_delivery_at", None)
    if isinstance(normalized.get("release"), dict):
        normalized["release"].pop("observed_at", None)
    return normalized


def dashboard_revision() -> str:
    """Return a content revision for database state exposed by dashboard pages."""
    payload = {
        "projects": list(
            Project.objects.filter(qualification_run__isnull=True).order_by("id").values_list(
                "id",
                "name",
                "attention_state",
                "current_state",
                "state_schema_version",
                "last_activity_at",
                "is_hidden",
            )
        ),
        "instances": [
            (*row[:-1], _semantic_health(row[-1]))
            for row in Instance.objects.filter(project__qualification_run__isnull=True).order_by("id").values_list(
                "id",
                "project_id",
                "platform",
                "client_version",
                "report_schema_version",
                "counter_epoch",
                "quiescent",
                "work_inventory_digest",
                "work_inventory_total",
                "work_inventory_truncated",
                "health_state",
            )
        ],
        "enrollments": list(
            Enrollment.objects.order_by("id").values_list(
                "id", "status", "expires_at", "decided_at", "issued_instance_id"
            )
        ),
        "credentials": list(
            ReporterCredential.objects.filter(scope="operational").order_by("id").values_list(
                "id", "instance_id", "created_at", "rotated_at", "revoked_at"
            )
        ),
        "material_events": list(
            MaterialEvent.objects.filter(project__qualification_run__isnull=True).order_by("id").values_list(
                "id", "project_id", "instance_id", "event_kind", "summary_code", "occurred_at"
            )
        ),
        "app_server": list(
            AppServerAggregate.objects.filter(instance__project__qualification_run__isnull=True).order_by("instance_id").values_list(
                "instance_id",
                "counter_epoch",
                "enabled",
                "availability_state",
                "attempts",
                "failures",
                "fallbacks",
                "last_success",
                "last_failure",
                "client_version",
                "readiness_observed_at",
                "performance",
            )
        ),
        "failure_groups": list(
            FailureGroup.objects.filter(instance__project__qualification_run__isnull=True).order_by("id").values_list(
                "id", "instance_id", "signature", "category", "count", "first_seen", "last_seen"
            )
        ),
        "work_efficiency": list(
            WorkEfficiencyAggregate.objects.filter(instance__project__qualification_run__isnull=True).order_by("id").values_list(
                "id",
                "instance_id",
                "counter_epoch",
                "window_start",
                "window_end",
                "remedial_tokens_actual",
                "remedial_token_coverage",
                "remedial_interactions",
                "remedial_output_bytes",
                "remedial_duration_ms",
                "remedial_retries",
            )
        ),
        "work_artifacts": list(
            WorkArtifactSnapshot.objects.filter(project__qualification_run__isnull=True).order_by("instance_id", "visible_id").values_list(
                "instance_id",
                "artifact_external_id",
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
                "source_updated_at",
            )
        ),
        "lifecycle_events": list(
            LifecycleEvent.objects.filter(project__qualification_run__isnull=True).order_by("instance_id", "event_key").values_list(
                "instance_id",
                "event_key",
                "artifact_external_id",
                "transition",
                "from_state",
                "to_state",
                "occurred_at",
            )
        ),
        "loop_findings": list(
            LoopFindingSnapshot.objects.filter(project__qualification_run__isnull=True).order_by(
                "instance_id", "finding_external_id"
            ).values_list(
                "instance_id",
                "finding_external_id",
                "category",
                "severity",
                "reason_code",
                "subject_visible_id",
                "observed_state",
                "expected_state",
                "state",
                "source_revision",
                "last_observed_at",
                "recurrence_count",
                "command",
            )
        ),
        "attention_conditions": list(
            AttentionCondition.objects.filter(project__qualification_run__isnull=True).order_by("id").values_list(
                "id",
                "project_id",
                "instance_id",
                "reason_code",
                "severity",
                "active",
                "current_count",
                "first_seen",
                "last_changed",
                "resolved_at",
            )
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]
