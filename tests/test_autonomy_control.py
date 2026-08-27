from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.autonomy_control import AutonomyError, AutonomyStore, evaluate
from scripts.project_identity import ensure_project_identity


class AutonomyControlTests(unittest.TestCase):
    def make_workspace(self, root: Path, name: str = "workspace") -> Path:
        workspace = root / name
        workspace.mkdir()
        subprocess.run(["git", "init", "--quiet"], cwd=workspace, check=True)
        ensure_project_identity(workspace, project_name=name)
        return workspace

    def test_project_bound_preference_persists_and_resets(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tool-shed-autonomy-") as temporary:
            root = Path(temporary)
            workspace = self.make_workspace(root)
            preference = root / "state" / "autonomy.json"
            store = AutonomyStore(preference)

            default = store.status(workspace)
            self.assertEqual(default.level, 0)
            self.assertEqual(default.source, "default-observe")
            self.assertEqual(default.warning, "not-found")

            selected = store.set(workspace, 3)
            self.assertEqual(selected.level, 3)
            self.assertEqual(selected.name, "Checkpoint")
            self.assertEqual(selected.source, "project-bound-user-preference")
            self.assertIn("campaign-materialize", selected.as_dict()["covered_actions"])
            if os.name != "nt":
                self.assertEqual(preference.stat().st_mode & 0o777, 0o600)
                self.assertEqual(preference.parent.stat().st_mode & 0o777, 0o700)

            reset = store.reset(workspace)
            self.assertEqual(reset.level, 0)
            payload = json.loads(preference.read_text(encoding="utf-8"))
            self.assertEqual(payload["projects"], {})

    def test_copied_project_identity_does_not_transfer_preference(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tool-shed-autonomy-") as temporary:
            root = Path(temporary)
            first = self.make_workspace(root, "first")
            preference = root / "state" / "autonomy.json"
            store = AutonomyStore(preference)
            store.set(first, 5)

            second = root / "second"
            second.mkdir()
            subprocess.run(["git", "init", "--quiet"], cwd=second, check=True)
            (second / "work").mkdir()
            shutil.copy2(first / "work" / "tool-shed-project.json", second / "work" / "tool-shed-project.json")

            status = store.status(second)
            self.assertEqual(status.level, 0)
            self.assertEqual(status.warning, "project-binding-mismatch-or-malformed-entry")

    def test_malformed_state_fails_safe_and_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tool-shed-autonomy-") as temporary:
            root = Path(temporary)
            workspace = self.make_workspace(root)
            preference = root / "state" / "autonomy.json"
            preference.parent.mkdir()
            preference.write_text("not json\n", encoding="utf-8")
            store = AutonomyStore(preference)

            status = store.status(workspace)
            self.assertEqual(status.level, 0)
            self.assertEqual(status.warning, "malformed-preference")
            with self.assertRaisesRegex(AutonomyError, "refusing to overwrite malformed"):
                store.set(workspace, 2)
            self.assertEqual(preference.read_text(encoding="utf-8"), "not json\n")

    def test_evaluator_separates_level_endpoint_and_hard_boundaries(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tool-shed-autonomy-") as temporary:
            root = Path(temporary)
            workspace = self.make_workspace(root)
            status = AutonomyStore(root / "state" / "autonomy.json").status(workspace)
            common = {
                "scope": "in-scope",
                "target": "known",
                "decision": "settled",
                "provider": "allowed",
            }

            planning = evaluate(status, "roadmap-accept", endpoint="none", override_level=1, **common)
            self.assertTrue(planning["automatic"])
            self.assertEqual(planning["state_tokens"], "internal-concurrency-control")

            materialize = evaluate(status, "campaign-materialize", endpoint="none", override_level=2, **common)
            self.assertFalse(materialize["automatic"])
            self.assertEqual(materialize["outcome"], "request_authority")
            self.assertIn("requires autonomy level 3", materialize["why"])

            source_without_endpoint = evaluate(status, "source-edit", endpoint="none", override_level=5, **common)
            self.assertFalse(source_without_endpoint["automatic"])
            self.assertIn("requires work1", source_without_endpoint["why"])

            delivery = evaluate(status, "known-production-delivery", endpoint="work5", override_level=5, **common)
            self.assertTrue(delivery["automatic"])

            decision = evaluate(status, "source-edit", endpoint="work1", decision="material", override_level=5, **{key: value for key, value in common.items() if key != "decision"})
            self.assertEqual(decision["outcome"], "request_decision")
            self.assertIn("impact", decision)
            self.assertIn("blast_radius", decision)
            self.assertIn("rollback", decision)
            self.assertIn("recommendation", decision)

            provider = evaluate(status, "source-edit", endpoint="work1", provider="approval-required", override_level=5, **{key: value for key, value in common.items() if key != "provider"})
            self.assertEqual(provider["outcome"], "request_provider")

            destructive = evaluate(status, "destructive-irreversible", endpoint="work5", override_level=5, **common)
            self.assertFalse(destructive["automatic"])
            self.assertEqual(destructive["outcome"], "fail_closed")

            unknown = evaluate(status, "not-classified", endpoint="work5", override_level=5, **common)
            self.assertEqual(unknown["outcome"], "fail_closed")


if __name__ == "__main__":
    unittest.main()
