from __future__ import annotations

from pathlib import Path
from unittest import mock
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import project_projection  # noqa: E402


class ProjectProjectionTests(unittest.TestCase):
    def test_build_resolves_authority_once_and_shares_the_exact_decision(self) -> None:
        workspace = Path("/fixture")
        authority = {
            "state": "hybrid",
            "authority": "sqlite",
            "reason": "fixture",
            "feature_limits": ["bounded-fixture"],
        }

        def summary(candidate: Path, decision: dict[str, object]) -> dict[str, int]:
            self.assertEqual(workspace, candidate)
            self.assertIs(authority, decision)
            return {"active_idea_count": 2}

        def inventory(candidate: Path, decision: dict[str, object]) -> dict[str, object]:
            self.assertEqual(workspace, candidate)
            self.assertIs(authority, decision)
            return {"total_count": 2, "truncated": False, "artifacts": []}

        with mock.patch.object(
            project_projection.authority_resolver, "resolve", return_value=authority
        ) as resolved, mock.patch.object(
            project_projection, "_summary", side_effect=summary
        ) as summarized, mock.patch.object(
            project_projection, "_inventory", side_effect=inventory
        ) as inventoried:
            result = project_projection.build(workspace)

        resolved.assert_called_once_with(workspace)
        summarized.assert_called_once_with(workspace, authority)
        inventoried.assert_called_once_with(workspace, authority)
        self.assertEqual("tool-shed-project-projection", result["kind"])
        self.assertEqual("sqlite", result["authority"]["authority"])
        self.assertEqual(["bounded-fixture"], result["authority"]["feature_limits"])
        self.assertFalse(result["writes_performed"])

    def test_build_refuses_unknown_authority_before_reading_consumers(self) -> None:
        authority = {"state": "invalid", "authority": "none", "reason": "split truth"}
        with mock.patch.object(
            project_projection.authority_resolver, "resolve", return_value=authority
        ), mock.patch.object(project_projection, "_summary") as summarized, mock.patch.object(
            project_projection, "_inventory"
        ) as inventoried:
            with self.assertRaisesRegex(project_projection.ProjectProjectionError, "split truth"):
                project_projection.build(Path("/fixture"))
        summarized.assert_not_called()
        inventoried.assert_not_called()


if __name__ == "__main__":
    unittest.main()
