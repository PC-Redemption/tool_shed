from __future__ import annotations

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

import dashboard_reporter  # noqa: E402
import document_store  # noqa: E402
import hybrid_state  # noqa: E402
import planning_order  # noqa: E402


def binding(workspace: Path) -> str:
    project_id = json.loads(
        (workspace / "work/tool-shed-project.json").read_text(encoding="utf-8")
    )["project_id"]
    digest = hashlib.sha256()
    for value in ("tool-shed-binding-v1", project_id, str(workspace.resolve()), "hybrid-state"):
        digest.update(value.encode())
        digest.update(b"\0")
    return digest.hexdigest()[:24]


class LocalPlanningOrderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        subprocess.run(["git", "init", "--quiet"], cwd=self.workspace, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Tool Shed Tests"], cwd=self.workspace, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "tests@example.invalid"],
            cwd=self.workspace,
            check=True,
        )
        identity = self.workspace / "work/tool-shed-project.json"
        identity.parent.mkdir(parents=True)
        (self.workspace / ".gitignore").write_text("/.tool-shed/\n", encoding="utf-8")
        identity.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "project_id": str(uuid.uuid4()),
                    "project_name": "planning-order-fixture",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "."], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=self.workspace, check=True)
        self.binding = binding(self.workspace)
        self.database = self.workspace / ".tool-shed/state.sqlite3"
        hybrid_state.initialize(
            self.workspace, project_binding=self.binding, target=self.database
        )
        document_store.migrate(
            self.workspace, project_binding=self.binding, database=self.database
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create_idea(self, title: str) -> str:
        return document_store.create_document(
            self.workspace,
            project_binding=self.binding,
            document_type="idea-brief",
            title=title,
            body=f"# {title}\n\nStatus: exploring\nType: idea-brief\n",
            lifecycle="active",
            metadata={"document_type": "idea-brief"},
            actor="fixture",
            reason="planning order fixture",
            database=self.database,
        )["result"]["visible_id"]

    def test_local_derivation_override_new_item_and_report_projection(self) -> None:
        first, second, third = (self.create_idea(title) for title in ("First", "Second", "Third"))
        derived = planning_order.status(
            self.workspace, "bs", database=self.database
        )
        self.assertEqual(
            [item["visible_id"] for item in derived["items"]],
            [third, second, first],
        )
        self.assertTrue(all(item["order_source"] == "derived" for item in derived["items"]))

        planning_order.set_order(
            self.workspace,
            project_binding=self.binding,
            artifact_type="idea-brief",
            ordered_ids=[first, third, second],
            expected_token=derived["state_token"],
            actor="owner",
            database=self.database,
        )
        overridden = planning_order.status(
            self.workspace, "idea", database=self.database
        )
        self.assertEqual(
            [item["visible_id"] for item in overridden["items"]],
            [first, third, second],
        )
        self.assertTrue(overridden["override_active"])
        self.assertTrue(all(item["order_source"] == "owner" for item in overridden["items"]))

        fourth = self.create_idea("Fourth")
        extended = planning_order.status(self.workspace, "bs", database=self.database)
        self.assertEqual(
            [item["visible_id"] for item in extended["items"]],
            [first, third, second, fourth],
        )
        self.assertEqual(extended["items"][-1]["order_source"], "derived")

        inventory = dashboard_reporter._work_inventory(self.workspace)
        projected = {item["visible_id"]: item for item in inventory["artifacts"]}
        self.assertEqual(projected[first]["planning_position"], 1)
        self.assertEqual(projected[first]["planning_order_source"], "owner")
        self.assertEqual(projected[fourth]["planning_order_source"], "derived")

        planning_order.reset_order(
            self.workspace,
            project_binding=self.binding,
            artifact_type="idea-brief",
            expected_token=extended["state_token"],
            actor="owner",
            database=self.database,
        )
        reset = planning_order.status(self.workspace, "bs", database=self.database)
        self.assertFalse(reset["override_active"])
        self.assertTrue(all(item["order_source"] == "derived" for item in reset["items"]))

    def test_override_rejects_stale_token_and_incomplete_order(self) -> None:
        first, second = (self.create_idea(title) for title in ("First", "Second"))
        current = planning_order.status(self.workspace, "idea", database=self.database)
        with self.assertRaisesRegex(planning_order.PlanningOrderError, "every current"):
            planning_order.set_order(
                self.workspace,
                project_binding=self.binding,
                artifact_type="idea-brief",
                ordered_ids=[first],
                expected_token=current["state_token"],
                actor="owner",
                database=self.database,
            )
        self.create_idea("Third")
        with self.assertRaisesRegex(planning_order.PlanningOrderError, "stale"):
            planning_order.set_order(
                self.workspace,
                project_binding=self.binding,
                artifact_type="idea-brief",
                ordered_ids=[first, second],
                expected_token=current["state_token"],
                actor="owner",
                database=self.database,
            )
