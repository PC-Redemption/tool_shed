from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hybrid_state
import outcome_reconciliation


def project_binding(workspace: Path) -> str:
    project_id = json.loads(
        (workspace / "work/tool-shed-project.json").read_text(encoding="utf-8")
    )["project_id"]
    digest = hashlib.sha256()
    for value in ("tool-shed-binding-v1", project_id, str(workspace.resolve()), "hybrid-state"):
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:24]


class OutcomeReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        bootstrap = json.loads(
            (ROOT / outcome_reconciliation.DEFAULT_BOOTSTRAP).read_text(encoding="utf-8")
        )
        self.project_id = bootstrap["project"]["project_id"]
        self.prepare_workspace(self.workspace)
        self.binding = project_binding(self.workspace)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def prepare_workspace(self, workspace: Path) -> None:
        workspace.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "--quiet"], cwd=workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Tool Shed Tests"], cwd=workspace, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=workspace, check=True)
        identity = workspace / "work/tool-shed-project.json"
        identity.parent.mkdir(parents=True, exist_ok=True)
        identity.write_text(
            json.dumps(
                {"schema_version": 1, "project_id": self.project_id, "project_name": "tool_shed"},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (workspace / ".gitignore").write_text("/.tool-shed/\n", encoding="utf-8")
        sources = {
            outcome_reconciliation.DEFAULT_BOOTSTRAP,
            outcome_reconciliation.DEFAULT_IDS,
            *(Path(value) for value in outcome_reconciliation.PRODUCT_PATHS.values()),
        }
        for relative in sources:
            source = ROOT / relative
            destination = workspace / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        subprocess.run(["git", "add", "."], cwd=workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=workspace, check=True)

    def apply_slice(self) -> dict[str, object]:
        hybrid_state.initialize(self.workspace, project_binding=self.binding)
        return outcome_reconciliation.apply_hpt2(
            self.workspace, project_binding=self.binding
        )

    def test_hpt2_import_preserves_unknown_history_and_bootstrap_parity(self) -> None:
        source_bytes = {
            relative: (self.workspace / relative).read_bytes()
            for relative in outcome_reconciliation.PRODUCT_PATHS.values()
        }
        imported = self.apply_slice()
        self.assertEqual(imported["result"]["hpt2_disposition"], "partial")
        self.assertEqual(imported["result"]["hpt2_reconciliation"], "reconciled")
        self.assertEqual(imported["result"]["missing_history"], outcome_reconciliation.MISSING_HPT2)
        mutation = outcome_reconciliation.apply_bounded_mutation(
            self.workspace, project_binding=self.binding
        )
        self.assertEqual(mutation["actual_writes"], 1)
        parity = outcome_reconciliation.qualify_parity(self.workspace)
        self.assertTrue(parity["valid"])
        self.assertTrue(parity["bootstrap_parity"])
        self.assertTrue(parity["operation_parity"])
        self.assertEqual(set(parity["operations"]), set(outcome_reconciliation.OPERATIONS))
        self.assertEqual(parity["hpt2_disposition"], "partial")
        self.assertEqual(parity["hpt2_reconciliation"], "reconciled")
        for relative, content in source_bytes.items():
            self.assertEqual((self.workspace / relative).read_bytes(), content)

    def test_fresh_workspace_import_and_checkpoint_rebuild_are_semantically_exact(self) -> None:
        self.apply_slice()
        outcome_reconciliation.apply_bounded_mutation(self.workspace, project_binding=self.binding)
        first = outcome_reconciliation.qualify_parity(self.workspace)
        checkpoint = hybrid_state.write_checkpoint(
            self.workspace, project_binding=self.binding
        )
        rebuilt = hybrid_state.rebuild_from_checkpoint(
            self.workspace,
            project_binding=self.binding,
            checkpoint=Path(checkpoint["path"]),
            output=Path(".tool-shed/rebuilt.sqlite3"),
        )
        self.assertEqual(rebuilt["domain_digest"], hybrid_state.audit(self.workspace)["domain_digest"])

        with tempfile.TemporaryDirectory() as directory:
            fresh = Path(directory)
            self.prepare_workspace(fresh)
            fresh_binding = project_binding(fresh)
            hybrid_state.initialize(fresh, project_binding=fresh_binding)
            outcome_reconciliation.apply_hpt2(fresh, project_binding=fresh_binding)
            outcome_reconciliation.apply_bounded_mutation(fresh, project_binding=fresh_binding)
            second = outcome_reconciliation.qualify_parity(fresh)
        self.assertTrue(first["valid"])
        self.assertTrue(second["valid"])
        self.assertEqual(first["bootstrap_projection_digest"], second["bootstrap_projection_digest"])
        self.assertEqual(first["operations"], second["operations"])

    def test_all_file_first_and_hybrid_capsules_match(self) -> None:
        self.apply_slice()
        outcome_reconciliation.apply_bounded_mutation(self.workspace, project_binding=self.binding)
        _, bootstrap, ids = outcome_reconciliation.load_sources(self.workspace)
        file_view = outcome_reconciliation.file_state(bootstrap, mutation_applied=True)
        hybrid_view = outcome_reconciliation.hybrid_state_view(self.workspace, ids)
        for operation in outcome_reconciliation.OPERATIONS:
            self.assertEqual(
                outcome_reconciliation.operation_result(file_view, operation),
                outcome_reconciliation.operation_result(hybrid_view, operation),
                operation,
            )

    def test_context_efficiency_suite_meets_frozen_thresholds(self) -> None:
        _, bootstrap, _ = outcome_reconciliation.load_sources(self.workspace)
        report = outcome_reconciliation.efficiency_report(self.workspace, bootstrap)
        self.assertTrue(report["passed"])
        self.assertTrue(report["semantic_parity"])
        self.assertGreaterEqual(report["median_reduction_percent"], 70.0)
        self.assertLessEqual(report["fallback_percent"], 5.0)
        self.assertEqual(len(report["operations"]), 24)
        self.assertEqual(
            {item["fixture"] for item in report["operations"]},
            {"small", "maintainer", "large"},
        )
        self.assertTrue(all(not item["fallback"] for item in report["operations"]))

    def test_foreign_project_and_non_v4_assignments_fail_closed(self) -> None:
        identity_path = self.workspace / "work/tool-shed-project.json"
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        identity["project_id"] = str(uuid.uuid4())
        identity_path.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(
            outcome_reconciliation.ReconciliationError, "belongs to another"
        ):
            outcome_reconciliation.load_sources(self.workspace)


if __name__ == "__main__":
    unittest.main()
