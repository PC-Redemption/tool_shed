from __future__ import annotations

import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from dashboard.fleet.models import (
    AttentionCondition,
    IngestReceipt,
    Instance,
    LifecycleEvent,
    Project,
    WorkArtifactSnapshot,
)


class Command(BaseCommand):
    help = "Export a bounded, credential-free raw development snapshot for the independent qualification oracle."

    def handle(self, *args, **options):
        if settings.DASHBOARD_ENVIRONMENT != "development":
            raise CommandError("qualification snapshot is restricted to the development environment")
        projects = [
            {
                "external_id": str(row.external_id),
                "name": row.name,
                "is_hidden": row.is_hidden,
                "attention_state": row.attention_state,
                "last_seen": row.last_seen.isoformat() if row.last_seen else None,
            }
            for row in Project.objects.order_by("external_id")
        ]
        instances = [
            {
                "external_id": str(row.external_id),
                "project_external_id": str(row.project.external_id),
                "platform": row.platform,
                "client_version": row.client_version,
                "last_sequence": row.last_sequence,
                "last_seen": row.last_seen.isoformat() if row.last_seen else None,
                "work_inventory_sequence": row.work_inventory_sequence,
                "work_inventory_observed_at": (
                    row.work_inventory_observed_at.isoformat()
                    if row.work_inventory_observed_at
                    else None
                ),
                "work_inventory_digest": row.work_inventory_digest,
                "work_inventory_total": row.work_inventory_total,
                "work_inventory_truncated": row.work_inventory_truncated,
                "health_state": row.health_state,
            }
            for row in Instance.objects.select_related("project").order_by("project__external_id", "external_id")
        ]
        artifacts = [
            {
                "project_external_id": str(row.project.external_id),
                "instance_external_id": str(row.instance.external_id),
                "artifact_external_id": str(row.artifact_external_id),
                "visible_id": row.visible_id,
                "artifact_type": row.artifact_type,
                "title": row.title,
                "document_lifecycle": row.document_lifecycle,
                "outcome_lifecycle": row.outcome_lifecycle,
                "outcome_disposition": row.outcome_disposition,
                "reconciliation_state": row.reconciliation_state,
                "closure_status": row.closure_status,
                "parent_ids": row.parent_ids,
                "produces_ids": row.produces_ids,
                "source_updated_at": row.source_updated_at.isoformat(),
                "observed_at": row.observed_at.isoformat(),
                "snapshot_sequence": row.snapshot_sequence,
            }
            for row in WorkArtifactSnapshot.objects.select_related("project", "instance").order_by(
                "project__external_id", "instance__external_id", "artifact_external_id"
            )
        ]
        attention = [
            {
                "project_external_id": str(row.project.external_id),
                "instance_external_id": str(row.instance.external_id),
                "reason_code": row.reason_code,
                "severity": row.severity,
                "active": row.active,
            }
            for row in AttentionCondition.objects.select_related("project", "instance").order_by("id")
        ]
        receipts = [
            {
                "instance_external_id": str(row.instance.external_id),
                "idempotency_key": str(row.idempotency_key),
                "sequence": row.sequence,
                "payload_digest": row.payload_digest,
                "received_at": row.received_at.isoformat(),
            }
            for row in IngestReceipt.objects.select_related("instance").order_by(
                "instance__external_id", "sequence", "id"
            )
        ]
        lifecycle_events = [
            {
                "project_external_id": str(row.project.external_id),
                "instance_external_id": str(row.instance.external_id),
                "event_key": row.event_key,
                "artifact_external_id": str(row.artifact_external_id),
                "visible_id": row.visible_id,
                "transition": row.transition,
                "from_state": row.from_state,
                "to_state": row.to_state,
                "occurred_at": row.occurred_at.isoformat(),
            }
            for row in LifecycleEvent.objects.select_related("project", "instance").order_by(
                "instance__external_id", "event_key"
            )
        ]
        payload = {
            "schema_version": 1,
            "kind": "tool-shed-dashboard-qualification-snapshot",
            "environment": "development",
            "observed_at": timezone.now().isoformat(),
            "source": {"layer": "hosted-postgresql", "authority_class": "hosted-projection"},
            "projects": projects,
            "instances": instances,
            "work_artifacts": artifacts,
            "attention_conditions": attention,
            "ingest_receipts": receipts,
            "lifecycle_events": lifecycle_events,
        }
        self.stdout.write(json.dumps(payload, separators=(",", ":"), sort_keys=True))
