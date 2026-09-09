from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import document_conversion  # noqa: E402
import hybrid_state  # noqa: E402
import outcome_loop  # noqa: E402
import release_convergence  # noqa: E402


def binding(workspace: Path) -> str:
    project_id = json.loads(
        (workspace / "work/tool-shed-project.json").read_text(encoding="utf-8")
    )["project_id"]
    value = hashlib.sha256()
    for item in ("tool-shed-binding-v1", project_id, str(workspace.resolve()), "hybrid-state"):
        value.update(item.encode())
        value.update(b"\0")
    return value.hexdigest()[:24]


class ReleaseConvergenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name) / "workspace"
        self.workspace.mkdir()
        subprocess.run(["git", "init", "--quiet"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Tool Shed Tests"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=self.workspace, check=True)
        files = {
            ".gitignore": "/.tool-shed/\n",
            "work/tool-shed-project.json": json.dumps(
                {
                    "schema_version": 1,
                    "project_id": str(uuid.uuid4()),
                    "project_name": "release-convergence-fixture",
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            "work/ideas/idea-example.md": (
                "# Example Idea\n\nStatus: promoted\nType: idea-brief\n"
                "Produces: work/maps/map-example.md\n"
            ),
            "work/maps/map-example.md": (
                "# Example Map\n\nStatus: approved\nType: project-map\n"
                "Source Idea: work/ideas/idea-example.md\n"
            ),
        }
        for relative, content in files.items():
            path = self.workspace / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=self.workspace, check=True)
        self.binding = binding(self.workspace)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_schema_chain_journal_interruption_resume_and_stale_refusal(self) -> None:
        plan = release_convergence.build_plan(self.workspace)
        self.assertEqual(plan["database"]["schema"], 0)
        self.assertTrue(plan["runtime_capability"]["mutation_ready"])
        interrupted = release_convergence.apply_plan(
            self.workspace,
            supplied_plan=plan,
            expected_token=plan["plan_token"],
            project_binding=self.binding,
            stop_after_journal="hybrid-substrate",
        )
        self.assertEqual(interrupted["state"], "interrupted")
        resumed = release_convergence.apply_plan(
            self.workspace,
            supplied_plan=plan,
            expected_token=plan["plan_token"],
            project_binding=self.binding,
        )
        self.assertEqual(resumed["final_plan"]["database"]["schema"], 6)
        self.assertEqual(resumed["state"], "deferred")
        rows = release_convergence._journal_rows(self.workspace)
        self.assertEqual(
            [row["sequence"] for row in rows],
            list(range(1, len(rows) + 1)),
        )
        self.assertEqual(rows[0]["state"], "running")
        self.assertGreaterEqual(rows[-1]["after_schema"], 6)

        repeated_plan = release_convergence.build_plan(self.workspace)
        repeated = release_convergence.apply_plan(
            self.workspace,
            supplied_plan=repeated_plan,
            expected_token=repeated_plan["plan_token"],
            project_binding=self.binding,
        )
        self.assertFalse(repeated["writes_performed"])
        (self.workspace / "work/ideas/idea-example.md").write_text(
            "# changed after planning\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(release_convergence.ConvergenceError, "stale"):
            release_convergence.apply_plan(
                self.workspace,
                supplied_plan=repeated_plan,
                expected_token=repeated_plan["plan_token"],
                project_binding=self.binding,
            )

    def test_approved_conversion_preserves_identity_relationships_and_archive(self) -> None:
        plan = release_convergence.build_plan(self.workspace)
        archive = Path(self.temporary.name) / "retained-source-archive"
        result = release_convergence.apply_plan(
            self.workspace,
            supplied_plan=plan,
            expected_token=plan["plan_token"],
            project_binding=self.binding,
            allow={"document-authority"},
            archive=archive,
        )
        self.assertEqual(result["state"], "converged")
        self.assertTrue((archive / "archive-manifest.json").is_file())
        self.assertEqual(hybrid_state.audit(self.workspace)["storage_mode"], "hybrid")
        relationships = document_conversion.build_relationship_plan(self.workspace)
        self.assertEqual(relationships["candidates"], [])
        self.assertEqual(relationships["findings"], [])

        connection = hybrid_state.connect(
            hybrid_state.database_path(self.workspace), writable=False
        )
        try:
            ids = {
                row["visible_id"]: row["id"]
                for row in connection.execute(
                    "SELECT visible_id, id FROM document ORDER BY visible_id"
                )
            }
        finally:
            connection.close()
        self.assertTrue(all(uuid.UUID(value).version == 5 for value in ids.values()))

        source = {
            "schema_version": 1,
            "kind": outcome_loop.SOURCE_KIND,
            "mode": "current",
            "project_id": json.loads(
                (self.workspace / "work/tool-shed-project.json").read_text(encoding="utf-8")
            )["project_id"],
            "authorization_ref": "fixture",
            "ambiguities": [],
            "cycle": {
                "kind": "campaign",
                "origin": {
                    "path": "work/maps/map-example.md",
                    "type": "project-map",
                },
                "accepted_outcome": "Use a deterministic imported origin.",
                "lifecycle_state": "working",
            },
            "relationships": [
                {
                    "from_artifact_key": "origin",
                    "to_artifact_id": ids["IDEA-0001"],
                    "relation_type": "related-to",
                }
            ],
            "verdict": {"disposition": "open"},
            "reconciliation": {"state": "open"},
        }
        manifest = outcome_loop._prepare_inline_source(self.workspace, source)
        validation = outcome_loop.validate_manifest(self.workspace, manifest)
        self.assertTrue(validation["valid"], validation["errors"])

    def test_runtime_failure_is_bounded_and_human_summary_matches_counts(self) -> None:
        failure = {
            "python_version": "3.11.2",
            "sqlite_version": "3.39.4",
            "read_healthy": True,
            "mutation_ready": False,
            "diagnostic_code": "SQLITE_TRUSTED_SCHEMA_TRIGGER_UNSAFE",
        }
        completed = subprocess.CompletedProcess(
            ["python"], 0, stdout=json.dumps(failure), stderr="raw unsafe detail"
        )
        with mock.patch.object(
            release_convergence.subprocess_launch, "run", return_value=completed
        ):
            probe = release_convergence.probe_runtime("python", role="background")
        self.assertEqual(
            probe["diagnostic_code"], "SQLITE_TRUSTED_SCHEMA_TRIGGER_UNSAFE"
        )
        self.assertNotIn("raw unsafe detail", json.dumps(probe))

        plan = release_convergence.build_plan(self.workspace)
        human = release_convergence.render_human(plan)
        summary = plan["summary"]
        self.assertIn(f"{summary['satisfied']} satisfied", human)
        self.assertIn(f"{summary['ready']} ready", human)
        self.assertIn(f"{summary['deferred']} deferred", human)
        self.assertIn(f"{summary['blocked']} blocked", human)


if __name__ == "__main__":
    unittest.main()
