from __future__ import annotations

import json
import os
import uuid
from datetime import timedelta
from pathlib import Path


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.config.settings")
os.environ.setdefault("TOOL_SHED_DASHBOARD_TESTING", "1")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.test import TestCase, override_settings  # noqa: E402
from django.urls import reverse  # noqa: E402
from django.utils import timezone  # noqa: E402

from dashboard.fleet.contracts import ContractError, validate_report  # noqa: E402
from dashboard.fleet.context import fleet_navigation  # noqa: E402
from dashboard.fleet.live import dashboard_revision  # noqa: E402
from dashboard.fleet.models import (  # noqa: E402
    AttentionCondition,
    Enrollment,
    Instance,
    LifecycleEvent,
    Project,
    ReporterCredential,
    WorkArtifactSnapshot,
    WorkEfficiencyAggregate,
)
from dashboard.fleet.services import _trim_efficiency_history, approve_enrollment  # noqa: E402

call_command("migrate", verbosity=0)


class DashboardApplicationTests(TestCase):
    def setUp(self) -> None:
        self.project_id = uuid.uuid4()
        self.instance_id = uuid.uuid4()
        self.epoch = uuid.uuid4()

    def enrollment_payload(self) -> dict[str, object]:
        return {
            "project_id": str(self.project_id),
            "project_name": "Fixture project",
            "instance_id": str(self.instance_id),
            "platform": "linux-x86_64",
            "client_version": "0.39.0",
        }

    def report_payload(self) -> dict[str, object]:
        now = timezone.now().isoformat()
        return {
            "schema_version": 1,
            "idempotency_key": str(uuid.uuid4()),
            "sequence": 1,
            "observed_at": now,
            "project": {"id": str(self.project_id), "name": "Fixture project"},
            "instance": {
                "id": str(self.instance_id),
                "platform": "linux-x86_64",
                "client_version": "0.39.0",
                "counter_epoch": str(self.epoch),
                "quiescent": False,
            },
            "state": {
                "working_count": 1,
                "ready_count": 2,
                "blocked_count": 0,
                "active_idea_count": 1,
                "open_outcome_count": 3,
                "unreconciled_outcome_count": 0,
                "last_completed_id": "CAMP-0131",
            },
            "material_events": [{"kind": "campaign-change", "summary_code": "campaign-started", "occurred_at": now}],
            "app_server": {
                "enabled": True,
                "availability_state": "available",
                "attempts": 10,
                "failures": 1,
                "fallbacks": 1,
                "last_success": now,
                "last_failure": now,
                "client_version": "0.200.0",
                "failure_groups": [
                    {
                        "signature": "a" * 64,
                        "category": "transport",
                        "count": 1,
                        "first_seen": now,
                        "last_seen": now,
                    }
                ],
            },
            "work_efficiency": {
                "window_start": (timezone.now() - timedelta(hours=1)).isoformat(),
                "window_end": now,
                "remedial_tokens_actual": 1200,
                "remedial_token_coverage": "0.7500",
                "remedial_interactions": 4,
                "remedial_output_bytes": 2048,
                "remedial_duration_ms": 9000,
                "remedial_retries": 1,
            },
        }

    def lifecycle_report_payload(self) -> dict[str, object]:
        payload = self.report_payload()
        observed = str(payload["observed_at"])
        artifact_id = uuid.uuid4()
        payload.update(
            {
                "schema_version": 2,
                "work_inventory": {
                    "total_count": 1,
                    "truncated": False,
                    "artifacts": [
                        {
                            "artifact_id": str(artifact_id),
                            "visible_id": "IDEA-0012",
                            "artifact_type": "idea-brief",
                            "title": "Hosted dashboard work lifecycle and history",
                            "document_lifecycle": "active",
                            "outcome_lifecycle": "working",
                            "outcome_disposition": "open",
                            "reconciliation_state": "open",
                            "parent_ids": [],
                            "produces_ids": ["MAP-0017"],
                            "updated_at": observed,
                        }
                    ],
                },
                "lifecycle_events": [
                    {
                        "event_key": "b" * 64,
                        "artifact_id": str(artifact_id),
                        "visible_id": "IDEA-0012",
                        "artifact_type": "idea-brief",
                        "title": "Hosted dashboard work lifecycle and history",
                        "transition": "document-lifecycle",
                        "from_state": "active",
                        "to_state": "completed",
                        "occurred_at": observed,
                    }
                ],
            }
        )
        return payload

    def health_report_payload(self) -> dict[str, object]:
        payload = self.lifecycle_report_payload()
        payload["schema_version"] = 4
        payload["work_inventory"]["artifacts"][0].update(  # type: ignore[index]
            {
                "planning_position": 1,
                "planning_order_source": "derived",
                "planning_readiness": "working",
            }
        )
        payload["instance_health"] = {
            "reporter_state": "delivery-delayed",
            "pending_event_count": 2,
            "last_delivery_at": (timezone.now() - timedelta(minutes=8)).isoformat(),
            "semantic_digest": "c" * 64,
            "release": {
                "installed_version": "0.40.0",
                "stable_version": "v0.39.2",
                "stable_source": "local-git-tag",
                "candidate_version": "0.40.0",
                "pending_candidate_count": 3,
                "production_version": "v0.39.0",
                "production_source": "release-cohort",
                "observed_at": timezone.now().isoformat(),
                "compatibility_state": "compatible",
                "qualification_state": "unknown",
            },
        }
        return payload

    def release_chain_report_payload(self) -> dict[str, object]:
        payload = self.health_report_payload()
        payload["schema_version"] = 5
        payload["instance_health"]["release"].update(  # type: ignore[index]
            {
                "awaiting_work5_chain_count": 1,
                "candidate_commit_count": 2,
                "registration_count": 4,
                "release_chains_truncated": False,
                "release_chains": [
                    {
                        "root_id": "IDEA-0012",
                        "idea_id": "IDEA-0012",
                        "map_id": "MAP-0017",
                        "prm_id": "PRM-0028",
                        "campaign_id": "CAMP-0136",
                        "stage": "awaiting-work5",
                        "latest_commit": "a" * 40,
                        "candidate_count": 2,
                    }
                ],
            }
        )
        return payload

    def enroll_and_issue(self) -> str:
        created = self.client.post(
            reverse("fleet:enrollment-request"),
            data=json.dumps(self.enrollment_payload()),
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 202)
        body = created.json()
        user = get_user_model().objects.create_user("operator", password="fixture", is_staff=True)
        approve_enrollment(Enrollment.objects.get(id=body["request_id"]), user, approved=True)
        issued = self.client.post(
            reverse("fleet:enrollment-poll", args=(body["request_id"],)),
            HTTP_X_TOOL_SHED_DEVICE_SECRET=body["device_secret"],
        )
        self.assertEqual(issued.status_code, 200)
        self.assertEqual(issued.json()["status"], "issued")
        replay = self.client.post(
            reverse("fleet:enrollment-poll", args=(body["request_id"],)),
            HTTP_X_TOOL_SHED_DEVICE_SECRET=body["device_secret"],
        )
        self.assertEqual(replay.json()["status"], "issued")
        self.assertNotIn("reporter_token", replay.json())
        return issued.json()["reporter_token"]

    def test_contract_rejects_unknown_and_raw_diagnostic_fields(self) -> None:
        payload = self.report_payload()
        payload["source_path"] = "/private/project"
        with self.assertRaisesRegex(ContractError, "unsupported fields"):
            validate_report(payload)
        payload = self.health_report_payload()
        payload["instance_health"]["raw_diagnostic"] = "private host detail"  # type: ignore[index]
        with self.assertRaisesRegex(ContractError, "unsupported fields"):
            validate_report(payload)
        payload = self.report_payload()
        payload["app_server"]["raw_error"] = "secret diagnostic"  # type: ignore[index]
        with self.assertRaisesRegex(ContractError, "unsupported fields"):
            validate_report(payload)

    def test_enrollment_issues_one_revocable_verifier_only_token(self) -> None:
        token = self.enroll_and_issue()
        credential = ReporterCredential.objects.get()
        self.assertNotEqual(credential.token_digest, token)
        self.assertEqual(credential.token_prefix, token[:12])
        self.assertTrue(credential.active)

    def test_maintainer_can_match_and_approve_enrollment_code_in_dashboard(self) -> None:
        created = self.client.post(
            reverse("fleet:enrollment-request"),
            data=json.dumps(self.enrollment_payload()),
            content_type="application/json",
        ).json()
        user = get_user_model().objects.create_user("approver", password="fixture", is_staff=True)
        self.client.force_login(user)
        page = self.client.get(reverse("fleet:enrollments"))
        self.assertContains(page, created["user_code"])
        decision = self.client.post(
            reverse("fleet:enrollment-decision-ui", args=(created["request_id"],)),
            {"decision": "approve"},
        )
        self.assertRedirects(decision, reverse("fleet:enrollments"))
        self.assertEqual(Enrollment.objects.get(id=created["request_id"]).status, Enrollment.Status.APPROVED)

    def test_ingestion_is_identity_bound_idempotent_and_projects_current_state(self) -> None:
        token = self.enroll_and_issue()
        payload = self.report_payload()
        accepted = self.client.post(
            reverse("fleet:report-ingest"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(accepted.status_code, 200, accepted.content)
        self.assertEqual(accepted.json(), {"schema_version": 1, "status": "accepted", "sequence": 1})
        duplicate = self.client.post(
            reverse("fleet:report-ingest"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(duplicate.json()["status"], "duplicate")
        changed = dict(payload)
        changed["sequence"] = 2
        conflict = self.client.post(
            reverse("fleet:report-ingest"),
            data=json.dumps(changed),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(conflict.status_code, 409)

    def test_ingestion_records_work_efficiency_only_when_metrics_change(self) -> None:
        token = self.enroll_and_issue()
        first = self.report_payload()
        response = self.client.post(
            reverse("fleet:report-ingest"),
            data=json.dumps(first),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200, response.content)

        unchanged = self.report_payload()
        unchanged["sequence"] = 2
        response = self.client.post(
            reverse("fleet:report-ingest"),
            data=json.dumps(unchanged),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(WorkEfficiencyAggregate.objects.count(), 1)

        changed = self.report_payload()
        changed["sequence"] = 3
        changed["work_efficiency"]["remedial_interactions"] = 5  # type: ignore[index]
        response = self.client.post(
            reverse("fleet:report-ingest"),
            data=json.dumps(changed),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(WorkEfficiencyAggregate.objects.count(), 2)

    def test_attention_conditions_are_controlled_change_only_and_clear_deterministically(self) -> None:
        token = self.enroll_and_issue()
        opened = self.report_payload()
        opened["state"]["blocked_count"] = 2  # type: ignore[index]
        opened["state"]["unreconciled_outcome_count"] = 1  # type: ignore[index]
        opened["app_server"]["availability_state"] = "unavailable"  # type: ignore[index]
        before_revision = dashboard_revision()
        response = self.client.post(
            reverse("fleet:report-ingest"),
            data=json.dumps(opened),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            set(AttentionCondition.objects.filter(active=True).values_list("reason_code", flat=True)),
            {"blocked-work", "unreconciled-outcomes", "app-server-failure"},
        )
        self.assertNotEqual(dashboard_revision(), before_revision)
        changed_at = {
            item.reason_code: item.last_changed for item in AttentionCondition.objects.filter(active=True)
        }

        unchanged = self.report_payload()
        unchanged["sequence"] = 2
        unchanged["material_events"] = []
        unchanged["state"]["blocked_count"] = 2  # type: ignore[index]
        unchanged["state"]["unreconciled_outcome_count"] = 1  # type: ignore[index]
        unchanged["app_server"]["availability_state"] = "unavailable"  # type: ignore[index]
        response = self.client.post(
            reverse("fleet:report-ingest"),
            data=json.dumps(unchanged),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(AttentionCondition.objects.count(), 3)
        self.assertEqual(
            {item.reason_code: item.last_changed for item in AttentionCondition.objects.filter(active=True)},
            changed_at,
        )

        user = get_user_model().objects.create_user("attention-viewer", password="fixture")
        self.client.force_login(user)
        overview = self.client.get(reverse("fleet:overview"), {"state": "attention"})
        self.assertContains(overview, "Blocked work")
        self.assertContains(overview, "Unreconciled outcomes")
        self.assertContains(overview, "App Server needs attention")
        self.assertContains(overview, "Investigate locally: <code>ts: status</code>", html=True)
        self.client.logout()

        cleared = self.report_payload()
        cleared["sequence"] = 3
        cleared["material_events"] = []
        cleared["app_server"]["failures"] = 0  # type: ignore[index]
        cleared["app_server"]["last_failure"] = None  # type: ignore[index]
        response = self.client.post(
            reverse("fleet:report-ingest"),
            data=json.dumps(cleared),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(AttentionCondition.objects.filter(active=True).count(), 0)
        self.assertEqual(AttentionCondition.objects.filter(resolved_at__isnull=False).count(), 3)

        self.client.force_login(user)
        project = Project.objects.get(external_id=self.project_id)
        history = self.client.get(reverse("fleet:project-tab", args=(project.id, "history")))
        self.assertContains(history, "Recent Changes")
        self.assertContains(history, "Resolved · This instance reports blocked Tool Shed work.")
        self.assertContains(history, "Campaign started")
        self.assertContains(history, "Reporter credential issued")
        self.assertContains(history, "Transport failure")
        self.assertNotContains(history, token[:12])
        self.assertContains(history, 'data-project-key="')

    def test_stale_instance_attention_preserves_source_and_safe_route(self) -> None:
        user = get_user_model().objects.create_user("stale-attention-viewer", password="fixture")
        self.client.force_login(user)
        project = Project.objects.create(external_id=uuid.uuid4(), name="Stale source")
        instance = Instance.objects.create(
            project=project,
            external_id=uuid.uuid4(),
            platform="linux",
            client_version="0.40.0",
            last_seen=timezone.now() - timedelta(minutes=25),
        )
        response = self.client.get(reverse("fleet:overview"), {"state": "stale"})
        self.assertContains(response, "Reporter stale or offline")
        self.assertContains(response, str(instance.external_id))
        self.assertContains(response, "ts: dashboard status")

    def test_schema_two_projects_per_instance_work_and_change_only_history(self) -> None:
        token = self.enroll_and_issue()
        payload = self.lifecycle_report_payload()
        response = self.client.post(
            reverse("fleet:report-ingest"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        instance = Instance.objects.get()
        self.assertEqual(instance.report_schema_version, 2)
        self.assertEqual(instance.work_inventory_total, 1)
        self.assertFalse(instance.work_inventory_truncated)
        self.assertEqual(WorkArtifactSnapshot.objects.get().visible_id, "IDEA-0012")
        self.assertEqual(LifecycleEvent.objects.get().to_state, "completed")

        user = get_user_model().objects.create_user("lifecycle-viewer", password="fixture")
        self.client.force_login(user)
        work = self.client.get(reverse("fleet:project-tab", args=(instance.project_id, "work")))
        self.assertContains(work, "IDEA-0012")
        self.assertContains(work, "MAP-0017")
        history = self.client.get(reverse("fleet:project-tab", args=(instance.project_id, "history")))
        self.assertContains(history, "active → completed")

    def test_schema_three_ingests_local_planning_projection(self) -> None:
        token = self.enroll_and_issue()
        payload = self.lifecycle_report_payload()
        payload["schema_version"] = 3
        artifact = payload["work_inventory"]["artifacts"][0]
        artifact.update(
            {
                "planning_position": 2,
                "planning_order_source": "owner",
                "planning_readiness": "working",
            }
        )
        response = self.client.post(
            reverse("fleet:report-ingest"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        snapshot = WorkArtifactSnapshot.objects.get()
        self.assertEqual(snapshot.planning_position, 2)
        self.assertEqual(snapshot.planning_order_source, "owner")
        self.assertEqual(snapshot.planning_readiness, "working")

    def test_schema_four_projects_instance_health_and_semantic_divergence(self) -> None:
        token = self.enroll_and_issue()
        payload = self.health_report_payload()
        response = self.client.post(
            reverse("fleet:report-ingest"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        instance = Instance.objects.get()
        self.assertEqual(instance.report_schema_version, 4)
        self.assertEqual(instance.health_state["reporter_state"], "delivery-delayed")
        self.assertEqual(instance.health_state["release"]["production_version"], "v0.39.0")

        legacy = self.report_payload()
        legacy["sequence"] = 2
        legacy["material_events"] = []
        response = self.client.post(
            reverse("fleet:report-ingest"),
            data=json.dumps(legacy),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        instance.refresh_from_db()
        self.assertEqual(instance.report_schema_version, 4)
        self.assertEqual(instance.health_state["semantic_digest"], "c" * 64)

    def test_schema_five_validates_and_stores_chain_level_release_projection(self) -> None:
        token = self.enroll_and_issue()
        payload = self.release_chain_report_payload()
        validated = validate_report(payload)
        self.assertEqual(
            validated["instance_health"]["release"]["awaiting_work5_chain_count"], 1
        )
        response = self.client.post(
            reverse("fleet:report-ingest"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        instance = Instance.objects.get()
        release = instance.health_state["release"]
        self.assertEqual(release["candidate_commit_count"], 2)
        self.assertEqual(release["registration_count"], 4)
        self.assertEqual(release["release_chains"][0]["root_id"], "IDEA-0012")

        second = Instance.objects.create(
            project=instance.project,
            external_id=uuid.uuid4(),
            platform="windows-amd64",
            client_version="0.39.2",
            report_schema_version=4,
            last_seen=timezone.now(),
            health_state={
                "reporter_state": "active",
                "pending_event_count": 0,
                "last_delivery_at": timezone.now().isoformat(),
                "semantic_digest": "d" * 64,
                "release": {
                    "installed_version": "0.39.2",
                    "stable_version": "v0.39.2",
                    "stable_source": "local-git-tag",
                    "candidate_version": None,
                    "pending_candidate_count": 0,
                    "production_version": "v0.39.0",
                    "production_source": "release-cohort",
                    "observed_at": timezone.now().isoformat(),
                    "compatibility_state": "compatible",
                    "qualification_state": "qualified",
                },
            },
        )
        user = get_user_model().objects.create_user("health-viewer", password="fixture")
        self.client.force_login(user)
        health = self.client.get(reverse("fleet:project-tab", args=(instance.project_id, "health")))
        self.assertContains(health, "Instance Health")
        self.assertContains(health, "Delivery-delayed")
        self.assertContains(health, "Divergent")
        self.assertContains(health, "Candidate")
        self.assertContains(health, str(second.external_id))

        before = dashboard_revision()
        second.health_state["last_delivery_at"] = (timezone.now() + timedelta(minutes=1)).isoformat()
        second.health_state["release"]["observed_at"] = (timezone.now() + timedelta(minutes=1)).isoformat()
        second.save(update_fields=("health_state", "updated_at"))
        self.assertEqual(dashboard_revision(), before)
        second.health_state["reporter_state"] = "quiescent"
        second.save(update_fields=("health_state", "updated_at"))
        self.assertNotEqual(dashboard_revision(), before)

    def test_work_table_is_newest_first_and_supports_bounded_page_sizes(self) -> None:
        user = get_user_model().objects.create_user("work-table-viewer", password="fixture")
        self.client.force_login(user)
        project = Project.objects.create(external_id=uuid.uuid4(), name="Paginated work")
        instance = Instance.objects.create(
            project=project,
            external_id=uuid.uuid4(),
            platform="linux",
            client_version="0.40.0",
            report_schema_version=2,
            work_inventory_total=25,
        )
        observed = timezone.now()
        for number in range(1, 26):
            WorkArtifactSnapshot.objects.create(
                project=project,
                instance=instance,
                artifact_external_id=uuid.uuid4(),
                visible_id=f"CAMP-{number:04d}",
                artifact_type="campaign",
                title=f"Campaign {number}",
                document_lifecycle="completed",
                outcome_lifecycle="terminal",
                outcome_disposition=(
                    "satisfied-with-approved-change" if number == 25 else "satisfied"
                ),
                reconciliation_state="reconciled",
                source_updated_at=observed + timedelta(minutes=number),
                observed_at=observed,
                snapshot_sequence=1,
            )
        url = reverse("fleet:project-tab", args=(project.id, "work"))

        first = self.client.get(url)
        self.assertContains(first, '<option value="20" selected>20</option>', html=True)
        self.assertEqual(first.content.count(b'class="artifact-id"'), 20)
        self.assertContains(first, "CAMP-0025")
        self.assertContains(first, "CAMP-0006")
        self.assertNotContains(first, "CAMP-0005")
        self.assertLess(first.content.index(b"CAMP-0025"), first.content.index(b"CAMP-0006"))
        self.assertContains(first, 'class="project-summary-bar"')
        self.assertContains(first, 'class="dashboard-panel compact-table-panel"')
        self.assertContains(first, 'class="table-toolbar"')
        self.assertContains(first, 'class="artifact-title"')
        self.assertContains(first, "Open outcomes")
        self.assertContains(first, "Approved change")
        self.assertContains(first, 'class="table-state table-state-terminal"')
        self.assertContains(first, 'class="table-state table-state-reconciled"')
        self.assertContains(first, '<select name="type" data-auto-submit>')
        self.assertContains(first, '<select name="rows" data-auto-submit>')
        self.assertContains(first, "Apply status")
        self.assertContains(first, 'aria-label="Work table pages (top)"', count=1)
        self.assertContains(first, 'aria-label="Work table pages (bottom)"', count=1)

        second = self.client.get(url, {"page": 2})
        self.assertContains(second, 'aria-current="page">2</span>')
        self.assertContains(second, "CAMP-0005")
        self.assertNotContains(second, "CAMP-0025")

        ten = self.client.get(url, {"rows": "10"})
        self.assertEqual(ten.content.count(b'class="artifact-id"'), 10)
        self.assertContains(ten, "Showing 1–10 of 25")

        all_rows = self.client.get(url, {"rows": "all"})
        self.assertEqual(all_rows.content.count(b'class="artifact-id"'), 25)
        self.assertContains(all_rows, "CAMP-0001")
        self.assertContains(all_rows, "Showing all 25")

        invalid = self.client.get(url, {"rows": "500"})
        self.assertContains(invalid, '<option value="20" selected>20</option>', html=True)

    def test_idea_planning_order_is_reported_by_local_instance_and_read_only(self) -> None:
        user = get_user_model().objects.create_user("planning-viewer", password="fixture")
        self.client.force_login(user)
        project = Project.objects.create(external_id=uuid.uuid4(), name="Reported planning order")
        instance = Instance.objects.create(
            project=project,
            external_id=uuid.uuid4(),
            platform="linux",
            client_version="0.41.0",
            report_schema_version=3,
            work_inventory_total=2,
        )
        observed = timezone.now()
        for number, position, source in ((1, 2, "derived"), (2, 1, "owner")):
            WorkArtifactSnapshot.objects.create(
                project=project,
                instance=instance,
                artifact_external_id=uuid.uuid4(),
                visible_id=f"IDEA-{number:04d}",
                artifact_type="idea-brief",
                title=f"Idea {number}",
                document_lifecycle="active",
                planning_position=position,
                planning_order_source=source,
                planning_readiness="ready",
                source_updated_at=observed + timedelta(minutes=number),
                observed_at=observed,
                snapshot_sequence=1,
            )
        url = reverse("fleet:project-tab", args=(project.id, "work"))
        response = self.client.get(url, {"type": "idea-brief"})
        self.assertEqual(response.status_code, 200)
        self.assertLess(response.content.index(b"IDEA-0002"), response.content.index(b"IDEA-0001"))
        self.assertContains(response, "Local planning order")
        self.assertContains(response, "Owner · Ready")
        self.assertContains(response, "this dashboard cannot change execution priority")
        self.assertNotContains(response, "Reset to suggested")

    def test_history_table_is_newest_first_and_uses_work_paging_model(self) -> None:
        user = get_user_model().objects.create_user("history-table-viewer", password="fixture")
        self.client.force_login(user)
        project = Project.objects.create(external_id=uuid.uuid4(), name="Paginated history")
        instance = Instance.objects.create(
            project=project,
            external_id=uuid.uuid4(),
            platform="linux",
            client_version="0.40.0",
            report_schema_version=2,
        )
        observed = timezone.now()
        for number in range(1, 26):
            LifecycleEvent.objects.create(
                project=project,
                instance=instance,
                event_key=f"history-{number}",
                artifact_external_id=uuid.uuid4(),
                visible_id=f"CAMP-{number:04d}",
                artifact_type="campaign",
                title=f"History {number}",
                transition="document",
                from_state="working",
                to_state="completed",
                occurred_at=observed + timedelta(minutes=number),
                retained_until=observed + timedelta(days=30),
            )
        url = reverse("fleet:project-tab", args=(project.id, "history"))

        first = self.client.get(url)
        self.assertContains(first, '<option value="20" selected>20</option>', html=True)
        self.assertEqual(first.content.count(b"data-change-at="), 20)
        self.assertContains(first, "CAMP-0025")
        self.assertContains(first, "CAMP-0006")
        self.assertNotContains(first, "CAMP-0005")
        self.assertLess(first.content.index(b"CAMP-0025"), first.content.index(b"CAMP-0006"))
        self.assertContains(first, "Showing 1–20 of 25")
        self.assertContains(first, '<select name="rows" data-auto-submit>')
        self.assertNotContains(first, "Apply status")
        self.assertContains(first, 'aria-label="History table pages (top)"', count=1)
        self.assertContains(first, 'aria-label="History table pages (bottom)"', count=1)

        second = self.client.get(url, {"page": 2})
        self.assertContains(second, 'aria-current="page">2</span>')
        self.assertContains(second, "CAMP-0005")
        self.assertNotContains(second, "CAMP-0025")

        ten = self.client.get(url, {"rows": "10"})
        self.assertEqual(ten.content.count(b"data-change-at="), 10)
        self.assertContains(ten, "Showing 1–10 of 25")

        all_rows = self.client.get(url, {"rows": "all"})
        self.assertEqual(all_rows.content.count(b"data-change-at="), 25)
        self.assertContains(all_rows, "Showing all 25")

        invalid = self.client.get(url, {"rows": "500"})
        self.assertContains(invalid, '<option value="20" selected>20</option>', html=True)

    def test_reporter_credential_is_required(self) -> None:
        response = self.client.post(
            reverse("fleet:report-ingest"),
            data=json.dumps(self.report_payload()),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_health_is_public_and_contains_no_runtime_detail(self) -> None:
        response = self.client.get(reverse("fleet:health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"status", "service", "schema_version"})

    def test_login_uses_password_and_otp_fields(self) -> None:
        response = self.client.get(reverse("login"))
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, 'name="otp_token"')

    @override_settings(DASHBOARD_AUTH_MODE="local-password")
    def test_password_only_login_omits_otp_field(self) -> None:
        response = self.client.get(reverse("login"))
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertNotContains(response, 'name="otp_token"')

    def test_authenticated_views_render_unknown_aggregates_and_filter_projects(self) -> None:
        user = get_user_model().objects.create_user("viewer", password="fixture")
        self.client.force_login(user)
        first = Project.objects.create(external_id=uuid.uuid4(), name="Alpha", attention_state="working")
        second = Project.objects.create(external_id=uuid.uuid4(), name="Beta", attention_state="attention")
        Instance.objects.create(project=first, external_id=uuid.uuid4(), platform="linux", client_version="0.39.0")
        response = self.client.get(reverse("fleet:overview"), {"state": "attention"})
        self.assertContains(response, "/dashboard/static/fleet/dashboard.js?v=")
        self.assertContains(response, "/dashboard/static/fleet/dashboard.css?v=")
        self.assertContains(response, f'data-dashboard-stream-url="{reverse("fleet:events")}"')
        self.assertContains(response, "data-dashboard-revision=")
        self.assertContains(response, "Beta")
        self.assertNotContains(response, "Alpha</a></th>")
        response = self.client.get(reverse("fleet:overview"), {"q": "Alpha"})
        self.assertContains(response, "Alpha")
        response = self.client.get(reverse("fleet:app-server"))
        self.assertContains(response, "Unknown")
        response = self.client.get(reverse("fleet:work-efficiency"))
        self.assertContains(response, "No efficiency windows reported")

    def test_fleet_search_uses_bounded_reported_work_filters_and_stable_pages(self) -> None:
        user = get_user_model().objects.create_user("fleet-search-viewer", password="fixture")
        self.client.force_login(user)
        now = timezone.now()
        alpha = Project.objects.create(
            external_id=uuid.uuid4(), name="Alpha", last_seen=now, last_activity_at=now
        )
        beta = Project.objects.create(
            external_id=uuid.uuid4(), name="Beta", last_seen=now, last_activity_at=now - timedelta(minutes=1)
        )
        alpha_instance = Instance.objects.create(
            project=alpha,
            external_id=uuid.uuid4(),
            platform="linux-x86_64",
            client_version="0.40.0",
        )
        beta_instance = Instance.objects.create(
            project=beta,
            external_id=uuid.uuid4(),
            platform="windows-amd64",
            client_version="0.39.2",
        )
        for project, instance, visible_id, artifact_type, title, lifecycle in (
            (alpha, alpha_instance, "IDEA-0015", "idea-brief", "Cross-project operator search", "active"),
            (beta, beta_instance, "PRM-0032", "program-roadmap", "Bounded trend exports", "completed"),
        ):
            WorkArtifactSnapshot.objects.create(
                project=project,
                instance=instance,
                artifact_external_id=uuid.uuid4(),
                visible_id=visible_id,
                artifact_type=artifact_type,
                title=title,
                document_lifecycle=lifecycle,
                source_updated_at=now,
                observed_at=now,
                snapshot_sequence=1,
            )

        by_identifier = self.client.get(reverse("fleet:overview"), {"q": "IDEA-0015", "rows": "10"})
        self.assertContains(by_identifier, "Alpha")
        self.assertNotContains(by_identifier, "Beta</a></th>")
        self.assertContains(by_identifier, "IDEA-0015")
        self.assertContains(by_identifier, "filters affect presentation only")

        by_filters = self.client.get(
            reverse("fleet:overview"),
            {"type": "program-roadmap", "lifecycle": "completed", "version": "0.39.2", "rows": "20"},
        )
        self.assertContains(by_filters, "Beta")
        self.assertNotContains(by_filters, "Alpha</a></th>")
        self.assertContains(by_filters, '<option value="20" selected>20</option>', html=True)

    def test_work_efficiency_filters_exports_and_retention_are_bounded(self) -> None:
        user = get_user_model().objects.create_user("efficiency-exporter", password="fixture")
        self.client.force_login(user)
        project = Project.objects.create(external_id=uuid.uuid4(), name="Exportable")
        instance = Instance.objects.create(
            project=project,
            external_id=uuid.uuid4(),
            platform="linux-x86_64",
            client_version="0.40.0",
            counter_epoch=self.epoch,
        )
        now = timezone.now()
        for offset in range(3):
            WorkEfficiencyAggregate.objects.create(
                instance=instance,
                counter_epoch=self.epoch,
                window_start=now - timedelta(hours=offset + 1),
                window_end=now - timedelta(hours=offset),
                remedial_tokens_actual=100 + offset,
                remedial_token_coverage="0.7500",
                remedial_interactions=offset,
                remedial_output_bytes=200 + offset,
                remedial_duration_ms=300 + offset,
                remedial_retries=offset,
            )

        page = self.client.get(
            reverse("fleet:work-efficiency"),
            {"window": "24h", "project": str(project.id), "platform": "linux-x86_64", "version": "0.40.0"},
        )
        self.assertContains(page, "3 semantic changes")
        self.assertContains(page, "Export CSV")
        self.assertContains(page, "counter epoch remains separate")

        exported = self.client.get(
            reverse("fleet:work-efficiency"),
            {"window": "24h", "project": str(project.id), "format": "json"},
        )
        payload = exported.json()
        self.assertEqual(exported["Content-Disposition"], 'attachment; filename="tool-shed-work-efficiency.json"')
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(len(payload["rows"]), 3)
        self.assertEqual(payload["filters"]["project"], str(project.id))
        self.assertEqual(
            set(payload["rows"][0]),
            {
                "project", "project_id", "instance_id", "platform", "client_version", "counter_epoch",
                "window_start", "window_end", "remedial_tokens_actual", "remedial_token_coverage",
                "remedial_interactions", "remedial_output_bytes", "remedial_duration_ms", "remedial_retries",
            },
        )

        self.assertEqual(_trim_efficiency_history(instance, self.epoch, retention=2), 1)
        self.assertEqual(WorkEfficiencyAggregate.objects.filter(instance=instance).count(), 2)

    def test_project_navigation_orders_activity_filters_freshness_and_toggles_visibility(self) -> None:
        user = get_user_model().objects.create_user("project-nav-viewer", password="fixture")
        self.client.force_login(user)
        now = timezone.now()
        alpha = Project.objects.create(
            external_id=uuid.uuid4(),
            name="Alpha",
            last_seen=now,
            last_activity_at=now - timedelta(minutes=5),
        )
        beta = Project.objects.create(
            external_id=uuid.uuid4(),
            name="Beta",
            last_seen=now,
            last_activity_at=now,
        )
        stale = Project.objects.create(
            external_id=uuid.uuid4(),
            name="Stale",
            last_seen=now - timedelta(minutes=30),
            last_activity_at=now + timedelta(minutes=1),
        )
        hidden = Project.objects.create(
            external_id=uuid.uuid4(),
            name="Hidden",
            last_seen=now,
            last_activity_at=now + timedelta(minutes=2),
            is_hidden=True,
        )

        response = self.client.get(reverse("fleet:overview"))
        navigation = fleet_navigation(response.wsgi_request)
        self.assertEqual([project.id for project in navigation["fleet_projects"]], [beta.id, alpha.id])
        self.assertContains(response, "Active now")
        self.assertContains(response, "Show hidden")

        preferences = self.client.post(
            reverse("fleet:project-navigation-preferences"),
            {"project_scope": "all", "show_hidden": "1", "next": reverse("fleet:overview")},
        )
        self.assertRedirects(preferences, reverse("fleet:overview"))
        response = self.client.get(reverse("fleet:overview"))
        navigation = fleet_navigation(response.wsgi_request)
        self.assertEqual(
            [project.id for project in navigation["fleet_projects"]],
            [hidden.id, stale.id, beta.id, alpha.id],
        )

        toggled = self.client.post(
            reverse("fleet:project-visibility", args=(beta.id,)),
            {"action": "hide", "next": reverse("fleet:overview")},
        )
        self.assertRedirects(toggled, reverse("fleet:overview"))
        beta.refresh_from_db()
        self.assertTrue(beta.is_hidden)

        self.client.post(
            reverse("fleet:project-navigation-preferences"),
            {"project_scope": "all", "next": reverse("fleet:overview")},
        )
        response = self.client.get(reverse("fleet:overview"))
        nav_ids = [project.id for project in fleet_navigation(response.wsgi_request)["fleet_projects"]]
        self.assertNotIn(beta.id, nav_ids)
        self.assertNotIn(hidden.id, nav_ids)

        self.client.post(
            reverse("fleet:project-visibility", args=(beta.id,)),
            {"action": "show", "next": reverse("fleet:overview")},
        )
        beta.refresh_from_db()
        self.assertFalse(beta.is_hidden)

    def test_project_overview_presents_latest_instance_operator_snapshot(self) -> None:
        user = get_user_model().objects.create_user("overview-operator", password="fixture")
        self.client.force_login(user)
        now = timezone.now()
        project = Project.objects.create(
            external_id=uuid.uuid4(),
            name="Operator project",
            attention_state="healthy",
            current_state={"open_outcome_count": 5, "unreconciled_outcome_count": 0},
            last_seen=now,
        )
        older = Instance.objects.create(
            project=project,
            external_id=uuid.uuid4(),
            platform="windows-amd64",
            client_version="0.39.2",
            work_inventory_observed_at=now - timedelta(hours=1),
        )
        latest = Instance.objects.create(
            project=project,
            external_id=uuid.uuid4(),
            platform="linux-x86_64",
            client_version="0.40.0",
            last_seen=now,
            work_inventory_observed_at=now,
            health_state={
                "reporter_state": "active",
                "semantic_digest": "d" * 64,
                "release": {
                    "installed_version": "0.40.0",
                    "stable_version": "v0.39.2",
                    "candidate_version": "0.40.0",
                    "pending_candidate_count": 2,
                    "awaiting_work5_chain_count": 1,
                    "candidate_commit_count": 2,
                    "registration_count": 4,
                    "release_chains_truncated": False,
                    "release_chains": [
                        {
                            "root_id": "IDEA-0100",
                            "idea_id": "IDEA-0100",
                            "map_id": "MAP-0100",
                            "prm_id": "PRM-0100",
                            "campaign_id": "CAMP-0100",
                            "stage": "awaiting-work5",
                            "latest_commit": "e" * 40,
                            "candidate_count": 2,
                        }
                    ],
                },
            },
        )
        WorkArtifactSnapshot.objects.create(
            project=project,
            instance=older,
            artifact_external_id=uuid.uuid4(),
            visible_id="IDEA-OLD",
            artifact_type="idea-brief",
            title="Old reporter work",
            document_lifecycle="active",
            outcome_lifecycle="working",
            outcome_disposition="open",
            reconciliation_state="open",
            source_updated_at=now - timedelta(hours=1),
            observed_at=now - timedelta(hours=1),
            snapshot_sequence=1,
        )
        chain = (
            ("IDEA-0100", "idea-brief", "Operator overview", [], ["MAP-0100"], 1),
            ("MAP-0100", "project-map", "Operator overview map", ["IDEA-0100"], ["PRM-0100"], None),
            ("PRM-0100", "program-roadmap", "Operator overview roadmap", ["MAP-0100"], ["CAMP-0100"], 1),
            ("CAMP-0100", "campaign", "Implement operator overview", ["PRM-0100"], [], None),
        )
        for visible_id, artifact_type, title, parents, produces, position in chain:
            WorkArtifactSnapshot.objects.create(
                project=project,
                instance=latest,
                artifact_external_id=uuid.uuid4(),
                visible_id=visible_id,
                artifact_type=artifact_type,
                title=title,
                document_lifecycle="working" if artifact_type == "campaign" else "active",
                outcome_lifecycle="working",
                outcome_disposition="open",
                reconciliation_state="open",
                parent_ids=parents,
                produces_ids=produces,
                planning_position=position,
                planning_order_source="owner" if position else "not-applicable",
                planning_readiness="working" if position else "not-applicable",
                source_updated_at=now,
                observed_at=now,
                snapshot_sequence=2,
            )
        LifecycleEvent.objects.create(
            project=project,
            instance=latest,
            event_key="f" * 64,
            artifact_external_id=uuid.uuid4(),
            visible_id="CAMP-0100",
            artifact_type="campaign",
            title="Implement operator overview",
            transition="document-lifecycle",
            from_state="queued",
            to_state="working",
            occurred_at=now,
            retained_until=now + timedelta(days=30),
        )

        response = self.client.get(reverse("fleet:project", args=(project.id,)))
        self.assertEqual(response.status_code, 200)
        for heading in (
            "Awaiting Work5",
            "Active work chains",
            "Next up",
            "Open outcomes",
            "Lifecycle summary",
            "Reporting & release",
            "Recent meaningful changes",
        ):
            self.assertContains(response, heading)
        self.assertContains(response, "IDEA-0100")
        self.assertContains(response, "MAP-0100")
        self.assertContains(response, "PRM-0100")
        self.assertContains(response, "CAMP-0100")
        self.assertNotContains(response, "IDEA-OLD")
        self.assertContains(response, "4 open loops")
        self.assertContains(response, "additional reported loop")
        self.assertContains(response, "Owner")
        self.assertContains(response, "Snapshot from")
        self.assertContains(response, "document-lifecycle: queued → working")
        self.assertContains(response, "1</strong><span>Idea chains")
        self.assertContains(response, "2</strong><span>Candidate commits")
        self.assertContains(response, "4</strong><span>Audit registrations")

        work = self.client.get(
            reverse("fleet:project-tab", args=(project.id, "work")),
            {"release_stage": "awaiting-work5"},
        )
        self.assertEqual(work.status_code, 200)
        self.assertContains(work, "Release stage")
        self.assertContains(work, "Awaiting Work5", count=5)
        self.assertContains(work, "IDEA-0100")

    def test_project_activity_changes_only_for_material_report_updates(self) -> None:
        token = self.enroll_and_issue()
        first = self.lifecycle_report_payload()
        response = self.client.post(
            reverse("fleet:report-ingest"),
            data=json.dumps(first),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        project = Project.objects.get(external_id=self.project_id)
        first_activity = project.last_activity_at
        self.assertEqual(first_activity.isoformat(), first["observed_at"])

        unchanged = json.loads(json.dumps(first))
        unchanged["idempotency_key"] = str(uuid.uuid4())
        unchanged["sequence"] = 2
        unchanged["observed_at"] = (timezone.now() + timedelta(minutes=1)).isoformat()
        unchanged["material_events"] = []
        unchanged["lifecycle_events"] = []
        response = self.client.post(
            reverse("fleet:report-ingest"),
            data=json.dumps(unchanged),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        project.refresh_from_db()
        self.assertEqual(project.last_activity_at, first_activity)
        self.assertEqual(project.last_seen.isoformat(), unchanged["observed_at"])

        changed = json.loads(json.dumps(unchanged))
        changed["idempotency_key"] = str(uuid.uuid4())
        changed["sequence"] = 3
        changed["observed_at"] = (timezone.now() + timedelta(minutes=2)).isoformat()
        changed["work_inventory"]["artifacts"][0]["document_lifecycle"] = "completed"
        response = self.client.post(
            reverse("fleet:report-ingest"),
            data=json.dumps(changed),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        project.refresh_from_db()
        self.assertEqual(project.last_activity_at.isoformat(), changed["observed_at"])

    def test_work_efficiency_view_hides_existing_unchanged_windows(self) -> None:
        user = get_user_model().objects.create_user("efficiency-viewer", password="fixture")
        self.client.force_login(user)
        project = Project.objects.create(external_id=uuid.uuid4(), name="Efficiency")
        instance = Instance.objects.create(
            project=project,
            external_id=uuid.uuid4(),
            platform="linux",
            client_version="0.39.0",
            counter_epoch=self.epoch,
        )
        now = timezone.now()
        metrics = {
            "remedial_tokens_actual": 1200,
            "remedial_token_coverage": "0.7500",
            "remedial_interactions": 4,
            "remedial_output_bytes": 2048,
            "remedial_duration_ms": 9000,
            "remedial_retries": 1,
        }
        for offset in (2, 1):
            WorkEfficiencyAggregate.objects.create(
                instance=instance,
                counter_epoch=self.epoch,
                window_start=now - timedelta(hours=offset + 1),
                window_end=now - timedelta(hours=offset),
                **metrics,
            )
        response = self.client.get(reverse("fleet:work-efficiency"))
        self.assertContains(response, ">1200<", count=1)
        self.assertContains(response, "Unchanged sliding-window reports are suppressed")

    def test_dashboard_event_stream_announces_a_stale_revision(self) -> None:
        user = get_user_model().objects.create_user("stream-viewer", password="fixture")
        self.client.force_login(user)
        response = self.client.get(reverse("fleet:events"), {"since": "stale"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        self.assertEqual(response["Cache-Control"], "no-cache, no-transform")
        self.assertEqual(response["X-Accel-Buffering"], "no")
        chunks = iter(response.streaming_content)
        payload = next(chunks) + next(chunks)
        self.assertIn(b"retry: 5000", payload)
        self.assertIn(b"event: dashboard-update", payload)

    @override_settings(
        DASHBOARD_SSE_MAX_SECONDS=0.01,
        DASHBOARD_SSE_POLL_SECONDS=0.001,
        DASHBOARD_SSE_KEEPALIVE_SECONDS=0.001,
    )
    def test_dashboard_event_stream_pulses_to_release_disconnected_clients(self) -> None:
        user = get_user_model().objects.create_user("stream-pulse-viewer", password="fixture")
        self.client.force_login(user)
        response = self.client.get(reverse("fleet:events"), {"since": dashboard_revision()})
        chunks = iter(response.streaming_content)
        self.assertIn(b"connected", next(chunks))
        self.assertIn(b"keepalive", next(chunks))

    def test_dashboard_revision_ignores_heartbeat_only_updates(self) -> None:
        project = Project.objects.create(
            external_id=uuid.uuid4(),
            name="Heartbeat",
            current_state={"working_count": 1},
        )
        instance = Instance.objects.create(
            project=project,
            external_id=uuid.uuid4(),
            platform="linux",
            client_version="0.39.2",
            report_schema_version=2,
            work_inventory_sequence=1,
            work_inventory_observed_at=timezone.now(),
            work_inventory_digest="d" * 64,
            work_inventory_total=1,
        )
        artifact_id = uuid.uuid4()
        source_updated = timezone.now() - timedelta(minutes=2)
        WorkArtifactSnapshot.objects.create(
            project=project,
            instance=instance,
            artifact_external_id=artifact_id,
            visible_id="IDEA-0012",
            artifact_type="idea-brief",
            title="Lifecycle history",
            document_lifecycle="active",
            outcome_lifecycle="working",
            outcome_disposition="open",
            reconciliation_state="open",
            source_updated_at=source_updated,
            observed_at=timezone.now(),
            snapshot_sequence=1,
        )
        initial = dashboard_revision()
        observed = timezone.now()
        Project.objects.filter(id=project.id).update(last_seen=observed)
        Instance.objects.filter(id=instance.id).update(
            last_seen=observed,
            last_sequence=2,
            work_inventory_sequence=2,
            work_inventory_observed_at=observed,
        )
        WorkArtifactSnapshot.objects.filter(instance=instance).delete()
        WorkArtifactSnapshot.objects.create(
            project=project,
            instance=instance,
            artifact_external_id=artifact_id,
            visible_id="IDEA-0012",
            artifact_type="idea-brief",
            title="Lifecycle history",
            document_lifecycle="active",
            outcome_lifecycle="working",
            outcome_disposition="open",
            reconciliation_state="open",
            source_updated_at=source_updated,
            observed_at=observed,
            snapshot_sequence=2,
        )
        self.assertEqual(dashboard_revision(), initial)
        Project.objects.filter(id=project.id).update(current_state={"working_count": 2})
        self.assertNotEqual(dashboard_revision(), initial)

    def test_dashboard_script_scopes_event_source_to_visible_page(self) -> None:
        script = (
            Path(__file__).parents[1] / "dashboard" / "fleet" / "static" / "fleet" / "dashboard.js"
        ).read_text(encoding="utf-8")
        self.assertIn('window.addEventListener("pagehide", closeStream)', script)
        self.assertIn('window.addEventListener("beforeunload", closeStream)', script)
        self.assertIn('window.addEventListener("pageshow", openStream)', script)
        self.assertIn('document.addEventListener("click"', script)
        self.assertIn('document.addEventListener("submit", closeStream', script)
        self.assertIn('document.addEventListener("visibilitychange"', script)
        self.assertIn("if (source || document.visibilityState", script)
        self.assertIn("window.localStorage.getItem(storageKey)", script)
        self.assertIn("window.localStorage.setItem(storageKey, viewedAt)", script)
        self.assertIn("never affects active attention", script)
        self.assertIn('document.querySelectorAll("[data-auto-submit]")', script)
        self.assertIn("control.form.requestSubmit()", script)

    def test_contract_rejects_uncontrolled_summary_and_non_boolean_flags(self) -> None:
        payload = self.report_payload()
        payload["material_events"][0]["summary_code"] = "path-/private/repository"  # type: ignore[index]
        with self.assertRaisesRegex(ContractError, "summary_code is unsupported"):
            validate_report(payload)
        payload = self.report_payload()
        payload["instance"]["quiescent"] = "false"  # type: ignore[index]
        with self.assertRaisesRegex(ContractError, "must be a boolean"):
            validate_report(payload)

    def test_first_release_fleet_capacity_renders_100_instances_with_25_active(self) -> None:
        user = get_user_model().objects.create_user("capacity-viewer", password="fixture")
        self.client.force_login(user)
        active_at = timezone.now()
        for index in range(100):
            project = Project.objects.create(
                external_id=uuid.uuid4(),
                name=f"Capacity {index:03d}",
                attention_state="working" if index < 25 else "unknown",
                last_seen=active_at if index < 25 else None,
            )
            Instance.objects.create(
                project=project,
                external_id=uuid.uuid4(),
                platform="linux",
                client_version="0.39.0",
                last_seen=project.last_seen,
            )
        response = self.client.get(reverse("fleet:overview"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<strong>100</strong><span>Projects</span>", html=True)
        self.assertContains(response, "<strong>25</strong><span>Working</span>", html=True)
        self.assertContains(response, "<strong>75</strong><span>Stale / offline</span>", html=True)
