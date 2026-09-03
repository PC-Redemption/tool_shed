from __future__ import annotations

import json
import os
import uuid
from io import StringIO


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.config.settings")
os.environ.setdefault("TOOL_SHED_DASHBOARD_TESTING", "1")

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402
from django.core.management.base import CommandError  # noqa: E402
from django.test import TestCase, override_settings  # noqa: E402

from dashboard.fleet.management.commands.seed_dashboard_development import SYNTHETIC_PROJECTS  # noqa: E402
from dashboard.fleet.models import Instance, Project  # noqa: E402


call_command("migrate", verbosity=0)


class DashboardQualificationSnapshotTests(TestCase):
    @override_settings(DASHBOARD_ENVIRONMENT="development")
    def test_snapshot_exports_raw_hidden_and_operational_rows_without_credentials(self) -> None:
        call_command("seed_dashboard_development", verbosity=0)
        project = Project.objects.create(external_id=uuid.uuid4(), name="ts_linux_test_bed")
        Instance.objects.create(project=project, external_id=uuid.uuid4(), platform="linux-x86_64", client_version="fixture")
        output = StringIO()
        call_command("export_dashboard_qualification_snapshot", stdout=output, verbosity=0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["kind"], "tool-shed-dashboard-qualification-snapshot")
        self.assertEqual(len(payload["projects"]), 3)
        hidden = {item["external_id"] for item in payload["projects"] if item["is_hidden"]}
        self.assertEqual(hidden, {str(item[0]) for item in SYNTHETIC_PROJECTS})
        self.assertNotIn("credentials", payload)

    @override_settings(DASHBOARD_ENVIRONMENT="production")
    def test_snapshot_refuses_production(self) -> None:
        with self.assertRaisesRegex(CommandError, "restricted"):
            call_command("export_dashboard_qualification_snapshot", stdout=StringIO(), verbosity=0)
