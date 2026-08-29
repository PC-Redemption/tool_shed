from __future__ import annotations

import contextlib
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import document_conversion  # noqa: E402
import document_store  # noqa: E402
import hybrid_state  # noqa: E402


def binding(workspace: Path) -> str:
    project_id = json.loads((workspace / "work/tool-shed-project.json").read_text(encoding="utf-8"))["project_id"]
    digest = hashlib.sha256()
    for value in ("tool-shed-binding-v1", project_id, str(workspace.resolve()), "hybrid-state"):
        digest.update(value.encode()); digest.update(b"\0")
    return digest.hexdigest()[:24]


class DocumentConversionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name) / "workspace"
        self.workspace.mkdir()
        subprocess.run(["git", "init", "--quiet"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Tool Shed Tests"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=self.workspace, check=True)
        files = {
            ".gitignore": "/.tool-shed/\n",
            "work/tool-shed-project.json": json.dumps({"schema_version": 1, "project_id": str(uuid.uuid4()), "project_name": "conversion-fixture"}, indent=2) + "\n",
            "work/00-campaigns/completed/007-finished.md": "# Finished\n\nStatus: complete\nType: campaign\nCampaign Number: 7\n\n## Body\n\nKept.\n",
            "work/ideas/example.md": "# Example\n\nStatus: promoted\nType: idea-brief\n\n## Body\n\nExact bytes.\n",
            "work/maps/example.md": "# Example Map\n\nStatus: approved\nType: project-map\nSource Idea: work/ideas/example.md\n",
            "work/00-campaigns/active-queue.md": "# Active queue\n",
            "work/evidence/raw.bin": "raw evidence\n",
            "work/notes/unknown.md": "# Owner note without generated type\n",
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

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_inventory_archive_resume_idempotence_parity_rollback_and_fencing(self) -> None:
        plan = document_conversion.build_plan(self.workspace, database=self.database)
        paths = {entry["path"]: entry for entry in plan["entries"]}
        self.assertEqual(paths["work/00-campaigns/completed/007-finished.md"]["assigned_number"], 7)
        self.assertEqual(paths["work/00-campaigns/active-queue.md"]["classification"], "projection")
        self.assertEqual(paths["work/evidence/raw.bin"]["classification"], "file-owned")
        self.assertEqual(paths["work/notes/unknown.md"]["classification"], "unresolved")
        archive = Path(self.temporary.name) / "external-archive"
        archived = document_conversion.create_archive(self.workspace, manifest=plan, destination=archive)
        self.assertEqual(archived["files"], len(plan["entries"]))

        with self.assertRaisesRegex(document_conversion.ConversionError, "simulated"):
            document_conversion.apply_plan(
                self.workspace, project_binding=self.binding, manifest=plan, database=self.database,
                actor="fixture", fail_after=1,
            )
        resumed = document_conversion.apply_plan(
            self.workspace, project_binding=self.binding, manifest=plan, database=self.database, actor="fixture",
        )
        self.assertTrue(resumed["imported"])
        self.assertTrue(resumed["idempotent"])
        revision_before_repeat = document_store.audit(self.workspace, self.database)["current_revision"]
        repeated = document_conversion.apply_plan(
            self.workspace, project_binding=self.binding, manifest=plan, database=self.database, actor="fixture",
        )
        self.assertFalse(repeated["imported"])
        self.assertEqual(len(repeated["idempotent"]), 3)
        self.assertEqual(document_store.audit(self.workspace, self.database)["current_revision"], revision_before_repeat)
        qualification = document_conversion.qualify(self.workspace, manifest=plan, database=self.database)
        self.assertTrue(qualification["passed"], qualification["findings"])

        checkpoint = document_store.write_checkpoint(
            self.workspace, project_binding=self.binding, output=Path("work/state/checkpoints/conversion-v2.json"), database=self.database,
        )
        rebuilt = document_store.rebuild(
            self.workspace, project_binding=self.binding, checkpoint=Path(checkpoint["path"]), output=Path(".tool-shed/rebuilt.sqlite3"),
        )
        self.assertEqual(rebuilt["domain_digest"], document_store.audit(self.workspace, self.database)["domain_digest"])
        rollback = document_conversion.rollback_export(
            self.workspace, manifest=plan, database=self.database, output=Path(".tool-shed/rollback"),
        )
        self.assertEqual(rollback["documents"], 3)
        for entry in plan["entries"]:
            if entry["classification"] == "generated":
                self.assertEqual((self.workspace / ".tool-shed/rollback" / entry["path"]).read_bytes(), (self.workspace / entry["path"]).read_bytes())

        older = self.workspace / ".tool-shed/older.sqlite3"
        hybrid_state.initialize(self.workspace, project_binding=self.binding, target=older)
        with self.assertRaisesRegex(document_store.DocumentStoreError, "schema 2"):
            document_store.show(self.workspace, "IDEA-0001", database=older)
        newer = self.workspace / ".tool-shed/newer.sqlite3"
        shutil.copyfile(self.database, newer)
        with contextlib.closing(sqlite3.connect(newer)) as connection:
            connection.execute("PRAGMA user_version=3")
            connection.commit()
        self.assertEqual(document_store.audit(self.workspace, newer)["classification"], "INVALID")


if __name__ == "__main__":
    unittest.main()
