from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import document_store  # noqa: E402
import hybrid_state  # noqa: E402
import check_work_tree  # noqa: E402
import campaign_queue  # noqa: E402
from work_tree import WORK_DIRS  # noqa: E402


def binding(workspace: Path) -> str:
    project_id = json.loads((workspace / "work/tool-shed-project.json").read_text())["project_id"]
    digest = hashlib.sha256()
    for value in ("tool-shed-binding-v1", project_id, str(workspace.resolve()), "hybrid-state"):
        digest.update(value.encode())
        digest.update(b"\0")
    return digest.hexdigest()[:24]


class RetainedSourceRetirementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        subprocess.run(["git", "init", "--quiet"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Tool Shed Tests"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=self.workspace, check=True)
        files = {
            ".gitignore": "/.tool-shed/\n",
            "work/tool-shed-project.json": json.dumps({
                "schema_version": 1, "project_id": str(uuid.uuid4()), "project_name": "retirement-fixture",
            }) + "\n",
            "work/maps/map-one.md": "# Map One\n\nRetained generated source.\n",
            "README.md": "See work/maps/map-one.md for current planning.\n",
        }
        for relative, content in files.items():
            path = self.workspace / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=self.workspace, check=True)
        self.binding = binding(self.workspace)
        self.database = self.workspace / ".tool-shed/state.sqlite3"
        hybrid_state.initialize(self.workspace, project_binding=self.binding, target=self.database)
        document_store.migrate(self.workspace, project_binding=self.binding, database=self.database)
        document_store.import_document(
            self.workspace, project_binding=self.binding, source=Path("work/maps/map-one.md"),
            document_type="project-map", lifecycle="active", actor="fixture", reason="retirement test",
            database=self.database,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_plan_classifies_rewrites_and_apply_retires_only_alias(self) -> None:
        revision_before = document_store.audit(self.workspace, self.database)["current_revision"]
        blocked = document_store.retirement_plan(self.workspace, database=self.database)
        self.assertTrue(blocked["valid"])
        self.assertFalse(blocked["applicable"])
        self.assertEqual(blocked["candidate_count"], 1)
        self.assertGreaterEqual(blocked["excluded_work_file_count"], 1)
        self.assertEqual(blocked["reference_counts"]["rewrite-required"], 1)
        self.assertEqual(document_store.audit(self.workspace, self.database)["current_revision"], revision_before)
        blocked_manifest = self.workspace / ".tool-shed/blocked-retirement.json"
        blocked_manifest.write_text(json.dumps(blocked), encoding="utf-8")
        with self.assertRaisesRegex(document_store.DocumentStoreError, "not applicable"):
            document_store.retire_source_aliases(
                self.workspace, project_binding=self.binding, manifest_path=blocked_manifest,
                expected_token=blocked["manifest_token"], actor="fixture", reason="must refuse rewrite",
                database=self.database,
            )

        (self.workspace / "README.md").write_text("Current planning uses the managed document store.\n")
        ready = document_store.retirement_plan(self.workspace, database=self.database)
        self.assertTrue(ready["applicable"])
        manifest = self.workspace / ".tool-shed/retirement.json"
        manifest.write_text(json.dumps(ready), encoding="utf-8")
        result = document_store.retire_source_aliases(
            self.workspace, project_binding=self.binding, manifest_path=manifest,
            expected_token=ready["manifest_token"], actor="fixture", reason="prove alias-only retirement",
            database=self.database,
        )
        self.assertEqual(result["result"]["retired_alias_count"], 1)
        self.assertEqual(result["result"]["filesystem_deletions"], 0)
        self.assertEqual(result["actual_writes"], 1)
        self.assertTrue((self.workspace / "work/maps/map-one.md").is_file())
        with contextlib.closing(hybrid_state.connect(self.database, writable=False)) as connection:
            retired_revision = connection.execute(
                "SELECT retired_revision FROM document_path_alias WHERE path='work/maps/map-one.md'"
            ).fetchone()[0]
        self.assertIsNotNone(retired_revision)

    def test_apply_refuses_stale_revision(self) -> None:
        (self.workspace / "README.md").write_text("No retained path reference.\n")
        ready = document_store.retirement_plan(self.workspace, database=self.database)
        manifest = self.workspace / ".tool-shed/retirement.json"
        manifest.write_text(json.dumps(ready), encoding="utf-8")
        document_store.create_document(
            self.workspace, project_binding=self.binding, document_type="ticket", title="Drift",
            body="# Drift\n", lifecycle="active", metadata={}, actor="fixture", reason="advance revision",
            database=self.database,
        )
        with self.assertRaisesRegex(document_store.DocumentStoreError, "expected_revision is stale"):
            document_store.retire_source_aliases(
                self.workspace, project_binding=self.binding, manifest_path=manifest,
                expected_token=ready["manifest_token"], actor="fixture", reason="must fail stale",
                database=self.database,
            )

    def test_plan_reports_source_hash_drift(self) -> None:
        (self.workspace / "work/maps/map-one.md").write_text("# Map One\n\nChanged behind authority.\n")
        result = document_store.retirement_plan(self.workspace, database=self.database)
        self.assertFalse(result["valid"])
        self.assertFalse(result["applicable"])
        self.assertEqual(result["findings"], [{
            "code": "SOURCE_HASH_DRIFT", "path": "work/maps/map-one.md",
        }])

    def test_work_tree_ignores_retired_file_queue_under_database_authority(self) -> None:
        with contextlib.closing(sqlite3.connect(self.database)) as connection:
            connection.execute("UPDATE state_meta SET storage_mode='hybrid' WHERE id=1")
            connection.commit()
        for relative in WORK_DIRS:
            (self.workspace / relative).mkdir(parents=True, exist_ok=True)
        for name in campaign_queue.LIFECYCLE_DIRS:
            (self.workspace / "work/00-campaigns" / name).mkdir(parents=True, exist_ok=True)
        files = {
            "work/README.md": "# Work\n",
            "work/index.md": "# Generated legacy projection\n",
            "work/index.json": json.dumps({"schema_version": 1}) + "\n",
            "work/00-campaigns/active-queue.md": "stale retired-source projection\n",
            "work/00-campaigns/completed-queue.md": "stale retired-source projection\n",
            "work/01-q&a/ask.txt": "",
        }
        for relative, content in files.items():
            path = self.workspace / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        report = check_work_tree.inspect_work_tree(self.workspace)

        self.assertEqual(report["campaign_authority"], "sqlite")
        self.assertTrue(report["converged"])
        self.assertEqual(report["findings"], [])


if __name__ == "__main__":
    unittest.main()
