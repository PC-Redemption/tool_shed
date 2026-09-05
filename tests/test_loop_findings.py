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

import closure_lineage  # noqa: E402
import document_store  # noqa: E402
import hybrid_state  # noqa: E402
import loop_findings  # noqa: E402
from project_identity import binding_token  # noqa: E402


class LoopFindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        subprocess.run(["git", "init", "--quiet", "-b", "main"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Fixture"], cwd=self.workspace, check=True)
        (self.workspace / "work").mkdir()
        (self.workspace / "work/tool-shed-project.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "project_id": "d6de773f-54c7-4862-aeb2-461595d6a805",
                    "project_name": "loop-finding-fixture",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (self.workspace / ".gitignore").write_text("/.tool-shed/\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=self.workspace, check=True)
        self.binding = binding_token(self.workspace, operation="hybrid-state")
        hybrid_state.initialize(self.workspace, project_binding=self.binding)
        document_store.migrate(self.workspace, project_binding=self.binding)
        self.idea = document_store.create_document(
            self.workspace,
            project_binding=self.binding,
            document_type="idea-brief",
            title="Already promoted idea",
            body="# Already promoted idea\n\nStatus: promoted\n",
            lifecycle="active",
            metadata={"document_type": "idea-brief"},
            actor="fixture",
            reason="loop finding fixture",
        )["result"]
        self.cycle_id = document_store.open_outcome(
            self.workspace,
            project_binding=self.binding,
            identity=str(self.idea["visible_id"]),
            accepted_outcome="The idea is promoted and reconciled.",
            actor="fixture",
        )["result"]["cycle_id"]
        manifest = closure_lineage.prepare_migration(self.workspace)
        closure_lineage.apply_migration(
            self.workspace,
            manifest,
            expected_token=str(manifest["manifest_token"]),
            project_binding=self.binding,
        )
        self._close_cycle()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _close_cycle(self) -> None:
        def write(connection, revision):
            stamp = "2030-01-01T00:00:00Z"
            connection.execute(
                "UPDATE cycle SET lifecycle_state='terminal', closed_at=? WHERE id=?",
                (stamp, self.cycle_id),
            )
            verdict_id = hybrid_state.random_uuid()
            connection.execute(
                "INSERT INTO outcome_verdict VALUES (?, ?, 'fixture', 'satisfied', ?, 'fixture', ?, ?)",
                (verdict_id, self.cycle_id, "Promotion result verified.", revision, stamp),
            )
            connection.execute(
                "INSERT INTO reconciliation VALUES (?, ?, ?, 'fixture-product-truth', ?, 'reconciled', ?, '[]')",
                (hybrid_state.random_uuid(), self.cycle_id, revision, verdict_id, stamp),
            )

        hybrid_state.managed_write(
            self.workspace,
            project_binding=self.binding,
            command="close-loop-finding-fixture",
            actor="fixture",
            callback=write,
        )

    def test_schema4_migration_discovers_and_persists_stable_finding(self) -> None:
        migrated = loop_findings.migrate(self.workspace, project_binding=self.binding)
        self.assertEqual(migrated["to_schema"], 4)
        self.assertEqual(migrated["active_count"], 1)
        self.assertTrue((self.workspace / str(migrated["backup"])).is_file())

        audit = loop_findings.audit(self.workspace)
        self.assertTrue(audit["fresh"])
        self.assertEqual(audit["active_count"], 1)
        finding = audit["findings"][0]
        self.assertEqual(finding["subject_id"], self.idea["visible_id"])
        self.assertEqual(finding["reason_code"], "PROMOTED_IDEA_LIFECYCLE_STALE")
        self.assertEqual(finding["command"], f"ts: resolve loop {finding['finding_id']}")

        resolved = loop_findings.resolve(self.workspace, str(finding["finding_id"]))
        self.assertEqual(resolved["status"], "actionable")
        self.assertEqual(
            resolved["recommended_action"], "correct-document-lifecycle-and-body-status"
        )
        self.assertFalse(resolved["writes_performed"])

        document_store.create_document(
            self.workspace,
            project_binding=self.binding,
            document_type="ticket",
            title="Unrelated mutation",
            body="# Unrelated mutation\n",
            lifecycle="active",
            metadata={"document_type": "ticket"},
            actor="fixture",
            reason="prove finding deduplication",
        )
        repeated = loop_findings.audit(self.workspace)
        self.assertEqual(repeated["active_count"], 1)
        self.assertEqual(repeated["findings"][0]["finding_id"], finding["finding_id"])

    def test_lifecycle_correction_resolves_and_recurrence_reopens_same_finding(self) -> None:
        loop_findings.migrate(self.workspace, project_binding=self.binding)
        loop_findings.migrate(self.workspace, project_binding=self.binding)
        finding_id = loop_findings.audit(self.workspace)["findings"][0]["finding_id"]
        current = document_store.show(self.workspace, str(self.idea["visible_id"]))
        document_store.set_lifecycle(
            self.workspace,
            project_binding=self.binding,
            identity=str(self.idea["visible_id"]),
            lifecycle="completed",
            expected_revision=int(current["document_revision"]),
            actor="fixture",
            reason="resolve loop finding",
        )
        resolved = loop_findings.audit(self.workspace)
        self.assertEqual(resolved["active_count"], 0)
        self.assertEqual(resolved["resolved_count"], 1)
        self.assertEqual(resolved["findings"][0]["finding_id"], finding_id)
        self.assertEqual(resolved["findings"][0]["state"], "resolved")

        current = document_store.show(self.workspace, str(self.idea["visible_id"]))
        document_store.set_lifecycle(
            self.workspace,
            project_binding=self.binding,
            identity=str(self.idea["visible_id"]),
            lifecycle="active",
            expected_revision=int(current["document_revision"]),
            actor="fixture",
            reason="prove recurrence semantics",
        )
        recurring = loop_findings.audit(self.workspace)
        self.assertEqual(recurring["active_count"], 1)
        self.assertEqual(recurring["findings"][0]["finding_id"], finding_id)
        self.assertEqual(recurring["findings"][0]["recurrence_count"], 1)

    def test_history_review_is_source_bounded_stale_safe_and_guarded(self) -> None:
        loop_findings.migrate(self.workspace, project_binding=self.binding)
        finding = loop_findings.audit(self.workspace)["findings"][0]
        selected = loop_findings.history_audit(
            self.workspace, sources=[str(self.idea["visible_id"])]
        )
        self.assertEqual(selected["selected_count"], 1)
        self.assertEqual(selected["findings"][0]["finding_id"], finding["finding_id"])
        self.assertIn(
            f"{finding['finding_id']}=apply-expected-state",
            loop_findings.default_history_decisions(self.workspace),
        )

        first = loop_findings.history_review_plan(
            self.workspace,
            decisions=[f"{finding['finding_id']}=apply-expected-state"],
            rationale="The promoted Idea has terminal reconciled outcome evidence.",
            complete_cluster=True,
        )
        self.assertTrue(loop_findings.validate_history_review(self.workspace, first)["applicable"])
        document_store.create_document(
            self.workspace,
            project_binding=self.binding,
            document_type="ticket",
            title="Concurrent mutation",
            body="# Concurrent mutation\n",
            lifecycle="active",
            metadata={"document_type": "ticket"},
            actor="fixture",
            reason="invalidate history review token",
        )
        with self.assertRaisesRegex(loop_findings.LoopFindingError, "stale"):
            loop_findings.validate_history_review(self.workspace, first)

        current = loop_findings.history_review_plan(
            self.workspace,
            decisions=[f"{finding['finding_id']}=apply-expected-state"],
            rationale="The promoted Idea has terminal reconciled outcome evidence.",
            complete_cluster=True,
        )
        applied = loop_findings.apply_history_review(
            self.workspace,
            manifest=current,
            expected_token=current["manifest_token"],
            project_binding=self.binding,
            authorization="fixture-supervised-review",
        )
        self.assertEqual(applied["result"]["applied"], [finding["finding_id"]])
        self.assertEqual(applied["audit"]["active_count"], 0)
        self.assertEqual(
            document_store.show(self.workspace, str(self.idea["visible_id"]))["lifecycle"],
            "completed",
        )
        self.assertIn(
            "Status: completed",
            document_store.show(self.workspace, str(self.idea["visible_id"]))["body_markdown"],
        )
        with contextlib.closing(
            hybrid_state.connect(hybrid_state.database_path(self.workspace), writable=False)
        ) as connection:
            evidence = connection.execute(
                "SELECT target_identity FROM evidence_reference "
                "WHERE cycle_id=? AND kind='loop-history-review'",
                (self.cycle_id,),
            ).fetchone()
        self.assertEqual(evidence["target_identity"], "apply-expected-state")

    def test_open_descendant_is_closure_debt_not_an_automatic_lifecycle_repair(self) -> None:
        loop_findings.migrate(self.workspace, project_binding=self.binding)
        loop_findings.migrate(self.workspace, project_binding=self.binding)
        child = document_store.create_document(
            self.workspace,
            project_binding=self.binding,
            document_type="project-map",
            title="Open child",
            body="# Open child\n\nStatus: active\n",
            lifecycle="active",
            metadata={"document_type": "project-map"},
            actor="fixture",
            reason="open descendant fixture",
        )["result"]
        document_store.open_outcome(
            self.workspace,
            project_binding=self.binding,
            identity=str(child["visible_id"]),
            accepted_outcome="Child is completed.",
            actor="fixture",
        )
        document_store.relate(
            self.workspace,
            project_binding=self.binding,
            source=str(child["visible_id"]),
            relation="outcome-parent",
            target=str(self.idea["visible_id"]),
            actor="fixture",
        )
        finding = next(
            item for item in loop_findings.audit(self.workspace)["findings"]
            if item["state"] == "active" and item["subject_id"] == self.idea["visible_id"]
        )
        self.assertEqual(finding["reason_code"], "LINEAGE_RECOVERY_REQUIRED")
        self.assertEqual(finding["expected_state"], "retain-open-until-recursively-closed")
        self.assertIn(
            f"{finding['finding_id']}=retain-open",
            loop_findings.default_history_decisions(self.workspace),
        )
        with self.assertRaisesRegex(loop_findings.LoopFindingError, "does not support"):
            loop_findings.history_review_plan(
                self.workspace,
                decisions=[f"{finding['finding_id']}=apply-expected-state"],
                rationale="Automatic repair must refuse open descendants.",
                complete_cluster=False,
            )

    def test_schema5_discovers_current_outcome_health_and_preserves_schema4_history(self) -> None:
        loop_findings.migrate(self.workspace, project_binding=self.binding)
        migrated = loop_findings.migrate(self.workspace, project_binding=self.binding)
        self.assertEqual((migrated["from_schema"], migrated["to_schema"]), (4, 5))

        blocked = document_store.create_document(
            self.workspace,
            project_binding=self.binding,
            document_type="campaign",
            title="Blocked campaign",
            body="# Blocked campaign\n",
            lifecycle="working",
            metadata={"document_type": "campaign"},
            actor="fixture",
            reason="schema five finding fixture",
        )["result"]
        blocked_cycle = document_store.open_outcome(
            self.workspace,
            project_binding=self.binding,
            identity=str(blocked["visible_id"]),
            accepted_outcome="The campaign completes.",
            actor="fixture",
        )["result"]["cycle_id"]

        def block(connection, revision):
            connection.execute(
                "UPDATE cycle SET lifecycle_state='blocked' WHERE id=?", (blocked_cycle,)
            )

        hybrid_state.managed_write(
            self.workspace,
            project_binding=self.binding,
            command="block-fixture",
            actor="fixture",
            callback=block,
        )
        audit = loop_findings.audit(self.workspace)
        reasons = {item["reason_code"] for item in audit["findings"] if item["state"] == "active"}
        self.assertIn("PROMOTED_IDEA_LIFECYCLE_STALE", reasons)
        self.assertIn("OUTCOME_BLOCKED", reasons)
        blocked_finding = next(item for item in audit["findings"] if item["reason_code"] == "OUTCOME_BLOCKED")
        self.assertEqual(
            loop_findings.resolve(self.workspace, blocked_finding["finding_id"])["recommended_action"],
            "inspect-blocker-and-continue-or-dispose",
        )
        checkpoint = document_store.write_checkpoint(
            self.workspace,
            project_binding=self.binding,
            output=self.workspace / "work/state/checkpoints/state-v2.json",
        )
        rebuilt_path = self.workspace / ".tool-shed/schema5-rebuilt.sqlite3"
        document_store.rebuild(
            self.workspace,
            project_binding=self.binding,
            checkpoint=self.workspace / str(checkpoint["path"]),
            output=rebuilt_path,
        )
        rebuilt_audit = document_store.audit(self.workspace, rebuilt_path)
        self.assertEqual(rebuilt_audit["hybrid_schema"], 5)
        self.assertEqual(rebuilt_audit["classification"], "CLEAN")

    def test_missing_report_projection_does_not_create_an_empty_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            empty = Path(directory)
            subprocess.run(["git", "init", "--quiet", "-b", "main"], cwd=empty, check=True)
            (empty / "work").mkdir()
            (empty / "work/tool-shed-project.json").write_text(
                (self.workspace / "work/tool-shed-project.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            projection = loop_findings.report_projection(empty)
            self.assertEqual(projection["total_active_count"], 0)
            self.assertFalse((empty / ".tool-shed/state.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
