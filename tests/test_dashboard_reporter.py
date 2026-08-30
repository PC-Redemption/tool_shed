from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import stat
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dashboard_reporter  # noqa: E402


class DashboardReporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        (self.workspace / ".tool-shed/dashboard").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def connected(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "project_id": str(uuid.uuid4()),
            "instance_id": str(uuid.uuid4()),
            "server": "https://dashboard.invalid",
            "status": "connected",
            "reporter_token": "x" * 48,
        }

    def test_private_connection_state_uses_restrictive_permissions(self) -> None:
        target = self.workspace / "protected/state.json"
        dashboard_reporter._write_private_json(target, {"schema_version": 1, "credential": "secret"})
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["credential"], "secret")

    def test_worker_lease_is_released_and_two_events_deliver_once(self) -> None:
        with contextlib.closing(dashboard_reporter._outbox(self.workspace)) as connection:
            for sequence in (1, 2):
                connection.execute(
                    "INSERT INTO outbox VALUES (?, ?, ?, 0, 0, ?, NULL)",
                    (str(uuid.uuid4()), sequence, json.dumps({"sequence": sequence}), dashboard_reporter.stamp()),
                )
        with mock.patch.object(dashboard_reporter, "load_connection", return_value=self.connected()), mock.patch.object(
            dashboard_reporter, "_request", return_value={"status": "accepted"}
        ) as request:
            first = dashboard_reporter.worker_once(self.workspace)
            second = dashboard_reporter.worker_once(self.workspace)
            idle = dashboard_reporter.worker_once(self.workspace)
        self.assertEqual((first["sequence"], second["sequence"]), (1, 2))
        self.assertEqual(idle["status"], "idle")
        self.assertEqual(request.call_count, 2)

    def test_retry_preserves_event_and_releases_singleton(self) -> None:
        with contextlib.closing(dashboard_reporter._outbox(self.workspace)) as connection:
            event_id = str(uuid.uuid4())
            connection.execute(
                "INSERT INTO outbox VALUES (?, 1, ?, 0, 0, ?, NULL)",
                (event_id, json.dumps({"sequence": 1}), dashboard_reporter.stamp()),
            )
        with mock.patch.object(dashboard_reporter, "load_connection", return_value=self.connected()), mock.patch.object(
            dashboard_reporter, "_request", side_effect=dashboard_reporter.DashboardReporterError("offline")
        ):
            with self.assertRaisesRegex(dashboard_reporter.DashboardReporterError, "offline"):
                dashboard_reporter.worker_once(self.workspace)
        with contextlib.closing(dashboard_reporter._outbox(self.workspace)) as connection:
            event = connection.execute("SELECT attempts, delivered_at FROM outbox WHERE id=?", (event_id,)).fetchone()
            lease = connection.execute("SELECT COUNT(*) FROM worker_lease").fetchone()[0]
        self.assertEqual(event["attempts"], 1)
        self.assertIsNone(event["delivered_at"])
        self.assertEqual(lease, 0)

    def test_worker_retires_only_exact_stale_sequence_conflicts(self) -> None:
        with contextlib.closing(dashboard_reporter._outbox(self.workspace)) as connection:
            event_id = str(uuid.uuid4())
            connection.execute(
                "INSERT INTO outbox VALUES (?, 1, ?, 0, 0, ?, NULL)",
                (event_id, json.dumps({"sequence": 1}), dashboard_reporter.stamp()),
            )
        with mock.patch.object(
            dashboard_reporter, "load_connection", return_value=self.connected()
        ), mock.patch.object(
            dashboard_reporter,
            "_request",
            side_effect=dashboard_reporter.DashboardHTTPError(
                409, "report sequence is stale"
            ),
        ):
            result = dashboard_reporter.worker_once(self.workspace)
        self.assertEqual(result["status"], "superseded")
        with contextlib.closing(dashboard_reporter._outbox(self.workspace)) as connection:
            event = connection.execute(
                "SELECT attempts, delivered_at FROM outbox WHERE id=?", (event_id,)
            ).fetchone()
        self.assertEqual(event["attempts"], 0)
        self.assertIsNotNone(event["delivered_at"])

    def test_continuous_worker_refuses_a_second_live_process(self) -> None:
        with contextlib.closing(dashboard_reporter._outbox(self.workspace)) as connection:
            connection.execute(
                "INSERT INTO worker_process VALUES (1, 'existing', ?)",
                (__import__("time").time() + 30,),
            )
        with mock.patch.object(dashboard_reporter, "require_project_binding"):
            result = dashboard_reporter.worker(self.workspace, project_binding="fixture", max_cycles=1)
        self.assertEqual(result["status"], "singleton-active")

    def test_linux_scheduler_install_writes_project_scoped_private_units(self) -> None:
        config = self.workspace / "config"
        identity = {"project_id": str(uuid.uuid4())}
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config)}), mock.patch.object(
            dashboard_reporter, "require_project_binding"
        ), mock.patch.object(
            dashboard_reporter, "load_project_identity", return_value=identity
        ), mock.patch.object(
            dashboard_reporter, "binding_token", return_value="binding"
        ), mock.patch.object(
            dashboard_reporter.platform, "system", return_value="Linux"
        ), mock.patch.object(dashboard_reporter.subprocess, "run") as run:
            result = dashboard_reporter.scheduler_install(self.workspace, project_binding="fixture")
        self.assertEqual(result["status"], "installed")
        self.assertEqual(run.call_count, 2)
        for target in result["targets"]:
            path = Path(target)
            self.assertTrue(path.is_file())
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertIn(identity["project_id"], path.name)
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config)}), mock.patch.object(
            dashboard_reporter, "require_project_binding"
        ), mock.patch.object(
            dashboard_reporter, "load_project_identity", return_value=identity
        ), mock.patch.object(
            dashboard_reporter.platform, "system", return_value="Linux"
        ), mock.patch.object(dashboard_reporter.subprocess, "run") as remove_run:
            removed = dashboard_reporter.scheduler_remove(self.workspace, project_binding="fixture")
        self.assertEqual(removed["status"], "removed")
        self.assertEqual(remove_run.call_count, 2)
        self.assertFalse(any(Path(target).exists() for target in result["targets"]))

    def test_report_payload_contains_only_bounded_aggregate_contract(self) -> None:
        database = self.workspace / ".tool-shed/state.sqlite3"
        with contextlib.closing(sqlite3.connect(database)) as connection:
            connection.execute("CREATE TABLE cycle (id TEXT, lifecycle_state TEXT)")
            connection.execute("CREATE TABLE reconciliation (id TEXT, cycle_id TEXT, state TEXT, compared_at TEXT)")
            connection.execute("INSERT INTO cycle VALUES ('cycle-1', 'working')")
            connection.execute("INSERT INTO reconciliation VALUES ('recon-old', 'cycle-1', 'reconciliation-required', '2026-08-28T00:00:00Z')")
            connection.execute("INSERT INTO reconciliation VALUES ('recon-1', 'cycle-1', 'open', '2026-08-29T00:00:00Z')")
            connection.commit()
        connection_state = self.connected()
        efficiency = {
            "counter_epoch": str(uuid.uuid4()),
            "window": {"started_at": "2026-08-29T00:00:00Z", "ended_at": "2026-08-29T01:00:00Z"},
            "remedial_tokens_actual": None,
            "remedial_token_coverage": 0.0,
            "remedial_proxy": {"interactions": 2, "output_bytes": 100, "duration_ms": 50, "retry_count": 1},
        }
        app = {
            "opportunities": 2,
            "app_server_selections": 1,
            "execution_attempts": 1,
            "gui_fallbacks": 1,
            "counts": {"outcome": {"failed": 1}},
        }
        documents = {
            ("active", "campaign"): {"documents": [{"visible_id": "CAMP-0001"}]},
            ("active", "idea-brief"): {"documents": [{"visible_id": "IDEA-0001"}]},
            ("completed", "campaign"): {"documents": [{"visible_id": "CAMP-0000"}]},
        }

        def listed(workspace, *, lifecycle, document_type, limit):
            self.assertLessEqual(limit, 500)
            return documents[(lifecycle, document_type)]

        with mock.patch.object(dashboard_reporter, "load_project_identity", return_value={"project_id": connection_state["project_id"], "project_name": "Fixture"}), mock.patch.object(
            dashboard_reporter, "load_connection", return_value=connection_state
        ), mock.patch.object(dashboard_reporter.document_store, "list_documents", side_effect=listed), mock.patch.object(
            dashboard_reporter.hybrid_state, "database_path", return_value=database
        ), mock.patch.object(dashboard_reporter.work_orchestration, "efficiency_report", return_value=efficiency), mock.patch.object(
            dashboard_reporter.app_server_user_state.AppServerEventStore, "report", return_value=app
        ), mock.patch.object(
            dashboard_reporter.app_server_user_state.AppServerPreferenceStore, "status", return_value=mock.Mock(enabled=True)
        ):
            payload = dashboard_reporter.report_payload(self.workspace, sequence=4, reason="managed-update")
        serialized = json.dumps(payload)
        for prohibited in ("prompt", "source_path", "command", "credential", "raw_diagnostic"):
            self.assertNotIn(prohibited, serialized)
        self.assertEqual(payload["state"]["open_outcome_count"], 1)
        self.assertEqual(payload["state"]["unreconciled_outcome_count"], 0)
        self.assertEqual(payload["app_server"]["client_version"], "unknown")
        self.assertIsNone(payload["work_efficiency"]["remedial_tokens_actual"])
        self.assertEqual(payload["schema_version"], 5)
        self.assertEqual(payload["work_inventory"], {"total_count": 0, "truncated": False, "artifacts": []})
        self.assertEqual(payload["instance_health"]["reporter_state"], "active")
        self.assertEqual(len(payload["instance_health"]["semantic_digest"]), 64)
        self.assertEqual(payload["instance_health"]["release"]["compatibility_state"], "compatible")
        self.assertEqual(payload["instance_health"]["release"]["awaiting_work5_chain_count"], 0)

    def test_release_projection_rolls_registrations_up_to_distinct_idea_chains(self) -> None:
        artifacts = []
        candidates = []
        commits = [f"{value:040x}" for value in range(1, 7)]
        for index in range(1, 6):
            idea = f"IDEA-{index:04d}"
            map_id = f"MAP-{index:04d}"
            prm = f"PRM-{index:04d}"
            camp = f"CAMP-{index:04d}"
            chain_ids = (idea, map_id, prm, camp)
            types = ("idea-brief", "project-map", "program-roadmap", "campaign")
            for position, (visible_id, artifact_type) in enumerate(zip(chain_ids, types)):
                artifacts.append(
                    {
                        "visible_id": visible_id,
                        "artifact_type": artifact_type,
                        "parent_ids": [chain_ids[position - 1]] if position else [],
                        "produces_ids": [chain_ids[position + 1]] if position < 3 else [],
                    }
                )
                candidates.append(
                    {
                        "origin_path": f"sqlite/documents/{visible_id}",
                        "commit": commits[index - 1],
                    }
                )
        # A later candidate for the first chain creates four more registrations but one commit.
        for visible_id in ("IDEA-0001", "MAP-0001", "PRM-0001", "CAMP-0001"):
            candidates.append(
                {"origin_path": f"sqlite/documents/{visible_id}", "commit": commits[-1]}
            )
        # These are retained for audit but are intentionally not operator-facing document chains.
        for value in range(4):
            candidates.append(
                {
                    "origin_path": f"sqlite/outcome-capsules/{value}",
                    "commit": commits[-1],
                }
            )
        projection = dashboard_reporter._release_chain_projection(
            {"active": [{"candidates": candidates}]},
            {"artifacts": artifacts},
        )
        self.assertEqual(projection["awaiting_work5_chain_count"], 5)
        self.assertEqual(projection["candidate_commit_count"], 6)
        self.assertEqual(projection["registration_count"], 24)
        self.assertEqual(len(projection["release_chains"]), 5)
        first = next(
            chain for chain in projection["release_chains"] if chain["root_id"] == "IDEA-0001"
        )
        self.assertEqual(first["candidate_count"], 2)
        self.assertEqual(first["latest_commit"], commits[-1])

    def test_lifecycle_events_are_change_only_and_first_snapshot_is_a_baseline(self) -> None:
        artifact_id = str(uuid.uuid4())
        current = {
            "total_count": 1,
            "truncated": False,
            "artifacts": [
                {
                    "artifact_id": artifact_id,
                    "visible_id": "PRM-0028",
                    "artifact_type": "program-roadmap",
                    "title": "Lifecycle history",
                    "document_lifecycle": "active",
                    "outcome_lifecycle": "working",
                    "outcome_disposition": "open",
                    "reconciliation_state": "open",
                    "parent_ids": ["MAP-0017"],
                    "produces_ids": ["CAMP-0136"],
                    "updated_at": "2026-08-30T10:00:00Z",
                }
            ],
        }
        self.assertEqual(
            dashboard_reporter._lifecycle_events(
                None,
                current,
                instance_id=str(uuid.uuid4()),
                sequence=1,
                occurred_at="2026-08-30T10:00:00Z",
            ),
            [],
        )
        self.assertEqual(
            dashboard_reporter._lifecycle_events(
                current,
                current,
                instance_id=str(uuid.uuid4()),
                sequence=2,
                occurred_at="2026-08-30T10:01:00Z",
            ),
            [],
        )
        changed = json.loads(json.dumps(current))
        changed["artifacts"][0]["document_lifecycle"] = "completed"
        events = dashboard_reporter._lifecycle_events(
            current,
            changed,
            instance_id=str(uuid.uuid4()),
            sequence=3,
            occurred_at="2026-08-30T10:02:00Z",
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["transition"], "document-lifecycle")
        self.assertEqual((events[0]["from_state"], events[0]["to_state"]), ("active", "completed"))


if __name__ == "__main__":
    unittest.main()
