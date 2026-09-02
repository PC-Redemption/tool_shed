from __future__ import annotations

import contextlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import closure_lineage
import document_store
import hybrid_state
from project_identity import binding_token


class ClosureLineageTests(unittest.TestCase):
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
                    "project_id": "25c67979-5053-4625-a99d-e49af67964c4",
                    "project_name": "closure-fixture",
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
        self.create_chain()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create_document(self, document_type: str, title: str) -> dict[str, object]:
        return document_store.create_document(
            self.workspace,
            project_binding=self.binding,
            document_type=document_type,
            title=title,
            body=f"# {title}\n\nStatus: active\n",
            lifecycle="active",
            metadata={"document_type": document_type},
            actor="fixture",
            reason="closure fixture",
        )["result"]

    def create_chain(self) -> None:
        self.idea = self.create_document("idea-brief", "Root idea")
        self.project_map = self.create_document("project-map", "Child map")
        self.roadmap = self.create_document("program-roadmap", "Child roadmap")
        self.idea_cycle = document_store.open_outcome(
            self.workspace,
            project_binding=self.binding,
            identity=str(self.idea["visible_id"]),
            accepted_outcome="Root is recursively closed.",
            actor="fixture",
        )["result"]["cycle_id"]
        self.map_cycle = document_store.open_outcome(
            self.workspace,
            project_binding=self.binding,
            identity=str(self.project_map["visible_id"]),
            accepted_outcome="Map result is closed.",
            actor="fixture",
        )["result"]["cycle_id"]
        self.roadmap_cycle = document_store.open_outcome(
            self.workspace,
            project_binding=self.binding,
            identity=str(self.roadmap["visible_id"]),
            accepted_outcome="Roadmap result is closed.",
            actor="fixture",
        )["result"]["cycle_id"]
        document_store.relate(
            self.workspace,
            project_binding=self.binding,
            source=str(self.project_map["visible_id"]),
            relation="outcome-parent",
            target=str(self.idea["visible_id"]),
            actor="fixture",
        )
        document_store.relate(
            self.workspace,
            project_binding=self.binding,
            source=str(self.roadmap["visible_id"]),
            relation="outcome-parent",
            target=str(self.project_map["visible_id"]),
            actor="fixture",
        )

    def migrate(self) -> dict[str, object]:
        manifest = closure_lineage.prepare_migration(self.workspace)
        self.assertTrue(closure_lineage.validate_manifest(self.workspace, manifest)["applicable"])
        return closure_lineage.apply_migration(
            self.workspace,
            manifest,
            expected_token=str(manifest["manifest_token"]),
            project_binding=self.binding,
        )

    def requirement_for(self, cycle_id: str) -> str:
        with contextlib.closing(
            hybrid_state.connect(hybrid_state.database_path(self.workspace), writable=False)
        ) as connection:
            return str(connection.execute("SELECT id FROM requirement WHERE cycle_id=?", (cycle_id,)).fetchone()[0])

    def close(self, element_id: str, *, method: str = "closed-loop") -> None:
        closure_lineage.close_element(
            self.workspace,
            project_binding=self.binding,
            element_id=element_id,
            method=method,
            evidence_health="current" if method == "closed-loop" else "not-required",
            authorization_ref="fixture authorization",
            evidence=["fixture:test"],
            actor="fixture",
        )

    def test_exact_migration_and_recursive_parent_blocking(self) -> None:
        migrated = self.migrate()
        self.assertEqual(migrated["to_schema"], 3)
        self.assertTrue((self.workspace / str(migrated["backup"])).is_file())
        self.assertIn(closure_lineage.audit(self.workspace)["classification"], {"VALID_DIRTY", "CHECKPOINT_DUE"})

        root = closure_lineage.status(self.workspace, self.idea_cycle)
        self.assertFalse(root["effective_closed"])
        self.assertIn("LOCAL_OPEN", root["reason_codes"])

        self.close(self.requirement_for(self.roadmap_cycle))
        self.close(self.roadmap_cycle)
        self.close(self.map_cycle)
        self.close(self.idea_cycle)
        root = closure_lineage.status(self.workspace, self.idea_cycle)
        self.assertTrue(root["effective_closed"])
        self.assertEqual(root["graph_health"], "valid")
        self.assertEqual(root["blockers"], [])

    def test_parent_stays_open_until_deep_child_and_its_obligation_close(self) -> None:
        self.migrate()
        self.close(self.idea_cycle)
        self.close(self.map_cycle)
        status = closure_lineage.status(self.workspace, self.idea_cycle)
        self.assertFalse(status["effective_closed"])
        self.assertIn("DESCENDANT_OPEN", status["reason_codes"])
        reasons = {item["reason_code"] for item in status["blockers"]}
        self.assertTrue({"LOCAL_OPEN", "UNFULFILLED_REQUIREMENT"} & reasons)

    def test_incremental_projection_matches_independent_recursive_evaluator(self) -> None:
        self.migrate()
        self.close(self.requirement_for(self.roadmap_cycle))
        self.close(self.roadmap_cycle)
        with contextlib.closing(
            hybrid_state.connect(hybrid_state.database_path(self.workspace), writable=False)
        ) as connection:
            recursive = closure_lineage.evaluate_recursive(connection)
            projected = {
                str(row["element_id"]): {
                    "local_closure": str(row["local_closure"]),
                    "evidence_health": str(row["evidence_health"]),
                    "graph_health": str(row["graph_health"]),
                    "effective_closed": bool(row["effective_closed"]),
                    "reasons": json.loads(row["reason_codes_json"]),
                    "open_descendants": int(row["open_descendants"]),
                    "unknown_descendants": int(row["unknown_descendants"]),
                    "invalid_descendants": int(row["invalid_descendants"]),
                }
                for row in connection.execute("SELECT * FROM closure_rollup")
            }
        for element_id, expected in recursive.items():
            self.assertEqual(
                projected[element_id],
                {key: expected[key] for key in projected[element_id]},
                element_id,
            )

    def test_proof_recipe_is_idempotent_and_subject_bound(self) -> None:
        self.migrate()
        requirement_id = self.requirement_for(self.roadmap_cycle)
        declaration = {
            "obligation_id": requirement_id,
            "target_identity": "fixture-local",
            "read_class": "read-only",
            "write_class": "none",
            "network_class": "none",
            "credential_class": "none",
            "production_class": "non-production",
            "cost_class": "zero",
            "workspace_boundary": "current",
            "target_boundary": "fixture-local",
            "timeout_seconds": 30,
            "resource_limit": "bounded",
            "retry_limit": 1,
            "cooldown_seconds": 60,
            "freshness_seconds": 3600,
            "output_schema": "proof-v1",
            "redaction": "no-output",
            "pass_semantics": "exact predicate passed",
            "fail_semantics": "exact predicate failed",
        }
        registered = closure_lineage.register_recipe(
            self.workspace,
            project_binding=self.binding,
            recipe_id="fixture-proof-v1",
            version=1,
            checker_id="fixture-checker",
            checker_digest="a" * 64,
            declaration=declaration,
            actor="fixture",
        )
        self.assertFalse(registered["result"]["idempotent"])
        repeated = closure_lineage.register_recipe(
            self.workspace,
            project_binding=self.binding,
            recipe_id="fixture-proof-v1",
            version=1,
            checker_id="fixture-checker",
            checker_digest="a" * 64,
            declaration=declaration,
            actor="fixture",
        )
        self.assertTrue(repeated["result"]["idempotent"])
        first = closure_lineage.record_proof_attempt(
            self.workspace,
            project_binding=self.binding,
            recipe_id="fixture-proof-v1",
            element_id=self.roadmap_cycle,
            target_identity="fixture-local",
            state="passed",
            result={
                "status": "passed",
                "checker_digest": "a" * 64,
                "recipe_digest": registered["result"]["recipe_digest"],
                "target_identity": "fixture-local",
                "subject_digest": closure_lineage.status(self.workspace, self.roadmap_cycle)["subject_digest"],
            },
            authority_ref="fixture proof execution",
            actor="fixture",
        )
        second = closure_lineage.record_proof_attempt(
            self.workspace,
            project_binding=self.binding,
            recipe_id="fixture-proof-v1",
            element_id=self.roadmap_cycle,
            target_identity="fixture-local",
            state="passed",
            result={
                "status": "passed",
                "checker_digest": "a" * 64,
                "recipe_digest": registered["result"]["recipe_digest"],
                "target_identity": "fixture-local",
                "subject_digest": closure_lineage.status(self.workspace, self.roadmap_cycle)["subject_digest"],
            },
            authority_ref="fixture proof execution",
            actor="fixture",
        )
        self.assertFalse(first["result"]["idempotent"])
        self.assertTrue(second["result"]["idempotent"])

        fabricated = closure_lineage.record_proof_attempt(
            self.workspace,
            project_binding=self.binding,
            recipe_id="fixture-proof-v1",
            element_id=self.map_cycle,
            target_identity="fixture-local",
            state="passed",
            result={"status": "passed"},
            actor="fixture",
        )
        self.assertEqual(fabricated["result"]["state"], "blocked")
        self.assertEqual(closure_lineage.status(self.workspace, self.map_cycle)["local_closure"], "open")

    def test_recovery_case_blocks_until_exact_resolution(self) -> None:
        self.migrate()
        self.close(self.requirement_for(self.roadmap_cycle))
        self.close(self.roadmap_cycle)
        opened = closure_lineage.open_recovery_case(
            self.workspace,
            project_binding=self.binding,
            element_id=self.roadmap_cycle,
            reason_code="MISSING_PARENT",
            detail={"claim": "fixture"},
            actor="fixture",
        )
        self.assertEqual(closure_lineage.status(self.workspace, self.roadmap_cycle)["graph_health"], "recovery-required")
        closure_lineage.resolve_recovery_case(
            self.workspace,
            project_binding=self.binding,
            case_id=opened["result"]["case_id"],
            disposition="restored",
            authorization_ref="fixture exact restore",
            reason="Exact parent restored.",
            actor="fixture",
        )
        self.assertEqual(closure_lineage.status(self.workspace, self.roadmap_cycle)["graph_health"], "valid")

    def test_recovery_retry_is_owned_bounded_and_escalates(self) -> None:
        self.migrate()
        opened = closure_lineage.open_recovery_case(
            self.workspace,
            project_binding=self.binding,
            element_id=self.roadmap_cycle,
            reason_code="MISSING_PARENT",
            detail={"claim": "fixture"},
            actor="fixture",
        )
        case_id = opened["result"]["case_id"]
        retry = closure_lineage.retry_recovery_case(
            self.workspace,
            project_binding=self.binding,
            case_id=case_id,
            owner_ref="fixture-owner",
            reason="first bounded attempt",
            max_attempts=2,
            cooldown_seconds=60,
            actor="fixture",
        )
        self.assertEqual(retry["result"]["state"], "retry-wait")
        self.assertIsNotNone(retry["result"]["next_retry_at"])
        escalated = closure_lineage.retry_recovery_case(
            self.workspace,
            project_binding=self.binding,
            case_id=case_id,
            owner_ref="fixture-owner",
            reason="second bounded attempt",
            max_attempts=2,
            cooldown_seconds=60,
            actor="fixture",
        )
        self.assertEqual(escalated["result"]["state"], "escalated")
        with self.assertRaisesRegex(closure_lineage.ClosureLineageError, "not eligible"):
            closure_lineage.retry_recovery_case(
                self.workspace,
                project_binding=self.binding,
                case_id=case_id,
                owner_ref="fixture-owner",
                reason="unbounded retry refused",
                max_attempts=3,
                cooldown_seconds=60,
                actor="fixture",
            )

    def test_schema3_checkpoint_rebuild_preserves_status(self) -> None:
        self.migrate()
        self.close(self.requirement_for(self.roadmap_cycle))
        checkpoint = document_store.write_checkpoint(
            self.workspace,
            project_binding=self.binding,
            output=self.workspace / "work/state/checkpoints/state-v2.json",
        )
        rebuilt = document_store.rebuild(
            self.workspace,
            project_binding=self.binding,
            checkpoint=Path(checkpoint["path"]),
            output=Path(".tool-shed/rebuilt-schema3.sqlite3"),
        )
        live = document_store.audit(self.workspace)["domain_digest"]
        self.assertEqual(rebuilt["domain_digest"], live)

    def test_verified_migration_backup_restores_exact_schema2_state(self) -> None:
        before = document_store.audit(self.workspace)
        migrated = self.migrate()
        current = closure_lineage.audit(self.workspace)
        restored = hybrid_state.restore_verified_backup(
            self.workspace,
            project_binding=self.binding,
            backup=Path(str(migrated["backup"])),
            expected_sha256=str(migrated["backup_sha256"]),
            expected_current_revision=int(current["current_revision"]),
        )
        self.assertEqual(restored["schema_version"], 2)
        self.assertEqual(restored["domain_digest"], before["domain_digest"])

    def test_interrupted_shadow_promotion_preserves_live_schema2(self) -> None:
        manifest = closure_lineage.prepare_migration(self.workspace)
        with mock.patch.object(closure_lineage, "_replace_file", side_effect=OSError("injected promotion failure")):
            with self.assertRaisesRegex(OSError, "injected promotion failure"):
                closure_lineage.apply_migration(
                    self.workspace,
                    manifest,
                    expected_token=str(manifest["manifest_token"]),
                    project_binding=self.binding,
                )
        self.assertEqual(document_store.audit(self.workspace)["hybrid_schema"], 2)
        self.assertFalse((self.workspace / ".tool-shed/state.sqlite3.schema3-next").exists())

    def test_ambiguous_parent_requirement_fails_before_migration(self) -> None:
        def add_requirement(connection, revision):
            connection.execute(
                "INSERT INTO requirement VALUES (?, ?, ?, ?, 'accepted', ?, 'M2', 'G2')",
                (
                    "fe0ed5f4-ffaf-4f07-b317-fdf604427e08",
                    self.idea_cycle,
                    self.idea["artifact_id"],
                    "Second explicit requirement.",
                    revision,
                ),
            )

        hybrid_state.managed_write(
            self.workspace,
            project_binding=self.binding,
            command="fixture-ambiguous-requirement",
            actor="fixture",
            callback=add_requirement,
        )
        manifest = closure_lineage.prepare_migration(self.workspace)
        self.assertFalse(manifest["applicable"])
        self.assertIn("AMBIGUOUS_PARENT_REQUIREMENT", {item["code"] for item in manifest["findings"]})
        self.assertFalse(closure_lineage.validate_manifest(self.workspace, manifest)["valid"])


if __name__ == "__main__":
    unittest.main()
