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
    MaterialEvent,
    Project,
    ReporterCredential,
    WorkArtifactSnapshot,
    WorkEfficiencyAggregate,
)


def dashboard_revision() -> str:
    """Return a content revision for database state exposed by dashboard pages."""
    payload = {
        "projects": list(
            Project.objects.order_by("id").values_list(
                "id",
                "name",
                "attention_state",
                "current_state",
                "state_schema_version",
                "last_activity_at",
                "is_hidden",
            )
        ),
        "instances": list(
            Instance.objects.order_by("id").values_list(
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
            )
        ),
        "enrollments": list(
            Enrollment.objects.order_by("id").values_list(
                "id", "status", "expires_at", "decided_at", "issued_instance_id"
            )
        ),
        "credentials": list(
            ReporterCredential.objects.order_by("id").values_list(
                "id", "instance_id", "created_at", "rotated_at", "revoked_at"
            )
        ),
        "material_events": list(
            MaterialEvent.objects.order_by("id").values_list(
                "id", "project_id", "instance_id", "event_kind", "summary_code", "occurred_at"
            )
        ),
        "app_server": list(
            AppServerAggregate.objects.order_by("instance_id").values_list(
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
            )
        ),
        "failure_groups": list(
            FailureGroup.objects.order_by("id").values_list(
                "id", "instance_id", "signature", "category", "count", "first_seen", "last_seen"
            )
        ),
        "work_efficiency": list(
            WorkEfficiencyAggregate.objects.order_by("id").values_list(
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
            WorkArtifactSnapshot.objects.order_by("instance_id", "visible_id").values_list(
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
            LifecycleEvent.objects.order_by("instance_id", "event_key").values_list(
                "instance_id",
                "event_key",
                "artifact_external_id",
                "transition",
                "from_state",
                "to_state",
                "occurred_at",
            )
        ),
        "attention_conditions": list(
            AttentionCondition.objects.order_by("id").values_list(
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
