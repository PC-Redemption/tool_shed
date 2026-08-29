from __future__ import annotations

import contextlib
import json
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

import hybrid_state  # noqa: E402
import release_cohort  # noqa: E402
from project_identity import binding_token  # noqa: E402


class ReleaseCohortTests(unittest.TestCase):
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
        identity = {
            "schema_version": 1,
            "project_id": str(uuid.uuid4()),
            "project_name": "release-cohort-fixture",
        }
        files = {
            ".gitignore": "/.tool-shed/\n",
            "work/tool-shed-project.json": json.dumps(identity, indent=2, sort_keys=True) + "\n",
            "product.txt": "released baseline\n",
        }
        for relative, content in files.items():
            path = self.workspace / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "baseline"], cwd=self.workspace, check=True)
        subprocess.run(["git", "tag", "v1.0.0"], cwd=self.workspace, check=True)
        (self.workspace / "product.txt").write_text("Work2 candidate\n", encoding="utf-8")
        subprocess.run(["git", "add", "product.txt"], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "candidate"], cwd=self.workspace, check=True)
        self.binding = binding_token(self.workspace, operation="hybrid-state")
        hybrid_state.initialize(self.workspace, project_binding=self.binding)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _close_cycle(self, cycle_id: str) -> None:
        def write(connection, revision):
            stamp = hybrid_state.now()
            connection.execute(
                "UPDATE cycle SET lifecycle_state='terminal', closed_at=? WHERE id=?",
                (stamp, cycle_id),
            )
            verdict_id = hybrid_state.random_uuid()
            connection.execute(
                "INSERT INTO outcome_verdict VALUES (?, ?, 'fixture', 'satisfied', ?, ?, ?, ?)",
                (verdict_id, cycle_id, "Production release verified.", "fixture", revision, stamp),
            )
            connection.execute(
                "INSERT INTO reconciliation VALUES (?, ?, ?, '[]', ?, 'reconciled', ?, '[]')",
                (hybrid_state.random_uuid(), cycle_id, revision, verdict_id, stamp),
            )

        hybrid_state.managed_write(
            self.workspace,
            project_binding=self.binding,
            command="close-fixture-origin",
            actor="fixture",
            callback=write,
            expected_writes=3,
        )

    def test_work2_registration_release_and_final_reconciliation_are_persistent(self) -> None:
        initial = release_cohort.status(self.workspace)
        registered = release_cohort.register(
            self.workspace,
            expected=initial["state_token"],
            project_binding=self.binding,
            commitish="HEAD",
            origin_cycles=[],
            accepted_outcome="Ship and production-verify the candidate behavior.",
            summary="Fixture candidate outcome.",
        )
        direct_cycle = registered["result"]["created_direct_cycle"]
        current = registered["status"]
        self.assertEqual(current["active"][0]["base_tag"], "v1.0.0")
        self.assertEqual(len(current["active"][0]["candidates"]), 1)
        self.assertEqual(
            current["active"][0]["candidates"][0]["origin_cycle_id"], direct_cycle
        )

        repeated = release_cohort.register(
            self.workspace,
            expected=current["state_token"],
            project_binding=self.binding,
            commitish="HEAD",
            origin_cycles=[direct_cycle],
            accepted_outcome=None,
            summary=None,
        )
        self.assertFalse(repeated["writes_performed"])
        self.assertEqual(repeated["status"]["revision"], current["revision"])

        frozen = release_cohort.freeze(
            self.workspace,
            expected=current["state_token"],
            project_binding=self.binding,
            content_commitish="HEAD",
        )
        first_content_commit = frozen["result"]["content_commit"]
        (self.workspace / "product.txt").write_text("Corrected Work5 candidate\n", encoding="utf-8")
        subprocess.run(["git", "add", "product.txt"], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "correct candidate"], cwd=self.workspace, check=True)
        corrected = release_cohort.status(self.workspace)
        with self.assertRaisesRegex(
            release_cohort.ReleaseCohortError, "requires durable failed-CI evidence"
        ):
            release_cohort.freeze(
                self.workspace,
                expected=corrected["state_token"],
                project_binding=self.binding,
                content_commitish="HEAD",
            )
        refrozen = release_cohort.freeze(
            self.workspace,
            expected=corrected["state_token"],
            project_binding=self.binding,
            content_commitish="HEAD",
            failure_evidence="https://example.invalid/actions/runs/failed",
        )
        content_commit = refrozen["result"]["content_commit"]
        self.assertEqual(refrozen["result"]["previous_content_commit"], first_content_commit)
        self.assertNotEqual(content_commit, first_content_commit)
        self.assertEqual(refrozen["status"]["active"][0]["content_commit"], content_commit)
        subprocess.run(["git", "tag", "v1.1.0", content_commit], cwd=self.workspace, check=True)
        tagged = release_cohort.status(self.workspace)
        published = release_cohort.record_release(
            self.workspace,
            expected=tagged["state_token"],
            project_binding=self.binding,
            tag="v1.1.0",
            evidence="https://example.invalid/releases/v1.1.0",
        )
        candidate = published["status"]["active"][0]["candidates"][0]
        self.assertEqual(candidate["disposition"], "released-pending-reconciliation")
        with self.assertRaisesRegex(
            release_cohort.ReleaseCohortError, "still require closed-loop reconciliation"
        ):
            release_cohort.finalize(
                self.workspace,
                expected=published["status"]["state_token"],
                project_binding=self.binding,
                authorization="fixture",
            )

        self._close_cycle(direct_cycle)
        ready = release_cohort.status(self.workspace)
        finalized = release_cohort.finalize(
            self.workspace,
            expected=ready["state_token"],
            project_binding=self.binding,
            authorization="fixture",
        )
        self.assertEqual(finalized["result"]["lifecycle"], "terminal")
        self.assertEqual(finalized["status"]["active"], [])
        self.assertEqual(finalized["status"]["recent_terminal"][0]["release_tag"], "v1.1.0")
        self.assertEqual(release_cohort.status(self.workspace)["finding_count"], 0)

        checkpoint = hybrid_state.write_checkpoint(
            self.workspace, project_binding=self.binding
        )
        rebuilt = hybrid_state.rebuild_from_checkpoint(
            self.workspace,
            project_binding=self.binding,
            checkpoint=Path(checkpoint["path"]),
            output=Path(".tool-shed/rebuilt-release-cohort.sqlite3"),
        )
        self.assertEqual(rebuilt["domain_digest"], hybrid_state.audit(self.workspace)["domain_digest"])

    def test_registration_expands_to_every_open_parent_outcome(self) -> None:
        ids: dict[str, str] = {}

        def write(connection, revision):
            stamp = hybrid_state.now()
            for name in ("idea", "roadmap"):
                artifact_id = hybrid_state.random_uuid()
                cycle_id = hybrid_state.random_uuid()
                ids[f"{name}_artifact"] = artifact_id
                ids[f"{name}_cycle"] = cycle_id
                connection.execute(
                    "INSERT INTO artifact VALUES (?, ?, NULL, ?, 'sqlite', 'working', ?, ?, ?)",
                    (artifact_id, name, f"sqlite/documents/{name}", "0" * 64, stamp, stamp),
                )
                connection.execute(
                    "INSERT INTO cycle VALUES (?, ?, ?, ?, 'working', ?, NULL)",
                    (cycle_id, name, artifact_id, f"Complete {name} outcome.", stamp),
                )
                verdict_id = hybrid_state.random_uuid()
                connection.execute(
                    "INSERT INTO outcome_verdict VALUES (?, ?, ?, 'open', ?, 'fixture', ?, ?)",
                    (verdict_id, cycle_id, name, f"Open {name}.", revision, stamp),
                )
                connection.execute(
                    "INSERT INTO reconciliation VALUES (?, ?, ?, '[]', ?, 'open', ?, '[]')",
                    (hybrid_state.random_uuid(), cycle_id, revision, verdict_id, stamp),
                )
            connection.execute(
                "INSERT INTO relationship VALUES (?, ?, 'outcome-parent', ?, 'fixture', ?, NULL)",
                (
                    hybrid_state.random_uuid(), ids["roadmap_artifact"], ids["idea_artifact"],
                    revision,
                ),
            )

        hybrid_state.managed_write(
            self.workspace,
            project_binding=self.binding,
            command="create-parent-chain",
            actor="fixture",
            callback=write,
            expected_writes=9,
        )
        initial = release_cohort.status(self.workspace)
        registered = release_cohort.register(
            self.workspace,
            expected=initial["state_token"],
            project_binding=self.binding,
            commitish="HEAD",
            origin_cycles=[ids["roadmap_cycle"]],
            accepted_outcome=None,
            summary=None,
        )
        candidates = registered["status"]["active"][0]["candidates"]
        self.assertEqual(
            {item["origin_cycle_id"] for item in candidates},
            {ids["roadmap_cycle"], ids["idea_cycle"]},
        )
        self.assertEqual(registered["status"]["finding_count"], 0)
        with contextlib.closing(
            hybrid_state.connect(hybrid_state.database_path(self.workspace), writable=False)
        ) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM relationship WHERE relation_type='release-candidate-member'"
                ).fetchone()[0],
                2,
            )

    def test_terminal_pre_cohort_work2_result_gets_one_release_extension(self) -> None:
        ids: dict[str, str] = {}

        def write(connection, revision):
            stamp = hybrid_state.now()
            artifact_id = hybrid_state.random_uuid()
            cycle_id = hybrid_state.random_uuid()
            verdict_id = hybrid_state.random_uuid()
            ids.update(artifact=artifact_id, cycle=cycle_id)
            connection.execute(
                "INSERT INTO artifact VALUES (?, 'direct-work', NULL, ?, 'sqlite', 'terminal', ?, ?, ?)",
                (artifact_id, f"sqlite/outcome-capsules/{artifact_id}", "1" * 64, stamp, stamp),
            )
            connection.execute(
                "INSERT INTO cycle VALUES (?, 'direct-work', ?, ?, 'terminal', ?, ?)",
                (cycle_id, artifact_id, "Deliver the prior Work2 fix.", stamp, stamp),
            )
            connection.execute(
                "INSERT INTO outcome_verdict VALUES (?, ?, 'fixture', 'satisfied', ?, 'fixture', ?, ?)",
                (verdict_id, cycle_id, "Work2 checks passed.", revision, stamp),
            )
            connection.execute(
                "INSERT INTO reconciliation VALUES (?, ?, ?, '[]', ?, 'reconciled', ?, '[]')",
                (hybrid_state.random_uuid(), cycle_id, revision, verdict_id, stamp),
            )

        hybrid_state.managed_write(
            self.workspace,
            project_binding=self.binding,
            command="create-terminal-work2-origin",
            actor="fixture",
            callback=write,
            expected_writes=4,
        )
        initial = release_cohort.status(self.workspace)
        registered = release_cohort.register(
            self.workspace,
            expected=initial["state_token"],
            project_binding=self.binding,
            commitish="HEAD",
            origin_cycles=[ids["cycle"]],
            accepted_outcome=None,
            summary=None,
        )
        extension = registered["result"]["release_extensions"][0]
        self.assertEqual(extension["original_cycle_id"], ids["cycle"])
        self.assertNotEqual(extension["extension_cycle_id"], ids["cycle"])
        candidate = registered["status"]["active"][0]["candidates"][0]
        self.assertEqual(candidate["origin_cycle_id"], extension["extension_cycle_id"])

        repeated = release_cohort.register(
            self.workspace,
            expected=registered["status"]["state_token"],
            project_binding=self.binding,
            commitish="HEAD",
            origin_cycles=[ids["cycle"]],
            accepted_outcome=None,
            summary=None,
        )
        self.assertFalse(repeated["writes_performed"])
        with contextlib.closing(
            hybrid_state.connect(hybrid_state.database_path(self.workspace), writable=False)
        ) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM relationship WHERE relation_type='release-extension-of'"
                ).fetchone()[0],
                1,
            )


if __name__ == "__main__":
    unittest.main()
