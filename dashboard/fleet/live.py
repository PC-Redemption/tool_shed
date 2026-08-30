from __future__ import annotations

import hashlib
import json

from .models import AppServerAggregate, Enrollment, FailureGroup, Instance, Project, WorkEfficiencyAggregate


def dashboard_revision() -> str:
    """Return a content revision for database state exposed by dashboard pages."""
    payload = {
        "projects": list(
            Project.objects.order_by("id").values_list(
                "id", "name", "attention_state", "current_state", "state_schema_version"
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
            )
        ),
        "enrollments": list(
            Enrollment.objects.order_by("id").values_list(
                "id", "status", "expires_at", "decided_at", "issued_instance_id"
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
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]
