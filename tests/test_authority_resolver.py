from __future__ import annotations

import datetime
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import authority_resolver  # noqa: E402
import doctor  # noqa: E402
import document_store  # noqa: E402
import hybrid_state  # noqa: E402
import idea_readiness  # noqa: E402
import planning_order  # noqa: E402
import project_projection  # noqa: E402

class ShadowAuthorityFallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        subprocess.run(["git", "init", "--quiet"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Tool Shed Tests"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=self.workspace, check=True)
        project_id = str(uuid.uuid4())
        files = {
            ".gitignore": "/.tool-shed/\n",
            "SHED_VERSION.json": json.dumps(
                {"schema_version": 1, "version": "0.52.1", "files": {}}
            ) + "\n",
            "work/tool-shed-project.json": json.dumps(
                {"schema_version": 1, "project_id": project_id, "project_name": "shadow-fallback"}
            ) + "\n",
            "work/ideas/idea-shadow.md": (
                "# Idea Brief: Shadow Fixture\n\n"
                "Status: ready-for-prm\n"
                "Type: idea-brief\n"
                "Updated: 2026-09-09\n"
                "Next Action: promote\n"
            ),
            "work/roadmaps/roadmap-shadow.md": (
                "# Program Roadmap: Shadow\n\n"
                "Status: active\n"
                "Type: program-roadmap\n"
                "Updated: 2026-09-08\n"
                "Roadmap ID: shadow-roadmap\n"
            ),
            "work/00-campaigns/active/001-shadow-campaign.md": (
                "# Campaign: Shadow Campaign\n\n"
                "Status: queued\n"
                "Type: campaign\n"
                "Updated: 2026-09-09\n"
                "Campaign ID: shadow-campaign\n"
                "Campaign Number: 001\n"
                "Outcome: prove fallback\n"
            ),
        }
        for relative, body in files.items():
            path = self.workspace / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=self.workspace, check=True)
        digest = hashlib.sha256()
        for value in ("tool-shed-binding-v1", project_id, str(self.workspace.resolve()), "hybrid-state"):
            digest.update(value.encode())
            digest.update(b"\0")
        self.binding = digest.hexdigest()[:24]
        self.database = self.workspace / ".tool-shed/state.sqlite3"
        hybrid_state.initialize(self.workspace, project_binding=self.binding, target=self.database)
        document_store.migrate(self.workspace, project_binding=self.binding, database=self.database)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_schema2_shadow_keeps_file_authority_for_every_projection(self) -> None:
        authority = authority_resolver.resolve(self.workspace, database=self.database)
        self.assertEqual(authority["authority"], "file")
        self.assertEqual(authority["state"], "shadow")
        self.assertIn("guarded conversion", authority["next_action"])
        self.assertFalse(document_store.is_authoritative(self.workspace, self.database))

        database_only = document_store.create_document(
            self.workspace,
            project_binding=self.binding,
            document_type="idea-brief",
            title="Database-only Shadow Decoy",
            body="# Idea Brief: Database-only Shadow Decoy\n\nStatus: active\n",
            lifecycle="active",
            metadata={"document_type": "idea-brief"},
            actor="test",
            reason="prove-shadow-remains-file-authoritative",
            database=self.database,
        )["result"]

        ideas = planning_order.status(self.workspace, "idea", database=self.database)
        roadmaps = planning_order.status(self.workspace, "prm", database=self.database)
        self.assertEqual([item["path"] for item in ideas["items"]], ["work/ideas/idea-shadow.md"])
        self.assertEqual([item["path"] for item in roadmaps["items"]], ["work/roadmaps/roadmap-shadow.md"])
        self.assertEqual(ideas["authority"]["storage_mode"], "shadow")
        self.assertNotIn(database_only["visible_id"], json.dumps(ideas))

        readiness = idea_readiness.status(
            self.workspace, "work/ideas/idea-shadow.md", database=self.database
        )
        self.assertEqual(readiness["state"], "FILE-AUTHORITY")
        self.assertEqual(readiness["idea"]["status"], "ready-for-prm")
        self.assertIn("idea-readiness-persistence-unavailable", readiness["feature_limits"])

        self.assertIsNone(doctor.database_document_state(self.workspace))
        projection = project_projection.build(self.workspace)
        dashboard = projection["state"]
        self.assertEqual(dashboard["active_idea_count"], 1)
        self.assertEqual(dashboard["ready_count"], 1)
        inventory = projection["work_inventory"]
        self.assertEqual(inventory["total_count"], 3)
        paths = {item["visible_id"] for item in inventory["artifacts"]}
        self.assertIn("work/ideas/idea-shadow.md", paths)
        self.assertIn("work/roadmaps/roadmap-shadow.md", paths)
        self.assertIn("work/00-campaigns/active/001-shadow-campaign.md", paths)
        self.assertNotIn(database_only["visible_id"], paths)
        idea_inventory = next(
            item for item in inventory["artifacts"]
            if item["visible_id"] == "work/ideas/idea-shadow.md"
        )
        self.assertEqual(idea_inventory["artifact_id"], ideas["items"][0]["artifact_id"])
        self.assertEqual(idea_inventory["document_lifecycle"], "active")
        uuid.UUID(idea_inventory["artifact_id"])
        self.assertIsNotNone(
            datetime.datetime.fromisoformat(idea_inventory["updated_at"].replace("Z", "+00:00")).tzinfo
        )

    def test_qualified_shadow_remains_file_authoritative_until_cutover(self) -> None:
        checkpoint = hybrid_state.write_checkpoint(
            self.workspace, project_binding=self.binding
        )
        qualified = authority_resolver.resolve(self.workspace, database=self.database)
        self.assertEqual(qualified["authority"], "file")
        self.assertEqual(qualified["state"], "qualified-shadow")
        self.assertIn("awaits guarded cutover", qualified["reason"])

        hybrid_state.activate_hybrid_mode(
            self.workspace,
            project_binding=self.binding,
            expected_checkpoint_digest=checkpoint["digest"],
        )
        active = authority_resolver.resolve(self.workspace, database=self.database)
        self.assertEqual(active["authority"], "sqlite")
        self.assertEqual(active["state"], "hybrid")
        self.assertIsNone(active["next_action"])

    def test_absent_and_indeterminate_databases_have_exact_recovery_actions(self) -> None:
        self.database.unlink()
        absent = authority_resolver.resolve(self.workspace, database=self.database)
        self.assertEqual(absent["state"], "file-only")
        self.assertIn("Initialize and qualify", absent["next_action"])

        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.database.write_bytes(b"not sqlite")
        indeterminate = authority_resolver.resolve(self.workspace, database=self.database)
        self.assertEqual(indeterminate["state"], "indeterminate")
        self.assertIn("Doctor", indeterminate["next_action"])
