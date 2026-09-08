from __future__ import annotations

import contextlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import campaign_execution  # noqa: E402
import closure_lineage  # noqa: E402
import document_store  # noqa: E402
import dashboard_reporter  # noqa: E402
import hybrid_state  # noqa: E402
import loop_findings  # noqa: E402
from project_identity import binding_token  # noqa: E402


class CampaignExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        subprocess.run(["git", "init", "--quiet", "-b", "main"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Fixture"], cwd=self.workspace, check=True)
        (self.workspace / "work").mkdir()
        (self.workspace / "work/tool-shed-project.json").write_text(
            json.dumps({
                "schema_version": 1,
                "project_id": "a22713f4-c54e-46f4-9a64-3bed2cb91276",
                "project_name": "campaign-execution-fixture",
            }) + "\n",
            encoding="utf-8",
        )
        (self.workspace / ".gitignore").write_text("/.tool-shed/\n/work/state/objects/\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=self.workspace, check=True)
        self.binding = binding_token(self.workspace, operation="hybrid-state")
        hybrid_state.initialize(self.workspace, project_binding=self.binding)
        document_store.migrate(self.workspace, project_binding=self.binding)
        closure_lineage.apply_migration(
            self.workspace,
            (closure_manifest := closure_lineage.prepare_migration(self.workspace)),
            expected_token=str(closure_manifest["manifest_token"]),
            project_binding=self.binding,
        )
        loop_findings.migrate(self.workspace, project_binding=self.binding)
        loop_findings.migrate(self.workspace, project_binding=self.binding)
        self.campaign = document_store.create_document(
            self.workspace,
            project_binding=self.binding,
            document_type="campaign",
            title="Terminal execution fixture",
            body="# Terminal execution fixture\n\nStatus: working\n",
            lifecycle="working",
            metadata={"document_type": "campaign"},
            actor="fixture",
            reason="campaign execution fixture",
        )["result"]
        self.cycle_id = document_store.open_outcome(
            self.workspace,
            project_binding=self.binding,
            identity=str(self.campaign["visible_id"]),
            accepted_outcome="The bounded campaign outcome is accepted only with evidence.",
            actor="fixture",
        )["result"]["cycle_id"]
        migrated = campaign_execution.migrate(self.workspace, project_binding=self.binding)
        self.assertEqual(6, migrated["to_schema"])

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def snapshot(self, *, version: int = 1, runnable: bool = False, nonterminal: bool = False,
                 missing_reason: bool = False, result: str = "mixed") -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": campaign_execution.SNAPSHOT_KIND,
            "project_id": "a22713f4-c54e-46f4-9a64-3bed2cb91276",
            "campaign_id": self.campaign["visible_id"],
            "source_version": version,
            "campaign_state": "running",
            "execution_result": result,
            "runs": [
                {"id": "run-1", "state": "running" if nonterminal else "completed", "result": "passed"},
                {"id": "run-2", "state": "failed", "result": "failed"},
            ],
            "operations": [
                {"id": "op-1", "run_id": "run-1", "state": "running" if nonterminal else "completed", "result": "passed"},
                {"id": "op-2", "run_id": "run-2", "state": "failed", "result": "failed"},
            ],
            "assignments": [
                {
                    "id": "assignment-1", "run_id": "run-1", "operation_id": "op-1",
                    "state": "pending", "runnable": runnable,
                    "stale_reason": None if missing_reason else "terminal-owner",
                },
                {
                    "id": "assignment-2", "run_id": "run-2", "operation_id": "op-2",
                    "state": "leased", "runnable": False, "stale_reason": "expired-lease",
                },
                {
                    "id": "assignment-3", "run_id": "run-1", "operation_id": "op-1",
                    "state": "completed", "runnable": False, "stale_reason": None,
                },
            ],
        }

    def record(self, payload: dict[str, object]) -> dict[str, object]:
        source = self.workspace / ".tool-shed/execution-snapshot.json"
        source.write_text(json.dumps(payload), encoding="utf-8")
        token = campaign_execution.state_token(self.workspace, str(self.campaign["visible_id"]))
        return campaign_execution.record_snapshot(
            self.workspace,
            str(self.campaign["visible_id"]),
            source,
            project_binding=self.binding,
            expected_token=token,
            actor="scheduler-fixture",
        )

    def make_plan(self, **overrides: object) -> dict[str, object]:
        values = {
            "disposition": "administratively-reconciled",
            "reason": "All execution is terminal; stale control-plane leases remain.",
            "actor": "owner-fixture",
            "authorization_ref": "fixture-authorization-64",
            "handoff_evidence": "evidence://terminal-run-summary",
            "superseding_outcome_ref": None,
        }
        values.update(overrides)
        return campaign_execution.plan(
            self.workspace, str(self.campaign["visible_id"]), **values
        )

    def apply(self, manifest: dict[str, object]) -> dict[str, object]:
        target = self.workspace / ".tool-shed/terminal-reconciliation.json"
        target.write_text(json.dumps(manifest), encoding="utf-8")
        return campaign_execution.apply_manifest(
            self.workspace, target, project_binding=self.binding
        )

    def test_terminal_reconciliation_retires_only_stale_assignments_and_preserves_mixed_result(self) -> None:
        self.record(self.snapshot())
        manifest = self.make_plan()
        self.assertTrue(manifest["applicable"])
        self.assertEqual(2, manifest["counts"]["retirable_assignments"])
        self.assertEqual("mixed", manifest["execution_result"])
        before_reconciliation = next(
            item for item in dashboard_reporter._work_inventory(self.workspace)["artifacts"]
            if item["visible_id"] == self.campaign["visible_id"]
        )
        self.assertIsNone(before_reconciliation["terminal_reason"])

        result = self.apply(manifest)
        self.assertFalse(result["result"]["idempotent"])
        self.assertEqual("administratively-reconciled", result["result"]["terminal_disposition"])
        self.assertEqual("mixed", result["result"]["execution_result"])
        current = document_store.show(self.workspace, str(self.campaign["visible_id"]))
        self.assertEqual("terminal", current["lifecycle"])
        self.assertIn("Status: reconciled-terminal", current["body_markdown"])

        status = campaign_execution.status(self.workspace, str(self.campaign["visible_id"]))
        self.assertEqual("terminal", status["execution"]["state"])
        self.assertEqual("administratively-reconciled", status["terminal_reconciliation"]["terminal_disposition"])
        self.assertFalse(status["reconciliation_ready"])
        projected = next(
            item for item in dashboard_reporter._work_inventory(self.workspace)["artifacts"]
            if item["visible_id"] == self.campaign["visible_id"]
        )
        self.assertEqual("administratively-reconciled", projected["outcome_disposition"])
        self.assertIn("stale control-plane leases", projected["terminal_reason"])
        self.assertEqual("terminal", projected["planning_readiness"])
        with contextlib.closing(hybrid_state.connect(hybrid_state.database_path(self.workspace), writable=False)) as connection:
            states = dict(connection.execute("SELECT id, state FROM campaign_assignment ORDER BY id"))
            self.assertEqual({"assignment-1": "retired", "assignment-2": "retired", "assignment-3": "completed"}, states)
            audit = connection.execute("SELECT * FROM campaign_reconciliation_audit").fetchone()
            self.assertEqual("fixture-authorization-64", audit["authorization_ref"])
            self.assertEqual("mixed", audit["execution_result"])
            self.assertEqual(3, json.loads(audit["counts_json"])["assignments"])

        repeated = self.apply(manifest)
        self.assertFalse(repeated["writes_performed"])
        self.assertTrue(repeated["result"]["idempotent"])

    def test_runnable_nonterminal_and_unclassified_assignments_fail_closed(self) -> None:
        for payload, expected in (
            (self.snapshot(version=1, runnable=True), "runnable assignment"),
            (self.snapshot(version=2, nonterminal=True), "nonterminal runs"),
            (self.snapshot(version=3, missing_reason=True), "unproven stale assignment"),
        ):
            with self.subTest(expected=expected):
                self.record(payload)
                planned = self.make_plan()
                self.assertFalse(planned["applicable"])
                self.assertTrue(any(expected in item for item in planned["blockers"]))

    def test_newly_runnable_snapshot_invalidates_prepared_manifest(self) -> None:
        self.record(self.snapshot(version=1))
        manifest = self.make_plan()
        self.record(self.snapshot(version=2, runnable=True))
        with self.assertRaisesRegex(campaign_execution.CampaignExecutionError, "state token is stale"):
            self.apply(manifest)

    def test_superseded_requires_reference_and_does_not_claim_success(self) -> None:
        self.record(self.snapshot(result="not-satisfied"))
        with self.assertRaisesRegex(campaign_execution.CampaignExecutionError, "superseding outcome"):
            self.make_plan(disposition="superseded")
        manifest = self.make_plan(
            disposition="superseded",
            superseding_outcome_ref="PRM-0999",
            handoff_evidence=None,
        )
        result = self.apply(manifest)
        self.assertEqual("superseded", result["result"]["lifecycle"])
        status = campaign_execution.status(self.workspace, str(self.campaign["visible_id"]))
        self.assertEqual("not-satisfied", status["terminal_reconciliation"]["execution_result"])
        self.assertEqual("PRM-0999", status["terminal_reconciliation"]["superseding_outcome_ref"])

    def test_checkpoint_rebuild_preserves_execution_and_audit_history(self) -> None:
        self.record(self.snapshot())
        manifest = self.make_plan()
        self.apply(manifest)
        checkpoint = self.workspace / "work/state/checkpoints/state-v2.json"
        document_store.write_checkpoint(
            self.workspace, project_binding=self.binding, output=checkpoint
        )
        rebuilt = self.workspace / ".tool-shed/rebuilt.sqlite3"
        result = document_store.rebuild(
            self.workspace, project_binding=self.binding, checkpoint=checkpoint, output=rebuilt
        )
        self.assertEqual(6, document_store.audit(self.workspace, rebuilt)["hybrid_schema"])
        with contextlib.closing(hybrid_state.connect(rebuilt, writable=False)) as connection:
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM campaign_reconciliation_audit").fetchone()[0])
            self.assertEqual(3, connection.execute("SELECT COUNT(*) FROM campaign_assignment").fetchone()[0])
            self.assertEqual("terminal", connection.execute("SELECT state FROM campaign_execution").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
