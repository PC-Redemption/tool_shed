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
        self.assertEqual(resolved["recommended_action"], "correct-document-lifecycle")
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


if __name__ == "__main__":
    unittest.main()
