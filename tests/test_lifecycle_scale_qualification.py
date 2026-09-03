from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import closure_lineage  # noqa: E402
import document_store  # noqa: E402
import hybrid_state  # noqa: E402
import lifecycle_scale_qualification as scale  # noqa: E402
from project_identity import binding_token  # noqa: E402


class LifecycleScaleQualificationTests(unittest.TestCase):
    def test_small_accumulation_is_exact_clean_and_resumable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "fixture"
            workspace.mkdir()
            subprocess.run(["git", "init", "--quiet", "-b", "main"], cwd=workspace, check=True)
            subprocess.run(["git", "config", "user.name", "Scale Fixture"], cwd=workspace, check=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=workspace, check=True)
            identity = workspace / "work/tool-shed-project.json"
            identity.parent.mkdir(parents=True)
            identity.write_text(json.dumps({"schema_version": 1, "project_id": str(uuid.uuid4()), "project_name": "scale-fixture"}) + "\n")
            (workspace / ".gitignore").write_text("/.tool-shed/\n/tool_shed/\n")
            scenario = workspace / "tool_shed/schemas/lifecycle-qualification/v1/scenarios/QH-002.json"
            scenario.parent.mkdir(parents=True)
            shutil.copy2(ROOT / "schemas/lifecycle-qualification/v1/scenarios/QH-002.json", scenario)
            subprocess.run(["git", "add", "."], cwd=workspace, check=True)
            subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=workspace, check=True)
            binding = binding_token(workspace, operation="hybrid-state")
            hybrid_state.initialize(workspace, project_binding=binding)
            document_store.migrate(workspace, project_binding=binding)
            migration = closure_lineage.prepare_migration(workspace)
            closure_lineage.apply_migration(
                workspace, migration, expected_token=migration["manifest_token"], project_binding=binding
            )
            output = workspace / ".tool-shed/qualification/scale/result.json"
            with mock.patch.object(scale.dashboard_reporter, "safety_pass", return_value={"status": "delivered", "pending_events": 0, "writes_performed": True}):
                result = scale.run(
                workspace,
                project_binding=binding,
                candidate_commit="a" * 40,
                candidate_version="0.46.0",
                platform_name="linux-x86_64",
                instance_id="fixture-instance",
                serial_start=9000,
                lifecycle_count=2,
                minimum_history_delta=1,
                mutation_samples=1,
                output=output,
            )
            self.assertEqual(result["verdict"], "PASS", result)
            self.assertEqual(result["semantic"]["actual_documents"], 8)
            self.assertEqual(result["semantic"]["open_cycles"], 0)
            self.assertEqual(result["semantic"]["projection_mismatch_count"], 0)
            first_revision = document_store.audit(workspace)["current_revision"]
            with mock.patch.object(scale.dashboard_reporter, "safety_pass", return_value={"status": "delivered", "pending_events": 0, "writes_performed": True}):
                repeated = scale.run(
                workspace,
                project_binding=binding,
                candidate_commit="a" * 40,
                candidate_version="0.46.0",
                platform_name="linux-x86_64",
                instance_id="fixture-instance",
                serial_start=9000,
                lifecycle_count=2,
                minimum_history_delta=1,
                mutation_samples=1,
                output=output,
            )
            self.assertEqual(repeated["verdict"], "PASS")
            # Only the bounded post-scale mutation probes are new; lifecycle artifacts do not duplicate.
            self.assertEqual(repeated["semantic"]["actual_documents"], 8)
            self.assertEqual(document_store.audit(workspace)["current_revision"], first_revision + 2)


if __name__ == "__main__":
    unittest.main()
