from __future__ import annotations

import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from dashboard.fleet.models import AttentionCondition, Instance, Project, WorkArtifactSnapshot


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
                "document_lifecycle": row.document_lifecycle,
                "outcome_lifecycle": row.outcome_lifecycle,
                "outcome_disposition": row.outcome_disposition,
                "reconciliation_state": row.reconciliation_state,
                "closure_status": row.closure_status,
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
        }
        self.stdout.write(json.dumps(payload, separators=(",", ":"), sort_keys=True))
