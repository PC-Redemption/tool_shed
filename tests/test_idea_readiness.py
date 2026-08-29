from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import document_store  # noqa: E402
import hybrid_state  # noqa: E402
import idea_readiness  # noqa: E402


def binding(workspace: Path) -> str:
    project_id = json.loads((workspace / "work/tool-shed-project.json").read_text(encoding="utf-8"))["project_id"]
    value = hashlib.sha256()
    for item in ("tool-shed-binding-v1", project_id, str(workspace.resolve()), "hybrid-state"):
        value.update(item.encode())
        value.update(b"\0")
    return value.hexdigest()[:24]


class IdeaReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        subprocess.run(["git", "init", "--quiet"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Tool Shed Tests"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=self.workspace, check=True)
        project_id = "817b6358-b2f5-48fd-bb66-bd80f936faca"
        files = {
            ".gitignore": "/.tool-shed/\n",
            "work/tool-shed-project.json": json.dumps(
                {"schema_version": 1, "project_id": project_id, "project_name": "readiness-fixture"}, indent=2
            ) + "\n",
            "work/ideas/idea-ready.md": "# Idea Brief: Ready\n\nStatus: exploring\n\nClear outcome.\n",
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
        self.idea = document_store.import_document(
            self.workspace,
            project_binding=self.binding,
            source=Path("work/ideas/idea-ready.md"),
            document_type="idea-brief",
            lifecycle="active",
            actor="fixture",
            reason="readiness fixture",
            database=self.database,
        )["result"]

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def input(self, verdict: str = "READY", *, gates: list[dict[str, str]] | None = None) -> Path:
        blockers = []
        if verdict == "NOT-READY":
            blockers = [{
                "id": "owner-boundary",
                "summary": "The owner boundary is unknown.",
                "decision_owner": "operator",
                "why_prm_cannot_infer": "Two choices change product scope.",
                "recommendation": "Choose the bounded local target.",
            }]
        payload = {
            "schema_version": 1,
            "kind": idea_readiness.INPUT_KIND,
            "review_contract_version": 1,
            "verdict": verdict,
            "reviewer": "fixture",
            "adaptive_modules": [],
            "promotion_blockers": blockers,
            "prm_gates": gates or [],
            "deferred_items": [],
            "contradictions": [],
            "complexity_findings": [],
            "recommended_updates": [],
            "resumes_result_digest": None,
        }
        path = self.workspace / ".tool-shed/review-input.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def apply_review(self, verdict: str = "READY", *, gates: list[dict[str, str]] | None = None) -> dict[str, object]:
        manifest = idea_readiness.prepare(
            self.workspace, self.idea["visible_id"], self.input(verdict, gates=gates), database=self.database
        )
        self.assertTrue(idea_readiness.validate_manifest(self.workspace, manifest, database=self.database)["valid"])
        return idea_readiness.apply(
            self.workspace,
            manifest,
            expected_token=manifest["manifest_token"],
            project_binding=self.binding,
            database=self.database,
        )

    def test_ready_review_is_current_structured_and_projected_without_semantic_rerun(self) -> None:
        applied = self.apply_review()
        self.assertEqual(applied["result"]["verdict"], "READY")
        status = idea_readiness.status(self.workspace, self.idea["visible_id"], database=self.database)
        self.assertEqual(status["state"], "CURRENT-READY")
        self.assertTrue(status["promotion_allowed"])
        rendered = document_store.render_views(self.workspace, database=self.database)
        view = next((self.workspace / rendered["path"] / "active").glob("IDEA-*.md")).read_text(encoding="utf-8")
        self.assertIn("State: CURRENT-READY", view)
        self.assertIn("Semantic Review Performed: no (projection only)", view)
        checkpoint = document_store.write_checkpoint(
            self.workspace,
            project_binding=self.binding,
            output=Path("work/state/checkpoints/readiness-v2.json"),
            database=self.database,
        )
        rebuilt = Path(".tool-shed/readiness-rebuilt.sqlite3")
        document_store.rebuild(
            self.workspace,
            project_binding=self.binding,
            checkpoint=Path(checkpoint["path"]),
            output=rebuilt,
        )
        rebuilt_status = idea_readiness.status(
            self.workspace, self.idea["visible_id"], database=self.workspace / rebuilt
        )
        self.assertEqual(rebuilt_status["state"], "CURRENT-READY")
        with contextlib.closing(sqlite3.connect(self.database)) as connection:
            event_id = status["latest_review"]["event_id"]
            with self.assertRaises(sqlite3.DatabaseError):
                connection.execute("UPDATE event SET kind='changed' WHERE id=?", (event_id,))

    def test_not_ready_is_semantic_result_not_operational_error(self) -> None:
        self.apply_review("NOT-READY")
        status = idea_readiness.status(self.workspace, self.idea["visible_id"], database=self.database)
        self.assertEqual(status["state"], "CURRENT-NOT-READY")
        self.assertEqual(status["verdict"], "NOT-READY")
        self.assertTrue(status["review_required"])

    def test_concurrent_idea_edit_rejects_prepared_review_and_marks_prior_result_stale(self) -> None:
        self.apply_review()
        projection = Path(".tool-shed/idea-edit.md")
        document_store.export_edit(self.workspace, self.idea["visible_id"], projection, database=self.database)
        edit = self.workspace / projection
        edit.write_text(edit.read_text(encoding="utf-8").replace("Clear outcome.", "Changed outcome."), encoding="utf-8")
        document_store.apply_edit(
            self.workspace,
            project_binding=self.binding,
            edit=projection,
            actor="fixture",
            reason="concurrent change",
            database=self.database,
        )
        self.assertEqual(
            idea_readiness.status(self.workspace, self.idea["visible_id"], database=self.database)["state"],
            "STALE",
        )
        manifest = idea_readiness.prepare(
            self.workspace, self.idea["visible_id"], self.input(), database=self.database
        )
        second_projection = Path(".tool-shed/idea-edit-2.md")
        document_store.export_edit(self.workspace, self.idea["visible_id"], second_projection, database=self.database)
        second = self.workspace / second_projection
        second.write_text(second.read_text(encoding="utf-8").replace("Changed outcome.", "Changed again."), encoding="utf-8")
        document_store.apply_edit(
            self.workspace,
            project_binding=self.binding,
            edit=second_projection,
            actor="fixture",
            reason="race",
            database=self.database,
        )
        with self.assertRaisesRegex(idea_readiness.IdeaReadinessError, "stale|changed"):
            idea_readiness.apply(
                self.workspace,
                manifest,
                expected_token=manifest["manifest_token"],
                project_binding=self.binding,
                database=self.database,
            )

    def test_unknown_contract_and_verdict_fail_closed(self) -> None:
        payload = json.loads(self.input().read_text(encoding="utf-8"))
        payload["review_contract_version"] = 2
        with self.assertRaisesRegex(idea_readiness.IdeaReadinessError, "unknown readiness contract"):
            idea_readiness.validate_input(payload)
        payload["review_contract_version"] = 1
        payload["verdict"] = "MAYBE"
        with self.assertRaisesRegex(idea_readiness.IdeaReadinessError, "unknown readiness verdict"):
            idea_readiness.validate_input(payload)

    def test_cli_distinguishes_review_error_unavailable_and_not_ready(self) -> None:
        unknown = json.loads(self.input().read_text(encoding="utf-8"))
        unknown["review_contract_version"] = 2
        unknown_path = self.workspace / ".tool-shed/unknown-review.json"
        unknown_path.write_text(json.dumps(unknown), encoding="utf-8")
        errored = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "idea_readiness.py"),
                "--workspace",
                str(self.workspace),
                "--database",
                str(self.database),
                "--json",
                "prepare",
                self.idea["visible_id"],
                "--input",
                str(unknown_path),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(errored.returncode, 2)
        self.assertEqual(json.loads(errored.stdout)["status"], "REVIEW-ERROR")
        unavailable = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "idea_readiness.py"),
                "--workspace",
                str(self.workspace),
                "--database",
                str(self.workspace / ".tool-shed/missing.sqlite3"),
                "--json",
                "status",
                self.idea["visible_id"],
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(unavailable.returncode, 2)
        self.assertEqual(json.loads(unavailable.stdout)["status"], "REVIEW-UNAVAILABLE")
        self.apply_review("NOT-READY")
        current = idea_readiness.status(self.workspace, self.idea["visible_id"], database=self.database)
        self.assertEqual(current["verdict"], "NOT-READY")
        self.assertNotIn(current["verdict"], {"REVIEW-ERROR", "REVIEW-UNAVAILABLE"})

    def test_lossless_gate_transfer_requires_exact_review_binding_and_gate_set(self) -> None:
        gates = [{"id": "G-ONE", "title": "First gate", "requirement": "Prove the first gate."}]
        self.apply_review("READY-WITH-PRM-GATES", gates=gates)
        current = idea_readiness.status(self.workspace, self.idea["visible_id"], database=self.database)
        metadata = {
            "readiness_review_digest": current["latest_review"]["result_digest"],
            "reviewed_idea_artifact_id": current["idea"]["artifact_id"],
            "reviewed_idea_document_revision": current["idea"]["document_revision"],
            "reviewed_idea_body_sha256": current["idea"]["body_sha256"],
            "readiness_gate_ids": ["G-ONE"],
        }
        project_map = document_store.create_document(
            self.workspace,
            project_binding=self.binding,
            document_type="project-map",
            title="Transferred map",
            body="# Transferred map\n",
            lifecycle="active",
            metadata=metadata,
            actor="fixture",
            reason="transfer fixture",
            database=self.database,
        )["result"]
        checked = idea_readiness.transfer_check(
            self.workspace, self.idea["visible_id"], project_map["visible_id"], database=self.database
        )
        self.assertTrue(checked["valid"])
        self.assertEqual(checked["transfer_count"], 1)

        dropped_gate_map = document_store.create_document(
            self.workspace,
            project_binding=self.binding,
            document_type="project-map",
            title="Dropped gate map",
            body="# Dropped gate map\n",
            lifecycle="active",
            metadata={**metadata, "readiness_gate_ids": []},
            actor="fixture",
            reason="negative transfer fixture",
            database=self.database,
        )["result"]
        rejected = idea_readiness.transfer_check(
            self.workspace,
            self.idea["visible_id"],
            dropped_gate_map["visible_id"],
            database=self.database,
        )
        self.assertFalse(rejected["valid"])
        self.assertIn("gate ids mismatch", rejected["errors"])
        self.assertEqual(rejected["transfer_count"], 0)

    def test_interrupted_dialogue_resumes_only_same_idea_history(self) -> None:
        first = self.apply_review("NOT-READY")["result"]
        payload = json.loads(self.input("NOT-READY").read_text(encoding="utf-8"))
        payload["resumes_result_digest"] = first["result_digest"]
        source = self.workspace / ".tool-shed/resumed-review.json"
        source.write_text(json.dumps(payload), encoding="utf-8")
        manifest = idea_readiness.prepare(
            self.workspace, self.idea["visible_id"], source, database=self.database
        )
        self.assertEqual(manifest["review"]["resumes_result_digest"], first["result_digest"])
        payload["resumes_result_digest"] = "0" * 64
        source.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(idea_readiness.IdeaReadinessError, "prior review history"):
            idea_readiness.prepare(
                self.workspace, self.idea["visible_id"], source, database=self.database
            )

    def test_adaptive_result_shapes_cover_simple_moderate_and_consequential_inputs(self) -> None:
        for modules in (
            [],
            [{"id": "database", "reason": "The idea changes stored authority."}],
            [
                {"id": "database", "reason": "The idea changes stored authority."},
                {"id": "release", "reason": "The idea changes a published client."},
                {"id": "portability", "reason": "Disconnected clients must upgrade safely."},
            ],
        ):
            payload = json.loads(self.input().read_text(encoding="utf-8"))
            payload["adaptive_modules"] = modules
            self.assertEqual(idea_readiness.validate_input(payload)["adaptive_modules"], modules)


if __name__ == "__main__":
    unittest.main()
