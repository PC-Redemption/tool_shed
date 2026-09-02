from __future__ import annotations

import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from dashboard.fleet.models import Instance, Project


SYNTHETIC_PROJECTS = (
    (
        uuid.UUID("10000000-0000-4000-8000-000000000001"),
        uuid.UUID("20000000-0000-4000-8000-000000000001"),
        "Tool Shed Development Linux",
        "linux-x86_64",
    ),
    (
        uuid.UUID("10000000-0000-4000-8000-000000000002"),
        uuid.UUID("20000000-0000-4000-8000-000000000002"),
        "Tool Shed Development Windows",
        "windows-amd64",
    ),
)


class Command(BaseCommand):
    help = "Create optional hidden, credential-free synthetic development dashboard rows."

    def handle(self, *args, **options):
        if settings.DASHBOARD_ENVIRONMENT != "development":
            raise CommandError("synthetic dashboard seed is restricted to the development environment")
        now = timezone.now()
        for project_id, instance_id, name, platform in SYNTHETIC_PROJECTS:
            project, _ = Project.objects.update_or_create(
                external_id=project_id,
                defaults={
                    "name": name,
                    "attention_state": "unknown",
                    "current_state": {"synthetic": True, "environment": "development"},
                    "last_seen": now,
                    "last_activity_at": now,
                    "is_hidden": True,
                },
            )
            Instance.objects.update_or_create(
                project=project,
                external_id=instance_id,
                defaults={
                    "platform": platform,
                    "client_version": "development-seed",
                    "last_seen": now,
                    "quiescent": True,
                    "health_state": {"synthetic": True, "environment": "development"},
                },
            )
        self.stdout.write(
            f"development synthetic seed: {len(SYNTHETIC_PROJECTS)} hidden projects"
        )
