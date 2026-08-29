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
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import document_store  # noqa: E402
import hybrid_state  # noqa: E402


def binding(workspace: Path) -> str:
    project_id = json.loads((workspace / "work/tool-shed-project.json").read_text(encoding="utf-8"))["project_id"]
    digest = hashlib.sha256()
    for value in ("tool-shed-binding-v1", project_id, str(workspace.resolve()), "hybrid-state"):
        digest.update(value.encode())
        digest.update(b"\0")
    return digest.hexdigest()[:24]


class DocumentStoreThinSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        subprocess.run(["git", "init", "--quiet"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Tool Shed Tests"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=self.workspace, check=True)
        files = {
            ".gitignore": "/.tool-shed/\n",
            "work/tool-shed-project.json": json.dumps({"schema_version": 1, "project_id": str(uuid.uuid4()), "project_name": "document-fixture"}, indent=2) + "\n",
            "work/ideas/idea-one.md": "# Idea One\n\nOriginal idea bytes.\n",
            "work/maps/map-one.md": "# Map One\n\nOriginal map bytes.\n",
        }
        for relative, content in files.items():
            path = self.workspace / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=self.workspace, check=True)
        self.binding = binding(self.workspace)
        self.database = self.workspace / ".tool-shed/thin.sqlite3"
        hybrid_state.initialize(self.workspace, project_binding=self.binding, target=self.database)
        document_store.migrate(self.workspace, project_binding=self.binding, database=self.database)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_transactional_edit_relationship_checkpoint_rebuild_and_outcome(self) -> None:
        originals = {path: (self.workspace / path).read_bytes() for path in ("work/ideas/idea-one.md", "work/maps/map-one.md")}
        idea = document_store.import_document(
            self.workspace, project_binding=self.binding, source=Path("work/ideas/idea-one.md"),
            document_type="idea-brief", lifecycle="active", actor="fixture", reason="thin slice", database=self.database,
        )["result"]
        project_map = document_store.import_document(
            self.workspace, project_binding=self.binding, source=Path("work/maps/map-one.md"),
            document_type="project-map", lifecycle="working", actor="fixture", reason="thin slice", database=self.database,
        )["result"]
        self.assertEqual(idea["visible_id"], "IDEA-0001")
        self.assertEqual(project_map["visible_id"], "MAP-0001")
        self.assertFalse(idea["idempotent"])
        repeated = document_store.import_document(
            self.workspace, project_binding=self.binding, source=Path("work/ideas/idea-one.md"),
            document_type="idea-brief", lifecycle="active", actor="fixture", reason="repeat", database=self.database,
        )["result"]
        self.assertTrue(repeated["idempotent"])

        edit_path = Path(".tool-shed/idea-edit.md")
        document_store.export_edit(self.workspace, idea["visible_id"], edit_path, database=self.database)
        absolute_edit = self.workspace / edit_path
        exported = absolute_edit.read_text(encoding="utf-8")
        absolute_edit.write_text(exported.replace("Original idea bytes.", "Revised database-owned body."), encoding="utf-8")
        applied = document_store.apply_edit(
            self.workspace, project_binding=self.binding, edit=edit_path, actor="fixture", reason="prove revision fence", database=self.database,
        )
        self.assertEqual(applied["result"]["document_revision"], 2)
        shown = document_store.show(self.workspace, idea["artifact_id"], database=self.database)
        self.assertIn("Revised database-owned body.", shown["body_markdown"])
        self.assertEqual(len(document_store.history(self.workspace, idea["visible_id"], database=self.database)["revisions"]), 2)
        self.assertIn("Revised database-owned body.", document_store.diff_revisions(self.workspace, idea["visible_id"], 1, 2, database=self.database)["diff"])
        with self.assertRaisesRegex(document_store.DocumentStoreError, "stale document revision"):
            document_store.apply_edit(self.workspace, project_binding=self.binding, edit=edit_path, actor="fixture", reason="stale", database=self.database)

        document_store.relate(
            self.workspace, project_binding=self.binding, source=idea["visible_id"], relation="produces",
            target=project_map["visible_id"], actor="fixture", database=self.database,
        )
        relations = document_store.related(self.workspace, idea["visible_id"], database=self.database)["relationships"]
        self.assertEqual(relations[0]["to_visible_id"], "MAP-0001")
        outcome = document_store.open_outcome(
            self.workspace, project_binding=self.binding, identity=idea["visible_id"],
            accepted_outcome="Prove database-owned revision and reconciliation propagation.", actor="fixture", database=self.database,
        )["result"]
        self.assertEqual((outcome["lifecycle"], outcome["verdict"], outcome["reconciliation"]), ("working", "open", "open"))

        checkpoint = document_store.write_checkpoint(
            self.workspace, project_binding=self.binding, output=Path("work/state/checkpoints/thin-v2.json"), database=self.database,
        )
        self.assertTrue(checkpoint["objects"])
        rebuilt_path = Path(".tool-shed/rebuilt-v2.sqlite3")
        rebuilt = document_store.rebuild(
            self.workspace, project_binding=self.binding, checkpoint=Path(checkpoint["path"]), output=rebuilt_path,
        )
        self.assertEqual(rebuilt["domain_digest"], document_store.audit(self.workspace, self.database)["domain_digest"])
        self.assertEqual(document_store.show(self.workspace, idea["visible_id"], database=self.workspace / rebuilt_path)["body_markdown"], shown["body_markdown"])

        for relative, content in originals.items():
            self.assertEqual((self.workspace / relative).read_bytes(), content)

    def test_direct_sql_sets_unmanaged_review(self) -> None:
        imported = document_store.import_document(
            self.workspace, project_binding=self.binding, source=Path("work/ideas/idea-one.md"),
            document_type="idea-brief", lifecycle="active", actor="fixture", reason="thin slice", database=self.database,
        )["result"]
        with contextlib.closing(sqlite3.connect(self.database)) as connection:
            connection.execute("UPDATE document SET title='Direct SQL' WHERE id=?", (imported["artifact_id"],))
            connection.commit()
        result = document_store.audit(self.workspace, self.database)
        self.assertEqual(result["classification"], "UNMANAGED_REVIEW")
        self.assertTrue(result["unmanaged_write_detected"])


if __name__ == "__main__":
    unittest.main()
